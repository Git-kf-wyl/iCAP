"""Authenticated A2A worker using OpenJiuwen's pinned A2A SDK and card adapter."""

from __future__ import annotations

import hmac
import json
import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import uvicorn
from a2a.server.request_handlers import LegacyRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks.database_task_store import DatabaseTaskStore
from google.protobuf.json_format import MessageToDict
from openjiuwen.extensions.a2a.a2a_agentcard_adapter import A2AAgentCardAdapter
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from agentworker.a2a_executor import MetaAgentExecutor, WorkerContextBuilder
from agentworker.team import TeamWorker
from meta_agent import MetaBaseAgent
from meta_agent.boot import MetaBootLoader
from meta_agent.checkpoint import LocalRecovery, PostgresRecoveryStore, SQLiteRecoveryStore
from meta_agent.errors import BootError, MetaAgentError
from meta_agent_adapter.agentgov import AgentGovClient, AgentGovConfig


class PluginLoadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str = Field(min_length=1)


class PluginVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class HumanMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    target: str = Field(min_length=1)
    body: str = Field(min_length=1)


class HumanInboxQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    after: int = Field(default=0, ge=0)


class HumanToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: Literal["view_task", "claim_task", "member_complete_task", "verify_task"]
    arguments: dict[str, Any] = Field(default_factory=dict)


