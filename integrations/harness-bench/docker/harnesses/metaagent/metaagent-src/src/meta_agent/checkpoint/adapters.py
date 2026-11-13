"""Opt-in native boundaries. Hosts bind a stable semantic key, never the LLM.

These helpers route only their own calls through L3. Arbitrary tools, HTTP/RPC
clients, skill scripts and subagents are not automatically intercepted.
"""

from collections.abc import AsyncIterator
from typing import Any

from openjiuwen.core.foundation.tool import Tool, ToolCard
from openjiuwen.core.runner.callback import AbortError
from openjiuwen.core.single_agent.rail.base import AgentCallbackContext, AgentRail, ToolCallInputs
from openjiuwen.core.workflow import WorkflowComponent

from meta_agent.checkpoint.executor import EffectAdapter, current_effects
from meta_agent.checkpoint.models import identifier
from meta_agent.errors import RecoveryConflict


class ReadOnlyMcpRail(AgentRail):  # type: ignore[misc]
    """Check every native MCP invocation against the host's read-only contract.

    MCP discovery and refresh happen inside the native ability manager, after
    static tool validation. Native MCP names are qualified as mcp_<server>_<tool>.
    User approval cannot turn an undeclared remote operation into a safe read.
    """

    priority = 100

    def __init__(self, read_only_tools: tuple[str, ...]) -> None:
        self.allowed = frozenset(read_only_tools)

    async def before_tool_call(self, ctx: AgentCallbackContext) -> None:
        if isinstance(ctx.inputs, ToolCallInputs):
            name = ctx.inputs.tool_name
            if name.startswith("mcp_") and name not in self.allowed:
                # Ordinary callback exceptions are logged and ignored by the
                # native callback framework. Its public AbortError is the
                # propagation contract that stops the actual tool invocation.
                raise AbortError(
                    reason="MCP operation is not declared read-only",
                    cause=RecoveryConflict(
                        "META_MCP_READ_ONLY_REQUIRED",
                        "Recovery permits only host-declared read-only MCP tools",
                    ),
                    is_error=True,
                )


class EffectWorkflowComponent(WorkflowComponent):  # type: ignore[misc]
    def __init__(self, adapter: EffectAdapter, logical_key: str) -> None:
        super().__init__()
        self.adapter, self.logical_key = adapter, identifier(logical_key)

    async def invoke(self, inputs: dict[str, Any], session: Any, context: Any) -> dict[str, Any]:
        result = await current_effects().execute(self.logical_key, self.adapter, inputs)
        return {"result": result}


class BoundEffectTool(Tool):  # type: ignore[misc]
    """One host-approved logical operation per durable execution.

    Repeated model calls to this tool refer to the same operation; argument
    changes fail closed. Distinct effects need distinct host-bound keys/tools.
    Standalone hosts must finish DurableExecution before publishing an answer;
    MetaBaseAgent with LocalRecovery performs that gate itself. Native agents may
    convert tool exceptions into model observations.
    """

    def __init__(self, card: ToolCard, adapter: EffectAdapter, logical_key: str) -> None:
        super().__init__(card)
        self.adapter, self.logical_key = adapter, identifier(logical_key)

    async def invoke(self, inputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return await current_effects().execute(self.logical_key, self.adapter, inputs)

    async def stream(self, inputs: dict[str, Any], **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        # An external effect is published only after its result commit.
        yield await self.invoke(inputs, **kwargs)
