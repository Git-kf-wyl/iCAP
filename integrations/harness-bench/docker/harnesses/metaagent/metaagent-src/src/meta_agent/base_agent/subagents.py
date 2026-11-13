"""Host approvals for native child agents without replacing their scheduler."""

import asyncio
import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

from openjiuwen.harness.rails.security.tool_security_rail import PermissionInterruptRail
from openjiuwen.harness.security.permission_engine.host import ToolPermissionHost
from openjiuwen.harness.security.permission_engine.models import PermissionConfirmResponse

from meta_agent.errors import SessionStateError


class SubagentApprovals:
    def __init__(self) -> None:
        self.pending: dict[str, tuple[dict[str, Any], asyncio.Future[Any]]] = {}

    async def request(self, request: Any) -> Any:
        approval_id = uuid4().hex
        args = request.tool_call.arguments
        if isinstance(args, str):
            args = json.loads(args)
        value = {
            "approval_id": approval_id,
            "subagent_id": request.ctx.session.get_session_id(),
            "tool_call_id": request.tool_call.id,
            "tool_name": request.tool_call.name,
            "arguments": args,
        }
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self.pending[approval_id] = value, future
        try:
            return await future
        finally:
            self.pending.pop(approval_id, None)

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(value) for value, _ in self.pending.values()]

    def answer(self, approval_id: str, *, approved: bool, feedback: str = "") -> None:
        item = self.pending.get(approval_id)
        if item is None or item[1].done():
            raise SessionStateError(
                "META_SUBAGENT_APPROVAL", "No pending child approval with this ID"
            )
        item[1].set_result(PermissionConfirmResponse(approved=approved, feedback=feedback))


class SubagentPermissionRail(PermissionInterruptRail):  # type: ignore[misc]
    def __init__(self, config: dict[str, Any], approvals: SubagentApprovals) -> None:
        self.policy, self.approvals = config, approvals
        super().__init__(
            config=config,
            host=ToolPermissionHost(request_permission_confirmation=approvals.request),
        )

    def fork_for_agent(self) -> "SubagentPermissionRail":
        return SubagentPermissionRail(self.policy, self.approvals)
