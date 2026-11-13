"""Serve a trusted agent/team package through the MetaAgent worker."""

import argparse
import asyncio
import os

from aiohttp import web

from agentworker.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="Directory containing meta_agent.yaml or meta_team.yaml")
    parser.add_argument(
        "--state-dir", default=".artifacts/worker", help="Retained SQLite/runtime data"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--protocol", choices=["http", "a2a"], default="http")
    parser.add_argument("--callback-url", default=os.getenv("META_WORKER_CALLBACK_URL"))
    parser.add_argument("--durable", action="store_true", help="A2A: enable runtime recovery")
    parser.add_argument(
        "--postgres", action="store_true", help="A2A: share state using META_AGENT_POSTGRES_DSN"
    )
    parser.add_argument("--postgres-schema", default="meta_recovery")
    parser.add_argument("--agentgov-endpoint", default=os.getenv("META_AGENTGOV_ENDPOINT"))
    args = parser.parse_args()
    if args.postgres and (args.protocol != "a2a" or not args.durable):
        parser.error("--postgres requires --protocol a2a --durable")
    dsn = os.getenv("META_AGENT_POSTGRES_DSN") if args.postgres else None
    if args.postgres and not dsn:
        parser.error("--postgres requires META_AGENT_POSTGRES_DSN")
    if args.protocol == "a2a":
        import uvicorn

        from agentworker.a2a_server import WorkerServer, create_a2a_app
        from meta_agent_adapter.agentgov import AgentGovConfig

        token = os.getenv("META_WORKER_TOKEN", "")
        if not token.strip() or not args.callback_url:
            parser.error(
                "A2A requires META_WORKER_TOKEN and --callback-url/META_WORKER_CALLBACK_URL"
            )
        gov = None
        if args.agentgov_endpoint:
            key = os.getenv("META_AGENTGOV_API_KEY", "")
            if not key:
                parser.error("AgentGov requires META_AGENTGOV_API_KEY")
            gov = AgentGovConfig(endpoint=args.agentgov_endpoint, api_key=key)
        app = create_a2a_app(
            args.package,
            args.state_dir,
            callback_url=args.callback_url,
            token=token,
            durable=args.durable,
            postgres_dsn=dsn,
            postgres_schema=args.postgres_schema,
            agentgov=gov,
        )
        asyncio.run(WorkerServer(uvicorn.Config(app, host=args.host, port=args.port)).serve())
        return
    web.run_app(
        create_app(args.package, args.state_dir),
        host=args.host,
        port=args.port,
        handler_cancellation=True,
    )


if __name__ == "__main__":
    main()
