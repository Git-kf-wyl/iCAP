"""Durable synchronous delegation through the native factory and executor."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from openjiuwen.core.runner import Runner
from openjiuwen.core.runner.callback import AbortError
from openjiuwen.core.session import InteractiveInput
from openjiuwen.core.single_agent.rail.base import (
    AgentCallbackContext,
    AgentRail,
    bind_usage_delegation,
    build_usage_delegation_attribution,
    reset_usage_delegation,
)
from openjiuwen.harness.kv_cache.kv_cache_subagent_lifecycle import is_sticky_subagent_type
from openjiuwen.harness.rails.interrupt.interrupt_base import BaseInterruptRail
from openjiuwen.harness.subagent_lifecycle import (
    cleanup_subagent_task_resources,
    prepare_subagent_task_resources,
)
from openjiuwen.harness.tools.base_tool import ToolOutput
from openjiuwen.harness.tools.subagent.task_tool import resolve_subagent_task_timeout_s

from meta_agent.checkpoint.native import NATIVE_RUN
from meta_agent.errors import RecoveryConflict

_DELEGATIONS = "meta_durable_subagent_delegations"


class AsyncChildBoundaryRail(AgentRail):  # type: ignore[misc]
    """Detect interactions that the native asynchronous stream cannot resume."""

    async def after_invoke(self, ctx: AgentCallbackContext) -> None:
        run = NATIVE_RUN.get()
        if run is None or ctx.exception is not None:
            return
        result = getattr(ctx.inputs, "result", None)
        if result is None or (
            isinstance(result, dict) and result.get("result_type") == "interrupt"
        ):
            run.interrupted_subagents.add(ctx.session.get_session_id())


class DurableSubagentRail(BaseInterruptRail):  # type: ignore[misc]
    """Return child interruptions to the native parent interruption handler.

    The stock TaskTool consumes a child stream and loses interaction chunks.
    This rail substitutes a native invoke result using the public skip contract;
    the native parent still schedules tools and resumes interrupted calls.
    """

    priority = -200

    def __init__(self, parent: Any) -> None:
        super().__init__(tool_names=("task_tool",))
        self.parent = parent

    async def resolve_interrupt(
        self,
        ctx: AgentCallbackContext,
        tool_call: Any,
        user_input: Any,
        auto_confirm_config: Any,
    ) -> Any:
        # Earlier permission/budget rails may already have denied this call.
        if ctx.inputs.tool_msg is not None or ctx.has_force_finish_request:
            return self.approve()
        try:
            result = await self._delegate(ctx, tool_call)
        except AbortError:
            raise
        except Exception as error:
            # Ordinary callback errors are logged and ignored by the kernel.
            # Propagate instead of falling through to a second TaskTool call.
            raise AbortError(
                reason="Durable child delegation failed", cause=error, is_error=True
            ) from error
        return self.reject(tool_result=result)

    async def _delegate(self, ctx: AgentCallbackContext, tool_call: Any) -> Any:
        args = ctx.inputs.tool_args
        if isinstance(args, str):
            args = json.loads(args)
        if not isinstance(args, dict):
            raise RecoveryConflict("META_SUBAGENT_INPUT", "Child arguments must be an object")
        name, task = args.get("subagent_type"), args.get("task_description")
        if not isinstance(name, str) or not name.strip() or not isinstance(task, str) or not task:
            raise RecoveryConflict("META_SUBAGENT_INPUT", "Child type and task are required")
        name = name.strip()
        call_id = str(tool_call.id or "")
        if not call_id or ctx.session is None:
            raise RecoveryConflict("META_SUBAGENT_INPUT", "Child delegation requires a session")
        # The native interruption handler supplies this object on outer replay.
        # JSON model arguments cannot fabricate an InteractiveInput instance.
        resume = args.get("query")
        if resume is not None and not isinstance(resume, InteractiveInput):
            raise RecoveryConflict("META_SUBAGENT_INPUT", "Child resume requires native input")
        if args.get("resume_task_id"):
            raise RecoveryConflict("META_SUBAGENT_INPUT", "Resume through the pending interaction")
        records = {item["call_id"]: item for item in ctx.session.get_state(_DELEGATIONS) or []}
        record = records.get(call_id)
        parent_id = ctx.session.get_session_id()
        if record is None:
            if resume is not None:
                raise RecoveryConflict("META_SUBAGENT_STATE", "Missing child delegation snapshot")
            child_id = f"{parent_id}_sub_{name}"
            if not is_sticky_subagent_type(name):
                child_id += f"_{uuid4().hex[:8]}"
            record = {"call_id": call_id, "session_id": child_id, "type": name, "task": task}
        elif record["type"] != name or record["task"] != task:
            raise RecoveryConflict("META_SUBAGENT_STATE", "Child delegation changed during resume")
        child_id = record["session_id"]
        child = self.parent.create_subagent(name, child_id)
        token = bind_usage_delegation(
            build_usage_delegation_attribution(
                agent_id=child.card.id,
                parent_session_id=parent_id,
                delegation_id=child_id,
            )
        )
        try:
            await prepare_subagent_task_resources(child)
            async with asyncio.timeout(resolve_subagent_task_timeout_s()):
                result = await Runner.run_agent(
                    child,
                    {"query": resume if resume is not None else task, "conversation_id": child_id},
                    session=child_id,
                )
        finally:
            try:
                await cleanup_subagent_task_resources(child)
            finally:
                reset_usage_delegation(token)
        if result.get("result_type") == "interrupt":
            # Publish only a successful pause, so a failed initial lookup can
            # be corrected even when the provider reuses its tool-call ID.
            records = {item["call_id"]: item for item in ctx.session.get_state(_DELEGATIONS) or []}
            records[call_id] = record
            ctx.session.update_state({_DELEGATIONS: list(records.values())})
            return result
        # Keep only pending calls: providers may reuse a tool-call ID later.
        # Re-read after awaiting the child so parallel siblings remain intact.
        records = {item["call_id"]: item for item in ctx.session.get_state(_DELEGATIONS) or []}
        records.pop(call_id, None)
        # Native state recursively merges dicts; a list also replaces removals.
        ctx.session.update_state({_DELEGATIONS: list(records.values())})
        if result.get("result_type") == "error":
            raise RecoveryConflict(
                "META_SUBAGENT_RESULT", str(result.get("output", "Child failed"))
            )
        return ToolOutput(
            success=True,
            data={"output": result.get("output", ""), "agent_id": child.card.id},
            error=None,
        )
