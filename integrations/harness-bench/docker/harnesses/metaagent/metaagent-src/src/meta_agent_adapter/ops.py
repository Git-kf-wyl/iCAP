"""Best-effort Ops HTTP reports; the next interval replaces a failed report."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from meta_agent.spec.platform import OpsConfig

logger = logging.getLogger(__name__)


class OpsReporter:
    def __init__(
        self, config: OpsConfig, identity: dict[str, str], snapshot: Callable[[], dict[str, Any]]
    ) -> None:
        self.config, self.identity, self.snapshot = config, identity, snapshot
        self.failures = 0
        self.last_error: str | None = None
        self.reports = 0
        self._alerted_errors = 0
        self._task: asyncio.Task[None] | None = None
        self._http = httpx.AsyncClient(
            base_url=config.endpoint + "/",
            headers={"Authorization": f"Bearer {config.api_key}"},
            timeout=config.timeout_s,
        )

    def status(self) -> dict[str, Any]:
        return {"reports": self.reports, "failures": self.failures, "last_error": self.last_error}

    async def _post(self, kind: str, payload: dict[str, Any]) -> bool:
        try:
            response = await self._http.post(
                f"v1/ops/{kind}",
                json={
                    "schema_version": 1,
                    "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
                    **self.identity,
                    **payload,
                },
            )
            response.raise_for_status()
            self.reports += 1
            self.last_error = None
            return True
        except httpx.HTTPError as error:
            self.failures += 1
            self.last_error = type(error).__name__
            logger.warning("Ops report unavailable (%s)", self.last_error)
            return False

    async def start(self) -> None:
        try:
            await self._post("boot", self.snapshot())
        except OSError as error:
            self.failures += 1
            self.last_error = type(error).__name__
        self._task = asyncio.create_task(self._run())

    async def report_metrics(self) -> None:
        try:
            snapshot = self.snapshot()
        except OSError as error:
            self.failures += 1
            self.last_error = type(error).__name__
            return
        await self._post("metrics", snapshot)
        errors = snapshot["metrics"]["trace_errors"]
        if errors > self._alerted_errors and await self._post(
            "alerts", {"level": "warn", "source": "trace", "trace_errors": errors}
        ):
            self._alerted_errors = errors

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.config.report_interval_s)
            await self.report_metrics()

    async def aclose(self) -> None:
        if self._http.is_closed:
            return
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        try:
            await self.report_metrics()
        finally:
            await self._http.aclose()
