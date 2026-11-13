"""Native goal assessment with configured strategies and metered assessor calls."""

from typing import Any

from openjiuwen.core.session import InteractiveInput
from openjiuwen.core.single_agent.rail.base import AgentCallbackContext, ModelCallInputs
from openjiuwen.harness.goal.evaluation import GoalEvaluator
from openjiuwen.harness.goal.schema import GoalStopConfig, GoalStopStrategy
from openjiuwen.harness.rails import TaskCompletionRail

from meta_agent.errors import RecoveryConflict
from meta_agent.spec.meta_agent_spec import BudgetConfig
from meta_agent.trace.rail import TraceRail

_ATTEMPT_STATE = "meta.goal.attempt"


class _AssessmentModel:
    def __init__(self, model: Any, rail: "BudgetRail", ctx: Any) -> None:
        self.model, self.rail, self.ctx = model, rail, ctx

    async def invoke(self, messages: Any, **kwargs: Any) -> Any:
        ctx = AgentCallbackContext(
            agent=self.ctx.agent,
            session=self.ctx.session,
            inputs=ModelCallInputs(messages=messages, tools=[]),
        )
        await self.rail.trace.before_model_call(ctx)
        try:
            response = await self.model.invoke(messages, **kwargs)
            ctx.inputs.response = response
            usage = getattr(response, "usage_metadata", None)
            manager = self.rail._goal_manager
            record = await manager.get()
            if usage is not None and record is not None:
                await manager.accumulate_usage(
                    goal_id=record.goal_id,
                    revision=record.revision,
                    input_tokens=max(0, usage.input_tokens),
                    output_tokens=max(0, usage.output_tokens),
                )
            return response
        except Exception as exc:
            ctx.exception = exc
            await self.rail.trace.on_model_exception(ctx)
            raise
        finally:
            await self.rail.trace.after_model_call(ctx)


class BudgetRail(TaskCompletionRail):  # type: ignore[misc]
    """Small adapter around the pinned kernel's goal lifecycle rail.

    The kernel owns reports, prompts, attempts and stop decisions. Its current
    strategy/model seams are protected methods, isolated here for upgrade review.
    """

    def __init__(self, budget: BudgetConfig, trace: TraceRail) -> None:
        super().__init__()
        self.budget, self.trace = budget, trace

    def set_goal_manager(self, goal_manager: Any) -> None:
        super().set_goal_manager(goal_manager)
        self._goal_evaluator = GoalEvaluator(
            GoalStopConfig(strategy=GoalStopStrategy(self.budget.stop_strategy))
        )

    def _resolve_transcript_model(self, ctx: Any) -> Any:
        model = super()._resolve_transcript_model(ctx)
        return _AssessmentModel(model, self, ctx) if model is not None else None

    async def before_invoke(self, ctx: Any) -> None:
        if (
            getattr(ctx.agent, "goal_manager", None) is self._goal_manager
            and self._goal_manager is not None
            and isinstance(getattr(ctx.inputs, "query", None), InteractiveInput)
            and not getattr(self, "_is_goal_round", False)
        ):
            record = await self._goal_manager.get()
            saved = ctx.session.get_state(_ATTEMPT_STATE)
            if (
                record is None
                or not isinstance(saved, dict)
                or any(
                    saved.get(key) != getattr(record, key)
                    for key in ("goal_id", "revision", "attempt_count")
                )
            ):
                raise RecoveryConflict(
                    "META_GOAL_RECOVERY_STATE", "Missing goal attempt checkpoint"
                )
            self._is_goal_round = True
            self._current_goal_id = record.goal_id
            self._current_revision = record.revision
            self._current_session_id = record.session_id
            self._current_attempt_messages = saved["messages"]
            self._goal_report_sink.begin_attempt(
                record.session_id, record.goal_id, record.revision, record.attempt_count
            )
            if saved["report"] is not None:
                self._goal_report_sink.submit(saved["report"])
        await super().before_invoke(ctx)

    async def after_invoke(self, ctx: Any) -> None:
        # The native interaction loop resumes interrupted ReAct directly, so
        # it does not fire task-iteration hooks for this finishing half-turn.
        if (
            getattr(ctx.agent, "goal_manager", None) is self._goal_manager
            and self._goal_manager is not None
            and isinstance(getattr(ctx.inputs, "query", None), InteractiveInput)
            and self._is_goal_round
        ):
            await self._do_goal_after_iteration(ctx)
            result = getattr(ctx.inputs, "result", None)
            current = await self._goal_manager.get()
            if (
                isinstance(result, dict)
                and result.get("result_type") != "interrupt"
                and current is not None
                and current.status.value == "paused"
            ):
                await self._goal_manager.resume()
        if (
            getattr(ctx.agent, "goal_manager", None) is self._goal_manager
            and self._goal_manager is not None
            and self._is_goal_round
        ):
            result = getattr(ctx.inputs, "result", None)
            saved = None
            if isinstance(result, dict) and result.get("result_type") == "interrupt":
                current = await self._goal_manager.get()
                saved = {
                    "goal_id": current.goal_id,
                    "revision": current.revision,
                    "attempt_count": current.attempt_count,
                    "messages": self._current_attempt_messages,
                    "report": self._goal_report_sink.report,
                }
            ctx.session.update_state({_ATTEMPT_STATE: saved})

    async def _maybe_invoke_transcript_assessor(
        self, record: Any, agent_report: Any, ctx: Any
    ) -> Any:
        response = await super()._maybe_invoke_transcript_assessor(record, agent_report, ctx)
        # Native assessment loaded this record before its isolated model call.
        # Include that call in the limit check of this same attempt.
        current = await self._goal_manager.get()
        if current is not None:
            record.token_usage = current.token_usage
        return response
