"""Per-runtime service tool bindings for native Workflow components."""

from typing import Any
from uuid import uuid4

from openjiuwen.core.runner import Runner

from meta_agent.identity import ExecutionIdentity
from meta_agent.spec.platform import PackageServicesConfig
from meta_agent_adapter.service_bindings import validate_service_bindings
from meta_agent_adapter.services import MemoryServiceAdapter, SkillsRuntimeAdapter, service_tools


class WorkflowServices:
    def __init__(self, config: PackageServicesConfig, product_id: str, agent_id: str) -> None:
        validate_service_bindings(config)
        self.identity = ExecutionIdentity(product_id, agent_id, uuid4().hex, "boot", "boot")
        self.memory = MemoryServiceAdapter(config.memory_service) if config.memory_service else None
        self.skills = SkillsRuntimeAdapter(config.skills_runtime) if config.skills_runtime else None
        self.tools: dict[str, Any] = {
            tool.card.name: tool
            for tool in service_tools(lambda: self.identity, self.memory, self.skills)
        }

    def register(self) -> None:
        for tool in self.tools.values():
            Runner.resource_mgr.add_tool(tool)

    async def close(self) -> None:
        for tool in self.tools.values():
            Runner.resource_mgr.remove_tool(tool.card.id)
        self.tools.clear()
        if self.memory is not None:
            await self.memory.aclose()
        if self.skills is not None:
            await self.skills.aclose()
