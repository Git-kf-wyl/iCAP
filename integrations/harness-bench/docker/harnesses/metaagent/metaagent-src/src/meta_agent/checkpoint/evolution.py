"""Durable Skill review using the existing lease and native checkpoint store.

Native evolution edits a private working copy. Only a committed checkpoint
publishes that copy; reopening discards an interrupted, uncommitted edit.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from meta_agent.checkpoint.contracts import OperationScope
from meta_agent.checkpoint.lease import LeaseGuard
from meta_agent.checkpoint.models import RecoverySnapshot
from meta_agent.checkpoint.runtime import Recovery
from meta_agent.errors import RecoveryConflict
from meta_agent.spec import MetaAgentSpec

if TYPE_CHECKING:
    from meta_agent.evolution import SkillEvolution


def materialize_skills(spec: MetaAgentSpec, content: bytes, version: str) -> MetaAgentSpec:
    """Keep configured directory names and workspace boundaries in a saved version."""
    result = spec.model_copy(deep=True)
    namespace = hashlib.sha256(f"{spec.product_id}/{spec.agent_id}".encode()).hexdigest()[:16]
    roots: list[Path] = []
    # Keep native archive paths within ordinary Windows path lengths. The
    # recovery store still verifies the full artifact digest and all file bytes.
    version = version[:32]
    for agent in [result.deep_agent, *(result.deep_agent.subagents or [])]:
        workspace = agent.workspace or result.deep_agent.workspace
        paths = []
        for configured in agent.skills or []:
            directory = (
                Path(workspace.root_path)
                / ".meta-skills"
                / namespace
                / version
                / str(len(roots))
                / Path(configured).name
            ).resolve()
            directory.mkdir(parents=True, exist_ok=True)
            roots.append(directory)
            paths.append(str(directory))
        agent.skills = paths
    # These are trusted, checksum-verified native artifacts, like Session state.
    for index, name, value in pickle.loads(content):
        root = roots[index]
        target = (root / name).resolve()
        if not target.is_relative_to(root):
            raise RecoveryConflict("META_ARTIFACT_CORRUPT", "Invalid Skill artifact path")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != value:
                raise RecoveryConflict("META_SKILLS_CHANGED", "Materialized Skill version changed")
        else:
            # Publish complete files; an interrupted extraction can be retried.
            temporary = root.parent / f".{uuid4().hex}.tmp"
            temporary.write_bytes(value)
            os.replace(temporary, target)
    if Recovery.skills(result) != content:
        raise RecoveryConflict("META_SKILLS_CHANGED", "Materialized Skill files differ")
    return result


class EvolutionCheckpoint:
    """One leased reviewer; no shared mutable Skill files or new execution engine."""

    execution = "skill-review-v1"

    def __init__(self, recovery: Recovery, spec: MetaAgentSpec, package_digest: str) -> None:
        self.recovery, self.original = recovery, spec
        self.fingerprint = recovery.config_digest(spec, package_digest)
        self.guard = LeaseGuard(
            recovery.store,
            OperationScope(spec.product_id, spec.agent_id, "skill-review", "evolution"),
            ttl=recovery.ttl,
        )
        self.spec = spec
        self.review: dict[str, Any] = {}
        self.failed = False

    async def open(self) -> None:
        await self.guard.__aenter__()
        snapshot = RecoverySnapshot(self.fingerprint, "skill-review-v1", "review", {}, {})
        await self.recovery.store.bind_execution(self.guard.current, self.execution, snapshot)
        saved = await self.recovery.store.load_checkpoint(
            self.guard.scope, self.execution, "review"
        )
        state = pickle.loads(saved) if saved is not None else {}
        self.review = state.get("review", {})
        content = state.get("skills")
        if content is None:
            content = self.recovery.skills(self.original)
        self.spec = materialize_skills(self.original, content, f"working-{uuid4().hex}")

    async def check(self) -> None:
        if self.failed:
            raise RecoveryConflict(
                "META_EVOLUTION_REOPEN", "Reopen the runtime after an uncommitted Skill operation"
            )
        await self.guard.check()

    async def save(self, evolution: SkillEvolution) -> None:
        await self.check()
        state = {"skills": self.recovery.skills(self.spec), "review": evolution.review_state()}
        await self.recovery.store.save_checkpoint(
            self.guard.current, self.execution, "review", pickle.dumps(state, protocol=5)
        )

    async def close(self) -> None:
        await self.guard.aclose()
