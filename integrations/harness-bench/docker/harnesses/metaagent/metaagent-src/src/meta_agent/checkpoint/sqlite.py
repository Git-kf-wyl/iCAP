"""Single-host SQLite WAL/FULL recovery; not a network-filesystem backend."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from meta_agent.checkpoint.contracts import LeaseToken, OperationScope
from meta_agent.checkpoint.models import duration
from meta_agent.checkpoint.store import _SCHEMA, Connection, RecoveryStore
from meta_agent.errors import RecoveryConflict, StorageUnavailable


class SQLiteRecoveryStore(RecoveryStore):
    storage_errors = (OSError, sqlite3.Error)

    @property
    def backend_id(self) -> str:
        return str(self.path)

    def _now(self, db: Connection) -> float:
        return self.clock()

    def __init__(
        self, path: str | Path, *, timeout: float = 5.0, clock: Callable[[], float] = time.time
    ) -> None:
        self.path = Path(path).resolve()
        self.timeout, self.clock = duration(timeout), clock
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as db:
                version = db.execute("PRAGMA user_version").fetchone()[0]
                if version not in (0, 1, 2):
                    raise RecoveryConflict("META_STORE_VERSION", "Unsupported recovery schema")
                if db.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                    raise StorageUnavailable("META_STORAGE_MODE", "WAL mode is required")
                db.executescript(_SCHEMA)
                db.execute("PRAGMA user_version=2")
        except (OSError, sqlite3.Error) as error:
            raise StorageUnavailable(
                "META_STORAGE_OPEN", "Cannot initialize recovery store"
            ) from error

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA foreign_keys=ON")
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(
        self, lease: LeaseToken | None = None, *, scope: OperationScope | None = None
    ) -> Iterator[sqlite3.Connection]:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if lease:
                    self._guard(db, lease)
                yield db
                if lease:
                    self._guard(db, lease)
                db.commit()
            except BaseException:
                db.rollback()
                raise
