"""Renew a session lease and stop dispatched work when ownership is lost."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TypeVar
from uuid import uuid4

from meta_agent.checkpoint.contracts import LeaseToken, OperationScope
from meta_agent.checkpoint.models import duration
from meta_agent.checkpoint.store import RecoveryStore
from meta_agent.errors import LeaseLost, StorageUnavailable

T = TypeVar("T")


class LeaseGuard:
    def __init__(self, store: RecoveryStore, scope: OperationScope, *, ttl: float = 30.0) -> None:
        self.store, self.scope, self.ttl = store, scope, duration(ttl)
        self.token: LeaseToken | None = None
        self._monitor: asyncio.Task[None] | None = None
        self._calls: set[asyncio.Task[object]] = set()
        self._failure: Exception | None = None
        self._closed = False

    @property
    def current(self) -> LeaseToken:
        if self._failure is not None:
            raise self._failure
        if self._closed or self.token is None:
            raise LeaseLost("META_LEASE_CLOSED", "Lease guard is not active")
        return self.token

    async def __aenter__(self) -> LeaseGuard:
        if self.token is not None or self._closed:
            raise RuntimeError("LeaseGuard is single-use")
        self.token = await self.store.acquire(self.scope, uuid4().hex, self.ttl)
        self._monitor = asyncio.create_task(self._renew())
        return self

    async def _renew(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.ttl / 3)
                self.token = await self.store.renew(self.current, self.ttl)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._failure = (
                error
                if isinstance(error, (LeaseLost, StorageUnavailable))
                else StorageUnavailable("META_LEASE_RENEWAL", "Lease renewal failed")
            )
            for call in tuple(self._calls):
                call.cancel()

    async def check(self) -> None:
        await self.store.check(self.current)
        # Renewal may have failed while the store read was in flight.
        _ = self.current

    async def run(self, call: Callable[[], Awaitable[T]]) -> T:
        await self.check()
        task = asyncio.ensure_future(call())
        self._calls.add(task)
        try:
            result = await task
            await self.check()
            return result
        except asyncio.CancelledError:
            if self._failure is not None:
                raise self._failure
            raise
        finally:
            self._calls.discard(task)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._monitor:
            self._monitor.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor
        calls = tuple(self._calls)
        for call in calls:
            call.cancel()
        if calls:
            await asyncio.gather(*calls, return_exceptions=True)
        if self.token:
            with suppress(LeaseLost):
                await self.store.release(self.token)

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        task = asyncio.create_task(self.aclose())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            task.result()
            raise
        except Exception:
            if exc is None:
                raise
