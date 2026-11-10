"""Harness 评测服务（harness-bench 接入层）。

本模块把 Qihoo360/YilaiYan harness-bench 评测工程以「在线评估」的形式接到 iCAP：

- GET  /api/harness-eval/catalog        枚举 harness-bench 的任务与 harness
- GET  /api/harness-eval/runs           历史运行列表
- POST /api/harness-eval/runs           发起一次运行（后台 subprocess，不阻塞）
- GET  /api/harness-eval/runs/{id}      单次运行状态 + 日志尾
- POST /api/harness-eval/runs/{id}/stop 停止运行

设计要点（与 harness-bench 工程本身保持一致）：
- harness-bench 的镜像方向是「harness 固定、任务挂载进去」，因此一次运行 =
  `python tools/run_benchmark.py --harness <id> --tasks <task_id> ...`。
- 运行结果落在 runs 目录，本模块只读不改，状态由 run.json + 进程存活推导。
- 不改写 harness-bench 仓库；仓库路径由 HARNESS_BENCH_REPO 指定。

依赖：目标机需已 `uv sync`（或装好 PyYAML）并构建好 harness/grader 镜像。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

# ── 路径配置 ────────────────────────────────────────────────────────────────
_REPO_DEFAULT = "/opt/harness-bench"
_REPO = Path(os.getenv("HARNESS_BENCH_REPO", _REPO_DEFAULT)).resolve()
_RUNS_DIR = Path(os.getenv("HARNESS_BENCH_RUNS_DIR", "/var/lib/icap/harness_runs")).resolve()
_LOG_TAIL_BYTES = 64 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ── 目录枚举 ────────────────────────────────────────────────────────────────
def _task_dirs() -> list[Path]:
    """harness-bench 任务包：tasks/<id>/task.yaml。"""
    root = _REPO / "tasks"
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "task.yaml").is_file())


def _harness_dirs() -> list[Path]:
    """被测 harness 的镜像目录：docker/harnesses/<id>/。"""
    root = _REPO / "docker" / "harnesses"
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "Dockerfile").is_file()
    )


def _image_exists(tag: str) -> bool:
    try:
        out = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}", tag],
            capture_output=True, text=True, timeout=30, check=False,
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def _task_brief(task_dir: Path) -> dict:
    spec = None
    try:
        import yaml  # 延迟 import：缺 PyYAML 时该字段为空
        spec = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        spec = {}
    if not isinstance(spec, dict):
        spec = {}
    return {
        "id": str(spec.get("task_id") or task_dir.name),
        "dir": task_dir.name,
        "category": str(spec.get("task_category") or "all"),
        "timeout_sec": int(spec.get("timeout_sec") or 0),
        "artifacts": list(spec.get("required_artifacts") or []),
    }


def catalog() -> dict:
    tasks = [_task_brief(p) for p in _task_dirs()]
    harnesses = []
    for p in _harness_dirs():
        tag = f"harnessbench/{p.name}:local"
        harnesses.append({"id": p.name, "image": tag, "image_ready": _image_exists(tag)})
    return {
        "repo": str(_REPO),
        "repo_ready": (_REPO / "tools" / "run_benchmark.py").is_file(),
        "runs_dir": str(_RUNS_DIR),
        "task_count": len(tasks),
        "tasks": tasks,
        "harnesses": harnesses,
        "grader": {"image": "harnessbench/grader:local", "image_ready": _image_exists("harnessbench/grader:local")},
    }


# ── 运行管理 ────────────────────────────────────────────────────────────────
def _run_dir(run_id: str) -> Path:
    return _RUNS_DIR / run_id


def _alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _summarize(meta: dict, path: Path) -> dict:
    status = meta.get("status", "running")
    if status == "running":
        if meta.get("pid") and not _alive(meta["pid"]):
            status = "finished" if meta.get("exit_code") in (0, None) else "failed"
        elif not meta.get("pid"):
            status = "failed"
    return {
        "id": meta.get("id"),
        "status": status,
        "created_at": meta.get("created_at"),
        "finished_at": meta.get("finished_at"),
        "task_id": meta.get("task_id"),
        "harness": meta.get("harness"),
        "model": meta.get("model"),
        "workers": meta.get("workers"),
        "exit_code": meta.get("exit_code"),
        "run_root": meta.get("run_root"),
    }


def _list_runs(limit: int = 50) -> list[dict]:
    if not _RUNS_DIR.is_dir():
        return []
    items = []
    for path in sorted(_RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        meta = _read_json(path / "run.json", default=None)
        if not isinstance(meta, dict):
            continue
        items.append(_summarize(meta, path))
        if len(items) >= limit:
            break
    return items


def _tail(path: Path, limit: int = _LOG_TAIL_BYTES) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > limit:
                fh.seek(size - limit)
            return fh.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


def start_run(body: dict) -> dict:
    task_id = str(body.get("task_id") or "").strip()
    harness = str(body.get("harness") or "").strip()
    model = str(body.get("model") or "").strip()
    base_url = str(body.get("model_base_url") or "").strip()
    api_key = str(body.get("model_api_key") or "").strip()
    workers = int(body.get("workers") or 1)

    if not task_id or not harness or not model or not base_url:
        raise HTTPException(422, "task_id / harness / model / model_base_url 均为必填")
    if not (_REPO / "tools" / "run_benchmark.py").is_file():
        raise HTTPException(503, f"harness-bench 工程不存在或缺少 tools/run_benchmark.py: {_REPO}")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    key_file = run_dir / "upstream_key.txt"
    if api_key:
        key_file.write_text(api_key.strip() + "\n", encoding="utf-8")
        os.chmod(key_file, 0o600)

    cmd = [
        sys.executable, "tools/run_benchmark.py",
        "--base-url", base_url,
        "--model", model,
        "--harness", harness,
        "--tasks", task_id,
        "--workers", str(workers),
        "--temperature", str(body.get("temperature") or 1),
        "--run-root", str(run_dir / "artifacts"),
    ]
    task_set = str(body.get("task_set") or "").strip()
    if task_set:
        cmd += ["--task-set", task_set]
    if api_key:
        cmd += ["--upstream-api-key-file", str(key_file)]

    log_path = run_dir / "run.log"
    log_fh = log_path.open("wb")
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        proc = subprocess.Popen(cmd, cwd=str(_REPO), stdout=log_fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    except Exception as exc:  # noqa: BLE001 - 启动失败也要落盘成 failed，前端可读
        meta = {"id": run_id, "status": "failed", "created_at": now(), "task_id": task_id,
                "harness": harness, "model": model, "workers": workers,
                "command": cmd, "error": f"{type(exc).__name__}: {exc}", "pid": None}
        _write_json(run_dir / "run.json", meta)
        return _summarize(meta, run_dir)
    finally:
        log_fh.close()

    meta = {
        "id": run_id, "status": "running", "created_at": now(), "finished_at": None,
        "task_id": task_id, "harness": harness, "model": model, "workers": workers,
        "temperature": body.get("temperature") or 1,
        "base_url": base_url,          # api_key 只落 600 权限的文件，不写 meta
        "command": cmd, "pid": proc.pid,
        "run_root": str(run_dir / "artifacts"),
    }
    _write_json(run_dir / "run.json", meta)
    return _summarize(meta, run_dir)


def run_detail(run_id: str) -> dict:
    path = _run_dir(run_id)
    if not path.is_dir():
        raise HTTPException(404, "运行不存在")
    meta = _read_json(path / "run.json", default={}) or {}
    detail = _summarize(meta, path)
    detail["log_tail"] = _tail(path / "run.log")
    detail["command"] = meta.get("command")
    return detail


def stop_run(run_id: str) -> dict:
    path = _run_dir(run_id)
    meta = _read_json(path / "run.json", default=None)
    if not isinstance(meta, dict) or not meta.get("pid"):
        raise HTTPException(404, "运行不存在或已结束")
    try:
        os.killpg(os.getpgid(int(meta["pid"])), 15)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(409, f"停止失败: {exc}") from exc
    meta["status"] = "stopped"
    meta["finished_at"] = now()
    _write_json(path / "run.json", meta)
    return _summarize(meta, path)


# ── 路由 ────────────────────────────────────────────────────────────────────
def router(auth_dep) -> APIRouter:
    """返回挂载到主 app 的路由；auth_dep 为既有鉴权依赖函数。"""
    api = APIRouter(prefix="/api/harness-eval", tags=["harness-eval"])

    @api.get("/catalog", dependencies=[Depends(auth_dep)])
    def get_catalog():
        return catalog()

    @api.get("/runs", dependencies=[Depends(auth_dep)])
    def get_runs(limit: int = Query(default=50, ge=1, le=500)):
        return {"runs": _list_runs(limit)}

    @api.post("/runs", status_code=201, dependencies=[Depends(auth_dep)])
    def create_run(body: dict = Body(...)):
        return start_run(body)

    @api.get("/runs/{run_id}", dependencies=[Depends(auth_dep)])
    def get_run(run_id: str):
        return run_detail(run_id)

    @api.post("/runs/{run_id}/stop", dependencies=[Depends(auth_dep)])
    def post_stop(run_id: str):
        return stop_run(run_id)

    return api
