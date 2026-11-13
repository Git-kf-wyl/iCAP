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

import ast
import copy
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

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


def _local_images(tags: list[str]) -> set[str]:
    """Query Docker once per catalog request so image readiness stays live."""
    try:
        out = subprocess.run(
            ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}",
             *(argument for tag in sorted(set(tags)) for argument in ("--filter", f"reference={tag}"))],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return set(out.stdout.splitlines()) if out.returncode == 0 else set()
    except (OSError, subprocess.TimeoutExpired):
        return set()


def _file_stamp(path: Path) -> tuple[int, int, int] | None:
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size
    except OSError:
        return None


@lru_cache(maxsize=32)
def _runner_images(path: Path, stamp: tuple[int, int, int] | None) -> dict[str, str]:
    """Read literal image declarations without importing or executing repo code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not any(
                isinstance(target, ast.Name) and target.id == "SPECS" for target in node.targets
            ) or not isinstance(node.value, ast.Dict):
                continue
            images = {}
            for key, value in zip(node.value.keys, node.value.values):
                if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                    continue
                if not isinstance(value, ast.Call):
                    continue
                for keyword in value.keywords:
                    if keyword.arg == "image" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                        images[key.value] = keyword.value.value
            return images
    except (OSError, SyntaxError, ValueError):
        pass
    return {}


def _task_brief(task_dir: Path) -> dict:
    # A changed, added or removed task is visible on the very next request.
    return copy.deepcopy(_cached_task_brief(task_dir, _file_stamp(task_dir / "task.yaml")))


@lru_cache(maxsize=2048)
def _cached_task_brief(task_dir: Path, stamp: tuple[int, int, int] | None) -> dict:
    spec = None
    try:
        import yaml  # 延迟 import：缺 PyYAML 时该字段为空
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        spec = yaml.load((task_dir / "task.yaml").read_text(encoding="utf-8"), Loader=loader) or {}
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
    runtime_path = _REPO / "tools" / "harness_runtime.py"
    runner_images = _runner_images(runtime_path, _file_stamp(runtime_path))
    harnesses = []
    for p in _harness_dirs():
        tag = os.getenv("HARNESS_" + p.name.upper() + "_OBS_IMAGE", runner_images.get(p.name, f"harnessbench/{p.name}:local"))
        harnesses.append({"id": p.name, "image": tag})
    images = _local_images([h["image"] for h in harnesses] + ["harnessbench/grader:local"])
    for harness in harnesses:
        harness["image_ready"] = harness["image"] in images
    return {
        "repo": str(_REPO),
        "repo_ready": (_REPO / "tools" / "run_benchmark.py").is_file(),
        "runs_dir": str(_RUNS_DIR),
        "task_count": len(tasks),
        "tasks": tasks,
        "harnesses": harnesses,
        "grader": {"image": "harnessbench/grader:local", "image_ready": "harnessbench/grader:local" in images},
    }


# ── 运行管理 ────────────────────────────────────────────────────────────────
def _run_dir(run_id: str) -> Path:
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise HTTPException(422, '运行 ID 无效')
    path = (_RUNS_DIR / run_id).resolve()
    if not path.is_relative_to(_RUNS_DIR):
        raise HTTPException(422, '运行路径无效')
    return path


def _alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
        # A completed Popen child can remain a zombie until the next process
        # launch reaps it. kill(pid, 0) alone incorrectly keeps the UI running.
        proc_stat = Path(f"/proc/{int(pid)}/stat")
        if proc_stat.exists() and proc_stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False
        return True
    except Exception:
        return False


def _selected_ids(meta: dict) -> list[str]:
    values = meta.get("task_ids")
    if not isinstance(values, list):
        values = str(meta.get("task_id") or "").split(",")
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


def _validate_selection(body: dict) -> list[str]:
    if body.get("task_set"):
        raise HTTPException(422, "请明确勾选用例，不支持通过 task_set 启动全量评测")
    if "task_ids" in body:
        values = body["task_ids"]
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise HTTPException(422, "task_ids 必须是用例 ID 数组")
    else:
        # Compatibility with existing single-task clients; never default to a suite.
        value = body.get("task_id")
        values = [value] if isinstance(value, str) else []
    if not values or any(not value.strip() for value in values):
        raise HTTPException(422, "请至少勾选一条用例")
    selected = list(dict.fromkeys(value.strip() for value in values))
    known = {_task_brief(path)["id"] for path in _task_dirs()}
    unknown = set(selected) - known
    if unknown:
        raise HTTPException(422, "未知用例 ID：" + ", ".join(sorted(unknown)))
    return selected


def _selection_progress(path: Path, selected: list[str]) -> dict:
    summary = _read_json(path / "artifacts" / "summary.json", default={}) or {}
    rows = {row.get("task_id"): row for row in summary.get("tasks", []) if isinstance(row, dict)}
    tasks = []
    for task_id in selected:
        row = rows.get(task_id, {})
        tasks.append({"task_id": task_id, "status": row.get("status", "queued"),
                      "outcome_score": row.get("outcome_score"), "elapsed_sec": row.get("elapsed_sec"),
                      "error": row.get("error", "")})
    counts = {}
    for task in tasks:
        status = task["status"]
        counts[status] = counts.get(status, 0) + 1
    return {"selected_count": len(selected), "counts": counts, "tasks": tasks}


def _execution_log(path: Path, selected: list[str]) -> str:
    # The runner's final JSON contains all 274 catalogue rows, including
    # not_selected. Keep raw logs on disk; display execution messages in the UI.
    raw = _tail(path, 1024 * 1024)
    decoder = json.JSONDecoder()
    lines = []
    offset = 0
    while offset < len(raw):
        end = raw.find("\n", offset)
        end = len(raw) if end < 0 else end
        line = raw[offset:end]
        stripped = line.lstrip()
        if stripped.startswith("{"):
            try:
                value, consumed = decoder.raw_decode(raw, offset + len(line) - len(stripped))
                if isinstance(value, dict) and ("suite_size" in value or "tasks" in value):
                    offset = consumed
                    if offset < len(raw) and raw[offset] == "\n":
                        offset += 1
                    continue
            except (ValueError, TypeError):
                pass
        if '"not_selected"' not in line:
            lines.append(line)
        offset = end + 1
    header = f"本次仅执行 {len(selected)} 条已选用例：" + ", ".join(selected) + "\n"
    return header + "\n".join(lines)[-_LOG_TAIL_BYTES:]


def _summarize(meta: dict, path: Path) -> dict:
    status = meta.get("status", "running")
    if status == "running":
        if meta.get("pid") and not _alive(meta["pid"]):
            status = "finished" if meta.get("exit_code") == 0 else "failed"
        elif not meta.get("pid"):
            status = "failed"
    return {
        "id": meta.get("id"),
        "status": status,
        "created_at": meta.get("created_at"),
        "finished_at": meta.get("finished_at"),
        "task_id": meta.get("task_id"),
        "task_ids": _selected_ids(meta),
        "task_count": len(_selected_ids(meta)),
        "harness": meta.get("harness"),
        "model": meta.get("model"),
        "workers": meta.get("workers"),
        "thinking_mode": meta.get("thinking_mode"),
        "reasoning_effort": meta.get("reasoning_effort"),
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
    harness = str(body.get("harness") or "").strip()
    model = str(body.get("model") or "").strip()
    base_url = str(body.get("model_base_url") or "").strip()
    api_key = str(body.get("model_api_key") or "").strip()
    try:
        workers = int(body.get("workers") or 1)
        temperature = float(body.get("temperature", 1))
    except (ValueError, TypeError):
        raise HTTPException(422, "并发数或温度无效")
    if not 1 <= workers <= 8 or not 0 <= temperature <= 2:
        raise HTTPException(422, "并发数须为 1–8，温度须为 0–2")
    if harness not in {"metaagent", "openjiuwen"}:
        raise HTTPException(422, "观测评测仅支持 metaagent 和 openjiuwen")

    if not harness or not model or not base_url:
        raise HTTPException(422, "harness / model / model_base_url 均为必填")
    if not (_REPO / "tools" / "run_benchmark.py").is_file():
        raise HTTPException(503, f"harness-bench 工程不存在或缺少 tools/run_benchmark.py: {_REPO}")
    bundle = os.getenv('HARNESS_TELEMETRY_BUNDLE')
    if not bundle or not (Path(bundle)/'runtime.env').is_file():
        raise HTTPException(503, "观测运行包尚未配置，暂不能启动评测")
    thinking_mode=body.get('thinking_mode','disabled')
    effort=body.get('reasoning_effort')
    if thinking_mode not in {'enabled','disabled'}:
        raise HTTPException(422,'思考模式无效')
    if effort is not None and effort not in {'minimal','low','medium','high','max','xhigh'}:
        raise HTTPException(422,'思考档位无效')
    if thinking_mode=='disabled' and effort is not None:
        raise HTTPException(422,'关闭思考时不能设置思考档位')
    thinking='off' if thinking_mode=='disabled' else (effort or 'on')
    task_ids = _validate_selection(body)
    task_id = ",".join(task_ids)

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
        "--temperature", str(temperature),
        "--thinking", thinking,
        "--run-root", str(run_dir / "artifacts"),
    ]
    observer_image = os.getenv('HARNESS_' + harness.upper() + '_OBS_IMAGE')
    if not observer_image:
        raise HTTPException(503, '观测镜像尚未配置')
    cmd += ['--harness-image', observer_image]
    if api_key:
        cmd += ["--upstream-api-key-file", str(key_file)]

    log_path = run_dir / "run.log"
    log_fh = log_path.open("wb")
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env['HARNESS_RUN_ID'] = run_id
    env['HARNESS_MODEL_THINKING_SCHEMA']=json.dumps(body.get('_thinking_schema') or {})
    initial = {"id":run_id, "status":"running", "created_at":now(),
               "task_id":task_id, "task_ids":task_ids, "harness":harness,
               "model":model, "workers":workers, "command":cmd, "repo":str(_REPO),
               "run_root":str(run_dir/'artifacts'), "temperature":temperature,
               "thinking_mode":thinking_mode,"reasoning_effort":effort}
    _write_json(run_dir/'run.json', initial)
    try:
        proc = subprocess.Popen([sys.executable, '-m', 'app.harness_run_worker', str(run_dir/'run.json')],
                                cwd=str(Path(__file__).resolve().parents[1]), stdout=log_fh, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    except Exception as exc:  # noqa: BLE001 - 启动失败也要落盘成 failed，前端可读
        meta = {"id": run_id, "status": "failed", "created_at": now(), "task_id": task_id, "task_ids": task_ids,
                "harness": harness, "model": model, "workers": workers,
                "command": cmd, "error": f"{type(exc).__name__}: {exc}", "pid": None}
        _write_json(run_dir / "run.json", meta)
        return _summarize(meta, run_dir)
    finally:
        log_fh.close()

    meta = _read_json(run_dir / "run.json", initial)
    meta['pid'] = proc.pid
    return _summarize(meta, run_dir)


def run_detail(run_id: str) -> dict:
    path = _run_dir(run_id)
    if not path.is_dir():
        raise HTTPException(404, "运行不存在")
    meta = _read_json(path / "run.json", default={}) or {}
    detail = _summarize(meta, path)
    selected = _selected_ids(meta)
    detail["selection"] = _selection_progress(path, selected)
    detail["log_tail"] = _execution_log(path / "run.log", selected)
    detail["command"] = meta.get("command")
    return detail


def stop_run(run_id: str) -> dict:
    path = _run_dir(run_id)
    meta = _read_json(path / "run.json", default=None)
    if not isinstance(meta, dict) or not meta.get("pid"):
        raise HTTPException(404, "运行不存在或已结束")
    if meta.get('pid_start_ticks'):
        try:
            current_ticks=Path(f"/proc/{int(meta['pid'])}/stat").read_text().rsplit(')',1)[1].split()[19]
        except OSError:
            current_ticks=None
        if current_ticks!=meta['pid_start_ticks']:
            raise HTTPException(409,'原运行进程已退出')
    if meta.get('status') != 'running' or not _alive(meta['pid']):
        raise HTTPException(409, '运行已结束')
    meta['status'] = 'stopped'
    meta['finished_at'] = now()
    _write_json(path / 'run.json', meta)
    try:
        os.killpg(os.getpgid(int(meta["pid"])), 15)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(409, f"停止失败: {exc}") from exc
    return _summarize(_read_json(path / "run.json", meta), path)


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
    def create_run(request: Request, body: dict = Body(...), actor=Depends(auth_dep)):
        from .model_thinking import validate
        registered=next((m for m in request.app.state.registry.list_models(actor) if m['id']==body.get('model')),None)
        if registered:
            validate(registered,body.get('thinking_mode','disabled')=='enabled',body.get('reasoning_effort'))
            endpoint=registered['endpoints'][0]
            body={**body,'model_base_url':endpoint['url'],
                  'model_api_key':request.app.state.registry.api_key(endpoint),
                  '_thinking_schema':endpoint.get('thinking_schema') or {}}
        elif body.get('thinking_mode')=='enabled':
            raise HTTPException(422,'请先在模型管理中注册模型及思考能力，再开启思考')
        return start_run(body)

    @api.get("/runs/{run_id}", dependencies=[Depends(auth_dep)])
    def get_run(run_id: str):
        return run_detail(run_id)

    @api.post("/runs/{run_id}/stop", dependencies=[Depends(auth_dep)])
    def post_stop(run_id: str):
        return stop_run(run_id)

    from .harness_observability import router as observation_router
    combined = APIRouter()
    combined.include_router(api)
    combined.include_router(observation_router(auth_dep, _RUNS_DIR))
    return combined
