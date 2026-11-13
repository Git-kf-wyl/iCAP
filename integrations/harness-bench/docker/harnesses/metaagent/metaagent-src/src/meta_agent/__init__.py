"""MetaAgent public API, imported lazily to keep CLI output and imports lightweight."""

from importlib import import_module
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from meta_agent.base_agent import AgentEvent, AgentResult, MetaBaseAgent
    from meta_agent.boot import MetaBootLoader
    from meta_agent.identity import ExecutionIdentity
    from meta_agent.spec import MetaAgentSpec

__version__ = version("meta-agent")

_EXPORTS = {
    "AgentEvent": "meta_agent.base_agent",
    "AgentResult": "meta_agent.base_agent",
    "MetaBaseAgent": "meta_agent.base_agent",
    "MetaBootLoader": "meta_agent.boot",
    "ExecutionIdentity": "meta_agent.identity",
    "MetaAgentSpec": "meta_agent.spec",
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    value = getattr(import_module(_EXPORTS[name]), name)
    globals()[name] = value
    return value


__all__ = [
    "AgentEvent",
    "AgentResult",
    "ExecutionIdentity",
    "MetaAgentSpec",
    "MetaBaseAgent",
    "MetaBootLoader",
    "__version__",
]
