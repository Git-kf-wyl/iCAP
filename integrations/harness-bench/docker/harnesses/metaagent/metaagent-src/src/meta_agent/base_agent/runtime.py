"""Managed sessions over the pinned OpenJiuwen kernel.

Request IDs are consumed on admission, even on failure or cancellation. Replays
are rejected for the lifetime of this object; no response cache is maintained.
Interrupted runs retain their execution ID across a new resume request ID.
Plain persistence selects native storage only. Explicit LocalRecovery adds
fenced cold reconstruction, durable request admission and buffered publication.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing, suppress
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, Self
from uuid import uuid4

from openjiuwen.agent_evolving.checkpointing.evolution_store import EvolutionStore
from openjiuwen.core.common.constants.constant import INTERACTION
from openjiuwen.core.context_engine import ContextEngineConfig
from openjiuwen.core.runner import Runner
from openjiuwen.core.session import InteractiveInput
from openjiuwen.core.session.checkpointer import CheckpointerFactory
from openjiuwen.core.session.checkpointer.checkpointer import CheckpointerConfig
from openjiuwen.core.session.stream.base import BaseStreamMode, TraceSchema
from openjiuwen.harness import DeepAgent
from openjiuwen.harness.factory import apply_deep_agent_parts
from openjiuwen.harness.observability import AgentObservabilityRail
from openjiuwen.harness.rails import SkillUseRail
from openjiuwen.harness.rails.security.tool_security_rail import PermissionInterruptRail
from openjiuwen.harness.schema.build_context import BuildContext
from openjiuwen.harness.schema.deep_agent_spec import RailSpec, SysOperationSpec
from openjiuwen.harness.tools.subagent._control_registry import release_subagent_control
from pydantic import JsonValue

from meta_agent.base_agent.subagents import SubagentApprovals, SubagentPermissionRail
from meta_agent.checkpoint import (
    LeaseGuard,
    LocalRecovery,
    OperationScope,
    RecoverySnapshot,
    SideEffectExecutor,
)
from meta_agent.checkpoint.adapters import ReadOnlyMcpRail
from meta_agent.checkpoint.async_subagents import DurableAsyncSubagentRail
from meta_agent.checkpoint.evolution import EvolutionCheckpoint, materialize_skills
from meta_agent.checkpoint.executor import bind_effects, reset_effects
from meta_agent.checkpoint.native import NATIVE_RUN, NativeRun
from meta_agent.checkpoint.subagents import AsyncChildBoundaryRail, DurableSubagentRail
from meta_agent.errors import (
    BootError,
    MetaAgentError,
    RecoveryConflict,
    RequestConflictError,
    SessionConflict,
    SessionStateError,
    TraceError,
)
from meta_agent.evolution import SkillEvolution
from meta_agent.identity import ExecutionIdentity
from meta_agent.lifecycle import acquire_runner, release_runner
from meta_agent.orchestrator import DeepAgentComp, build_dag
from meta_agent.orchestrator.dag import interaction_payload
from meta_agent.orchestrator.fastpath import build_dual_dag, draw_dag
from meta_agent.registry import MetaRegistry, PluginPackage, scan_plugins
from meta_agent.registry.lifecycle import PluginManager, PluginSnapshot
from meta_agent.routing import FastPathRouter, RouteDecision
from meta_agent.spec import MetaAgentSpec
from meta_agent.spec.platform import PackageServicesConfig
from meta_agent.trace import JsonlTraceSink, TraceRail
from meta_agent.trace.execution import ExecutionTrace, execution_trace, skill_manifest_digest
from meta_agent.trace.goal import BudgetRail
from meta_agent.trace.subagent import SubagentUsageRail
from meta_agent.trace.trajectory import (
    TrajectoryArchive,
    acquire_tracing,
    release_tracing,
)
from meta_agent_adapter.infer_schedule import InferScheduleModelAdapter
from meta_agent_adapter.mcp_gateway import McpGatewayAdapter
from meta_agent_adapter.ops import OpsReporter
from meta_agent_adapter.service_bindings import attach_context_adapter, validate_service_bindings
from meta_agent_adapter.services import MemoryServiceAdapter, SkillsRuntimeAdapter, service_tools


@dataclass(frozen=True)
class AgentResult:
    output: str
    result_type: Literal["answer", "input_required", "error"]
    identity: ExecutionIdentity
    interactions: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    route: dict[str, Any] | None = None
    data: JsonValue = None


@dataclass(frozen=True)
class AgentEvent:
    type: Literal["delta", "input_required", "final"]
    data: dict[str, Any]
    identity: ExecutionIdentity


class _RequiredRailSpec(RailSpec):  # type: ignore[misc]
    def build(self, **kwargs: Any) -> Any:
        result = super().build(**kwargs)
        if result is None or result == []:
            raise BootError("META_RAIL_UNRESOLVED", "A configured rail could not be materialized.")
        return result


@dataclass
class _RuntimeBuildContext(BuildContext):  # type: ignore[misc]
    """Give native rail providers the same processor used by our trace archive."""

    trajectory_span_processor: Any = None


@dataclass
class _Session:
    agent: DeepAgent
    component: DeepAgentComp
    graph: Any
    workflow_id: str
    rail: TraceRail
    identity: ExecutionIdentity
    requests: set[str] = field(default_factory=set)
    task: asyncio.Task[AgentResult] | None = None
    pending: list[dict[str, Any]] = field(default_factory=list)
    broken: bool = False
    fresh: bool = True
    host_trace_errors: int = 0
    graph_built: bool = False
    route_context: dict[str, Any] = field(default_factory=dict)
    route: RouteDecision | None = None
    registry: MetaRegistry | None = None
    router: FastPathRouter | None = None
    durable_data: dict[str, Any] | None = None
    snapshot: PluginSnapshot | None = None
    subagent_approvals: SubagentApprovals = field(default_factory=SubagentApprovals)
    trace: ExecutionTrace | None = None
    skill_paths: list[str] = field(default_factory=list)


_LIVE_SCOPES: set[tuple[str, str]] = set()


class MetaBaseAgent:
    """A started local runtime. Always close it or use ``async with``."""

    def __init__(self, spec: MetaAgentSpec, sink: JsonlTraceSink, package_digest: str) -> None:
        self._spec = spec
        self.package_digest = package_digest
        self._sink = sink
        self._host_identity = ExecutionIdentity(
            spec.product_id, spec.agent_id, "host", "host", uuid4().hex
        )
        self._ops: OpsReporter | None = None
        self.evolution: SkillEvolution | None = None
        self._trajectories: TrajectoryArchive | None = None
        self._tracing_owned = False
        self._trajectory_processor: Any = None
        self._team_trace: dict[str, str] = {}
        self._sessions: dict[str, _Session] = {}
        self._closed = False
        self._runner_owned = True
        self._close_task: asyncio.Task[None] | None = None
        self._plugins = PluginManager(
            spec, recovery=None, catalog=None, package_digest=package_digest
        )
        self._recovery: LocalRecovery | None = None
        self._evolution_checkpoint: EvolutionCheckpoint | None = None
        self._durable_tasks: dict[str, asyncio.Task[AgentResult]] = {}
        self._permission_rail_factory: Callable[[], Any] | None = None
        self._mcp_scope = uuid4().hex
        self._gateway = McpGatewayAdapter(spec.csp.mcp_gateway)
        self._owned_sys_operations: set[str] = set()
        self._memory = (
            MemoryServiceAdapter(spec.csp.memory_service) if spec.csp.memory_service else None
        )
        self._skills_runtime = (
            SkillsRuntimeAdapter(spec.csp.skills_runtime) if spec.csp.skills_runtime else None
        )

    @property
    def spec(self) -> MetaAgentSpec:
        """Return a defensive copy; a loaded runtime never changes configuration."""
        return self._spec.model_copy(deep=True)

    @classmethod
    async def create(
        cls,
        spec: MetaAgentSpec,
        *,
        package_digest: str = "",
        plugins: tuple[PluginPackage, ...] | None = None,
        recovery: LocalRecovery | None = None,
        permission_rail_factory: Callable[[], Any] | None = None,
        plugin_catalog: str | Path | None = None,
        team_trace: dict[str, str] | None = None,
    ) -> Self:
        try:
            spec = MetaAgentSpec.model_validate(spec.model_dump()).model_copy(deep=True)
        except Exception as exc:
            raise BootError("META_SPEC_INVALID", "Runtime configuration is invalid.") from exc
        scope = (spec.product_id, spec.agent_id)
        validate_service_bindings(
            PackageServicesConfig(
                memory_service=spec.csp.memory_service,
                skills_runtime=spec.csp.skills_runtime,
                context_service=spec.csp.context_service,
            )
        )
        if scope in _LIVE_SCOPES:
            raise SessionConflict("META_AGENT_ALREADY_OPEN", "This agent identity is already open.")
        _LIVE_SCOPES.add(scope)
        trace_path = (
            Path(spec.trace.file_dir) / f"meta-agent-{uuid4().hex}.jsonl"
            if spec.trace.enabled
            else None
        )
        sink: JsonlTraceSink | None = None
        runtime: Self | None = None
        acquired = False
        try:
            sink = JsonlTraceSink(trace_path, rollout=spec.trace.rollout)
            if recovery is not None and (
                spec.deep_agent.enable_sys_operation
                or spec.deep_agent.sys_operation is not None
                or any(c.sys_operation is not None for c in spec.deep_agent.subagents or [])
            ):
                raise BootError(
                    "META_SYS_OPERATION_RECOVERY_UNSUPPORTED",
                    "Native shell/filesystem tools run without LocalRecovery; "
                    "durable writes require explicit effect bindings",
                )
            if (
                recovery is not None
                and spec.deep_agent.subagents
                and spec.deep_agent.enable_async_subagent
                and not spec.deep_agent.enable_subagent_runtime
            ):
                raise BootError(
                    "META_HARNESS_RECOVERY_UNSUPPORTED",
                    "Use enable_subagent_runtime for durable asynchronous children",
                )
            if (
                recovery is not None
                and (spec.deep_agent.mcps or any(c.mcps for c in spec.deep_agent.subagents or []))
                and not any(name.startswith("mcp_") for name in recovery.read_only_tools)
            ):
                raise BootError(
                    "META_MCP_RECOVERY_UNSUPPORTED",
                    "MCP recovery requires explicit host-declared read-only tools",
                )
            if recovery is not None and (
                spec.csp.memory_service or spec.csp.skills_runtime or spec.csp.context_service
            ):
                raise BootError(
                    "META_SERVICE_RECOVERY_UNSUPPORTED",
                    "External Memory/Skills/Context services need recovery contracts "
                    "before LocalRecovery",
                )
            if recovery is not None and spec.checkpoint.backend != "in_memory":
                raise BootError(
                    "META_RECOVERY_BACKEND", "LocalRecovery supplies its own checkpoint store"
                )
            await acquire_runner(
                CheckpointerConfig(
                    type="meta_local_recovery", conf={"backend_id": recovery.store.backend_id}
                )
                if recovery is not None
                else spec.checkpoint.to_kernel()
            )
            acquired = True
            runtime = cls(spec, sink, package_digest)
            runtime._team_trace = team_trace or {}
            runtime._recovery = recovery
            if recovery is not None and spec.evolution.enabled:
                runtime._evolution_checkpoint = EvolutionCheckpoint(recovery, spec, package_digest)
                await runtime._evolution_checkpoint.open()
            runtime._plugins = PluginManager(
                spec,
                recovery=recovery,
                catalog=Path(plugin_catalog) if plugin_catalog is not None else None,
                package_digest=package_digest,
            )
            runtime._permission_rail_factory = permission_rail_factory
            if spec.trace.trajectories or (
                spec.trace.observability is not None and spec.trace.observability.enabled
            ):
                processor = acquire_tracing(spec.trace.observability)
                runtime._trajectory_processor = processor
                runtime._tracing_owned = True
            parts = runtime._resolve_parts(spec.agent_id)
            if spec.trace.trajectories:
                runtime._trajectories = TrajectoryArchive(
                    Path(spec.trace.file_dir)
                    / "trajectories"
                    / (
                        runtime._evolution_checkpoint.fingerprint
                        if runtime._evolution_checkpoint is not None
                        else runtime._host_identity.execution_id
                    ),
                    daily=spec.trace.rollout == "daily",
                )
                if spec.evolution.enabled:
                    runtime.evolution = SkillEvolution(
                        skills=list(
                            runtime._evolution_checkpoint.spec.deep_agent.skills
                            if runtime._evolution_checkpoint is not None
                            else spec.deep_agent.skills
                        ),
                        model=parts.config.model,
                        model_name=parts.config.model.model_config.model_name,
                        language=spec.deep_agent.language,
                        processor=processor,
                        archive=runtime._trajectories,
                        ensure_idle=runtime._ensure_evolution_idle,
                        emit=runtime._emit,
                        host_identity=runtime._host_identity,
                        plugins=runtime._plugins,
                        checkpoint=runtime._evolution_checkpoint,
                    )
                    if runtime._evolution_checkpoint is not None:
                        await runtime._evolution_checkpoint.save(runtime.evolution)
            if runtime._gateway is not None:
                servers = list(parts.config.mcps or [])
                for child in parts.config.subagents or []:
                    servers.extend(child.mcps or [])
                await runtime._gateway.open(list({s.server_id: s for s in servers}.values()))
            packages = scan_plugins(spec.fastpath) if plugins is None else plugins
            if packages and not spec.fastpath.enabled:
                raise BootError("META_PLUGIN_CONFIG", "Plugins require enabled fastpath.")
            await runtime._plugins.start(packages)
            runtime._emit("agent.boot", runtime._host_identity, package_digest=package_digest)
            if spec.csp.ops is not None:
                runtime._ops = OpsReporter(
                    spec.csp.ops,
                    {
                        "product_id": spec.product_id,
                        "agent_id": spec.agent_id,
                        "instance_id": runtime._host_identity.execution_id,
                    },
                    runtime.observability,
                )
                await runtime._ops.start()
            return runtime
        except BaseException:
            try:
                try:
                    if runtime is not None and runtime._gateway is not None:
                        await runtime._gateway.aclose()
                finally:
                    if acquired:
                        if runtime is not None:
                            runtime._release_sys_operations()
                        await release_runner()
            finally:
                try:
                    if runtime is not None:
                        if runtime._evolution_checkpoint is not None:
                            await runtime._evolution_checkpoint.close()
                        for service in (runtime._memory, runtime._skills_runtime):
                            if service is not None:
                                await service.aclose()
                        if runtime._tracing_owned:
                            release_tracing()
                            runtime._tracing_owned = False
                        if runtime._ops is not None:
                            await runtime._ops.aclose()
                        await runtime._plugins.aclose()
                    if sink is not None:
                        sink.close()
                finally:
                    _LIVE_SCOPES.discard(scope)
            raise

    async def __aenter__(self) -> Self:
        self._ensure_open()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    def draw(self) -> str:
        return draw_dag(
            [p.manifest.name for p in self._registry.packages] if self._registry else []
        )

    def route_stats(self) -> dict[str, Any]:
        return self._router.snapshot() if self._router else {"totals": {}, "plugins": {}}

    @property
    def _registry(self) -> MetaRegistry | None:
        return self._plugins.active.registry

    @property
    def _router(self) -> FastPathRouter | None:
        return self._plugins.active.router

    def list_plugins(self) -> list[dict[str, Any]]:
        return self._plugins.list()

    def observability(self) -> dict[str, Any]:
        """Cumulative process counters plus the active router's current window."""
        return {
            "metrics": self._sink.metrics(),
            "router": self.route_stats(),
            "trace_files": self._sink.files(),
            "ops": self._ops.status() if self._ops else None,
            "trajectories": self._trajectories.status() if self._trajectories else None,
        }

    def _ensure_evolution_idle(self) -> None:
        self._ensure_open()
        if self._plugins.lock.locked():
            raise SessionConflict("META_PLUGIN_BUSY", "A plugin change is running")
        if self._durable_tasks or any(
            s.task is not None or (s.pending and self._recovery is None)
            for s in self._sessions.values()
        ):
            raise SessionConflict(
                "META_SKILL_IN_USE",
                "Finish or cancel active/paused executions before evolving Skills",
            )

    async def load_plugin(self, directory: str | Path) -> PluginPackage:
        self._ensure_open()
        self._ensure_plugin_change()
        package = await self._plugins.load(directory)
        self._emit(
            "plugin.load",
            self._host_identity,
            plugin=package.manifest.name,
            plugin_version=package.manifest.version,
            plugin_digest=package.digest,
        )
        return package

    async def activate_plugin(self, name: str, version: str) -> None:
        """Activate a loaded version for new executions; an older version is rollback."""
        self._ensure_open()
        self._ensure_plugin_change(name)
        await self._plugins.activate(name, version)
        self._emit("plugin.activate", self._host_identity, plugin=name, plugin_version=version)

    async def deactivate_plugin(self, name: str) -> None:
        self._ensure_open()
        self._ensure_plugin_change(name)
        await self._plugins.activate(name, None)
        self._emit("plugin.deactivate", self._host_identity, plugin=name)

    async def unload_plugin(self, name: str, version: str) -> None:
        self._ensure_open()
        self._ensure_plugin_change(name)
        await self._plugins.unload(name, version)
        self._emit("plugin.unload", self._host_identity, plugin=name, plugin_version=version)

    def _ensure_plugin_change(self, name: str | None = None) -> None:
        if self.evolution is not None:
            if self.evolution.busy:
                raise SessionConflict("META_EVOLUTION_BUSY", "A Skill operation is running")
            if name is not None:
                self.evolution.workflows.ensure_external_change(name)

    def _release_snapshot(self, session: _Session) -> None:
        if session.snapshot is not None:
            self._plugins.release(session.snapshot)
            session.snapshot = None

    @property
    def trace_failures(self) -> int:
        return self._sink.failed_writes

    def _ensure_open(self) -> None:
        if self._closed:
            raise SessionStateError("META_CLOSED", "The agent is closed.")

    def _emit(self, event: str, identity: ExecutionIdentity, **fields: Any) -> None:
        try:
            self._sink.emit(event, identity, **fields)
        except TraceError:
            # Observability failure cannot turn a completed tool/model action into a retry.
            session = self._sessions.get(identity.session_id)
            if session is not None:
                session.host_trace_errors += 1

    def _resolve_parts(self, card_id: str, skill_spec: MetaAgentSpec | None = None) -> Any:
        source = skill_spec or (
            self._evolution_checkpoint.spec
            if self._evolution_checkpoint is not None
            else self._spec
        )
        native = source.deep_agent.model_copy(deep=True)
        if native.context_engine_config is not None:
            native.context_engine_config = ContextEngineConfig.model_validate(
                native.context_engine_config
            )
        native.card.id = card_id
        if self._spec.csp.infer_schedule is not None:
            adapter = InferScheduleModelAdapter(self._spec.csp.infer_schedule)
            native.model = adapter.configure(native.model)
            for child in native.subagents or []:
                if child.model is not None:
                    child.model = adapter.configure(child.model)
        if self._gateway is not None:
            native.mcps = self._gateway.build_mcps(native.mcps or [], scope=self._mcp_scope)
            for child in native.subagents or []:
                child.mcps = self._gateway.build_mcps(child.mcps or [], scope=self._mcp_scope)
        native.rails = [
            _RequiredRailSpec.model_validate(r.model_dump()) for r in native.rails or []
        ]
        for child in native.subagents or []:
            child.rails = [
                _RequiredRailSpec.model_validate(r.model_dump()) for r in child.rails or []
            ]
        # Only our session-scoped factory defaults are private to this runtime.
        # Explicit and child operation IDs can be shared; Runner owns their lifetime.
        if (
            native.enable_sys_operation
            and native.sys_operation is None
            and card_id != self._spec.agent_id
        ):
            operation_id = f"{native.card.name}_{native.card.id}"
            if Runner.resource_mgr.get_sys_operation(operation_id) is None:
                self._owned_sys_operations.add(operation_id)
        try:
            parts = native.resolve_parts(
                context=_RuntimeBuildContext(
                    language=native.language,
                    trajectory_span_processor=self._trajectory_processor,
                )
            )
            for child in parts.config.subagents or []:
                # Native create_subagent forwards these kwargs to its factory.
                system_tools = native.enable_sys_operation or child.sys_operation is not None
                child.factory_kwargs = {"enable_sys_operation": bool(system_tools or child.skills)}
                child.rails = list(child.rails or [])
                skill_rails = [r for r in child.rails if isinstance(r, SkillUseRail)]
                if child.skills and not skill_rails:
                    skill = SkillUseRail(skills_dir=list(child.skills), include_tools=system_tools)
                    child.rails.append(skill)
                    skill_rails.append(skill)
                for skill in skill_rails:
                    if not system_tools:
                        skill.include_tools = False
                    skill.skills_dir = list(child.skills or [])
                    if skill_spec is not None and child.skills:
                        skill.evolution_store = self._skill_store(list(child.skills))
            if self._recovery is not None:
                from openjiuwen.harness.rails.sys_operation_rail import SysOperationRail

                if any(
                    isinstance(rail, SysOperationRail)
                    for rail in [
                        *parts.rails,
                        *[r for c in parts.config.subagents or [] for r in c.rails or []],
                    ]
                ):
                    raise BootError(
                        "META_SYS_OPERATION_RECOVERY_UNSUPPORTED",
                        "SysOperationRail requires ordinary execution without LocalRecovery",
                    )
                for child in parts.config.subagents or []:
                    self._recovery.validate_tools(child.tools)
                instance_cards = {id(tool.card) for tool in parts.tool_instances}
                self._recovery.validate_tools(
                    [
                        *parts.tool_instances,
                        *[card for card in parts.tool_cards if id(card) not in instance_cards],
                    ]
                )
            for skill_rail in parts.rails:
                if isinstance(skill_rail, SkillUseRail):
                    # Retain native tool ownership when enabled. The tools-disabled
                    # profile still needs Skill discovery without shell fallback.
                    if not native.enable_sys_operation:
                        skill_rail.include_tools = False
                    skill_rail.skills_dir = list(native.skills)
                    if skill_spec is not None:
                        skill_rail.evolution_store = self._skill_store(list(native.skills))
                    elif self.evolution is not None:
                        skill_rail.evolution_store = self.evolution.store
            return parts
        except BootError:
            raise
        except Exception as exc:
            raise BootError("META_HARNESS_BUILD", "Native harness materialization failed.") from exc

    @staticmethod
    def _skill_store(paths: list[str]) -> Any:
        return EvolutionStore(
            [str(Path(p).parent if (Path(p) / "SKILL.md").is_file() else Path(p)) for p in paths]
        )

    def _new_session(
        self, identity: ExecutionIdentity, skill_spec: MetaAgentSpec | None = None
    ) -> _Session:
        parts = self._resolve_parts(identity.child_session_id, skill_spec)
        rail = TraceRail(self._sink, identity)
        tools = service_tools(lambda: rail.identity, self._memory, self._skills_runtime)
        if {tool.card.name for tool in tools} & {card.name for card in parts.tool_cards}:
            raise BootError("META_SERVICE_TOOL_CONFLICT", "Service tool name already configured")
        parts.tool_instances.extend(tools)
        parts.tool_cards.extend(tool.card for tool in tools)
        if parts.config.sys_operation is None:
            operation_id = f"meta-skills-{identity.child_session_id}"
            if Runner.resource_mgr.get_sys_operation(operation_id) is None:
                self._owned_sys_operations.add(operation_id)
            parts.config.sys_operation = SysOperationSpec(id=operation_id).resolve()
        agent = DeepAgent(parts.config.card)
        try:
            apply_deep_agent_parts(agent, parts)
            if agent.react_agent is not None:
                attach_context_adapter(
                    agent.react_agent.context_engine,
                    self._spec.csp.context_service,
                    lambda: rail.identity,
                )
        except Exception as exc:
            agent.ability_manager.teardown_tools()
            self._release_skill_operation(identity.child_session_id)
            raise BootError("META_HARNESS_BUILD", "Native harness application failed.") from exc
        servers = list(parts.config.mcps or [])
        for child in parts.config.subagents or []:
            servers.extend(child.mcps or [])
        if self._spec.csp.mcp_gateway is not None:
            rail.gateway_prefixes = tuple({f"mcp_{m.server_name}_" for m in servers})
        agent.add_rail(rail)
        if self._recovery is not None and servers:
            agent.add_rail(ReadOnlyMcpRail(self._recovery.read_only_tools))
        if self._spec.budget.enabled:
            agent.add_rail(BudgetRail(self._spec.budget, rail))
        if self._tracing_owned:
            agent.add_rail(AgentObservabilityRail())
        if self._trajectories is not None:
            agent.add_rail(self._trajectories.rail(lambda: rail.identity))
        if self._spec.permissions.enabled:
            agent.add_rail(
                self._permission_rail_factory()
                if self._permission_rail_factory is not None
                else PermissionInterruptRail(config=self._spec.permissions.native_config())
            )
        if self._recovery is not None and parts.config.subagents:
            agent.add_rail(DurableSubagentRail(agent))
            if parts.config.enable_subagent_runtime:
                agent.add_rail(DurableAsyncSubagentRail(agent))
        approvals = SubagentApprovals()
        for child in parts.config.subagents or []:
            child.rails.append(SubagentUsageRail(agent, rail))
            if self._recovery is not None and parts.config.enable_subagent_runtime:
                child.rails.append(AsyncChildBoundaryRail())
            if self._recovery is not None and child.mcps:
                child.rails.append(ReadOnlyMcpRail(self._recovery.read_only_tools))
            if self._spec.permissions.enabled:
                child.rails.append(
                    self._permission_rail_factory()
                    if self._permission_rail_factory is not None
                    else PermissionInterruptRail(config=self._spec.permissions.native_config())
                    if self._recovery is not None
                    else SubagentPermissionRail(self._spec.permissions.native_config(), approvals)
                )
            if self._tracing_owned:
                child.rails.append(AgentObservabilityRail())
        component = DeepAgentComp(agent, identity.child_session_id, self._spec.budget)
        workflow_id = f"meta-workflow-{identity.child_session_id}"
        return _Session(
            agent,
            component,
            build_dag(component, workflow_id),
            workflow_id,
            rail,
            identity,
            subagent_approvals=approvals,
            skill_paths=list((skill_spec or self._spec).deep_agent.skills),
        )

    def pending_subagent_approvals(self, session_id: str) -> list[dict[str, Any]]:
        """Read child ASK requests while the parent invocation is still running."""
        self._ensure_open()
        session = self._sessions.get(session_id)
        return session.subagent_approvals.list() if session is not None else []

    def answer_subagent_approval(
        self, session_id: str, approval_id: str, *, approved: bool, feedback: str = ""
    ) -> None:
        """Trusted host decision; wake the same child tool call without replay."""
        self._ensure_open()
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionStateError("META_SESSION_NOT_FOUND", "Unknown session")
        session.subagent_approvals.answer(approval_id, approved=approved, feedback=feedback)

    def _admit(
        self,
        query: Any,
        session_id: str,
        request_id: str,
        streaming: bool,
        context: dict[str, Any] | None = None,
    ) -> tuple[_Session, Any]:
        self._ensure_open()
        if self.evolution is not None and self.evolution.busy:
            raise SessionConflict("META_EVOLUTION_BUSY", "A Skill operation is running")
        if not session_id.strip() or not request_id.strip():
            raise SessionStateError(
                "META_ID_REQUIRED", "Session and request IDs must not be blank."
            )
        session = self._sessions.get(session_id)
        if session is not None and session.task is not None:
            raise SessionConflict("META_SESSION_BUSY", "The session already has an active request.")
        if session is not None and request_id in session.requests:
            raise RequestConflictError(
                "META_REQUEST_REPLAY", "The request ID was already consumed."
            )
        if session is not None and session.broken:
            raise SessionStateError(
                "META_SESSION_TERMINATED",
                "A failed or cancelled session requires a new session ID.",
            )
        try:
            if context is not None and not isinstance(context, dict):
                raise ValueError("Context must be an object")
            route_context = json.loads(json.dumps(context or {}, allow_nan=False, sort_keys=True))
            if not isinstance(route_context, dict):
                raise ValueError("Context must be an object")
        except (ValueError, TypeError) as exc:
            raise SessionStateError(
                "META_ROUTE_CONTEXT", "Routing context must be JSON data."
            ) from exc
        if session is not None and session.pending:
            if context is not None and route_context != session.route_context:
                raise SessionStateError(
                    "META_CONTEXT_CHANGED", "Paused execution retains its routing context."
                )
            route_context = session.route_context
        execution_id = (
            session.identity.execution_id
            if session is not None and session.pending
            else uuid4().hex
        )
        identity = ExecutionIdentity(
            self._spec.product_id, self._spec.agent_id, session_id, request_id, execution_id
        )
        if session is None:
            session = self._new_session(identity)
            self._sessions[session_id] = session
        if session.pending:
            if isinstance(query, InteractiveInput):
                inputs = query
            else:
                inputs = InteractiveInput()
                for interaction in session.pending:
                    inputs.update(interaction["id"], query)
        else:
            if not isinstance(query, str) or not query.strip():
                raise SessionStateError("META_QUERY_REQUIRED", "A new turn requires nonempty text.")
            snapshot = self._plugins.acquire()
            session.snapshot = snapshot
            if session.registry is not snapshot.registry:
                session.graph = build_dag(session.component, session.workflow_id)
                session.graph_built = False
            session.registry, session.router = snapshot.registry, snapshot.router
            inputs = {"query": query, "route_context": route_context, "execution_id": execution_id}
            session.route = None
            if session.component.goal is not None:
                session.component.goal.record = None
        session.identity = identity
        session.requests.add(request_id)
        session.rail.bind(identity)
        session.host_trace_errors = 0
        session.route_context = route_context
        session.component.streaming = streaming
        session.component.dispatch_count = 0
        return session, inputs

    async def invoke(
        self,
        query: Any,
        *,
        session_id: str,
        request_id: str,
        context: dict[str, Any] | None = None,
        selected_route: RouteDecision | None = None,
    ) -> AgentResult:
        if selected_route is not None and (
            self._spec.fastpath.enabled or self._recovery is not None or selected_route.matched
        ):
            raise SessionStateError(
                "META_ROUTE_OWNER", "An external DeepAgent route requires an unrouted local runtime"
            )
        if self._recovery is not None:
            return await self._submit_durable(query, session_id, request_id, context=context)
        session, inputs = self._admit(query, session_id, request_id, False, context)
        if selected_route is not None:
            session.route = selected_route
        task = asyncio.create_task(self._execute(session, inputs, None))
        session.task = task
        try:
            result = await task
        finally:
            session.task = None
            if not session.pending or session.broken:
                self._release_snapshot(session)
        await self._auto_evolve(result)
        return result

    async def _auto_evolve(self, result: AgentResult) -> None:
        if (
            self.evolution is not None
            and self._spec.evolution.auto_propose
            and result.result_type == "answer"
            and result.usage.get("deep_agent_calls", 0) > 0
        ):
            assert self._spec.evolution.auto_skill is not None
            await self.evolution.on_execution_complete(
                result.identity.execution_id, skill_name=self._spec.evolution.auto_skill
            )

    async def stream(
        self,
        query: Any,
        *,
        session_id: str,
        request_id: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        if self._recovery is not None:
            # Durable output is buffered until the final effect/response commit.
            result = await self._submit_durable(query, session_id, request_id, context=context)
            yield AgentEvent(
                "input_required" if result.result_type == "input_required" else "final",
                {k: v for k, v in asdict(result).items() if k != "identity"},
                result.identity,
            )
            return
        session, inputs = self._admit(query, session_id, request_id, True, context)
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue()

        async def produce() -> AgentResult:
            try:
                return await self._execute(session, inputs, queue)
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(produce())
        session.task = task
        terminal: AgentEvent | None = None
        try:
            while (event := await queue.get()) is not None:
                if event.type in {"final", "input_required"}:
                    terminal = event
                else:
                    yield event
            result = await task  # Propagate model/graph failures, including CancelledError.
        finally:
            if not task.done():
                task.cancel()
            try:
                with suppress(asyncio.CancelledError):
                    await task
            finally:
                session.task = None
                if not session.pending or session.broken:
                    self._release_snapshot(session)
        await self._auto_evolve(result)
        if terminal is not None:
            yield terminal

    async def resume(
        self,
        *,
        session_id: str,
        request_id: str,
        answer: Any = None,
    ) -> AgentResult:
        """Recover the last durable execution, or retrieve its committed result.

        An answer is accepted only for a saved interaction. With no answer, a
        paused question is returned again; an interrupted active run continues.
        """
        if self._recovery is None:
            raise RecoveryConflict("META_RECOVERY_DISABLED", "resume requires LocalRecovery")
        return await self._submit_durable(answer, session_id, request_id, resume=True)

    async def _submit_durable(
        self,
        query: Any,
        session_id: str,
        request_id: str,
        *,
        context: dict[str, Any] | None = None,
        resume: bool = False,
    ) -> AgentResult:
        self._ensure_open()
        if self._evolution_checkpoint is not None:
            await self._evolution_checkpoint.check()
            if self.evolution is not None and self.evolution.busy:
                raise SessionConflict("META_EVOLUTION_BUSY", "A Skill operation is running")
            if self.evolution is not None:
                self.evolution.workflows.require_ready()
        if not session_id.strip() or not request_id.strip():
            raise SessionStateError("META_ID_REQUIRED", "Session and request IDs are required")
        if session_id in self._durable_tasks:
            raise SessionConflict("META_SESSION_BUSY", "The session has an active request")
        snapshot = self._plugins.acquire() if not resume else None
        task = asyncio.create_task(
            self._durable_call(query, session_id, request_id, context, resume, snapshot)
        )
        self._durable_tasks[session_id] = task
        try:
            result = await task
        finally:
            self._durable_tasks.pop(session_id, None)
            if snapshot is not None:
                self._plugins.release(snapshot)
        await self._auto_evolve(result)
        return result

    async def _durable_call(
        self,
        query: Any,
        session_id: str,
        request_id: str,
        context: dict[str, Any] | None,
        resume: bool,
        admitted: PluginSnapshot | None,
    ) -> AgentResult:
        recovery = self._recovery
        assert recovery is not None
        scope = OperationScope(self._spec.product_id, self._spec.agent_id, session_id)
        async with LeaseGuard(recovery.store, scope, ttl=recovery.ttl) as guard:
            saved = await recovery.store.runtime_state(scope)
            registry, router = (admitted.registry, admitted.router) if admitted else (None, None)
            owns_registry = False
            if resume:
                if saved is None:
                    raise RecoveryConflict(
                        "META_RECOVERY_MISSING", "No admitted execution to recover"
                    )
                snapshot = RecoverySnapshot(**saved["snapshot"])
                packages = await recovery.restore_packages(
                    snapshot, self._spec, self.package_digest
                )
                data = saved["data"]
                execution_id = saved["execution_id"]
                identity = ExecutionIdentity(
                    scope.product_id, scope.agent_id, session_id, request_id, execution_id
                )
                if snapshot.child_session_id != identity.child_session_id:
                    raise RecoveryConflict(
                        "META_RECOVERY_IDENTITY", "Child session identity changed"
                    )
                if saved["status"] == "completed":
                    if query is not None:
                        raise RecoveryConflict(
                            "META_EXECUTION_CLOSED", "Completed execution accepts no answer"
                        )
                    return AgentResult(**{**data["result"], "identity": identity})
                if (
                    self._spec.budget.enabled
                    or self._spec.deep_agent.mcps
                    or self._spec.deep_agent.subagents
                ) and (saved["status"] != "paused" or data.get("resume_inputs") is not None):
                    raise RecoveryConflict(
                        "META_SUBAGENT_RECOVERY_BOUNDARY"
                        if self._spec.deep_agent.subagents
                        else "META_GOAL_RECOVERY_BOUNDARY"
                        if self._spec.budget.enabled
                        else "META_MCP_RECOVERY_BOUNDARY",
                        "This configuration requires a completed interaction checkpoint",
                    )
                if query is not None:
                    if not data["pending"] or data.get("resume_inputs") is not None:
                        raise RecoveryConflict(
                            "META_UNEXPECTED_ANSWER", "No unanswered durable interaction"
                        )
                    answer_inputs = InteractiveInput()
                    for interaction in data["pending"]:
                        answer_inputs.update(interaction["id"], query)
                    data["resume_inputs"] = answer_inputs.model_dump(mode="json")
                    data["resume_request_id"] = request_id
                data["request_id"] = request_id
                await recovery.store.update_runtime(
                    guard.current, execution_id, data, request_id=request_id
                )
                if data["pending"] and data.get("resume_inputs") is None:
                    return AgentResult(**{**data["result"], "identity": identity})
                registry, router = None, None
                if packages:
                    registry = MetaRegistry(
                        packages,
                        self._spec.fastpath,
                        scope.product_id,
                        scope.agent_id,
                        effect_bindings=recovery.plugin_effects,
                        operations=self._plugins.operations,
                    )
                    owns_registry = True
                    try:
                        await registry.start()
                        if registry.graph_version != snapshot.graph_version:
                            raise RecoveryConflict(
                                "META_GRAPH_CHANGED", "Retained graph version differs"
                            )
                        router = FastPathRouter(
                            self._spec.fastpath.router,
                            [p.manifest for p in packages],
                            {p.manifest.name: p.digest for p in packages},
                            registry.graph_version,
                        )
                        await router.start()
                    except BaseException:
                        registry.close()
                        raise
                elif snapshot.graph_version != "meta-single-v1":
                    raise RecoveryConflict("META_GRAPH_CHANGED", "Missing retained plugin graph")
            else:
                if saved is not None and saved["status"] != "completed":
                    raise RecoveryConflict(
                        "META_RECOVERY_REQUIRED", "Use resume for the unfinished execution"
                    )
                if not isinstance(query, str) or not query.strip():
                    raise SessionStateError(
                        "META_QUERY_REQUIRED", "A new turn requires nonempty text"
                    )
                if context is not None and not isinstance(context, dict):
                    raise SessionStateError(
                        "META_ROUTE_CONTEXT", "Routing context must be an object"
                    )
                data = json.loads(
                    json.dumps(
                        {
                            "request_id": request_id,
                            "query": query,
                            "context": context or {},
                            "pending": [],
                            "route": None,
                            "result": None,
                            "resume_inputs": None,
                        },
                        allow_nan=False,
                    )
                )
                execution_id = uuid4().hex
                identity = ExecutionIdentity(
                    scope.product_id, scope.agent_id, session_id, request_id, execution_id
                )
                snapshot = await recovery.snapshot(
                    self._spec,
                    self.package_digest,
                    identity.child_session_id,
                    registry.graph_version if registry else "meta-single-v1",
                    registry.packages if registry else (),
                    skill_content=(
                        await recovery.store.get_artifact(saved["snapshot"]["artifacts"]["skills"])
                        if saved is not None
                        else recovery.skills(self._evolution_checkpoint.spec)
                    )
                    if self._evolution_checkpoint is not None
                    else None,
                )
                await recovery.store.bind_execution(
                    guard.current, execution_id, snapshot, runtime_data=data
                )
            executor = SideEffectExecutor(guard, execution_id, observer=recovery.effect_observer)
            effect_token = bind_effects(executor)
            native = NativeRun(
                executor,
                identity.child_session_id,
                f"meta-workflow-{identity.child_session_id}",
                data.get("resume_request_id"),
                tuple(child.agent_card.name for child in self._spec.deep_agent.subagents or []),
            )
            native_token = NATIVE_RUN.set(native)
            try:
                # Reconciliation precedes the native workflow, so it needs its
                # own lease-wide cancellation scope (including observer waits).
                await guard.run(lambda: executor.recover_pending(list(recovery.adapters)))
                previous = self._sessions.pop(session_id, None)
                if previous is not None:
                    await self._dispose_session(previous)
                skill_spec = None
                if self._evolution_checkpoint is not None:
                    digest = snapshot.artifacts["skills"]
                    skill_spec = materialize_skills(
                        self._spec, await recovery.store.get_artifact(digest), digest
                    )
                session = self._new_session(identity, skill_spec)
                self._sessions[session_id] = session
                session.fresh = False
                session.registry, session.router = registry, router
                session.durable_data = data
                session.route_context = data["context"]
                session.route = RouteDecision(**data["route"]) if data["route"] else None
                session.task = asyncio.current_task()
                if data.get("resume_inputs") is not None:
                    inputs: Any = InteractiveInput()
                    inputs.user_inputs = data["resume_inputs"]["user_inputs"]
                    inputs.raw_inputs = data["resume_inputs"]["raw_inputs"]
                elif await native.load("workflow") is not None:
                    inputs = InteractiveInput()
                else:
                    inputs = {
                        "query": data["query"],
                        "route_context": data["context"],
                        "execution_id": execution_id,
                    }
                return await guard.run(lambda: self._execute(session, inputs, None))
            finally:
                try:
                    closing_session = self._sessions.get(session_id)
                    if closing_session is not None:
                        closing_session.task = None
                        if self._spec.deep_agent.enable_subagent_runtime:
                            # Also stop children when the parent raises before
                            # reaching its checkpoint, while it still owns the lease.
                            await release_subagent_control(
                                closing_session.agent, identity.child_session_id
                            )
                finally:
                    NATIVE_RUN.reset(native_token)
                    reset_effects(effect_token)
                    if owns_registry and registry is not None:
                        registry.close()

    async def _execute(
        self, session: _Session, inputs: Any, queue: asyncio.Queue[AgentEvent | None] | None
    ) -> AgentResult:
        if not self._tracing_owned:
            return await self._execute_inner(session, inputs, queue)
        with execution_trace(
            session.identity,
            inputs,
            package_digest=self.package_digest,
            skill_digest=skill_manifest_digest(session.skill_paths),
            team=self._team_trace,
        ) as trace:
            session.trace = trace
            try:
                if session.pending and session.route is not None:
                    trace.route(session.route, resumed=True)
                elif session.route is not None and session.router is None:
                    trace.route(session.route)
                result = await self._execute_inner(session, inputs, queue)
                trace.result = result
                return result
            finally:
                session.trace = None

    async def _execute_inner(
        self, session: _Session, inputs: Any, queue: asyncio.Queue[AgentEvent | None] | None
    ) -> AgentResult:
        identity = session.identity
        started = perf_counter()
        self._emit(
            "execution.start",
            identity,
            child_session_id=identity.child_session_id,
            workflow_id=session.workflow_id,
            package_digest=self.package_digest,
        )
        try:
            registry, router = session.registry, session.router
            if not session.graph_built and registry is not None and router is not None:

                async def on_route(decision: RouteDecision) -> None:
                    session.route = decision
                    if session.trace is not None:
                        session.trace.route(decision)
                    if session.durable_data is not None:
                        session.durable_data["route"] = decision.as_dict()
                        run = NATIVE_RUN.get()
                        assert run is not None
                        await run.executor.store.update_runtime(
                            run.executor.guard.current, identity.execution_id, session.durable_data
                        )
                    self._emit(
                        "route.decision",
                        session.identity,
                        plugin=decision.plugin,
                        plugin_version=decision.plugin_version,
                        plugin_digest=decision.plugin_digest,
                        graph_version=decision.graph_version,
                        strategy=decision.strategy,
                        confidence=decision.confidence,
                        threshold=decision.threshold,
                        cache_hit=decision.cache_hit,
                    )

                def on_outcome(name: str, status: str, code: str) -> None:
                    if session.trace is not None:
                        session.trace.outcome(name, status, code)
                    self._emit(
                        "route.outcome",
                        session.identity,
                        plugin=name,
                        status=status,
                        error_code=code,
                    )

                session.graph = await build_dual_dag(
                    session.component,
                    session.workflow_id,
                    registry,
                    router,
                    on_route,
                    on_outcome,
                    fixed_decision=session.route if session.durable_data is not None else None,
                )
                session.graph_built = True
            if session.fresh:
                checkpointer = CheckpointerFactory.get_checkpointer()
                if await checkpointer.session_exists(
                    identity.child_session_id
                ) or await checkpointer.session_exists(session.workflow_id):
                    raise SessionStateError(
                        "META_COLD_SESSION_UNSUPPORTED",
                        "Existing checkpoints need explicit recovery.",
                    )
                session.fresh = False
            if queue is None:
                raw = await Runner.run_workflow(session.graph, inputs, session=session.workflow_id)
                if raw is None:
                    raise SessionStateError("META_KERNEL_PROTOCOL", "Workflow returned no result")
                if str(raw.state.value) == "INPUT_REQUIRED":
                    interactions = [
                        interaction_payload(c) for c in raw.result if c.type == INTERACTION
                    ]
                    result = AgentResult("", "input_required", identity, interactions)
                else:
                    result = self._final_result(raw.result["output"], identity)
            else:
                result = await self._stream_workflow(session, inputs, queue)
            if result.result_type == "input_required" and len(result.interactions) != 1:
                raise SessionStateError(
                    "META_MULTI_INTERRUPT_UNSUPPORTED",
                    "Exactly one pending interaction is supported.",
                )
            session.pending = result.interactions
            self._emit(
                "execution.end",
                identity,
                status=result.result_type,
                duration_ms=(perf_counter() - started) * 1000,
                **self._counts(session),
            )
            result = replace(
                result,
                usage=self._counts(session),
                route=session.route.as_dict() if session.route else None,
            )
            if session.durable_data is not None:
                data = session.durable_data
                data.update(
                    pending=result.interactions,
                    result=asdict(result),
                    resume_inputs=None,
                    resume_request_id=None,
                )
                run = NATIVE_RUN.get()
                assert run is not None
                await run.executor.store.update_runtime(
                    run.executor.guard.current,
                    identity.execution_id,
                    data,
                    status="paused" if result.result_type == "input_required" else "completed",
                )
            if queue is not None:
                event_type: Literal["input_required", "final"] = (
                    "input_required" if result.result_type == "input_required" else "final"
                )
                queue.put_nowait(
                    AgentEvent(
                        event_type,
                        {
                            "output": result.output,
                            "data": result.data,
                            "interactions": result.interactions,
                            "usage": result.usage,
                            "error": result.error,
                            "route": result.route,
                            "result_type": result.result_type,
                        },
                        identity,
                    )
                )
            return result
        except asyncio.CancelledError:
            session.broken = True
            self._emit(
                "execution.cancel",
                identity,
                status="cancelled",
                duration_ms=(perf_counter() - started) * 1000,
                **self._counts(session),
            )
            raise
        except Exception as error:
            session.broken = True
            self._emit(
                "execution.error",
                identity,
                status="error",
                duration_ms=(perf_counter() - started) * 1000,
                error_type=type(error).__name__,
                error_code=getattr(error, "code", "META_KERNEL_ERROR"),
                **self._counts(session),
            )
            raise

    def _counts(self, session: _Session) -> dict[str, int]:
        counts = {
            name: int(getattr(session.rail, name))
            for name in (
                "model_calls",
                "subagent_calls",
                "model_errors",
                "input_tokens",
                "output_tokens",
                "usage_reports",
                "trace_errors",
            )
        }
        counts["trace_errors"] = session.rail.trace_errors + session.host_trace_errors
        counts["deep_agent_calls"] = session.component.dispatch_count
        if session.component.goal is not None and session.component.goal.record is not None:
            goal = session.component.goal.record
            counts["goal_attempts"] = goal.attempt_count
            counts["goal_tokens"] = goal.token_usage.total_tokens
        return counts

    @staticmethod
    def _final_result(payload: dict[str, Any], identity: ExecutionIdentity) -> AgentResult:
        result_type = payload.get("result_type", "answer")
        if result_type not in {"answer", "error"}:
            raise MetaAgentError("META_KERNEL_PROTOCOL", "Invalid final result type.")
        return AgentResult(
            str(payload["answer"]),
            result_type,
            identity,
            error=payload.get("error"),
            data=payload.get("data"),
        )

    async def _stream_workflow(
        self, session: _Session, inputs: Any, queue: asyncio.Queue[AgentEvent | None]
    ) -> AgentResult:
        final: AgentResult | None = None
        interactions: list[dict[str, Any]] = []
        async with aclosing(
            Runner.run_workflow_streaming(
                session.graph,
                inputs,
                session=session.workflow_id,
                stream_modes=[BaseStreamMode.OUTPUT, BaseStreamMode.TRACE]
                if self._spec.trace.enabled
                else [BaseStreamMode.OUTPUT],
            )
        ) as chunks:
            async for chunk in chunks:
                if isinstance(chunk, TraceSchema):
                    payload = chunk.payload if isinstance(chunk.payload, dict) else {}
                    names = {
                        "traceId": "source_trace_id",
                        "invokeId": "invoke_id",
                        "parentInvokeId": "parent_invoke_id",
                        "loopIndex": "loop_index",
                        "componentId": "component_id",
                        "status": "status",
                    }
                    self._emit(
                        "workflow.trace",
                        session.identity,
                        **{
                            target: payload[key]
                            for key, target in names.items()
                            if isinstance(payload.get(key), (str, int, bool))
                        },
                    )
                elif chunk.type == session.component.delta_type:
                    queue.put_nowait(AgentEvent("delta", dict(chunk.payload), session.identity))
                elif chunk.type == INTERACTION:
                    interactions.append(interaction_payload(chunk))
                elif chunk.type == "workflow_final":
                    if chunk.payload.get("output", {}).get("__meta_final__") != session.workflow_id:
                        continue  # Plugin output is buffered and cannot own the public final.
                    if final is not None:
                        raise MetaAgentError("META_KERNEL_PROTOCOL", "Multiple workflow finals.")
                    final = self._final_result(chunk.payload["output"], session.identity)
        if interactions:
            return AgentResult("", "input_required", session.identity, interactions)
        if final is None:
            raise MetaAgentError("META_KERNEL_PROTOCOL", "Workflow ended without terminal output.")
        return final

    async def follow_up(self, text: str, *, session_id: str) -> None:
        """Queue text in the active native TaskLoop; idle turns use ``invoke``."""
        self._ensure_open()
        if self._recovery is not None:
            raise RecoveryConflict(
                "META_FOLLOW_UP_UNSUPPORTED", "Durable follow-up admission is not enabled"
            )
        session = self._sessions.get(session_id)
        if (
            session is None
            or session.task is None
            or session.task.done()
            or not self._spec.deep_agent.enable_task_loop
            or session.agent.loop_controller is None
        ):
            raise SessionStateError("META_NOT_ACTIVE", "Follow-up requires an active TaskLoop.")
        if not text.strip():
            raise SessionStateError("META_QUERY_REQUIRED", "Follow-up text must not be blank.")
        await session.agent.follow_up(text, session=session.component.child_session)
        self._emit("execution.follow_up", session.identity, status="queued")

    async def abort(self, session_id: str) -> None:
        """Cancel and await an active run; its session ID cannot be reused."""
        self._ensure_open()
        session = self._sessions.get(session_id)
        if session is None or session.task is None:
            raise SessionStateError("META_NOT_ACTIVE", "The session has no active request.")
        task = session.task
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await session.agent.abort(session=session.component.child_session)
        if session.component.goal is not None:
            await session.agent.stop()

    async def close_session(self, session_id: str) -> bool:
        """Close an idle local session; the host serializes this with admission."""
        self._ensure_open()
        if self._recovery is not None:
            raise SessionStateError(
                "META_SESSION_CLOSE_UNSUPPORTED",
                "Durable session deletion needs its recovery owner",
            )
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if session.task is not None:
            raise SessionConflict("META_SESSION_BUSY", "Wait for the active request before closing")
        await self._dispose_session(session)
        checkpointer = CheckpointerFactory.get_checkpointer()
        await checkpointer.release(session.workflow_id)
        await checkpointer.release(session.identity.child_session_id)
        self._release_snapshot(session)
        del self._sessions[session_id]
        return True

    async def aclose(self) -> None:
        if self._close_task is None:
            self._closed = True
            self._plugins.closed = True
            self._close_task = asyncio.create_task(self._close())
        try:
            await asyncio.shield(self._close_task)
        except Exception:
            # A failed native Runner stop retains its lifecycle ownership.
            # Let callers retry aclose instead of permanently stranding that lease.
            if self._runner_owned:
                self._close_task = None
            raise

    async def _close(self) -> None:
        active = list(
            {
                *[s.task for s in self._sessions.values() if s.task is not None],
                *self._durable_tasks.values(),
            }
        )
        active = [task for task in active if task is not asyncio.current_task()]
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        errors: list[Exception] = []

        async def attempt(action: Awaitable[Any]) -> None:
            try:
                await action
            except Exception as error:
                errors.append(error)

        for session in self._sessions.values():
            await attempt(session.agent.abort(session=session.component.child_session))
            await attempt(session.agent.stop())
            if session.component.goal is not None:
                await attempt(session.component.goal.close_session(persist=self._recovery is None))
            for rail in list(session.agent.configured_rails()):
                if session.agent.is_registered_rail(rail):
                    await attempt(session.agent.unregister_rail(rail))
            try:
                session.agent.ability_manager.teardown_tools()
            except Exception as error:
                errors.append(error)
            if not session.fresh and self._recovery is None:
                await attempt(CheckpointerFactory.get_checkpointer().release(session.workflow_id))
                await attempt(
                    CheckpointerFactory.get_checkpointer().release(
                        session.identity.child_session_id
                    )
                )
            try:
                self._release_skill_operation(session.identity.child_session_id)
            except Exception as error:
                errors.append(error)
        if self._gateway is not None:
            await attempt(self._gateway.aclose())
        try:
            self._release_sys_operations()
        except Exception as error:
            errors.append(error)
        for service in (self._memory, self._skills_runtime):
            if service is not None:
                await attempt(service.aclose())
        if self.evolution is not None:
            await attempt(self.evolution.aclose())
        if self._evolution_checkpoint is not None:
            await attempt(self._evolution_checkpoint.close())
        if self._tracing_owned:
            release_tracing()
            self._tracing_owned = False
        await attempt(self._plugins.aclose())
        self._emit("agent.shutdown", self._host_identity, status="closed")
        if self._ops is not None:
            await attempt(self._ops.aclose())
        try:
            if self._runner_owned:
                try:
                    await release_runner()
                except Exception as error:
                    errors.append(error)
                else:
                    self._runner_owned = False
        finally:
            try:
                self._sink.close()
            finally:
                if not self._runner_owned:
                    _LIVE_SCOPES.discard((self._spec.product_id, self._spec.agent_id))
        if errors:
            raise ExceptionGroup("MetaAgent resource cleanup failed", errors)

    async def _dispose_session(self, session: _Session) -> None:
        """Discard an idle in-memory harness while retaining durable state."""
        await session.agent.stop()
        if session.component.goal is not None:
            await session.component.goal.close_session(persist=self._recovery is None)
        for rail in list(session.agent.configured_rails()):
            if session.agent.is_registered_rail(rail):
                await session.agent.unregister_rail(rail)
        session.agent.ability_manager.teardown_tools()
        self._release_skill_operation(session.identity.child_session_id)

    def _release_skill_operation(self, session_id: str) -> None:
        operation_id = f"meta-skills-{session_id}"
        if operation_id in self._owned_sys_operations:
            Runner.resource_mgr.remove_sys_operation(operation_id)
            self._owned_sys_operations.discard(operation_id)

    def _release_sys_operations(self) -> None:
        for operation_id in list(self._owned_sys_operations):
            Runner.resource_mgr.remove_sys_operation(operation_id)
            self._owned_sys_operations.discard(operation_id)
