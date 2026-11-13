"""Storage and effect identities; local implementation guarantees are documented separately."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias

JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True)
class OperationScope:
    product_id: str
    agent_id: str
    session_id: str
    member_id: str | None = None


@dataclass(frozen=True)
class OperationIdentity:
    scope: OperationScope
    execution_id: str
    operation_id: str


@dataclass(frozen=True)
class LeaseToken:
    scope: OperationScope
    owner: str
    fencing_token: int
    expires_at: float


@dataclass(frozen=True)
class OperationTicket:
    identity: OperationIdentity
    arguments_sha256: str
    fencing_token: int


class EffectState(StrEnum):
    PREPARED = "prepared"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class JournalRecord:
    ticket: OperationTicket
    state: EffectState
    result: Mapping[str, JsonValue] | None = None
    error_code: str | None = None
    created: bool = False


class OperationJournal(Protocol):
    """Implementations must atomically guard writes and acknowledge durable commit.

    Operation identity is persisted before dispatch. Retry reuses it; identical
    arguments under a different identity represent a new operation. A hash only
    detects argument drift and is never the deduplication key. Unknown outcomes
    require reconciliation or pause, never unconditional replay.
    """

    async def prepare(
        self, identity: OperationIdentity, arguments_sha256: str, lease: LeaseToken
    ) -> JournalRecord:
        """Insert/read with atomic fencing validation; reject same-ID argument drift."""
        ...

    async def read(self, identity: OperationIdentity) -> JournalRecord | None: ...

    async def complete(
        self, ticket: OperationTicket, result: Mapping[str, JsonValue], lease: LeaseToken
    ) -> JournalRecord:
        """CAS the result under the current lease, returning only after durable commit."""
        ...

    async def mark_unknown(
        self, ticket: OperationTicket, error_code: str, lease: LeaseToken
    ) -> JournalRecord:
        """Persist ambiguity under fencing; do not convert it into a safe retry."""
        ...

    async def pending(self, scope: OperationScope, execution_id: str) -> Sequence[JournalRecord]:
        """Enumerate prepared/unknown operations for explicit reconciliation."""
        ...


class LeaseStore(Protocol):
    """Multi-instance stores require atomic owner/expiry/monotonic-token semantics.

    Atomic fencing validation belongs inside each journal/checkpoint write, not
    only in a separate check-before-call. Renewal failure must stop dispatch;
    an in-flight external write still needs its downstream outcome contract.
    """

    async def acquire(self, scope: OperationScope, owner: str, ttl_seconds: float) -> LeaseToken:
        """Reject an active owner; allocate a strictly greater fencing token on acquisition."""
        ...

    async def renew(self, token: LeaseToken, ttl_seconds: float) -> LeaseToken:
        """Renew only the unexpired matching owner/token; otherwise signal lease loss."""
        ...

    async def release(self, token: LeaseToken) -> None:
        """Release only the matching owner/token without resetting fencing history."""
        ...
