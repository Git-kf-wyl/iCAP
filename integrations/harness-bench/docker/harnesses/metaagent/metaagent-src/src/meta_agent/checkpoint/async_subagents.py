"""Checkpoint completed native background turns without replacing their workers."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openjiuwen.core.runner.callback import AbortError
from openjiuwen.core.single_agent.rail.base import AgentCallbackContext
from openjiuwen.harness.rails.interrupt.interrupt_base import BaseInterruptRail
from openjiuwen.harness.subagent_runtime.config import WAIT_TIMEOUT_MS_DEFAULT
from openjiuwen.harness.subagent_runtime.persistence import read_subagent_bucket
from openjiuwen.harness.tools.base_tool import ToolOutput
from openjiuwen.harness.tools.subagent._control_registry import (
    get_subagent_control,
    release_subagent_control,
)
from openjiuwen.harness.tools.subagent.task_tool import resolve_subagent_task_timeout_s

from meta_agent.checkpoint.native import current_native_run
from meta_agent.errors import RecoveryConflict


async def checkpoint_async_children(parent: Any, session: Any) -> None:
    """Finish the native queue before the parent publishes a complete checkpoint.

    Native persistence retains child conversations and results, but not worker
    queues. Wait for each child's latest queued task, then release its worker.
    A crash before this boundary remains an unfinished execution.
    """
    if not parent.deep_config.enable_subagent_runtime:
        return
    control = get_subagent_control(parent, session)
    targets = {item.subagent_id: item.current_task_id for item in control.list_live()}
    try:
        async with asyncio.timeout(resolve_subagent_task_timeout_s()):
            pending = dict(targets)
            while pending:
                await control.wait(list(pending))
                control.flush()
                turns = read_subagent_bucket(session)["turns"]
                pending = {
                    sid: task_id
                    for sid, task_id in pending.items()
                    if not control.get_status(sid).is_final()
                    or (
                        task_id is not None
                        and not any(turn.get("task_id") == task_id for turn in turns.get(sid, []))
                    )
                }
                if any(control.get_status(sid).kind.value == "errored" for sid in pending):
                    # Native error handling can retain the prior successful
                    # task ID instead of archiving this failed follow-up.
                    raise RecoveryConflict(
                        "META_SUBAGENT_RECOVERY_BOUNDARY",
                        "Background child failed before committing its latest queued turn",
                    )
                if pending:
                    # wait() may observe a previous turn's final status while
                    # native cleanup precedes the next queued turn.
                    await asyncio.sleep(0.01)
        control.flush()
        runtime_ids = set(read_subagent_bucket(session)["records"]) | set(targets)
        run = current_native_run()
        if runtime_ids & run.interrupted_subagents:
            raise RecoveryConflict(
                "META_SUBAGENT_RECOVERY_BOUNDARY",
                "Pending background child interactions require synchronous task_tool delegation",
            )
        if any(sid not in run.subagent_states for sid in runtime_ids):
            raise RecoveryConflict(
                "META_ASYNC_SUBAGENT_STATE", "Background child did not commit native state"
            )
    except TimeoutError as error:
        raise RecoveryConflict(
            "META_ASYNC_SUBAGENT_PENDING", "Background children did not finish before checkpoint"
        ) from error
    finally:
        # Public native teardown persists its records and commits the parent
        # state after all queued work has settled (or closes an aborted run).
        await release_subagent_control(parent, session.get_session_id())


class DurableAsyncSubagentRail(BaseInterruptRail):  # type: ignore[misc]
    """Return saved native turn results when a cold parent waits on a child."""

    priority = -200

    def __init__(self, parent: Any) -> None:
        super().__init__(tool_names=("subagent_wait",))
        self.parent = parent

    async def resolve_interrupt(
        self,
        ctx: AgentCallbackContext,
        tool_call: Any,
        user_input: Any,
        auto_confirm_config: Any,
    ) -> Any:
        if ctx.inputs.tool_msg is not None or ctx.has_force_finish_request:
            return self.approve()
        try:
            output = await self._wait(ctx)
        except AbortError:
            raise
        except Exception as error:
            raise AbortError(
                reason="Durable background child wait failed", cause=error, is_error=True
            ) from error
        return self.reject(tool_result=output)

    async def _wait(self, ctx: AgentCallbackContext) -> Any:
        args = ctx.inputs.tool_args
        if isinstance(args, str):
            args = json.loads(args)
        if not isinstance(args, dict) or ctx.session is None:
            raise RecoveryConflict(
                "META_SUBAGENT_INPUT", "Child wait requires arguments and session"
            )
        raw_ids = args.get("subagent_ids", args.get("subagent_id"))
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]
        ids = (
            [item.strip() for item in raw_ids if isinstance(item, str) and item.strip()]
            if isinstance(raw_ids, list)
            else []
        )
        timeout_ms = args.get("timeout_ms", WAIT_TIMEOUT_MS_DEFAULT)
        if not ids or not isinstance(timeout_ms, int):
            raise RecoveryConflict(
                "META_SUBAGENT_INPUT", "Child IDs and an integer timeout are required"
            )
        control = get_subagent_control(self.parent, ctx.session)
        live_ids = {item.subagent_id for item in control.list_live()}
        result = await control.wait(ids, timeout_ms=timeout_ms)
        control.flush()
        turns = read_subagent_bucket(ctx.session)["turns"]
        statuses = {sid: status.kind.value for sid, status in result.statuses.items()}
        results, output_files = dict(result.results), dict(result.output_files)
        for sid in ids:
            if sid in live_ids or not turns.get(sid):
                continue
            latest = max(turns[sid], key=lambda turn: turn.get("seq", 0))
            outcome = latest.get("closed_reason")
            statuses[sid] = {
                "completed": "completed",
                "failed": "errored",
                "cancelled": "interrupted",
            }.get(outcome, "closed")
            if outcome == "completed":
                if latest.get("answer") is not None:
                    results[sid] = latest["answer"]
                if latest.get("output_file"):
                    output_files[sid] = latest["output_file"]
        for sid in ids:
            await control.emit_status_update(sid, session=ctx.session)
        return ToolOutput(
            success=True,
            data={
                "statuses": statuses,
                "results": results,
                "output_files": output_files,
                "timed_out": result.timed_out,
            },
        )
