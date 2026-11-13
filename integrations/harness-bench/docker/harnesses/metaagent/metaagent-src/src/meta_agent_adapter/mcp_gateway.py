"""Own native MCP connections, optionally routing them through a CSP gateway."""

import asyncio
from hashlib import sha256
from typing import Any

from openjiuwen.core.foundation.tool import McpServerConfig
from openjiuwen.core.runner import Runner

from meta_agent.spec.platform import McpGatewayConfig


class McpGatewayAdapter:
    def __init__(self, config: McpGatewayConfig | None = None) -> None:
        self.config = config
        self._close = asyncio.Event()
        self._owner: asyncio.Task[None] | None = None

    async def open(self, servers: list[Any]) -> None:
        """MCP's AnyIO scopes must be entered and exited by the same task."""
        if not servers:
            return
        ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()

        async def own_connections() -> None:
            registered = []
            try:
                for server in servers:
                    result = await Runner.resource_mgr.add_mcp_server(server)
                    if result.is_err():
                        raise result.msg()
                    registered.append(server.server_id)
                ready.set_result(None)
                await self._close.wait()
            except BaseException as error:
                if not ready.done():
                    ready.set_exception(error)
                else:
                    raise
            finally:
                for server_id in reversed(registered):
                    results = await Runner.resource_mgr.remove_mcp_server(server_id)
                    for result in results if isinstance(results, list) else [results]:
                        if result.is_err():
                            raise result.msg()

        self._owner = asyncio.create_task(own_connections())
        try:
            await asyncio.shield(ready)
        except BaseException:
            self._close.set()
            await self._owner
            raise

    async def aclose(self) -> None:
        self._close.set()
        if self._owner is not None:
            await self._owner

    def build_mcps(self, servers: list[Any], *, scope: str) -> list[Any]:
        result = []
        for server in servers:
            if self.config is None:
                # Preserve native transports, endpoints, headers and stdio args.
                result.append(
                    server.model_copy(
                        update={
                            "server_id": "meta-mcp-"
                            + sha256(f"{scope}/{server.server_id}".encode()).hexdigest()
                        }
                    )
                )
                continue
            headers = {"X-Meta-Mcp-Server": server.server_name}
            if self.config.api_key:
                headers["Authorization"] = "Bearer " + self.config.api_key
            result.append(
                McpServerConfig(
                    server_id="meta-gateway-"
                    + sha256(f"{scope}/{server.server_name}".encode()).hexdigest(),
                    server_name=server.server_name,
                    server_path=self.config.endpoint,
                    client_type="streamable-http",
                    auth_headers=headers,
                    include_image_content=server.include_image_content,
                )
            )
        return result
