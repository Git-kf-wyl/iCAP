"""Native Workflow construction with a public, auditable construction record."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from openjiuwen.core.workflow import SubWorkflowComponent, Workflow, WorkflowComponent

from meta_agent.errors import BootError

if TYPE_CHECKING:
    from meta_agent.checkpoint.bindings import EffectBinding


class PluginWorkflow(Workflow):  # type: ignore[misc]
    """Use public construction methods; the kernel still compiles and runs the DAG.

    Plugins are trusted Python. This gate validates declared composition, not code
    hidden inside custom nodes. Opaque native graphs cannot be inspected publicly.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.nodes: dict[str, Any] = {}
        self.edges: dict[str, set[str]] = {}
        self.start: str | None = None
        self.end: str | None = None
        self.sealed = False
        self.conditional_sources: set[str] = set()

    def _record(self, name: str, component: Any) -> None:
        if self.sealed or name in self.nodes:
            raise ValueError("Sealed graph or duplicate component")
        if not isinstance(component, WorkflowComponent):
            raise ValueError("Plugin nodes must be WorkflowComponents")
        self.nodes[name] = component

    def set_start_comp(self, name: str, component: Any, *args: Any, **kwargs: Any) -> Self:
        if self.start is not None:
            raise ValueError("Only one start is supported")
        self._record(name, component)
        self.start = name
        super().set_start_comp(name, component, *args, **kwargs)
        return self

    def add_workflow_comp(self, name: str, component: Any, **kwargs: Any) -> Self:
        self._record(name, component)
        if kwargs.get("max_retries", 0) or kwargs.get("exception_config"):
            raise ValueError(
                "Plugin retries/error substitution require an explicit future contract"
            )
        super().add_workflow_comp(name, component, **kwargs)
        return self

    def set_end_comp(self, name: str, component: Any, *args: Any, **kwargs: Any) -> Self:
        if self.end is not None or kwargs.get("response_mode") == "streaming":
            raise ValueError("Plugins require one buffered End")
        self._record(name, component)
        self.end = name
        super().set_end_comp(name, component, *args, **kwargs)
        return self

    def add_connection(self, source: str | list[str], target: str) -> Self:
        if self.sealed:
            raise ValueError("Graph is sealed")
        for name in [source] if isinstance(source, str) else source:
            if name in self.conditional_sources:
                raise ValueError("A source cannot mix conditional and unconditional edges")
            self.edges.setdefault(name, set()).add(target)
        super().add_connection(source, target)
        return self

    def add_conditional_connection(self, source: str, router: Any) -> Self:
        if self.sealed or source in self.edges or not hasattr(router, "all_targets"):
            raise ValueError("Each source needs one inspectable BranchRouter")
        self.conditional_sources.add(source)
        self.edges.setdefault(source, set()).update(router.all_targets)
        super().add_conditional_connection(source, router)
        return self

    def add_stream_connection(self, *args: Any, **kwargs: Any) -> Self:
        raise ValueError("M3 plugins use buffered invocation, not stream edges")

    def validate(self, max_depth: int, ancestors: frozenset[int] = frozenset()) -> None:
        from meta_agent.orchestrator.dag import DeepAgentComp

        if max_depth < 1 or id(self) in ancestors:
            raise BootError("META_PLUGIN_GRAPH", "Plugin nesting is cyclic or too deep.")
        if self.start is None or self.end is None:
            raise BootError("META_PLUGIN_GRAPH", "Plugin requires Start and End.")
        if set(self.edges) - set(self.nodes):
            raise BootError("META_PLUGIN_GRAPH", "Unknown edge source.")
        for node in self.nodes.values():
            if isinstance(node, DeepAgentComp):
                raise BootError("META_PLUGIN_GRAPH", "DeepAgentComp is forbidden inside plugins.")
            if isinstance(node, SubWorkflowComponent):
                if not isinstance(node.sub_workflow, PluginWorkflow):
                    raise BootError("META_PLUGIN_GRAPH", "Nested graphs must use PluginWorkflow.")
                node.sub_workflow.validate(max_depth - 1, ancestors | {id(self)})
            elif node.graph_invoker():
                raise BootError(
                    "META_PLUGIN_GRAPH", "Opaque graph-invoking components are unsupported."
                )
        visited: set[str] = set()
        active: set[str] = set()

        def walk(name: str) -> None:
            if name not in self.nodes or name in active:
                raise BootError("META_PLUGIN_GRAPH", "Plugin graph has unknown nodes or a cycle.")
            if name in visited:
                return
            active.add(name)
            for target in self.edges.get(name, set()):
                walk(target)
            active.remove(name)
            visited.add(name)

        walk(self.start)
        if (
            visited != set(self.nodes)
            or any(not self.edges.get(name) for name in self.nodes if name != self.end)
            or self.edges.get(self.end)
        ):
            raise BootError("META_PLUGIN_GRAPH", "All nodes must reach the single terminal End.")
        self.sealed = True

    def validate_effects(self, bindings: tuple[EffectBinding, ...]) -> None:
        """Check inspectable effect nodes, including native nested workflows.

        Custom Python nodes remain trusted code; this is not a sandbox.
        """
        from meta_agent.checkpoint.adapters import EffectWorkflowComponent

        for node in self.nodes.values():
            if isinstance(node, EffectWorkflowComponent) and not any(
                node.adapter == b.adapter and node.logical_key == b.logical_key for b in bindings
            ):
                raise BootError("META_PLUGIN_EFFECT", "Effect node lacks a declared host binding")
            if isinstance(node, SubWorkflowComponent):
                node.sub_workflow.validate_effects(bindings)
