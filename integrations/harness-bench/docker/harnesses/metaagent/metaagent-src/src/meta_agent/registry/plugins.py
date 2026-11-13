"""Snapshot local trusted plugins before importing any of their code."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from packaging.version import Version

from meta_agent.errors import BootError
from meta_agent.registry.workflow import PluginWorkflow
from meta_agent.routing.conditions import Condition
from meta_agent.spec.fastpath import FastPathConfig, WorkflowPluginManifest

if TYPE_CHECKING:
    from meta_agent.checkpoint.adapters import EffectWorkflowComponent
    from meta_agent.checkpoint.bindings import EffectBinding


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


@dataclass(frozen=True)
class PluginPackage:
    """Manifest JSON and source bytes, detached from later filesystem edits."""

    manifest_json: str
    files: tuple[tuple[str, bytes], ...]
    digest: str

    @property
    def manifest(self) -> WorkflowPluginManifest:
        return WorkflowPluginManifest.model_validate_json(self.manifest_json)


def _linked(path: Path) -> bool:
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def package_from_files(files: dict[str, bytes]) -> PluginPackage:
    """Validate the same immutable bytes for boot, hot loading and catalog restore."""
    try:
        if len(files) > 128 or sum(map(len, files.values())) > 5_000_000:
            raise ValueError("Plugin package exceeds size limits")
        manifest = WorkflowPluginManifest.model_validate(
            json.loads(files["manifest.json"], object_pairs_hook=_unique_object)
        )
        Condition(manifest.intent.when)
        if manifest.min_meta_agent and Version(version("meta-agent")) < Version(
            manifest.min_meta_agent
        ):
            raise ValueError("Plugin requires a newer MetaAgent")
        entry_file = manifest.entry.split(":")[0]
        if entry_file not in files or any(
            name.endswith(".py") and name != entry_file for name in files
        ):
            raise ValueError("Plugins require one self-contained Python entry file")
        digest = hashlib.sha256()
        for name, content in sorted(files.items()):
            digest.update(json.dumps([name, hashlib.sha256(content).hexdigest()]).encode())
        return PluginPackage(
            manifest.model_dump_json(), tuple(sorted(files.items())), digest.hexdigest()
        )
    except (ValueError, KeyError, UnicodeError) as exc:
        raise BootError("META_PLUGIN_PACKAGE", "Invalid plugin package.") from exc


def read_plugin(directory: str | Path) -> PluginPackage:
    """Read one trusted version directory without executing its entry point."""
    try:
        directory = Path(directory)
        if _linked(directory) or not directory.is_dir():
            raise ValueError("Plugin directory must be unlinked")
        files: dict[str, bytes] = {}
        for current, folders, names in os.walk(directory, followlinks=False):
            folders[:] = [name for name in folders if name != "__pycache__"]
            for name in folders + names:
                if _linked(Path(current) / name):
                    raise ValueError("Plugin links are forbidden")
            for name in names:
                path = Path(current) / name
                files[path.relative_to(directory).as_posix()] = path.read_bytes()
        return package_from_files(files)
    except (OSError, ValueError) as exc:
        raise BootError("META_PLUGIN_PACKAGE", "Invalid plugin directory.") from exc


def scan_plugins(config: FastPathConfig) -> tuple[PluginPackage, ...]:
    if not config.enabled:
        return ()
    assert config.plugins_dir is not None
    try:
        root = Path(config.plugins_dir)
        if not root.is_dir() or _linked(root):
            raise ValueError("Invalid plugin root")
        packages = []
        identities = set()
        for directory in sorted(root.iterdir()):
            if _linked(directory) or not directory.is_dir():
                raise ValueError("Plugin root must contain unlinked package directories only")
            package = read_plugin(directory)
            manifest = package.manifest
            identity = (manifest.name, manifest.version)
            if identity in identities:
                raise ValueError("Duplicate plugin name/version")
            identities.add(identity)
            packages.append(package)
        selected: dict[str, PluginPackage] = {}
        requested = config.plugins or sorted({p.manifest.name for p in packages})
        for selector in requested:
            name, _, requested_version = selector.partition("@")
            candidates = [
                p
                for p in packages
                if p.manifest.name == name
                and (not requested_version or p.manifest.version == requested_version)
            ]
            if not candidates or name in selected:
                raise ValueError("Missing or ambiguous plugin selection")
            selected[name] = max(candidates, key=lambda p: Version(p.manifest.version))
        return tuple(selected[name] for name in sorted(selected))
    except (OSError, ValueError, KeyError, UnicodeError) as exc:
        raise BootError("META_PLUGIN_PACKAGE", "Invalid plugin package or selection.") from exc


@dataclass(frozen=True)
class PluginBuildContext:
    product_id: str
    agent_id: str
    workflow_id: str
    plugin_name: str
    plugin_version: str
    plugin_digest: str
    files: MappingProxyType[str, bytes]
    effects: MappingProxyType[str, EffectBinding]
    operations: MappingProxyType[str, Callable[[dict[str, Any]], Awaitable[Any]]]

    def effect(self, name: str) -> EffectWorkflowComponent:
        """Construct a node using a declared, host-bound operation."""
        if name not in self.effects:
            raise BootError("META_PLUGIN_EFFECT", "Plugin requested an undeclared effect binding")
        return self.effects[name].component()

    def workflow(self) -> PluginWorkflow:
        from openjiuwen.core.workflow import WorkflowCard

        return PluginWorkflow(card=WorkflowCard(id=self.workflow_id, name=self.plugin_name))


class MetaRegistry:
    def __init__(
        self,
        packages: tuple[PluginPackage, ...],
        config: FastPathConfig,
        product_id: str,
        agent_id: str,
        *,
        effect_bindings: tuple[EffectBinding, ...] = (),
        operations: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] | None = None,
    ) -> None:
        self.packages = packages
        self.config = config
        self.product_id, self.agent_id = product_id, agent_id
        self.effect_bindings = {binding.name: binding for binding in effect_bindings}
        self.operations = dict(operations or {})
        if len(self.effect_bindings) != len(effect_bindings):
            raise BootError("META_PLUGIN_EFFECT", "Duplicate host effect bindings")
        self.modules: dict[str, ModuleType] = {}
        self.factories: dict[str, Any] = {}
        self.graph_version = hashlib.sha256(
            json.dumps(
                [config.model_dump(mode="json"), [p.digest for p in packages]], sort_keys=True
            ).encode()
        ).hexdigest()

    async def start(self) -> None:
        try:
            # Validate all declarations before importing any plugin code.
            for package in self.packages:
                if set(package.manifest.effects) - self.effect_bindings.keys():
                    raise BootError(
                        "META_PLUGIN_EFFECT", "Plugin effects require LocalRecovery host bindings"
                    )
            for package in self.packages:
                manifest = package.manifest
                filename, function = manifest.entry.split(":")
                name = f"_meta_plugin_{package.digest}_{uuid4().hex}"
                module = ModuleType(name)
                module.__file__ = f"<plugin:{manifest.name}@{manifest.version}/{filename}>"
                self.modules[name] = module
                sys.modules[name] = module
                exec(
                    compile(dict(package.files)[filename], module.__file__, "exec"), module.__dict__
                )
                factory = getattr(module, function)
                if not inspect.iscoroutinefunction(factory):
                    raise ValueError("Plugin build must be async")
                self.factories[manifest.name] = factory
            await self.build("preflight")
        except Exception as exc:
            self.close()
            if isinstance(exc, BootError):
                raise
            raise BootError(
                "META_PLUGIN_IMPORT", "Plugin import or factory resolution failed."
            ) from exc
        except BaseException:
            self.close()
            raise

    async def build(self, scope: str) -> dict[str, PluginWorkflow]:
        result = {}
        for package in self.packages:
            manifest = package.manifest
            context = PluginBuildContext(
                self.product_id,
                self.agent_id,
                f"{scope}-{manifest.name}-{package.digest[:12]}",
                manifest.name,
                manifest.version,
                package.digest,
                MappingProxyType(dict(package.files)),
                MappingProxyType({name: self.effect_bindings[name] for name in manifest.effects}),
                MappingProxyType(self.operations),
            )
            try:
                graph = await self.factories[manifest.name](context)
                if not isinstance(graph, PluginWorkflow) or graph.sealed:
                    raise ValueError("Factory must return a fresh PluginWorkflow")
                graph.validate(self.config.max_nesting_depth)
                graph.validate_effects(tuple(context.effects.values()))
                result[manifest.name] = graph
            except Exception as exc:
                raise BootError("META_PLUGIN_BUILD", "Plugin graph construction failed.") from exc
        return result

    def close(self) -> None:
        for name, module in self.modules.items():
            if sys.modules.get(name) is module:
                del sys.modules[name]
        self.modules.clear()
        self.factories.clear()
