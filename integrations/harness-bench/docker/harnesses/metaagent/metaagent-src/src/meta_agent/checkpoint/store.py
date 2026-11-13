"""Shared relational recovery operations; backends own transactions, locking and time."""

from __future__ import annotations

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from typing import Any, Protocol, TypeVar
from uuid import uuid4

from meta_agent.checkpoint.contracts import (
    EffectState,
    JournalRecord,
    JsonValue,
    LeaseToken,
    OperationIdentity,
    OperationScope,
    OperationTicket,
)
from meta_agent.checkpoint.models import (
    EffectIntent,
    RecoverySnapshot,
    canonical,
    duration,
    identifier,
    scope_key,
)
from meta_agent.errors import (
    LeaseBusy,
    LeaseLost,
    OperationConflict,
    RecoveryConflict,
    StorageUnavailable,
)

T = TypeVar("T")


class Cursor(Protocol):
    def fetchone(self) -> Any: ...
    def fetchall(self) -> list[Any]: ...


class Connection(Protocol):
    def execute(self, query: str, parameters: Sequence[Any] = ()) -> Cursor: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS leases (
 scope TEXT PRIMARY KEY, owner TEXT NOT NULL, fence INTEGER NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts (digest TEXT PRIMARY KEY, content BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS executions (
 scope TEXT NOT NULL, execution TEXT NOT NULL, snapshot TEXT NOT NULL, status TEXT NOT NULL,
 PRIMARY KEY(scope,execution), CHECK(status IN ('active','paused','completed')));
CREATE TABLE IF NOT EXISTS pins (
 scope TEXT NOT NULL, execution TEXT NOT NULL, digest TEXT NOT NULL REFERENCES artifacts(digest),
 PRIMARY KEY(scope,execution,digest),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution));
CREATE TABLE IF NOT EXISTS identities (
 scope TEXT NOT NULL, execution TEXT NOT NULL, logical_key TEXT NOT NULL, operation TEXT NOT NULL,
 PRIMARY KEY(scope,execution,logical_key), UNIQUE(scope,execution,operation),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution));
CREATE TABLE IF NOT EXISTS journal (
 scope TEXT NOT NULL, execution TEXT NOT NULL, operation TEXT NOT NULL, args_hash TEXT NOT NULL,
 effect TEXT NOT NULL, version TEXT NOT NULL, arguments TEXT NOT NULL, state TEXT NOT NULL,
 result TEXT, reason TEXT, fence INTEGER NOT NULL,
 PRIMARY KEY(scope,execution,operation),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution),
 CHECK(state IN ('prepared','completed','unknown')));
CREATE TABLE IF NOT EXISTS runtime_runs (
 scope TEXT NOT NULL, execution TEXT NOT NULL, data TEXT NOT NULL,
 PRIMARY KEY(scope,execution),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution));
CREATE TABLE IF NOT EXISTS runtime_requests (
 scope TEXT NOT NULL, request TEXT NOT NULL, execution TEXT NOT NULL,
 PRIMARY KEY(scope,request),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution));
CREATE TABLE IF NOT EXISTS native_checkpoints (
 scope TEXT NOT NULL, execution TEXT NOT NULL, name TEXT NOT NULL,
 content BLOB NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(scope,execution,name),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution));
CREATE TABLE IF NOT EXISTS checkpoint_manifest (
 scope TEXT NOT NULL, execution TEXT NOT NULL, name TEXT NOT NULL, digest TEXT NOT NULL,
 PRIMARY KEY(scope,execution,name),
 FOREIGN KEY(scope,execution) REFERENCES executions(scope,execution));
