"""Run a MetaBaseAgent DAG through OpenJiuwen's serialized harness protocol."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import asdict, replace
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

from openjiuwen.agent_teams import ExternalTeamClient, TeamJoinDescriptor
from openjiuwen.agent_teams.rails.team_permission_rail import (
    TeamApprovalOrchestrator,
    TeamPermissionRail,
)
from openjiuwen.core.foundation.tool import Tool, ToolCard
from openjiuwen.harness.schema.deep_agent_spec import register_tool_provider
from openjiuwen.harness.security.permission_engine.host import ToolPermissionHost
from openjiuwen.harness_protocol import (
    CheckpointReason,
    HarnessCapability,
    HarnessCard,
    HarnessContext,
    HarnessInput,
    InteractionResponseStatus,
    OutputEvent,
    OutputKind,
    ToolInvocation,
    TurnEventKind,
    TurnResult,
    TurnStatus,
    UserInputRequest,
    json_value_to_builtin,
)
from openjiuwen.harness_providers.base import PendingTurn, SerializedTurnHarness
from openjiuwen.harness_providers.inputs import harness_input_text

from meta_agent.base_agent import MetaBaseAgent
from meta_agent.boot.boot_loader import LoadedPackage
from meta_agent.checkpoint import EffectAdapter, LocalRecovery, OperationScope
from meta_agent.checkpoint.adapters import BoundEffectTool
from meta_agent.checkpoint.native import NATIVE_RUN
from meta_agent.errors import SessionStateError
from meta_agent.spec import MetaAgentSpec

PROVIDER = "meta_agent"
BINDING_ENV = "META_AGENT_TEAM_BINDING"
LEADER_ENV = "META_AGENT_TEAM_LEADER"
TASKS_ENV = "META_AGENT_TEAM_TASKS"
TEAM_TOOLS = frozenset({"build_team", "send_message", "list_members", "approve_tool"})
TEAM_TASK_TOOLS = frozenset(
    {"create_task", "update_task", "view_task", "claim_task", "member_complete_task", "verify_task"}
)
# Live, host-owned bindings keep model credentials out of serialized team specs.
PACKAGES: dict[str, LoadedPackage] = {}
HARNESSES: dict[str, list[MetaAgentHarness]] = {}
RECOVERIES: dict[str, LocalRecovery] = {}
TRACE_CONTEXTS: dict[str, dict[str, str]] = {}
KEEPALIVE: set[str] = set()
_TOOLS: dict[str, Tool] = {}


def scoped_id(*parts: str) -> str:
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def bound_tool(params: dict[str, Any], context: Any) -> Tool:
    return _TOOLS[params["binding"]]


register_tool_provider("meta_agent.team_tool", bound_tool)


class GatewayTool(Tool):  # type: ignore[misc]
    def __init__(self, card: Any, gateway: Any) -> None:
        super().__init__(card)
        self.gateway = gateway

    async def invoke(self, inputs: dict[str, Any], **kwargs: Any) -> Any:
        result = await self.gateway.invoke(
            ToolInvocation(call_id=uuid4().hex, name=self.card.name, arguments=inputs)
        )
        if result.is_error:
            raise RuntimeError(str(result.content))
        return json_value_to_builtin(result.content)

    async def stream(self, inputs: dict[str, Any], **kwargs: Any) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, **kwargs)


class ClientTool(Tool):  # type: ignore[misc]
    def __init__(self, card: Any, tool: Any, client: Any) -> None:
        super().__init__(card)
        self.tool, self.client = tool, client

    async def invoke(self, inputs: dict[str, Any], **kwargs: Any) -> Any:
        self.client.bind_session_context()
        result = await self.tool.invoke(inputs, member_name=self.client.member_name)
        return self.tool.render_for_llm(result)

    async def stream(self, inputs: dict[str, Any], **kwargs: Any) -> AsyncIterator[Any]:
        yield await self.invoke(inputs, **kwargs)


def coordination_adapter(tool: Tool) -> EffectAdapter:
    """One coordination operation of each kind per member execution, journalled once.

    The native mailbox has no deduplicating RPC contract here. An unknown outcome
    stays unresolved; recovery must never resend it speculatively.
    """

    async def invoke(call: Any, arguments: dict[str, Any]) -> dict[str, Any]:
        token = NATIVE_RUN.set(None)
        try:
            return {"result": await tool.invoke(arguments)}
        finally:
            NATIVE_RUN.reset(token)

    return EffectAdapter("meta-team." + tool.card.name, "1", invoke)


class MetaAgentHarness(SerializedTurnHarness):  # type: ignore[misc]
    card = HarnessCard(
        name=PROVIDER,
        implementation_version="0.1.0",
        capabilities=frozenset({HarnessCapability.NATIVE_TOOLS, HarnessCapability.FORCE_ABORT}),
    )

    def __init__(self, binding: str, env: Mapping[str, str] | None = None) -> None:
        super().__init__()
        self.binding = binding
        if binding not in PACKAGES:
            raise SessionStateError(
                "META_TEAM_BINDING_EXPIRED", "Recreate MetaAgentTeam with its member packages first"
            )
        self.package = PACKAGES[binding]
        self.join_env = env
        self.agent: MetaBaseAgent | None = None
        self.client: Any = None
        self.results: list[dict[str, Any]] = []
        self.tool_bindings: list[str] = []
        self._context_updates: list[str] = []
        self.recovery = RECOVERIES.get(binding)
        self.pending: dict[str, Any] | None = None
        self._resume_execution = False
        self._turn_task: asyncio.Task[tuple[Any, Any]] | None = None
        self._restore_waiter: asyncio.Future[dict[str, Any]] | None = None
        self._started = asyncio.Event()
        self._start_error: BaseException | None = None
        self.before_resume: Callable[[], Awaitable[None]] | None = None
        HARNESSES.setdefault(binding, []).append(self)

    async def start(self, context: HarnessContext) -> None:
        try:
            await super().start(context)
        except BaseException as error:
            self._start_error = error
            raise
        finally:
            self._started.set()

    @property
    def pending_approval_id(self) -> str | None:
        """Only native Leader-mediated tool approvals are a member handoff seam."""
        if self.pending is None or self.client is None or not self.package.spec.permissions.enabled:
            return None
        question = self.pending["interactions"][0]
        value = question.get("value")
        nested = value.get("interactions", []) if isinstance(value, dict) else []
        if len(nested) != 1:
            return None
        approval = nested[0].get("value", {})
        call_id = approval.get("tool_call_id")
        return call_id if isinstance(call_id, str) and call_id == nested[0]["id"] else None

    async def restore_pending_turn(self, saved: dict[str, Any]) -> None:
        """Wake the saved execution before the Leader can deliver its approval."""
        await self._started.wait()
        if self._start_error is not None:
            raise self._start_error
        if not self._resume_execution:
            raise SessionStateError("META_TEAM_MEMBER_RESUME", "Member has no suspended execution")
        waiter = asyncio.get_running_loop().create_future()
        self._restore_waiter = waiter
        try:
            await self.send(HarnessInput(content="Resume the suspended MetaAgent execution."))
            restored = await waiter
        finally:
            self._restore_waiter = None
        if (
            restored["identity"]["execution_id"] != saved["identity"]["execution_id"]
            or restored["interactions"] != saved["interactions"]
            or self.pending_approval_id is None
        ):
            raise SessionStateError("META_TEAM_MEMBER_RESUME", "Stored member approval changed")

    async def _open_session(self, context: HarnessContext) -> str:
        if context.mcp_servers:
            raise ValueError("Platform MCP support is not configured for this local team")
        identity = scoped_id(context.host_session_id, context.agent_id)
        if self.binding in KEEPALIVE:
            previous = next((h for h in HARNESSES[self.binding] if h.agent is not None), None)
            if previous is not None:
                self.agent, self.client = previous.agent, previous.client
                self.tool_bindings = previous.tool_bindings
                if previous is not self:
                    previous.agent, previous.client, previous.tool_bindings = None, None, []
                if context.tools is not None:
                    for binding in self.tool_bindings:
                        tool = _TOOLS[binding]
                        if isinstance(tool, GatewayTool):
                            tool.gateway = context.tools
                return identity
        spec = self.package.spec.model_dump(mode="python")
        native = spec["deep_agent"]
        native["card"]["id"] = "team-" + identity
        native["workspace"]["root_path"] += "/team-" + identity
        prompt = native.get("system_prompt") or ""
        native["system_prompt"] = str(prompt) + "\n" + context.system_prompt
        mounted: list[Tool] = []
        permission_factory = None
        if context.tools is not None:
            for definition in await context.tools.definitions():
                if definition.name not in TEAM_TOOLS | TEAM_TASK_TOOLS:
                    continue
                card = ToolCard(
                    id=f"team-{identity}-{definition.name}",
                    name=definition.name,
                    description=definition.description,
                    input_params=json_value_to_builtin(definition.input_schema),
                )
                mounted.append(GatewayTool(card, context.tools))
        elif self.join_env is not None:
            self.client = ExternalTeamClient(TeamJoinDescriptor.from_env(self.join_env))
            await self.client.connect()
            if self.package.spec.permissions.enabled:
                orchestrator = TeamApprovalOrchestrator(
                    self.client.tools["send_message"].message_manager,
                    self.join_env[LEADER_ENV],
                )

                def permission_factory() -> Any:
                    return TeamPermissionRail(
                        config=self.package.spec.permissions.native_config(),
                        host=ToolPermissionHost(
                            request_permission_confirmation=orchestrator.handle_approval_request
                        ),
                    )

            for name, tool in self.client.tools.items():
                allowed = TEAM_TOOLS | (
                    TEAM_TASK_TOOLS if self.join_env.get(TASKS_ENV) == "1" else frozenset()
                )
                if name not in allowed:
                    continue
                card = tool.card.model_copy(update={"id": f"team-{identity}-{name}"})
                mounted.append(ClientTool(card, tool, self.client))
        for tool in mounted:
            binding = scoped_id(self.binding, identity, tool.card.name)
            self.tool_bindings.append(binding)
            _TOOLS[binding] = tool
            native.setdefault("tools", [])
            if native["tools"] is None:
                native["tools"] = []
            native["tools"].append({"type": "meta_agent.team_tool", "params": {"binding": binding}})
        recovery = self.recovery
        if recovery is not None:
            adapters = []
            for tool, binding in zip(mounted, self.tool_bindings, strict=True):
                if tool.card.name == "list_members":
                    continue
                adapter = coordination_adapter(tool)
                adapters.append(adapter)
                _TOOLS[binding] = BoundEffectTool(tool.card, adapter, "team." + tool.card.name)
            recovery = replace(
                recovery,
                adapters=(*recovery.adapters, *adapters),
                read_only_tools=(*recovery.read_only_tools, "list_members"),
            )
        try:
            self.agent = await MetaBaseAgent.create(
                MetaAgentSpec.model_validate(spec),
                package_digest=self.package.digest,
                plugins=self.package.plugins,
                permission_rail_factory=permission_factory,
                recovery=recovery,
                team_trace=TRACE_CONTEXTS.get(self.binding),
            )
            if recovery is not None:
                saved = await recovery.store.runtime_state(
                    OperationScope(self.agent.spec.product_id, self.agent.spec.agent_id, identity)
                )
                self._resume_execution = saved is not None and saved["status"] != "completed"
                # The protocol pointer is an identity only; LocalRecovery owns the bytes.
                self._restored_checkpoint_data(context)
                await self._publish_checkpoint(
                    {"session_id": identity}, reason=CheckpointReason.SESSION_ACTIVATED
                )
        except BaseException:
            await self._close_session()
            raise
        return identity

    async def _close_session(self) -> None:
        # Native pause ends a coordination cycle. The containing local Team
        # still owns the DAG, its conversations, plugins and evolution proposals.
        if self.binding in KEEPALIVE:
            return
        try:
            if self.agent is not None:
                await self.agent.aclose()
                self.agent = None
        finally:
            if self.client is not None:
                await self.client.close()
                self.client = None
            for binding in self.tool_bindings:
                _TOOLS.pop(binding, None)
            self.tool_bindings.clear()

    async def close_member(self) -> None:
        """Release the Team-owned DAG when the host closes the whole context."""
        KEEPALIVE.discard(self.binding)
        await self._close_session()

    async def _execute_turn(self, turn: PendingTurn) -> tuple[Any, Any]:
        self._turn_task = asyncio.create_task(self._execute_meta_turn(turn))
        try:
            return await self._turn_task
        except asyncio.CancelledError:
            if not (turn.abort_requested or turn.stop_requested):
                raise
            return TurnEventKind.ABORTED, TurnResult(status=TurnStatus.ABORTED)
        except Exception as error:
            if self._restore_waiter is not None and not self._restore_waiter.done():
                self._restore_waiter.set_exception(error)
            raise
        finally:
            self._turn_task = None

    async def _interrupt_turn(self, turn: PendingTurn, mode: Any) -> None:
        if self._turn_task is not None:
            self._turn_task.cancel()
            await asyncio.gather(self._turn_task, return_exceptions=True)

    async def _execute_meta_turn(self, turn: PendingTurn) -> tuple[Any, Any]:
        assert self.agent is not None
        session_id = str(self.provider_session_id)
        query = harness_input_text(turn.content)
        # Native coordination announces identity/roster before delivering work.
        # Retain those updates for the next request without scheduling a DAG turn.
        try:
            envelope = ElementTree.fromstring("<input>" + query + "</input>")
        except ElementTree.ParseError:
            envelope = None
        if (
            envelope is not None
            and len(envelope) > 0
            and not (envelope.text or "").strip()
            and all(
                not (node.tail or "").strip()
                and (
                    node.tag in {"team-context", "team-clock"}
                    or (node.tag == "team-event" and node.get("kind") == "roster")
                )
                for node in envelope
            )
        ):
            self._context_updates.append(query)
            return TurnEventKind.FINISHED, TurnResult(status=TurnStatus.COMPLETED, final_output="")
        query = "\n\n".join([*self._context_updates, query])
        self._context_updates.clear()
        restored_question = self._resume_execution
        if self._resume_execution:
            if self.before_resume is not None:
                await self.before_resume()
                self.before_resume = None
            result = await self.agent.resume(session_id=session_id, request_id=turn.turn_id)
            self._resume_execution = False
        else:
            result = await self.agent.invoke(query, session_id=session_id, request_id=turn.turn_id)
        if self._restore_waiter is not None and result.result_type != "input_required":
            raise SessionStateError(
                "META_TEAM_MEMBER_RESUME", "Member did not restore its approval"
            )
        usage: dict[str, int] = {}
        while result.result_type == "input_required":
            self.pending = asdict(result)
            if self.recovery is None:
                for name, count in result.usage.items():
                    if not name.startswith("goal_"):
                        usage[name] = usage.get(name, 0) + count
                self.pending["usage"] = {**result.usage, **usage}
            if restored_question:
                # Re-emitting an already-accounted question does no new model work.
                self.pending["usage"] = {}
                restored_question = False
            if self._restore_waiter is not None and not self._restore_waiter.done():
                self._restore_waiter.set_result(self.pending)
            question = result.interactions[0]
            interaction_id = question["id"]
            if self.client is not None and self.package.spec.permissions.enabled:
                # The DAG wraps the native interrupt under component "deep".
                # Team approve_tool addresses the original tool call ID.
                value = question.get("value")
                ids = value.get("interrupt_ids", []) if isinstance(value, dict) else []
                if len(ids) == 1:
                    interaction_id = ids[0]
            response = await self._request_interaction(
                UserInputRequest(
                    request_id=interaction_id,
                    prompt=json.dumps(question, ensure_ascii=False),
                    provider_session_id=session_id,
                    turn_id=turn.turn_id,
                )
            )
            if (
                turn.stop_requested
                or turn.abort_requested
                or response is None
                or response.status != InteractionResponseStatus.COMPLETED
            ):
                return TurnEventKind.ABORTED, TurnResult(status=TurnStatus.ABORTED)
            answer = json_value_to_builtin(response.content)
            self.pending = None
            if self.recovery is not None:
                result = await self.agent.resume(
                    session_id=session_id, request_id=uuid4().hex, answer=answer
                )
            else:
                result = await self.agent.invoke(
                    answer, session_id=session_id, request_id=uuid4().hex
                )
        self.pending = None
        if usage:
            result = replace(
                result,
                usage={
                    **result.usage,
                    **{name: value + result.usage.get(name, 0) for name, value in usage.items()},
                },
            )
        self.results.append(asdict(result))
        if result.result_type == "error":
            raise RuntimeError(str(result.error))
        output = result.output
        # Fast paths have no model to call the native reply tool. Return their
        # result to the single message sender through the same native mailbox.
        if self.client is not None and result.usage.get("deep_agent_calls") == 0:
            try:
                inbound = ElementTree.fromstring("<input>" + query + "</input>").findall(
                    "team-inbound"
                )
            except ElementTree.ParseError:
                inbound = []
            senders = {node.attrib.get("from") for node in inbound}
            if len(senders) == 1 and (sender := next(iter(senders))):
                await self.client.send_message(sender, output)
        await self._emit(
            OutputEvent(output_id=turn.turn_id, kind=OutputKind.TEXT, content=str(output)),
            turn=turn,
        )
        return TurnEventKind.FINISHED, TurnResult(status=TurnStatus.COMPLETED, final_output=output)


class MetaAgentHarnessProvider:
    card = MetaAgentHarness.card

    def create(self, config: Mapping[str, Any]) -> MetaAgentHarness:
        env = config.get("env", {})
        binding = env[BINDING_ENV]
        if binding.startswith("{"):
            binding = json.loads(binding)[TeamJoinDescriptor.from_env(env).member_name]
        return MetaAgentHarness(binding, env)