class BearerAuth:
    """Worker service identity: one AgentGov-to-worker bearer credential."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app, self.expected = app, ("Bearer " + token).encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != "/health":
            provided = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(provided, self.expected):
                response = JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_a2a_app(
    package: str | Path,
    state_dir: str | Path,
    *,
    callback_url: str,
    token: str,
    env: Mapping[str, str] | None = None,
    durable: bool = False,
    postgres_dsn: str | None = None,
    postgres_schema: str = "meta_recovery",
    agentgov: AgentGovConfig | None = None,
) -> Starlette:
    """One package/worker; optional PostgreSQL shares tasks and runtime recovery."""
    if postgres_dsn is not None and not durable:
        raise ValueError("PostgreSQL A2A storage requires durable=True")
    if not token.strip():
        raise ValueError("A2A worker requires META_WORKER_TOKEN")
    endpoint = urlsplit(callback_url)
    if (
        endpoint.scheme not in {"http", "https"}
        or not endpoint.hostname
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or endpoint.path.rstrip("/") != "/a2a/jsonrpc"
    ):
        raise ValueError("callback_url must be an HTTP(S) /a2a/jsonrpc/ endpoint")
    callback_url = callback_url.rstrip("/") + "/"
    state = Path(state_dir).resolve()
    variables = dict(os.environ if env is None else env)
    variables.setdefault("META_AGENT_WORKSPACE", str(state / "workspace"))
    variables.setdefault("META_AGENT_TRACE", str(state / "trace"))
    variables.setdefault("META_TEAM_STATE", str(state / "team"))
    variables.setdefault("META_TEAM_WORKSPACE", str(state / "workspace"))
    variables.setdefault("META_TEAM_TRACE", str(state / "trace"))
    recovery = (
        LocalRecovery(
            PostgresRecoveryStore(postgres_dsn, schema=postgres_schema)
            if postgres_dsn is not None
            else SQLiteRecoveryStore(state / "recovery.sqlite")
        )
        if durable
        else None
    )
    team_worker = (
        TeamWorker(
            package,
            env=variables,
            recovery=recovery,
        )
        if (Path(package) / "meta_team.yaml").is_file()
        else None
    )
    loaded = (
        team_worker.packages[team_worker.spec.leader]
        if team_worker is not None
        else MetaBootLoader(package, env=variables).load()
    )
    native_card = loaded.spec.deep_agent.card
    if team_worker is not None:
        native_card = native_card.model_copy(
            update={
                "id": team_worker.spec.team_name,
                "name": team_worker.spec.team_name,
                "description": "MetaAgent team: " + ", ".join(team_worker.spec.members),
            }
        )
    card = A2AAgentCardAdapter.to_a2a_agent_card(
        native_card, interface_url=callback_url, protocol_binding="JSONRPC"
    )
    assert card is not None
    card.version = version("meta-agent")

    @asynccontextmanager
    async def lifetime(app: Starlette) -> AsyncIterator[None]:
        state.mkdir(parents=True, exist_ok=True)
        engine = create_async_engine(
            recovery.store.sqlalchemy_url()
            if recovery is not None and isinstance(recovery.store, PostgresRecoveryStore)
            else "sqlite+aiosqlite:///" + (state / "a2a.sqlite").as_posix()
        )
        store = DatabaseTaskStore(engine)
        agent = None
        executor = None
        gov = None
        try:
            await store.initialize()
            agent = team_worker or await MetaBaseAgent.create(
                loaded.spec,
                package_digest=loaded.digest,
                plugins=loaded.plugins,
                recovery=recovery,
                plugin_catalog=state / "plugins.json",
            )
            executor = MetaAgentExecutor(
                agent,
                durable=durable,
                digest=team_worker.digest if team_worker is not None else loaded.digest,
            )
            # The SDK 1.0 default handler keeps idle producer/consumer tasks after
            # INPUT_REQUIRED and exposes no shutdown hook. Its public per-request
            # handler retains the same wire protocol and closes those resources.
            handler = LegacyRequestHandler(
                agent_executor=executor,
                task_store=store,
                agent_card=card,
                request_context_builder=WorkerContextBuilder(executor, store),
            )
            app.router.routes.extend(create_agent_card_routes(agent_card=card))
            app.router.routes.extend(
                create_jsonrpc_routes(
                    request_handler=handler, rpc_url="/a2a/jsonrpc/", enable_v0_3_compat=True
                )
            )
            app.state.agent = agent
            if agentgov is not None:
                gov = AgentGovClient(
                    agentgov,
                    {
                        "agent_card": MessageToDict(card),
                        "instance": {
                            "instance_id": uuid4().hex,
                            "callback_endpoint": callback_url,
                            "product": loaded.spec.product_id,
                            "mode": "teamworker" if team_worker is not None else "agentworker",
                            "meta_agent_version": version("meta-agent"),
                            "ready": True,
                        },
                        "heartbeat": {"interval_s": agentgov.interval_s, "ttl_s": agentgov.ttl_s},
                    },
                )
                app.state.gov = gov

                async def listener_ready() -> bool:
                    async with httpx.AsyncClient(timeout=agentgov.timeout_s) as client:
                        response = await client.get(
                            callback_url.replace("/a2a/jsonrpc/", "/health")
                        )
                        return response.status_code == 200

                gov.start(listener_ready)
            app.state.booted = True
            yield
        finally:
            app.state.booted = False
            if gov is not None:
                await gov.aclose()
            if executor is not None:
                await executor.aclose()
            if agent is not None:
                await agent.aclose()
            await engine.dispose()

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "up" if request.app.state.booted else "starting"})

    async def admin_health(request: Request) -> Response:
        gov = request.app.state.gov
        ready = request.app.state.booted and (gov is None or gov.registered)
        return JSONResponse(
            {
                "status": "ready" if ready else "degraded",
                "agent_id": team_worker.spec.team_name if team_worker else loaded.spec.agent_id,
                "kind": "team" if team_worker else "agent",
                "agentgov": "disabled"
                if gov is None
                else ("registered" if gov.registered else "degraded"),
                "registration_error": gov.last_error if gov is not None else None,
                "durable": durable,
                "ops": None if team_worker else request.app.state.agent.observability()["ops"],
            },
            status_code=200 if ready else 503,
        )

    async def dag(request: Request) -> Response:
        return PlainTextResponse(request.app.state.agent.draw())

    async def plugins(request: Request) -> Response:
        return JSONResponse(request.app.state.agent.list_plugins())

    async def mutate_plugin(request: Request) -> Response:
        agent = request.app.state.agent
        try:
            name = request.path_params.get("name", "")
            action = request.path_params.get("action", "load")
            if request.method == "DELETE":
                body = PluginVersionRequest.model_validate(dict(request.query_params))
                await agent.unload_plugin(name, body.version)
            elif action == "deactivate":
                await agent.deactivate_plugin(name)
            elif action in {"activate", "rollback"}:
                body = PluginVersionRequest.model_validate(await request.json())
                await agent.activate_plugin(name, body.version)
            elif not name:
                load = PluginLoadRequest.model_validate(await request.json())
                await agent.load_plugin(load.path)
            else:
                return JSONResponse({"error": {"code": "META_PLUGIN_ACTION"}}, status_code=404)
            return JSONResponse(agent.list_plugins())
        except (ValidationError, json.JSONDecodeError, UnicodeError):
            return JSONResponse({"error": {"code": "META_HTTP_INPUT"}}, status_code=400)
        except MetaAgentError as error:
            return JSONResponse(
                {"error": {"code": error.code, "message": error.message}},
                status_code=400 if isinstance(error, BootError) else 409,
            )

    async def stats(request: Request) -> Response:
        return JSONResponse(request.app.state.agent.route_stats())

    async def observation(request: Request) -> Response:
        return JSONResponse(request.app.state.agent.observability())

    async def traces(request: Request) -> Response:
        root = Path(loaded.spec.trace.file_dir)
        return JSONResponse(
            [
                {"name": p.name, "bytes": p.stat().st_size}
                for p in sorted(root.glob("*.jsonl"))
                if p.is_file()
            ]
        )

    async def team_status(request: Request) -> Response:
        assert team_worker is not None
        return JSONResponse(team_worker.inspect())

    async def team_reload(request: Request) -> Response:
        assert team_worker is not None
        try:
            return JSONResponse(team_worker.reload())
        except (ValidationError, OSError, ValueError):
            return JSONResponse({"error": {"code": "META_TEAM_CONFIG"}}, status_code=400)
        except MetaAgentError as error:
            return JSONResponse(
                {"error": {"code": error.code, "message": error.message}}, status_code=409
            )

    async def team_human(request: Request) -> Response:
        assert team_worker is not None
        session_id = request.path_params["session_id"]
        member = request.path_params["member"]
        try:
            if request.method == "GET":
                query = HumanInboxQuery.model_validate(dict(request.query_params))
                data = team_worker.human_inbox(session_id, member, after=query.after)
            elif request.url.path.endswith("/tools"):
                action = HumanToolRequest.model_validate(await request.json())
                data = await team_worker.human_tool(
                    session_id, member, action.name, action.arguments
                )
            else:
                body = HumanMessageRequest.model_validate(await request.json())
                data = await team_worker.human_message(session_id, member, body.target, body.body)
            return JSONResponse(data)
        except (ValidationError, json.JSONDecodeError, UnicodeError):
            return JSONResponse({"error": {"code": "META_HTTP_INPUT"}}, status_code=400)
        except MetaAgentError as error:
            return JSONResponse(
                {"error": {"code": error.code, "message": error.message}},
                status_code=404 if error.code in {"META_TEAM_CONTEXT", "META_TEAM_HUMAN"} else 409,
            )

    app = Starlette(
        lifespan=lifetime,
        routes=[
            Route("/health", health),
            Route("/admin/health", admin_health),
        ]
        + (
            [
                Route("/admin/team", team_status),
                Route("/admin/team/reload", team_reload, methods=["POST"]),
                Route("/admin/team/contexts/{session_id}/humans/{member}/inbox", team_human),
                Route(
                    "/admin/team/contexts/{session_id}/humans/{member}/messages",
                    team_human,
                    methods=["POST"],
                ),
                Route(
                    "/admin/team/contexts/{session_id}/humans/{member}/tools",
                    team_human,
                    methods=["POST"],
                ),
            ]
            if team_worker is not None
            else [
                Route("/admin/dag", dag),
                Route("/admin/plugins", plugins),
                Route("/admin/plugins", mutate_plugin, methods=["POST"]),
                Route("/admin/plugins/{name}/{action}", mutate_plugin, methods=["POST"]),
                Route("/admin/plugins/{name}", mutate_plugin, methods=["DELETE"]),
                Route("/admin/stats/router", stats),
                Route("/admin/stats/observability", observation),
                Route("/admin/trace/files", traces),
            ]
        ),
    )
    app.state.booted = False
    app.state.gov = None
    app.add_middleware(BearerAuth, token=token)
    return app


class WorkerServer(uvicorn.Server):
    """Deregister before Uvicorn drains connections and runs ASGI cleanup."""

    async def shutdown(self, sockets: Any = None) -> None:
        app = self.config.app
        assert isinstance(app, Starlette)
        app.state.booted = False
        if app.state.gov is not None:
            await app.state.gov.aclose()
        await super().shutdown(sockets=sockets)
