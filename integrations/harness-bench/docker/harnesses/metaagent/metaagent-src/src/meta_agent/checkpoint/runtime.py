"""Opt-in recovery policy and immutable application artifacts."""

from __future__ import annotations

import hashlib
import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from meta_agent.checkpoint.bindings import EffectBinding
from meta_agent.checkpoint.executor import EffectAdapter, Observer
from meta_agent.checkpoint.models import RecoverySnapshot, canonical, duration, identifier
from meta_agent.checkpoint.skill_files import read_skill_tree
from meta_agent.checkpoint.store import RecoveryStore
from meta_agent.errors import RecoveryConflict

if TYPE_CHECKING:
    from meta_agent.registry import PluginPackage
    from meta_agent.spec import MetaAgentSpec


@dataclass(frozen=True)
class Recovery:
    """Recovery using the selected store. Providers/rails remain trusted host code.

    Writes must use BoundEffectTool/EffectWorkflowComponent. Other configured
    tools require an explicit read-only declaration. Bump contract_version when
    host provider code changes; it cannot be inferred from provider names.
    """

    store: RecoveryStore
    adapters: tuple[EffectAdapter, ...] = ()
    read_only_tools: tuple[str, ...] = ()
    contract_version: str = "1"
    ttl: float = 30.0
    effect_observer: Observer | None = None
    plugin_effects: tuple[EffectBinding, ...] = ()

    def __post_init__(self) -> None:
        identifier(self.contract_version)
        duration(self.ttl)
        contracts = [(a.name, a.version) for a in self.adapters]
        if len(contracts) != len(set(contracts)):
            raise ValueError("Duplicate recovery effect contracts")
        names = [binding.name for binding in self.plugin_effects]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate plugin effect binding names")
        keys: dict[str, EffectAdapter] = {}
        for binding in self.plugin_effects:
            if binding.adapter not in self.adapters:
                raise ValueError("Plugin effect adapter must be registered for recovery")
            if binding.logical_key in keys and keys[binding.logical_key] != binding.adapter:
                raise ValueError("A logical key cannot bind different effect adapters")
            keys[binding.logical_key] = binding.adapter

    def config_digest(self, spec: MetaAgentSpec, package_digest: str) -> str:
        config = spec.state_config()
        # Native clients generate a new connection identity on every parse.
        # Endpoint/provider/model settings still participate in the fingerprint.
        config["deep_agent"]["model"]["model_client_config"].pop("client_id", None)
        for child in config["deep_agent"].get("subagents") or []:
            if child.get("model") is not None:
                child["model"]["model_client_config"].pop("client_id", None)
        data = [
            config,
            package_digest,
            self.contract_version,
            sorted([a.name, a.version, a.deduplicates, a.query is not None] for a in self.adapters),
            sorted(self.read_only_tools),
        ]
        # Preserve fingerprints of existing read-only recovery configurations.
        if self.plugin_effects:
            data.append(
                sorted(
                    [b.name, b.adapter.name, b.adapter.version, b.logical_key]
                    for b in self.plugin_effects
                )
            )
        return hashlib.sha256(canonical(data).encode()).hexdigest()

    @staticmethod
    def skills(spec: MetaAgentSpec) -> bytes:
        files = []
        directories = list(spec.deep_agent.skills)
        for child in spec.deep_agent.subagents or []:
            directories.extend(child.skills or [])
        for index, directory in enumerate(directories):
            for name, value in read_skill_tree(Path(directory)).items():
                files.append((index, name, value))
        return pickle.dumps(files, protocol=5)

    async def snapshot(
        self,
        spec: MetaAgentSpec,
        package_digest: str,
        child_id: str,
        graph_version: str,
        packages: tuple[PluginPackage, ...],
        *,
        skill_content: bytes | None = None,
    ) -> RecoverySnapshot:
        artifacts = {
            "skills": await self.store.put_artifact(
                self.skills(spec) if skill_content is None else skill_content
            )
        }
        for package in packages:
            artifacts[f"plugin:{package.manifest.name}"] = await self.store.put_artifact(
                pickle.dumps(package, protocol=5)
            )
        return RecoverySnapshot(
            self.config_digest(spec, package_digest), graph_version, child_id, {}, artifacts
        )

    async def restore_packages(
        self,
        snapshot: RecoverySnapshot,
        spec: MetaAgentSpec,
        package_digest: str,
    ) -> tuple[PluginPackage, ...]:
        from meta_agent.registry import PluginPackage

        if snapshot.config_digest != self.config_digest(spec, package_digest):
            raise RecoveryConflict(
                "META_CONFIG_CHANGED", "Recovery requires the original host configuration"
            )
        if "skills" not in snapshot.artifacts:
            raise RecoveryConflict("META_ARTIFACT_MISSING", "Required skills snapshot is missing")
        packages = []
        for name, digest in snapshot.artifacts.items():
            content = await self.store.get_artifact(digest)
            if name == "skills":
                if not spec.evolution.enabled and content != self.skills(spec):
                    raise RecoveryConflict(
                        "META_SKILLS_CHANGED", "Restore the original pinned skill files"
                    )
            elif name.startswith("plugin:"):
                try:
                    package = pickle.loads(content)
                    if (
                        not isinstance(package, PluginPackage)
                        or name != f"plugin:{package.manifest.name}"
                    ):
                        raise ValueError("Invalid plugin artifact")
                    computed = hashlib.sha256()
                    for filename, value in sorted(package.files):
                        computed.update(
                            json.dumps([filename, hashlib.sha256(value).hexdigest()]).encode()
                        )
                    if computed.hexdigest() != package.digest:
                        raise ValueError("Invalid plugin digest")
                    packages.append(package)
                except Exception as error:
                    raise RecoveryConflict(
                        "META_ARTIFACT_CORRUPT", "Invalid retained plugin"
                    ) from error
        return tuple(sorted(packages, key=lambda p: p.manifest.name))

    def validate_tools(self, tools: list[Any]) -> None:
        from meta_agent.checkpoint.adapters import BoundEffectTool

        for tool in tools:
            if isinstance(tool, BoundEffectTool):
                if tool.adapter not in self.adapters:
                    raise RecoveryConflict(
                        "META_EFFECT_ADAPTER", "Tool adapter must be registered for recovery"
                    )
                if any(
                    b.logical_key == tool.logical_key and b.adapter != tool.adapter
                    for b in self.plugin_effects
                ):
                    raise RecoveryConflict(
                        "META_EFFECT_BINDING", "Plugin and tool disagree on the operation adapter"
                    )
            elif getattr(getattr(tool, "card", tool), "name", None) not in self.read_only_tools:
                raise RecoveryConflict(
                    "META_UNMANAGED_TOOL", "Declare a read-only tool or use BoundEffectTool"
                )


# Preserve existing callers and configuration fingerprints.
LocalRecovery = Recovery
