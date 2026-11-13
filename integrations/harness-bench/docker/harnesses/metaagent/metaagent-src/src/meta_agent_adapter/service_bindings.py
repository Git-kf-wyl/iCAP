"""Staff-owned service bindings; these Python contracts are not platform wire formats."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from openjiuwen.core.context_engine import ContextEngine, ContextWindow, ModelContext

from meta_agent.errors import BootError
from meta_agent.identity import ExecutionIdentity
from meta_agent.spec.platform import ContextServiceConfig, PackageServicesConfig


@dataclass(frozen=True)
class ServiceRequest:
    service: Literal["memory", "skills"]
    operation: str
    payload: dict[str, Any]
    timeout_s: float


class ServiceTransport(ABC):
    """Map scope/identity/version and operations to the real service SDK.

    The host owns connection, authentication, deadline enforcement and closure.
    Return the normalized dictionaries consumed by the existing service adapters.
    """

    @abstractmethod
    async def invoke(self, request: ServiceRequest) -> dict[str, Any]:
        raise NotImplementedError


class ContextWindowAdapter(ABC):
    """Transform a native final window; do not mutate stored history implicitly.

    Host-owned instances can serve concurrent sessions. Staff maps native messages
    and trusted identity to ContextService and preserves tool-message ordering.
    """

    @abstractmethod
    async def transform(
        self, context: ModelContext, window: ContextWindow, identity: ExecutionIdentity
    ) -> ContextWindow:
        raise NotImplementedError


_SERVICES: dict[str, ServiceTransport] = {}
_CONTEXTS: dict[str, ContextWindowAdapter] = {}


def register_service_transport(name: str, transport: ServiceTransport) -> None:
    if not name.strip() or name in _SERVICES:
        raise BootError("META_SERVICE_BINDING", "Service binding name must be new and nonblank")
    _SERVICES[name] = transport


def unregister_service_transport(name: str) -> None:
    """Host unregisters after all dependent runtimes have closed."""
    _SERVICES.pop(name, None)


def get_service_transport(name: str) -> ServiceTransport:
    if name not in _SERVICES:
        raise BootError("META_SERVICE_NOT_CONFIGURED", f"Bind service transport '{name}' first")
    return _SERVICES[name]


def register_context_adapter(name: str, adapter: ContextWindowAdapter) -> None:
    if not name.strip() or name in _CONTEXTS:
        raise BootError("META_CONTEXT_BINDING", "Context binding name must be new and nonblank")
    _CONTEXTS[name] = adapter


def unregister_context_adapter(name: str) -> None:
    _CONTEXTS.pop(name, None)


def get_context_adapter(name: str) -> ContextWindowAdapter:
    if name not in _CONTEXTS:
        raise BootError("META_CONTEXT_NOT_CONFIGURED", f"Bind context adapter '{name}' first")
    return _CONTEXTS[name]


def validate_service_bindings(config: PackageServicesConfig) -> None:
    """Check host bindings before allocating HTTP clients or native resources."""
    for service in (config.memory_service, config.skills_runtime):
        if service is not None and service.transport_name is not None:
            get_service_transport(service.transport_name)
    if config.context_service is not None:
        get_context_adapter(config.context_service.adapter_name)


def attach_context_adapter(
    engine: ContextEngine,
    config: ContextServiceConfig | None,
    identity: Callable[[], ExecutionIdentity],
) -> None:
    if config is None:
        return
    adapter = get_context_adapter(config.adapter_name)

    async def transform(context: ModelContext, window: ContextWindow) -> ContextWindow:
        return await adapter.transform(context, window, identity())

    engine.register_window_mutator(transform)