"""


class RecoveryStore(ABC):
    """Common recovery contract for SQLite and PostgreSQL."""

    storage_errors: tuple[type[Exception], ...] = (OSError,)
    order_column = "rowid"
    read_begin = "BEGIN"
    artifact_read_lock = ""
    artifact_write_lock = ""

    @property
    @abstractmethod
    def backend_id(self) -> str:
        """Non-secret identity for the process-wide native checkpointer."""
        ...

    @abstractmethod
    def _connection(self) -> AbstractContextManager[Connection]: ...

    @abstractmethod
    def _transaction(
        self, lease: LeaseToken | None = None, *, scope: OperationScope | None = None
    ) -> AbstractContextManager[Connection]: ...

    @abstractmethod
    def _now(self, db: Connection) -> float: ...

    async def _run(self, operation: Callable[[], T]) -> T:
        def work() -> T:
            try:
                return operation()
            except self.storage_errors as error:
                raise StorageUnavailable(
                    "META_STORAGE_IO", "Recovery transaction failed"
                ) from error

        # Cancellation must not leave an unobserved worker committing after this
        # method returns and the caller releases its lease.
        task = asyncio.create_task(asyncio.to_thread(work))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if task.done() and not task.cancelled():
                task.exception()
            raise

    def _guard(self, db: Connection, token: LeaseToken) -> None:
        row = db.execute("SELECT * FROM leases WHERE scope=?", (scope_key(token.scope),)).fetchone()
        if (
            row is None
            or row["owner"] != token.owner
            or row["fence"] != token.fencing_token
            or row["expires"] <= self._now(db)
        ):
            raise LeaseLost("META_LEASE_LOST", "Lease is stale or expired")

    async def acquire(self, scope: OperationScope, owner: str, ttl_seconds: float) -> LeaseToken:
        key, owner, ttl = scope_key(scope), identifier(owner), duration(ttl_seconds)

        def work() -> LeaseToken:
            with self._transaction(scope=scope) as db:
                now = self._now(db)
                row = db.execute("SELECT * FROM leases WHERE scope=?", (key,)).fetchone()
                if row and row["expires"] > now:
                    raise LeaseBusy("META_LEASE_BUSY", "Session is owned by another execution")
                fence = row["fence"] + 1 if row else 1
                db.execute(
                    "INSERT INTO leases VALUES (?,?,?,?) ON CONFLICT(scope) DO UPDATE SET "
                    "owner=excluded.owner,fence=excluded.fence,expires=excluded.expires",
                    (key, owner, fence, now + ttl),
                )
            return LeaseToken(scope, owner, fence, now + ttl)

        return await self._run(work)

    async def renew(self, token: LeaseToken, ttl_seconds: float) -> LeaseToken:
        ttl = duration(ttl_seconds)

        def work() -> LeaseToken:
            with self._transaction(token) as db:
                expiry = self._now(db) + ttl
                db.execute(
                    "UPDATE leases SET expires=? WHERE scope=?", (expiry, scope_key(token.scope))
                )
            return LeaseToken(token.scope, token.owner, token.fencing_token, expiry)

        return await self._run(work)

    async def release(self, token: LeaseToken) -> None:
        def work() -> None:
            with self._transaction(scope=token.scope) as db:
                self._guard(db, token)
                db.execute("UPDATE leases SET expires=0 WHERE scope=?", (scope_key(token.scope),))

        await self._run(work)

    async def check(self, token: LeaseToken) -> None:
        def work() -> None:
            with self._connection() as db:
                self._guard(db, token)

        await self._run(work)

    async def put_artifact(self, content: bytes) -> str:
        if len(content) > 8 * 1024 * 1024:
            raise ValueError("Artifact exceeds 8 MiB")
        digest = hashlib.sha256(content).hexdigest()

        def work() -> str:
            with self._transaction() as db:
                db.execute(
                    "INSERT INTO artifacts VALUES (?,?) ON CONFLICT DO NOTHING", (digest, content)
                )
            return digest

        return await self._run(work)

    async def get_artifact(self, digest: str) -> bytes:
        def work() -> bytes:
            with self._connection() as db:
                row = db.execute(
                    "SELECT content FROM artifacts WHERE digest=?", (digest,)
                ).fetchone()
            if row is None or hashlib.sha256(row[0]).hexdigest() != digest:
                raise RecoveryConflict(
                    "META_ARTIFACT_MISSING", "Pinned artifact is missing or corrupt"
                )
            return bytes(row[0])

        return await self._run(work)

    async def delete_artifact(self, digest: str) -> None:
        def work() -> None:
            with self._transaction() as db:
                db.execute(
                    "SELECT digest FROM artifacts WHERE digest=?" + self.artifact_write_lock,
                    (digest,),
                ).fetchone()
                if db.execute("SELECT 1 FROM pins WHERE digest=?", (digest,)).fetchone():
                    raise RecoveryConflict(
                        "META_VERSION_PINNED", "Execution still references this artifact"
                    )
                db.execute("DELETE FROM artifacts WHERE digest=?", (digest,))

        await self._run(work)

    async def bind_execution(
        self,
        lease: LeaseToken,
        execution: str,
        snapshot: RecoverySnapshot,
        *,
        runtime_data: dict[str, Any] | None = None,
    ) -> None:
        key, execution, encoded = scope_key(lease.scope), identifier(execution), snapshot.encode()

        def work() -> None:
            with self._transaction(lease) as db:
                row = db.execute(
                    "SELECT snapshot FROM executions WHERE scope=? AND execution=?",
                    (key, execution),
                ).fetchone()
                if (
                    row is None
                    and db.execute(
                        "SELECT 1 FROM executions WHERE scope=? AND status!='completed'", (key,)
                    ).fetchone()
                ):
                    raise RecoveryConflict(
                        "META_EXECUTION_PENDING", "Finish or recover the prior session execution"
                    )
                if row and row[0] != encoded:
                    raise RecoveryConflict(
                        "META_SNAPSHOT_CHANGED", "Recovery requires the original snapshot"
                    )
                for digest in sorted(set(json.loads(encoded)["artifacts"].values())):
                    artifact = db.execute(
                        "SELECT content FROM artifacts WHERE digest=?" + self.artifact_read_lock,
                        (digest,),
                    ).fetchone()
                    if artifact is None or hashlib.sha256(artifact[0]).hexdigest() != digest:
                        raise RecoveryConflict(
                            "META_ARTIFACT_MISSING", "Required artifact is missing or corrupt"
                        )
                db.execute(
                    "INSERT INTO executions VALUES (?,?,?,'active') ON CONFLICT DO NOTHING",
                    (key, execution, encoded),
                )
                for digest in sorted(set(json.loads(encoded)["artifacts"].values())):
                    db.execute(
                        "INSERT INTO pins VALUES (?,?,?) ON CONFLICT DO NOTHING",
                        (key, execution, digest),
                    )
                if runtime_data is not None:
                    if row is not None:
                        raise RecoveryConflict("META_RUNTIME_EXISTS", "Execution already admitted")
                    self._request(db, key, execution, runtime_data["request_id"])
                    # Carry only native conversation memory into a subsequent turn.
                    prior = db.execute(
                        "SELECT execution FROM runtime_runs WHERE scope=? "
                        f"ORDER BY {self.order_column} DESC LIMIT 1",
                        (key,),
                    ).fetchone()
                    if prior:
                        db.execute(
                            "INSERT INTO checkpoint_manifest SELECT scope,?,name,digest "
                            "FROM checkpoint_manifest WHERE scope=? AND execution=? "
                            "AND name='agent'",
                            (execution, key, prior[0]),
                        )
                        db.execute(
                            "INSERT INTO native_checkpoints SELECT scope,?,name,content,digest "
                            "FROM native_checkpoints WHERE scope=? AND execution=? "
                            "AND name='agent'",
                            (execution, key, prior[0]),
                        )
                    db.execute(
                        "INSERT INTO runtime_runs (scope,execution,data) VALUES (?,?,?)",
                        (key, execution, canonical(runtime_data)),
                    )

        await self._run(work)

    @staticmethod
    def _request(db: Connection, key: str, execution: str, request: str) -> None:
        from meta_agent.errors import RequestConflictError

        if db.execute(
            "SELECT 1 FROM runtime_requests WHERE scope=? AND request=?", (key, identifier(request))
        ).fetchone():
            raise RequestConflictError("META_REQUEST_REPLAY", "Request ID was already consumed")
        db.execute("INSERT INTO runtime_requests VALUES (?,?,?)", (key, request, execution))

    async def runtime_state(self, scope: OperationScope) -> dict[str, Any] | None:
        def work() -> dict[str, Any] | None:
            with self._connection() as db:
                row = db.execute(
                    "SELECT r.execution,r.data,e.snapshot,e.status FROM runtime_runs r "
                    "JOIN executions e USING(scope,execution) WHERE r.scope=? "
                    f"ORDER BY r.{self.order_column} DESC LIMIT 1",
                    (scope_key(scope),),
                ).fetchone()
            return (
                {
                    "execution_id": row[0],
                    "data": json.loads(row[1]),
                    "snapshot": json.loads(row[2]),
                    "status": row[3],
                }
                if row
                else None
            )

        return await self._run(work)

    async def update_runtime(
        self,
        lease: LeaseToken,
        execution: str,
        data: dict[str, Any],
        *,
        request_id: str | None = None,
        status: str | None = None,
    ) -> None:
        encoded = canonical(data)
        if status not in (None, "active", "paused", "completed"):
            raise ValueError("Invalid execution state")

        def work() -> None:
            with self._transaction(lease) as db:
                self._execution(db, lease, execution)
                key = (scope_key(lease.scope), execution)
                if not db.execute(
                    "SELECT 1 FROM runtime_runs WHERE scope=? AND execution=?", key
                ).fetchone():
                    raise RecoveryConflict("META_RUNTIME_MISSING", "No durable runtime admission")
                if request_id:
                    self._request(db, key[0], execution, request_id)
                if (
                    status == "completed"
                    and db.execute(
                        "SELECT 1 FROM journal WHERE scope=? AND execution=? "
                        "AND state!='completed'",
                        key,
                    ).fetchone()
                ):
                    raise RecoveryConflict(
                        "META_PENDING_EFFECTS", "Cannot publish with unresolved effects"
                    )
                db.execute(
                    "UPDATE runtime_runs SET data=? WHERE scope=? AND execution=?", (encoded, *key)
                )
                if status:
                    db.execute(
                        "UPDATE executions SET status=? WHERE scope=? AND execution=?",
                        (status, *key),
                    )

        await self._run(work)

    async def save_checkpoint(
        self,
        lease: LeaseToken,
        execution: str,
        name: str,
        content: bytes,
    ) -> None:
        await self.save_checkpoints(lease, execution, {name: content})

    async def save_checkpoints(
        self,
        lease: LeaseToken,
        execution: str,
        entries: dict[str, bytes],
    ) -> None:
        for name, content in entries.items():
            identifier(name)
            if not isinstance(content, bytes) or len(content) > 32 * 1024 * 1024:
                raise ValueError("Checkpoint must be bytes, at most 32 MiB")

        def work() -> None:
            with self._transaction(lease) as db:
                self._execution(db, lease, execution)
                for name, content in entries.items():
                    db.execute(
                        "INSERT INTO checkpoint_manifest VALUES (?,?,?,?) "
                        "ON CONFLICT(scope,execution,name) DO UPDATE SET digest=excluded.digest",
                        (
                            scope_key(lease.scope),
                            execution,
                            name,
                            hashlib.sha256(content).hexdigest(),
                        ),
                    )
                    db.execute(
                        "INSERT INTO native_checkpoints VALUES (?,?,?,?,?) "
                        "ON CONFLICT(scope,execution,name) DO UPDATE SET "
                        "content=excluded.content,digest=excluded.digest",
                        (
                            scope_key(lease.scope),
                            execution,
                            name,
                            content,
                            hashlib.sha256(content).hexdigest(),
                        ),
                    )

        await self._run(work)

    async def load_checkpoint(
        self, scope: OperationScope, execution: str, name: str
    ) -> bytes | None:
        def work() -> bytes | None:
            with self._connection() as db:
                db.execute(self.read_begin)
                key = (scope_key(scope), execution, name)
                expected = db.execute(
                    "SELECT digest FROM checkpoint_manifest "
                    "WHERE scope=? AND execution=? AND name=?",
                    key,
                ).fetchone()
                row = db.execute(
                    "SELECT content,digest FROM native_checkpoints "
                    "WHERE scope=? AND execution=? AND name=?",
                    key,
                ).fetchone()
            if row is None and expected is None:
                return None
            if (
                row is None
                or expected is None
                or row[1] != expected[0]
                or hashlib.sha256(row[0]).hexdigest() != row[1]
            ):
                raise RecoveryConflict("META_CHECKPOINT_CORRUPT", "Checkpoint checksum mismatch")
            return bytes(row[0])

        return await self._run(work)

    def _execution(self, db: Connection, lease: LeaseToken, execution: str) -> None:
        row = db.execute(
            "SELECT status FROM executions WHERE scope=? AND execution=?",
            (scope_key(lease.scope), execution),
        ).fetchone()
        if row is None or row[0] == "completed":
            raise RecoveryConflict(
                "META_EXECUTION_CLOSED", "Execution must be pinned and unfinished"
            )

    async def execution(self, scope: OperationScope, execution: str) -> dict[str, Any] | None:
        def work() -> dict[str, Any] | None:
            with self._connection() as db:
                row = db.execute(
                    "SELECT snapshot,status FROM executions WHERE scope=? AND execution=?",
                    (scope_key(scope), execution),
                ).fetchone()
            return {"snapshot": json.loads(row[0]), "status": row[1]} if row else None

        return await self._run(work)

    async def set_status(self, lease: LeaseToken, execution: str, status: str) -> None:
        if status not in {"active", "paused", "completed"}:
            raise ValueError("Invalid execution state")

        def work() -> None:
            with self._transaction(lease) as db:
                self._execution(db, lease, execution)
                key = (scope_key(lease.scope), execution)
                if (
                    status in {"active", "completed"}
                    and db.execute(
                        "SELECT 1 FROM journal WHERE scope=? AND execution=? "
                        "AND state!='completed'",
                        key,
                    ).fetchone()
                ):
                    raise RecoveryConflict(
                        "META_PENDING_EFFECTS", "Cannot finish with unresolved effects"
                    )
                db.execute(
                    "UPDATE executions SET status=? WHERE scope=? AND execution=?", (status, *key)
                )

        await self._run(work)

    async def retire_pins(self, lease: LeaseToken, execution: str) -> None:
        """Explicit retention decision; leaves operation identities/results permanently intact."""

        def work() -> None:
            with self._transaction(lease) as db:
                key = (scope_key(lease.scope), execution)
                row = db.execute(
                    "SELECT status FROM executions WHERE scope=? AND execution=?", key
                ).fetchone()
                if row is None or row[0] != "completed":
                    raise RecoveryConflict(
                        "META_VERSION_PINNED", "Only completed executions may retire pins"
                    )
                db.execute("DELETE FROM pins WHERE scope=? AND execution=?", key)

        await self._run(work)

    async def identify(
        self, lease: LeaseToken, execution: str, logical_key: str
    ) -> OperationIdentity:
        execution, logical_key = identifier(execution), identifier(logical_key)

        def work() -> OperationIdentity:
            with self._transaction(lease) as db:
                self._execution(db, lease, execution)
                key = (scope_key(lease.scope), execution, logical_key)
                existing = db.execute(
                    "SELECT operation FROM identities WHERE scope=? AND execution=? "
                    "AND logical_key=?",
                    key,
                ).fetchone()
                if existing is None:
                    status = db.execute(
                        "SELECT status FROM executions WHERE scope=? AND execution=?", key[:2]
                    ).fetchone()[0]
                    pending = db.execute(
                        "SELECT 1 FROM journal WHERE scope=? AND execution=? "
                        "AND state!='completed'",
                        key[:2],
                    ).fetchone()
                    if status == "paused" or pending:
                        raise RecoveryConflict(
                            "META_PENDING_EFFECTS", "Reconcile pending effects before new work"
                        )
                db.execute(
                    "INSERT INTO identities VALUES (?,?,?,?) ON CONFLICT DO NOTHING",
                    (*key, uuid4().hex),
                )
                row = db.execute(
                    "SELECT operation FROM identities WHERE scope=? AND execution=? "
                    "AND logical_key=?",
                    key,
                ).fetchone()
            return OperationIdentity(lease.scope, execution, row[0])

        return await self._run(work)

    @staticmethod
    def _key(identity: OperationIdentity) -> tuple[str, str, str]:
        return (
            scope_key(identity.scope),
            identifier(identity.execution_id),
            identifier(identity.operation_id),
        )

    @staticmethod
    def _record(identity: OperationIdentity, row: Any, created: bool = False) -> JournalRecord:
        return JournalRecord(
            OperationTicket(identity, row["args_hash"], row["fence"]),
            EffectState(row["state"]),
            json.loads(row["result"]) if row["result"] is not None else None,
            row["reason"],
            created,
        )

    async def _prepare(
        self,
        identity: OperationIdentity,
        digest: str,
        lease: LeaseToken,
        effect: str,
        version: str,
        arguments: str,
    ) -> JournalRecord:
        if identity.scope != lease.scope:
            raise LeaseLost("META_LEASE_SCOPE", "Operation is outside the leased session")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Arguments digest must be SHA256")

        def work() -> JournalRecord:
            with self._transaction(lease) as db:
                self._execution(db, lease, identity.execution_id)
                key = self._key(identity)
                row = db.execute(
                    "SELECT * FROM journal WHERE scope=? AND execution=? AND operation=?", key
                ).fetchone()
                created = row is None
                if row and (row["args_hash"], row["effect"], row["version"], row["arguments"]) != (
                    digest,
                    effect,
                    version,
                    arguments,
                ):
                    raise OperationConflict(
                        "META_OPERATION_DRIFT",
                        "Operation identity was reused with different intent",
                    )
                if created:
                    status = db.execute(
                        "SELECT status FROM executions WHERE scope=? AND execution=?", key[:2]
                    ).fetchone()[0]
                    pending = db.execute(
                        "SELECT 1 FROM journal WHERE scope=? AND execution=? "
                        "AND state!='completed'",
                        key[:2],
                    ).fetchone()
                    # Identity allocation can precede prepare by an arbitrary
                    # interval, including a crash. It never grants dispatch rights.
                    if status == "paused" or pending:
                        raise RecoveryConflict(
                            "META_PENDING_EFFECTS", "Reconcile pending effects before new work"
                        )
                    db.execute(
                        "INSERT INTO journal (scope,execution,operation,args_hash,effect,version,"
                        "arguments,state,result,reason,fence) "
                        "VALUES (?,?,?,?,?,?,?,'prepared',NULL,NULL,?)",
                        (*key, digest, effect, version, arguments, lease.fencing_token),
                    )
                else:
                    db.execute(
                        "UPDATE journal SET fence=? WHERE scope=? AND execution=? AND operation=?",
                        (lease.fencing_token, *key),
                    )
                row = db.execute(
                    "SELECT * FROM journal WHERE scope=? AND execution=? AND operation=?", key
                ).fetchone()
                return self._record(identity, row, created)

        return await self._run(work)

    async def prepare(
        self, identity: OperationIdentity, arguments_sha256: str, lease: LeaseToken
    ) -> JournalRecord:
        return await self._prepare(identity, arguments_sha256, lease, "", "", "{}")

    async def prepare_effect(
        self,
        identity: OperationIdentity,
        effect: str,
        version: str,
        arguments: dict[str, Any],
        lease: LeaseToken,
    ) -> EffectIntent:
        if not isinstance(arguments, dict):
            raise ValueError("Effect arguments must be a JSON object")
        effect, version = identifier(effect), identifier(version)
        arguments_json = canonical(arguments)
        digest = hashlib.sha256(
            canonical([effect, version, json.loads(arguments_json)]).encode()
        ).hexdigest()
        record = await self._prepare(identity, digest, lease, effect, version, arguments_json)
        return EffectIntent(record, effect, version, json.loads(arguments_json))

    async def read(self, identity: OperationIdentity) -> JournalRecord | None:
        def work() -> JournalRecord | None:
            with self._connection() as db:
                row = db.execute(
                    "SELECT * FROM journal WHERE scope=? AND execution=? AND operation=?",
                    self._key(identity),
                ).fetchone()
            return self._record(identity, row) if row else None

        return await self._run(work)

    async def intents(
        self, scope: OperationScope, execution: str, *, include_completed: bool = False
    ) -> list[EffectIntent]:
        """Pending recovery work, or the full journal for confirmed fallback evidence."""

        def work() -> list[EffectIntent]:
            with self._connection() as db:
                rows = db.execute(
                    "SELECT * FROM journal WHERE scope=? AND execution=? "
                    f"AND (? OR state!='completed') ORDER BY {self.order_column}",
                    (scope_key(scope), execution, include_completed),
                ).fetchall()
            return [
                EffectIntent(
                    self._record(OperationIdentity(scope, execution, row["operation"]), row),
                    row["effect"],
                    row["version"],
                    json.loads(row["arguments"]),
                )
                for row in rows
            ]

        return await self._run(work)

    async def pending(self, scope: OperationScope, execution_id: str) -> Sequence[JournalRecord]:
        return [intent.record for intent in await self.intents(scope, execution_id)]

    async def _update(
        self,
        ticket: OperationTicket,
        lease: LeaseToken,
        state: str,
        result: str | None,
        reason: str | None,
    ) -> JournalRecord:
        if ticket.identity.scope != lease.scope or ticket.fencing_token != lease.fencing_token:
            raise LeaseLost("META_LEASE_SCOPE", "Ticket does not belong to this lease")

        def work() -> JournalRecord:
            with self._transaction(lease) as db:
                self._execution(db, lease, ticket.identity.execution_id)
                key = self._key(ticket.identity)
                row = db.execute(
                    "SELECT * FROM journal WHERE scope=? AND execution=? AND operation=?", key
                ).fetchone()
                if row is None or row["args_hash"] != ticket.arguments_sha256:
                    raise OperationConflict(
                        "META_OPERATION_DRIFT", "Missing or changed prepared intent"
                    )
                if row["fence"] != lease.fencing_token:
                    raise LeaseLost("META_LEASE_LOST", "Ticket has not been adopted by this owner")
                if row["state"] == "completed" and (
                    state != "completed" or row["result"] != result
                ):
                    raise OperationConflict(
                        "META_RESULT_IMMUTABLE", "Completed results cannot be changed"
                    )
                db.execute(
                    "UPDATE journal SET state=?,result=?,reason=? WHERE scope=? "
                    "AND execution=? AND operation=?",
                    (state, result, reason, *key),
                )
                row = db.execute(
                    "SELECT * FROM journal WHERE scope=? AND execution=? AND operation=?", key
                ).fetchone()
                return self._record(ticket.identity, row)

        return await self._run(work)

    async def complete(
        self, ticket: OperationTicket, result: Mapping[str, JsonValue], lease: LeaseToken
    ) -> JournalRecord:
        return await self._update(ticket, lease, "completed", canonical(dict(result)), None)

    async def mark_unknown(
        self, ticket: OperationTicket, error_code: str, lease: LeaseToken
    ) -> JournalRecord:
        return await self._update(ticket, lease, "unknown", None, identifier(error_code))
