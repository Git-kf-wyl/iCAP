"""M1 experiment: public spec assembly and a real Workflow/DeepAgent boundary.

This deliberately small prototype is not production MetaBaseAgent. In particular,
it proves invoke and buffered final-output ownership, not token streaming. The
budget helper binds native goal limits; token accounting and stop enforcement
remain separate acceptance work. Only the model provider is scripted.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from openjiuwen.agent_evolving.trajectory.processor import TrajectorySpanProcessor
from openjiuwen.core.foundation.llm import (
    AssistantMessage,
    BaseModelClient,
    ModelClientConfig,
    ModelRequestConfig,
)
from openjiuwen.core.foundation.llm.schema.message_chunk import AssistantMessageChunk
from openjiuwen.core.foundation.tool import tool
from openjiuwen.core.graph.pregel import GraphInterrupt
from openjiuwen.core.runner import Runner
from openjiuwen.core.runner.runner_config import RunnerConfig
from openjiuwen.core.session import InteractiveInput
from openjiuwen.core.session.agent import create_agent_session
from openjiuwen.core.session.checkpointer.checkpointer import CheckpointerConfig
from openjiuwen.core.single_agent.rail.base import AgentCallbackContext, AgentRail
from openjiuwen.core.single_agent.schema.agent_card import AgentCard
from openjiuwen.core.workflow import (
    BranchRouter,
    End,
    Start,
    SubWorkflowComponent,
    Workflow,
    WorkflowCard,
    WorkflowComponent,
)
from openjiuwen.harness import DeepAgent
from openjiuwen.harness.rails import AskUserRail, TaskCompletionRail
from openjiuwen.harness.rails.evolution.configuration import configure_skill_evolution
from openjiuwen.harness.schema.build_context import BuildContext
from openjiuwen.harness.schema.config import SubAgentConfig
from openjiuwen.harness.schema.deep_agent_spec import (
    BuiltinToolSpec,
    DeepAgentSpec,
    ModelSpec,
    RailSpec,
    SubAgentSpec,
    WorkspaceSpec,
    register_rail_provider,
    register_subagent_provider,
    register_tool_provider,
)
from pydantic import BaseModel, ConfigDict, Field


@dataclass
class ProbeState:
    """In-memory observations at model/tool boundaries, never a recovery store."""

    id: str = field(default_factory=lambda: uuid4().hex)
    model_calls: list[list[dict[str, Any]]] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    rail_calls: int = 0
    task_iterations: int = 0
    materialized: list[str] = field(default_factory=list)
    deep_calls: int = 0
    plugin_calls: int = 0
    child_session_ids: list[str] = field(default_factory=list)
    final_outputs: list[str] = field(default_factory=list)
    model_started: asyncio.Event = field(default_factory=asyncio.Event)
    model_cancelled: asyncio.Event = field(default_factory=asyncio.Event)


_PROBES: dict[str, ProbeState] = {}


class ProbeModelClient(BaseModelClient):
    """Registered external-model substitute, including tool calls and cancellation."""

    __client_name__ = "metaagent_m1_probe"

    def __init__(self, model_config: Any, model_client_config: Any) -> None:
        super().__init__(model_config, model_client_config)
        self.responses = deque(deepcopy(model_client_config.responses))
        self.observer = _PROBES[model_client_config.probe_id]

    async def invoke(self, messages: Any, **kwargs: Any) -> AssistantMessage:
        self.observer.model_calls.append(
            deepcopy([m.model_dump() if hasattr(m, "model_dump") else m for m in messages])
        )
        if not self.responses:
            raise AssertionError("Unexpected model call: response script exhausted")
        response = self.responses.popleft()
        if response.get("wait_until_cancelled"):
            self.observer.model_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.observer.model_cancelled.set()
                raise
        return AssistantMessage.model_validate(response)

    async def stream(self, messages: Any, **kwargs: Any) -> AsyncIterator[AssistantMessageChunk]:
        response = await self.invoke(messages, **kwargs)
        yield AssistantMessageChunk(**response.model_dump())

    async def generate_image(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def generate_speech(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def generate_video(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class BudgetSpec(BaseModel):
    max_attempts: int = Field(default=3, gt=0)
    token_budget: int = Field(default=500, gt=0)
    stop_strategy: Literal["hybrid", "agent_report", "transcript"] = "hybrid"


class EvolutionSpec(BaseModel):
    enabled: bool = False
    skills_dir: str
    auto_save: bool = False


class PrototypeMetaSpec(BaseModel):
    """Outer spec subset for this gate; unsupported production sections are rejected."""

    model_config = ConfigDict(extra="forbid")
    deep_agent: DeepAgentSpec
    checkpoint: CheckpointerConfig = Field(default_factory=CheckpointerConfig)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    evolution: EvolutionSpec


@dataclass
class ProbeBuildContext(BuildContext):
    observer: ProbeState | None = None


class ObserveRail(AgentRail):
    def __init__(self, observer: ProbeState) -> None:
        super().__init__()
        self.observer = observer

    async def before_model_call(self, ctx: AgentCallbackContext) -> None:
        self.observer.rail_calls += 1

    async def before_task_iteration(self, ctx: AgentCallbackContext) -> None:
        self.observer.task_iterations += 1


def _build_tool(params: dict[str, Any], context: ProbeBuildContext) -> Any:
    observer = context.observer
    assert observer is not None
    observer.materialized.append("tool")

    @tool(name="probe_echo", description="Return the supplied text, without external side effects.")
    def probe_echo(text: str) -> str:
        observer.tool_calls.append(text)
        return text.upper()

    return probe_echo


def _build_rail(params: dict[str, Any], context: ProbeBuildContext) -> AgentRail:
    assert context.observer is not None
    context.observer.materialized.append("rail")
    return ObserveRail(context.observer)


def _build_subagent(params: dict[str, Any], context: ProbeBuildContext) -> SubAgentConfig:
    assert context.observer is not None
    context.observer.materialized.append("subagent")
    return SubAgentConfig(
        agent_card=AgentCard(name="probe_researcher", id=f"researcher-{context.observer.id}"),
        system_prompt="Return a short research summary.",
        workspace=context.workspace,
        model=context.extras["_parent_model"],
        enable_task_loop=False,
        max_iterations=2,
    )


def make_spec(
    workspace: Path,
    state: ProbeState,
    responses: list[dict[str, Any]],
    *,
    subagents: bool = False,
    evolution: bool = False,
    ask_user: bool = False,
) -> PrototypeMetaSpec:
    """Create a serializable input fixture, using registered provider names."""
    _PROBES[state.id] = state
    register_tool_provider("metaagent.spike.echo", _build_tool)
    register_rail_provider("metaagent.spike.observe", _build_rail)
    register_rail_provider("metaagent.spike.ask_user", lambda params, context: AskUserRail())
    register_rail_provider(
        "metaagent.spike.one_round", lambda params, context: TaskCompletionRail(max_rounds=1)
    )
    register_subagent_provider("metaagent.spike.researcher", _build_subagent)
    rails = [RailSpec(type="metaagent.spike.observe")]
    if ask_user:
        rails.append(RailSpec(type="metaagent.spike.ask_user"))
    return PrototypeMetaSpec(
        deep_agent=DeepAgentSpec(
            card=AgentCard(id=f"agent-{state.id}", name="m1_dag_probe"),
            model=ModelSpec(
                model_client_config=ModelClientConfig(
                    client_provider=ProbeModelClient.__client_name__,
                    api_key="local-placeholder",
                    api_base="https://spike.invalid/v1",
                    probe_id=state.id,
                    responses=responses,
                ),
                model_request_config=ModelRequestConfig(model="scripted-m1"),
            ),
            workspace=WorkspaceSpec(root_path=str(workspace), language="en"),
            system_prompt="Use the available tools when asked. Keep the final answer concise.",
            tools=[BuiltinToolSpec(type="metaagent.spike.echo")],
            rails=rails,
            subagents=[
                SubAgentSpec(
                    agent_card=AgentCard(name="probe_researcher"),
                    system_prompt="Research the request.",
                    factory_name="metaagent.spike.researcher",
                )
            ]
            if subagents
            else [],
            enable_task_loop=False,
            enable_sys_operation=False,
            enable_read_image_multimodal=False,
            max_iterations=4,
            language="en",
        ),
        evolution=EvolutionSpec(enabled=evolution, skills_dir=str(workspace / "skills")),
    )


def runner_config(spec: PrototypeMetaSpec) -> RunnerConfig:
    """Must be applied before Runner.start: checkpointer selection is process-wide."""
    return RunnerConfig(distributed_mode=False, checkpointer_config=spec.checkpoint)


def assemble(spec: PrototypeMetaSpec, state: ProbeState) -> DeepAgent:
    """Accept the outer spec and materialize native provider-backed capabilities."""
    if spec.budget.stop_strategy != "hybrid":
        raise NotImplementedError("Native TaskCompletionRail has no public stop-strategy injection")
    agent = spec.deep_agent.build(context=ProbeBuildContext(observer=state))
    if spec.evolution.enabled:
        Path(spec.evolution.skills_dir).mkdir(parents=True, exist_ok=True)
        configure_skill_evolution(
            agent,
            skills_dir=spec.evolution.skills_dir,
            llm=agent.deep_config.model,
            model="scripted-m1",
            trajectory_span_processor=TrajectorySpanProcessor(),
            auto_save=spec.evolution.auto_save,
            language="en",
        )
    return agent


async def bind_goal_budget(
    agent: DeepAgent, spec: PrototypeMetaSpec, session: Any, objective: str
) -> Any:
    """Prove native goal-record binding, not budget enforcement during model calls."""
    await agent.start(session=session)
    assert agent.goal_manager is not None
    existing = await agent.goal_manager.get()
    if existing is not None:
        return existing
    return await agent.goal_manager.set(
        objective, max_attempts=spec.budget.max_attempts, token_budget=spec.budget.token_budget
    )


class DeepAgentComponent(WorkflowComponent):
    """Buffer an invoke result; bridge native agent interruption to workflow interaction."""

    def __init__(self, agent: DeepAgent, state: ProbeState) -> None:
        super().__init__()
        self.agent, self.state = agent, state

    async def invoke(self, inputs: dict[str, Any], session: Any, context: Any) -> dict[str, Any]:
        child_id = f"{session.get_session_id()}::deep"
        self.state.child_session_ids.append(child_id)
        child = create_agent_session(
            session_id=child_id, card=self.agent.card, parent_session_id=session.get_session_id()
        )
        pending = session.get_state("pending_child")
        query: Any = inputs["query"]
        if pending:
            answer = await session.interact(pending)
            query = InteractiveInput()
            for interrupt_id in pending["interrupt_ids"]:
                query.update(interrupt_id, answer)
        self.state.deep_calls += 1
        result = await Runner.run_agent(self.agent, {"query": query}, session=child)
        if result.get("result_type") == "interrupt":
            pending = {"interrupt_ids": result["interrupt_ids"], "prompt": "Provide a response"}
            session.update_state({"pending_child": pending})
            await session.interact(pending)
            raise RuntimeError("An initial interaction must suspend before continuing")
        if result.get("result_type") != "answer":
            raise RuntimeError(f"Unrecognized child result: {result}")
        session.update_state({"pending_child": None})
        session.update_global_state({"selected_answer": result["output"]})
        return {"answer": result["output"]}


class OrdinaryPluginError(Exception):
    """The one explicitly classified business exception in this experiment."""


class PluginComponent(WorkflowComponent):
    def __init__(self, state: ProbeState, mode: str) -> None:
        super().__init__()
        self.state, self.mode = state, mode

    async def invoke(self, inputs: dict[str, Any], session: Any, context: Any) -> dict[str, Any]:
        self.state.plugin_calls += 1
        if self.mode == "exception":
            raise OrdinaryPluginError("BUSINESS_REJECTED")
        if self.mode == "interrupt":
            answer = await session.interact("Approve the plugin result")
            return {"answer": f"plugin:{answer}"}
        if self.mode == "failure":
            # An explicit business failure is ordinary data, not a graph failure.
            return {"ok": False, "error": "BUSINESS_REJECTED"}
        return {"ok": True, "answer": "plugin:ok"}


class PluginOutcomeComponent(SubWorkflowComponent):
    """Keep the native graph-invoker contract and avoid treating pauses as failure."""

    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, Any]:
        try:
            result = await super().invoke(inputs, session, context)
        except (GraphInterrupt, asyncio.CancelledError):
            raise
        except Exception as error:
            # The kernel preserves its component failure as a chained cause.
            # Only our declared business error is eligible for fallback here.
            cause: BaseException | None = error
            seen: set[int] = set()
            while cause is not None and id(cause) not in seen:
                seen.add(id(cause))
                if isinstance(cause, OrdinaryPluginError):
                    return {"ok": False, "error": "BUSINESS_REJECTED"}
                cause = cause.__cause__
            raise
        outcome = result["output"]
        if outcome.get("ok", True):
            session.update_global_state({"selected_answer": outcome["answer"]})
            return {"ok": True, "answer": outcome["answer"]}
        return {"ok": False, "error": outcome["error"]}


class MergeComponent(WorkflowComponent):
    def __init__(self, state: ProbeState) -> None:
        super().__init__()
        self.state = state

    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, Any]:
        answer = session.get_global_state("selected_answer")
        self.state.final_outputs.append(answer)
        return {"answer": answer}


def build_dag(
    agent: DeepAgent, state: ProbeState, *, route: str = "harness", plugin_mode: str = "success"
) -> Workflow:
    """Compile real conditional edges and a native nested plugin workflow."""
    plugin = Workflow(card=WorkflowCard(id=f"plugin-{state.id}", name="probe_plugin"))
    plugin.set_start_comp("start", Start(), inputs_schema={"query": "${query}"})
    plugin.add_workflow_comp("run", PluginComponent(state, plugin_mode))
    plugin.set_end_comp(
        "end",
        End(),
        inputs_schema={"ok": "${run.ok}", "answer": "${run.answer}", "error": "${run.error}"},
    )
    plugin.add_connection("start", "run")
    plugin.add_connection("run", "end")

    graph = Workflow(card=WorkflowCard(id=f"dag-{state.id}", name="m1_metaagent_dag"))
    graph.set_start_comp("start", Start(), inputs_schema={"query": "${query}"})
    graph.add_workflow_comp(
        "plugin", PluginOutcomeComponent(plugin), inputs_schema={"query": "${start.query}"}
    )
    graph.add_workflow_comp(
        "harness", DeepAgentComponent(agent, state), inputs_schema={"query": "${start.query}"}
    )
    graph.add_workflow_comp("merge", MergeComponent(state))
    graph.set_end_comp("end", End(), inputs_schema={"answer": "${merge.answer}"})
    dispatch = BranchRouter()
    dispatch.add_branch(lambda: route == "plugin", "plugin")
    dispatch.add_branch(lambda: True, "harness")
    outcome = BranchRouter()
    outcome.add_branch("${plugin.ok} == True", "merge")
    outcome.add_branch(lambda: True, "harness")
    graph.add_conditional_connection("start", dispatch)
    graph.add_conditional_connection("plugin", outcome)
    graph.add_connection("harness", "merge")
    graph.add_connection("merge", "end")
    return graph
