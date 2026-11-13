"""JiuwenSwarm (openJiuwen) process-CLI harness.

Runs the JiuwenSwarm ``jiuwenswarm-process`` non-interactive process CLI as a
coding agent. Model credentials are inlined through environment variables
(``API_BASE`` / ``API_KEY`` / ``MODEL_NAME`` / ``MODEL_PROVIDER``), which is what
workswarm 0.2.7 expects: the older ``--model`` / ``--api-base`` CLI flags were
removed, and the package's default ``config.yaml`` uses exactly these
placeholders. ``--output json`` returns one JSON document whose ``events`` carry
the final answer (``chat.final``) plus the tool-call trajectory.
"""

from __future__ import annotations

import json
import logging
import shlex
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal

from agentcompass.harnesses.utils.model import build_model_api_config
from agentcompass.runtime import (HARNESSES, AssistantContent, BaseHarness, EnvironmentSession, EnvironmentSpec,
                                  ExecResult, HarnessPlan, ModelSpec, PreparedTask, RunRequest, RunResult, StepInfo,
                                  TaskStatus, Trajectory, TrajMetric)
from agentcompass.runtime.config import (RuntimeHarnessConfig, config_field, normalize_choice, parse_bool,
                                         parse_optional_positive_int)
from agentcompass.runtime.llm import ApiProtocol, select_api_protocol
from agentcompass.utils.call import maybe_call

logger = logging.getLogger(__name__)

# JiuwenSwarm writes these into its working directory (coding memory / logs).
_WORKSPACE_ARTIFACTS = ("memory.db", "memory.db-shm", "memory.db-wal", "daily_memory", "logs", ".jiuwenswarm")
# Events that carry a fatal runtime/agent failure in the process CLI event stream.
_ERROR_EVENTS = ("chat.error", "runtime.error")
_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")


@dataclass(slots=True)
class JiuwenSwarmConfig(RuntimeHarnessConfig):
    """User-facing params for the JiuwenSwarm harness."""

    binary: str = config_field(
        default="jiuwenswarm-process",
        description="Executable name or path; for container runs point it at the mounted vendor tree.",
    )
    install_strategy: Literal["preinstalled", "install_if_missing", "upload"] = config_field(
        default="preinstalled",
        description="How to prepare the executable: preinstalled, install_if_missing, or upload.",
    )
    install_command: str = config_field(
        default="/opt/jiuwenswarm-vendor/venv/bin/python -m pip install workswarm",
        description="Command run when install_strategy is install_if_missing (workswarm needs python 3.11-3.13).",
    )
    upload_src: str = config_field(default="", description="Local file path uploaded by the upload install strategy.")
    upload_dst: str = config_field(default="/usr/local/bin/jiuwenswarm-process",
                                   description="Target path used by the upload install strategy.")
    mode: str = config_field(default="code.normal", description="JiuwenSwarm run mode passed to --mode.")
    model_provider: str = config_field(
        default="OpenAI",
        description="Value of MODEL_PROVIDER: OpenAI for OpenAI-compatible endpoints (MaaS/DeepSeek/DashScope).",
    )
    api_key_env: str = config_field(
        default="API_KEY",
        description="Environment variable carrying the model api key (JiuwenSwarm reads API_KEY).",
    )
    output: Literal["json", "jsonl", "human"] = config_field(
        default="json",
        description="Value of --output; json yields one document with events including chat.final.",
    )
    timeout: int | None = config_field(default=None, description="Task wall-clock timeout in seconds (--timeout).")
    prompt_append: str = config_field(
        default="",
        description="Text appended to the task prompt before the expected-answer spec.",
    )
    clear_proxy: bool = config_field(
        default=True,
        description="Clear HTTP_PROXY/HTTPS_PROXY for the process so the model endpoint is reached directly.",
    )
    no_proxy: str = config_field(
        default=".aliyuncs.com",
        description="Value of no_proxy, keeping the model endpoint off any proxy.",
    )
    config_home: str = config_field(
        default="",
        description="Optional JIUWENSWARM_HOME/JIUWENSWARM_DATA_DIR value isolating memory.db and logs.",
    )
    cleanup_workspace_artifacts: bool = config_field(
        default=True,
        description="Remove memory.db/daily_memory/logs that JiuwenSwarm writes into the workspace.",
    )

    def __post_init__(self) -> None:
        self.binary = str(self.binary or "").strip()
        if not self.binary:
            raise ValueError("binary is required")
        self.install_strategy = normalize_choice(
            self.install_strategy,
            "install_strategy",
            {"preinstalled", "install_if_missing", "upload"},
        )
        self.install_command = str(self.install_command or "").strip()
        self.upload_src = str(self.upload_src or "").strip()
        self.upload_dst = str(self.upload_dst or "").strip()
        self.mode = str(self.mode or "").strip() or "code.normal"
        self.model_provider = str(self.model_provider or "").strip() or "OpenAI"
        self.api_key_env = str(self.api_key_env or "").strip() or "API_KEY"
        self.output = normalize_choice(self.output, "output", {"json", "jsonl", "human"})
        self.timeout = parse_optional_positive_int(self.timeout, "timeout")
        self.prompt_append = str(self.prompt_append or "").strip()
        self.clear_proxy = parse_bool(self.clear_proxy, "clear_proxy")
        self.no_proxy = str(self.no_proxy or "").strip()
        self.config_home = str(self.config_home or "").strip()
        self.cleanup_workspace_artifacts = parse_bool(
            self.cleanup_workspace_artifacts,
            "cleanup_workspace_artifacts",
        )


