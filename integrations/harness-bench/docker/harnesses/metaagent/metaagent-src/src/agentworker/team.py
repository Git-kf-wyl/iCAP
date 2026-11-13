"""One native team per A2A context, retaining its stream across human input."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import aclosing
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from meta_agent.boot import MetaBootLoader
from meta_agent.checkpoint import LocalRecovery, PostgresRecoveryStore
from meta_agent.errors import (
    MetaAgentError,
    RequestConflictError,
    SessionConflict,
    SessionStateError,
)
from meta_agent.identity import ExecutionIdentity
from meta_agent.team import MetaAgentTeam, MetaAgentTeamSpec
from meta_agent.team.provider import scoped_id


def _sum_usage(*reports: dict[str, int]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for report in reports:
        for name, value in report.items():
            totals[name] = totals.get(name, 0) + value
    return totals


@dataclass(frozen=True)
class TeamEvent:
    type: Literal["member_result", "input_required", "final"]
    data: dict[str, Any]
    identity: ExecutionIdentity


@dataclass
class _Conversation:
    identity: ExecutionIdentity
    package_digest: str
    config_revision: int = 1
    team: MetaAgentTeam | None = None
    pump: asyncio.Task[None] | None = None
    queue: asyncio.Queue[TeamEvent | Exception] = field(default_factory=asyncio.Queue)
    requests: set[str] = field(default_factory=set)
    pending: str | None = None
    results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    pending_usage: dict[str, dict[str, int]] = field(default_factory=dict)
    human_inbox: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    human_ready: bool = False
    human_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    busy: bool = False
    closed: bool = False


class TeamWorker:
    def __init__(
        self, root: str | Path, *, env: Mapping[str, str], recovery: LocalRecovery | None = None
    ) -> None:
        self.root, self.env = Path(root).resolve(), dict(env)
        self.config_revision = 1
        self.spec = MetaAgentTeamSpec.from_package(root, env=env)
        self.packages = {
            name: MetaBootLoader(path, env=env).load() for name, path in self.spec.members.items()
        }
        self.recovery = recovery
        if recovery is not None and any(
            p.spec.fastpath.enabled for n, p in self.packages.items() if n != self.spec.leader
        ):
            raise SessionStateError(
                "META_TEAM_RECOVERY_FAST_REPLY",
                "Teammate fast-path auto-replies need a durable delivery binding",
            )
        self.product_id = self.packages[self.spec.leader].spec.product_id
        self.digest = hashlib.sha256(
            json.dumps(
                [
                    self.spec.model_dump(
                        exclude={"state_dir"}
                        if recovery is not None
                        and isinstance(recovery.store, PostgresRecoveryStore)
                        else set()
                    ),
                    {name: p.digest for name, p in self.packages.items()},
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        self.sessions: dict[str, _Conversation] = {}
        self.closed = False

    async def stream(
        self,
        query: Any,
        *,
        session_id: str,
        request_id: str,
        previous: dict[str, Any] | None = None,
    ) -> AsyncIterator[TeamEvent]:
        if self.closed:
            raise SessionStateError("META_TEAM_CLOSED", "The team worker is closed")
        conversation = self.sessions.get(session_id)
        if conversation is None:
            conversation = _Conversation(
                ExecutionIdentity(
                    self.product_id, self.spec.team_name, session_id, request_id, uuid4().hex
                ),
                package_digest=self.digest,
                config_revision=self.config_revision,
            )
            self.sessions[session_id] = conversation
        if conversation.closed:
            raise SessionStateError(
                "META_SESSION_CLOSED", "Start a new context after cancellation/failure"
            )
        if conversation.busy:
            raise SessionConflict("META_SESSION_CONFLICT", "The conversation already has a request")
        if request_id in conversation.requests:
            raise RequestConflictError("META_REQUEST_REPLAY", "messageId was already used")
        conversation.busy = True
        conversation.requests.add(request_id)
        completed_request = False
        try:
            if previous is not None:
                # Only the executor's stored task artifact supplies recovery data.
                assert self.recovery is not None
                conversation.identity = ExecutionIdentity(**previous["identity"])
                conversation.pending = previous["team"]["interaction_id"]
                conversation.results = previous["team"]["members"]
                conversation.pending_usage = previous["team"]["pending_usage"]
                conversation.human_inbox = previous["team"].get("human_inbox", {})
            if conversation.team is None:
                spec = self.spec
                if self.recovery is not None:
                    # Independent contexts share one store/Runner configuration,
                    # but retain distinct team leases, epochs and checkpoints.
                    spec = spec.model_copy(
                        update={"team_name": "a2a-" + scoped_id(spec.team_name, session_id)}
                    )
                conversation.team = await MetaAgentTeam.from_loaded(
                    spec, self.packages, recovery=self.recovery
                )
            if conversation.pending is not None:
                conversation.identity = replace(conversation.identity, request_id=request_id)
                if self.recovery is not None:
                    conversation.pump = asyncio.create_task(
                        self._run(conversation, query, resuming=True)
                    )
                else:
                    interaction_id, conversation.pending = conversation.pending, None
                    await conversation.team.answer(interaction_id, query)
            else:
                if conversation.pump is not None and not conversation.pump.done():
                    raise SessionConflict("META_SESSION_CONFLICT", "The team is still running")
                conversation.identity = replace(
                    conversation.identity, request_id=request_id, execution_id=uuid4().hex
                )
                conversation.results = {name: [] for name in conversation.team.spec.members}
                conversation.pending_usage = {}
                conversation.pump = asyncio.create_task(self._run(conversation, query))
            while True:
                event = await conversation.queue.get()
                if isinstance(event, Exception):
                    raise event
                terminal = event.type in {"final", "input_required"}
                if event.type == "final" or (terminal and self.recovery is not None):
                    assert conversation.pump is not None
                    await conversation.pump
                completed_request = terminal
                yield event
                if terminal:
                    return
        finally:
            conversation.busy = False
            if not completed_request:
                await self.abort(session_id)

    async def _run(
        self, conversation: _Conversation, query: Any, *, resuming: bool = False
    ) -> None:
        team = conversation.team
        assert team is not None
        spec = team.spec
        offsets = {name: len(rows) for name, rows in team.member_results.items()}
        results = conversation.results
        suspended: dict[str, Any] | None = None

        async def receive_human(event: Any) -> None:
            inbox = conversation.human_inbox.setdefault(event.member_name, [])
            if not any(row["message_id"] == event.message_id for row in inbox):
                inbox.append({"cursor": len(inbox) + 1, **asdict(event)})

        async def register_humans() -> None:
            for member in spec.human_members:
                if not await team.listen_human(member, receive_human):
                    raise SessionStateError("META_TEAM_HUMAN", "Human inbox registration failed")
            conversation.human_ready = bool(spec.human_members)

        async def collect() -> None:
            for name, rows in team.member_results.items():
                for result in rows[offsets[name] :]:
                    # LocalRecovery reports usage for each resumed segment.
                    # Carry the interrupted segment into its completed result.
                    carried = conversation.pending_usage.pop(result["identity"]["execution_id"], {})
                    if carried:
                        result = {**result, "usage": _sum_usage(carried, result["usage"])}
                    results[name].append(result)
                    await conversation.queue.put(
                        TeamEvent(
                            "member_result",
                            {"member": name, "result": result},
                            conversation.identity,
                        )
                    )
                    if result["result_type"] == "error":
                        raise MetaAgentError("META_TEAM_MEMBER_FAILED", f"Member {name} failed")
                offsets[name] = len(rows)

        try:
            async with aclosing(
                team.stream(
                    None if resuming else query,
                    session_id=conversation.identity.session_id,
                    on_team_built=register_humans,
                )
            ) as events:
                async for chunk in events:
                    if (
                        isinstance(chunk.payload, dict)
                        and chunk.payload.get("event_type") == "team.runtime_ready"
                    ):
                        try:
                            await register_humans()
                        except KeyError:
                            # First turn: configured humans are created by build_team.
                            # Its gateway callback registers before the next model call.
                            pass
                    await collect()
                    if chunk.type == "__interaction__":
                        if team.is_member_approval(chunk.payload.id):
                            continue
                        if resuming:
                            if chunk.payload.id != conversation.pending:
                                raise SessionStateError(
                                    "META_TEAM_INTERACTION", "Stored interaction changed"
                                )
                            await team.answer(chunk.payload.id, query)
                            conversation.pending = None
                            resuming = False
                            continue
                        pending = team.pending_interactions[spec.leader]
                        if not pending:
                            raise SessionStateError(
                                "META_TEAM_INTERACTION", "Expected a Leader interaction"
                            )
                        conversation.pending = chunk.payload.id
                        if self.recovery is not None:
                            suspended = dict(pending[-1])
                            # Drain admitted human actions before the native snapshot.
                            async with conversation.human_lock:
                                conversation.human_ready = False
                            # Settle active computation; tool approvals can be retained.
                            while True:
                                try:
                                    await team.suspend()
                                    break
                                except SessionConflict as error:
                                    if error.code != "META_TEAM_MEMBER_BUSY":
                                        raise
                                    if any(
                                        rows
                                        for name, rows in team.pending_interactions.items()
                                        if name != spec.leader
                                    ):
                                        raise SessionStateError(
                                            "META_TEAM_MEMBER_INPUT",
                                            "Finish member interactions before handoff",
                                        ) from error
                                    await asyncio.sleep(0.02)
                            continue
                        await conversation.queue.put(
                            TeamEvent(
                                "input_required",
                                {**pending[-1], "team": {"name": spec.team_name}},
                                conversation.identity,
                            )
                        )
            await collect()
            if suspended is not None:
                for pending_result in [suspended, *team.suspended_members.values()]:
                    member_execution = pending_result["identity"]["execution_id"]
                    conversation.pending_usage[member_execution] = _sum_usage(
                        conversation.pending_usage.get(member_execution, {}),
                        pending_result["usage"],
                    )
                await conversation.queue.put(
                    TeamEvent(
                        "input_required",
                        {
                            **suspended,
                            "team": {
                                "name": spec.team_name,
                                "leader": spec.leader,
                                "members": results,
                                "pending_members": team.suspended_members,
                                "pending_usage": conversation.pending_usage,
                                "human_inbox": conversation.human_inbox,
                                "interaction_id": conversation.pending,
                                "recoverable": True,
                            },
                        },
                        conversation.identity,
                    )
                )
                return
            if not results[spec.leader]:
                raise MetaAgentError("META_TEAM_RESULT_MISSING", "Leader produced no final result")
            final = results[spec.leader][-1]
            usage = _sum_usage(*(r["usage"] for rows in results.values() for r in rows))
            await conversation.queue.put(
                TeamEvent(
                    "final",
                    {
                        **final,
                        "usage": usage,
                        "team": {
                            "name": spec.team_name,
                            "leader": spec.leader,
                            "members": results,
                        },
                    },
                    conversation.identity,
                )
            )
        except Exception as error:
            await conversation.queue.put(error)
        finally:
            conversation.human_ready = False

    def _human_context(self, session_id: str, member: str) -> _Conversation:
        conversation = self.sessions.get(session_id)
        if conversation is None:
            raise SessionStateError("META_TEAM_CONTEXT", "Unknown team context")
        if conversation.team is None or member not in conversation.team.spec.human_members:
            raise SessionStateError("META_TEAM_HUMAN", "Unknown configured human member")
        return conversation

    def context_team(self, session_id: str) -> MetaAgentTeam:
        """Return this context's initialized native Team and member DAGs."""
        conversation = self.sessions.get(session_id)
        if conversation is None or conversation.team is None or conversation.closed:
            raise SessionStateError("META_TEAM_CONTEXT", "Unknown or closed team context")
        return conversation.team

    def context_digest(self, session_id: str) -> str:
        """A running context keeps the package version it originally loaded."""
        conversation = self.sessions.get(session_id)
        return conversation.package_digest if conversation is not None else self.digest

    def reload(self) -> dict[str, Any]:
        """Load the host-edited team package for new contexts; keep live contexts intact."""
        if self.recovery is not None:
            raise SessionStateError("META_TEAM_RELOAD", "Reload requires the default runtime mode")
        candidate = TeamWorker(self.root, env=self.env)
        if (
            candidate.spec.team_name != self.spec.team_name
            or candidate.product_id != self.product_id
        ):
            raise SessionStateError(
                "META_TEAM_RELOAD", "Keep the worker's team and product identity"
            )
        self.spec, self.packages = candidate.spec, candidate.packages
        self.digest = candidate.digest
        self.config_revision += 1
        return {"applies_to": "new_contexts", **self.inspect()}

    def human_inbox(self, session_id: str, member: str, *, after: int = 0) -> dict[str, Any]:
        conversation = self._human_context(session_id, member)
        inbox = conversation.human_inbox.get(member, [])
        return {
            "context_id": session_id,
            "member": member,
            "ready": conversation.human_ready,
            "messages": inbox[after:],
            "next_cursor": len(inbox),
        }

    async def human_message(
        self, session_id: str, member: str, target: str, body: str
    ) -> dict[str, Any]:
        """The authenticated host supplies the configured human identity."""
        conversation = self._human_context(session_id, member)
        async with conversation.human_lock:
            if conversation.closed or not conversation.human_ready:
                raise SessionStateError("META_TEAM_INACTIVE", "No active human collaboration")
            assert conversation.team is not None
            delivered = await conversation.team.human_message(member, target, body)
        if not delivered.ok:
            raise SessionStateError("META_TEAM_HUMAN_DELIVERY", delivered.reason or "Send failed")
        return {"context_id": session_id, "member": member, **asdict(delivered)}

    async def human_tool(
        self, session_id: str, member: str, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        conversation = self._human_context(session_id, member)
        async with conversation.human_lock:
            if conversation.closed or not conversation.human_ready:
                raise SessionStateError("META_TEAM_INACTIVE", "No active human collaboration")
            assert conversation.team is not None
            delivered = await conversation.team.human_tool(member, name, arguments)
        if not delivered.ok:
            raise SessionStateError("META_TEAM_HUMAN_TOOL", delivered.reason or "Action failed")
        return {"context_id": session_id, "member": member, **asdict(delivered)}

    def inspect(self) -> dict[str, Any]:
        return {
            "team_name": self.spec.team_name,
            "leader": self.spec.leader,
            "durable": self.recovery is not None,
            "members": list(self.spec.members),
            "human_members": self.spec.human_members,
            "task_management": self.spec.task_management,
            "dispatch_mode": self.spec.dispatch_mode,
            "config_revision": self.config_revision,
            "sessions": {
                session_id: {
                    "state": "closed"
                    if c.closed
                    else (
                        "input_required"
                        if c.pending
                        else ("working" if c.pump is not None and not c.pump.done() else "idle")
                    ),
                    "execution_id": c.identity.execution_id,
                    "human_ready": c.human_ready,
                    "config_revision": c.config_revision,
                    "members": list(c.team.spec.members) if c.team else [],
                }
                for session_id, c in self.sessions.items()
            },
        }

    async def abort(self, session_id: str) -> None:
        conversation = self.sessions.get(session_id)
        if conversation is None or conversation.closed:
            return
        conversation.closed = True
        conversation.pending = None
        if conversation.pump is not None:
            conversation.pump.cancel()
            await asyncio.gather(conversation.pump, return_exceptions=True)
        if conversation.team is not None:
            await conversation.team.aclose()

    async def aclose(self) -> None:
        self.closed = True
        for session_id in self.sessions:
            await self.abort(session_id)
