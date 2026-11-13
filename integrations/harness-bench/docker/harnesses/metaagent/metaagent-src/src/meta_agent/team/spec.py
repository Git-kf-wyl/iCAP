"""Configuration for the first local MetaAgentTeam integration."""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from openjiuwen.extensions.observability.config import ObservabilityConfig
from pydantic import Field, field_validator, model_validator

from meta_agent.spec.meta_agent_spec import StrictConfig, _reject_dropped_fields


class MetaAgentTeamSpec(StrictConfig):
    team_name: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    members: dict[str, str]
    leader: str = "leader"
    state_dir: str
    language: Literal["en", "cn"] = "en"
    human_members: dict[str, str] = Field(default_factory=dict)
    task_management: bool = False
    dispatch_mode: Literal["autonomous", "scheduled"] = "autonomous"
    observability: ObservabilityConfig | None = Field(default=None, repr=False)

    @field_validator("observability", mode="before")
    @classmethod
    def validate_observability(cls, value: Any) -> ObservabilityConfig | None:
        if value is None:
            return None
        parsed = ObservabilityConfig.model_validate(value)
        _reject_dropped_fields(value, parsed, "meta_team.observability")
        return parsed

    @classmethod
    def from_package(cls, root: str | Path, *, env: Mapping[str, str] | None = None) -> Self:
        from meta_agent.boot.boot_loader import _expand_env, _read_yaml

        root = Path(root).resolve()
        data = _expand_env(
            _read_yaml((root / "meta_team.yaml").read_text("utf-8")),
            os.environ if env is None else env,
        )
        return cls.model_validate(data["meta_team"]).resolve(root)

    @model_validator(mode="after")
    def validate_members(self) -> Self:
        if self.leader not in self.members:
            raise ValueError("leader must name a member package")
        if self.members.keys() & self.human_members.keys():
            raise ValueError("Human and agent member names must be distinct")
        for name, display_name in self.human_members.items():
            if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or name in {"user", "human-agent"}:
                raise ValueError("Human member names must be explicit lowercase slugs")
            if not display_name.strip():
                raise ValueError("Human members require a display name")
        for name, package in self.members.items():
            if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not package.strip():
                raise ValueError("member names must use lowercase letters, digits or hyphens")
            if name == "user":
                raise ValueError("member name is reserved")
        if not self.state_dir.strip():
            raise ValueError("state_dir must not be blank")
        return self

    def resolve(self, root: Path) -> Self:
        def path(value: str) -> str:
            return str((root / value).resolve())

        return self.model_copy(
            update={
                "members": {name: path(value) for name, value in self.members.items()},
                "state_dir": path(self.state_dir),
            }
        )
