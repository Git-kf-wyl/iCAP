"""Load the new package manifest while preserving the legacy DeepAgent loader."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal

from openjiuwen.core.context_engine import ContextEngineConfig
from openjiuwen.core.workflow import Workflow
from openjiuwen.extensions.observability.config import ObservabilityConfig
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from meta_agent.boot.boot_loader import LoadedPackage, MetaBootLoader, _expand_env, _read_yaml
from meta_agent.errors import BootError
from meta_agent.routing.router import FastPathRouter, WorkflowRouteTarget
from meta_agent.spec.fastpath import IntentMetadata, RouterConfig
from meta_agent.spec.platform import PackageServicesConfig, ToolPermissions
from meta_agent.workflow.ir import compile_workflow, parse_workflow_ir
from meta_agent.workflow.runtime import MetaWorkflowRuntime

if TYPE_CHECKING:
    from meta_agent.package_runtime import MetaPackageRuntime


class WorkflowSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ir: str | None = Field(default=None, min_length=1)
    factory: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def one_source(self) -> WorkflowSource:
        if (self.ir is None) == (self.factory is None):
            raise ValueError("Select exactly one workflow.ir or workflow.factory")
        return self


class DeepAgentSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: str = Field(min_length=1)
    permissions: ToolPermissions = Field(default_factory=ToolPermissions)


class PackageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    mode: Literal["workflow", "deepagent", "hybrid"]
    product_id: str = Field(default="local", min_length=1)
    agent_id: str | None = Field(default=None, min_length=1)
    workflow: WorkflowSource | None = None
    deep_agent: DeepAgentSource | None = None
    router: str | None = Field(default=None, min_length=1)
    observability: ObservabilityConfig | None = Field(default=None, repr=False)
    services: PackageServicesConfig = Field(default_factory=PackageServicesConfig)
    context_engine_config: ContextEngineConfig | None = None

    @field_validator("product_id", "agent_id")
    @classmethod
    def nonempty_identity(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Identity must not be blank")
        return value

    @model_validator(mode="after")
    def mode_sources(self) -> PackageConfig:
        if self.mode == "workflow" and self.services.context_service is not None:
            raise ValueError(
                "ContextService final-window binding currently supports the DeepAgent path only"
            )
        expected = {
            "workflow": (True, False, False),
            "deepagent": (False, True, False),
            "hybrid": (True, True, True),
        }[self.mode]
        if (
            self.workflow is not None,
            self.deep_agent is not None,
            self.router is not None,
        ) != expected:
            raise ValueError("Package sources must match the selected runtime mode")
        return self


class HybridRoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    workflow: IntentMetadata
    router: RouterConfig = Field(default_factory=RouterConfig)


@dataclass(frozen=True)
class WorkflowBuildContext:
    """Inputs to a trusted synchronous ``build_workflow(context)`` factory."""

    package_root: Path
    workflow_id: str
    product_id: str
    agent_id: str
    tools: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedWorkflowPackage:
    name: str
    version: str
    spec: PackageConfig
    config_root: Path
    digest: str
    source_path: Path
    source_bytes: bytes = field(repr=False)
    ir: dict[str, Any] | None = field(default=None, repr=False)
    factory_name: str | None = None

    @property
    def agent_id(self) -> str:
        return self.spec.agent_id or self.name

    @property
    def workflow_id(self) -> str:
        return f"{self.agent_id}-{self.digest[:16]}"

    def build_workflow(self, tools: dict[str, Any] | None = None) -> Any:
        """Construct native components only; no Runner or provider startup."""
        if self.ir is not None:
            return compile_workflow(self.ir, workflow_id=self.workflow_id, tools=tools)
        module_name = f"_meta_workflow_{self.digest}"
        module = ModuleType(module_name)
        module.__file__ = str(self.source_path)
        # Python class decorators (including dataclass) look up their module.
        sys.modules[module_name] = module
        try:
            exec(compile(self.source_bytes, str(self.source_path), "exec"), module.__dict__)
            factory = getattr(module, self.factory_name or "", None)
            if not callable(factory):
                raise TypeError("Missing synchronous workflow factory")
            graph = factory(
                WorkflowBuildContext(
                    self.config_root,
                    self.workflow_id,
                    self.spec.product_id,
                    self.agent_id,
                    tools or {},
                )
            )
            if not isinstance(graph, Workflow):
                raise TypeError("Workflow factory must return a native Workflow")
            return graph
        except Exception as error:
            sys.modules.pop(module_name, None)
            raise BootError(
                "META_WORKFLOW_FACTORY", "Could not construct the configured native Workflow"
            ) from error

    async def boot(self) -> MetaWorkflowRuntime:
        return await MetaWorkflowRuntime.create(
            self.build_workflow,
            product_id=self.spec.product_id,
            agent_id=self.agent_id,
            package_digest=self.digest,
            observability=self.spec.observability,
            services=self.spec.services,
            context_engine_config=self.spec.context_engine_config,
        )


@dataclass(frozen=True)
class LoadedAgentPackage:
    name: str
    version: str
    spec: PackageConfig
    config_root: Path
    digest: str
    deep: LoadedPackage
    workflow: LoadedWorkflowPackage | None = None
    routing: HybridRoutingConfig | None = None

    @property
    def agent_id(self) -> str:
        return self.deep.spec.agent_id

    def build_router(self) -> FastPathRouter | None:
        if self.routing is None:
            return None
        assert self.workflow is not None
        return FastPathRouter(
            self.routing.router,
            [WorkflowRouteTarget("workflow", self.version, self.routing.workflow)],
            {"workflow": self.workflow.digest},
            self.digest,
        )

    async def boot(self) -> MetaPackageRuntime:
        from meta_agent.package_runtime import MetaPackageRuntime

        return await MetaPackageRuntime.create(
            self.deep.spec,
            package_digest=self.digest,
            workflow=self.workflow.build_workflow if self.workflow else None,
            router=self.build_router(),
            services=self.spec.services,
            context_engine_config=self.spec.context_engine_config,
        )


class MetaPackageLoader:
    """Explicit new-format dispatch; ordinary legacy packages keep their contract.

    AgentFlow still owns its manifest fields (including ``workflows``). Only the
    top-level ``meta_agent`` block is interpreted here. N1 supports three modes;
    declaring an unsupported mode never silently falls back to DeepAgent.
    """

    def __init__(self, cfg_root: str | Path, env: Mapping[str, str] | None = None) -> None:
        self.config_root = Path(cfg_root).resolve()
        self.env = dict(os.environ if env is None else env)

    def _source_path(self, value: str) -> Path:
        try:
            path = (self.config_root / value).resolve(strict=True)
            path.relative_to(self.config_root)
            if not path.is_file():
                raise ValueError("Not a file")
            return path
        except (OSError, ValueError) as error:
            raise BootError(
                "META_PACKAGE_PATH", "Package source must be a file within the package"
            ) from error

    def load(self) -> LoadedWorkflowPackage | LoadedAgentPackage | LoadedPackage:
        manifest_path = self.config_root / "package.json"
        if not manifest_path.exists():
            return MetaBootLoader(self.config_root, self.env).load()
        try:
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes)
            if not isinstance(manifest, dict):
                raise ValueError("Package manifest must be an object")
        except (OSError, ValueError) as error:
            raise BootError("META_CONFIG_INVALID", "Invalid package.json") from error
        if "meta_agent" not in manifest:
            return MetaBootLoader(self.config_root, self.env).load()
        try:
            spec = PackageConfig.model_validate(_expand_env(manifest["meta_agent"], self.env))
            name, version = manifest["name"], manifest["version"]
            if not all(isinstance(value, str) and value.strip() for value in (name, version)):
                raise ValueError("Package name and version are required")
        except (KeyError, ValueError, ValidationError) as error:
            raise BootError(
                "META_CONFIG_INVALID",
                "Invalid package configuration: select workflow, deepagent or hybrid "
                "with matching sources",
            ) from error
        if spec.mode == "workflow":
            return self._load_workflow(spec, name, version, manifest_bytes)
        assert spec.deep_agent is not None
        try:
            native_bytes = self._source_path(spec.deep_agent.spec).read_bytes()
            native = _read_yaml(native_bytes.decode("utf-8"))
            if not isinstance(native, dict):
                raise ValueError("Expected native DeepAgent configuration")
            native = _expand_env(native, self.env)
            card = native.setdefault("card", {})
            if spec.agent_id is not None and card.get("id", spec.agent_id) != spec.agent_id:
                raise ValueError("Manifest and DeepAgent identities differ")
            card.setdefault("id", spec.agent_id or name)
            if spec.context_engine_config is not None:
                if native.get("context_engine_config") is not None:
                    raise ValueError(
                        "Set context_engine_config in manifest or agent spec, not both"
                    )
                native["context_engine_config"] = spec.context_engine_config.model_dump()
            service_config = spec.services.model_dump(exclude_none=True)
            deep = MetaBootLoader(self.config_root, self.env).load_mapping(
                {
                    "meta_agent": {
                        "product_id": spec.product_id,
                        "deep_agent": native,
                        "csp": {"enabled": bool(service_config), **service_config},
                        "permissions": spec.deep_agent.permissions.model_dump(),
                        "trace": {
                            "enabled": False,
                            "file_dir": ".artifacts/trace",
                            "observability": spec.observability,
                        },
                    }
                }
            )
            workflow = None
            routing = None
            digest = hashlib.sha256(manifest_bytes + b"\0" + native_bytes + deep.digest.encode())
            if spec.mode == "hybrid":
                assert spec.workflow is not None and spec.router is not None
                workflow = self._load_workflow(
                    PackageConfig(
                        schema_version=1,
                        mode="workflow",
                        product_id=spec.product_id,
                        agent_id=deep.spec.agent_id,
                        workflow=spec.workflow,
                        observability=spec.observability,
                        services=spec.services.model_copy(update={"context_service": None}),
                        context_engine_config=spec.context_engine_config,
                    ),
                    name,
                    version,
                    manifest_bytes,
                )
                router_bytes = self._source_path(spec.router).read_bytes()
                routing = HybridRoutingConfig.model_validate(
                    _expand_env(_read_yaml(router_bytes.decode("utf-8")), self.env)
                )
                digest.update(workflow.digest.encode())
                digest.update(router_bytes)
            loaded = LoadedAgentPackage(
                name, version, spec, self.config_root, digest.hexdigest(), deep, workflow, routing
            )
            # Validate rules/provider registration without starting providers or Runner.
            loaded.build_router()
            return loaded
        except (ValueError, TypeError, AttributeError, OSError) as error:
            raise BootError(
                "META_CONFIG_INVALID", "Invalid DeepAgent or Hybrid package configuration"
            ) from error

    def _load_workflow(
        self, spec: PackageConfig, name: str, version: str, manifest_bytes: bytes
    ) -> LoadedWorkflowPackage:
        assert spec.workflow is not None
        factory_name = None
        if spec.workflow.factory is not None:
            path, separator, factory_name = spec.workflow.factory.rpartition(":")
            if not separator or not path or not factory_name.isidentifier():
                raise BootError("META_WORKFLOW_FACTORY", "Use relative/file.py:factory_name")
        else:
            assert spec.workflow.ir is not None
            path = spec.workflow.ir
        source_path = self._source_path(path)
        try:
            source_bytes = source_path.read_bytes()
        except OSError as error:
            raise BootError("META_PACKAGE_PATH", "Could not read workflow source") from error
        ir = None
        if spec.workflow.ir is not None:
            try:
                ir = _expand_env(json.loads(source_bytes), self.env)
            except ValueError as error:
                raise BootError("META_WORKFLOW_IR", "Invalid Workflow IR JSON") from error
            parse_workflow_ir(ir)
        # Fingerprint the manifest and directly declared workflow source. Factory
        # imports/dependency versions remain the responsibility of the package lock.
        digest = hashlib.sha256(manifest_bytes + b"\0" + source_bytes).hexdigest()
        return LoadedWorkflowPackage(
            name,
            version,
            spec,
            self.config_root,
            digest,
            source_path,
            source_bytes,
            ir,
            factory_name,
        )
