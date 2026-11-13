"""Small platform contracts; transport and permission execution stay native."""

from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EndpointConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str
    api_key: str = Field(default="", repr=False)

    @field_validator("endpoint")
    @classmethod
    def http_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("A HTTP(S) endpoint is required")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Endpoint credentials/query/fragment belong in explicit configuration")
        return value.rstrip("/")


class InferScheduleConfig(EndpointConfig):
    timeout: float = Field(default=60, gt=0)


class McpGatewayConfig(EndpointConfig):
    """Streamable HTTP; X-Meta-Mcp-Server selects a logical upstream."""


class OpsConfig(EndpointConfig):
    report_interval_s: float = Field(default=60, gt=0)
    timeout_s: float = Field(default=5, gt=0)


class ServiceConnection(BaseModel):
    """Existing HTTP demo contract or a host-owned SDK/gRPC binding."""

    model_config = ConfigDict(extra="forbid")
    endpoint: str | None = None
    transport_name: str | None = Field(default=None, min_length=1)
    api_key: str = Field(default="", repr=False)
    timeout_s: float = Field(default=10, gt=0)

    @model_validator(mode="after")
    def connection(self) -> Self:
        if (self.endpoint is None) == (self.transport_name is None):
            raise ValueError("Select endpoint or transport_name")
        if self.endpoint is not None:
            self.endpoint = EndpointConfig.http_endpoint(self.endpoint)
        elif self.api_key or not (self.transport_name or "").strip():
            raise ValueError("Host transport owns credentials and needs a nonblank name")
        return self


class MemoryServiceConfig(ServiceConnection):
    """A host-selected user and namespace, shared across that runtime's sessions."""

    scope_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1)
    threshold: float = Field(default=0.3, ge=0, le=1)


class SkillsRuntimeConfig(ServiceConnection):
    """Explicit remote Skill names mapped to immutable service versions."""

    skills: dict[str, str] = Field(min_length=1)

    @field_validator("skills")
    @classmethod
    def explicit_versions(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not name.strip() or not version.strip() for name, version in value.items()):
            raise ValueError("Remote Skills require nonempty names and explicit versions")
        return value


class ContextServiceConfig(BaseModel):
    """Host supplies a native ContextEngine final-window adapter."""

    model_config = ConfigDict(extra="forbid")
    adapter_name: str = Field(min_length=1)


class PackageServicesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_service: MemoryServiceConfig | None = None
    skills_runtime: SkillsRuntimeConfig | None = None
    context_service: ContextServiceConfig | None = None


class CspConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    infer_schedule: InferScheduleConfig | None = None
    mcp_gateway: McpGatewayConfig | None = None
    ops: OpsConfig | None = None
    memory_service: MemoryServiceConfig | None = None
    skills_runtime: SkillsRuntimeConfig | None = None
    context_service: ContextServiceConfig | None = None

    @model_validator(mode="after")
    def configured(self) -> Self:
        if self.enabled != bool(
            self.infer_schedule
            or self.mcp_gateway
            or self.ops
            or self.memory_service
            or self.skills_runtime
            or self.context_service
        ):
            raise ValueError("CSP enabled requires at least one adapter; disabled requires none")
        return self


class ToolPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    default: Literal["allow", "ask", "deny"] = "deny"
    tools: dict[str, Literal["allow", "ask", "deny"]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def configured(self) -> Self:
        if not self.enabled and self.tools:
            raise ValueError("Tool policies require permissions.enabled=true")
        return self

    def native_config(self) -> dict[str, object]:
        return {"enabled": True, "defaults": {"*": self.default}, "tools": self.tools}
