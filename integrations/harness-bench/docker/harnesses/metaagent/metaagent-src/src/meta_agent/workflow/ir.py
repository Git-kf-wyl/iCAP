"""Assemble local IR v1 with native components; OpenJiuwen owns execution."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from typing import Any, Literal, Self

from openjiuwen.core.runner import Runner
from openjiuwen.core.workflow import (
    BranchComponent,
    End,
    EndConfig,
    HttpComponentConfig,
    HTTPRequestComponent,
    IntentDetectionCompConfig,
    IntentDetectionComponent,
    LLMCompConfig,
    LLMComponent,
    LoopBreakComponent,
    LoopComponent,
    LoopGroup,
    LoopSetVariableComponent,
    QuestionerComponent,
    QuestionerConfig,
    Start,
    SubWorkflowComponent,
    ToolComponent,
    ToolComponentConfig,
    Workflow,
    WorkflowCard,
)
from openjiuwen.core.workflow.components.llm.react.react_component import ReActAgentComp
from openjiuwen.core.workflow.components.llm.react.react_config import ReActAgentCompConfig
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from meta_agent.errors import BootError
from meta_agent_adapter import fusionmind_model as _fusionmind_model  # noqa: F401

NodeType = Literal[
    "start",
    "end",
    "branch",
    "loop",
    "loop_break",
    "loop_set_variable",
    "subworkflow",
    "llm",
    "intent_detection",
    "questioner",
    "react_agent",
    "tool",
    "http",
]


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkflowBranch(_Schema):
    condition: str = Field(min_length=1)
    target: str | list[str]


class WorkflowNode(_Schema):
    id: str = Field(min_length=1)
    type: NodeType
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    branches: list[WorkflowBranch] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    wait_for_all: bool = False


class WorkflowEdge(_Schema):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)


class LoopBody(_Schema):
    """LoopGroup is a container, not an additional executable node."""

    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    start_nodes: list[str] = Field(min_length=1)
    end_nodes: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_body(self) -> Self:
        _validate_nodes(self.nodes, self.edges, in_loop=True)
        ids = {node.id for node in self.nodes}
        if not set(self.start_nodes + self.end_nodes) <= ids:
            raise ValueError("LoopGroup entry/exit must reference body nodes")
        if any(n.type in {"start", "end", "loop"} for n in self.nodes):
            raise ValueError(
                "LoopGroup uses entry/exit IDs; native direct nested loops are unsupported"
            )
        return self


class LoopConfig(_Schema):
    body: LoopBody
    output_schema: dict[str, Any]


class SubWorkflowConfig(_Schema):
    workflow: WorkflowIR


class SetVariableConfig(_Schema):
    variable_mapping: dict[str, Any] = Field(min_length=1)


class WorkflowIR(_Schema):
    schema_version: Literal[1]
    name: str = Field(default="MetaAgent workflow", min_length=1)
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        _validate_nodes(self.nodes, self.edges, in_loop=False)
        if sum(n.type == "start" for n in self.nodes) != 1:
            raise ValueError("Workflow requires one Start")
        if sum(n.type == "end" for n in self.nodes) != 1:
            raise ValueError("Workflow requires one End")
        return self


_CONFIGS: dict[str, Any] = {
    "end": EndConfig,
    "llm": LLMCompConfig,
    "intent_detection": IntentDetectionCompConfig,
    "questioner": QuestionerConfig,
    "react_agent": ReActAgentCompConfig,
    "http": HttpComponentConfig,
    "tool": ToolComponentConfig,
    "loop": LoopConfig,
    "subworkflow": SubWorkflowConfig,
    "loop_set_variable": SetVariableConfig,
}


def _config(node: WorkflowNode) -> Any:
    if node.type == "end" and not node.config:
        return None
    cls = _CONFIGS.get(node.type)
    if cls is None:
        if node.config:
            raise ValueError(f"{node.type} does not take config")
        return None
    if is_dataclass(cls):
        keys = {f.name for f in fields(cls)}
    else:
        keys = set(cls.model_fields)
        keys.update(f.alias for f in cls.model_fields.values() if f.alias)
    if node.config.keys() - keys:
        raise ValueError(f"Unknown {node.type} config field")
    return TypeAdapter(cls).validate_python(node.config)


def _validate_nodes(nodes: list[WorkflowNode], edges: list[WorkflowEdge], *, in_loop: bool) -> None:
    ids = {n.id for n in nodes}
    if len(ids) != len(nodes):
        raise ValueError("Node IDs must be unique within a graph")
    for edge in edges:
        if edge.source not in ids or edge.target not in ids:
            raise ValueError("Edge references an unknown node")
    for node in nodes:
        if node.type in {"loop_break", "loop_set_variable"} and not in_loop:
            raise ValueError("Loop control components require a LoopGroup")
        if node.tools and node.type != "react_agent":
            raise ValueError("Only react_agent takes tools; tool uses config.tool_id")
        if node.type in {"branch", "intent_detection"}:
            if not node.branches or any(e.source == node.id for e in edges):
                raise ValueError("Branch nodes use branches instead of outgoing edges")
        elif node.branches:
            raise ValueError("Only branch and intent_detection accept branches")
        for branch in node.branches:
            targets = [branch.target] if isinstance(branch.target, str) else branch.target
            if not targets or not set(targets) <= ids:
                raise ValueError("Branch references an unknown node")
        config = _config(node)
        if node.type == "tool" and not config.tool_id:
            raise ValueError("Tool node requires config.tool_id")


SubWorkflowConfig.model_rebuild()


def parse_workflow_ir(data: dict[str, Any]) -> WorkflowIR:
    try:
        return WorkflowIR.model_validate(data)
    except (ValueError, TypeError) as error:
        raise BootError("META_WORKFLOW_IR", "Invalid Workflow IR configuration") from error


def _tool(name: str, tools: dict[str, Any]) -> Any:
    tool = tools.get(name) or Runner.resource_mgr.get_tool(tool_id=name)
    if tool is None:
        raise BootError(
            "META_WORKFLOW_TOOL_NOT_BOUND", f"Register native tool '{name}' before boot"
        )
    return tool


def _component(node: WorkflowNode, workflow_id: str, tools: dict[str, Any]) -> Any:
    config = _config(node)
    if node.type == "start":
        return Start()
    if node.type == "end":
        return End(config)
    if node.type == "branch":
        component = BranchComponent()
    elif node.type == "intent_detection":
        component = IntentDetectionComponent(config)
    elif node.type == "loop":
        group = LoopGroup()
        _assemble(group, config.body.nodes, config.body.edges, workflow_id, tools)
        group.start_nodes(config.body.start_nodes)
        group.end_nodes(config.body.end_nodes)
        return LoopComponent(group, config.output_schema)
    elif node.type == "loop_break":
        return LoopBreakComponent()
    elif node.type == "loop_set_variable":
        return LoopSetVariableComponent(config.variable_mapping)
    elif node.type == "subworkflow":
        return SubWorkflowComponent(_compile(config.workflow, f"{workflow_id}-{node.id}", tools))
    elif node.type == "tool":
        return ToolComponent(ToolComponentConfig()).bind_tool(_tool(config.tool_id, tools))
    elif node.type == "react_agent":
        component = ReActAgentComp(config)
        for name in node.tools:
            # Host owns the native resource registration and its lifecycle.
            component.executable.ability_manager.add(_tool(name, tools).card)
        return component
    else:
        return {
            "llm": LLMComponent,
            "questioner": QuestionerComponent,
            "http": HTTPRequestComponent,
        }[node.type](config)
    for branch in node.branches:
        component.add_branch(branch.condition, branch.target)
    return component


def _assemble(
    graph: Any,
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
    workflow_id: str,
    tools: dict[str, Any],
) -> None:
    for node in nodes:
        component = _component(node, workflow_id, tools)
        kwargs = {
            "inputs_schema": node.inputs if node.inputs is not None else {},
            "outputs_schema": node.outputs,
        }
        if node.type == "start":
            graph.set_start_comp(node.id, component, **kwargs)
        elif node.type == "end":
            graph.set_end_comp(node.id, component, **kwargs)
        else:
            graph.add_workflow_comp(node.id, component, wait_for_all=node.wait_for_all, **kwargs)
    for edge in edges:
        graph.add_connection(edge.source, edge.target)


def _compile(spec: WorkflowIR, workflow_id: str, tools: dict[str, Any]) -> Any:
    graph = Workflow(card=WorkflowCard(id=workflow_id, name=spec.name))
    _assemble(graph, spec.nodes, spec.edges, workflow_id, tools)
    return graph


def compile_workflow(
    data: dict[str, Any], *, workflow_id: str, tools: dict[str, Any] | None = None
) -> Workflow:
    """Host registers native tools; OpenJiuwen executes them."""
    return _compile(parse_workflow_ir(data), workflow_id, tools or {})


def draw_workflow_ir(data: dict[str, Any]) -> str:
    """Offline top-level diagram; no runtime tools or model services needed."""
    spec = parse_workflow_ir(data)
    names = {n.id: f"n{i}" for i, n in enumerate(spec.nodes)}
    lines = ["flowchart TD"]
    for node in spec.nodes:
        label = json.dumps(f"{node.id}: {node.type}", ensure_ascii=True)
        lines.append(f"  {names[node.id]}[{label}]")
        for branch in node.branches:
            for target in [branch.target] if isinstance(branch.target, str) else branch.target:
                lines.append(f"  {names[node.id]} -.-> {names[target]}")
    lines += [f"  {names[e.source]} --> {names[e.target]}" for e in spec.edges]
    return "\n".join(lines)
