"""Validate/draw trusted packages, or run a native Workflow/DeepAgent/Hybrid package."""

import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Native log handlers bind stdout during import. Keep CLI stdout machine-readable.
with redirect_stdout(sys.stderr):
    from meta_agent.boot import LoadedAgentPackage, LoadedWorkflowPackage, MetaPackageLoader
    from meta_agent.errors import MetaAgentError
    from meta_agent.orchestrator.fastpath import draw_dag
    from meta_agent.registry import MetaRegistry
    from meta_agent.workflow.ir import draw_workflow_ir


async def run(
    command: str,
    package: str,
    *,
    inputs: dict[str, Any] | None = None,
    session_id: str = "local",
    request_id: str | None = None,
) -> None:
    with redirect_stdout(sys.stderr):
        loaded = MetaPackageLoader(package).load()
    if isinstance(loaded, LoadedWorkflowPackage):
        await run_workflow(command, loaded, inputs or {}, session_id, request_id)
        return
    if isinstance(loaded, LoadedAgentPackage):
        await run_agent_package(command, loaded, inputs or {}, session_id, request_id)
        return
    if command == "run":
        raise MetaAgentError(
            "META_PACKAGE_MODE", "run requires a package.json with a supported meta_agent mode"
        )
    registry = MetaRegistry(
        loaded.plugins, loaded.spec.fastpath, loaded.spec.product_id, loaded.spec.agent_id
    )
    try:
        await registry.start()
        if command == "draw":
            print(draw_dag([p.manifest.name for p in loaded.plugins]), end="")
        else:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "package_digest": loaded.digest,
                        "graph_version": registry.graph_version,
                        "plugins": [
                            {
                                "name": p.manifest.name,
                                "version": p.manifest.version,
                                "digest": p.digest,
                            }
                            for p in loaded.plugins
                        ],
                    }
                )
            )
    finally:
        registry.close()


async def run_agent_package(
    command: str,
    loaded: LoadedAgentPackage,
    inputs: dict[str, Any],
    session_id: str,
    request_id: str | None,
) -> None:
    if command == "run":
        with redirect_stdout(sys.stderr):
            runtime = await loaded.boot()
            try:
                result = await runtime.invoke(inputs, session_id=session_id, request_id=request_id)
            finally:
                await runtime.close()
        print(json.dumps(asdict(result), ensure_ascii=False))
        return
    with redirect_stdout(sys.stderr):
        if loaded.workflow is not None and loaded.workflow.ir is None:
            loaded.workflow.build_workflow()
    if command == "draw":
        if loaded.spec.mode == "hybrid":
            print(
                'flowchart LR\n  input --> router["FastPathRouter: one decision"]\n'
                '  router -->|match| workflow["Native Workflow"]\n'
                '  router -->|no match| deep["Native DeepAgent"]\n'
                '  workflow --> result["Structured result"]\n  deep --> result'
            )
        else:
            print('flowchart LR\n  input --> deep["Native DeepAgent"]\n  deep --> result')
    else:
        print(
            json.dumps(
                {
                    "valid": True,
                    "mode": loaded.spec.mode,
                    "name": loaded.name,
                    "version": loaded.version,
                    "agent_id": loaded.agent_id,
                    "package_digest": loaded.digest,
                    "deep_agent": loaded.spec.deep_agent.spec if loaded.spec.deep_agent else None,
                    "router": loaded.spec.router,
                }
            )
        )


async def run_workflow(
    command: str,
    loaded: LoadedWorkflowPackage,
    inputs: dict[str, Any],
    session_id: str,
    request_id: str | None,
) -> None:
    if command == "run":
        with redirect_stdout(sys.stderr):
            runtime = await loaded.boot()
            try:
                result = await runtime.invoke(inputs, session_id=session_id, request_id=request_id)
            finally:
                await runtime.close()
        print(json.dumps(asdict(result), ensure_ascii=False))
        return
    previous = os.environ.get("WORKFLOW_DRAWABLE")
    try:
        if command == "draw":
            os.environ["WORKFLOW_DRAWABLE"] = "true"
        with redirect_stdout(sys.stderr):
            if loaded.ir is not None:
                # Loading validates native config types without connecting services.
                diagram = draw_workflow_ir(loaded.ir) if command == "draw" else None
            else:
                graph = loaded.build_workflow()
                diagram = graph.draw() if command == "draw" else None
    finally:
        if previous is None:
            os.environ.pop("WORKFLOW_DRAWABLE", None)
        else:
            os.environ["WORKFLOW_DRAWABLE"] = previous
    if command == "draw":
        print(diagram)
    else:
        print(
            json.dumps(
                {
                    "valid": True,
                    "mode": "workflow",
                    "name": loaded.name,
                    "version": loaded.version,
                    "package_digest": loaded.digest,
                    "workflow_id": loaded.workflow_id,
                    "source": loaded.source_path.relative_to(loaded.config_root).as_posix(),
                }
            )
        )


def read_inputs(value: str | None, filename: str | None) -> dict[str, Any]:
    try:
        if filename is not None:
            value = (
                sys.stdin.read() if filename == "-" else Path(filename).read_text(encoding="utf-8")
            )
        parsed = json.loads(value if value is not None else "{}")
        if not isinstance(parsed, dict):
            raise ValueError("Input must be an object")
        return parsed
    except (OSError, ValueError) as error:
        raise MetaAgentError("META_INPUT_INVALID", "Package input must be a JSON object") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "draw", "run"])
    parser.add_argument("package", help="Directory with package.json or legacy meta_agent.yaml")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", help="JSON object for package run")
    source.add_argument("--input-file", help="JSON input file; use - for stdin")
    parser.add_argument("--session-id", default="local")
    parser.add_argument("--request-id")
    args = parser.parse_args()
    try:
        inputs = read_inputs(args.input, args.input_file) if args.command == "run" else None
        asyncio.run(
            run(
                args.command,
                args.package,
                inputs=inputs,
                session_id=args.session_id,
                request_id=args.request_id,
            )
        )
    except MetaAgentError as error:
        print(
            json.dumps({"valid": False, "code": error.code, "message": error.message}),
            file=sys.stderr,
        )
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
