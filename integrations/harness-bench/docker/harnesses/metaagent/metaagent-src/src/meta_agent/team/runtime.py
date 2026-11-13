"""Local team facade using the native Runner and member coordination."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Mapping
from contextlib import aclosing
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal, Self
from uuid import uuid4

from openjiuwen.agent_teams import TeamAgent, TeamAgentSpec, TeamRole, TeamRuntimeContext, TeamSpec
from openjiuwen.agent_teams.context import reset_session_id, set_session_id
from openjiuwen.agent_teams.external.member_runtime import ExternalHarnessMemberRuntime
from openjiuwen.agent_teams.external.tool_gateway import ExternalTeamToolGateway
from openjiuwen.agent_teams.interaction import DeliverResult, HumanAgentMessage, HumanAgentToolCall
from openjiuwen.agent_teams.interaction.passive_tool_executor import PassiveToolExecutor
from openjiuwen.agent_teams.tools.team_tools import create_team_tools
from openjiuwen.core.runner import Runner
from openjiuwen.core.session import InteractiveInput
from openjiuwen.core.session.agent_team import Session as AgentTeamSession
from openjiuwen.core.session.checkpointer.checkpointer import CheckpointerConfig
from openjiuwen.harness_protocol import HarnessContext, ToolExecutionResult, ToolInvocation
from openjiuwen.harness_providers import register_harness_provider
from pydantic import PrivateAttr

from meta_agent.base_agent import MetaBaseAgent
from meta_agent.boot import MetaBootLoader
from meta_agent.boot.boot_loader import LoadedPackage
from meta_agent.checkpoint import LocalRecovery, PostgresRecoveryStore
from meta_agent.errors import BootError, SessionConflict, SessionStateError
from meta_agent.lifecycle import acquire_runner, release_runner
from meta_agent.team.provider import (
    BINDING_ENV,
    HARNESSES,
    KEEPALIVE,
    LEADER_ENV,
    PACKAGES,
    PROVIDER,
    RECOVERIES,
    TASKS_ENV,
    TEAM_TASK_TOOLS,
    TEAM_TOOLS,
    TRACE_CONTEXTS,
    MetaAgentHarness,
    MetaAgentHarnessProvider,
    scoped_id,
)
from meta_agent.team.recovery import TEAM_RECOVERY, TeamRecovery, native_home
from meta_agent.team.spec import MetaAgentTeamSpec
from meta_agent.trace.trajectory import acquire_team_tracing, release_tracing


class _TeamToolGateway(ExternalTeamToolGateway):  # type: ignore[misc]
    """Bind host listeners after native build_team creates configured members."""

    def __init__(self, on_built: Callable[[], Awaitable[None]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.on_built = on_built

    async def invoke(self, invocation: ToolInvocation) -> ToolExecutionResult:
        result = await super().invoke(invocation)
        if invocation.name == "build_team" and not result.is_error:
            await self.on_built()
        return result


class LocalTeamRuntimeSpec(TeamAgentSpec):  # type: ignore[misc]
    """Public build override supplies the Leader runtime; native Runner owns scheduling."""

    meta_binding: str
    meta_session_id: str = ""
    meta_task_management: bool = False
    _on_team_built: Callable[[], Awaitable[None]] | None = PrivateAttr(default=None)

    async def _notify_team_built(self) -> None:
        if self._on_team_built is not None:
            await self._on_team_built()

    def build(self, *, conversation_mode: Literal["team", "group_chat"] = "team") -> Any:
        if conversation_mode != "team":
            raise ValueError("Group chat is not supported by the local MetaAgentTeam")
        member = self.leader.member_name
        session_id = self.meta_session_id
        context = TeamRuntimeContext(
            role=TeamRole.LEADER,
            member_name=member,
            display_name=member,
            team_spec=TeamSpec(
                team_name=self.team_name,
                display_name=self.team_name,
                leader_member_name=member,
                language=self.language,
            ),
            db_config=self.resolve_db_config(),
            messager_config=self.transport.build(),
        )
        card = self.agents["leader"].card
        runtime = ExternalHarnessMemberRuntime(
            harness=MetaAgentHarness(self.meta_binding),
            context=HarnessContext(
                agent_name=member,
                agent_id=card.id,
                host_session_id=session_id,
                system_prompt=(
                    "You are the team leader. Use build_team to initialize collaboration. "
                    "Use send_message to delegate to configured members. "
                    "Your final text is delivered directly to the user. "
                    "Only configured members and the mounted tools are available. "
                    "Read available tool schemas; do not invent tool arguments."
                ),
            ),
        )
        agent = TeamAgent(card).configure(self, context, member_runtime=runtime)
        # Pass team_mode explicitly: the convenience gateway factory currently
        # defaults its build_team policy to dynamic membership.
        native_tools = create_team_tools(
            role="leader",
            agent_team=agent.team_backend,
            teammate_mode=self.teammate_mode,
            dispatch_mode=self.dispatch_mode,
            lifecycle=self.lifecycle,
            team_mode=self.team_mode,
            lang=self.language,
            parent_agent=agent,
            messager=agent.infra.messager,
            team_name=self.team_name,
            team_permissions_enabled=self.enable_permissions,
        )
        runtime.bind_tools(
            _TeamToolGateway(
                on_built=self._notify_team_built,
                session_id=session_id,
                team_backend=agent.team_backend,
                tools=[
                    tool
                    for tool in native_tools
                    if tool.card.name
                    in TEAM_TOOLS | (TEAM_TASK_TOOLS if self.meta_task_management else frozenset())
                ],
            )
        )
        return agent


class MetaAgentTeam:
    """One team session; optional LocalRecovery supports explicit checkpoint handoff."""

    def __init__(self, spec: MetaAgentTeamSpec, runtime: LocalTeamRuntimeSpec, bindings: list[str]):
        self.spec, self.runtime_spec, self.bindings = spec, runtime, bindings
        self._epoch = uuid4().hex
        self._session_id: str | None = None
        self._active: asyncio.Task[Any] | None = None
        self._closed = False
        self._recovery: TeamRecovery | None = None
        self._team_agent: Any = None
        self._suspending = False
        self._native_home: Path | None = None
        self._tracing_owned = False

    @classmethod
    async def from_package(
        cls,
        root: str | Path,
        *,
        env: Mapping[str, str] | None = None,
        recovery: LocalRecovery | None = None,
    ) -> Self:
        spec = MetaAgentTeamSpec.from_package(root, env=env)
        return await cls.create(spec, env=env, recovery=recovery)

    @classmethod
    async def create(
        cls,
        spec: MetaAgentTeamSpec,
        *,
        env: Mapping[str, str] | None = None,
        recovery: LocalRecovery | None = None,
    ) -> Self:
        packages = {
            name: MetaBootLoader(path, env=env).load() for name, path in spec.members.items()
        }
        return await cls.from_loaded(spec, packages, recovery=recovery)

    @classmethod
    async def from_loaded(
        cls,
        spec: MetaAgentTeamSpec,
        packages: Mapping[str, LoadedPackage],
        *,
        recovery: LocalRecovery | None = None,
    ) -> Self:
        """Build a session from the host's already validated business packages."""
        if set(packages) != set(spec.members):
            raise ValueError("Loaded packages must match the configured team members")
        shared = recovery is not None and isinstance(recovery.store, PostgresRecoveryStore)
        packages = {name: packages[name] for name in spec.members}
        observation = spec.observability
        for package in packages.values():
            member_config = package.spec.trace.observability
            if member_config is not None and member_config.enabled:
                if observation is None:
                    observation = member_config
                elif observation != member_config:
                    raise BootError(
                        "META_OBSERVABILITY_CONFLICT",
                        "Team and members must use one observability configuration",
                    )
        if observation is not None and observation.enabled:
            packages = {
                name: replace(
                    package,
                    spec=package.spec.model_copy(
                        update={
                            "trace": package.spec.trace.model_copy(
                                update={"observability": observation}
                            )
                        }
                    ),
                )
                for name, package in packages.items()
            }
        durable = TeamRecovery(recovery, spec.team_name) if recovery is not None else None
        if durable is not None:
            assert recovery is not None
            if any(p.spec.fastpath.enabled for n, p in packages.items() if n != spec.leader):
                raise SessionStateError(
                    "META_TEAM_RECOVERY_FAST_REPLY",
                    "Teammate fast-path auto-replies need a durable delivery binding",
                )
            await durable.open(
                {
                    "spec": spec.model_dump(
                        exclude={"observability"} | ({"state_dir"} if shared else set())
                    ),
                    "members": {
                        name: recovery.config_digest(package.spec, package.digest)
                        for name, package in packages.items()
                    },
                }
            )
        runner_owned = False
        try:
            epoch = durable.manifest["epoch"] if durable else uuid4().hex
            state = Path(spec.state_dir).resolve() / epoch
            state.mkdir(parents=True, exist_ok=True)
            bindings = {name: scoped_id(epoch, name) for name in packages}
            native = packages[spec.leader].spec.deep_agent
            # The native spec is persisted in team state; member models stay in PACKAGES.
            leader = {"card": native.card.model_dump(), "workspace": native.workspace.model_dump()}
            runtime = LocalTeamRuntimeSpec(
                meta_binding=bindings[spec.leader],
                meta_task_management=spec.task_management,
                team_name=spec.team_name + "-" + state.name,
                agents={"leader": leader},
                leader={"member_name": spec.leader, "display_name": spec.leader},
                storage=(
                    {
                        "type": "postgresql",
                        "params": {"connection_string": recovery.store.sqlalchemy_url()},
                    }
                    if recovery is not None and isinstance(recovery.store, PostgresRecoveryStore)
                    else {"type": "sqlite", "params": {"connection_string": str(state / "team.db")}}
                ),
                transport={"type": "inprocess"},
                spawn_mode="inprocess",
                lifecycle="persistent",
                dispatch_mode=spec.dispatch_mode,
                evolution_enabled=False,
                enable_permissions=any(p.spec.permissions.enabled for p in packages.values()),
                enable_hitt=bool(spec.human_members),
                language=spec.language,
                team_mode="predefined",
                predefined_members=[
                    {
                        "member_name": name,
                        "display_name": name,
                        "desc": f"MetaAgent {name}",
                        "role_type": "external_cli",
                        "external_cli": {
                            "cli_agent": PROVIDER,
                            "inject_mcp": False,
                            "env": {
                                BINDING_ENV: bindings[name],
                                LEADER_ENV: spec.leader,
                                TASKS_ENV: "1" if spec.task_management else "0",
                            },
                        },
                    }
                    for name in packages
                    if name != spec.leader
                ]
                + [
                    {
                        "member_name": name,
                        "display_name": display,
                        "role_type": "passive_human",
                        "desc": "Human collaborator",
                    }
                    for name, display in spec.human_members.items()
                ],
                external_cli_agents=[
                    {
                        "cli_agent": PROVIDER,
                        "inject_mcp": False,
                        "env": {
                            BINDING_ENV: json.dumps(bindings),
                            LEADER_ENV: spec.leader,
                            TASKS_ENV: "1" if spec.task_management else "0",
                        },
                    }
                ],
            )
            await acquire_runner(
                CheckpointerConfig(
                    type="meta_local_recovery", conf={"backend_id": recovery.store.backend_id}
                )
                if recovery
                else CheckpointerConfig(type="in_memory")
            )
            runner_owned = True
            if observation is not None and observation.enabled:
                acquire_team_tracing(observation)
        except BaseException:
            if runner_owned:
                await release_runner()
            if durable:
                await durable.guard.aclose()
            raise
        for name, binding in bindings.items():
            PACKAGES[binding] = packages[name]
            if observation is not None and observation.enabled:
                TRACE_CONTEXTS[binding] = {
                    "name": spec.team_name,
                    "member": name,
                    "role": "leader" if name == spec.leader else "teammate",
                }
            if recovery is not None:
                RECOVERIES[binding] = recovery
            else:
                KEEPALIVE.add(binding)
        register_harness_provider(PROVIDER, MetaAgentHarnessProvider)
        team = cls(spec, runtime, list(bindings.values()))
        team._tracing_owned = observation is not None and observation.enabled
        team._epoch, team._recovery = epoch, durable
        if shared:
            team._native_home = state / "native-home"
            if os.name == "nt":
                # Native session/message IDs make paths exceed MAX_PATH even
                # with a short state directory. Keep file spill working on Windows.
                team._native_home = Path("\\\\?\\" + str(team._native_home))
        if durable:
            team._session_id = durable.manifest["session_id"]
        return team

    @property
    def member_results(self) -> dict[str, list[dict[str, Any]]]:
        return {
            name: [r for h in HARNESSES.get(binding, []) for r in h.results]
            for name, binding in zip(self.spec.members, self.bindings, strict=True)
        }

    def member_agent(self, name: str) -> MetaBaseAgent:
        """Return an initialized member DAG for host inspection or idle-time evolution."""
        if self._closed or name not in self.spec.members:
            raise SessionStateError("META_TEAM_MEMBER", "Unknown or closed team member")
        binding = self.bindings[list(self.spec.members).index(name)]
        for harness in reversed(HARNESSES.get(binding, [])):
            if harness.agent is not None:
                return harness.agent
        raise SessionStateError("META_TEAM_MEMBER", "Member has not started yet")

    @property
    def pending_interactions(self) -> dict[str, list[dict[str, Any]]]:
        """Checkpointed member results currently waiting for an answer."""
        return {
            name: [
                h.pending
                for h in HARNESSES.get(binding, [])
                if h.pending is not None and h.active_turn is not None
            ]
            for name, binding in zip(self.spec.members, self.bindings, strict=True)
        }

    async def stream(
        self,
        query: Any,
        *,
        session_id: str,
        on_team_built: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncGenerator[Any, None]:
        if self._closed:
            raise SessionStateError("META_TEAM_CLOSED", "The team is closed")
        if self._active is not None:
            raise SessionConflict("META_TEAM_BUSY", "The team already has an active request")
        resuming = query is None and self._recovery is not None
        if not session_id.strip() or (
            not resuming and (not isinstance(query, str) or not query.strip())
        ):
            raise SessionStateError("META_TEAM_INPUT", "A session ID and text query are required")
        if self._session_id is not None and self._session_id != session_id:
            raise SessionConflict("META_TEAM_SESSION", "Create a separate team for another session")
        self._session_id = session_id
        self._active = asyncio.current_task()
        self.runtime_spec.meta_session_id = scoped_id(self._epoch, session_id)
        for binding in self.bindings:
            if binding in TRACE_CONTEXTS:
                TRACE_CONTEXTS[binding].update(
                    session_id=session_id, native_session_id=self.runtime_spec.meta_session_id
                )
        self.runtime_spec._on_team_built = on_team_built
        try:
            if self._recovery is not None:
                async with aclosing(self._durable_stream(query, session_id=session_id)) as events:
                    async for chunk in events:
                        yield chunk
                return
            async with aclosing(
                Runner.run_agent_team_streaming(
                    agent_team=self.runtime_spec,
                    inputs={"query": query},
                    session=scoped_id(self._epoch, session_id),
                )
            ) as events:
                async for chunk in events:
                    yield chunk
                    if (
                        isinstance(chunk.payload, dict)
                        and chunk.payload.get("event_type") == "team.idle"
                    ):
                        await Runner.pause_agent_team(
                            team_name=self.runtime_spec.team_name,
                            session_id=self.runtime_spec.meta_session_id,
                        )
        finally:
            self._active = None

    async def invoke(self, query: Any, *, session_id: str) -> list[Any]:
        return [chunk async for chunk in self.stream(query, session_id=session_id)]

    def resume(self, *, session_id: str) -> AsyncIterator[Any]:
        """Re-emit the stored Leader interaction; answer through the usual answer API."""
        return self.stream(None, session_id=session_id)

    def is_member_approval(self, interaction_id: str) -> bool:
        """Member permissions are answered through native Leader approve_tool."""
        return any(
            h.active_turn is not None and h.pending_approval_id == interaction_id
            for name, binding in zip(self.spec.members, self.bindings, strict=True)
            if name != self.spec.leader
            for h in HARNESSES.get(binding, [])
        )

    @property
    def suspended_members(self) -> dict[str, dict[str, Any]]:
        return dict(self._recovery.manifest.get("pending_members", {})) if self._recovery else {}

    async def _restore_members(self) -> None:
        # Run inside the Leader's first turn, after native coordination starts.
        # This also keeps native teardown responsible for failed member startup.
        await self._team_agent.recover_team()
        for name, saved in self.suspended_members.items():
            binding = self.bindings[list(self.spec.members).index(name)]
            harnesses = HARNESSES.get(binding, [])
            if not harnesses:
                raise SessionStateError(
                    "META_TEAM_MEMBER_RESUME", "Suspended member was not reconstructed"
                )
            # Native spawn returns before the harness has started.
            await harnesses[-1].restore_pending_turn(saved)

    async def suspend(self) -> None:
        """Stop at Leader input with members settled or awaiting native tool approval."""
        if self._recovery is None or self._active is None or self._team_agent is None:
            raise SessionStateError("META_TEAM_SUSPEND", "A recoverable team stream is required")
        leader_pending = False
        pending_members = {}
        for name, binding in zip(self.spec.members, self.bindings, strict=True):
            for harness in HARNESSES.get(binding, []):
                if name == self.spec.leader:
                    leader_pending |= (
                        harness.pending is not None and harness.active_turn is not None
                    )
                elif harness.active_turn is not None:
                    if harness.pending_approval_id is None:
                        raise SessionConflict(
                            "META_TEAM_MEMBER_BUSY", "Member must finish or reach tool approval"
                        )
                    pending_members[name] = harness.pending
        if not leader_pending:
            raise SessionStateError("META_TEAM_SUSPEND", "Suspend at a Leader interaction")
        self._suspending = True
        self._recovery.manifest["pending_members"] = pending_members
        token = TEAM_RECOVERY.set(self._recovery)
        try:
            with native_home(self._native_home):
                await self._team_agent.stop_coordination()
        finally:
            TEAM_RECOVERY.reset(token)

    async def _durable_stream(self, query: Any, *, session_id: str) -> AsyncGenerator[Any, None]:
        durable = self._recovery
        assert durable is not None
        if (query is None) != (durable.manifest["status"] == "suspended"):
            raise SessionStateError("META_TEAM_RESUME", "Use resume only for a suspended team")
        self._suspending = False
        queue: asyncio.Queue[Any] = asyncio.Queue()
        end = object()

        async def drive() -> None:
            with native_home(self._native_home):
                await drive_at_home()

        async def drive_at_home() -> None:
            token = TEAM_RECOVERY.set(durable)
            session = AgentTeamSession(
                session_id=self.runtime_spec.meta_session_id, team_id=self.runtime_spec.team_name
            )
            finished = False
            try:
                if self._native_home is not None:
                    await durable.restore_files(self._native_home)
                await durable.status("running", session_id)
                await session.pre_run()
                if self._team_agent is None or query is None:
                    # suspend() stopped the previous harness. Rebuild the same
                    # custom Leader for both same-host and new-host handoff.
                    self._team_agent = self.runtime_spec.build()
                    await self._team_agent.team_backend.db.initialize()
                    await self._team_agent.recover_for_existing_session(session)
                    if query is None:
                        await self.runtime_spec._notify_team_built()
                    if query is None and self.suspended_members:
                        leader = self._team_agent.resources.harness.harness
                        leader.before_resume = self._restore_members
                async with aclosing(
                    self._team_agent.stream(
                        {
                            "query": query
                            if query is not None
                            else "Continue the suspended request."
                        },
                        session=session,
                    )
                ) as events:
                    async for chunk in events:
                        await queue.put(chunk)
                        if (
                            isinstance(chunk.payload, dict)
                            and chunk.payload.get("event_type") == "team.idle"
                        ):
                            await self._team_agent.pause_coordination()
                finished = True
            finally:
                try:
                    await session.post_run()
                    if finished:
                        if self._native_home is not None:
                            await durable.save_files(self._native_home)
                        await durable.status(
                            "suspended" if self._suspending else "ready", session_id
                        )
                finally:
                    TEAM_RECOVERY.reset(token)

        async def pump() -> None:
            try:
                await durable.guard.run(drive)
            finally:
                await queue.put(end)

        task = asyncio.create_task(pump())
        try:
            while (chunk := await queue.get()) is not end:
                yield chunk
            await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def answer(self, interaction_id: str, answer: Any) -> Any:
        """Answer a pending Leader interaction while consuming its stream."""
        if self._active is None or self._closed:
            raise SessionStateError("META_TEAM_INACTIVE", "No active team interaction")
        reply = InteractiveInput()
        reply.update(interaction_id, answer)
        if self._recovery is not None:
            with native_home(self._native_home):
                await self._team_agent.resume_interrupt(reply)
            return None
        return await Runner.interact_agent_team(
            reply,
            team_name=self.runtime_spec.team_name,
            session_id=self.runtime_spec.meta_session_id,
        )

    async def _durable_human_call(self, call: Callable[[], Awaitable[Any]]) -> Any:
        assert self._recovery is not None
        token = set_session_id(self.runtime_spec.meta_session_id)
        recovery_token = TEAM_RECOVERY.set(self._recovery)
        try:
            with native_home(self._native_home):
                return await self._recovery.guard.run(call)
        finally:
            TEAM_RECOVERY.reset(recovery_token)
            reset_session_id(token)

    async def human_message(self, sender: str, target: str, body: str) -> Any:
        """Host-authenticated human identity, delivered by the native HITT inbox."""
        if self._closed or self._active is None:
            raise SessionStateError("META_TEAM_INACTIVE", "Consume the team stream first")
        if sender not in self.spec.human_members or target not in self.spec.members:
            raise SessionStateError("META_TEAM_HUMAN", "Unknown human sender or agent target")
        if self._recovery is not None:

            async def deliver() -> Any:
                await self._team_agent.auto_start_member(target)
                return await self._team_agent.human_agent_say(body, to=target, sender=sender)

            return await self._durable_human_call(deliver)
        return await Runner.interact_agent_team(
            HumanAgentMessage(body=body, sender=sender, target=target),
            team_name=self.runtime_spec.team_name,
            session_id=self.runtime_spec.meta_session_id,
        )

    async def listen_human(
        self, member: str, callback: Callable[[Any], Awaitable[None]] | None
    ) -> bool:
        """Subscribe the host UI to native team messages for a human member."""
        if self._closed or self._active is None or member not in self.spec.human_members:
            raise SessionStateError("META_TEAM_HUMAN", "An active registered human is required")
        if self._recovery is not None:
            await self._durable_human_call(
                lambda: self._team_agent.team_backend.register_human_agent_inbound(member, callback)
            )
            return True
        return bool(
            await Runner.register_human_agent_inbound(
                team_name=self.runtime_spec.team_name,
                session_id=self.runtime_spec.meta_session_id,
                member_name=member,
                callback=callback,
            )
        )

    async def human_tool(self, sender: str, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a native task action under the authenticated human member identity."""
        if self._closed or self._active is None:
            raise SessionStateError("META_TEAM_INACTIVE", "Consume the team stream first")
        if sender not in self.spec.human_members:
            raise SessionStateError("META_TEAM_HUMAN", "Unknown human sender")
        if not self.spec.task_management:
            raise SessionStateError("META_TEAM_TASKS", "Enable task_management in meta_team.yaml")
        if self._recovery is not None:

            async def execute() -> Any:
                backend = self._team_agent.team_backend
                if not await backend.is_passive_human(sender):
                    raise SessionStateError("META_TEAM_HUMAN", "A passive human is required")
                executor = PassiveToolExecutor(backend, language=self.spec.language)
                output = await executor.execute(sender, name, arguments)
                if not output.success:
                    return DeliverResult.failure(output.error or "tool_failed")
                return DeliverResult.tool_success(
                    output=executor.map_output(name, output), data=output.data
                )

            return await self._durable_human_call(execute)
        return await Runner.interact_agent_team(
            HumanAgentToolCall(sender=sender, tool_name=name, tool_args=arguments),
            team_name=self.runtime_spec.team_name,
            session_id=self.runtime_spec.meta_session_id,
        )

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        for binding in self.bindings:
            KEEPALIVE.discard(binding)
        if self._active is not None and self._active is not asyncio.current_task():
            self._active.cancel()
            await asyncio.gather(self._active, return_exceptions=True)
        try:
            if self._session_id is not None:
                if self._recovery is None:
                    await Runner.stop_agent_team(
                        team_name=self.runtime_spec.team_name,
                        session_id=scoped_id(self._epoch, self._session_id),
                    )
                elif self._team_agent is not None:
                    token = TEAM_RECOVERY.set(self._recovery)
                    try:
                        with native_home(self._native_home):
                            await self._team_agent.stop_coordination()
                    finally:
                        TEAM_RECOVERY.reset(token)
        finally:
            try:
                for binding in self.bindings:
                    for harness in HARNESSES.pop(binding, []):
                        await harness.stop()
                        await harness.close_member()
                    PACKAGES.pop(binding, None)
                    RECOVERIES.pop(binding, None)
                    TRACE_CONTEXTS.pop(binding, None)
            finally:
                try:
                    if self._tracing_owned:
                        release_tracing()
                        self._tracing_owned = False
                    await release_runner()
                finally:
                    if self._recovery is not None:
                        await self._recovery.guard.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
