"""AgentCompass local web UI backend.

Exposes a small JSON API + static single-page frontend. The browser cannot read
the AgentCompass filesystem or invoke its CLI directly, so this service bridges:
component enumeration imports the registry, run submission shells out to
``agentcompass run``, and history/detail reads the ``results/`` directory tree.

See ``DevDocs/web前端界面设计.md``.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="AgentCompass Web")

_STATIC_DIR = Path(__file__).parent / "static"

def _results_root() -> Path:
    """Resolve the results directory (same source AgentCompass uses)."""
    from agentcompass.runtime.config import get_runtime_settings

    cfg = get_runtime_settings()
    path = Path(getattr(cfg, "results_dir", "results") or "results")
    return path if path.is_absolute() else Path.cwd() / path

def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def _read_text(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None

def _find_log_file(run_dir: Path, run_id: str) -> Path:
    candidate = run_dir / "logs" / f"{run_id}.log"
    if candidate.is_file():
        return candidate
    logs_dir = run_dir / "logs"
    if logs_dir.is_dir():
        logs = sorted(logs_dir.glob("*.log"))
        if logs:
            return logs[0]
    return candidate

def _wall_seconds(started: Any, finished: Any) -> Optional[float]:
    """Wall seconds between two ISO timestamps; if finished is missing, use now."""
    def _parse(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    start = _parse(started)
    if start is None:
        return None
    end = _parse(finished)
    if end is None:
        end = datetime.now().astimezone()
    return round(max(0.0, (end - start).total_seconds()), 2)

def _build_load_request(benchmark_id: str) -> Any:
    """Build a minimal RunRequest only to trigger benchmark.load_tasks().

    Only the benchmark id matters for loading data; harness/environment/model
    are placeholders to pass required-field validation. judge_model is passed
    only when the benchmark's config class actually declares it (e.g. taubench);
    otherwise the unknown field crashes build_config() with an unexpected
    keyword argument (e.g. swebench_verified).
    """
    from agentcompass.runtime.models.request import RunRequest
    from agentcompass.runtime.registry import BENCHMARKS

    params: Dict[str, Any] = {}
    cfg_cls = getattr(BENCHMARKS.get(benchmark_id).component_cls, "config_class", None)
    if cfg_cls is not None:
        try:
            field_names = {f.name for f in dataclasses.fields(cfg_cls)}
        except TypeError:
            field_names = set()
        if "judge_model" in field_names:
            params["judge_model"] = {"id": "preview-judge"}

    return RunRequest.from_params({
        "benchmark": {"id": benchmark_id, "params": params},
        "harness": {"id": "codex"},
        "environment": {"id": "host_process"},
        "model": {"id": "preview"},
    })

def _components() -> Dict[str, Any]:
    from agentcompass.runtime.registry import BENCHMARKS, HARNESSES, load_builtin_components

    load_builtin_components()
    return {
        "benchmarks": [
            {"id": name, "description": desc}
            for name, desc in sorted(BENCHMARKS.descriptions().items())
        ],
        "harnesses": [
            {"id": name, "description": desc}
            for name, desc in sorted(HARNESSES.descriptions().items())
        ],
    }

def _read_run_summary(benchmark: str, model: str, run_id: str, run_dir: Path) -> Dict[str, Any]:
    info = _read_json(run_dir / "run_info.json")
    progress = _read_json(run_dir / "progress.json")
    run_metrics = _read_json(run_dir / "run_metrics.json")

    harness = ""
    request = (info or {}).get("request") or {}
    if isinstance(request.get("harness"), dict):
        harness = str(request["harness"].get("id") or "")

    total_wall_seconds = ((run_metrics or {}).get("summary") or {}).get("total_wall_seconds")
    if not isinstance(total_wall_seconds, (int, float)):
        total_wall_seconds = _wall_seconds((info or {}).get("started_at"), (info or {}).get("finished_at"))

    return {
        "benchmark": benchmark,
        "model": model,
        "run_id": run_id,
        "harness": harness,
        "status": (info or {}).get("status", ""),
        "started_at": (info or {}).get("started_at"),
        "finished_at": (info or {}).get("finished_at"),
        "total_wall_seconds": total_wall_seconds,
        "total_tasks": (progress or {}).get("total_tasks"),
        "finished_tasks": (progress or {}).get("finished_tasks"),
    }

@app.get("/api/components")
def components() -> Dict[str, Any]:
    return _components()

@app.get("/api/runs")
def list_runs() -> List[Dict[str, Any]]:
    root = _results_root()
    runs: List[Dict[str, Any]] = []
    if not root.is_dir():
        return runs
    for bench_dir in sorted(root.iterdir()):
        if not bench_dir.is_dir():
            continue
        for model_dir in sorted(bench_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            for run_dir in sorted(model_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                runs.append(_read_run_summary(bench_dir.name, model_dir.name, run_dir.name, run_dir))
    runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return runs

@app.get("/api/runs/{benchmark}/{model}/{run_id}")
def run_detail(benchmark: str, model: str, run_id: str) -> Dict[str, Any]:
    run_dir = _results_root() / benchmark / model / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_info": _read_json(run_dir / "run_info.json"),
        "metrics": _read_json(run_dir / "metrics.json"),
        "run_metrics": _read_json(run_dir / "run_metrics.json"),
        "analysis_summary_md": _read_text(run_dir / "analysis_summary.md"),
        "run_log": _read_text(_find_log_file(run_dir, run_id)),
    }

@app.get("/api/runs/{benchmark}/{model}/{run_id}/details/{task_id}")
def task_detail(benchmark: str, model: str, run_id: str, task_id: str) -> Dict[str, Any]:
    run_dir = _results_root() / benchmark / model / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="run not found")
    details_dir = run_dir / "details"
    matches = sorted(details_dir.glob(f"{task_id}--*.json")) if details_dir.is_dir() else []
    if not matches:
        raise HTTPException(status_code=404, detail="task details not found")
    return {"task_id": task_id, "data": _read_json(matches[0])}

class RunRequest(BaseModel):
    benchmark: str
    harness: str
    model: str
    # 模型
    model_base_url: str = ""
    model_api_key: str = ""
    model_api_protocol: str = ""
    model_params: Optional[Dict[str, Any]] = None
    wrap_api_key: bool = False
    # 环境
    environment: str = ""
    env_params: Optional[Dict[str, Any]] = None
    env_open_qps: str = ""
    keep_environment: bool = False
    # benchmark / harness
    benchmark_params: Optional[Dict[str, Any]] = None
    harness_params: Optional[Dict[str, Any]] = None
    recipe: str = ""
    recipe_dir: str = ""
    # 执行
    task_concurrency: Optional[int] = None
    k: Optional[int] = None
    attempt_strategy: str = ""
    max_retries: Optional[int] = None
    retry_pattern_list: Optional[List[str]] = None
    # 输出
    run_id: str = ""
    run_name: str = ""
    results_dir: str = ""
    data_dir: str = ""
    reuse: str = ""
    # 超时 / 资源
    timeout_seconds: Optional[int] = None
    provider_limit: str = ""
    # 日志 / 进度
    log_level: str = ""
    file_log_level: str = ""
    progress: str = ""
    # 分析
    enable_analysis: bool = False
    analysis_params: Optional[Dict[str, Any]] = None
    # 依赖 / 配置
    auto_install_dependencies: bool = False
    config: str = ""


def _split_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,，\s]+", str(value)) if item.strip()]


def _build_run_cmd(req: RunRequest) -> List[str]:
    cmd = [sys.executable, "-m", "agentcompass.cli", "run", req.benchmark, req.harness, req.model]

    def add(flag: str, value: Any) -> None:
        if value not in (None, "", []):
            cmd.extend([flag, str(value)])

    def add_json(flag: str, value: Any) -> None:
        if value not in (None, ""):
            cmd.extend([flag, json.dumps(value)])

    def add_bool(flag: str, value: bool) -> None:
        if value:
            cmd.append(flag)

    def add_list(flag: str, value: Any) -> None:
        for item in _split_list(value):
            cmd.extend([flag, item])

    add("--env", req.environment)
    add("--model-base-url", req.model_base_url)
    add("--model-api-key", req.model_api_key)
    add("--model-api-protocol", req.model_api_protocol)
    add_json("--model-params", req.model_params)
    add_bool("--wrap-api-key", req.wrap_api_key)
    add_json("--benchmark-params", req.benchmark_params)
    add_json("--harness-params", req.harness_params)
    add_json("--env-params", req.env_params)
    add("--task-concurrency", req.task_concurrency)
    add("--k", req.k)
    add("--attempt-strategy", req.attempt_strategy)
    add_list("--env-open-qps", req.env_open_qps)
    add("--max-retries", req.max_retries)
    add_json("--retry-pattern-list", req.retry_pattern_list)
    add_list("--recipe", req.recipe)
    add_list("--recipe-dir", req.recipe_dir)
    add("--results-dir", req.results_dir)
    add("--data-dir", req.data_dir)
    add("--run-name", req.run_name)
    add("--run-id", req.run_id)
    if req.reuse:
        cmd += ["--reuse", req.reuse.strip()]
    add("--timeout-seconds", req.timeout_seconds)
    add("--progress", req.progress)
    add("--log-level", req.log_level)
    add("--file-log-level", req.file_log_level)
    add_bool("--auto-install-dependencies", req.auto_install_dependencies)
    add_list("--provider-limit", req.provider_limit)
    add_bool("--keep-environment", req.keep_environment)
    add_bool("--enable-analysis", req.enable_analysis)
    add_json("--analysis-params", req.analysis_params)
    add_list("--config", req.config)
    return cmd

def _launch(cmd: List[str]) -> Dict[str, Any]:
    results_root = _results_root()
    results_root.mkdir(parents=True, exist_ok=True)
    log_path = results_root / "web_run.log"

    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"\n=== {datetime.now().isoformat()} | start ===\n")
        log_file.write(" ".join(cmd) + "\n")
        log_file.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    return {
        "started": True,
        "pid": proc.pid,
        "results_dir": str(results_root),
        "command": " ".join(cmd),
    }

@app.post("/api/runs")
def start_run(req: RunRequest) -> Dict[str, Any]:
    result = _launch(_build_run_cmd(req))
    result["run_id"] = req.run_id or ""
    return result

@app.post("/api/runs/preview")
def preview_run(req: RunRequest) -> Dict[str, Any]:
    return {"command": " ".join(_build_run_cmd(req))}

class CliRunRequest(BaseModel):
    command: str

def _parse_cli_command(raw: str) -> List[str]:
    # 去掉续行符（反斜杠+换行），其余按 POSIX shell 规则解析（单/双引号包裹）
    normalized = re.sub(r'\\\r?\n', ' ', raw)
    try:
        tokens = shlex.split(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"command 解析失败: {exc}")
    if not tokens:
        raise HTTPException(status_code=400, detail="command 不能为空")
    head = tokens[0]
    if head == "agentcompass":
        if len(tokens) < 2 or tokens[1] != "run":
            raise HTTPException(status_code=400, detail="仅支持 agentcompass run ... 命令")
        return [sys.executable, "-m", "agentcompass.cli"] + tokens[1:]
    if head in ("python", "python3"):
        if len(tokens) < 4 or tokens[1] != "-m" or tokens[2] != "agentcompass.cli" or tokens[3] != "run":
            raise HTTPException(status_code=400, detail="仅支持 python -m agentcompass.cli run ... 命令")
        return [sys.executable, "-m", "agentcompass.cli"] + tokens[3:]
    raise HTTPException(status_code=400, detail="命令必须以 agentcompass run 或 python -m agentcompass.cli run 开头")

@app.post("/api/runs/cli")
def start_run_cli(req: CliRunRequest) -> Dict[str, Any]:
    return _launch(_parse_cli_command(req.command))

@app.get("/api/runs/{benchmark}/{model}/{run_id}/progress")
def run_progress(benchmark: str, model: str, run_id: str) -> Dict[str, Any]:
    run_dir = _results_root() / benchmark / model / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="run not found")

    info = _read_json(run_dir / "run_info.json")
    events: List[Dict[str, Any]] = []
    progress_path = run_dir / "progress.jsonl"
    if progress_path.is_file():
        try:
            with open(progress_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
        except (OSError, ValueError):
            events = []
    return {
        "status": (info or {}).get("status", ""),
        "events": events[-100:],
    }

@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))

_DATA_DIR_OVERRIDES = {
    "swebench_pro": "swe_bench_pro",
    "swebench_verified": "swe_bench_verified",
    "terminal_bench_2_1": "terminalbench2_1",
}

def _data_root() -> Path:
    """Resolve the data directory (same source AgentCompass uses)."""
    from agentcompass.runtime.config import get_runtime_settings

    cfg = get_runtime_settings()
    path = Path(getattr(cfg, "data_dir", "data") or "data")
    return path if path.is_absolute() else Path.cwd() / path

def _data_dir_for(benchmark_id: str) -> str:
    """Map a benchmark id to its on-disk data directory name."""
    return _DATA_DIR_OVERRIDES.get(benchmark_id, benchmark_id)

def _benchmark_ready(benchmark_id: str) -> bool:
    """True when the benchmark's data directory exists and is non-empty."""
    directory = _data_root() / _data_dir_for(benchmark_id)
    if not directory.is_dir():
        return False
    return any(directory.iterdir())

