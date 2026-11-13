"""Local Skill trees shared by immutable snapshots and source publication."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

from openjiuwen.agent_evolving.checkpointing.evolution_store import EvolutionStore
from openjiuwen.agent_evolving.checkpointing.skill_package import list_packable_files

from meta_agent.errors import RecoveryConflict


def _linked(path: Path) -> bool:
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def read_skill_tree(directory: Path) -> dict[str, bytes]:
    """Capture local files with the recovery snapshot's unlinked-tree invariant."""
    root = Path(directory)
    if not root.is_dir() or _linked(root):
        raise RecoveryConflict("META_SKILL_SNAPSHOT", "Recovery needs local unlinked skills")
    files = {}
    for path in sorted(root.rglob("*")):
        if _linked(path):
            raise RecoveryConflict("META_SKILL_SNAPSHOT", "Linked skill files cannot be pinned")
        if path.is_file() and "__pycache__" not in path.parts:
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


async def read_source_skill(directory: Path) -> dict[str, bytes]:
    """Capture a native shareable source without local evolution projections."""
    captured = read_skill_tree(directory)
    root = Path(directory).resolve()
    files = {
        path.relative_to(root).as_posix(): captured[path.relative_to(root).as_posix()]
        for path in list_packable_files(root)
        if path.relative_to(root).as_posix() in captured
    }
    if "SKILL.md" not in files:
        raise RecoveryConflict("META_SKILL_SOURCE", "Source Skill requires SKILL.md")
    pristine = await EvolutionStore(str(root.parent)).read_pristine_skill_content(root.name)
    if not pristine:
        raise RecoveryConflict("META_SKILL_SOURCE", "Could not read source Skill")
    files["SKILL.md"] = pristine.encode("utf-8")
    return files


def replace_skill_tree(directory: Path, files: dict[str, bytes], workspace: Path) -> None:
    """Replace a leased review working tree; the checkpoint commit publishes it."""
    read_skill_tree(directory)
    root = Path(directory).resolve()
    workspace_root = Path(workspace).resolve()
    private = (workspace_root / ".meta-skills").resolve()
    if not private.is_relative_to(workspace_root) or not root.is_relative_to(private):
        raise RecoveryConflict("META_SKILL_SOURCE", "Skill target is outside the private workspace")
    relative = root.relative_to(private)
    if len(relative.parts) < 4 or not relative.parts[1].startswith("working-"):
        raise RecoveryConflict("META_SKILL_SOURCE", "Source updates require a review working tree")
    targets = {}
    for name, content in files.items():
        target = (root / name).resolve()
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or target == root
            or not target.is_relative_to(root)
        ):
            raise RecoveryConflict("META_ARTIFACT_CORRUPT", "Invalid Skill artifact path")
        targets[target] = content
    shutil.rmtree(root)
    root.mkdir(parents=True)
    for target, content in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
