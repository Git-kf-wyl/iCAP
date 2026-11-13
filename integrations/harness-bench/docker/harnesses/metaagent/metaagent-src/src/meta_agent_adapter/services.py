"""Optional service RPCs mounted as native tools, with host-owned scope/version.

Each operation is awaited once. Storage, extraction and Skill execution belong to
the service; this module adds no store, automatic turn capture or retry worker.
"""

from collections.abc import Callable
from typing import Any, Literal

import httpx
from openjiuwen.core.foundation.tool import ToolCard
from openjiuwen.core.foundation.tool.function.function import LocalFunction
from pydantic import BaseModel, Field, ValidationError

from meta_agent.errors import MetaAgentError
from meta_agent.identity import ExecutionIdentity
from meta_agent.spec.platform import MemoryServiceConfig, ServiceConnection, SkillsRuntimeConfig
from meta_agent_adapter.service_bindings import ServiceRequest, get_service_transport


class MemoryRecord(BaseModel):
    content: str
    score: float = Field(ge=0, le=1)


class ResolvedSkill(BaseModel):
    name: str
    version: str
    description: str
    instructions: str


class _Service:
    def __init__(self, config: ServiceConnection, service: Literal["memory", "skills"]) -> None:
        self._service = service
        self._timeout = config.timeout_s
        self._transport = (
            get_service_transport(config.transport_name) if config.transport_name else None
        )
        self._client = (
            httpx.AsyncClient(
                base_url=config.endpoint + "/",
                headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else {},
                timeout=config.timeout_s,
            )
            if config.endpoint is not None
            else None
        )

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if self._transport is not None:
                result = await self._transport.invoke(
                    ServiceRequest(self._service, path, payload, self._timeout)
                )
            else:
                assert self._client is not None
                response = await self._client.post(path, json=payload)
                response.raise_for_status()
                result = response.json()
            if not isinstance(result, dict):
                raise ValueError("Expected an object")
            return result
        except httpx.TimeoutException:
            raise MetaAgentError("META_SERVICE_TIMEOUT", "Service request timed out") from None
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            code = "AUTH" if status in {401, 403} else "HTTP"
            raise MetaAgentError(
                f"META_SERVICE_{code}", f"Service returned HTTP {status}"
            ) from None
        except (httpx.RequestError, ValueError):
            raise MetaAgentError("META_SERVICE_RESPONSE", "Service request failed") from None

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()


class MemoryServiceAdapter(_Service):
    def __init__(self, config: MemoryServiceConfig) -> None:
        super().__init__(config, "memory")
        self.config = config.model_copy(deep=True)

    def _scope(self, identity: ExecutionIdentity) -> dict[str, Any]:
        return dict(identity.as_dict(), scope_id=self.config.scope_id, user_id=self.config.user_id)

    async def retrieve(self, query: str, identity: ExecutionIdentity) -> list[dict[str, Any]]:
        result = await self._post(
            "retrieve",
            dict(
                self._scope(identity),
                query=query,
                top_k=self.config.top_k,
                threshold=self.config.threshold,
            ),
        )
        try:
            records = result["memories"]
            if not isinstance(records, list):
                raise ValueError("Expected memories")
            return [MemoryRecord.model_validate(item).model_dump() for item in records]
        except (KeyError, ValueError, ValidationError):
            raise MetaAgentError(
                "META_MEMORY_RESPONSE", "Invalid memory retrieval result"
            ) from None

    async def write(self, content: str, identity: ExecutionIdentity) -> dict[str, bool]:
        result = await self._post(
            "write",
            dict(self._scope(identity), messages=[{"role": "user", "content": content}]),
        )
        if result.get("accepted") is not True:
            raise MetaAgentError(
                "META_MEMORY_WRITE", "Memory service did not acknowledge the write"
            )
        return {"accepted": True}


class SkillsRuntimeAdapter(_Service):
    def __init__(self, config: SkillsRuntimeConfig) -> None:
        super().__init__(config, "skills")
        self.config = config.model_copy(deep=True)

    def _selection(self, name: str, identity: ExecutionIdentity) -> dict[str, Any]:
        if name not in self.config.skills:
            raise MetaAgentError("META_SKILL_NOT_CONFIGURED", "Remote Skill is not configured")
        return dict(identity.as_dict(), name=name, version=self.config.skills[name])

    def _check_version(self, name: str, result: dict[str, Any]) -> None:
        if result.get("name") != name or result.get("version") != self.config.skills[name]:
            raise MetaAgentError("META_SKILL_VERSION", "Service returned a different Skill version")

    async def resolve_skill(self, name: str, identity: ExecutionIdentity) -> dict[str, Any]:
        result = await self._post("resolve", self._selection(name, identity))
        self._check_version(name, result)
        try:
            return ResolvedSkill.model_validate(result).model_dump()
        except ValidationError:
            raise MetaAgentError("META_SKILL_RESPONSE", "Invalid resolved Skill") from None

    async def execute(
        self, name: str, args: dict[str, Any], identity: ExecutionIdentity
    ) -> dict[str, Any]:
        result = await self._post("execute", dict(self._selection(name, identity), args=args))
        self._check_version(name, result)
        if "output" not in result:
            raise MetaAgentError("META_SKILL_RESPONSE", "Skill execution returned no output")
        return {"name": name, "version": self.config.skills[name], "output": result["output"]}


def service_tools(
    identity: Callable[[], ExecutionIdentity],
    memory: MemoryServiceAdapter | None,
    skills: SkillsRuntimeAdapter | None,
) -> list[Any]:
    """Use native registration, trace callbacks and PermissionInterruptRail unchanged."""
    result = []

    def tool(name: str, description: str, properties: dict[str, Any], function: Any) -> None:
        card = ToolCard(
            id=f"{identity().child_session_id}-{name}",
            name=name,
            description=description,
            input_params={
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        )
        result.append(LocalFunction(card=card, func=function))

    if memory is not None:

        async def retrieve(query: str) -> list[dict[str, Any]]:
            return await memory.retrieve(query, identity())

        async def write(content: str) -> dict[str, bool]:
            return await memory.write(content, identity())

        tool(
            "memory_retrieve",
            "Recall saved facts/experience for this host-configured user.",
            {"query": {"type": "string"}},
            retrieve,
        )
        tool(
            "memory_write",
            "Save a fact or lesson for later sessions. Await storage acknowledgement.",
            {"content": {"type": "string"}},
            write,
        )
    if skills is not None:

        async def resolve(name: str) -> dict[str, Any]:
            return await skills.resolve_skill(name, identity())

        async def execute(name: str, args: dict[str, Any]) -> dict[str, Any]:
            return await skills.execute(name, args, identity())

        names = {"type": "string", "enum": sorted(skills.config.skills)}
        tool(
            "remote_skill_resolve",
            "Read instructions for a host-selected remote Skill version.",
            {"name": names},
            resolve,
        )
        tool(
            "remote_skill_execute",
            "Execute a remote Skill using its resolved instructions.",
            {"name": names, "args": {"type": "object"}},
            execute,
        )
    return result
