"""M1 local-disk recovery experiment; not the production M4 executor.

The worker's journal/leases and the downstream ledger use separate SQLite files
with WAL, synchronous=FULL, and explicit transactions. A parent process can kill
the worker at an acknowledged commit boundary. Only the downstream fixture has
an idempotency/query contract; it does not participate in the journal transaction.

Scope: one machine and SQLite's local filesystem guarantees. This does not test
power loss, distributed storage, kernel L1/L2 restoration, or cancellation of
real network calls. The --now switch is an explicit deterministic lease clock.
Restart receives original operation IDs and arguments through the CLI; the
journal stores identities and an argument hash, not the original request payload.
Loading/enumerating operations and reconstructing L1/L2 state remain M4 work.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LeaseBusy(RuntimeError):
    pass


class LeaseLost(RuntimeError):
    pass


class OperationConflict(ValueError):
    pass


@dataclass(frozen=True)
class Lease:
    scope: str
    owner: str
    epoch: int
    expires_at: float


@dataclass(frozen=True)
class Operation:
    scope: str
    execution_id: str
    operation_id: str
    account_id: str
    amount_cents: int

    def __post_init__(self) -> None:
        if not all((self.scope, self.execution_id, self.operation_id, self.account_id)):
            raise ValueError("Operation identities must be non-empty")
        if type(self.amount_cents) is not int or self.amount_cents <= 0:
            raise ValueError("amount_cents must be a positive integer")

    @property
    def key(self) -> tuple[str, str, str]:
        return self.scope, self.execution_id, self.operation_id

    @property
    def args_hash(self) -> str:
        payload = json.dumps(
            {"tool": "refund", "account_id": self.account_id, "amount_cents": self.amount_cents},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@contextmanager
def database(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=5000")
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    with database(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


class Journal:
    """Lease checks and journal writes share a SQLite write transaction."""

    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.clock = clock
        with database(path) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS leases (
                    scope TEXT PRIMARY KEY, owner TEXT NOT NULL,
                    epoch INTEGER NOT NULL, expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS journal (
                    scope TEXT NOT NULL, execution_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                    args_hash TEXT NOT NULL, state TEXT NOT NULL,
                    result TEXT, reason TEXT, last_epoch INTEGER NOT NULL,
                    PRIMARY KEY (scope, execution_id, operation_id),
                    CHECK (state IN ('prepared', 'completed', 'unknown'))
                );
            """)

    def acquire(self, scope: str, owner: str, ttl: float) -> Lease:
        if ttl <= 0 or not scope or not owner:
            raise ValueError("Lease requires identity and positive TTL")
        with transaction(self.path) as connection:
            now = self.clock()
            row = connection.execute("SELECT * FROM leases WHERE scope=?", (scope,)).fetchone()
            if row is not None and row["expires_at"] > now:
                raise LeaseBusy(f"Scope {scope} is held by {row['owner']}")
            lease = Lease(scope, owner, 1 if row is None else row["epoch"] + 1, now + ttl)
            connection.execute(
                "INSERT INTO leases VALUES (?, ?, ?, ?) ON CONFLICT(scope) DO UPDATE SET "
                "owner=excluded.owner, epoch=excluded.epoch, expires_at=excluded.expires_at",
                (scope, owner, lease.epoch, lease.expires_at),
            )
        return lease

    def _guard(self, connection: sqlite3.Connection, lease: Lease) -> None:
        row = connection.execute("SELECT * FROM leases WHERE scope=?", (lease.scope,)).fetchone()
        if (
            row is None
            or row["owner"] != lease.owner
            or row["epoch"] != lease.epoch
            or row["expires_at"] <= self.clock()
        ):
            raise LeaseLost(f"Stale or expired fencing token {lease.epoch} for {lease.scope}")

    def check(self, lease: Lease) -> None:
        with transaction(self.path) as connection:
            self._guard(connection, lease)

    def renew(self, lease: Lease, ttl: float) -> Lease:
        if ttl <= 0:
            raise ValueError("TTL must be positive")
        with transaction(self.path) as connection:
            self._guard(connection, lease)
            renewed = Lease(lease.scope, lease.owner, lease.epoch, self.clock() + ttl)
            connection.execute(
                "UPDATE leases SET expires_at=? WHERE scope=?",
                (renewed.expires_at, lease.scope),
            )
        return renewed

    def release(self, lease: Lease) -> None:
        with transaction(self.path) as connection:
            self._guard(connection, lease)
            # Keep the epoch history. Deletion would allow a later token to repeat.
            connection.execute("UPDATE leases SET expires_at=0 WHERE scope=?", (lease.scope,))

    def read(self, operation: Operation) -> dict[str, Any] | None:
        with database(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM journal WHERE scope=? AND execution_id=? AND operation_id=?",
                operation.key,
            ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["result"] = json.loads(value["result"]) if value["result"] else None
        return value

    def prepare(self, lease: Lease, operation: Operation) -> bool:
        """Return whether a newly committed operation may be dispatched."""
        if lease.scope != operation.scope:
            raise LeaseLost("Lease scope does not match operation")
        with transaction(self.path) as connection:
            self._guard(connection, lease)
            row = connection.execute(
                "SELECT args_hash FROM journal WHERE scope=? AND execution_id=? AND operation_id=?",
                operation.key,
            ).fetchone()
            if row is not None:
                if row["args_hash"] != operation.args_hash:
                    raise OperationConflict("Operation ID reused with different arguments")
                return False
            connection.execute(
                "INSERT INTO journal VALUES (?, ?, ?, ?, 'prepared', NULL, NULL, ?)",
                (*operation.key, operation.args_hash, lease.epoch),
            )
        return True

    def _update(
        self,
        lease: Lease,
        operation: Operation,
        state: str,
        result: dict[str, Any] | None,
        reason: str | None,
    ) -> None:
        if lease.scope != operation.scope:
            raise LeaseLost("Lease scope does not match operation")
        with transaction(self.path) as connection:
            self._guard(connection, lease)
            row = connection.execute(
                "SELECT * FROM journal WHERE scope=? AND execution_id=? AND operation_id=?",
                operation.key,
            ).fetchone()
            if row is None:
                raise ValueError("Operation must be prepared before result commit")
            if row["args_hash"] != operation.args_hash:
                raise OperationConflict("Operation arguments changed")
            serialized = json.dumps(result, sort_keys=True) if result is not None else None
            if row["state"] == "completed" and (
                state != "completed" or row["result"] != serialized
            ):
                raise OperationConflict("Completed result cannot be changed")
            connection.execute(
                "UPDATE journal SET state=?, result=?, reason=?, last_epoch=? "
                "WHERE scope=? AND execution_id=? AND operation_id=?",
                (state, serialized, reason, lease.epoch, *operation.key),
            )

    def complete(self, lease: Lease, operation: Operation, result: dict[str, Any]) -> None:
        self._update(lease, operation, "completed", result, None)

    def unknown(self, lease: Lease, operation: Operation, reason: str) -> None:
        self._update(lease, operation, "unknown", None, reason)


@dataclass(frozen=True)
class Contract:
    query: bool = True
    deduplicate: bool = True


class DownstreamLedger:
    """Independent durable fixture; intentionally does not enforce our lease."""

    def __init__(self, path: Path, contract: Contract = Contract()) -> None:
        self.path = path
        self.contract = contract
        with database(path) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS effects (
                    effect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL, execution_id TEXT NOT NULL, operation_id TEXT NOT NULL,
                    args_hash TEXT NOT NULL, result TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL, execution_id TEXT NOT NULL, operation_id TEXT NOT NULL
                );
            """)

    def lookup(self, operation: Operation) -> dict[str, Any] | None:
        if not self.contract.query:
            raise RuntimeError("Downstream result query unavailable")
        with database(self.path) as connection:
            row = connection.execute(
                "SELECT args_hash, result FROM effects "
                "WHERE scope=? AND execution_id=? AND operation_id=? ORDER BY effect_id LIMIT 1",
                operation.key,
            ).fetchone()
        if row is not None and row["args_hash"] != operation.args_hash:
            raise OperationConflict("Downstream operation arguments changed")
        return json.loads(row["result"]) if row is not None else None

    def apply(self, operation: Operation) -> dict[str, Any]:
        with transaction(self.path) as connection:
            connection.execute(
                "INSERT INTO attempts (scope, execution_id, operation_id) VALUES (?, ?, ?)",
                operation.key,
            )
            existing = connection.execute(
                "SELECT args_hash, result FROM effects "
                "WHERE scope=? AND execution_id=? AND operation_id=? ORDER BY effect_id LIMIT 1",
                operation.key,
            ).fetchone()
            if existing is not None and existing["args_hash"] != operation.args_hash:
                raise OperationConflict("Downstream operation arguments changed")
            if existing is not None and self.contract.deduplicate:
                return json.loads(existing["result"])
            cursor = connection.execute(
                "INSERT INTO effects (scope, execution_id, operation_id, args_hash, result) "
                "VALUES (?, ?, ?, ?, '{}')",
                (*operation.key, operation.args_hash),
            )
            result = {
                "effect_id": cursor.lastrowid,
                "operation_id": operation.operation_id,
                "account_id": operation.account_id,
                "credited_cents": operation.amount_cents,
            }
            connection.execute(
                "UPDATE effects SET result=? WHERE effect_id=?",
                (json.dumps(result, sort_keys=True), cursor.lastrowid),
            )
        return result

    def counts(self) -> tuple[int, int]:
        with database(self.path) as connection:
            effects = connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
            attempts = connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        return effects, attempts


def recover(
    journal: Journal, ledger: DownstreamLedger, lease: Lease, operation: Operation
) -> dict[str, Any]:
    if journal.read(operation) is None:
        raise ValueError("Recovery requires a previously prepared operation")
    journal.prepare(lease, operation)  # Validate fencing and immutable arguments.
    record = journal.read(operation)
    if record["state"] == "completed":
        return {"status": "completed", "source": "journal", "result": record["result"]}
    result = ledger.lookup(operation) if ledger.contract.query else None
    if result is not None:
        journal.complete(lease, operation, result)
        return {"status": "completed", "source": "query", "result": result}
    if ledger.contract.deduplicate:
        journal.check(lease)
        result = ledger.apply(operation)  # Reuse the exact persisted operation identity.
        journal.complete(lease, operation, result)
        return {"status": "completed", "source": "deduplication", "result": result}
    # Even a query returning no record may be racing with an in-flight write.
    reason = "No confirmed outcome and no downstream deduplication contract"
    journal.unknown(lease, operation, reason)
    return {"status": "paused", "reason": reason}


def execute(
    journal: Journal,
    ledger: DownstreamLedger,
    lease: Lease,
    operation: Operation,
    boundary: Callable[[str], None] = lambda _: None,
) -> dict[str, Any]:
    if not journal.prepare(lease, operation):
        return recover(journal, ledger, lease, operation)
    boundary("after_prepare")
    journal.check(lease)
    result = ledger.apply(operation)
    boundary("after_effect")
    journal.complete(lease, operation, result)
    boundary("after_complete")
    return {"status": "completed", "source": "execution", "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("worker", "recover"))
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--downstream", type=Path, required=True)
    parser.add_argument("--scope", default="m1-session")
    parser.add_argument("--execution-id", default="request-1")
    parser.add_argument("--operation-id", default="refund-1")
    parser.add_argument("--account-id", default="customer")
    parser.add_argument("--amount-cents", type=int, default=200)
    parser.add_argument("--owner", default=str(uuid.uuid4()))
    parser.add_argument("--ttl", type=float, default=10)
    parser.add_argument("--now", type=float, help="Test-only deterministic lease timestamp")
    parser.add_argument("--query", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--deduplicate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--stop-at", choices=("after_prepare", "after_effect", "after_complete"))
    args = parser.parse_args()
    journal = Journal(args.journal, time.time if args.now is None else lambda: args.now)
    ledger = DownstreamLedger(args.downstream, Contract(args.query, args.deduplicate))
    operation = Operation(
        args.scope, args.execution_id, args.operation_id, args.account_id, args.amount_cents
    )
    lease = journal.acquire(args.scope, args.owner, args.ttl)

    def boundary(stage: str) -> None:
        if stage == args.stop_at:
            print(
                json.dumps(
                    {
                        "event": "boundary",
                        "stage": stage,
                        "epoch": lease.epoch,
                        "operation_id": operation.operation_id,
                        "expires_at": lease.expires_at,
                    }
                ),
                flush=True,
            )
            sys.stdin.read(1)  # The parent holds this pipe open and kills the process.
            raise RuntimeError("Worker must be terminated at the selected boundary")

    if args.mode == "worker":
        result = execute(journal, ledger, lease, operation, boundary)
    else:
        result = recover(journal, ledger, lease, operation)
    journal.release(lease)
    print(json.dumps({**result, "epoch": lease.epoch}), flush=True)
    return 3 if result["status"] == "paused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
