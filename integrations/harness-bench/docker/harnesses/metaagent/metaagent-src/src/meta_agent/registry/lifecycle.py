"""Version catalog and atomic graph/index activation, with execution references."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import pickle
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from meta_agent.checkpoint import LocalRecovery
from meta_agent.errors import BootError, SessionStateError
from meta_agent.registry.plugins import MetaRegistry, PluginPackage, package_from_files, read_plugin
from meta_agent.routing import FastPathRouter
from meta_agent.spec import MetaAgentSpec


@dataclass(eq=False)
class PluginSnapshot:
    registry: MetaRegistry | None = None
    router: FastPathRouter | None = None
    users: int = 0

    @property
    def packages(self) -> tuple[PluginPackage, ...]:
        return self.registry.packages if self.registry else ()

    def close(self) -> None:
        if self.registry is not None:
            self.registry.close()


class PluginManager:
    """One owning runtime/event loop. Disk catalog is optional for component hosts."""

    def __init__(
        self,
        spec: MetaAgentSpec,
        *,
        recovery: LocalRecovery | None,
        catalog: Path | None,
        package_digest: str,
    ) -> None:
        self.spec, self.recovery, self.catalog = spec, recovery, catalog
        config = spec.state_config()
        config["deep_agent"]["model"]["model_client_config"].pop("client_id", None)
        for child in config["deep_agent"].get("subagents") or []:
            if child.get("model"):
                child["model"]["model_client_config"].pop("client_id", None)
        self.fingerprint = hashlib.sha256(
            json.dumps([config, package_digest], sort_keys=True).encode()
        ).hexdigest()
        self.versions: dict[tuple[str, str], PluginPackage] = {}
        self.active = PluginSnapshot()
        self.snapshots: list[PluginSnapshot] = [self.active]
        self.lock = asyncio.Lock()
        self.closed = False
        self.operations: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {}

    async def start(self, packages: tuple[PluginPackage, ...]) -> None:
        self.versions = {(p.manifest.name, p.manifest.version): p for p in packages}
        selected = list(self.versions)
        if packages and any(
            r.plugin not in {p.manifest.name for p in packages}
            for r in self.spec.fastpath.router.skill_routes
        ):
            raise BootError("META_SKILL_ROUTE", "Skill route refers to an inactive plugin.")
        if self.catalog is not None and self.catalog.exists():
            try:
                data = json.loads(self.catalog.read_text(encoding="utf-8"))
                if data["schema_version"] != 1 or data["fingerprint"] != self.fingerprint:
                    raise ValueError("Catalog belongs to another host configuration")
                self.versions = {}
                for item in data["packages"]:
                    p = package_from_files(
                        {
                            name: base64.b64decode(value, validate=True)
                            for name, value in item["files"].items()
                        }
                    )
                    if p.digest != item["digest"]:
                        raise ValueError("Catalog package digest differs")
                    self.versions[(p.manifest.name, p.manifest.version)] = p
                selected = [tuple(key) for key in data["active"]]
                packages = tuple(self.versions[key] for key in selected)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise BootError("META_PLUGIN_CATALOG", "Cannot restore plugin catalog") from exc
        self.active = await self._build(packages)
        self.snapshots = [self.active]

    async def _build(self, packages: tuple[PluginPackage, ...]) -> PluginSnapshot:
        if not packages:
            return PluginSnapshot()
        registry = MetaRegistry(
            packages,
            self.spec.fastpath,
            self.spec.product_id,
            self.spec.agent_id,
            effect_bindings=self.recovery.plugin_effects if self.recovery else (),
            operations=self.operations,
        )
        try:
            await registry.start()
            config = self.spec.fastpath.router.model_copy(deep=True)
            names = {p.manifest.name for p in packages}
            config = config.model_copy(
                update={"skill_routes": [r for r in config.skill_routes if r.plugin in names]}
            )
            router = FastPathRouter(
                config,
                [p.manifest for p in packages],
                {p.manifest.name: p.digest for p in packages},
                registry.graph_version,
            )
            await router.start()
            return PluginSnapshot(registry, router)
        except BaseException:
            registry.close()
            raise

    def _ensure_open(self) -> None:
        if self.closed:
            raise SessionStateError("META_CLOSED", "Plugin manager is closed")
        if not self.spec.fastpath.enabled:
            raise BootError("META_PLUGIN_CONFIG", "Hot loading requires enabled fastpath")

    def _persist(
        self, versions: dict[tuple[str, str], PluginPackage], packages: tuple[PluginPackage, ...]
    ) -> None:
        if self.catalog is None:
            return
        data = {
            "schema_version": 1,
            "fingerprint": self.fingerprint,
            "active": [[p.manifest.name, p.manifest.version] for p in packages],
            "packages": [
                {
                    "digest": p.digest,
                    "files": {
                        name: base64.b64encode(content).decode() for name, content in p.files
                    },
                }
                for p in versions.values()
            ],
        }
        temporary = self.catalog.with_name(self.catalog.name + "." + uuid4().hex + ".tmp")
        try:
            self.catalog.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(data, output)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(self.catalog)
        except OSError as exc:
            raise BootError("META_PLUGIN_CATALOG", "Cannot save plugin catalog") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def acquire(self) -> PluginSnapshot:
        self.active.users += 1
        return self.active

    def release(self, snapshot: PluginSnapshot) -> None:
        snapshot.users -= 1
        self._collect()

    def _collect(self) -> None:
        for snapshot in list(self.snapshots):
            if snapshot is not self.active and snapshot.users == 0:
                snapshot.close()
                self.snapshots.remove(snapshot)

    def list(self) -> list[dict[str, Any]]:
        active = {p.digest for p in self.active.packages}
        return [
            {
                "name": name,
                "version": version,
                "digest": p.digest,
                "active": p.digest in active,
                "live_references": sum(s.users for s in self.snapshots if p in s.packages),
            }
            for (name, version), p in sorted(self.versions.items())
        ]

    async def load(self, directory: str | Path) -> PluginPackage:
        async with self.lock:
            self._ensure_open()
            package = read_plugin(directory)
            key = (package.manifest.name, package.manifest.version)
            if key in self.versions:
                if self.versions[key].digest != package.digest:
                    raise BootError(
                        "META_PLUGIN_VERSION_CONFLICT", "Version already has different bytes"
                    )
                return self.versions[key]
            preflight = await self._build((package,))
            preflight.close()
            self._ensure_open()
            versions = {**self.versions, key: package}
            self._persist(versions, self.active.packages)
            self.versions = versions
            return package

    async def activate(self, name: str, version: str | None) -> None:
        """An explicit older version performs rollback; None deactivates a name."""
        async with self.lock:
            self._ensure_open()
            packages = {p.manifest.name: p for p in self.active.packages}
            if version is None:
                if name not in packages:
                    raise BootError("META_PLUGIN_NOT_FOUND", "Active plugin not found")
                del packages[name]
            else:
                if (name, version) not in self.versions:
                    raise BootError("META_PLUGIN_NOT_FOUND", "Load the plugin version first")
                packages[name] = self.versions[(name, version)]
            snapshot = await self._build(tuple(packages[key] for key in sorted(packages)))
            try:
                self._ensure_open()
                self._persist(self.versions, snapshot.packages)
            except BaseException:
                snapshot.close()
                raise
            self.active = snapshot  # No await between publishing the graph and its index.
            self.snapshots.append(snapshot)
            self._collect()

    async def publish_retained(
        self,
        packages: tuple[PluginPackage, ...],
        selected: dict[str, str | None],
        *,
        commit: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Publish reviewed bytes after their owning checkpoint has committed.

        Restoring an already committed selection omits ``commit``. The review
        checkpoint owns this state; the optional disk catalog is not written.
        """
        async with self.lock:
            self._ensure_open()
            versions = dict(self.versions)
            for package in packages:
                key = (package.manifest.name, package.manifest.version)
                if key in versions and versions[key].digest != package.digest:
                    raise BootError(
                        "META_PLUGIN_VERSION_CONFLICT", "Version already has different bytes"
                    )
                versions[key] = package
            active = {p.manifest.name: p for p in self.active.packages}
            for name, version in selected.items():
                if version is None:
                    active.pop(name, None)
                else:
                    if (name, version) not in versions:
                        raise BootError("META_PLUGIN_NOT_FOUND", "Load the plugin version first")
                    active[name] = versions[(name, version)]
            snapshot = await self._build(tuple(active[name] for name in sorted(active)))
            try:
                self._ensure_open()
                if commit is not None:
                    await commit()
                self._ensure_open()
            except BaseException:
                snapshot.close()
                raise
            self.versions = versions
            self.active = snapshot
            self.snapshots.append(snapshot)
            self._collect()

    async def unload(self, name: str, version: str) -> None:
        async with self.lock:
            self._ensure_open()
            package = self.versions.get((name, version))
            if package is None:
                raise BootError("META_PLUGIN_NOT_FOUND", "Plugin version not found")
            if package in self.active.packages:
                raise SessionStateError(
                    "META_PLUGIN_ACTIVE", "Deactivate or replace the active version first"
                )
            if any(s.users and package in s.packages for s in self.snapshots):
                raise SessionStateError(
                    "META_VERSION_PINNED", "A live execution still uses this version"
                )
            if self.recovery is not None:
                digest = hashlib.sha256(pickle.dumps(package, protocol=5)).hexdigest()
                # Existing store refuses deletion until all durable retention pins retire.
                await self.recovery.store.delete_artifact(digest)
            self._ensure_open()
            versions = {key: p for key, p in self.versions.items() if key != (name, version)}
            self._persist(versions, self.active.packages)
            self.versions = versions

    async def aclose(self) -> None:
        self.closed = True
        async with self.lock:
            for snapshot in self.snapshots:
                snapshot.close()
            self.snapshots.clear()
