"""Share one managed Runner across local MetaAgent instances on one event loop.

Applications using this lifecycle must not independently start, stop, or
reconfigure the global OpenJiuwen Runner while a MetaAgent is alive. This module
does not claim to discover ownership of a Runner started by unrelated host code.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from openjiuwen.core.runner import Runner
from openjiuwen.core.runner.runner_config import RunnerConfig, get_runner_config
from openjiuwen.core.session.checkpointer import CheckpointerFactory
from openjiuwen.core.session.checkpointer.base import Checkpointer
from openjiuwen.core.session.checkpointer.checkpointer import CheckpointerConfig

from meta_agent.errors import RunnerLifecycleError


@dataclass
class _RunnerState:
    requested: CheckpointerConfig
    previous_config: RunnerConfig
    previous_checkpointer: Checkpointer
    users: int = 1
    cleanup_failed: bool = False


_state: _RunnerState | None = None
_lock: asyncio.Lock | None = None
_owner_loop: asyncio.AbstractEventLoop | None = None


def _lifecycle_lock() -> asyncio.Lock:
    global _lock, _owner_loop
    loop = asyncio.get_running_loop()
    if _owner_loop is not loop:
        if _state is not None or (_lock is not None and _lock.locked()):
            raise RunnerLifecycleError(
                "META_RUNNER_LOOP_CONFLICT", "Managed agents must share one event loop."
            )
        _owner_loop = loop
        _lock = asyncio.Lock()
    assert _lock is not None
    return _lock


async def _stop_owned_runner(state: _RunnerState) -> None:
    """Retain ownership and its config if the kernel cannot finish teardown."""
    global _state
    try:
        stopped = await Runner.stop()
        if not stopped:
            raise RunnerLifecycleError("META_RUNNER_STOP_FAILED", "Kernel shutdown failed.")
    except BaseException as error:
        state.cleanup_failed = True
        if isinstance(error, (asyncio.CancelledError, RunnerLifecycleError)):
            raise
        raise RunnerLifecycleError(
            "META_RUNNER_STOP_FAILED", "Kernel shutdown failed; managed ownership is retained."
        ) from error
    Runner.set_config(state.previous_config)
    CheckpointerFactory.set_default_checkpointer(state.previous_checkpointer)
    _state = None


async def _finish_cleanup(state: _RunnerState) -> asyncio.CancelledError | None:
    """Keep the lifecycle lock until teardown finishes despite caller cancellation.

    A bare shield would let the caller release the lock while shutdown continues.
    Delay cancellation propagation until the protected task actually finishes.
    """
    task = asyncio.create_task(_stop_owned_runner(state))
    cancelled: asyncio.CancelledError | None = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            cancelled = cancelled or error
    # Also propagates an internal teardown cancellation/error, retaining ownership.
    task.result()
    return cancelled


async def acquire_runner(checkpointer_config: CheckpointerConfig) -> None:
    """Start once, or share a live Runner with identical checkpoint settings."""
    global _state
    async with _lifecycle_lock():
        if _state is not None:
            if _state.cleanup_failed:
                raise RunnerLifecycleError(
                    "META_RUNNER_STOP_FAILED",
                    "Previous shutdown failed; retry release_runner before acquiring a new owner.",
                )
            if _state.requested != checkpointer_config:
                raise RunnerLifecycleError(
                    "META_RUNNER_CONFIG_CONFLICT",
                    "Live agents must use the same checkpoint configuration.",
                )
            _state.users += 1
            return
        previous_config = get_runner_config()
        previous_checkpointer = CheckpointerFactory.get_checkpointer()
        requested = checkpointer_config.model_copy(deep=True)
        Runner.set_config(RunnerConfig(distributed_mode=False, checkpointer_config=requested))
        _state = _RunnerState(requested, previous_config, previous_checkpointer, users=0)
        try:
            started = await Runner.start()
            if not started:
                raise RunnerLifecycleError("META_RUNNER_START_FAILED", "Kernel startup failed.")
        except BaseException as error:
            try:
                await _finish_cleanup(_state)
            except BaseException:
                # The startup failure stays primary; a failed cleanup retains state
                # so a fresh owner cannot run on partially initialized resources.
                error.add_note("Kernel cleanup also failed; managed Runner ownership is retained.")
            if not isinstance(error, Exception) or isinstance(error, RunnerLifecycleError):
                raise
            raise RunnerLifecycleError(
                "META_RUNNER_START_FAILED", "Kernel startup failed."
            ) from error
        _state.users = 1


async def release_runner() -> None:
    """Release one managed owner; the last owner shuts down shared resources."""
    global _state
    async with _lifecycle_lock():
        if _state is None:
            raise RunnerLifecycleError("META_RUNNER_NOT_OWNED", "No managed Runner is active.")
        if _state.users:
            _state.users -= 1
        if _state.users:
            return
        cancelled = await _finish_cleanup(_state)
        if cancelled is not None:
            raise cancelled
