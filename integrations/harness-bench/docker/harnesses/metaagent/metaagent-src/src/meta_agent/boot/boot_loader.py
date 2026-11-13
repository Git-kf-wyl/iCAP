"""Fail-fast package loading without starting Runner or contacting providers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from openjiuwen.core.common.exception.errors import ValidationError as NativeValidationError
from pydantic import ValidationError

from meta_agent.errors import BootError
from meta_agent.registry import PluginPackage, scan_plugins
from meta_agent.spec import MetaAgentSpec
from meta_agent.spec.fastpath import SkillRoute

if TYPE_CHECKING:
    from meta_agent.base_agent import MetaBaseAgent
    from meta_agent.checkpoint import LocalRecovery

_ENV = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")
# Discovery contract of the pinned native SkillUseRail. Compatibility tests
# compare this gate with its public load_skills_from_dir entry point.
_SKILL_SCAN_SKIP_DIRS = frozenset({"output", "temp", "assets", "node_modules"})


@dataclass(frozen=True)
class LoadedPackage:
    spec: MetaAgentSpec
    config_root: Path
    digest: str
    plugins: tuple[PluginPackage, ...] = ()


def _check_yaml_node(node: yaml.Node, ancestors: frozenset[int] = frozenset()) -> None:
    if id(node) in ancestors:
        raise BootError("META_CONFIG_INVALID", "Recursive YAML aliases are not supported")
    ancestors = ancestors | {id(node)}
    if isinstance(node, yaml.MappingNode):
        keys: set[str] = set()
        for key, value in node.value:
            if not isinstance(key, yaml.ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                raise BootError("META_CONFIG_INVALID", "Configuration keys must be strings")
            if key.value in keys:
                raise BootError("META_CONFIG_INVALID", f"Duplicate configuration key: {key.value}")
            keys.add(key.value)
            _check_yaml_node(value, ancestors)
    elif isinstance(node, yaml.SequenceNode):
        for value in node.value:
            _check_yaml_node(value, ancestors)


def _read_yaml(text: str) -> Any:
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if node is not None:
            _check_yaml_node(node)
        return yaml.safe_load(text)
    except yaml.YAMLError:
        raise BootError(
            "META_CONFIG_INVALID", "Invalid YAML syntax or unsupported YAML tag"
        ) from None


def _expand_env(value: Any, env: Mapping[str, str]) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in env:
                raise BootError(
                    "META_ENV_MISSING", f"Required environment variable is missing: {name}"
                )
            return env[name]

        expanded = _ENV.sub(replace, value)
        if "${ENV:" in expanded:
            raise BootError("META_CONFIG_INVALID", "Malformed or unresolved ENV placeholder")
        return expanded
    if isinstance(value, list):
        return [_expand_env(item, env) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item, env) for key, item in value.items()}
    return value


def _is_link(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _walk_error(error: OSError) -> None:
    raise error


class MetaBootLoader:
    def __init__(self, cfg_root: str | Path, env: Mapping[str, str] | None = None) -> None:
        self.config_root = Path(cfg_root).absolute()
        self.env = dict(os.environ if env is None else env)
        self._skill_routes: list[SkillRoute] = []

    def _input_path(self, value: str, *, directory: bool) -> Path:
        root = self.config_root
        if not value.strip():
            raise BootError("META_PACKAGE_PATH", "Package input path must not be blank")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            relative = candidate.relative_to(root)
            if ".." in relative.parts:
                raise ValueError("parent traversal")
            current = root
            for part in ("", *relative.parts):
                current = current / part
                if _is_link(current):
                    raise BootError(
                        "META_PACKAGE_PATH", "Package inputs must not be symlinks or junctions"
                    )
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root.resolve(strict=True))
            if directory != resolved.is_dir() or (not directory and not resolved.is_file()):
                raise ValueError("wrong input type")
            return resolved
        except (OSError, ValueError) as exc:
            raise BootError(
                "META_PACKAGE_PATH", "Package input is missing, invalid or outside cfg_root"
            ) from exc

    def _output_path(self, value: str, *, directory: bool) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = self.config_root / path
        path = path.resolve()
        if path.exists() and (directory != path.is_dir() or (not directory and not path.is_file())):
            raise BootError("META_CONFIG_INVALID", "Runtime output path has the wrong file type")
        return str(path)

    def _skills(self, paths: list[str], files: dict[str, bytes]) -> list[str]:
        resolved_paths: list[str] = []
        all_manifests: set[Path] = set()
        visible_manifests: set[Path] = set()
        names: dict[str, Path] = {}
        for value in paths:
            root = self._input_path(value, directory=True)
            # Native list entries are still parsed as comma/semicolon separated
            # paths; accepting those characters would change the validated root.
            if any(separator in str(root) for separator in (",", ";")) or str(root).strip() != str(
                root
            ):
                raise BootError(
                    "META_SKILL_INVALID", "Skill roots cannot contain native path delimiters"
                )
            if str(root) in resolved_paths:
                raise BootError("META_SKILL_INVALID", "Configured skill roots must be distinct")
            manifests: list[Path] = []
            for current, directories, filenames in os.walk(
                root, followlinks=False, onerror=_walk_error
            ):
                parent = Path(current)
                for name in directories + filenames:
                    item = parent / name
                    if _is_link(item):
                        raise BootError(
                            "META_PACKAGE_PATH", "Skills must not contain symlinks or junctions"
                        )
                for name in filenames:
                    item = parent / name
                    files[item.relative_to(self.config_root.resolve()).as_posix()] = (
                        item.read_bytes()
                    )
                    if name == "SKILL.md":
                        manifests.append(item)
            if not manifests:
                raise BootError(
                    "META_SKILL_INVALID", "Each skills directory must contain a SKILL.md"
                )
            root_visible: set[Path] = set()
            for manifest in manifests:
                # An explicit root may itself be a skill, even if its basename
                # is normally skipped while descending from a library root.
                relative = manifest.parent.relative_to(root)
                ancestor = root
                visible = True
                for part in relative.parts:
                    if (
                        (ancestor / "SKILL.md").is_file()
                        or part.startswith(".")
                        or part in _SKILL_SCAN_SKIP_DIRS
                    ):
                        visible = False
                        break
                    ancestor /= part
                if visible:
                    root_visible.add(manifest)
                if manifest in all_manifests:
                    continue
                all_manifests.add(manifest)
                text = manifest.read_text(encoding="utf-8")
                lines = text.splitlines()
                if not lines or lines[0].strip() != "---":
                    raise BootError("META_SKILL_INVALID", "SKILL.md requires YAML frontmatter")
                end = next(
                    (i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None
                )
                if end is None:
                    raise BootError("META_SKILL_INVALID", "SKILL.md frontmatter is not closed")
                metadata = _read_yaml("\n".join(lines[1:end]))
                if not isinstance(metadata, dict) or any(
                    not isinstance(metadata.get(key), str) or not metadata[key].strip()
                    for key in ("name", "description")
                ):
                    raise BootError(
                        "META_SKILL_INVALID", "SKILL.md requires nonempty name and description"
                    )
                if "fastpath" in metadata:
                    if not isinstance(metadata["fastpath"], dict):
                        raise BootError(
                            "META_SKILL_INVALID", "Skill fastpath metadata must be a mapping"
                        )
                    self._skill_routes.append(
                        SkillRoute.model_validate(
                            {**metadata["fastpath"], "skill": metadata["name"]}
                        )
                    )
                name = manifest.parent.name
                if metadata["name"] != name:
                    raise BootError(
                        "META_SKILL_INVALID", "SKILL.md name must match its directory basename"
                    )
                previous = names.get(name)
                if previous is not None and previous != manifest:
                    raise BootError(
                        "META_SKILL_INVALID",
                        f"Distinct skill directories share the native name: {name}",
                    )
                names[name] = manifest
            if not root_visible:
                raise BootError(
                    "META_SKILL_INVALID", "A skill root has no natively discoverable skills"
                )
            visible_manifests.update(root_visible)
            resolved_paths.append(str(root))
        if all_manifests != visible_manifests:
            raise BootError(
                "META_SKILL_INVALID",
                "A SKILL.md is hidden by native discovery; "
                "configure its directory as an explicit root",
            )
        return resolved_paths

    def load(self) -> LoadedPackage:
        """Validate all package input before any runtime resource is allocated."""
        try:
            config_path = self._input_path("meta_agent.yaml", directory=False)
            data = _read_yaml(config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise BootError(
                "META_PACKAGE_READ", "Cannot read the local configuration package"
            ) from exc
        return self.load_mapping(data)

    def load_mapping(self, data: Any) -> LoadedPackage:
        """Apply the existing package contract to an assembled configuration."""
        try:
            self._skill_routes = []
            data = _expand_env(data, self.env)
            if not isinstance(data, dict) or set(data) != {"meta_agent"}:
                raise BootError(
                    "META_CONFIG_INVALID", "Expected exactly one top-level meta_agent mapping"
                )
            spec = MetaAgentSpec.model_validate(data["meta_agent"])
            # Native ModelClientConfig generates a random client_id when omitted.
            # Hash the validated declared config, not ephemeral native defaults.
            declared = json.loads(spec.model_dump_json(exclude_unset=True))
            digest = hashlib.sha256(
                json.dumps(
                    {"config_root": str(self.config_root.resolve()), "meta_agent": declared},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            values = spec.model_dump(mode="python")
            native = values["deep_agent"]
            files: dict[str, bytes] = {}
            native["skills"] = self._skills(native["skills"], files)
            native["workspace"]["root_path"] = self._output_path(
                native["workspace"]["root_path"], directory=True
            )
            for name in ("cwd", "project_root"):
                if native[name] is not None:
                    native[name] = self._output_path(native[name], directory=True)
            for child in native["subagents"] or []:
                if child["skills"]:
                    child["skills"] = self._skills(child["skills"], files)
                if child["workspace"]:
                    child["workspace"]["root_path"] = self._output_path(
                        child["workspace"]["root_path"], directory=True
                    )
            values["trace"]["file_dir"] = self._output_path(
                values["trace"]["file_dir"], directory=True
            )
            persistence = values["checkpoint"]["persistence"]
            if persistence is not None:
                persistence["db_path"] = self._output_path(persistence["db_path"], directory=False)
            if spec.fastpath.enabled:
                values["fastpath"]["plugins_dir"] = str(
                    self._input_path(spec.fastpath.plugins_dir or "", directory=True)
                )
                values["fastpath"]["router"]["skill_routes"].extend(
                    route.model_dump() for route in self._skill_routes
                )
            spec = MetaAgentSpec.model_validate(values)
            plugins = scan_plugins(spec.fastpath)
            for plugin in plugins:
                digest.update(plugin.digest.encode())
            for name, content in sorted(files.items()):
                digest.update(json.dumps([name, hashlib.sha256(content).hexdigest()]).encode())
            return LoadedPackage(spec, self.config_root.resolve(), digest.hexdigest(), plugins)
        except ValidationError as exc:
            # Never put Pydantic's input_value (possibly API credentials) in errors.
            fields = ", ".join(
                ".".join(str(part) for part in error["loc"]) or "meta_agent"
                for error in exc.errors(include_input=False, include_context=False)
            )
            raise BootError(
                "META_CONFIG_INVALID", f"Invalid or unsupported configuration at: {fields}"
            ) from None
        except NativeValidationError:
            raise BootError(
                "META_CONFIG_INVALID", "Invalid native configuration or unregistered model provider"
            ) from None
        except (OSError, UnicodeError) as exc:
            raise BootError(
                "META_PACKAGE_READ", "Cannot read the local configuration package"
            ) from exc

    async def boot(
        self, *, recovery: LocalRecovery | None = None, plugin_catalog: str | Path | None = None
    ) -> MetaBaseAgent:
        loaded = self.load()
        from meta_agent.base_agent import MetaBaseAgent

        return await MetaBaseAgent.create(
            loaded.spec,
            package_digest=loaded.digest,
            plugins=loaded.plugins,
            recovery=recovery,
            plugin_catalog=plugin_catalog,
        )
