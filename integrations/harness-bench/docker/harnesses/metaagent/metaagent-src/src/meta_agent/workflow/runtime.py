"""A loaded native Workflow, independent of DeepAgent, models and Skills.

This local entry point runs one invocation at a time and shares the existing
managed Runner. Request IDs correlate calls; they are not an idempotency key.
Interactive resume uses the native in-memory checkpoint; durable recovery is separate.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from types import TracebackType
from typing import Any, Literal, Self
from uuid import uuid4

from openjiuwen.core.common.constants.constant import INTERACTION
from openjiuwen.core.context_engine import ContextEngine, ContextEngineConfig
from openjiuwen.core.runner import Runner
from openjiuwen.core.session import InteractiveInput
from openjiuwen.core.session.checkpointer import CheckpointerFactory
from openjiuwen.core.session.checkpointer.checkpointer import CheckpointerConfig
from openjiuwen.core.workflow import Workflow, WorkflowExecutionState
from openjiuwen.extensions.observability.config import ObservabilityConfig
from pydantic import JsonValue, TypeAdapter, ValidationError

from meta_agent.errors import SessionStateError
from meta_agent.identity import ExecutionIdentity
from meta_agent.lifecycle import acquire_runner, release_runner
from meta_agent.orchestrator.dag import interaction_payload
from meta_agent.routing import RouteDecision
from meta_agent.spec.platform import PackageServicesConfig
from meta_agent.trace.execution import execution_trace
from meta_agent.trace.trajectory import acquire_tracing, release_tracing
from meta_agent.workflow.services import WorkflowServices

_JSON_VALUE: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)  # type: ignore[arg-type]


@dataclass(frozen=True)
class WorkflowResult:
    """The native End output, kept as JSON data rather than rendered text."""

    output: JsonValue
    identity: ExecutionIdentity
    state: Literal["COMPLETED", "INPUT_REQUIRED"] = "COMPLETED"
    interactions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def result_type(self) -> Literal["answer", "input_required"]:
        """Use the existing execution trace's result contract."""
        return "input_required" if self.state == "INPUT_REQUIRED" else "answer"