def _docs_root() -> Path:
    """Resolve docs/zh/user_guide/modules relative to the project root."""
    import agentcompass

    # agentcompass/__init__.py → src/agentcompass → src → 项目根
    return Path(agentcompass.__file__).resolve().parent.parent.parent / "docs" / "zh" / "user_guide" / "modules"

def _strip_frontmatter(content: str) -> str:
    """Strip a leading YAML frontmatter block (``--- ... ---``)."""
    text = content.lstrip("\ufeff")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip()
    return text

def _read_mdx(kind: str, name: str) -> Dict[str, Any]:
    path = _docs_root() / kind / f"{name}.mdx"
    if not path.is_file():
        return {"found": False, "content": ""}
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {"found": False, "content": ""}
    return {"found": True, "content": _strip_frontmatter(content)}

@app.get("/api/docs/benchmark/{benchmark_id}")
def benchmark_doc(benchmark_id: str) -> Dict[str, Any]:
    return _read_mdx("benchmarks", benchmark_id)

@app.get("/api/docs/harness/{harness_id}")
def harness_doc(harness_id: str) -> Dict[str, Any]:
    return _read_mdx("harnesses", harness_id)

@app.get("/api/benchmark-status")
def benchmark_status() -> Dict[str, bool]:
    from agentcompass.runtime.registry import BENCHMARKS, load_builtin_components

    load_builtin_components()
    return {bid: _benchmark_ready(bid) for bid in BENCHMARKS.names()}

