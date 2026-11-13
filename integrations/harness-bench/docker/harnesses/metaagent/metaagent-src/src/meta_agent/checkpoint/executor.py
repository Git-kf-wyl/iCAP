"""One durable effect boundary for explicitly managed, trusted adapters."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

from meta_agent.checkpoint.contracts import EffectState, OperationIdentity, OperationScope
from meta_agent.checkpoint.lease import LeaseGuard
from meta_agent.checkpoint.models import (
    EffectCall,
    EffectIntent,
    RecoverySnapshot,
    canonical,
    identifier,
)
from meta_agent.checkpoint.store import RecoveryStore
from meta_agent.errors import ControlFlowError, RecoveryConflict, SideEffectUnresolved

EffectFunction = Callable[[EffectCall, dict[str, Any]], Awaitable[dict[str, Any]]]
QueryFunction = Callable[[EffectCall, dict[str, Any]], Awaitable[dict[str, Any] | None]]
Observer = Callable[[str, OperationIdentity], Awaitable[None]]


@dataclass(frozen=True)
class EffectAdapter:
    """Host-owned adapter. Deduplication must be guaranteed by the downstream.

    Name/version identify an immutable implementation contract, including the
    destination. Callback implementations must honor cancellation where possible
    and pass EffectCall.idempotency_key (and fencing token if supported).
    A missing query result never proves no in-flight write exists.
    """

    name: str
    version: str
    invoke: EffectFunction
    query: QueryFunction | None = None
    deduplicates: bool = False

    def __post_init__(self) -> None:
        identifier(self.name)
        identifier(self.version)
        if type(self.deduplicates) is not bool:
            raise ValueError("deduplicates must be an explicit boolean")


class SideEffectExecutor:
    def __init__(
        self, guard: LeaseGuard, execution_id: str, *, observer: Observer | None = None
    ) -> None:
        self.guard, self.store = guard, guard.store
        self.execution_id = identifier(execution_id)
        self.observer = observer
        self._lock = asyncio.Lock()

    async def _boundary(self, stage: str, identity: OperationIdentity) -> None:
        if self.observer:
            await self.observer(stage, identity)

    async def execute(
        self, logical_key: str, adapter: EffectAdapter, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Stable semantic key per execution, never an argument hash or model guess.

        Callers must namespace keys across paths/nodes and include an occurrence
        ID for distinct operations. A retry of the same operation reuses its key.
        """
        arguments = json.loads(canonical(arguments))
        async with self._lock:
            identity = await self.store.identify(self.guard.current, self.execution_id, logical_key)
            await self._boundary("before_prepare", identity)
            intent = await self.store.prepare_effect(
                identity, adapter.name, adapter.version, arguments, self.guard.current
            )
            return await self._execute(intent, adapter)

    async def recover_pending(self, adapters: list[EffectAdapter]) -> list[dict[str, Any]]:
        """Reload persisted intents; no original request payload is needed."""
        index = {(a.name, a.version): a for a in adapters}
        if len(index) != len(adapters):
            raise ValueError("Duplicate effect adapter identities")
        async with self._lock:
            intents = await self.store.intents(self.guard.scope, self.execution_id)
            # Validate every binding before sending any external request.
            if any((i.effect, i.version) not in index for i in intents):
                raise RecoveryConflict(
                    "META_EFFECT_VERSION_MISSING", "Original effect adapter is required"
                )
            results = []
            for intent in intents:
                intent = await self.store.prepare_effect(
                    intent.record.ticket.identity,
                    intent.effect,
                    intent.version,
                    intent.arguments,
                    self.guard.current,
                )
                results.append(await self._execute(intent, index[(intent.effect, intent.version)]))
            state = await self.store.execution(self.guard.scope, self.execution_id)
            if state and state["status"] == "paused":
                await self.store.set_status(self.guard.current, self.execution_id, "active")
            return results

    async def confirmed_operations(self) -> list[dict[str, Any]]:
        """Gate path transitions and derive fallback evidence from the journal."""
        async with self._lock:
            await self.guard.check()
            intents = await self.store.intents(
                self.guard.scope, self.execution_id, include_completed=True
            )
            if any(intent.record.state != EffectState.COMPLETED for intent in intents):
                await self.store.set_status(self.guard.current, self.execution_id, "paused")
                raise SideEffectUnresolved(
                    "META_EFFECT_UNKNOWN", "Unresolved effects block fallback and final output"
                )
            await self.guard.check()
            return [
                {
                    "operation_id": intent.record.ticket.identity.operation_id,
                    "effect": intent.effect,
                    "version": intent.version,
                    "arguments": intent.arguments,
                    "result": dict(intent.record.result or {}),
                }
                for intent in intents
            ]

    async def _execute(self, intent: EffectIntent, adapter: EffectAdapter) -> dict[str, Any]:
        ticket = intent.record.ticket
        if intent.record.state == EffectState.COMPLETED:
            await self.guard.check()
            return dict(intent.record.result or {})
        call = EffectCall(intent)
        try:
            await self._boundary("after_prepare", ticket.identity)
            result = None
            if not intent.record.created:
                query = adapter.query
                if query:
                    result = await self.guard.run(
                        lambda: query(call, json.loads(canonical(intent.arguments)))
                    )
                if result is None and not adapter.deduplicates:
                    raise SideEffectUnresolved(
                        "META_EFFECT_UNKNOWN", "Outcome cannot be confirmed; replay is disabled"
                    )
            if result is None:
                await self._boundary("before_call", ticket.identity)
                result = await self.guard.run(
                    lambda: adapter.invoke(call, json.loads(canonical(intent.arguments)))
                )
                await self._boundary("after_effect", ticket.identity)
            if not isinstance(result, dict):
                raise ValueError("Effect result must be a JSON object")
            result = json.loads(canonical(result))
            await self._boundary("before_complete", ticket.identity)
            record = await self.store.complete(ticket, result, self.guard.current)
        except BaseException as error:
            # PREPARED itself is already a durable ambiguity marker. If storage
            # or ownership is gone, do not fabricate a successful UNKNOWN write.
            try:
                await self.store.mark_unknown(ticket, "META_EFFECT_UNCONFIRMED", self.guard.current)
                await self.store.set_status(self.guard.current, self.execution_id, "paused")
            except (ControlFlowError, asyncio.CancelledError):
                pass
            if isinstance(error, (ControlFlowError, asyncio.CancelledError)) or not isinstance(
                error, Exception
            ):
                raise
            raise SideEffectUnresolved(
                "META_EFFECT_UNKNOWN", "Effect did not produce a durable confirmed result"
            ) from error
        await self._boundary("after_complete", ticket.identity)
        return dict(record.result or {})