class MetaWorkflowRuntime:
    """Run a trusted native Workflow. Always close it or use ``async with``."""

    def __init__(
        self, workflow: Workflow, *, product_id: str, agent_id: str, package_digest: str
    ) -> None:
        self.workflow = workflow
        self.product_id = product_id
        self.agent_id = agent_id
        self.package_digest = package_digest
        self._runtime_id = uuid4().hex
        self._sessions: set[str] = set()
        self._pending: dict[str, tuple[str, list[str]]] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        self._runner_owned = False
        self._tracing_owned = False
        self._services: WorkflowServices | None = None
        self._context_engine: ContextEngine | None = None

    @classmethod
    async def create(
        cls,
        workflow: Workflow | Callable[[dict[str, Any]], Workflow],
        *,
        agent_id: str,
        product_id: str = "local",
        package_digest: str = "",
        observability: ObservabilityConfig | None = None,
        services: PackageServicesConfig | None = None,
        context_engine_config: ContextEngineConfig | None = None,
    ) -> Self:
        if not isinstance(workflow, Workflow) and not callable(workflow):
            raise TypeError("workflow must be an OpenJiuwen Workflow")
        # Validate identity before allocating shared kernel resources.
        try:
            ExecutionIdentity(product_id, agent_id, "host", "host", "host")
        except ValueError as error:
            raise SessionStateError(
                "META_WORKFLOW_IDENTITY", "Workflow identity fields must not be blank"
            ) from error
        config = services or PackageServicesConfig()
        if config.context_service is not None:
            raise SessionStateError(
                "META_CONTEXT_UNSUPPORTED",
                "ContextService final-window binding supports the DeepAgent path only",
            )
        bindings = WorkflowServices(config, product_id, agent_id)
        runtime = None
        try:
            bindings.register()
            graph = workflow(bindings.tools) if callable(workflow) else workflow
            if not isinstance(graph, Workflow):
                raise TypeError("Workflow builder must return an OpenJiuwen Workflow")
            runtime = cls(
                graph, product_id=product_id, agent_id=agent_id, package_digest=package_digest
            )
            runtime._services = bindings
            if context_engine_config is not None:
                runtime._context_engine = ContextEngine(context_engine_config)
            await acquire_runner(CheckpointerConfig(type="in_memory", conf={}))
            runtime._runner_owned = True
            if observability is not None and observability.enabled:
                acquire_tracing(observability)
                runtime._tracing_owned = True
        except BaseException:
            await bindings.close()
            if runtime is not None and runtime._runner_owned:
                await runtime.close()
            raise
        return runtime

    async def invoke(
        self,
        inputs: dict[str, Any],
        *,
        session_id: str,
        request_id: str | None = None,
        selected_route: RouteDecision | None = None,
    ) -> WorkflowResult:
        try:
            identity = ExecutionIdentity(
                self.product_id,
                self.agent_id,
                session_id,
                uuid4().hex if request_id is None else request_id,
                uuid4().hex,
            )
        except ValueError as error:
            raise SessionStateError(
                "META_WORKFLOW_IDENTITY", "Workflow identity fields must not be blank"
            ) from error
        async with self._lock:
            if self._closed:
                raise SessionStateError("META_WORKFLOW_CLOSED", "Workflow runtime is closed")
            native_session = f"workflow-{self._runtime_id}-{identity.child_session_id}"
            self._sessions.add(native_session)
            native_inputs: Any = inputs
            resuming = session_id in self._pending
            if resuming:
                execution_id, interaction_ids = self._pending[session_id]
                if "answer" not in inputs:
                    raise SessionStateError(
                        "META_INPUT_INVALID", "Pending Workflow requires answer"
                    )
                answer = inputs["answer"]
                if isinstance(answer, dict) and "answers" in answer:
                    answers = answer["answers"]
                elif len(interaction_ids) == 1:
                    answers = {interaction_ids[0]: answer}
                else:
                    raise SessionStateError(
                        "META_INPUT_INVALID", "Supply answers by interaction ID"
                    )
                if not isinstance(answers, dict) or set(answers) != set(interaction_ids):
                    raise SessionStateError(
                        "META_INPUT_INVALID", "Answer all pending interaction IDs"
                    )
                native_inputs = InteractiveInput()
                for key, value in answers.items():
                    native_inputs.update(key, value)
                identity = replace(identity, execution_id=execution_id)
            if self._services is not None:
                self._services.identity = identity
            context = (
                await self._context_engine.create_context(context_id=native_session)
                if self._context_engine is not None
                else None
            )
            with execution_trace(
                identity, inputs, package_digest=self.package_digest, skill_digest="", team={}
            ) as trace:
                if selected_route is not None:
                    trace.route(selected_route, resumed=resuming)
                if trace.span is not None:
                    trace.span.set_attributes(
                        {"meta.runtime.mode": "workflow", "gen_ai.operation.name": "workflow"}
                    )
                try:
                    raw = await Runner.run_workflow(
                        self.workflow, native_inputs, session=native_session, context=context
                    )
                except Exception as error:
                    raise SessionStateError(
                        "META_WORKFLOW_FAILED", "Native Workflow execution failed"
                    ) from error
                if raw is None:
                    raise SessionStateError("META_KERNEL_PROTOCOL", "Workflow returned no result")
                if raw.state == WorkflowExecutionState.INPUT_REQUIRED:
                    interactions = [
                        interaction_payload(c) for c in raw.result if c.type == INTERACTION
                    ]
                    self._pending[session_id] = (
                        identity.execution_id,
                        [item["id"] for item in interactions],
                    )
                    result = WorkflowResult(None, identity, "INPUT_REQUIRED", interactions)
                    trace.result = result
                    return result
                if raw.state != WorkflowExecutionState.COMPLETED:
                    raise SessionStateError(
                        "META_WORKFLOW_FAILED", "Native Workflow did not complete"
                    )
                # Unwrap only the native End envelope, never nested business fields.
                output = raw.result
                if isinstance(output, dict) and set(output) == {"output"}:
                    output = output["output"]
                try:
                    payload = _JSON_VALUE.validate_python(output, strict=True)
                except ValidationError as error:
                    raise SessionStateError(
                        "META_WORKFLOW_OUTPUT", "Workflow output must be JSON data"
                    ) from error
                result = WorkflowResult(payload, identity)
                self._pending.pop(session_id, None)
                trace.result = result
                return result

    async def close_session(self, session_id: str) -> bool:
        identity = ExecutionIdentity(self.product_id, self.agent_id, session_id, "close", "close")
        native_session = f"workflow-{self._runtime_id}-{identity.child_session_id}"
        async with self._lock:
            if native_session not in self._sessions:
                return False
            await CheckpointerFactory.get_checkpointer().release(native_session)
            if self._context_engine is not None:
                await self._context_engine.clear_context(
                    context_id=native_session, session_id="default_session_id"
                )
            self._sessions.remove(native_session)
            self._pending.pop(session_id, None)
            return True

    async def close(self) -> None:
        """Release this runtime's sessions and its share of the native Runner."""
        async with self._lock:
            self._closed = True
            if not self._runner_owned:
                return
            for session_id in tuple(self._sessions):
                await CheckpointerFactory.get_checkpointer().release(session_id)
                self._sessions.remove(session_id)
            self._pending.clear()
            if self._context_engine is not None:
                await self._context_engine.clear_context()
            if self._services is not None:
                await self._services.close()
            if self._tracing_owned:
                release_tracing()
                self._tracing_owned = False
            await release_runner()
            self._runner_owned = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
