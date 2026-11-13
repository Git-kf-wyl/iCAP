"""M1 provider/member seam probe; this is not the production MetaAgentTeam.

The provider executes the real M1 Workflow DAG. JSON files plus SHA-256 are a
local immutable-reference experiment, not a remote configuration service. Fresh
processes explicitly bootstrap the registry; installed wheel discovery and cold
team recovery require separate acceptance tests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openjiuwen.agent_teams.context import reset_session_id, set_session_id
from openjiuwen.agent_teams.external.cli_agent.spawn import build_cli_runtime
from openjiuwen.agent_teams.external.member_runtime import ExternalHarnessMemberRuntime
from openjiuwen.agent_teams.schema.team import (
    ExternalCliAgentSpec,
    TeamRole,
    TeamRuntimeContext,
    TeamSpec,
)
from openjiuwen.agent_teams.tools.database import DatabaseConfig
from openjiuwen.core.runner import Runner
from openjiuwen.core.session.agent_team import Session as TeamSession
from openjiuwen.core.session.interaction.interactive_input import InteractiveInput
from openjiuwen.harness_protocol import (
    HarnessCard,
    HarnessContext,
    HarnessInput,
    HarnessStateError,
    OutputEvent,
    OutputKind,
    TurnEventKind,
    TurnResult,
    TurnStatus,
    UserInputRequest,
)
from openjiuwen.harness_providers import register_harness_provider, unregister_harness_provider
from openjiuwen.harness_providers.base import PendingTurn, SerializedTurnHarness
from openjiuwen.harness_providers.inputs import harness_input_text

PROVIDER_NAME = "metaagent_m1_probe"
REF_ENV = "METAAGENT_PROBE_CONFIG_REF"
DIGEST_ENV = "METAAGENT_PROBE_CONFIG_SHA256"


def scoped_session_id(prefix: str, host_session_id: str, agent_id: str) -> str:
    identity = json.dumps([host_session_id, agent_id], separators=(",", ":")).encode()
    return prefix + hashlib.sha256(identity).hexdigest()


@dataclass(frozen=True)
class ConfigReference:
    """The digest pins the exact bytes; the file path alone has no immutability."""

    path: str
    sha256: str

    @classmethod
    def write(cls, directory: Path, config: dict[str, Any]) -> ConfigReference:
        payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        digest = hashlib.sha256(payload).hexdigest()
        path = directory / f"{digest}.json"
        directory.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != payload:
                raise ValueError("Existing configuration bytes do not match their digest")
        else:
            with path.open("xb") as stream:
                stream.write(payload)
        return cls(str(path.resolve()), digest)

    def load(self) -> dict[str, Any]:
        payload = Path(self.path).read_bytes()
        if hashlib.sha256(payload).hexdigest() != self.sha256:
            raise ValueError("MetaAgent configuration digest mismatch")
        config = json.loads(payload)
        if not isinstance(config, dict) or set(config) - {
            "schema_version",
            "workspace",
            "ask_user",
        }:
            raise ValueError("Unknown MetaAgent probe configuration fields")
        if (
            type(config.get("schema_version")) is not int
            or config["schema_version"] != 1
            or not isinstance(config.get("workspace"), str)
            or not Path(config["workspace"]).is_absolute()
            or type(config.get("ask_user", False)) is not bool
        ):
            raise ValueError("Unsupported MetaAgent probe configuration")
        return config

    def env(self) -> dict[str, str]:
        return {REF_ENV: self.path, DIGEST_ENV: self.sha256}


class WorkflowProbeHarness(SerializedTurnHarness):
    """A real workflow-backed harness with deliberately narrow capabilities."""

    card = HarnessCard(name=PROVIDER_NAME, implementation_version="0.1.0-m1")

    def __init__(self, reference: ConfigReference) -> None:
        super().__init__()
        self.reference = reference
        self.config = reference.load()
        self.executions: list[dict[str, Any]] = []

    async def _open_session(self, context: HarnessContext) -> str:
        # Revalidate when a cycle starts, including after process reconstruction.
        self.config = self.reference.load()
        if context.mcp_servers:
            raise ValueError("M1 probe has no platform MCP bridge; refuse unhandled MCP servers")
        return scoped_session_id("provider-", context.host_session_id, context.agent_id)

    async def _close_session(self) -> None:
        return None

    async def _execute_turn(self, turn: PendingTurn) -> tuple[TurnEventKind, TurnResult]:
        context = self.context
        assert context is not None
        answer = None
        if self.config.get("ask_user"):
            response = await self._request_interaction(
                UserInputRequest(
                    request_id=f"ask-{turn.turn_id}",
                    prompt="Choose the local probe label",
                    provider_session_id=self.provider_session_id,
                    turn_id=turn.turn_id,
                )
            )
            answer = getattr(response, "content", None)
        dag_session_id = scoped_session_id("member-dag-", context.host_session_id, context.agent_id)
        execution = await execute_member_dag(
            Path(self.config["workspace"]), harness_input_text(turn.content), dag_session_id
        )
        record = {
            "agent_id": context.agent_id,
            "host_session_id": context.host_session_id,
            "provider_session_id": self.provider_session_id,
            "turn_id": turn.turn_id,
            "message_id": turn.message_id,
            "config_sha256": self.reference.sha256,
            "dag": execution,
            "interaction_answer": answer,
        }
        self.executions.append(record)
        content = json.dumps(record, sort_keys=True)
        await self._emit(
            OutputEvent(output_id=f"output-{turn.turn_id}", kind=OutputKind.TEXT, content=content),
            turn=turn,
        )
        return TurnEventKind.FINISHED, TurnResult(status=TurnStatus.COMPLETED, final_output=content)


class WorkflowProbeProvider:
    card = WorkflowProbeHarness.card

    def create(self, config: Mapping[str, Any]) -> WorkflowProbeHarness:
        allowed = {"cwd", "env", "inherit_process_env", "skills", "skill_conflict"}
        if set(config) - allowed or config.get("skills"):
            raise ValueError("Unsupported MetaAgent probe provider options")
        env = config.get("env", {})
        return WorkflowProbeHarness(ConfigReference(env[REF_ENV], env[DIGEST_ENV]))


async def execute_member_dag(workspace: Path, query: str, session_id: str) -> dict[str, Any]:
    """Use the sibling M1 DAG spike, never substitute a fake workflow runner."""
    from spikes.dag_harness import ProbeState, assemble, build_dag, make_spec

    state = ProbeState()
    spec = make_spec(workspace, state, responses=[])
    agent = assemble(spec, state)
    workflow = build_dag(agent, state, route="plugin", plugin_mode="success")
    result = await Runner.run_workflow(workflow, inputs={"query": query}, session=session_id)
    return {
        "state": result.state.value,
        "session_id": session_id,
        "result": result.result,
        "plugin_calls": state.plugin_calls,
        "deep_calls": state.deep_calls,
        "model_calls": len(state.model_calls),
        "final_outputs": state.final_outputs,
    }


def bootstrap_provider() -> None:
    register_harness_provider(PROVIDER_NAME, WorkflowProbeProvider)


async def build_member_runtime(
    spec: ExternalCliAgentSpec, *, host_session_id: str, member_id: str
) -> ExternalHarnessMemberRuntime:
    """Use the upstream public spawn builder with its actual generic config transport."""
    if spec.inject_mcp:
        raise ValueError("Platform MCP bridge is not implemented; inject_mcp must be False")
    unsupported = set(spec.model_dump(exclude_defaults=True)) - {
        "cli_agent",
        "env",
        "inject_mcp",
        "cwd",
    }
    if unsupported:
        raise ValueError(f"Unsupported MetaAgent probe CLI options: {sorted(unsupported)}")
    context = TeamRuntimeContext(
        role=TeamRole.TEAMMATE,
        member_name=member_id,
        cli_agent=spec.cli_agent,
        team_spec=TeamSpec(team_name="metaagent-m1-probe", display_name="MetaAgent M1 probe"),
        db_config=DatabaseConfig(connection_string=":memory:"),
    )
    token = set_session_id(host_session_id)
    try:
        runtime = await build_cli_runtime(
            context,
            inject_mcp=False,
            cwd=spec.cwd,
            extra_env=spec.env,
            member_agent_id=member_id,
        )
    finally:
        reset_session_id(token)
    if not isinstance(runtime, ExternalHarnessMemberRuntime):
        raise TypeError("Provider was not routed through ExternalHarnessMemberRuntime")
    return runtime


async def run_serialized_member(
    serialized_spec: str, *, host_session_id: str, member_id: str
) -> dict[str, Any]:
    spec = ExternalCliAgentSpec.model_validate_json(serialized_spec)
    async with AsyncExitStack() as cleanup:
        bootstrap_provider()
        cleanup.callback(unregister_harness_provider, PROVIDER_NAME)
        team_session = TeamSession(session_id=host_session_id, team_id="metaagent-m1-probe")
        cleanup.push_async_callback(team_session.post_run)
        runtime = await build_member_runtime(
            spec, host_session_id=host_session_id, member_id=member_id
        )
        cleanup.push_async_callback(runtime.stop)
        await team_session.pre_run()
        terminal = asyncio.get_running_loop().create_future()

        async def on_round(*, kind: str, round_id: str, result: TurnResult | None) -> None:
            if kind in {"finished", "failed", "aborted"} and not terminal.done():
                terminal.set_result((kind, round_id, result))

        await runtime.subscribe(on_round=on_round)
        await runtime.start(team_session=team_session)
        try:
            runtime.harness.events()
        except HarnessStateError:
            single_consumer = True
        else:
            raise AssertionError("Member runtime did not retain sole ownership of provider events")
        interaction_ids: list[str] = []
        outputs: list[str] = []

        async def collect_outputs() -> None:
            async for chunk in runtime.outputs():
                if chunk.type == "__interaction__":
                    interaction_ids.append(chunk.payload.id)
                    reply = InteractiveInput()
                    reply.update(chunk.payload.id, "approved-local-label")
                    await runtime.send(reply)
                elif chunk.type == "llm_output":
                    outputs.append(chunk.payload["content"])

        collector = asyncio.create_task(collect_outputs())

        async def cancel_collector() -> None:
            if not collector.done():
                collector.cancel()
            await asyncio.gather(collector, return_exceptions=True)

        cleanup.push_async_callback(cancel_collector)
        receipt = await runtime.send(HarnessInput(content="execute the member DAG"))
        assert receipt is not None
        kind, turn_id, result = await asyncio.wait_for(terminal, timeout=20)
        if (
            turn_id != receipt.turn_id
            or kind != "finished"
            or result is None
            or result.status is not TurnStatus.COMPLETED
        ):
            raise RuntimeError(f"Member adapter terminal failure: {kind}/{turn_id}/{result}")
        member_session_id = runtime.member_session.get_session_id()
        await runtime.stop()
        await asyncio.wait_for(collector, timeout=20)
        if len(outputs) != 1 or outputs[0] != result.final_output:
            raise RuntimeError(
                "Member must emit exactly one final answer matching its terminal result"
            )
        record = json.loads(outputs[0])
        return {
            "pid": os.getpid(),
            "record": record,
            "receipt": {"turn_id": receipt.turn_id, "message_id": receipt.message_id},
            "member_session_id": member_session_id,
            "terminal_kind": kind,
            "terminal_status": result.status.value,
            "output_count": len(outputs),
            "single_event_consumer": single_consumer,
            "interaction_ids": interaction_ids,
            "registration": "explicit bootstrap in this process",
        }


async def child_main(request: dict[str, Any]) -> dict[str, Any]:
    await Runner.start()
    try:
        return await run_serialized_member(**request)
    finally:
        await Runner.stop()


if __name__ == "__main__":
    # The parent test sends only JSON; no shell interpolation or SDK mocking.
    request = json.loads(sys.stdin.read())
    report = asyncio.run(child_main(request))
    print("METAAGENT_TEAM_PROBE=" + json.dumps(report, sort_keys=True))
