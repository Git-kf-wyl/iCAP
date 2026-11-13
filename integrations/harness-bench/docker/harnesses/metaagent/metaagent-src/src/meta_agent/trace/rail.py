"""Count actual native lifecycle callbacks without capturing model payloads."""

from openjiuwen.core.foundation.llm.schema.message import AssistantMessage, UsageMetadata
from openjiuwen.core.single_agent.rail.base import (
    AgentCallbackContext,
    AgentRail,
    ModelCallInputs,
    ToolCallInputs,
)

from meta_agent.errors import TraceError
from meta_agent.identity import ExecutionIdentity
from meta_agent.trace.sink import JsonlTraceSink


# The pinned upstream package has no py.typed marker; only this native subclass
# boundary is untyped. MetaAgent's methods and exported state remain checked.
class TraceRail(AgentRail):  # type: ignore[misc]
    """Request-scoped observations, including retried model lifecycle attempts.

    model_calls counts BEFORE_MODEL_CALL events, not provider billing or token
    budget enforcement. Unknown usage contributes no estimated tokens and is
    distinguished by usage_reports. A failed model attempt is counted once by
    ON_MODEL_EXCEPTION; the following AFTER hook does not count it twice.
    """

    priority = -100

    def __init__(self, sink: JsonlTraceSink, identity: ExecutionIdentity) -> None:
        self.sink = sink
        self.identity = identity
        self.model_calls = 0
        self.subagent_calls = 0
        self.model_errors = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_reports = 0
        self.trace_errors = 0
        self.gateway_prefixes: tuple[str, ...] = ()

    def bind(self, identity: ExecutionIdentity) -> None:
        """Rebind only between executions while the owning session is locked."""
        self.identity = identity
        self.model_calls = 0
        self.subagent_calls = 0
        self.model_errors = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_reports = 0
        self.trace_errors = 0

    def _emit(self, event: str, **fields: object) -> None:
        try:
            self.sink.emit(event, self.identity, **fields)
        except TraceError:
            # Observability failures must not mask an original model exception
            # or turn a successful external action into an apparent retryable error.
            self.trace_errors += 1

    async def before_model_call(self, ctx: AgentCallbackContext) -> None:
        self.model_calls += 1
        iteration = ctx.inputs.react_iteration if isinstance(ctx.inputs, ModelCallInputs) else 0
        self._emit(
            "model_call_started",
            model_calls=self.model_calls,
            retry_attempt=ctx.retry_attempt,
            react_iteration=iteration,
        )

    async def on_model_exception(self, ctx: AgentCallbackContext) -> None:
        self.model_errors += 1
        self._emit(
            "model_call_failed",
            model_errors=self.model_errors,
            error_type=type(ctx.exception).__name__
            if ctx.exception is not None
            else "UnknownError",
            retry_attempt=ctx.retry_attempt,
        )

    async def after_model_call(self, ctx: AgentCallbackContext) -> None:
        usage: UsageMetadata | None = None
        if isinstance(ctx.inputs, ModelCallInputs) and isinstance(
            ctx.inputs.response, AssistantMessage
        ):
            usage = ctx.inputs.response.usage_metadata
        if ctx.exception is None and usage is not None:
            self.usage_reports += 1
            self.input_tokens += max(0, usage.input_tokens)
            self.output_tokens += max(0, usage.output_tokens)
        self._emit(
            "model_call_finished",
            status="failed" if ctx.exception is not None else "completed",
            model_calls=self.model_calls,
            model_errors=self.model_errors,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            usage_reports=self.usage_reports,
        )

    async def after_tool_call(self, ctx: AgentCallbackContext) -> None:
        if isinstance(ctx.inputs, ToolCallInputs):
            self._emit(
                "tool_call_finished",
                tool_name=ctx.inputs.tool_name,
                gateway=ctx.inputs.tool_name.startswith(self.gateway_prefixes),
                status="failed" if ctx.exception else "returned",
            )

    async def before_tool_call(self, ctx: AgentCallbackContext) -> None:
        if isinstance(ctx.inputs, ToolCallInputs):
            self._emit(
                "tool_call_started",
                tool_name=ctx.inputs.tool_name,
                gateway=ctx.inputs.tool_name.startswith(self.gateway_prefixes),
                react_iteration=ctx.inputs.react_iteration,
            )