@app.post("/api/benchmark/{benchmark_id}/download")
def download_benchmark(benchmark_id: str) -> Dict[str, Any]:
    from agentcompass.runtime.registry import BENCHMARKS, load_builtin_components

    load_builtin_components()
    try:
        benchmark = BENCHMARKS.get(benchmark_id).create()
    except KeyError:
        raise HTTPException(status_code=404, detail="benchmark not found")
    try:
        benchmark.load_tasks(_build_load_request(benchmark_id))
    except Exception as exc:  # noqa: BLE001 - surface the real failure to the UI
        return {"ok": False, "ready": False, "error": str(exc)}
    return {"ok": True, "ready": _benchmark_ready(benchmark_id)}

@app.delete("/api/benchmark/{benchmark_id}/data")
def delete_benchmark_data(benchmark_id: str) -> Dict[str, Any]:
    directory = _data_root() / _data_dir_for(benchmark_id)
    if directory.is_dir():
        shutil.rmtree(directory, ignore_errors=True)
    return {"ok": True, "ready": _benchmark_ready(benchmark_id)}

@app.get("/api/benchmark/{benchmark_id}/preview")
def preview_benchmark(benchmark_id: str) -> Dict[str, Any]:
    from agentcompass.runtime.registry import BENCHMARKS, load_builtin_components

    load_builtin_components()
    try:
        benchmark = BENCHMARKS.get(benchmark_id).create()
    except KeyError:
        raise HTTPException(status_code=404, detail="benchmark not found")
    try:
        tasks = benchmark.load_tasks(_build_load_request(benchmark_id))
    except Exception as exc:  # noqa: BLE001 - surface the real failure to the UI
        return {"ok": False, "error": str(exc), "tasks": [], "total": 0}

    preview = []
    for task in tasks[:100]:
        preview.append({
            "task_id": str(getattr(task, "task_id", "") or ""),
            "category": str(getattr(task, "category", "") or ""),
            "question": str(getattr(task, "question", "") or "")[:500],
        })
    return {"ok": True, "tasks": preview, "total": len(tasks)}

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
