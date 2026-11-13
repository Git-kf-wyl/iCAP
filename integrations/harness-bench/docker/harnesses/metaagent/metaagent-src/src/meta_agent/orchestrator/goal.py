"""A single consumer of the native goal loop; the kernel owns continuation."""

import asyncio
from typing import Any
from uuid import uuid4

from openjiuwen.core.session import InteractiveInput
from openjiuwen.harness.schema.interaction import SendInputRequest

from meta_agent.checkpoint.native import NATIVE_RUN
from meta_agent.errors import MetaAgentError
from meta_agent.spec.meta_agent_spec import BudgetConfig


class GoalRun:
    def __init__(self, agent: Any, budget: BudgetConfig) -> None:
        self.agent, self.budget = agent, budget
        self.session: Any = None
        self.record: Any = None

    async def invoke(self, query: Any, session: Any, emit_delta: Any = None) -> dict[str, Any]:
        if self.session is None:
            self.session = session
            await session.pre_run(inputs={})
            await self.agent.ensure_initialized()
            await self.agent.start(session=session)
        manager = self.agent.goal_manager
        resuming = isinstance(query, InteractiveInput)
        if resuming:
            self.record = await manager.get()
            if self.record is None or self.record.status.value != "paused":
                raise MetaAgentError("META_GOAL_RECOVERY_STATE", "Missing paused native goal")
        else:
            self.record = await manager.set(
                query,
                overwrite_confirmed=True,
                max_attempts=self.budget.max_attempts,
                token_budget=self.budget.token_budget,
            )
        stream = await self.agent.attach_output()
        if stream is None:
            raise MetaAgentError("META_GOAL_CONSUMER", "Goal output already has a consumer")
        terminal: dict[str, Any] | None = None
        interruption: Any = None
        try:
            if resuming:
                record = await manager.get()
                await self.agent.send_input(
                    SendInputRequest(
                        request_id=uuid4().hex,
                        inputs={
                            "query": query,
                            "run": {
                                "kind": "goal",
                                "context": {
                                    "goal_id": record.goal_id,
                                    "revision": record.revision,
                                    "session_id": record.session_id,
                                },
                            },
                        },
                    )
                )
            async for chunk in stream:
                if chunk.type == "__interaction__":
                    interruption = chunk
                    await manager.pause()
                if chunk.type == "llm_output" and emit_delta is not None:
                    content = chunk.payload.get("content")
                    if isinstance(content, str) and content:
                        await emit_delta(content)
                elif chunk.type == "answer":
                    terminal = dict(chunk.payload)
        except asyncio.CancelledError:
            await self.agent.stop()
            raise
        finally:
            await stream.close(abort_active_round=False)
            self.record = await manager.get()
        if NATIVE_RUN.get() is not None:
            # The interaction loop owns a long-lived Session. Capture its final
            # goal/rail state before the bridge commits the child result, while
            # the execution lease is still held.
            await self.session.commit()
        if interruption is not None:
            payload = interruption.payload
            interrupt_id = payload.get("id") if isinstance(payload, dict) else payload.id
            return {
                "result_type": "interrupt",
                "interrupt_ids": [interrupt_id],
                "state": [interruption],
            }
        if self.record.status.value != "completed":
            evidence = self.record.last_assessment.evidence if self.record.last_assessment else ""
            exhausted = evidence.startswith(("max_attempts_exhausted:", "token_budget_exhausted:"))
            return {
                "result_type": "error",
                "output": str((terminal or {}).get("output", "")),
                "error": {
                    "code": "META_BUDGET_EXHAUSTED" if exhausted else "META_GOAL_BLOCKED",
                    "message": evidence or "The goal did not complete",
                },
            }
        if terminal is None:
            raise MetaAgentError("META_KERNEL_PROTOCOL", "Goal ended without an answer")
        return terminal

    async def close_session(self, *, persist: bool = True) -> None:
        if self.session is not None:
            if persist:
                await self.session.post_run()
            self.session = None
