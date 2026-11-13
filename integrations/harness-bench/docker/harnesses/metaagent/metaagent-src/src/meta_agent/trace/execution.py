"""MetaAgent execution and route metadata on the native OpenJiuwen span tree."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import time_ns
from typing import Any

from openjiuwen.agent_teams.observability.span_context import get_team_span
from openjiuwen.extensions.observability.redaction import redact_prompt
from openjiuwen.extensions.observability.setup import get_config, get_tracer
from openjiuwen.extensions.observability.span_context import (
    clear_root_span,
    set_current_session_id,
    set_root_span,
)
from openjiuwen.harness.observability import close_agent_run_span, open_agent_run_span
from openjiuwen.harness.observability.run_span import stamp_run_output
from openjiuwen.harness.observability.span_context import (
    register_run_root_span,
    unregister_run_root_span,
)
from opentelemetry.trace import Status, StatusCode, set_span_in_context, use_span

from meta_agent.identity import ExecutionIdentity
from meta_agent.routing import RouteDecision


def skill_manifest_digest(paths: list[str]) -> str:
    """Identify the configured Skill instructions without exporting their contents."""
    digest = hashlib.sha256()
    for index, directory in enumerate(paths):
        root = Path(directory)
        for path in sorted(root.rglob("SKILL.md")):
            digest.update(f"{index}/{path.relative_to(root).as_posix()}\0".encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class ExecutionTrace:
    def __init__(self, span: Any, session_id: str) -> None:
        self.span = span
        self.session_id = session_id
        self.fast_span: Any = None
        self.result: Any = None

    def route(self, decision: RouteDecision, *, resumed: bool = False) -> None:
        if self.span is None:
            return
        attributes = {f"meta.route.{k}": v for k, v in decision.as_dict().items() if v is not None}
        self.span.set_attributes(attributes)
        self.span.set_attribute("meta.path", "fastpath" if decision.matched else "main")
        if resumed:
            self.span.set_attribute("meta.resumed", True)
        now = time_ns()
        if not resumed:
            route = get_tracer("meta_agent").start_span(
                "meta.route",
                context=set_span_in_context(self.span),
                attributes=attributes,
                start_time=now - int(decision.latency_ms * 1_000_000),
            )
            route.set_attribute("gen_ai.conversation.id", self.session_id)
            route.end(end_time=now)
        if decision.matched:
            self.fast_span = get_tracer("meta_agent").start_span(
                f"meta.fastpath.{decision.plugin}",
                context=set_span_in_context(self.span),
                attributes={
                    **attributes,
                    "gen_ai.operation.name": "workflow",
                    "gen_ai.conversation.id": self.session_id,
                },
            )

    def outcome(self, name: str, status: str, code: str) -> None:
        if self.span is None:
            return
        attributes = {"meta.plugin": name, "meta.outcome": status, "meta.error_code": code}
        self.span.set_attributes(attributes)
        if self.fast_span is not None:
            self.fast_span.set_attributes(attributes)
            if status in {"failed", "terminal", "control"}:
                self.fast_span.set_status(Status(StatusCode.ERROR, code or status))
            self.fast_span.end()
            self.fast_span = None
        if status == "failed":
            self.span.set_attribute("meta.path", "fallback")
            with get_tracer("meta_agent").start_as_current_span(
                "meta.fallback",
                context=set_span_in_context(self.span),
                attributes={
                    **attributes,
                    "gen_ai.conversation.id": self.session_id,
                },
            ):
                pass


@contextmanager
def execution_trace(
    identity: ExecutionIdentity,
    inputs: Any,
    *,
    package_digest: str,
    skill_digest: str,
    team: dict[str, str],
) -> Iterator[ExecutionTrace]:
    parent = get_team_span(session_id=team["native_session_id"]) if team else None
    if parent is not None:
        # A member is a child of the Team root. Never close it with the single
        # Agent root helper: that helper flushes the whole trace, including peers.
        span = get_tracer("meta_agent").start_span(
            f"meta.member.{team['member']}",
            context=set_span_in_context(parent),
            attributes={
                "gen_ai.operation.name": "invoke_agent",
                "gen_ai.conversation.id": team["native_session_id"],
            },
        )
        set_root_span(span, session_id=identity.child_session_id)
        set_current_session_id(identity.child_session_id)
        register_run_root_span(span, session_id=identity.child_session_id)
        parent.set_attributes(
            {"meta.team.name": team["name"], "meta.team.session_id": team["session_id"]}
        )
    else:
        span = open_agent_run_span(
            session_id=identity.child_session_id,
            mode="meta-agent",
            request_id=identity.request_id,
            run_id=identity.execution_id,
        )
    run = ExecutionTrace(
        span, team["native_session_id"] if parent is not None else identity.child_session_id
    )
    error = None
    if span is not None:
        span.set_attributes(
            {
                **{f"meta.{k}": v for k, v in identity.as_dict().items()},
                "meta.package_digest": package_digest,
                "meta.skill_manifest_digest": skill_digest,
                "meta.path": "main",
                "openjiuwen.request.id": identity.request_id,
                "openjiuwen.run.id": identity.execution_id,
            }
        )
        if team:
            span.set_attributes({f"meta.team.{k}": v for k, v in team.items()})
        config = get_config()
        if config is not None:
            span.set_attribute("openjiuwen.span.input", redact_prompt(inputs, config))
    try:
        if span is None:
            yield run
        else:
            with use_span(
                span, end_on_exit=False, record_exception=False, set_status_on_exception=False
            ):
                yield run
    except BaseException as exc:
        error = exc
        raise
    finally:
        if run.fast_span is not None:
            run.fast_span.set_attribute("meta.outcome", "interrupted" if error else "paused")
            run.fast_span.end()
        output = run.result.output if run.result is not None else None
        if span is not None and run.result is not None:
            span.set_attribute("meta.result_type", run.result.result_type)
        if parent is None:
            close_agent_run_span(
                span, session_id=identity.child_session_id, output=output, exception=error
            )
        else:
            stamp_run_output(span, output, allow_empty=True)
            if error is not None:
                span.set_status(Status(StatusCode.ERROR, type(error).__name__))
            span.end()
            unregister_run_root_span(span, session_id=identity.child_session_id)
            clear_root_span(session_id=identity.child_session_id, expected_span=span)
            set_root_span(parent, session_id=team["native_session_id"])
            set_current_session_id(team["native_session_id"])
