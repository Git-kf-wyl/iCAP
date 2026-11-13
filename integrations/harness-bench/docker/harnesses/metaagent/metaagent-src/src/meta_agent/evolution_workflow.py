"""Approved Skill recipes supply native workflows using host-bound operations.

Recipes are JSON data. Every generated package uses the same interpreter below;
neither the business model nor an evolution proposal supplies executable Python.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openjiuwen.core.workflow import End, Start, WorkflowComponent
from pydantic import Field

from meta_agent.checkpoint.adapters import EffectWorkflowComponent
from meta_agent.errors import SessionStateError
from meta_agent.registry.plugins import PluginBuildContext, PluginPackage, package_from_files
from meta_agent.spec.fastpath import IntentMetadata, StrictModel, WorkflowPluginManifest

if TYPE_CHECKING:
    from meta_agent.checkpoint.bindings import EffectBinding
    from meta_agent.evolution import SkillEvolution
    from meta_agent.registry.lifecycle import PluginManager


_WORKFLOW_ENTRY = b"from meta_agent.evolution_workflow import build_skill_workflow as build\n"


class WorkflowStep(StrictModel):
    tool: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    arguments: dict[str, Any] = Field(default_factory=dict)


class SkillWorkflowRecipe(StrictModel):
    skill_name: str
    skill_digest: str
    steps: list[WorkflowStep] = Field(min_length=1)


def _resolve(value: Any, state: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"input"}:
            if value["input"] != "query":
                raise ValueError("The supported input reference is query")
            return state["query"]
        if set(value) <= {"step", "path"} and "step" in value:
            result = state["results"][value["step"]]
            for key in value.get("path", []):
                result = result[key]
            return result
        return {key: _resolve(item, state) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, state) for item in value]
    return value


class _Operation(WorkflowComponent):  # type: ignore[misc]
    def __init__(self, step: WorkflowStep, operation: Callable[..., Awaitable[Any]]) -> None:
        super().__init__()
        self.step, self.operation = step, operation

    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, Any]:
        state = inputs.get("state") or {"query": inputs["query"], "results": []}
        result = await self.operation(_resolve(self.step.arguments, state))
        return {"state": {"query": state["query"], "results": [*state["results"], result]}}


class _Result(WorkflowComponent):  # type: ignore[misc]
    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, Any]:
        result = inputs["state"]["results"][-1]
        output = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return {"result": {"status": "success", "output": output}}


class _EffectOperation(EffectWorkflowComponent):
    """Resolve recipe arguments around the existing journal-owned effect node."""

    def __init__(self, step: WorkflowStep, binding: EffectBinding) -> None:
        super().__init__(binding.adapter, binding.logical_key)
        self.step = step

    async def invoke(self, inputs: Any, session: Any, context: Any) -> dict[str, Any]:
        state = inputs.get("state") or {"query": inputs["query"], "results": []}
        result = await super().invoke(_resolve(self.step.arguments, state), session, context)
        return {
            "state": {"query": state["query"], "results": [*state["results"], result["result"]]}
        }


async def build_skill_workflow(context: PluginBuildContext) -> Any:
    """Fixed package entry: build an inspectable native DAG for the approved recipe."""
    recipe = SkillWorkflowRecipe.model_validate_json(context.files["recipe.json"])
    graph = context.workflow()
    graph.set_start_comp("start", Start(), inputs_schema={"query": "${query}"})
    previous = "start"
    for index, step in enumerate(recipe.steps):
        if step.tool not in context.operations and step.tool not in context.effects:
            raise ValueError(f"Host has not bound workflow tool: {step.tool}")
        name = f"step_{index}"
        schema = (
            {"query": "${start.query}"} if index == 0 else {"state": "${" + previous + ".state}"}
        )
        graph.add_workflow_comp(
            name,
            _EffectOperation(step, context.effects[step.tool])
            if step.tool in context.effects
            else _Operation(step, context.operations[step.tool]),
            inputs_schema=schema,
        )
        graph.add_connection(previous, name)
        previous = name
    graph.add_workflow_comp(
        "result", _Result(), inputs_schema={"state": "${" + previous + ".state}"}
    )
    graph.add_connection(previous, "result")
    graph.set_end_comp("end", End(), inputs_schema={"result": "${result.result}"})
    graph.add_connection("result", "end")
    return graph


class WorkflowSupply:
    """Review, activate and roll back a concrete recipe over an approved Skill."""

    def __init__(self, evolution: SkillEvolution, plugins: PluginManager) -> None:
        self.evolution, self.plugins = evolution, plugins
        self._pending: dict[str, dict[str, Any]] = {}
        self._activated: dict[str, dict[str, Any]] = {}
        self._packages: dict[tuple[str, str], PluginPackage] = {}
        self._selected: dict[str, str | None] = {}
        self._ready = True

    def state(self) -> dict[str, Any]:
        return {
            "pending": self._pending,
            "activated": self._activated,
            "packages": self._packages,
            "selected": self._selected,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        self._pending = state.get("pending", {})
        self._activated = state.get("activated", {})
        self._packages = state.get("packages", {})
        self._selected = state.get("selected", {})
        self._ready = not self._packages

    def require_ready(self) -> None:
        if not self._ready:
            raise SessionStateError(
                "META_WORKFLOW_REBIND_REQUIRED",
                "Rebind host workflow tools and await restore_workflows before submitting work",
            )

    def ensure_external_change(self, name: str) -> None:
        if self.evolution.checkpoint is not None and name in self._selected:
            raise SessionStateError(
                "META_WORKFLOW_GOVERNED", "Use workflow review APIs to change this plugin"
            )

    def bind_tool(self, name: str, operation: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        self.evolution._ensure_idle()
        if self.evolution.busy:
            raise SessionStateError("META_EVOLUTION_BUSY", "A Skill operation is running")
        if self.plugins.recovery is not None and name not in self.plugins.recovery.read_only_tools:
            raise SessionStateError(
                "META_WORKFLOW_TOOL", "Declare a read-only callback or use a recovery EffectBinding"
            )
        if not re.fullmatch(r"[a-z][a-z0-9_.-]*", name) or name in self.plugins.operations:
            raise ValueError("Workflow tools need a unique capability name")
        if name in self._effects():
            raise ValueError("Workflow callback conflicts with an effect binding")
        self.plugins.operations[name] = operation

    def _effects(self) -> set[str]:
        return (
            {binding.name for binding in self.plugins.recovery.plugin_effects}
            if self.plugins.recovery is not None
            else set()
        )

    def _validate_tools(self, recipe: SkillWorkflowRecipe) -> None:
        for step in recipe.steps:
            if step.tool not in self._effects() and step.tool not in self.plugins.operations:
                raise SessionStateError("META_WORKFLOW_TOOL", f"Bind workflow tool: {step.tool}")

    def _sync_only(self) -> None:
        if self.evolution.checkpoint is not None:
            raise SessionStateError(
                "META_WORKFLOW_ASYNC_REQUIRED", "Use await stage_workflow / reject_workflow"
            )

    def propose(self, skill_name: str, **kwargs: Any) -> dict[str, Any]:
        self._sync_only()
        with self.evolution._operation():
            return self._propose(skill_name, **kwargs)

    async def stage(self, skill_name: str, **kwargs: Any) -> dict[str, Any]:
        async with self.evolution._review_operation():
            return self._propose(skill_name, **kwargs)

    def _propose(
        self,
        skill_name: str,
        *,
        name: str,
        version: str,
        rules: list[str],
        steps: list[dict[str, Any]],
        description: str | None = None,
    ) -> dict[str, Any]:
        self.require_ready()
        if self.plugins.catalog is not None and self.evolution.checkpoint is not None:
            raise SessionStateError(
                "META_WORKFLOW_CATALOG",
                "Durable workflows use the review store; omit plugin_catalog",
            )
        digest = self.evolution._skill_digest(skill_name)
        if self.evolution._approved_skills.get(skill_name) != digest:
            raise SessionStateError(
                "META_SKILL_UNAPPROVED", "Approve this Skill before supplying a workflow"
            )
        if not self.plugins.spec.fastpath.enabled:
            raise SessionStateError(
                "META_PLUGIN_CONFIG", "Workflow supply requires enabled fastpath"
            )
        recipe = SkillWorkflowRecipe.model_validate(
            {"skill_name": skill_name, "skill_digest": digest, "steps": steps}
        )
        self._validate_tools(recipe)
        if not rules:
            raise ValueError("A workflow requires an explicit route")
        manifest = WorkflowPluginManifest(
            name=name,
            version=version,
            entry="workflow.py:build",
            intent=IntentMetadata(
                description=description or f"Approved {skill_name} workflow", rules=rules
            ),
            effects=sorted({step.tool for step in recipe.steps} & self._effects()),
        )
        proposal: dict[str, Any] = {
            "request_id": uuid4().hex,
            "status": "staged",
            "manifest": manifest.model_dump(),
            "recipe": recipe.model_dump(),
        }
        # Store a detached snapshot of exactly what the host reviews.
        self._pending[proposal["request_id"]] = json.loads(json.dumps(proposal))
        self.evolution._emit(
            "evolution.workflow_proposed",
            self.evolution._host_identity,
            skill_name=skill_name,
            proposal_id=proposal["request_id"],
            status="staged",
        )
        return proposal

    def pending(self) -> list[dict[str, Any]]:
        return deepcopy(list(self._pending.values()))

    async def approve(self, request_id: str) -> dict[str, Any]:
        self.require_ready()
        with self.evolution._operation():
            if self.evolution.checkpoint is not None:
                await self.evolution.checkpoint.check()
            proposal = self._proposal(request_id)
            recipe = proposal["recipe"]
            skill = recipe["skill_name"]
            if self.evolution._approved_skills.get(skill) != self.evolution._skill_digest(skill):
                raise SessionStateError(
                    "META_SKILL_UNAPPROVED", "Skill approval changed; propose again"
                )
            if recipe["skill_digest"] != self.evolution._skill_digest(skill):
                raise SessionStateError(
                    "META_SKILL_CHANGED", "Skill changed; propose a new workflow"
                )
            manifest = proposal["manifest"]
            previous = next(
                (
                    p["version"]
                    for p in self.plugins.list()
                    if p["name"] == manifest["name"] and p["active"]
                ),
                None,
            )
            self._validate_tools(SkillWorkflowRecipe.model_validate(recipe))
            package = package_from_files(
                {
                    "manifest.json": json.dumps(manifest, indent=2).encode(),
                    "recipe.json": json.dumps(recipe, indent=2).encode(),
                    "workflow.py": _WORKFLOW_ENTRY,
                }
            )
            # Export for inspection; committed package bytes are the recovery source.
            root = (
                Path(self.plugins.spec.deep_agent.workspace.root_path) / ".meta-workflows"
                if self.evolution.checkpoint is not None
                else self.evolution._archive.directory / "workflows"
            )
            directory = root / request_id
            directory.mkdir(parents=True, exist_ok=True)
            for name, content in package.files:
                (directory / name).write_bytes(content)
            activated = {**proposal, "previous_version": previous, "digest": package.digest}
            if self.evolution.checkpoint is None:
                await self.plugins.load(directory)
                await self.plugins.activate(manifest["name"], manifest["version"])
                self._activated[request_id] = activated
                del self._pending[request_id]
            else:
                retained = {
                    key: value
                    for key, value in self.plugins.versions.items()
                    if key[0] == manifest["name"]
                }
                retained[(manifest["name"], manifest["version"])] = package

                async def commit() -> None:
                    self._packages.update(retained)
                    self._selected[manifest["name"]] = manifest["version"]
                    self._activated[request_id] = activated
                    del self._pending[request_id]
                    await self._save()

                await self.plugins.publish_retained(
                    tuple(retained.values()), {manifest["name"]: manifest["version"]}, commit=commit
                )
            result = {
                "status": "activated",
                "name": manifest["name"],
                "version": manifest["version"],
                "digest": package.digest,
                "directory": str(directory),
                "rollback_version": previous,
            }
            self.evolution._emit(
                "evolution.workflow_approved",
                self.evolution._host_identity,
                skill_name=skill,
                proposal_id=request_id,
                plugin=manifest["name"],
                plugin_version=manifest["version"],
                status="activated",
            )
            return result

    def reject(self, request_id: str) -> None:
        self._sync_only()
        with self.evolution._operation():
            self._proposal(request_id)
            del self._pending[request_id]

    async def reject_pending(self, request_id: str) -> None:
        async with self.evolution._review_operation():
            self._proposal(request_id)
            del self._pending[request_id]

    def _proposal(self, request_id: str) -> dict[str, Any]:
        if request_id not in self._pending:
            raise SessionStateError("META_PROPOSAL_UNKNOWN", "No pending workflow with this ID")
        return self._pending[request_id]

    async def _save(self) -> None:
        checkpoint = self.evolution.checkpoint
        assert checkpoint is not None
        try:
            await checkpoint.save(self.evolution)
        except BaseException:
            checkpoint.failed = True
            raise

    async def restore(self) -> None:
        with self.evolution._operation():
            if self.evolution.checkpoint is not None:
                await self.evolution.checkpoint.check()
            if not self._packages:
                return
            for package in self._packages.values():
                files = dict(package.files)
                if files.get("workflow.py") == _WORKFLOW_ENTRY:
                    self._validate_tools(
                        SkillWorkflowRecipe.model_validate_json(files["recipe.json"])
                    )
            await self.plugins.publish_retained(tuple(self._packages.values()), self._selected)
            self._ready = True

    async def rollback(self, request_id: str) -> None:
        self.require_ready()
        with self.evolution._operation():
            if request_id not in self._activated:
                raise SessionStateError(
                    "META_PROPOSAL_UNKNOWN", "No activated workflow with this ID"
                )
            activated = self._activated[request_id]
            name, previous = activated["manifest"]["name"], activated["previous_version"]
            current = next(
                (p for p in self.plugins.active.packages if p.manifest.name == name), None
            )
            if current is None or current.digest != activated["digest"]:
                raise SessionStateError(
                    "META_WORKFLOW_VERSION", "Only the active workflow can roll back"
                )
            if self.evolution.checkpoint is None:
                await self.plugins.activate(name, previous)
                del self._activated[request_id]
            else:
                await self.evolution.checkpoint.check()

                async def commit() -> None:
                    self._selected[name] = previous
                    del self._activated[request_id]
                    await self._save()

                await self.plugins.publish_retained(
                    tuple(self._packages.values()), {name: previous}, commit=commit
                )
            self.evolution._emit(
                "evolution.workflow_rollback",
                self.evolution._host_identity,
                proposal_id=request_id,
                plugin=activated["manifest"]["name"],
                status="restored",
            )
