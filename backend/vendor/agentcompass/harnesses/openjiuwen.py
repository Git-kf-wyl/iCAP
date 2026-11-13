"""OpenJiuwen (openjiuwen-eval) coding agent harness.

Runs the ``openjiuwen-eval`` entry script non-interactively against a prepared
workspace.  The entry script wraps openjiuwen's ``create_agent`` without the
approval rails (AskUserRail / ConfirmInterruptRail), so ``write_file`` /
``edit_file`` are allowed without approval.

Model credentials are injected via environment variables
(``OPENJIUWEN_API_BASE`` / ``OPENJIUWEN_API_KEY`` / ``OPENJIUWEN_MODEL`` /
``OPENJIUWEN_PROVIDER``) rather than a config file, so the API key never lands
on disk or in the command line.

Design notes (see DevDocs/Harness接入/openjiuwen接入方案.md and
openjiuwen-eval入口脚本设计.md):

* vendor + ro-mount (``~/.openjiuwen-vendor`` -> ``/opt/openjiuwen-vendor``),
  ``install_strategy=preinstalled`` with an absolute ``binary`` path.
* ``--output-format json`` yields a single JSON object whose ``result`` field
  is the final answer.  ``stream-json`` carries a per-chunk trajectory.
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
from agentcompass.runtime import (HARNESSES, BaseHarness, EnvironmentSession, EnvironmentSpec, ExecResult, HarnessPlan,
                                  ModelSpec, PreparedTask, RunRequest, RunResult, TaskStatus)
from agentcompass.runtime.config import (RuntimeHarnessConfig, config_field, normalize_choice, parse_bool,
                                         parse_optional_positive_int)
from agentcompass.runtime.llm import ApiProtocol, select_api_protocol
from agentcompass.utils.call import maybe_call

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenJiuwenConfig(RuntimeHarnessConfig):
    """User-facing params for the OpenJiuwen harness."""

    binary: str = config_field(default="openjiuwen-eval", description="Executable name or path.")
    install_strategy: Literal["preinstalled", "install_if_missing", "upload"] = config_field(
        default="preinstalled",
        description="How to prepare the executable.",
    )
    install_command: str = config_field(
        default="pip install openjiuwen[cli]",
        description="Command run when install_strategy needs to install the tool.",
    )
    provider: str = config_field(
        default="OpenAI",
        description="Model provider written into the OPENJIUWEN_PROVIDER env var.",
    )
    output: Literal["json", "stream-json"] = config_field(
        default="json",
        description="Entry script output format (--output-format).",
    )
    timeout: int | None = config_field(default=None, description="Task wall-clock timeout in seconds.")
    prompt_append: str = config_field(default="", description="Text appended to the task prompt.")
    clear_proxy: bool = config_field(
        default=True,
        description="Clear HTTP_PROXY/HTTPS_PROXY for the entry script (model endpoint goes no_proxy direct).",
    )

    def __post_init__(self) -> None:
        self.binary = str(self.binary or "").strip()
        if not self.binary:
            raise ValueError("binary is required")
        self.install_strategy = normalize_choice(
            self.install_strategy, "install_strategy", {"preinstalled", "install_if_missing", "upload"}
        )
        self.install_command = str(self.install_command or "").strip()
        self.provider = str(self.provider or "").strip() or "OpenAI"
        self.output = normalize_choice(self.output, "output", {"json", "stream-json"})
        self.timeout = parse_optional_positive_int(self.timeout, "timeout")
        self.prompt_append = str(self.prompt_append or "").strip()
        self.clear_proxy = parse_bool(self.clear_proxy, "clear_proxy")


@dataclass(slots=True)
class OpenJiuwenHarnessPlan(HarnessPlan):
    binary: str = "openjiuwen-eval"
    install_strategy: Literal["preinstalled", "install_if_missing", "upload"] = "preinstalled"
    install_command: str = "pip install openjiuwen[cli]"
    provider: str = "OpenAI"
    output: Literal["json", "stream-json"] = "json"
    timeout: int | None = None
    prompt_append: str = ""
    clear_proxy: bool = True


@HARNESSES.register()
class OpenJiuwenHarness(BaseHarness):
    """Run the openjiuwen-eval entry script non-interactively against a prepared workspace."""

    id = "openjiuwen"
    parallel_attempts_safe = True
    description = "Runs the openJiuwen (agent-core) coding agent through the openjiuwen-eval entry script (approval rails removed) as a non-interactive coding agent for prepared workspaces such as SWE-bench and Terminal-Bench (https://github.com/openJiuwen-ai/agent-core)."
    config_class = OpenJiuwenConfig
    plan_class = OpenJiuwenHarnessPlan

    API_BASE_ENV = "OPENJIUWEN_API_BASE"
    API_KEY_ENV = "OPENJIUWEN_API_KEY"
    MODEL_ENV = "OPENJIUWEN_MODEL"
    PROVIDER_ENV = "OPENJIUWEN_PROVIDER"

    _PROXY_ENV_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")

    def supports(self, environment: EnvironmentSpec, model: ModelSpec) -> bool:
        protocols = model.api_protocols
        preferred = [ApiProtocol.OPENAI_CHAT]
        if protocols:
            select_api_protocol(model.api_protocol, preferred, component=self.id)
        return True

    async def start_session(self, env: EnvironmentSession, req: RunRequest, plan: OpenJiuwenHarnessPlan) -> Dict[str, Any]:
        binary = str(plan.binary)
        install_strategy = str(plan.install_strategy or "preinstalled")
        if install_strategy == "install_if_missing":
            check_result = await env.exec(["command", "-v", shlex.quote(binary)])
            if check_result.returncode != 0:
                install_result = await env.exec(str(plan.install_command), shell=True)
                if install_result.returncode != 0:
                    raise RuntimeError(f"OpenJiuwen install failed: {install_result.stderr.strip()}")
        elif install_strategy == "upload":
            raise RuntimeError("OpenJiuwen upload install strategy is not supported (needs a full venv)")

        if not binary.startswith("/"):
            resolve_result = await env.exec(["command", "-v", shlex.quote(binary)])
            if resolve_result.returncode != 0:
                raise RuntimeError(f"OpenJiuwen binary resolution failed: {binary}")
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

    async def run_task(self, session: Dict[str, Any], prepared: PreparedTask, req: RunRequest,
                       plan: OpenJiuwenHarnessPlan) -> RunResult:
        env: EnvironmentSession = session["env"]
        prompt_text = str(prepared.input.prompt or "").strip()
        if not prompt_text:
            raise ValueError("openjiuwen requires prepared.input.prompt")
        workspace = str(prepared.input.workspace or "").strip()
        if not workspace:
            workspace = self._build_default_workspace(str(session.get("workspace_root") or "workspace/"), req, prepared)
        mkdir_result = await env.exec(["mkdir", "-p", workspace])
        if mkdir_result.returncode != 0:
            raise RuntimeError(f"Failed to create openjiuwen workspace {workspace}: {mkdir_result.stderr.strip()}")

        requested_files = list(prepared.output.files)
        prompt = self._build_prompt(prompt_text, prepared.output.answer, requested_files, plan.prompt_append)

        model_config: Dict[str, Any] = session["model_config"]
        api_base = str(model_config.get("base_url") or "").strip()
        api_key = str(model_config.get("api_key") or "").strip()
        if not api_base:
            raise RuntimeError("OpenJiuwen requires an OpenAI-compatible base url")
        if not api_key:
            raise RuntimeError("OpenJiuwen requires an OpenAI-compatible api key")

        exec_env: Dict[str, str] = {
            self.API_BASE_ENV: api_base,
            self.API_KEY_ENV: api_key,
            self.MODEL_ENV: req.model.id,
            self.PROVIDER_ENV: plan.provider,
            "no_proxy": ".aliyuncs.com,.deepseek.com",
        }
        if plan.clear_proxy:
            for proxy_var in self._PROXY_ENV_VARS:
                exec_env[proxy_var] = ""

        argv = [
            session["binary"],
            prompt,
            "--workspace", workspace,
            "--output-format", plan.output,
        ]
        command_text = shlex.join(argv)

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
            logger.exception("OpenJiuwen command execution failed | task=%s", prepared.task_id)
            run_result = ExecResult(returncode=-1, stderr=error)

        output_data = self._parse_output(run_result.stdout)
        final_answer = output_data.get("result", "") if isinstance(output_data, dict) else ""

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

        metrics: Dict[str, Any] = {
            "exit_code": run_result.returncode,
            "stdout": run_result.stdout,
            "stderr": run_result.stderr,
            "workspace": workspace,
            "model_base_url": api_base,
            "model_provider": plan.provider,
            "output_format": plan.output,
            "requested_output_files": [output_file.path for output_file in requested_files],
            "resolved_output_files": resolved_output_paths,
        }
        if output_data:
            metrics["chunks"] = output_data.get("chunks")
            metrics["model"] = output_data.get("model")
        if missing_files:
            metrics["missing_output_files"] = missing_files

        error = ""
        if run_result.timed_out:
            error = f"OpenJiuwen command timed out after {plan.timeout} seconds"
        elif run_result.returncode != 0:
            error = run_result.stderr.strip() or f"OpenJiuwen command failed: returncode={run_result.returncode}"
        if not error and missing_files:
            error = "Requested output files missing: " + ", ".join(missing_files)

        return RunResult(
            task_id=prepared.task_id,
            status=TaskStatus.RUN_ERROR if error else TaskStatus.COMPLETED,
            final_answer=final_answer,
            telemetry=metrics,
            artifacts={
                "file": collected_files,
                "raw_output": output_data,
            },
            error=error,
        )

    async def close_session(self, session: Dict[str, Any]) -> None:
        return None

    @staticmethod
    def _parse_output(stdout: str) -> Dict[str, Any]:
        text = str(stdout or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("OpenJiuwen --output-format json payload was not valid JSON")
            return {}
        return data if isinstance(data, dict) else {}