_CURRENT: ContextVar[SideEffectExecutor | None] = ContextVar("meta_effect_executor", default=None)


def bind_effects(executor: SideEffectExecutor) -> Token[SideEffectExecutor | None]:
    """Bind an executor whose lease is already held by a runtime host."""
    return _CURRENT.set(executor)


def reset_effects(token: Token[SideEffectExecutor | None]) -> None:
    _CURRENT.reset(token)


def current_effects() -> SideEffectExecutor:
    result = _CURRENT.get()
    if result is None:
        raise RecoveryConflict("META_EFFECT_CONTEXT", "A managed durable execution is required")
    return result


class DurableExecution:
    """Explicit effect session; does not restore MetaBaseAgent L1/L2 state.

    Closing releases the lease but retains execution/pins/journal. The caller
    explicitly calls finish() once business computation is confirmed complete.
    """

    def __init__(
        self,
        store: RecoveryStore,
        scope: OperationScope,
        execution_id: str,
        snapshot: RecoverySnapshot,
        *,
        ttl: float = 30.0,
        observer: Observer | None = None,
    ) -> None:
        self.guard = LeaseGuard(store, scope, ttl=ttl)
        self.snapshot = RecoverySnapshot(**json.loads(snapshot.encode()))
        self.executor = SideEffectExecutor(self.guard, execution_id, observer=observer)
        self._binding: Token[SideEffectExecutor | None] | None = None

    async def __aenter__(self) -> DurableExecution:
        await self.guard.__aenter__()
        try:
            await self.guard.store.bind_execution(
                self.guard.current, self.executor.execution_id, self.snapshot
            )
        except BaseException as error:
            await self.guard.__aexit__(type(error), error, error.__traceback__)
            raise
        self._binding = _CURRENT.set(self.executor)
        return self

    async def finish(self) -> None:
        await self.guard.store.set_status(
            self.guard.current, self.executor.execution_id, "completed"
        )

    async def pause(self) -> None:
        await self.guard.store.set_status(self.guard.current, self.executor.execution_id, "paused")

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            await self.guard.__aexit__(exc_type, exc, tb)
        finally:
            if self._binding is not None:
                _CURRENT.reset(self._binding)
                self._binding = None
