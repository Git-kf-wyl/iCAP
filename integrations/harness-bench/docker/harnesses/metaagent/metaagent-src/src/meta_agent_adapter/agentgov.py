"""AgentGov registration lifecycle; HTTP paths follow the local design contract."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Self

import httpx
from pydantic import Field, model_validator

from meta_agent.spec.platform import EndpointConfig

logger = logging.getLogger(__name__)


class AgentGovConfig(EndpointConfig):
    interval_s: float = Field(default=30, gt=0)
    ttl_s: float = Field(default=90, gt=0)
    timeout_s: float = Field(default=10, gt=0)

    @model_validator(mode="after")
    def check_ttl(self) -> Self:
        if self.ttl_s <= self.interval_s:
            raise ValueError("AgentGov ttl_s must exceed interval_s")
        return self


class AgentGovClient:
    def __init__(self, config: AgentGovConfig, registration: dict[str, Any]) -> None:
        self.config = config
        self.registration = registration
        self.instance_id = registration["instance"]["instance_id"]
        self.registered = False
        self.last_error: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._http = httpx.AsyncClient(
            base_url=config.endpoint + "/",
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=config.timeout_s,
        )

    def start(self, listener_ready: Callable[[], Awaitable[bool]]) -> None:
        self._task = asyncio.create_task(self._run(listener_ready))

    async def _run(self, listener_ready: Callable[[], Awaitable[bool]]) -> None:
        while True:
            try:
                if not await listener_ready():
                    self.registered = False
                    self.last_error = "ListenerUnavailable"
                    await asyncio.sleep(min(1, self.config.interval_s))
                    continue
                if not self.registered:
                    response = await self._http.post("v1/agents/register", json=self.registration)
                    response.raise_for_status()
                    if response.json().get("registered") is not True:
                        raise ValueError("Registration was not acknowledged")
                else:
                    response = await self._http.put(
                        f"v1/agents/{self.instance_id}/heartbeat", json={"ready": True}
                    )
                    response.raise_for_status()
                self.registered = True
                self.last_error = None
            except (httpx.HTTPError, ValueError) as error:
                self.registered = False
                # Do not put response bodies, URLs or credentials into health output.
                self.last_error = type(error).__name__
                logger.warning("AgentGov unavailable (%s)", self.last_error)
            await asyncio.sleep(self.config.interval_s)

    async def aclose(self) -> None:
        if self._http.is_closed:
            return
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        try:
            # Also remove a registration whose acknowledgement/heartbeat was lost.
            response = await self._http.delete(f"v1/agents/{self.instance_id}")
            response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning("AgentGov deregistration failed (%s)", type(error).__name__)
        finally:
            self.registered = False
            await self._http.aclose()
