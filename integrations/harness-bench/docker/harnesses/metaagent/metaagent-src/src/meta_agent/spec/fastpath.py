"""Serializable M3 plugin and routing contracts; no implicit executable expressions."""

from __future__ import annotations

import json
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SkillRoute(StrictModel):
    skill: str = Field(min_length=1)
    plugin: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    exact: list[str] = Field(default_factory=list)
    prefixes: list[str] = Field(default_factory=list)


class AdaptiveConfig(StrictModel):
    enabled: bool = False
    window_size: int = Field(default=20, ge=1)
    min_success_rate: float = Field(default=0.7, ge=0, le=1)
    threshold_step: float = Field(default=0.05, gt=0, le=1)
    disable_after_windows: int = Field(default=3, ge=1)


class RouterConfig(StrictModel):
    cache_ttl_s: float = Field(default=600.0, ge=0)
    cache_max_entries: int = Field(default=256, ge=0)
    embedding_provider: str | None = None
    classifier_provider: str | None = None
    skill_routes: list[SkillRoute] = Field(default_factory=list)
    adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)


class FastPathConfig(StrictModel):
    enabled: bool = False
    plugins_dir: str | None = None
    plugins: list[str] = Field(default_factory=list)
    max_nesting_depth: int = Field(default=5, ge=1, le=20)
    router: RouterConfig = Field(default_factory=RouterConfig)

    @model_validator(mode="after")
    def require_directory(self) -> Self:
        if self.enabled and (not self.plugins_dir or not self.plugins_dir.strip()):
            raise ValueError("Enabled fastpath requires plugins_dir")
        if not self.enabled and (self.plugins_dir or self.plugins or self.router != RouterConfig()):
            raise ValueError("Disabled fastpath cannot carry active settings")
        if len(self.plugins) != len(set(self.plugins)):
            raise ValueError("Duplicate plugin selection")
        return self


class IntentMetadata(StrictModel):
    description: str = Field(min_length=1)
    examples: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    when: str | None = None
    threshold: float = Field(default=0.8, ge=0, le=1)
    priority: int = 0
    tags: list[str] = Field(default_factory=list)

    @field_validator("rules")
    @classmethod
    def validate_patterns(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            if not pattern or len(pattern) > 512:
                raise ValueError("Rules must contain 1..512 characters")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError("Invalid route regular expression") from exc
        return patterns


class WorkflowPluginManifest(StrictModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    packageType: Literal["plugin"] = "plugin"
    entry: str = Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*\.py:[a-zA-Z_][a-zA-Z0-9_]*$")
    intent: IntentMetadata
    fallback_to_harness: bool = True
    fallback_whitelist: list[str] = Field(default_factory=list)
    min_meta_agent: str | None = None
    effects: list[str] = Field(default_factory=list)

    @field_validator("effects")
    @classmethod
    def validate_effects(cls, effects: list[str]) -> list[str]:
        if len(effects) != len(set(effects)) or any(
            not re.fullmatch(r"[a-z][a-z0-9_.-]{0,127}", name) for name in effects
        ):
            raise ValueError("Effect bindings need unique capability names")
        return effects


class PluginError(StrictModel):
    code: str = Field(min_length=1)
    message: str = "Plugin could not complete the request."
    exception_type: str = "PluginFailure"


class PluginOutcome(StrictModel):
    status: Literal["success", "failed"]
    output: str = ""
    data: JsonValue = None
    error: PluginError | None = None
    partial: dict[str, object] = Field(default_factory=dict)
    completed_operations: list[str] = Field(default_factory=list)

    @field_validator("data")
    @classmethod
    def finite_json_data(cls, value: JsonValue) -> JsonValue:
        """Keep business values serializable across streams, workers and recovery."""
        json.dumps(value, allow_nan=False)
        return value

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if (self.status == "failed") != (self.error is not None):
            raise ValueError("Only failed outcomes have an error")
        return self
