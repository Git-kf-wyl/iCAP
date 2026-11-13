"""Strict JSON envelopes for durable local effects and recovery pins."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from meta_agent.checkpoint.contracts import JournalRecord, OperationScope


def identifier(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > 1024:
        raise ValueError("Identity must be a nonblank string of at most 1024 bytes")
    return value


def duration(value: float) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError("Duration must be finite and positive")
    return value


def canonical(value: Any) -> str:
    def check(item: Any) -> None:
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
        elif type(item) not in (str, int, float, bool, type(None)):
            raise ValueError("Only JSON values are supported")

    check(value)
    result = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(result.encode()) > 1024 * 1024:
        raise ValueError("Durable JSON envelope exceeds 1 MiB")
    return result


def scope_key(scope: OperationScope) -> str:
    data = asdict(scope)
    for key, value in data.items():
        if key != "member_id" or value is not None:
            identifier(value)
    return canonical(data)


@dataclass(frozen=True)
class RecoverySnapshot:
    """Host-supplied immutable identities, not a native checkpoint restoration API.

    Artifact values are SHA256 digests of bytes previously added to the store.
    Store retains all references until explicit completed-execution retirement.
    """

    config_digest: str
    graph_version: str
    child_session_id: str
    route: Mapping[str, Any]
    artifacts: Mapping[str, str]

    def encode(self) -> str:
        for value in (self.config_digest, self.graph_version, self.child_session_id):
            identifier(value)
        for name, digest in self.artifacts.items():
            identifier(name)
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Artifact identity must be a SHA256 digest")
        return canonical(asdict(self))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.encode().encode()).hexdigest()


@dataclass(frozen=True)
class EffectIntent:
    record: JournalRecord
    effect: str
    version: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class EffectCall:
    """Pass this identity to the downstream system for deduplication/query/fencing."""

    intent: EffectIntent

    @property
    def idempotency_key(self) -> str:
        identity = self.intent.record.ticket.identity
        return hashlib.sha256(canonical(asdict(identity)).encode()).hexdigest()

    @property
    def fencing_token(self) -> int:
        return self.intent.record.ticket.fencing_token
