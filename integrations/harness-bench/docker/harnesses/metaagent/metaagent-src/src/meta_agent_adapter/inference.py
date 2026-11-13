"""Python handoff contract for staff-owned inference transports.

This is not an MMAgentWorker wire protocol. The platform adapter maps these
objects to its actual UDS/SDK requests and normalizes replies at this boundary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from meta_agent.errors import BootError, UnsupportedCapabilityError


@dataclass(frozen=True)
class InferenceContext:
    product_id: str
    agent_id: str
    session_id: str
    request_id: str
    package_digest: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceRequest:
    call_id: str
    payload: dict[str, Any]
    timeout_s: float
    context: InferenceContext | None = None


class InferenceTransport(ABC):
    """Implement I/O here; OpenJiuwen continues to own model/tool execution.

    Replies are JSON dictionaries matching native AssistantMessage fields:
    content, tool_calls, finish_reason, optional usage_metadata, etc. Stream
    replies match AssistantMessageChunk and contain deltas, not accumulated text.
    """

    @abstractmethod
    async def invoke(self, request: InferenceRequest) -> dict[str, Any]:
        raise NotImplementedError

    def stream(self, request: InferenceRequest) -> AsyncIterator[dict[str, Any]]:
        raise UnsupportedCapabilityError(
            "META_PLATFORM_STREAM_UNSUPPORTED",
            "The platform transport does not implement streaming",
        )

    async def list_models(self) -> list[dict[str, Any]]:
        """Optional discovery; each entry has an id. Activation does not call this."""
        raise UnsupportedCapabilityError(
            "META_PLATFORM_MODELS_UNSUPPORTED",
            "The platform transport does not implement discovery",
        )

    async def aclose(self) -> None:
        """The host calls this after closing runtimes and unregistering transport."""


_TRANSPORTS: dict[str, InferenceTransport] = {}
_CONTEXT: ContextVar[InferenceContext | None] = ContextVar("meta_inference_context", default=None)


def register_inference_transport(name: str, transport: InferenceTransport) -> None:
    if not name.strip() or name in _TRANSPORTS:
        raise BootError("META_PLATFORM_BINDING", "Transport name must be nonempty and unregistered")
    _TRANSPORTS[name] = transport


def unregister_inference_transport(name: str) -> None:
    """Remove a host-owned binding after all runtimes using it have closed."""
    _TRANSPORTS.pop(name, None)


def get_inference_transport(name: str) -> InferenceTransport:
    transport = _TRANSPORTS.get(name)
    if transport is None:
        raise BootError(
            "META_PLATFORM_NOT_CONFIGURED",
            "Register the platform inference transport before activation",
        )
    return transport


def current_inference_context() -> InferenceContext | None:
    return _CONTEXT.get()


@contextmanager
def bind_inference_context(value: InferenceContext) -> Iterator[None]:
    token = _CONTEXT.set(value)
    try:
        yield
    finally:
        _CONTEXT.reset(token)
