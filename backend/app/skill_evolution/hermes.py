"""Hermes integration: task-scoped inference relay and filesystem sandbox.

The agent never receives a provider credential. Only the parent worker can make
authenticated model requests. Hermes and all its tools share a mount/PID namespace
containing the current case and a read-only runtime, not the iCAP data directory.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
import secrets
import shutil
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class InferenceRelay:
    def __init__(self, request, models):
        self.token = secrets.token_hex(24)
        relay = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, value):
                data = json.dumps(value, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def role(self):
                parts = self.path.split("/")
                if len(parts) != 5 or not secrets.compare_digest(parts[1], relay.token) or parts[2] not in models:
                    return None
                return parts[2]

            def do_GET(self):
                role = self.role()
                if not role or not self.path.endswith("/v1/models"):
                    return self.reply(404, {"error": {"message": "Unknown route"}})
                self.reply(200, {"object": "list", "data": [{"id": models[role]["name"], "object": "model"}]})

            def do_POST(self):
                # /<task-token>/<role>/v1/chat/completions
                # Drain small invalid-route requests before closing, otherwise Windows
                # may reset the socket before the caller can receive the 404 response.
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    return self.reply(400, {"error": {"message": "Invalid request length"}})
                if not 0 < size <= 8_000_000:
                    return self.reply(413, {"error": {"message": "Request too large"}})
                self.connection.settimeout(30)
                raw_body = self.rfile.read(size)
                parts = self.path.split("/")
                if len(parts) != 6 or not secrets.compare_digest(parts[1], relay.token) or parts[2] not in models or parts[3:] != ["v1", "chat", "completions"]:
                    return self.reply(404, {"error": {"message": "Unknown route"}})
                try:
                    body = json.loads(raw_body)
                    streaming = body.get("stream", False)
                    response = request(parts[2], body)
                    if not streaming:
                        return self.reply(200, response)
                    # Hermes may request SSE. Providers are called in non-streaming
                    # mode so tool calls and errors remain atomic and budgeted.
                    message = response["choices"][0]["message"]
                    delta = {"role": "assistant", "content": message.get("content") or ""}
                    if message.get("tool_calls"):
                        delta["tool_calls"] = [{**call, "index": i} for i, call in enumerate(message["tool_calls"])]
                    chunks = [{"id": response.get("id", "icap"), "object": "chat.completion.chunk", "model": models[parts[2]]["name"],
                               "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                              {"id": response.get("id", "icap"), "object": "chat.completion.chunk", "model": models[parts[2]]["name"],
                               "choices": [{"index": 0, "delta": {}, "finish_reason": response["choices"][0].get("finish_reason", "stop")}],
                               "usage": response.get("usage", {})}]
                    data = ("".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    # Never expose provider response bodies, request headers or URLs.
                    self.reply(502, {"error": {"message": "iCAP model request failed; inspect task status"}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def url(self, role):
        return f"http://127.0.0.1:{self.server.server_port}/{self.token}/{role}/v1"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def sandbox_command(runtime: Path, case: Path, workspace: Path, command: list[str]):
    """Build an allowlisted mount tree; never bind /, /var/lib/icap or /etc."""
    args = ["/usr/bin/bwrap", "--die-with-parent", "--new-session", "--unshare-user", "--unshare-pid", "--unshare-ipc", "--unshare-uts",
            "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/sbin", "/sbin", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/home/agent"]
    # runtime contains source + venv only and is owned by root, not the agent.
    args += ["--ro-bind", str(runtime), str(runtime), "--bind", str(case), str(case)]
    for path in ("/etc/ssl/certs", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf"):
        if Path(path).exists():
            args += ["--ro-bind", path, path]
    args += ["--clearenv", "--setenv", "PATH", str(runtime / "venv/bin") + ":/usr/local/bin:/usr/bin:/bin",
             "--setenv", "HOME", "/home/agent", "--setenv", "USER", "agent", "--setenv", "LANG", "C.UTF-8", "--setenv", "PYTHONUTF8", "1",
             "--setenv", "HERMES_HOME", str(case / ".hermes"), "--setenv", "TERMINAL_CWD", str(workspace),
             "--chdir", str(workspace), "--", "/usr/bin/prlimit", "--nproc=96", "--nofile=512", "--fsize=67108864", "--cpu=180", "--", *command]
    return args


def install_runner(relay, cfg, models, assets, fatal_errors):
    """Use one platform adapter with either unmodified upstream engine."""
    from src.self_evolve.execution.hermes_runner import HermesCliRunner
    from src.self_evolve.schemas import HermesRunResult
    from src.self_evolve.evaluators.components.session_analyzer import SessionAnalyzer

    original_process = SessionAnalyzer._analyze_process
    original_tool = SessionAnalyzer._analyze_tool
    def analyze_tool(self, *, trajectory, expected_tool):
        if isinstance(expected_tool, dict) and "__icap_spreadsheet__" in expected_tool:
            from .spreadsheet import grade
            baseline = os.environ.get("ICAP_SPREADSHEET_BASELINE")
            workspace = os.environ.get("ICAP_HERMES_WORKSPACE")
            if not baseline or not workspace:
                raise ValueError("表格用例未提供隔离工作簿或可信基线")
            return grade(Path(workspace), expected_tool["__icap_spreadsheet__"], baseline_path=Path(baseline))
        return original_tool(self, trajectory=trajectory, expected_tool=expected_tool)
    SessionAnalyzer._analyze_tool = analyze_tool

    def analyze_process(self, *, trajectory, key_steps):
        score, details = original_process(self, trajectory=trajectory, key_steps=key_steps)
        # Upstream requests per-trajectory scores without reference steps, but
        # then divides by an empty reference weight map and always returns zero.
        if not key_steps and isinstance(details, dict):
            values = [v for v in details.get("step_scores", {}).values()
                      if type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 100]
            if values:
                score = sum(values) / len(values)
                details["weighted_score"] = score
        return score, details

    SessionAnalyzer._analyze_process = analyze_process

    runtime = Path(os.environ["ICAP_HERMES_RUNTIME"]).resolve()
    binary = str(runtime / "venv/bin/hermes")

    def init(self, config, run_dir, source, logger=None):
        self.config, self.run_dir, self.source = config, Path(run_dir), source

    def run_case(self, *, case_id, skill_path, input_text, case_dir, pre_condition=None):
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("Hermes 用例缺少有效文本提问")
        case = Path(case_dir).resolve()
        case.mkdir(parents=True, exist_ok=True)
        # Each case (and the B large-model path) has its own home and workspace.
        for name in (".hermes", "workspace"):
            path = case / name
            if path.exists():
                shutil.rmtree(path)
        home, workspace = case / ".hermes", case / "workspace"
        skill_dir = home / "skills" / "icap-task"
        skill_dir.mkdir(parents=True)
        workspace.mkdir()
        skill = Path(skill_path).read_text(encoding="utf-8")
        # Supply a stable, valid Skill identity; original content remains intact.
        (skill_dir / "SKILL.md").write_text("---\nname: icap-task\ndescription: Execute the current iCAP evaluation task.\n---\n\n" + skill, encoding="utf-8")
        judge_files = {str(Path(output.get("expect_path") if output["type"] == "file" else output.get("data")).resolve())
                       for item in cfg["dataset"] for output in item.get("output", [])
                       if output["type"] in {"file", "onlyllm"} and (output.get("expect_path") or output.get("data"))}
        for resource in cfg["resources"]:
            if str((assets / resource["name"]).resolve()) in judge_files:
                continue
            for root in (workspace, skill_dir):
                target = root / resource["name"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(resource["content"], encoding="utf-8")
        item = next((item for item in cfg["dataset"] if str(item["id"]) == str(case_id)), {})
        baseline = Path(item["input_path"]) if item.get("input_path") else None
        os.environ.pop("ICAP_SPREADSHEET_BASELINE", None)
        if baseline:
            if not baseline.resolve().is_relative_to(assets.resolve()) or not baseline.is_file() or baseline.is_symlink():
                raise ValueError("用例输入文件不在已快照的任务资源中")
            shutil.copyfile(baseline, workspace / "input.xlsx" if baseline.suffix.lower() == ".xlsx" else workspace / baseline.name)
            os.environ["ICAP_SPREADSHEET_BASELINE"] = str(baseline.resolve())
            input_text += "\n\n平台已将本用例输入工作簿放到当前目录 input.xlsx。只能读取本用例资源，结果须保存到当前目录 output.xlsx。"
        # Binary workbooks are staged per case, never the whole uploaded spreadsheet collection.
        for resource in cfg.get("managed_assets", []):
            source = (assets / resource["name"]).resolve()
            if str(source) in judge_files or source.suffix.lower() in {".xlsx", ".xls", ".zip"}:
                continue
            # Managed JSON datasets may contain the expected answers. Do not expose them to the agent.
            if source.suffix.lower() == ".json":
                continue
            target = workspace / "references" / source.name
            if target.exists():
                target = workspace / resource["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        role = "large" if self.config.hermes_env.get("ICAP_MODEL_ROLE") == "large" else "exec"
        config = {"model": {"default": models[role]["name"], "provider": "custom", "base_url": relay.url(role), "api_key": "icap-task-relay"},
                  "terminal": {"backend": "local", "cwd": str(workspace)},
                  "agent": {"max_turns": 12}, "max_tokens": cfg["max_tokens"],
                  "compression": {"enabled": False}, "memory": {"memory_enabled": False, "user_profile_enabled": False},
                  "checkpoints": {"enabled": False}}
        # JSON is a subset of YAML; no YAML dependency is needed in the worker.
        (home / "config.yaml").write_text(json.dumps(config), encoding="utf-8")
        command = [binary, "chat", "-q", input_text, "-Q", "--source", "tool", "--skills", "icap-task",
                   "--model", models[role]["name"], "--provider", "custom", "--toolsets", "terminal,file", "--max-turns", "12", "--yolo"]
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
        error, stdout, stderr, returncode = "", "", "", 0
        proc = subprocess.Popen(sandbox_command(runtime, case, workspace, command), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", start_new_session=True)
        try:
            stdout, stderr = proc.communicate(timeout=cfg["timeout"])
            returncode = proc.returncode
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            returncode, error = 124, f"Hermes 用例执行超过 {cfg['timeout']} 秒"
        if returncode and not error:
            error = "Hermes 执行失败：" + stderr[-1200:]
        export = case / "session.export.jsonl"
        # Export from Hermes' own persisted session database, not stdout guesses.
        export_cmd = [binary, "sessions", "export", str(export)]
        completed = subprocess.run(sandbox_command(runtime, case, workspace, export_cmd), env=env,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        messages, session_id = [], ""
        if export.is_file():
            for line in export.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                if record.get("messages"):
                    messages = record["messages"]
                    session_id = record.get("session_id", record.get("id", ""))
        if not messages:
            error = error or "Hermes 未导出真实会话轨迹：" + completed.stderr[-700:]
        final_output = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "assistant" and m.get("content")), "")
        if not final_output:
            error = error or "Hermes 未返回最终回答"
        os.environ["ICAP_SKILL_CONTEXT"] = skill
        os.environ["ICAP_HERMES_WORKSPACE"] = str(workspace)
        raw = case / "session.raw.jsonl"
        raw.write_text(json.dumps({"messages": messages, "session_id": session_id}, ensure_ascii=False), encoding="utf-8")
        result = HermesRunResult(case_id=case_id, command=["hermes", "chat"], returncode=returncode,
                                 stdout=final_output, stderr=stderr[-3000:], source=self.source, hermes_home=str(home),
                                 raw_session_path=str(raw), exported_session_path=str(export), session_id=session_id,
                                 final_output=final_output, error=error)
        (case / "run_result.json").write_text(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
        # Relay URLs expire when this worker exits. Keep runtime state out of artifacts.
        if error:
            fatal_errors.append(error)
        return result

    HermesCliRunner.__init__ = init
    HermesCliRunner.run_case = run_case
