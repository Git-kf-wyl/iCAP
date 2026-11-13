"""Shared native tracing for remote export and optional local content archives."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openjiuwen.agent_evolving.trajectory.schema import CASE_ID
from openjiuwen.agent_evolving.trajectory.store import FileTrajectoryStore
from openjiuwen.agent_teams.observability.setup import (
    acquire_observability as acquire_team_observability,
)
from openjiuwen.agent_teams.observability.setup import (
    release_observability as release_team_observability,
)
from openjiuwen.extensions.observability.config import ObservabilityConfig
from openjiuwen.extensions.observability.demand import (
    acquire_observability_demand,
    get_trajectory_span_processor,
)
from openjiuwen.extensions.observability.setup import get_config, init_observability
from openjiuwen.harness.observability import (
    acquire_observability,
    install_root_span_fallback,
    is_tracing_enabled,
    release_observability,
)
from openjiuwen.harness.rails.evolution.trajectory_rail import TrajectoryRail
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from meta_agent.errors import BootError
from meta_agent.identity import ExecutionIdentity


class _NoExport(SpanExporter):
    """TrajectorySpanProcessor supplies the local archive; no second exporter."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS


_users = 0
_owned = False
_local_only = False
_team_demand = False


def acquire_team_tracing(config: ObservabilityConfig) -> None:
    """Keep Team monitoring alive until the shared MetaAgent provider is released."""
    global _team_demand
    acquire_tracing(config)
    try:
        if not _team_demand:
            acquire_team_observability(config)
            _team_demand = True
    except BaseException:
        release_tracing()
        raise


def acquire_tracing(config: ObservabilityConfig | None = None) -> Any:
    """Share one native provider; omitted/disabled config means local capture only."""
    global _users, _owned, _local_only
    remote = config if config is not None and config.enabled else None
    active = get_config()
    if remote is not None and active is not None and (active != remote or _local_only):
        raise BootError(
            "META_OBSERVABILITY_CONFLICT",
            "A different observability provider is active. Configure remote tracing on the "
            "first agent and reuse that configuration, or close existing tracing agents first.",
        )
    if not _users:
        _owned = not is_tracing_enabled()
        if _owned:
            config = remote or ObservabilityConfig(
                enabled=True,
                service_name="meta-agent",
                redact_prompts=False,
                redact_completions=False,
            )

            if remote is not None:
                acquire_observability(config)
            else:

                def initialize(config: Any, processors: Any) -> None:
                    init_observability(
                        config,
                        span_exporter_override=_NoExport() if active is None else None,
                        additional_span_processors=processors,
                    )
                    install_root_span_fallback()

                acquire_observability_demand(
                    "agent",
                    observability_config=config,
                    initializer=initialize,
                )
                acquire_observability(config)
            _local_only = remote is None and active is None
    _users += 1
    return get_trajectory_span_processor()


def release_tracing() -> None:
    global _users, _owned, _local_only, _team_demand
    _users -= 1
    if not _users and _owned:
        release_observability()
        _owned = False
        _local_only = False
    if not _users and _team_demand:
        # Team's finalizer also clears its monitor. Release it last so the
        # single-agent finalizer cannot leave a monitor bound to an old provider.
        release_team_observability()
        _team_demand = False


class TrajectoryArchive:
    """Correlate native archives to MetaAgent executions, without a new format."""

    def __init__(self, directory: Path, *, daily: bool) -> None:
        self.directory = directory
        self.store = FileTrajectoryStore(directory)
        self.daily = daily
        self.saved = 0
        self.errors = 0

    def rail(self, identity: Callable[[], ExecutionIdentity]) -> Any:
        archive = self

        class BoundStore:
            def save(self, trajectory: Any, version: str | None = None) -> None:
                current = identity()
                trajectory = trajectory.with_resource_attributes(
                    {
                        CASE_ID: current.execution_id,
                        "meta.product_id": current.product_id,
                        "meta.agent_id": current.agent_id,
                        "meta.session_id": current.session_id,
                        "meta.request_id": current.request_id,
                    }
                )
                if archive.daily:
                    version = datetime.now(UTC).strftime("%Y%m%d")
                try:
                    archive.store.save(trajectory, version)
                    archive.saved += 1
                except Exception:
                    archive.errors += 1
                    raise

        return TrajectoryRail(
            trajectory_span_processor=get_trajectory_span_processor(), trajectory_store=BoundStore()
        )

    def executions(self, execution_id: str) -> list[Any]:
        return [
            trajectory
            for path in sorted(self.directory.glob("trajectories_*.jsonl"))
            for trajectory in self.store.query(
                version=path.stem.removeprefix("trajectories_"), case_id=execution_id
            )
        ]

    def status(self) -> dict[str, Any]:
        return {
            "saved": self.saved,
            "errors": self.errors,
            "files": [
                {"name": p.name, "bytes": p.stat().st_size}
                for p in sorted(self.directory.glob("*.jsonl"))
            ],
        }
