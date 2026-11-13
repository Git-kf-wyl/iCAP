"""Include native child calls in the owning request's usage."""

from typing import Any

from openjiuwen.core.foundation.llm import AssistantMessage
from openjiuwen.core.single_agent.rail.base import AgentRail, ModelCallInputs

from meta_agent.trace.rail import TraceRail


class SubagentUsageRail(AgentRail):  # type: ignore[misc]
    def __init__(self, parent: Any, trace: TraceRail) -> None:
        self.parent, self.trace = parent, trace
        self.owner: TraceRail | None = None
        self.goal: tuple[str, int] | None = None

    def fork_for_agent(self) -> "SubagentUsageRail":
        return SubagentUsageRail(self.parent, self.trace)

    async def before_invoke(self, ctx: Any) -> None:
        self.owner = TraceRail(self.trace.sink, self.trace.identity)
        self.owner.gateway_prefixes = self.trace.gateway_prefixes
        self.trace.subagent_calls += 1
        manager = self.parent.goal_manager
        record = await manager.get() if manager is not None else None
        self.goal = (record.goal_id, record.revision) if record is not None else None

    def _trace(self) -> TraceRail:
        if (
            self.owner is not None
            and self.owner.identity.execution_id != self.trace.identity.execution_id
        ):
            # A background child may outlive the request that launched it.
            # Continue its trace without charging the next parent execution.
            return self.owner
        return self.trace

    async def before_model_call(self, ctx: Any) -> None:
        await self._trace().before_model_call(ctx)

    async def on_model_exception(self, ctx: Any) -> None:
        await self._trace().on_model_exception(ctx)

    async def before_tool_call(self, ctx: Any) -> None:
        await self._trace().before_tool_call(ctx)

    async def after_tool_call(self, ctx: Any) -> None:
        await self._trace().after_tool_call(ctx)

    async def after_model_call(self, ctx: Any) -> None:
        await self._trace().after_model_call(ctx)
        manager = self.parent.goal_manager
        if manager is None or ctx.exception is not None:
            return
        if not isinstance(ctx.inputs, ModelCallInputs) or not isinstance(
            ctx.inputs.response, AssistantMessage
        ):
            return
        usage = ctx.inputs.response.usage_metadata
        if usage is not None and self.goal is not None:
            await manager.accumulate_usage(
                goal_id=self.goal[0],
                revision=self.goal[1],
                input_tokens=max(0, usage.input_tokens),
                output_tokens=max(0, usage.output_tokens),
            )
