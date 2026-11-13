"""Shared PostgreSQL recovery with server-time leases and transactional fencing."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from meta_agent.checkpoint.contracts import LeaseToken, OperationScope
from meta_agent.checkpoint.models import duration, scope_key
from meta_agent.checkpoint.store import _SCHEMA, Connection, RecoveryStore
from meta_agent.errors import RecoveryConflict, StorageUnavailable


def _rows(cursor: Any) -> Any:
    names = [column.name for column in cursor.description] if cursor.description else []

    def row(values: Sequence[Any]) -> dict[Any, Any]:
        return dict(enumerate(values)) | dict(zip(names, values, strict=True))

    return row


class _Connection:
    def __init__(self, native: Any) -> None:
        self.native = native

    def execute(self, query: str, parameters: Sequence[Any] = ()) -> Any:
        # Only the fixed statements in RecoveryStore use this DB-API adapter.
        return self.native.execute(query.replace("?", "%s"), parameters)


class PostgresRecoveryStore(RecoveryStore):
    """One database/schema contains leases, L1/L2, journal, artifacts and pins.

    Connect to the writable primary. Durability assumes fsync and normal logged
    tables; synchronous_commit is enabled on every connection. This does not
    promise database HA or restore native Team DB/workspace files.
    """

    order_column = "sequence"
    read_begin = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY"
    artifact_read_lock = " FOR KEY SHARE"
    artifact_write_lock = " FOR UPDATE"

    def __init__(self, dsn: str, *, schema: str = "meta_recovery", timeout: float = 5.0) -> None:
        import psycopg

        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("Recovery schema must be a lowercase SQL identifier")
        self._driver = psycopg
        self._dsn, self.schema, self.timeout = dsn, schema, duration(timeout)
        self.storage_errors = (OSError, psycopg.Error)
        self._backend_id = "postgres:" + hashlib.sha256((dsn + "\n" + schema).encode()).hexdigest()
        ddl = _SCHEMA.replace("BLOB", "BYTEA").replace("REAL", "DOUBLE PRECISION")
        ddl = ddl.replace("fence INTEGER", "fence BIGINT")
        for table in ("runtime_runs", "journal"):
            ddl = ddl.replace(
                f"CREATE TABLE IF NOT EXISTS {table} (",
                f"CREATE TABLE IF NOT EXISTS {table} ("
                "sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,",
            )
        try:
            with self._connection() as db, db.native.transaction():
                # Serialize initial schema creation only, not ordinary sessions.
                db.execute("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", (schema,))
                db.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
                version = db.execute("SELECT version FROM schema_version").fetchone()
                if version is not None and version[0] != 1:
                    raise RecoveryConflict("META_STORE_VERSION", "Unsupported recovery schema")
                for statement in ddl.split(";"):
                    if statement.strip():
                        db.execute(statement)
                if version is None:
                    db.execute("INSERT INTO schema_version VALUES (1)")
        except self.storage_errors as error:
            raise StorageUnavailable(
                "META_STORAGE_OPEN", "Cannot initialize PostgreSQL recovery store"
            ) from error

    @property
    def backend_id(self) -> str:
        return self._backend_id

    def sqlalchemy_url(self) -> str:
        """Connect native Team/A2A's asyncpg engines to the recovery schema.

        Nest the DSN so asyncpg treats search_path as a server setting.
        Shared workers require a PostgreSQL URI, not libpq keyword syntax.
        """
        from sqlalchemy.engine import URL

        uri = urlsplit(self._dsn)
        if uri.scheme not in {"postgres", "postgresql"}:
            raise ValueError("Shared Team/A2A storage requires a PostgreSQL URI")
        settings = dict(parse_qsl(uri.query))
        settings.update(search_path=self.schema, synchronous_commit="on")
        dsn = urlunsplit(uri._replace(query=urlencode(settings)))
        return URL.create("postgresql+asyncpg", query={"dsn": dsn}).render_as_string(
            hide_password=False
        )

    def _now(self, db: Connection) -> float:
        return float(db.execute("SELECT EXTRACT(EPOCH FROM clock_timestamp())").fetchone()[0])

    @contextmanager
    def _connection(self) -> Iterator[_Connection]:
        with self._driver.connect(
            self._dsn,
            autocommit=True,
            connect_timeout=math.ceil(self.timeout),
            row_factory=_rows,
        ) as native:
            db = _Connection(native)
            db.execute("SELECT set_config('search_path',?,false)", (self.schema,))
            db.execute("SELECT set_config('statement_timeout',?,false)", (f"{self.timeout}s",))
            db.execute("SET synchronous_commit=on")
            if db.execute("SHOW fsync").fetchone()[0] != "on":
                raise StorageUnavailable("META_STORAGE_MODE", "PostgreSQL fsync must be enabled")
            yield db

    @contextmanager
    def _transaction(
        self, lease: LeaseToken | None = None, *, scope: OperationScope | None = None
    ) -> Iterator[_Connection]:
        with self._connection() as db, db.native.transaction():
            target = lease.scope if lease is not None else scope
            if target is not None:
                key = scope_key(target)
                db.execute("INSERT INTO leases VALUES (?,'',0,0) ON CONFLICT DO NOTHING", (key,))
                db.execute("SELECT scope FROM leases WHERE scope=? FOR UPDATE", (key,)).fetchone()
            if lease is not None:
                self._guard(db, lease)
            yield db
            if lease is not None:
                self._guard(db, lease)
