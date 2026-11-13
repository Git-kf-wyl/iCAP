"""Full native harness configuration inside a strict, bounded MetaAgent spec.

M2 preserves native model-provider extension fields. Native fields that would be
silently ignored by Pydantic are rejected, including nested declarations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, Self

from openjiuwen.core.foundation.tool import ToolCard
from openjiuwen.core.session.checkpointer.checkpointer import CheckpointerConfig
from openjiuwen.extensions.observability.config import ObservabilityConfig
from openjiuwen.harness.schema.deep_agent_spec import DeepAgentSpec
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meta_agent.spec.fastpath import FastPathConfig
from meta_agent.spec.platform import CspConfig, ToolPermissions


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class DisabledFeature(StrictConfig):
    """An explicit disabled section; no unimplemented settings are accepted."""

    enabled: Literal[False] = False


class BudgetConfig(StrictConfig):
    """Native goal limits, checked at attempt boundaries."""

    enabled: bool = False
    max_attempts: int = Field(default=20, gt=0)
    token_budget: int = Field(default=200000, gt=0)
    stop_strategy: Literal["hybrid", "agent_report", "transcript"] = "hybrid"

    @model_validator(mode="after")
    def require_enabled(self) -> Self:
        if not self.enabled and self.model_fields_set - {"enabled"}:
            # model_dump includes defaults; allow those during runtime copying.
            if (
                self.max_attempts != 20
                or self.token_budget != 200000
                or self.stop_strategy != "hybrid"
            ):
                raise ValueError("Budget limits require enabled=true")
        return self


class PersistenceConfig(StrictConfig):
    db_type: Literal["sqlite"] = "sqlite"
    db_path: str = Field(min_length=1)
    db_timeout: float = Field(default=30.0, gt=0)
    db_enable_wal: bool = True

    @field_validator("db_path")
    @classmethod
    def nonempty_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("db_path must not be blank")
        return value


class CheckpointConfig(StrictConfig):
    backend: Literal["in_memory", "persistence"] = "in_memory"
    schema_version: Literal[1] = 1
    persistence: PersistenceConfig | None = None
    side_effect: DisabledFeature = Field(default_factory=DisabledFeature)

    @model_validator(mode="after")
    def validate_backend(self) -> Self:
        if (self.backend == "persistence") != (self.persistence is not None):
            raise ValueError(
                "SQLite persistence settings are required only for persistence backend"
            )
        return self

    def to_kernel(self) -> CheckpointerConfig:
        return CheckpointerConfig(
            type=self.backend,
            conf=self.persistence.model_dump() if self.persistence is not None else {},
        )


class TraceConfig(StrictConfig):
    """Metadata JSONL, optional local archives, and native remote observability."""

    file_dir: str = Field(min_length=1)
    enabled: bool = True
    rollout: Literal["none", "daily"] = "daily"
    trajectories: bool = False
    observability: ObservabilityConfig | None = Field(default=None, repr=False)

    @field_validator("observability", mode="before")
    @classmethod
    def validate_observability(cls, value: Any) -> ObservabilityConfig | None:
        if value is None:
            return None
        parsed = ObservabilityConfig.model_validate(value)
        _reject_dropped_fields(value, parsed, "trace.observability")
        return parsed

    @field_validator("file_dir")
    @classmethod
    def nonempty_path(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("file_dir must not be blank")
        return value


class ConcurrencyConfig(StrictConfig):
    distributed: Literal[False] = False
    conflict: Literal["reject"] = "reject"


class EvolutionConfig(StrictConfig):
    """Host-triggered native Skill proposals with mandatory approval."""

    enabled: bool = False
    auto_propose: bool = False
    auto_skill: str | None = None

    @model_validator(mode="after")
    def validate_auto_proposal(self) -> Self:
        if self.auto_propose and (
            not self.enabled or self.auto_skill is None or not self.auto_skill.strip()
        ):
            raise ValueError("Automatic evolution requires enabled=true and a nonempty auto_skill")
        return self


def _reject_dropped_fields(raw: Any, parsed: Any, path: str) -> None:
    """Respect explicit native extension maps while rejecting ignored typos."""
    if isinstance(parsed, BaseModel) and isinstance(raw, Mapping):
        fields = type(parsed).model_fields
        names = set(fields)
        names.update(field.alias for field in fields.values() if field.alias)
        if type(parsed).model_config.get("extra") != "allow":
            unknown = set(raw) - names
            if unknown:
                raise ValueError(
                    f"Unknown native configuration fields at {path}: "
                    f"{sorted(str(key) for key in unknown)}"
                )
        for name, field in fields.items():
            key = field.alias if field.alias in raw else name
            if key in raw:
                _reject_dropped_fields(raw[key], getattr(parsed, name), f"{path}.{name}")
    elif isinstance(raw, list) and isinstance(parsed, list):
        for index, (raw_item, parsed_item) in enumerate(zip(raw, parsed, strict=True)):
            _reject_dropped_fields(raw_item, parsed_item, f"{path}[{index}]")


class MetaAgentSpec(StrictConfig):
    """MetaAgent assembly over the pinned native DeepAgent specification.

    Tools and custom rails are trusted application code. Ordinary execution
    retains native system/web/MCP tools; LocalRecovery validates its own effects.
    """

    product_id: str = Field(default="local", min_length=1)
    deep_agent: DeepAgentSpec
    checkpoint: CheckpointConfig = Field(default_factory=CheckpointConfig)
    trace: TraceConfig
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    fastpath: FastPathConfig = Field(default_factory=FastPathConfig)
    team: DisabledFeature = Field(default_factory=DisabledFeature)
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    csp: CspConfig = Field(default_factory=CspConfig)
    permissions: ToolPermissions = Field(default_factory=ToolPermissions)

    @field_validator("deep_agent", mode="before")
    @classmethod
    def validate_native_keys(cls, value: Any) -> DeepAgentSpec:
        parsed = DeepAgentSpec.model_validate(value)
        _reject_dropped_fields(value, parsed, "deep_agent")
        return parsed

    @model_validator(mode="after")
    def validate_supported_runtime(self) -> Self:
        native = self.deep_agent
        if self.trace.trajectories and not self.trace.enabled:
            raise ValueError("Trajectory capture requires trace.enabled=true")
        if self.evolution.enabled and not self.trace.trajectories:
            raise ValueError("Evolution requires opt-in trace.trajectories=true")
        configured_rails = [
            *(native.rails or []),
            *[rail for child in native.subagents or [] for rail in child.rails or []],
        ]
        if any(rail.type == "core.skill_create" for rail in configured_rails):
            if not self.trace.trajectories:
                raise ValueError("core.skill_create requires opt-in trace.trajectories=true")
        if not self.product_id.strip():
            raise ValueError("product_id must not be blank")
        if (
            native.card is None
            or not native.card.id.strip()
            or "id" not in native.card.model_fields_set
        ):
            raise ValueError("deep_agent.card.id must be explicitly supplied and stable")
        if native.model is None or native.model.model_request_config is None:
            raise ValueError("deep_agent.model and model_request_config are required")
        if not native.model.model_request_config.model_name:
            raise ValueError("deep_agent.model.model_request_config.model is required")
        if native.workspace is None or not native.workspace.root_path.strip():
            raise ValueError("deep_agent.workspace.root_path is required")
        if "root_path" not in native.workspace.model_fields_set or native.workspace.stable_base:
            raise ValueError(
                "M2 requires an explicit workspace.root_path with stable_base disabled"
            )
        if not native.skills:
            raise ValueError("deep_agent.skills must reference the mandatory skill package")
        server_names = [m.server_name for m in native.mcps or []]
        if len(server_names) != len(set(server_names)):
            raise ValueError("MCP server names must be unique")
        if native.agent_template_spec is not None:
            raise ValueError("agent_template_spec is not supported by the M2 runtime")
        if native.add_general_purpose_agent:
            raise ValueError("Declare general-purpose agents explicitly in subagents")
        if native.enable_async_subagent and not native.enable_subagent_runtime:
            if not native.enable_task_loop:
                raise ValueError("Async session subagents require enable_task_loop=true")
        names: set[str] = set()
        for child in native.subagents or []:
            if "id" not in child.agent_card.model_fields_set or not child.agent_card.id.strip():
                raise ValueError("Subagent agent_card.id must be explicitly supplied and stable")
            if child.workspace is not None and (
                child.workspace.stable_base or "root_path" not in child.workspace.model_fields_set
            ):
                raise ValueError(
                    "Subagent workspace requires an explicit root_path and no stable_base"
                )
            name = child.agent_card.name
            if not name or name in names:
                raise ValueError("Subagents require unique nonempty names")
            names.add(name)
            if child.factory_name or child.factory_kwargs:
                raise ValueError("Subagent custom factories are not enabled")
            if child.enable_task_loop:
                raise ValueError("Configured subagents use one bounded ReAct round per turn")
            if child.max_iterations is not None and child.max_iterations <= 0:
                raise ValueError("Subagent max_iterations must be positive")
        if self.budget.enabled and not native.enable_task_loop:
            raise ValueError("Budget execution requires deep_agent.enable_task_loop=true")
        for tool in native.tools or []:
            if isinstance(tool, ToolCard) and (
                not tool.id.strip() or "id" not in tool.model_fields_set
            ):
                raise ValueError("Each tool card.id must be explicitly supplied and stable")
        if native.max_iterations is not None and native.max_iterations <= 0:
            raise ValueError("max_iterations must be positive")
        return self

    @property
    def agent_id(self) -> str:
        card = self.deep_agent.card
        assert card is not None
        return str(card.id)

    def state_config(self) -> dict[str, Any]:
        """Keep existing state fingerprints when only new observation defaults appear."""
        config = self.model_dump(mode="json")
        if not self.evolution.auto_propose:
            config["evolution"].pop("auto_propose")
        if self.evolution.auto_skill is None:
            config["evolution"].pop("auto_skill")
        if self.trace.rollout == "daily":
            config["trace"].pop("rollout")
        if not self.trace.trajectories:
            config["trace"].pop("trajectories")
        if self.trace.observability is None:
            config["trace"].pop("observability")
        for adapter in ("ops", "memory_service", "skills_runtime", "context_service"):
            if getattr(self.csp, adapter) is None:
                config["csp"].pop(adapter)
        for adapter in ("memory_service", "skills_runtime"):
            if adapter in config["csp"] and config["csp"][adapter]["transport_name"] is None:
                config["csp"][adapter].pop("transport_name")
        return config
