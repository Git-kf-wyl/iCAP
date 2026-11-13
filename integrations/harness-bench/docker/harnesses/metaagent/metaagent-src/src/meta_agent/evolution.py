"""Host-only Skill governance using native proposals, persistence and archives."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager, suppress
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openjiuwen.agent_evolving.experience.archive import EvolutionArchiveService
from openjiuwen.agent_evolving.signal.base import EvolutionSignal
from openjiuwen.agent_evolving.signal.from_conv import ConversationSignalDetector
from openjiuwen.agent_evolving.signal.team import make_team_user_intent_signal
from openjiuwen.agent_evolving.trajectory.messages import project_trajectory_messages
from openjiuwen.agent_evolving.trajectory.spans import merge_trajectories
from openjiuwen.agent_evolving.utils import parse_top_level_frontmatter
from openjiuwen.harness.rails.evolution.review.runtime import EvolutionReviewRuntime
from openjiuwen.harness.rails.evolution.skill_evolution_rail import SkillEvolutionRail
from openjiuwen.harness.rails.evolution.team_skill_evolution_rail import TeamSkillEvolutionRail

from meta_agent.errors import SessionConflict, SessionStateError
from meta_agent.evolution_source import SourcePublication
from meta_agent.evolution_workflow import WorkflowSupply
from meta_agent.identity import ExecutionIdentity
from meta_agent.registry.lifecycle import PluginManager
from meta_agent.trace.trajectory import TrajectoryArchive

if TYPE_CHECKING:
    from meta_agent.checkpoint.evolution import EvolutionCheckpoint


class _HostTeamRail(TeamSkillEvolutionRail):  # type: ignore[misc]
    """Native external-signal API inherits a regular-Skill filter; admit team Skills."""

    def _is_regular_skill(self, name: str) -> bool:
        return bool(self._is_team_skill(name))


class SkillEvolution:
    """One owner's native review flow, optionally checkpointed across restarts.

    No evolution tools are exposed to the business model. Approve/reject/rollback
    are trusted host operations; applications decide who may call them.
    """

    def __init__(
        self,
        *,
        skills: list[str],
        model: Any,
        model_name: str,
        language: str,
        processor: Any,
        archive: TrajectoryArchive,
        ensure_idle: Callable[[], None],
        emit: Callable[..., None],
        host_identity: ExecutionIdentity,
        plugins: PluginManager,
        checkpoint: EvolutionCheckpoint | None = None,
    ) -> None:
        directories = []
        for configured in skills:
            root = Path(configured).resolve()
            directories.extend(
                [root]
                if (root / "SKILL.md").is_file()
                else [p.parent for p in root.glob("*/SKILL.md")]
            )
        self._skills = {p.name: p for p in directories}
        if len(self._skills) != len(set(directories)):
            raise ValueError("Evolution requires unique Skill directory names")
        self._rail = SkillEvolutionRail(
            skills_dir=sorted({str(p.parent) for p in directories}),
            llm=model,
            model=model_name,
            language=language,
            trajectory_span_processor=processor,
            review_runtime=EvolutionReviewRuntime(),
            auto_save=False,
            signal_trigger=False,
            review_trigger=False,
        )
        self._team_rail = (
            _HostTeamRail(
                skills_dir=sorted({str(p.parent) for p in directories}),
                llm=model,
                model=model_name,
                language=language,
                trajectory_span_processor=processor,
                review_runtime=EvolutionReviewRuntime(),
                auto_save=False,
                signal_trigger=False,
                review_trigger=False,
            )
            if any(
                parse_top_level_frontmatter((p / "SKILL.md").read_text(encoding="utf-8")).get(
                    "kind"
                )
                in {"team-skill", "swarm-skill"}
                for p in directories
            )
            else None
        )
        self._archives = EvolutionArchiveService(store=self._rail.evolution_store)
        self._archive = archive
        self._ensure_idle = ensure_idle
        self._emit = emit
        self._host_identity = host_identity
        self._origins: dict[str, ExecutionIdentity] = {}
        self._rollback_versions: dict[str, str] = {}
        self._task: asyncio.Task[Any] | None = None
        self._scanned: set[tuple[str, str]] = set()
        self.automatic: list[dict[str, Any]] = []
        self._approved_skills: dict[str, str] = {}
        self.workflows = WorkflowSupply(self, plugins)
        self.checkpoint = checkpoint
        self.sources = SourcePublication(self)
        if checkpoint is not None:
            state = checkpoint.review
            for name, rail in (("skill", self._rail), ("team", self._team_rail)):
                if rail is not None:
                    rail.experience_manager.pending_approval_snapshots.update(state.get(name, {}))
            self._origins = state.get("origins", {})
            self._rollback_versions = state.get("rollback_versions", {})
            self._approved_skills = state.get("approved_skills", {})
            self._scanned = state.get("scanned", set())
            self.automatic = state.get("automatic", [])
            self.workflows.restore_state(state.get("workflows", {}))
            self.sources.restore_state(state.get("sources", {}))
            if plugins.catalog is not None and any(state.get("workflows", {}).values()):
                raise SessionStateError(
                    "META_WORKFLOW_CATALOG",
                    "Durable workflows use the review store; omit plugin_catalog",
                )

    def review_state(self) -> dict[str, Any]:
        """Native caller-owned pending snapshots plus the host's review metadata."""
        return {
            "skill": self._rail.experience_manager.pending_approval_snapshots,
            "team": self._team_rail.experience_manager.pending_approval_snapshots
            if self._team_rail is not None
            else {},
            "origins": self._origins,
            "rollback_versions": self._rollback_versions,
            "approved_skills": self._approved_skills,
            "scanned": self._scanned,
            "automatic": self.automatic,
            "workflows": self.workflows.state(),
            "sources": self.sources.state(),
        }

    def _skill_digest(self, name: str) -> str:
        self._skill(name)
        return sha256((self._skills[name] / "SKILL.md").read_bytes()).hexdigest()

    def _rail_for(self, skill_name: str) -> Any:
        if self._team_rail is not None and self._team_rail._is_team_skill(skill_name):
            return self._team_rail
        return self._rail

    def _pending_rail(self, request_id: str) -> Any:
        for rail in [self._rail, self._team_rail]:
            if (
                rail is not None
                and request_id in rail.experience_manager.pending_approval_snapshots
            ):
                return rail
        raise SessionStateError("META_PROPOSAL_UNKNOWN", "No pending proposal with this ID")

    def bind_workflow_tool(
        self, name: str, operation: Callable[[dict[str, Any]], Awaitable[Any]]
    ) -> None:
        """Bind a host-authorized tool; proposal/model text cannot create a binding."""
        self.workflows.bind_tool(name, operation)

    def propose_workflow(self, skill_name: str, **kwargs: Any) -> dict[str, Any]:
        return self.workflows.propose(skill_name, **kwargs)

    async def stage_workflow(self, skill_name: str, **kwargs: Any) -> dict[str, Any]:
        """Stage a recipe and await its durable review commit when recovery is enabled."""
        return await self.workflows.stage(skill_name, **kwargs)

    async def reject_workflow(self, request_id: str) -> None:
        await self.workflows.reject_pending(request_id)

    async def restore_workflows(self) -> None:
        """Publish retained workflows after the host has rebound its callbacks."""
        await self.workflows.restore()

    async def approve_workflow(self, request_id: str) -> dict[str, Any]:
        return await self.workflows.approve(request_id)

    async def rollback_workflow(self, request_id: str) -> None:
        await self.workflows.rollback(request_id)

    async def stage_source(self, skill_name: str, directory: str | Path) -> dict[str, Any]:
        """Capture a source package for review; existing sessions keep their version."""
        return await self.sources.stage(skill_name, directory)

    async def approve_source(self, request_id: str) -> dict[str, Any]:
        return await self.sources.approve(request_id)

    async def reject_source(self, request_id: str) -> None:
        await self.sources.reject(request_id)

    async def rollback_source(self, skill_name: str, version: str) -> bool:
        return await self.sources.rollback(skill_name, version)

    def _evidence(self, execution_id: str) -> tuple[Any, list[Any], list[Any]]:
        trajectories = self._archive.executions(execution_id)
        if not trajectories:
            raise SessionStateError("META_TRAJECTORY_UNKNOWN", "No captured execution found")
        trajectory = trajectories[0]
        for increment in trajectories[1:]:
            trajectory = merge_trajectories(trajectory, increment)
        messages, issues = project_trajectory_messages(trajectory)
        if not messages:
            raise SessionStateError("META_TRAJECTORY_EMPTY", "No conversation evidence captured")
        return trajectory, messages, issues

    async def detect_and_propose(self, skill_name: str, *, execution_id: str) -> dict[str, Any]:
        """Detect native failure/correction signals and stage a reviewable proposal."""
        async with self._review_operation():
            self._skill(skill_name)
            if any(p["skill_name"] == skill_name for p in self.pending()):
                return {"status": "pending", "skill_name": skill_name, "signals": []}
            trajectory, messages, issues = self._evidence(execution_id)
            detector = ConversationSignalDetector(existing_skills=set(self._skills))
            signals = detector.detect_trajectory_signals(trajectory, messages=messages)
            signals += await detector.detect_user_intent(messages, allow_skillless=True)
            signals = [s for s in signals if s.skill_name in (None, skill_name)]
            for signal in signals:
                signal.skill_name = skill_name
            if not signals:
                return {"status": "no_signal", "skill_name": skill_name, "signals": []}
            result = await self._stage(skill_name, trajectory, messages, issues, signals)
            result["signals"] = [s.to_dict() for s in signals]
            return result

    async def on_execution_complete(self, execution_id: str, *, skill_name: str) -> None:
        """Opt-in completion hook. Proposals never auto-approve or fail business output."""
        key = (skill_name, execution_id)
        if key in self._scanned:
            return
        try:
            result = await self.detect_and_propose(skill_name, execution_id=execution_id)
            async with self._review_operation():
                self._scanned.add(key)
                self.automatic.append({"execution_id": execution_id, **result})
            self._emit(
                "evolution.scan",
                self._host_identity,
                skill_name=skill_name,
                status=result["status"],
            )
        except Exception as exc:
            self.automatic.append(
                {
                    "execution_id": execution_id,
                    "status": "scan_failed",
                    "error_code": getattr(exc, "code", type(exc).__name__),
                }
            )
            self._emit(
                "evolution.scan",
                self._host_identity,
                skill_name=skill_name,
                status="scan_failed",
                error_type=type(exc).__name__,
            )

    async def _stage(
        self,
        skill_name: str,
        trajectory: Any,
        messages: list[Any],
        issues: list[Any],
        signals: list[EvolutionSignal],
        *,
        user_query: str = "",
    ) -> dict[str, Any]:
        attrs = trajectory.resource_attributes
        origin = ExecutionIdentity(
            self._host_identity.product_id,
            self._host_identity.agent_id,
            attrs.get("meta.session_id", "evolution"),
            attrs.get("meta.request_id", "evolution"),
            attrs.get("case_id", self._host_identity.execution_id),
        )
        result = await self._rail_for(skill_name).evolve_from_external_signals(
            signals=signals,
            trajectory=trajectory,
            messages=messages,
            user_query=user_query or "\n".join(s.excerpt for s in signals),
            requires_approval=True,
        )
        request = result.request
        request_id = request.request_id if request else None
        if request_id:
            self._origins[request_id] = origin
        self._emit(
            "evolution.proposed",
            origin,
            skill_name=skill_name,
            proposal_id=request_id,
            status=result.status,
        )
        return {
            "status": result.status,
            "request_id": request_id,
            "skill_name": skill_name,
            "capture_issues": [dict(issue) for issue in issues],
            "records": [r.to_dict() for r in request.proposal.records] if request else [],
        }

    @property
    def busy(self) -> bool:
        return self._task is not None

    @property
    def store(self) -> Any:
        """Native read view for SkillUseRail's progressive disclosure."""
        return self._rail.evolution_store

    @contextmanager
    def _operation(self) -> Iterator[None]:
        self._ensure_idle()
        if self.busy:
            raise SessionConflict("META_EVOLUTION_BUSY", "A Skill operation is running")
        self._task = asyncio.current_task()
        try:
            yield
        finally:
            self._task = None

    @asynccontextmanager
    async def _review_operation(self) -> AsyncIterator[None]:
        with self._operation():
            if self.checkpoint is not None:
                await self.checkpoint.check()
            try:
                yield
                if self.checkpoint is not None:
                    await self.checkpoint.save(self)
            except (SessionConflict, SessionStateError):
                # Rejected host input does not invalidate a committed review.
                raise
            except BaseException:
                if self.checkpoint is not None:
                    self.checkpoint.failed = True
                raise

    def _skill(self, name: str) -> None:
        if (
            name not in self._skills
            or self._rail.evolution_store.resolve_skill_dir(name) != self._skills[name]
        ):
            raise SessionStateError("META_SKILL_UNKNOWN", "Skill is not configured")

    def _pending(self, request_id: str) -> Any:
        pending = self._pending_rail(request_id).experience_manager.pending_approval_snapshots.get(
            request_id
        )
        if pending is None:
            raise SessionStateError("META_PROPOSAL_UNKNOWN", "No pending proposal with this ID")
        return pending

    async def propose(
        self, skill_name: str, *, execution_id: str, instruction: str
    ) -> dict[str, Any]:
        """Generate a reviewable proposal from this runtime's archived execution."""
        async with self._review_operation():
            self._skill(skill_name)
            if any(p["skill_name"] == skill_name for p in self.pending()):
                raise SessionConflict("META_PROPOSAL_PENDING", "Resolve the current proposal first")
            if not instruction.strip():
                raise ValueError("An evolution instruction is required")
            trajectory, messages, issues = self._evidence(execution_id)
            return await self._stage(
                skill_name,
                trajectory,
                messages,
                issues,
                [EvolutionSignal("user_intent", "Troubleshooting", instruction, skill_name)],
                user_query=instruction,
            )

    def pending(self) -> list[dict[str, Any]]:
        return [
            {
                "request_id": key,
                "skill_name": value.skill_name,
                "records": [record.to_dict() for record in value.payload],
            }
            for rail in [self._rail, self._team_rail]
            if rail is not None
            for key, value in rail.experience_manager.pending_approval_snapshots.items()
        ]

    async def approve(self, request_id: str) -> dict[str, Any]:
        """Archive the current pair, then commit the exact native proposal."""
        async with self._review_operation():
            pending = self._pending(request_id)
            if request_id not in self._rollback_versions:
                pair = await self._archives.archive_current_pair(pending.skill_name)
                if pair is None:
                    raise SessionStateError("META_SKILL_ARCHIVE", "Could not archive current Skill")
                self._rollback_versions[request_id] = pair.version
            rollback_version = self._rollback_versions[request_id]
            _, result = await self._pending_rail(
                request_id
            ).approval_runtime.approve_pending_request(
                request_id, rail_name="MetaAgent", action_name="approve"
            )
            status = "activated" if result.ok else "partial"
            self._emit(
                "evolution.approved",
                self._origins.get(request_id, self._host_identity),
                skill_name=pending.skill_name,
                proposal_id=request_id,
                status=status,
                skill_version=rollback_version,
                applied_count=result.applied_count,
                pending_count=result.pending_count,
            )
            if result.ok:
                self._approved_skills[pending.skill_name] = self._skill_digest(pending.skill_name)
                self._origins.pop(request_id, None)
                self._rollback_versions.pop(request_id, None)
            return {
                "status": status,
                "rollback_version": rollback_version,
                "applied_count": result.applied_count,
                "pending_count": result.pending_count,
            }

    async def reject(self, request_id: str) -> None:
        async with self._review_operation():
            pending = self._pending(request_id)
            await self._pending_rail(request_id).reject_record(request_id)
            self._rollback_versions.pop(request_id, None)
            self._emit(
                "evolution.rejected",
                self._origins.pop(request_id, self._host_identity),
                skill_name=pending.skill_name,
                proposal_id=request_id,
                status="rejected",
            )

    def versions(self, skill_name: str) -> list[dict[str, str]]:
        self._skill(skill_name)
        return [pair.to_payload() for pair in self._archives.list_pairs(skill_name)]

    async def rollback(self, skill_name: str, version: str) -> bool:
        async with self._review_operation():
            self._skill(skill_name)
            if any(p["skill_name"] == skill_name for p in self.pending()):
                raise SessionConflict("META_PROPOSAL_PENDING", "Resolve pending proposals first")
            restored = bool(await self._archives.rollback_to_pair(skill_name, version))
            if restored:
                self._approved_skills.pop(skill_name, None)
            self._emit(
                "evolution.rollback",
                self._host_identity,
                skill_name=skill_name,
                skill_version=version,
                status="restored" if restored else "not_found",
            )
            return restored

    async def aclose(self) -> None:
        if self._task is not None and self._task is not asyncio.current_task():
            task = self._task
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class TeamEvolution:
    """Compose captured member trajectories into one native, owner-reviewed proposal.

    This facade owns no second execution engine or approval store. A Team Skill
    lives in a member's package and uses that member's existing approval/rollback.
    """

    def __init__(self, team: Any) -> None:
        self.team = team

    async def propose(
        self, member: str, skill_name: str, *, executions: Mapping[str, str], instruction: str
    ) -> dict[str, Any]:
        owner = self.team.member_agent(member)
        evolution = owner.evolution
        if evolution is None:
            raise SessionStateError(
                "META_EVOLUTION_DISABLED", "Enable evolution on the owning member"
            )
        if not executions or not instruction.strip():
            raise ValueError("Team evolution requires executions and an improvement instruction")
        async with evolution._review_operation():
            evolution._skill(skill_name)
            if any(p["skill_name"] == skill_name for p in evolution.pending()):
                raise SessionConflict("META_PROPOSAL_PENDING", "Resolve the current proposal first")
            combined = None
            evidence = []
            for role, execution_id in executions.items():
                agent = self.team.member_agent(role)
                agent._ensure_evolution_idle()
                archive = agent._trajectories
                trajectories = archive.executions(execution_id) if archive is not None else []
                if not trajectories:
                    raise SessionStateError(
                        "META_TRAJECTORY_UNKNOWN", f"No captured execution for {role}"
                    )
                for trajectory in trajectories:
                    combined = (
                        trajectory if combined is None else merge_trajectories(combined, trajectory)
                    )
                evidence.append({"member": role, "execution_id": execution_id})
            messages, issues = project_trajectory_messages(combined)
            signal = make_team_user_intent_signal(skill_name=skill_name, user_intent=instruction)
            result: dict[str, Any] = await evolution._stage(
                skill_name, combined, messages, issues, [signal], user_query=instruction
            )
            result["team_evidence"] = evidence
            return result
