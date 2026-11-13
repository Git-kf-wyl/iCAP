"""Create delivery templates and zip an explicit file list without executing code."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

MODES = ("agentflow", "workflow", "deepagent", "hybrid")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_assets(group: str, destination: Path) -> None:
    def copy(source: Any, target: Path) -> None:
        for item in source.iterdir():
            if item.name == "__pycache__" or item.name.endswith((".pyc", ".pyo")):
                continue
            path = target / item.name
            if item.is_dir():
                path.mkdir(exist_ok=True)
                copy(item, path)
            else:
                path.write_bytes(item.read_bytes())

    copy(files("meta_agent").joinpath("_templates", group), destination)


def create_package(
    mode: str,
    destination: Path,
    *,
    name: str,
    version: str = "1.0.0",
    workflow_source: str = "ir",
) -> dict[str, Any]:
    if mode not in MODES or workflow_source not in {"ir", "python"}:
        raise ValueError("Unknown package mode or Workflow source")
    if workflow_source == "python" and mode not in {"workflow", "hybrid"}:
        raise ValueError("Python Workflow source requires workflow or hybrid mode")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or not version.strip():
        raise ValueError("Use a nonempty name/version; name accepts letters, digits, ._-")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    _copy_assets("common", destination)
    workflow_file = "workflow.json" if mode == "agentflow" else "jiuwen_runner_workflow.json"
    script = "scripts/echo.py" if mode == "agentflow" else "nodes/jiuwen_node/jiuwen_node.py"
    manifest: dict[str, Any] = {
        "name": name,
        "version": version,
        "description": f"{mode} delivery template",
        "workflows": [workflow_file],
        "metadata": {"type": "agent", "template": mode, "host_integration": "staff-adapter"},
    }
    _write_json(
        destination / "agent.json",
        {
            "name": name,
            "version": version,
            "description": "Single business skill entry",
            "session_pool_size": 1,
            "tasks": [
                {
                    "id": 0,
                    "type": "dispatcher",
                    "description": "Use native dispatch",
                    "next_skills": ["business"],
                    "max_concurrent_skills": 1,
                },
                {"id": 1, "type": "coordinator", "description": "Use native coordination"},
                {
                    "id": 2,
                    "type": "skill",
                    "description": "Run the business package",
                    "workflow_file": workflow_file,
                    "workflow_pool_size": 1,
                    "skill": {"name": "business", "config_dir": "conf", "instance_pool_size": 1},
                },
            ],
            "max_workflows": 3,
            "max_concurrent_workflows": 1,
        },
    )
    _write_json(
        destination / workflow_file,
        {
            "id": f"{name}-entry",
            "version": "1.0",
            "name": "Business entry",
            "nodes": [
                {
                    "id": "business",
                    "name": "Business node",
                    "type": "task",
                    "execution_mode": "python_script",
                    "command": f"./{script}",
                    "json_output": True,
                    "timeout_ms": 120000,
                    "inputs": [{"name": "user_text", "type": "string", "required": True}],
                    "outputs": [{"name": "response", "type": "string"}],
                }
            ],
            "edges": [],
        },
    )
    if mode == "agentflow":
        _copy_assets("agentflow", destination)
    else:
        _copy_assets("jiuwen", destination)
        meta: dict[str, Any] = {
            "schema_version": 1,
            "mode": mode,
            "product_id": "local",
            "agent_id": name,
        }
        if mode in {"workflow", "hybrid"}:
            _copy_assets("workflow_" + workflow_source, destination)
            meta["workflow"] = (
                {"ir": "openjiuwen_agent/workflow/workflow_ir.json"}
                if workflow_source == "ir"
                else {"factory": "openjiuwen_agent/workflow/workflow.py:build_workflow"}
            )
        if mode in {"deepagent", "hybrid"}:
            _copy_assets("deepagent", destination)
            meta["deep_agent"] = {"spec": "openjiuwen_agent/harness/agent.yaml"}
        if mode == "hybrid":
            _copy_assets("hybrid", destination)
            meta["router"] = "nodes/router_node/conf/fast_router.yaml"
        manifest["meta_agent"] = meta
    _write_json(destination / "package.json", manifest)
    _write_json(
        destination / "inputs.json",
        {
            "query": "Say hello." if mode == "deepagent" else "echo",
            "payload": {"value": 42, "items": [True, None]},
        },
    )
    selected = sorted(
        p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()
    )
    (destination / "package.files").write_text(
        "\n".join([*selected, "package.files"]) + "\n", encoding="utf-8"
    )
    return {"package": str(destination), "mode": mode, "files": len(selected) + 1}


def package_files(root: Path) -> dict[str, bytes]:
    """Snapshot selected regular files; runtime state and credentials stay unlisted."""
    root = root.resolve(strict=True)
    selected: dict[str, bytes] = {}
    for line in (root / "package.files").read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name:
            raise ValueError("package.files entries must be relative POSIX file paths")
        if relative.as_posix() != name or name in selected:
            raise ValueError("package.files contains a duplicate or noncanonical path")
        path = root.joinpath(*relative.parts)
        path.resolve(strict=True).relative_to(root)
        if path.is_symlink() or not path.is_file():
            raise ValueError("package.files requires regular files")
        selected[name] = path.read_bytes()
    if not {"package.json", "agent.json", "package.files"} <= selected.keys():
        raise ValueError("Include package.json, agent.json and package.files")
    manifest = json.loads(selected["package.json"])
    agent = json.loads(selected["agent.json"])
    required = list(manifest["workflows"])
    for source in manifest["workflows"]:
        if source in selected:
            for node in json.loads(selected[source]).get("nodes", []):
                command = node.get("command", "")
                if command.startswith("./"):
                    required.append(command[2:])
    required += [task["workflow_file"] for task in agent["tasks"] if task.get("workflow_file")]
    meta = manifest.get("meta_agent", {})
    workflow = meta.get("workflow", {})
    if workflow.get("ir"):
        required.append(workflow["ir"])
    if workflow.get("factory"):
        required.append(workflow["factory"].rpartition(":")[0])
    if meta.get("deep_agent"):
        required.append(meta["deep_agent"]["spec"])
    if meta.get("router"):
        required.append(meta["router"])
    missing = set(required) - selected.keys()
    if missing:
        raise ValueError(
            "Declared source missing from package.files: " + ", ".join(sorted(missing))
        )
    return selected


def pack_package(root: Path, output: Path) -> dict[str, Any]:
    selected = package_files(root)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fixed order/time/mode make repeated packaging of the same bytes reproducible.
    with output.open("xb") as target, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(selected.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return {
        "archive": str(output),
        "files": len(selected),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create a new delivery package directory")
    create.add_argument("mode", choices=MODES)
    create.add_argument("destination", type=Path)
    create.add_argument("--name", required=True)
    create.add_argument("--version", default="1.0.0")
    create.add_argument("--workflow-source", choices=["ir", "python"], default="ir")
    pack = commands.add_parser("pack", help="Zip exactly the files listed in package.files")
    pack.add_argument("package", type=Path)
    pack.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (
            create_package(
                args.mode,
                args.destination,
                name=args.name,
                version=args.version,
                workflow_source=args.workflow_source,
            )
            if args.command == "create"
            else pack_package(args.package, args.output)
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