@dataclass(slots=True)
class JiuwenSwarmHarnessPlan(HarnessPlan):
    # Execution state derived from JiuwenSwarmConfig plus the selected
    # environment; recipes may adjust the plan without mutating config.
    binary: str = "jiuwenswarm-process"
    install_strategy: Literal["preinstalled", "install_if_missing", "upload"] = "preinstalled"
    install_command: str = "/opt/jiuwenswarm-vendor/venv/bin/python -m pip install workswarm"
    upload_src: str = ""
    upload_dst: str = "/usr/local/bin/jiuwenswarm-process"
    mode: str = "code.normal"
    model_provider: str = "OpenAI"
    api_key_env: str = "API_KEY"
    output: Literal["json", "jsonl", "human"] = "json"
    timeout: int | None = None
    prompt_append: str = ""
    clear_proxy: bool = True
    no_proxy: str = ".aliyuncs.com"
    config_home: str = ""
    cleanup_workspace_artifacts: bool = True


@HARNESSES.register()
class JiuwenSwarmHarness(BaseHarness):
    """Run the JiuwenSwarm multi-agent swarm through its non-interactive process CLI."""

    id = "jiuwenswarm"
    parallel_attempts_safe = True
    description = (
        "Runs JiuwenSwarm (openJiuwen, PyPI package workswarm) through its non-interactive "
        "jiuwenswarm-process CLI as a coding agent for prepared workspaces such as SWE-bench. "
        "Model credentials are inlined via API_BASE/API_KEY/MODEL_NAME/MODEL_PROVIDER."
    )
    config_class = JiuwenSwarmConfig
    plan_class = JiuwenSwarmHarnessPlan

    def supports(self, environment: EnvironmentSpec, model: ModelSpec) -> bool:
        protocols = model.api_protocols
        preferred = [ApiProtocol.OPENAI_CHAT]
        if protocols:
            select_api_protocol(model.api_protocol, preferred, component=self.id)
        return True

    async def start_session(self, env: EnvironmentSession, req: RunRequest,
                            plan: JiuwenSwarmHarnessPlan) -> Dict[str, Any]:
        binary = str(plan.binary)
        install_strategy = str(plan.install_strategy or "preinstalled")
        if install_strategy == "install_if_missing":
            check_result = await env.exec(["command", "-v", shlex.quote(binary)])
            if check_result.returncode != 0:
                install_result = await env.exec(str(plan.install_command), shell=True)
                if install_result.returncode != 0:
                    raise RuntimeError(f"JiuwenSwarm install failed: {install_result.stderr.strip()}")
        elif install_strategy == "upload":
            if not plan.upload_src:
                raise RuntimeError("JiuwenSwarm `upload_src` is not specified.")
            await env.upload(plan.upload_src, plan.upload_dst)
            await env.exec(["chmod", "+x", plan.upload_dst])
            binary = str(plan.upload_dst)

        if binary.startswith("/"):
            probe = await env.exec(["test", "-x", binary])
            if probe.returncode != 0:
                raise RuntimeError(
                    f"JiuwenSwarm binary is not executable: {binary}. "
                    "Vendor it on the host and mount it read-only, e.g. "
                    "--env-params '{\"mounts\":[{\"mode\":\"ro\",\"source\":\"~/.jiuwenswarm-vendor\","
                    "\"target\":\"/opt/jiuwenswarm-vendor\"}]}' with "
                    "--harness-params '{\"binary\":\"/opt/jiuwenswarm-vendor/bin/jiuwenswarm-process\"}'."
                )
        else:
            resolve_result = await env.exec(["command", "-v", shlex.quote(binary)])
            if resolve_result.returncode != 0:
                raise RuntimeError(f"JiuwenSwarm binary resolution failed: {binary}")
            binary = resolve_result.stdout.strip()

        return {
            "env": env,
            "binary": binary,
            "workspace_root": getattr(env, "default_workspace_root", None) or getattr(env, "workspace", None)
            or "workspace/",
            "model_config": build_model_api_config(req.model),
        }

    @staticmethod
    def _build_prompt(prompt_text: str, answer_spec: str | None, output_files: list[Any],
                      prompt_append: str = "") -> str:
        has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in prompt_text)
        lang = "请用中文回答。" if has_chinese else "Please answer in English."
        lines = [lang]
        lines += ["", prompt_text.rstrip()]
        if prompt_append:
            lines += ["", prompt_append.rstrip()]
        if answer_spec:
            lines.extend(["", f"Expected answer: {answer_spec}"])
        if output_files:
            lines.extend(["", "Write the following files:"])
            for output_file in output_files:
                lines.append(f"- {output_file.path}: {output_file.description}")
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _build_default_workspace(root: str, req: RunRequest, prepared: PreparedTask) -> str:
        task_id = str(prepared.task_id or "task").strip().replace("/", "_")
        return str(Path(root) / req.benchmark.id / task_id / uuid.uuid4().hex[:8])

    @staticmethod
    def _resolve_output_path(workspace: str, requested_path: str) -> str:
        candidate = Path(str(requested_path))
        if candidate.is_absolute():
            return str(candidate)
        return str(Path(workspace) / candidate)

    async def run_task(
        self,
        session: Dict[str, Any],
        prepared: PreparedTask,
        req: RunRequest,
        plan: JiuwenSwarmHarnessPlan,
    ) -> RunResult:
        env: EnvironmentSession = session["env"]
        prompt_text = str(prepared.input.prompt or "").strip()
        if not prompt_text:
            raise ValueError("jiuwenswarm requires prepared.input.prompt")
        workspace = str(prepared.input.workspace or "").strip()
        if not workspace:
            workspace = self._build_default_workspace(str(session.get("workspace_root") or "workspace/"), req, prepared)
        mkdir_result = await env.exec(["mkdir", "-p", workspace])
        if mkdir_result.returncode != 0:
            raise RuntimeError(f"Failed to create JiuwenSwarm workspace {workspace}: {mkdir_result.stderr.strip()}")

        requested_files = list(prepared.output.files)
        prompt = self._build_prompt(prompt_text, prepared.output.answer, requested_files, plan.prompt_append)

        argv = [
            session["binary"],
            prompt,
            "--mode", str(plan.mode),
            "--cwd", workspace,
            "--project-dir", workspace,
            "--trusted-dir", workspace,
            "--output", str(plan.output),
        ]
        if plan.timeout:
            argv += ["--timeout", str(plan.timeout)]

        model_config = dict(session["model_config"])
        base_url = str(model_config.get("base_url") or "").strip()
        api_key = str(model_config.get("api_key") or "").strip()
        if not base_url:
            raise RuntimeError("JiuwenSwarm requires an OpenAI-compatible base url")

        # workswarm 0.2.7 inlines the model through environment variables; the
        # package default config.yaml is a ${API_BASE}/${API_KEY}/... template.
        exec_env: Dict[str, str] = {
            "API_BASE": base_url,
            "API_KEY": api_key,
            str(plan.api_key_env): api_key,
            "MODEL_NAME": req.model.id,
            "MODEL_PROVIDER": str(plan.model_provider),
        }
        if plan.no_proxy:
            exec_env["no_proxy"] = plan.no_proxy
            exec_env["NO_PROXY"] = plan.no_proxy
        if plan.config_home:
            exec_env["JIUWENSWARM_HOME"] = plan.config_home
            exec_env["JIUWENSWARM_DATA_DIR"] = plan.config_home
        if plan.clear_proxy:
            # httpx honours HTTP(S)_PROXY; the model endpoint is reached directly.
            for proxy_var in _PROXY_VARS:
                exec_env[proxy_var] = ""
        exec_env = {key: value for key, value in exec_env.items() if value != "" or key in _PROXY_VARS}
        command_text = shlex.join(argv)

        started_at = datetime.now().astimezone()
        try:
            run_result = await maybe_call(
                env.exec,
                command_text,
                shell=True,
                cwd=workspace,
                env=exec_env,
                timeout=plan.timeout,
                flags={"polling_exec": True},
            )
        except Exception:
            error = traceback.format_exc()
            logger.exception("JiuwenSwarm command execution failed | task=%s", prepared.task_id)
            run_result = ExecResult(returncode=-1, stderr=error)
        finished_at = datetime.now().astimezone()

        payload = self._parse_output(run_result.stdout)
        events = self._events(payload)
        final_answer = self._extract_final_answer(events, run_result.stdout)
        trajectory, usage = self._build_trajectory(events, prompt, started_at, finished_at)

        collected_files: Dict[str, str] = {}
        resolved_output_paths: Dict[str, str] = {}
        missing_files: list[str] = []
        for output_file in requested_files:
            path = str(output_file.path)
            resolved_path = self._resolve_output_path(workspace, path)
            resolved_output_paths[path] = resolved_path
            try:
                collected_files[path] = await env.read_text(resolved_path)
            except Exception:
                missing_files.append(path)

        removed_artifacts: list[str] = []
        if plan.cleanup_workspace_artifacts:
            removed_artifacts = await self._cleanup_workspace(env, workspace)

        metrics: Dict[str, Any] = {
            "exit_code": run_result.returncode,
            "timed_out": bool(getattr(run_result, "timed_out", False)),
            "stdout": run_result.stdout,
            "stderr": run_result.stderr,
            "workspace": workspace,
            "jiuwenswarm_mode": str(plan.mode),
            "jiuwenswarm_output": str(plan.output),
            "jiuwenswarm_ok": payload.get("ok") if isinstance(payload, dict) else None,
            "jiuwenswarm_session_id": payload.get("session_id") if isinstance(payload, dict) else None,
            "jiuwenswarm_request_id": payload.get("request_id") if isinstance(payload, dict) else None,
            "model_base_url": base_url,
            "model_api_protocol": model_config.get("api_protocol"),
            "requested_output_files": [output_file.path for output_file in requested_files],
            "resolved_output_files": resolved_output_paths,
            "removed_workspace_artifacts": removed_artifacts,
        }
        if usage:
            metrics["usage"] = usage
        if missing_files:
            metrics["missing_output_files"] = missing_files

        error = None
        if getattr(run_result, "timed_out", False) or run_result.returncode == 124:
            error = f"JiuwenSwarm timed out after {plan.timeout} seconds"
        else:
            # The process CLI logs everything to stderr, so prefer the
            # structured failure reported in the JSON event stream.
            error = self._run_error(payload)
            if error is None and run_result.returncode != 0:
                stderr_tail = run_result.stderr.strip()[-2000:]
                error = (f"JiuwenSwarm exited with returncode={run_result.returncode}"
                         + (f": {stderr_tail}" if stderr_tail else ""))
        if error is None and missing_files:
            error = "Requested output files missing: " + ", ".join(missing_files)

        return RunResult(
            task_id=prepared.task_id,
            status=TaskStatus.RUN_ERROR if error else TaskStatus.COMPLETED,
            final_answer=final_answer,
            trajectory=trajectory,
            telemetry=metrics,
            artifacts={
                "file": collected_files,
                "raw_jiuwenswarm_output": payload,
            },
            error=error,
        )

    async def close_session(self, session: Any) -> None:
        # The process CLI is a one-shot subprocess; nothing long-lived to stop.
        return None

    @staticmethod
    async def _cleanup_workspace(env: EnvironmentSession, workspace: str) -> list[str]:
        removed: list[str] = []
        for name in _WORKSPACE_ARTIFACTS:
            target = str(Path(workspace) / name)
            probe = await env.exec(["test", "-e", target])
            if probe.returncode != 0:
                continue
            await env.exec(["rm", "-rf", target])
            removed.append(target)
        if removed:
            logger.debug("JiuwenSwarm workspace artifacts removed | workspace=%s | paths=%s", workspace,
                         ",".join(removed))
        return removed

    @staticmethod
    def _parse_output(stdout: str) -> Dict[str, Any]:
        """Parse `--output json` stdout into one payload dict (tolerant of stray log lines)."""
        text = str(stdout or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            pass
        # Tolerate leading/trailing log lines by slicing the outermost object.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start:end + 1])
                return payload if isinstance(payload, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _events(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
        events = payload.get("events") if isinstance(payload, dict) else None
        if not isinstance(events, list):
            return []
        return [event for event in events if isinstance(event, dict)]

    @staticmethod
    def _event_body(event: Dict[str, Any]) -> Dict[str, Any]:
        body = event.get("payload")
        return body if isinstance(body, dict) else event

    @classmethod
    def _event_type(cls, event: Dict[str, Any]) -> str:
        body = cls._event_body(event)
        return str(body.get("event_type") or body.get("type") or event.get("event_type") or event.get("type") or "")

    @staticmethod
    def _content_of(body: Dict[str, Any]) -> str:
        for key in ("content", "text", "delta", "message"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                nested = value.get("content")
                if isinstance(nested, str) and nested:
                    return nested
        return ""

    @classmethod
    def _extract_final_answer(cls, events: list[Dict[str, Any]], stdout: str) -> str:
        answer = ""
        for event in events:
            if cls._event_type(event) != "chat.final":
                continue
            text = cls._content_of(cls._event_body(event))
            if text:
                answer = text
        if answer:
            return answer
        # Fallbacks: an explicit answer field, then accumulated deltas.
        deltas = [cls._content_of(cls._event_body(event)) for event in events
                  if cls._event_type(event) == "chat.delta"]
        joined = "".join(part for part in deltas if part).strip()
        return joined or str(stdout or "")

    @classmethod
    def _usage(cls, body: Dict[str, Any]) -> Dict[str, Any]:
        usage = body.get("usage_metadata") or body.get("metadata") or {}
        while isinstance(usage, dict) and isinstance(usage.get("usage_metadata"), dict):
            usage = usage["usage_metadata"]
        if not isinstance(usage, dict):
            usage = {}
        payload = {
            "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
            "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"),
            "cost": usage.get("cost") or usage.get("total_cost"),
        }
        if not any(payload.values()):
            # context.usage reports an estimated context size per model call.
            window = body.get("context_window") if isinstance(body.get("context_window"), dict) else {}
            estimated = body.get("tokens_used") or window.get("input_tokens")
            if estimated:
                payload["input_tokens"] = estimated
        return {key: value for key, value in payload.items() if value is not None}

    @classmethod
    def _build_trajectory(cls, events: list[Dict[str, Any]], prompt: str, started_at: datetime,
                          finished_at: datetime) -> tuple[Trajectory, Dict[str, Any]]:
        trajectory = Trajectory(started_at=started_at, finished_at=finished_at, steps=[])
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[Dict[str, Any]] = []
        observations: list[Any] = []
        usage_total: Dict[str, Any] = {}
        context_estimate: int | None = None

        def accumulate_usage(body: Dict[str, Any]) -> None:
            nonlocal context_estimate
            usage = cls._usage(body)
            explicit = any(key in usage for key in ("output_tokens", "reasoning_tokens", "cost"))
            for key, value in usage.items():
                if not isinstance(value, (int, float)):
                    continue
                if explicit:
                    usage_total[key] = usage_total.get(key, 0) + value
                elif key == "input_tokens":
                    # Estimated context size per model call: keep the largest,
                    # it is only a fallback when no explicit usage arrives.
                    context_estimate = max(context_estimate or 0, int(value))

        def flush(step_end: datetime | None) -> None:
            nonlocal text_parts, reasoning_parts, tool_calls, observations
            if not (text_parts or reasoning_parts or tool_calls or observations):
                return
            trajectory.steps.append(
                StepInfo(
                    step_id=len(trajectory.steps) + 1,
                    assistant_content=AssistantContent(
                        content="".join(text_parts).strip(),
                        reasoning_content="".join(reasoning_parts).strip(),
                        tool_calls=list(tool_calls),
                    ),
                    metric=TrajMetric(),
                    system_prompt="",
                    user_content=prompt if len(trajectory.steps) == 0 else "",
                    tools=list(tool_calls),
                    observation=list(observations),
                    started_at=started_at if len(trajectory.steps) == 0 else (step_end or started_at),
                    finished_at=step_end or finished_at,
                )
            )
            text_parts, reasoning_parts, tool_calls, observations = [], [], [], []

        for event in events:
            event_type = cls._event_type(event)
            body = cls._event_body(event)
            if event_type == "chat.delta":
                text_parts.append(cls._content_of(body))
            elif event_type == "chat.reasoning":
                reasoning_parts.append(cls._content_of(body))
            elif event_type == "chat.tool_call":
                tool_calls.append({
                    "id": body.get("tool_call_id") or body.get("id"),
                    "name": body.get("name") or body.get("tool_name") or body.get("tool"),
                    "arguments": body.get("arguments") or body.get("input") or body.get("args"),
                })
            elif event_type == "chat.tool_update":
                name = body.get("name") or body.get("tool_name")
                if name and tool_calls:
                    if not tool_calls[-1].get("name"):
                        tool_calls[-1]["name"] = name
                elif name:
                    tool_calls.append({"name": name, "arguments": body.get("arguments")})
            elif event_type == "chat.tool_result":
                observations.append({
                    "name": body.get("name") or body.get("tool_name"),
                    "content": cls._content_of(body) or body.get("result") or body.get("output"),
                })
                flush(finished_at)
            elif event_type in {"chat.usage_metadata", "chat.usage_summary", "context.usage"}:
                accumulate_usage(body)
        flush(finished_at)
        if not usage_total and context_estimate:
            usage_total = {"input_tokens": context_estimate, "tokens_source": "context_estimate"}
        return trajectory, usage_total

    @classmethod
    def _run_error(cls, payload: Dict[str, Any]) -> str | None:
        if not isinstance(payload, dict) or not payload:
            return None
        # The process CLI reports fatal failures as chat.error / runtime.error
        # events and only flips the top-level `ok` flag to false.
        for event in cls._events(payload):
            event_type = cls._event_type(event)
            if event_type not in _ERROR_EVENTS:
                continue
            body = cls._event_body(event)
            message = body.get("error") or body.get("message") or event.get("error")
            detail = str(message).strip() if message else "no error message in event"
            return f"JiuwenSwarm {event_type}: {detail}"
        if payload.get("ok") is False:
            message = payload.get("error") or payload.get("message") or payload.get("error_message")
            detail = str(message).strip() if message else "no error message in output"
            return f"JiuwenSwarm reported failure: {detail}"
        return None
