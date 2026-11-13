"""Stable error codes for the local MetaAgent API.

Messages must describe the failure without embedding credentials or raw request
payloads. The original exception may be chained for local debugging.
"""

from typing import Any


class MetaAgentError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")

    def __reduce__(self) -> tuple[object, ...]:
        # Native Workflow snapshots deepcopy exceptions before chaining them.
        return (
            type(self),
            (self.code, self.message),
            {
                **self.__dict__,
                "__cause__": self.__cause__,
                "__context__": self.__context__,
                "__suppress_context__": self.__suppress_context__,
            },
        )

    def __setstate__(self, state: dict[str, Any] | None) -> None:
        for key, value in (state or {}).items():
            setattr(self, key, value)


class BootError(MetaAgentError):
    """Configuration or package validation failed before the agent became ready."""


class UnsupportedCapabilityError(MetaAgentError):
    """A requested capability is not implemented by this release."""


class SessionConflict(MetaAgentError):
    """The session already has an active execution or stream."""


class SessionStateError(MetaAgentError):
    """The requested transition does not match the session's current state."""


class RequestConflictError(MetaAgentError):
    """A request identity has already been used and cannot be replayed."""


class TraceError(MetaAgentError):
    """A metadata trace could not be written; this is not a journal failure."""


class RunnerLifecycleError(MetaAgentError):
    """The process-wide kernel cannot serve the requested local lifecycle."""


class PluginFailure(MetaAgentError):
    """Explicit ordinary business failure, eligible for configured fallback."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        partial: dict[str, object] | None = None,
        completed_operations: list[str] | None = None,
    ) -> None:
        super().__init__(code, message)
        self.partial = partial or {}
        self.completed_operations = completed_operations or []


class ControlFlowError(MetaAgentError):
    """Infrastructure/control failures never become ordinary fallback."""


class LeaseLost(ControlFlowError):
    pass


class StorageUnavailable(ControlFlowError):
    pass


class SideEffectUnresolved(ControlFlowError):
    pass


class LeaseBusy(ControlFlowError):
    pass


class OperationConflict(ControlFlowError):
    pass


class RecoveryConflict(ControlFlowError):
    pass


class RouteClassificationError(MetaAgentError):
    """A declared classifier outage may degrade to the harness."""
