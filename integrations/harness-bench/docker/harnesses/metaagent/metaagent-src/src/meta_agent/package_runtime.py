"""Select an existing native runtime once per new package request.

There is no second DAG executor here. Hybrid routing uses FastPathRouter, native
Workflow execution uses MetaWorkflowRuntime, and DeepAgent uses MetaBaseAgent.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Literal, Self
from uuid import uuid4

from openjiuwen.core.context_engine import ContextEngineConfig
from openjiuwen.core.workflow import Workflow
from pydantic import JsonValue

from meta_agent.base_agent import MetaBaseAgent
from meta_agent.errors import SessionStateError
from meta_agent.identity import ExecutionIdentity
from meta_agent.routing import FastPathRouter, RouteDecision
from meta_agent.spec import MetaAgentSpec
from meta_agent.spec.platform import PackageServicesConfig
from meta_agent.workflow.runtime import MetaWorkflowRuntime
from meta_agent_adapter.service_bindings import validate_service_bindings


@dataclass(frozen=True)
class PackageResult:
    output: JsonValue
    identity: ExecutionIdentity
    engine: Literal["workflow", "deepagent"]
    state: Literal["COMPLETED", "INPUT_REQUIRED", "FAILED"] = "COMPLETED"
    result_type: Literal["answer", "input_required", "error"] = "answer"
    route: dict[str, Any] | None = None
    usage: dict[str, int] = field(default_factory=dict)
    interactions: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None


class MetaPackageRuntime:
    """A local DeepAgent-only or Hybrid package; close after use.

    Calls are serialized per package. A pending interaction remains on
    its selected engine until answered; it does not enter the router again.
    Workflow failures are surfaced, not silently rerouted as fresh model work.
    """

    def __init__(self, spec: MetaAgentSpec, digest: str, router: FastPathRouter | None) -> None:
        self.spec = spec
        self.package_digest = digest
        self.router = router
        self._deep: MetaBaseAgent | None = None
        self._workflow: MetaWorkflowRuntime | None = None
        self._pending: dict[str, RouteDecision | None] = {}
        self._lock = asyncio.Lock()
        self._closed = False

    @classmethod
    async def create(
        cls,
        spec: MetaAgentSpec,
        *,
        package_digest: str,
        workflow: Workflow | Callable[[dict[str, Any]], Workflow] | None = None,
        router: FastPathRouter | None = None,
        services: PackageServicesConfig | None = None,
        context_engine_config: ContextEngineConfig | None = None,
    ) -> Self:
        if spec.fastpath.enabled or (workflow is None) != (router is None):
            raise SessionStateError("META_ROUTE_OWNER", "Package routing must have a single owner")
        if services is not None:
            validate_service_bindings(services)
        runtime = cls(spec.model_copy(deep=True), package_digest, router)
        if workflow is not None:
            assert router is not None
            await router.start()
            runtime._workflow = await MetaWorkflowRuntime.create(
                workflow,
                agent_id=spec.agent_id,
                product_id=spec.product_id,
                package_digest=package_digest,
                observability=spec.trace.observability,
                services=(
                    services.model_copy(update={"context_service": None}) if services else None
                ),
                context_engine_config=context_engine_config,
            )
        else:
            await runtime._deep_runtime()
        return runtime

    async def _deep_runtime(self) -> MetaBaseAgent:
        if self._deep is None:
            self._deep = await MetaBaseAgent.create(
                self.spec, package_digest=self.package_digest, plugins=()
            )
        return self._deep

    def route_stats(self) -> dict[str, Any]:
        return self.router.snapshot() if self.router else {"totals": {}, "plugins": {}}

    async def invoke(
        self, inputs: dict[str, Any], *, session_id: str, request_id: str | None = None
    ) -> PackageResult:
        query = inputs.get("query")
        context = inputs.get("context", {})
        if not isinstance(context, dict):
            raise SessionStateError("META_INPUT_INVALID", "Agent context must be a JSON object")
        request_id = uuid4().hex if request_id is None else request_id
        try:
            identity = ExecutionIdentity(
                self.spec.product_id, self.spec.agent_id, session_id, request_id, "route"
            )
        except ValueError as error:
            raise SessionStateError(
                "META_ID_REQUIRED", "Request identity must not be blank"
            ) from error
        async with self._lock:
            if self._closed:
                raise SessionStateError("META_PACKAGE_CLOSED", "Package runtime is closed")
            if session_id in self._pending:
                if "answer" not in inputs:
                    raise SessionStateError(
                        "META_INPUT_INVALID", "A pending interaction requires answer"
                    )
                query = inputs["answer"]
            elif not isinstance(query, str):
                raise SessionStateError("META_INPUT_INVALID", "Agent input requires a string query")
            decision = self._pending.get(session_id)
            if session_id not in self._pending and self.router is not None:
                decision = await self.router.route(query, context, identity.child_session_id)
            if decision is not None and decision.matched:
                assert self._workflow is not None and self.router is not None
                try:
                    result = await self._workflow.invoke(
                        inputs,
                        session_id=session_id,
                        request_id=request_id,
                        selected_route=decision,
                    )
                except Exception:
                    self.router.on_result("workflow", "failed")
                    raise
                if result.state == "INPUT_REQUIRED":
                    self._pending[session_id] = decision
                else:
                    self._pending.pop(session_id, None)
                    self.router.on_result("workflow", "success")
                return PackageResult(
                    result.output,
                    result.identity,
                    "workflow",
                    state=result.state,
                    result_type=result.result_type,
                    route=decision.as_dict(),
                    usage={"deep_agent_calls": 0},
                    interactions=result.interactions,
                )
            deep = await self._deep_runtime()
            answer = await deep.invoke(
                query,
                session_id=session_id,
                request_id=request_id,
                context=context,
                selected_route=decision,
            )
            state: Literal["COMPLETED", "INPUT_REQUIRED", "FAILED"] = "COMPLETED"
            if answer.result_type == "input_required":
                self._pending[session_id] = decision
                state = "INPUT_REQUIRED"
            else:
                self._pending.pop(session_id, None)
                if answer.result_type == "error":
                    state = "FAILED"
            return PackageResult(
                answer.data if answer.data is not None else answer.output,
                answer.identity,
                "deepagent",
                state=state,
                result_type=answer.result_type,
                route=decision.as_dict() if decision is not None else None,
                usage=answer.usage,
                interactions=answer.interactions,
                error=answer.error,
            )

    async def close_session(self, session_id: str) -> bool:
        async with self._lock:
            closed = await self._deep.close_session(session_id) if self._deep is not None else False
            if self._workflow is not None:
                closed = await self._workflow.close_session(session_id) or closed
            self._pending.pop(session_id, None)
            return closed

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            try:
                if self._deep is not None:
                    await self._deep.aclose()
                    self._deep = None
            finally:
                if self._workflow is not None:
                    await self._workflow.close()
                    self._workflow = None
            self._pending.clear()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
