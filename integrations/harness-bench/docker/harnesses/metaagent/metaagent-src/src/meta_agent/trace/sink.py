"""Append metadata records; this observability file is not a recovery journal."""

import json
import math
import re
import threading
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, TextIO

from meta_agent.errors import TraceError
from meta_agent.identity import ExecutionIdentity

_EVENT = re.compile(r"[a-z][a-z0-9_.-]{0,95}\Z")
_FIELDS = frozenset(
    {
        "status",
        "skill_name",
        "proposal_id",
        "skill_version",
        "applied_count",
        "pending_count",
        "error_code",
        "error_type",
        "model_calls",
        "subagent_calls",
        "goal_attempts",
        "goal_tokens",
        "model_errors",
        "input_tokens",
        "output_tokens",
        "usage_reports",
        "trace_errors",
        "elapsed_ms",
        "duration_ms",
        "retry_attempt",
        "react_iteration",
        "child_session_id",
        "workflow_id",
        "graph_version",
        "package_digest",
        "tool_name",
        "gateway",
        "plugin",
        "plugin_version",
        "plugin_digest",
        "strategy",
        "confidence",
        "threshold",
        "cache_hit",
        "deep_agent_calls",
        "source_trace_id",
        "invoke_id",
        "parent_invoke_id",
        "loop_index",
        "component_id",
    }
)


class JsonlTraceSink:
    """Thread-safe within one process, append+flush per metadata record.

    Flush is not fsync and does not promise crash or power-loss durability.
    Constructor failures reject setup. Later failures are explicit TraceError
    exceptions; callers may degrade observability while counting the failure.
    Arbitrary payload fields are rejected rather than implicitly serialized.
    """

    def __init__(
        self,
        path: Path | None,
        *,
        rollout: Literal["none", "daily"] = "none",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._base_path = path
        self._rollout, self._clock = rollout, clock
        self._day = self._clock().astimezone(UTC).strftime("%Y%m%d")
        if path is not None and rollout == "daily":
            path = path.with_name(f"{path.stem}-{self._day}{path.suffix}")
        self.path = path
        self._lock = threading.Lock()
        self._stream: TextIO | None = None
        self._closed = False
        self._sequence = 0
        self.failed_writes = 0
        self._events: Counter[str] = Counter()
        self._totals: Counter[str] = Counter()
        self._duration_ms = 0.0
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self._stream = path.open("a", encoding="utf-8", newline="\n")
            except OSError as exc:
                raise TraceError("META_TRACE_OPEN_FAILED", "Could not open trace output") from exc

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "events": dict(self._events),
                "totals": {**self._totals, "duration_ms": self._duration_ms},
                "trace_errors": self.failed_writes,
                "written_events": self._sequence,
            }

    def files(self) -> list[dict[str, Any]]:
        if self._base_path is None:
            return []
        return [
            {"name": p.name, "bytes": p.stat().st_size}
            for p in sorted(self._base_path.parent.glob(f"{self._base_path.stem}*.jsonl"))
            if p.is_file()
        ]

    @staticmethod
    def _category(event: str) -> str:
        if event.startswith("evolution."):
            return "evolution"
        if event.startswith("model_"):
            return "llm"
        if event.startswith("tool_"):
            return "tool"
        if event.startswith("route."):
            return "route"
        if event.startswith("workflow."):
            return "workflow"
        return "lifecycle"

    def _rotate(self, now: datetime) -> None:
        day = now.strftime("%Y%m%d")
        if self._base_path is None or self._rollout != "daily" or day == self._day:
            return
        path = self._base_path.with_name(f"{self._base_path.stem}-{day}.jsonl")
        stream = path.open("a", encoding="utf-8", newline="\n")
        try:
            if self._stream is not None:
                self._stream.close()
        except OSError:
            stream.close()
            raise
        self._stream, self.path, self._day = stream, path, day

    def emit(self, event: str, identity: ExecutionIdentity, **fields: object) -> None:
        with self._lock:
            if self._closed:
                self.failed_writes += 1
                raise TraceError("META_TRACE_CLOSED", "Trace output is closed")
            if not _EVENT.fullmatch(event) or set(fields) - _FIELDS:
                raise TraceError("META_TRACE_INVALID_FIELDS", "Trace accepts metadata fields only")
            for value in fields.values():
                if not isinstance(value, (str, int, float, bool, type(None))) or (
                    isinstance(value, float) and not math.isfinite(value)
                ):
                    raise TraceError(
                        "META_TRACE_INVALID_FIELDS", "Trace metadata must contain finite scalars"
                    )
            self._events[event] += 1
            if event in {"execution.end", "execution.error", "execution.cancel"}:
                self._totals["requests"] += 1
                self._totals[str(fields.get("status", "unknown"))] += 1
                for key in ("input_tokens", "output_tokens", "model_calls", "usage_reports"):
                    value = fields.get(key, 0)
                    if isinstance(value, (int, float)):
                        self._totals[key] += int(value)
                duration = fields.get("duration_ms", 0)
                if isinstance(duration, (int, float)):
                    self._duration_ms += duration
            if self._stream is None:
                return
            now = self._clock().astimezone(UTC)
            record = {
                "schema_version": 2,
                "timestamp": now.isoformat(timespec="milliseconds"),
                "sequence": self._sequence + 1,
                "event": event,
                "category": self._category(event),
                "trajectory_id": sha256(
                    json.dumps(
                        [identity.product_id, identity.agent_id, identity.execution_id]
                    ).encode()
                ).hexdigest(),
                **identity.as_dict(),
                **fields,
            }
            try:
                self._rotate(now)
                line = json.dumps(
                    record, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                )
                self._stream.write(line + "\n")
                self._stream.flush()
            except (OSError, ValueError, TypeError) as exc:
                self.failed_writes += 1
                raise TraceError(
                    "META_TRACE_WRITE_FAILED", "Could not append trace metadata"
                ) from exc
            self._sequence += 1

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._stream is not None:
                try:
                    self._stream.close()
                except OSError as exc:
                    raise TraceError(
                        "META_TRACE_CLOSE_FAILED", "Could not close trace output"
                    ) from exc
