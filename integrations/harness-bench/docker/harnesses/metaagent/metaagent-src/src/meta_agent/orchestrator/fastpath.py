"""Native subworkflows return outcomes before the DAG chooses fallback."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from typing import Any

from openjiuwen.core.graph.pregel import GraphInterrupt
from openjiuwen.core.workflow import (
    BranchRouter,
    End,
    Start,
    SubWorkflowComponent,
    Workflow,
    WorkflowCard,
    WorkflowComponent,
)

from meta_agent.checkpoint.native import NATIVE_RUN
from meta_agent.errors import ControlFlowError, MetaAgentError, PluginFailure
from meta_agent.orchestrator.dag import DeepAgentComp
from meta_agent.registry import MetaRegistry, PluginWorkflow
from meta_agent.routing import FastPathRouter, RouteDecision
from meta_agent.spec.fastpath import PluginError, PluginOutcome, WorkflowPluginManifest


class RouterComp(WorkflowComponent):  # type: ignore[misc]
    def __init__(
        self,
        router: FastPathRouter,
        on_route: Callable[[RouteDecision], Any],
        fixed_decision: RouteDecision | None = None,
    ) -> None:
        super().__init__()
        self.router, self.on_route = router, on_route
        self.fixed_decision = fixed_decision

    async def invoke(self, inputs: dict[str, Any], session: Any, context: Any) -> dict[str, Any]:
        decision = self.fixed_decision or await self.router.route(
            inputs["query"], inputs["route_context"], session.get_session_id()
        )
        session.update_global_state(
            {
                "__route_decision__": decision.as_dict(),
                "__fastpath_partial__": None,
                "__meta_result__": None,
            }
        )
        notified = self.on_route(decision)
        if inspect.isawaitable(notified):
            await notified
        return {"plugin": decision.plugin or ""}


def _causes(error: BaseException) -> list[BaseException]:
    result = []
    seen = set()
    pending = [error]
    while pending:
        cause = pending.pop()
        if id(cause) in seen:
            continue
        seen.add(id(cause))
        result.append(cause)
        # A wrapper without ``raise ... from`` still carries a control failure
        # in __context__; suppressing its traceback must not permit fallback.
        if cause.__context__ is not None:
            pending.append(cause.__context__)
        if cause.__cause__ is not None:
            pending.append(cause.__cause__)
    return result


class FastPathOutcomeComp(SubWorkflowComponent):  # type: ignore[misc]
    def __init__(
        self,
        graph: PluginWorkflow,
        manifest: WorkflowPluginManifest,
        digest: str,
        router: FastPathRouter,
        on_outcome: Callable[[str, str, str], None],
    ) -> None:
        super().__init__(graph)
        self.manifest, self.digest, self.router = manifest, digest, router
        self.on_outcome = on_outcome

    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, str]:
        name = self.manifest.name
        try:
            result = await super().invoke(inputs, session, context)
        except BaseException as error:
            chain = _causes(error)
            if any(
                isinstance(e, (ControlFlowError, GraphInterrupt, asyncio.CancelledError))
                for e in chain
            ):
                outcome_name = (
                    "interrupted"
                    if any(isinstance(e, GraphInterrupt) for e in chain)
                    else "control"
                )
                self.router.on_result(name, outcome_name)
                self.on_outcome(name, outcome_name, getattr(error, "code", ""))
                raise
            ordinary = next((e for e in chain if isinstance(e, PluginFailure)), None)
            if ordinary is None:
                self.router.on_result(name, "error")
                raise
            outcome = PluginOutcome(
                status="failed",
                error=PluginError(
                    code=ordinary.code,
                    message=ordinary.message,
                    exception_type=type(ordinary).__name__,
                ),
                partial=ordinary.partial,
                completed_operations=ordinary.completed_operations,
            )
        else:
            outcome = PluginOutcome.model_validate(result["output"]["result"])
        durable = NATIVE_RUN.get()
        operations = None
        if durable is not None:
            # A custom node can catch a tool error and return an ordinary outcome.
            # Never let that turn an uncertain write into success or model fallback.
            operations = await durable.executor.confirmed_operations()
            outcome = outcome.model_copy(
                update={"completed_operations": [op["operation_id"] for op in operations]}
            )
        # A successful serialization is required before any result is published.
        json.dumps(outcome.model_dump(), allow_nan=False)
        if outcome.status == "success":
            session.update_global_state(
                {
                    "__meta_result__": {
                        "answer": outcome.output,
                        "data": outcome.data,
                        "result_type": "answer",
                        "error": None,
                    }
                }
            )
            self.router.on_result(name, "success")
            self.on_outcome(name, "success", "")
            return {"next": "merge"}
        error_data = outcome.error
        assert error_data is not None
        partial = {
            "plugin": name,
            "version": self.manifest.version,
            "digest": self.digest,
            "graph_version": self.router.graph_version,
            "execution_id": inputs["inputs"]["execution_id"],
            "partial": outcome.partial,
            "data": outcome.data,
            "completed_operations": outcome.completed_operations,
            "error": error_data.model_dump(),
        }
        if operations is not None:
            partial["durable_operations"] = operations
        session.update_global_state({"__fastpath_partial__": partial})
        terminal = not self.manifest.fallback_to_harness or bool(
            {error_data.code, error_data.exception_type} & set(self.manifest.fallback_whitelist)
        )
        status = "terminal" if terminal else "failed"
        self.router.on_result(name, status)
        self.on_outcome(name, status, error_data.code)
        if terminal:
            session.update_global_state(
                {
                    "__meta_result__": {
                        "answer": error_data.message,
                        "data": outcome.data,
                        "result_type": "error",
                        "error": error_data.model_dump(),
                    }
                }
            )
        return {"next": "merge" if terminal else "deep"}


class MergeComp(WorkflowComponent):  # type: ignore[misc]
    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, Any]:
        result = session.get_global_state("__meta_result__")
        if not isinstance(result, dict):
            raise MetaAgentError("META_RESULT_MISSING", "Selected path produced no final result.")
        return result


async def build_dual_dag(
    component: DeepAgentComp,
    workflow_id: str,
    registry: MetaRegistry,
    router: FastPathRouter,
    on_route: Callable[[RouteDecision], Any],
    on_outcome: Callable[[str, str, str], None],
    *,
    fixed_decision: RouteDecision | None = None,
) -> Workflow:
    plugins = await registry.build(workflow_id)
    graph = Workflow(card=WorkflowCard(id=workflow_id, name="meta_agent_dual"))
    graph.set_start_comp(
        "start",
        Start(),
        inputs_schema={
            "query": "${query}",
            "route_context": "${route_context}",
            "execution_id": "${execution_id}",
        },
    )
    graph.add_workflow_comp(
        "router",
        RouterComp(router, on_route, fixed_decision),
        inputs_schema={"query": "${start.query}", "route_context": "${start.route_context}"},
    )
    graph.add_connection("start", "router")
    dispatch = BranchRouter()
    for package in registry.packages:
        manifest = package.manifest
        node_id = f"wp_{manifest.name}"
        graph.add_workflow_comp(
            node_id,
            FastPathOutcomeComp(
                plugins[manifest.name], manifest, package.digest, router, on_outcome
            ),
            inputs_schema={
                "query": "${start.query}",
                "context": "${start.route_context}",
                "execution_id": "${start.execution_id}",
            },
        )
        dispatch.add_branch(f"${{router.plugin}} == '{manifest.name}'", node_id)
        outcome_router = BranchRouter()
        outcome_router.add_branch(f"${{{node_id}.next}} == 'merge'", "merge")
        outcome_router.add_branch(lambda: True, "deep")
        graph.add_conditional_connection(node_id, outcome_router)
    dispatch.add_branch(lambda: True, "deep")
    graph.add_conditional_connection("router", dispatch)
    graph.add_workflow_comp("deep", component, inputs_schema={"query": "${start.query}"})
    graph.add_workflow_comp("merge", MergeComp(), wait_for_all=False)
    graph.add_connection("deep", "merge")
    graph.set_end_comp(
        "end",
        End(),
        inputs_schema={
            "answer": "${merge.answer}",
            "data": "${merge.data}",
            "result_type": "${merge.result_type}",
            "error": "${merge.error}",
            "__meta_final__": workflow_id,
        },
    )
    graph.add_connection("merge", "end")
    return graph


def draw_dag(names: list[str]) -> str:
    if not names:
        return "flowchart LR\n  start[Start] --> deep[DeepAgentComp] --> end[End]\n"
    lines = [
        "flowchart LR",
        "  start[Start] --> router[Router]",
        "  router -->|miss| deep[DeepAgentComp]",
        "  deep --> merge[Merge]",
        "  merge --> end[End]",
    ]
    for name in names:
        node = f"wp_{name}"
        lines.extend(
            [
                f'  router -->|match| {node}["{name}"]',
                f"  {node} -->|success or terminal error| merge",
                f"  {node} -->|ordinary fallback| deep",
            ]
        )
    return "\n".join(lines) + "\n"
