"""Host-callable lifecycle facade; staff binds the actual MMAgentWorker protocol.

One app owns one active package on one event loop. This module creates no HTTP
server, UDS server, subprocess supervisor or replacement platform control plane.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import propagate

from meta_agent.boot import LoadedAgentPackage, LoadedWorkflowPackage, MetaPackageLoader
from meta_agent.errors import BootError, SessionStateError
from meta_agent.package_runtime import MetaPackageRuntime
from meta_agent.workflow.runtime import MetaWorkflowRuntime
from meta_agent_adapter import fusionmind_model as _fusionmind_model  # noqa: F401
from meta_agent_adapter.inference import InferenceContext, bind_inference_context


class SidecarApp:
    """A small Python API for a staff-owned persistent host request loop."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._package: LoadedAgentPackage | LoadedWorkflowPackage | None = None
        self._runtime: MetaPackageRuntime | MetaWorkflowRuntime | None = None
        self._phase = "inactive"

    def status(self) -> dict[str, Any]:
        package = self._package
        return {
            "state": self._phase,
            "package": package.name if package is not None else None,
            "version": package.version if package is not None else None,
            "mode": package.spec.mode if package is not None else None,
            "package_digest": package.digest if package is not None else None,
        }

    async def activate(
        self, package: str | Path, *, env: Mapping[str, str] | None = None
    ) -> dict[str, Any]:
        async with self._lock:
            if self._runtime is not None:
                raise SessionStateError(
                    "META_PACKAGE_ACTIVE", "Deactivate the active package first"
                )
            self._phase = "activating"
            try:
                loaded = MetaPackageLoader(package, env=env).load()
                if not isinstance(loaded, (LoadedAgentPackage, LoadedWorkflowPackage)):
                    raise BootError(
                        "META_PACKAGE_MODE", "SidecarApp requires a new package.json manifest"
                    )
                runtime = await loaded.boot()
            except BaseException:
                self._phase = "inactive"
                raise
            self._package, self._runtime = loaded, runtime
            self._phase = "ready"
            return self.status()

    async def run(
        self,
        inputs: dict[str, Any],
        *,
        session_id: str,
        request_id: str,
        metadata: dict[str, Any] | None = None,
        trace_context: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        async with self._lock:
            if self._runtime is None or self._package is None:
                raise SessionStateError(
                    "META_PACKAGE_INACTIVE", "Activate a package before running"
                )
            package = self._package
            call_context = InferenceContext(
                product_id=package.spec.product_id,
                agent_id=package.agent_id,
                session_id=session_id,
                request_id=request_id,
                package_digest=package.digest,
                metadata=dict(metadata or {}),
            )
            trace_token = (
                otel_context.attach(propagate.extract(dict(trace_context)))
                if trace_context
                else None
            )
            self._phase = "running"
            try:
                with bind_inference_context(call_context):
                    result = await self._runtime.invoke(
                        inputs, session_id=session_id, request_id=request_id
                    )
                response = asdict(result)
                response.setdefault("engine", "workflow")
                response.setdefault("result_type", result.result_type)
                return response
            finally:
                self._phase = "ready"
                if trace_token is not None:
                    otel_context.detach(trace_token)

    async def close_session(self, session_id: str) -> bool:
        async with self._lock:
            if self._runtime is None:
                raise SessionStateError("META_PACKAGE_INACTIVE", "No active package")
            return await self._runtime.close_session(session_id)

    async def deactivate(self) -> dict[str, Any]:
        async with self._lock:
            if self._runtime is not None:
                self._phase = "deactivating"
                await self._runtime.close()
            self._runtime = None
            self._package = None
            self._phase = "inactive"
            return self.status()
