"""Host operation bindings without importing the native workflow runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from meta_agent.checkpoint.executor import EffectAdapter
from meta_agent.checkpoint.models import identifier

if TYPE_CHECKING:
    from openjiuwen.core.foundation.tool import ToolCard

    from meta_agent.checkpoint.adapters import BoundEffectTool, EffectWorkflowComponent


@dataclass(frozen=True)
class EffectBinding:
    """One host-defined operation shared by plugin nodes and fallback tools.

    The name is a plugin capability; logical_key identifies the business operation
    within an execution. Reusing this binding across paths preserves that identity.
    """

    name: str
    adapter: EffectAdapter
    logical_key: str

    def __post_init__(self) -> None:
        identifier(self.name)
        identifier(self.logical_key)

    def component(self) -> EffectWorkflowComponent:
        from meta_agent.checkpoint.adapters import EffectWorkflowComponent

        return EffectWorkflowComponent(self.adapter, self.logical_key)

    def tool(self, card: ToolCard) -> BoundEffectTool:
        from meta_agent.checkpoint.adapters import BoundEffectTool

        return BoundEffectTool(card, self.adapter, self.logical_key)
