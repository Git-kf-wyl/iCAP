"""Fenced team state alongside the existing per-member LocalRecovery records."""

from __future__ import annotations

import hashlib
import json
import pickle
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any
from uuid import uuid4

from meta_agent.checkpoint import LeaseGuard, LocalRecovery, OperationScope, RecoverySnapshot
from meta_agent.errors import RecoveryConflict


@contextmanager
def native_home(path: Path | None) -> Iterator[None]:
    """Keep native Team files inside this worker's state directory."""
    from openjiuwen.agent_teams.paths import reset_task_openjiuwen_home, set_task_openjiuwen_home

    token = set_task_openjiuwen_home(path) if path is not None else None
    try:
        yield
    finally:
        if token is not None:
            reset_task_openjiuwen_home(token)


class TeamRecovery:
    def __init__(self, recovery: LocalRecovery, name: str) -> None:
        self.recovery = recovery
        self.guard = LeaseGuard(
            recovery.store, OperationScope("meta-team", name, "owner"), ttl=recovery.ttl
        )
        self.manifest: dict[str, Any] = {}

    async def open(self, config: dict[str, Any]) -> None:
        await self.guard.__aenter__()
        try:
            digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
            await self.recovery.store.bind_execution(
                self.guard.current,
                "team",
                RecoverySnapshot(digest, "meta-team-1", "team", {}, {}),
            )
            saved = await self.load("manifest")
            self.manifest = saved or {"epoch": uuid4().hex, "session_id": None, "status": "ready"}
            if self.manifest["status"] == "running":
                raise RecoveryConflict(
                    "META_TEAM_UNCLEAN", "Team must be suspended before reopening"
                )
            await self.save("manifest", self.manifest)
        except BaseException:
            await self.guard.aclose()
            raise

    async def load(self, name: str) -> Any:
        await self.guard.check()
        value = await self.recovery.store.load_checkpoint(self.guard.scope, "team", name)
        return pickle.loads(value) if value is not None else None

    async def save(self, name: str, value: Any) -> None:
        await self.recovery.store.save_checkpoint(
            self.guard.current, "team", name, pickle.dumps(value, protocol=5)
        )

    async def status(self, value: str, session_id: str | None) -> None:
        self.manifest.update(status=value, session_id=session_id)
        await self.save("manifest", self.manifest)

    async def save_files(self, root: Path) -> None:
        # Native PostgreSQL still spills message/task bodies to session files.
        # Capture after coordination drains, before publishing the handoff.
        files = {}
        for path in root.rglob("*"):
            if path.is_symlink():
                raise RecoveryConflict("META_TEAM_FILES", "Linked Team files cannot be saved")
            if path.is_file():
                files[path.relative_to(root).as_posix()] = path.read_bytes()
        await self.save("native-files", files)

    async def restore_files(self, root: Path) -> None:
        files = await self.load("native-files")
        for name, content in (files or {}).items():
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()):
                raise RecoveryConflict("META_TEAM_FILES", "Invalid saved Team file path")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    @staticmethod
    def key(session: Any, *, team: bool) -> str:
        entity = session.team_id() if team else session.agent_id()
        digest = hashlib.sha256(json.dumps([session.session_id(), entity]).encode()).hexdigest()
        return ("team-" if team else "member-") + digest

    async def restore(self, session: Any, inputs: Any, *, team: bool) -> None:
        from openjiuwen.core.common.constants.constant import INTERACTIVE_INPUT

        saved = await self.load(self.key(session, team=team))
        state = session.state()
        if saved is not None:
            (state.global_state if team else state).set_state(saved)
        if inputs is not None:
            if team:
                state.update_global({INTERACTIVE_INPUT: [inputs]})
            else:
                state.update({INTERACTIVE_INPUT: [inputs]})

    async def persist(self, session: Any, *, team: bool) -> None:
        state = session.state()
        value = state.get_global(None) if team else state.get_state(copied=True)
        await self.recovery.store.save_checkpoints(
            self.guard.current,
            "team",
            {
                self.key(session, team=team): pickle.dumps(value, protocol=5),
                "session-" + hashlib.sha256(session.session_id().encode()).hexdigest(): b"1",
            },
        )

    async def exists(self, session_id: str) -> bool:
        await self.guard.check()
        return (
            await self.recovery.store.load_checkpoint(
                self.guard.scope,
                "team",
                "session-" + hashlib.sha256(session_id.encode()).hexdigest(),
            )
            is not None
        )


TEAM_RECOVERY: ContextVar[TeamRecovery | None] = ContextVar("meta_team_recovery", default=None)
