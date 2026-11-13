"""Reviewed source packages share the existing Skill checkpoint and session pins."""

from __future__ import annotations

import json
from copy import deepcopy
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openjiuwen.agent_evolving.utils import parse_top_level_frontmatter
from openjiuwen.harness.skills.mount import split_skill_front_matter
from yaml import YAMLError

from meta_agent.checkpoint.skill_files import (
    read_skill_tree,
    read_source_skill,
    replace_skill_tree,
)
from meta_agent.errors import RecoveryConflict, SessionConflict, SessionStateError

if TYPE_CHECKING:
    from meta_agent.evolution import SkillEvolution


def _version(files: dict[str, bytes]) -> str:
    manifest = {name: sha256(value).hexdigest() for name, value in files.items()}
    return sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


class SourcePublication:
    """Host publication of an existing parent Skill; new sessions adopt the release."""

    def __init__(self, evolution: SkillEvolution) -> None:
        self.evolution = evolution
        self._pending: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, dict[str, dict[str, bytes]]] = {}

    def state(self) -> dict[str, Any]:
        return {"pending": self._pending, "versions": self._versions}

    def restore_state(self, state: dict[str, Any]) -> None:
        self._pending = state.get("pending", {})
        self._versions = state.get("versions", {})

    def pending(self) -> list[dict[str, Any]]:
        return [deepcopy(item["review"]) for item in self._pending.values()]

    def files(self, request_id: str) -> dict[str, bytes]:
        """Exact staged bytes for host review, including supporting assets."""
        return dict(self._proposal(request_id)["files"])

    def versions(self, skill_name: str) -> list[str]:
        """Full-tree rollback versions, separate from native experience archives."""
        self.evolution._skill(skill_name)
        return list(self._versions.get(skill_name, {}))

    def _proposal(self, request_id: str) -> dict[str, Any]:
        if request_id not in self._pending:
            raise SessionStateError("META_SOURCE_UNKNOWN", "No pending source with this ID")
        return self._pending[request_id]

    def _ready(self, skill_name: str, *, request_id: str | None = None) -> Path:
        evolution = self.evolution
        if evolution.checkpoint is None:
            raise SessionStateError(
                "META_SOURCE_RECOVERY_REQUIRED", "Source publication requires LocalRecovery"
            )
        evolution._skill(skill_name)
        if (
            any(p["skill_name"] == skill_name for p in evolution.pending())
            or any(p["recipe"]["skill_name"] == skill_name for p in evolution.workflows.pending())
            or any(
                key != request_id and p["review"]["skill_name"] == skill_name
                for key, p in self._pending.items()
            )
        ):
            raise SessionConflict("META_PROPOSAL_PENDING", "Resolve pending proposals first")
        return evolution._skills[skill_name]

    async def stage(self, skill_name: str, directory: str | Path) -> dict[str, Any]:
        async with self.evolution._review_operation():
            root = self._ready(skill_name)
            current = read_skill_tree(root)
            try:
                files = await read_source_skill(Path(directory))
                text = files["SKILL.md"].decode("utf-8")
                parsed = split_skill_front_matter(text)
                metadata = parsed[0] if parsed is not None else None
                if (
                    not isinstance(metadata, dict)
                    or metadata.get("name") != skill_name
                    or not isinstance(metadata.get("description"), str)
                    or not metadata["description"].strip()
                ):
                    raise ValueError("Invalid Skill metadata")
            except (RecoveryConflict, OSError, ValueError, YAMLError) as exc:
                raise SessionStateError("META_SKILL_SOURCE", "Invalid local source Skill") from exc
            # Native Team evolution uses the lightweight parser for rail selection.
            candidate = parse_top_level_frontmatter(text)
            previous = parse_top_level_frontmatter(current["SKILL.md"].decode("utf-8"))
            if candidate.get("kind", "skill") != previous.get("kind", "skill"):
                raise SessionStateError(
                    "META_SKILL_SOURCE", "Source publication must preserve the Skill name and kind"
                )
            manifest = []
            for name in sorted(current.keys() | files.keys()):
                old, new = current.get(name), files.get(name)
                if old == new:
                    continue
                manifest.append(
                    {
                        "path": name,
                        "change": "removed"
                        if new is None
                        else "added"
                        if old is None
                        else "changed",
                        "size": len(new) if new is not None else 0,
                        "sha256": sha256(new).hexdigest() if new is not None else None,
                    }
                )
            request_id = uuid4().hex
            review: dict[str, Any] = {
                "request_id": request_id,
                "status": "staged",
                "skill_name": skill_name,
                "version": _version(files),
                "base_version": _version(current),
                "files": manifest,
                "skill_diff": "".join(
                    unified_diff(
                        current["SKILL.md"].decode("utf-8").splitlines(keepends=True),
                        files["SKILL.md"].decode("utf-8").splitlines(keepends=True),
                        fromfile="current/SKILL.md",
                        tofile="candidate/SKILL.md",
                    )
                ),
                "resets_experience": True,
            }
            self._pending[request_id] = {"review": review, "files": files}
            self._emit("staged", skill_name, review["version"], request_id)
            return deepcopy(review)

    async def approve(self, request_id: str) -> dict[str, Any]:
        async with self.evolution._review_operation():
            proposal = self._proposal(request_id)
            review = proposal["review"]
            name = review["skill_name"]
            root = self._ready(name, request_id=request_id)
            current = read_skill_tree(root)
            if _version(current) != review["base_version"]:
                raise SessionStateError(
                    "META_SOURCE_STALE", "The Skill changed; reject this source and stage it again"
                )
            self._replace(name, root, proposal["files"], current)
            self.evolution._approved_skills[name] = self.evolution._skill_digest(name)
            del self._pending[request_id]
            self._emit("approved", name, review["version"], request_id)
            return {
                "status": "activated",
                "version": review["version"],
                "rollback_version": review["base_version"],
            }

    async def reject(self, request_id: str) -> None:
        async with self.evolution._review_operation():
            review = self._proposal(request_id)["review"]
            del self._pending[request_id]
            self._emit("rejected", review["skill_name"], review["version"], request_id)

    async def rollback(self, skill_name: str, version: str) -> bool:
        async with self.evolution._review_operation():
            root = self._ready(skill_name)
            files = self._versions.get(skill_name, {}).get(version)
            if files is None:
                return False
            self._replace(skill_name, root, files, read_skill_tree(root))
            self.evolution._approved_skills.pop(skill_name, None)
            self._emit("rollback", skill_name, version)
            return True

    def _replace(
        self, name: str, root: Path, files: dict[str, bytes], current: dict[str, bytes]
    ) -> None:
        checkpoint = self.evolution.checkpoint
        assert checkpoint is not None
        self._versions.setdefault(name, {})[_version(current)] = current
        replace_skill_tree(root, files, Path(checkpoint.spec.deep_agent.workspace.root_path))

    def _emit(self, action: str, name: str, version: str, request_id: str | None = None) -> None:
        self.evolution._emit(
            f"evolution.source_{action}",
            self.evolution._host_identity,
            skill_name=name,
            skill_version=version,
            proposal_id=request_id,
            status=action,
        )
