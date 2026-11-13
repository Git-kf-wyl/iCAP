"""Three local HTTP endpoints backed by the existing durable Agent runtime."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeVar

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from meta_agent import MetaBaseAgent
from meta_agent.boot import MetaBootLoader
from meta_agent.checkpoint import LocalRecovery, SQLiteRecoveryStore
from meta_agent.errors import (
    LeaseBusy,
    LeaseLost,
    MetaAgentError,
    OperationConflict,
    RecoveryConflict,
    RequestConflictError,
    SessionConflict,
    SessionStateError,
    SideEffectUnresolved,
    StorageUnavailable,
    UnsupportedCapabilityError,
)

AGENT = web.AppKey("agent", MetaBaseAgent)
logger = logging.getLogger(__name__)


class RequestIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: str = Field(min_length=1, pattern=r"\S")
    request_id: str = Field(min_length=1, pattern=r"\S")


class InvokeRequest(RequestIdentity):
    query: str = Field(min_length=1, pattern=r"\S")
    context: dict[str, Any] | None = None


class ResumeRequest(RequestIdentity):
    answer: Any = None


Body = TypeVar("Body", bound=BaseModel)


async def read_body(request: web.Request, schema: type[Body]) -> Body:
    try:
        return schema.model_validate(await request.json())
    except (ValidationError, json.JSONDecodeError, UnicodeDecodeError):
        raise web.HTTPBadRequest(
            text=json.dumps(
                {
                    "error": {
                        "code": "META_HTTP_INPUT",
                        "message": "Invalid JSON request or required fields",
                    }
                }
            ),
            content_type="application/json",
        ) from None


def error_response(status: int, code: str, message: str) -> web.Response:
    return web.json_response({"error": {"code": code, "message": message}}, status=status)


@web.middleware
async def errors(
    request: web.Request, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]
) -> web.StreamResponse:
    try:
        return await handler(request)
    except MetaAgentError as error:
        status = 500
        if isinstance(error, (LeaseLost, StorageUnavailable)):
            status = 503
        elif isinstance(
            error,
            (
                SessionConflict,
                RequestConflictError,
                LeaseBusy,
                RecoveryConflict,
                OperationConflict,
                SideEffectUnresolved,
            ),
        ):
            status = 409
        elif isinstance(error, (SessionStateError, UnsupportedCapabilityError)):
            status = 400
        return error_response(status, error.code, error.message)
    except web.HTTPException:
        raise
    except Exception:
        logger.exception("Agent request failed")
        return error_response(
            500, "META_HTTP_EXECUTION", "Agent execution failed; check worker logs"
        )


async def health(request: web.Request) -> web.Response:
    agent = request.app[AGENT]
    return web.json_response({"status": "ready", "agent_id": agent.spec.agent_id})


async def invoke(request: web.Request) -> web.Response:
    body = await read_body(request, InvokeRequest)
    result = await request.app[AGENT].invoke(
        body.query, session_id=body.session_id, request_id=body.request_id, context=body.context
    )
    return web.json_response(asdict(result))


async def resume(request: web.Request) -> web.Response:
    body = await read_body(request, ResumeRequest)
    result = await request.app[AGENT].resume(
        session_id=body.session_id, request_id=body.request_id, answer=body.answer
    )
    return web.json_response(asdict(result))


def create_app(
    package: str | Path,
    state_dir: str | Path,
    *,
    env: Mapping[str, str] | None = None,
    recovery: LocalRecovery | None = None,
) -> web.Application:
    """Own one Agent for the server lifetime. Custom hosts may supply effect bindings."""
    state = Path(state_dir).resolve()
    variables = dict(os.environ if env is None else env)
    variables.setdefault("META_AGENT_WORKSPACE", str(state / "workspace"))
    variables.setdefault("META_AGENT_TRACE", str(state / "trace"))
    loader = MetaBootLoader(package, env=variables)

    async def lifetime(app: web.Application) -> AsyncIterator[None]:
        policy = recovery or LocalRecovery(SQLiteRecoveryStore(state / "recovery.sqlite"))
        agent = await loader.boot(recovery=policy)
        app[AGENT] = agent
        try:
            yield
        finally:
            await agent.aclose()

    async def shutdown(app: web.Application) -> None:
        # Cancel active Agent work before waiting for HTTP handlers to drain.
        await app[AGENT].aclose()

    app = web.Application(middlewares=[errors])
    app.cleanup_ctx.append(lifetime)
    app.on_shutdown.append(shutdown)
    app.add_routes(
        [web.get("/health", health), web.post("/invoke", invoke), web.post("/resume", resume)]
    )
    return app
