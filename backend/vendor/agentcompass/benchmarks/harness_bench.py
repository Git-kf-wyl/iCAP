"""harness-bench 接入 agentcompass 的 benchmark 实现。

评测 Qihoo360/harness-bench（https://github.com/Qihoo360/harness-bench）的
274 道通用任务，用 agentcompass 自己的 harness（vendor 挂载）做横向对比。

评测流程（fresh 双容器模式）：
1. load_tasks        读 task.yaml + instruction.md
2. prepare_task      把 task 的 workspace/ 种子复制进 agent 容器 /workspace
3. harness run_task  agent 在 /workspace 干活，产出 required_artifacts
4. collect_artifacts no-op（/workspace 通过 host mount 已同步，MVP 不做 mutation report）
5. evaluate          起 grader 容器，挂 /workspace(ro) + /hidden(ro)，跑
                     grade_entrypoint.py，解析 outcome_score

镜像约定：
- 通用 agent 镜像：python:3.12-slim-bookworm + 17 包 task-toolchain
- grader 镜像：harness-bench docker/grader 的变体，ENTRYPOINT 改为 tail -f /dev/null
  （长驻，由 evaluate 用 docker exec 跑 grade_entrypoint.py）

安全门槛（mutation_contract）与语义判分（semantic_judge）留待第二阶段。
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

from agentcompass.benchmarks.config import RuntimeBenchmarkConfig, _parse_positive_int, config_field
from agentcompass.runtime import (
    BENCHMARKS,
    BaseBenchmark,
    BenchmarkPlan,
    EnvironmentSession,
    ExecutionPlan,
    PreparedTask,
    RunRequest,
    RunResult,
    TaskInput,
    TaskOutput,
    TaskSpec,
    TaskStatus,
    get_runtime_settings,
)

_DEFAULT_AGENT_IMAGE = "harnessbench/agent-tools:local"
_DEFAULT_GRADER_IMAGE = "harnessbench/grader:local"
_DEFAULT_WORKSPACE = "/workspace"

# task.yaml 里必读的字段
_TASK_FIELDS = (
    "task_id",
    "prompt_file",
    "timeout_sec",
    "required_artifacts",
    "workspace_dir",
    "outcome_test",
    "cases_file",
)


@dataclass(slots=True)
class HarnessBenchConfig(RuntimeBenchmarkConfig):
    """harness-bench 运行时配置。"""

    tasks_dir: str = config_field(
        default="",
        description="harness-bench tasks 根目录（含 001-xxx/ 等子目录）。",
    )
    agent_image: str = config_field(
        default=_DEFAULT_AGENT_IMAGE,
        description="通用 agent 镜像（agent 干活的容器）。",
    )
    grader_image: str = config_field(
        default=_DEFAULT_GRADER_IMAGE,
        description="grader 镜像（评分容器，ENTRYPOINT 为长驻 tail）。",
    )
    workspace_dir: str = config_field(
        default=_DEFAULT_WORKSPACE,
        description="容器内工作目录（agent 产物 + grader 评分对象）。",
    )
    eval_timeout: int = config_field(
        default=1800,
        description="grader 评分超时（秒）。",
    )

    def __post_init__(self) -> None:
        RuntimeBenchmarkConfig.__post_init__(self)
        self.tasks_dir = str(self.tasks_dir or "").strip()
        if not self.tasks_dir:
            raise ValueError("harness_bench requires tasks_dir")
        self.agent_image = str(self.agent_image or "").strip()
        self.grader_image = str(self.grader_image or "").strip()
        if not self.agent_image or not self.grader_image:
            raise ValueError("harness_bench requires agent_image and grader_image")
        self.workspace_dir = str(self.workspace_dir or "/workspace").strip()
        self.eval_timeout = _parse_positive_int(self.eval_timeout, "eval_timeout")


@dataclass(slots=True)
class HarnessBenchBenchmarkPlan(BenchmarkPlan):
    """单题运行计划（build_plan 产出，recipe 据此注入 mount/image）。"""

    tasks_dir: str = ""
    task_dir: str = ""
    workspace_dir: str = "/workspace"
    workspace_host_dir: str = ""
    grader_control_host_dir: str = ""
    agent_image: str = _DEFAULT_AGENT_IMAGE
    grader_image: str = _DEFAULT_GRADER_IMAGE
    eval_timeout: int = 1800


def _host_workspace_root(task_id: str) -> Path:
    """agent 与 grader 共享的 host 中转目录（挂载源）。"""
    results_root = Path(get_runtime_settings().results_dir).resolve()
    return results_root / "harness_bench" / "workspaces" / str(task_id)


@BENCHMARKS.register()
class HarnessBenchBenchmark(BaseBenchmark):
    """Harness-Bench 通用任务评测。"""

    id = "harness_bench"
    description = (
        "Harness-Bench: Measuring Harness Effects across Models "
        "(https://github.com/Qihoo360/harness-bench)."
    )
    config_class = HarnessBenchConfig
    evaluation_environment_mode = "fresh"
    parallel_attempts_safe = False

    # ── load_tasks ──────────────────────────────────────────────────────────

    def load_tasks(self, req: RunRequest) -> list[TaskSpec]:
        config = self.build_config(req)
        tasks_root = Path(config.tasks_dir).resolve()
        if not tasks_root.is_dir():
            raise FileNotFoundError(f"harness_bench tasks 目录不存在: {tasks_root}")

        tasks: list[TaskSpec] = []
        for task_dir in sorted(tasks_root.iterdir()):
            if not task_dir.is_dir():
                continue
            task_yaml_path = task_dir / "task.yaml"
            if not task_yaml_path.is_file():
                continue
            spec = yaml.safe_load(task_yaml_path.read_text(encoding="utf-8"))
            if not isinstance(spec, dict):
                continue

            task_id = str(spec.get("task_id") or task_dir.name)
            prompt_file = str(spec.get("prompt_file") or "instruction.md")
            instruction_path = task_dir / prompt_file
            if instruction_path.is_file():
                instruction = instruction_path.read_text(encoding="utf-8")
            else:
                instruction = ""

            tasks.append(
                TaskSpec(
                    task_id=task_id,
                    question=instruction,
                    category=str(spec.get("task_category") or "all"),
                    ground_truth=None,
                    metadata={
                        "task_dir": str(task_dir),
                        "task_yaml": spec,
                        "prompt_file": prompt_file,
                        "workspace_dir": str(spec.get("workspace_dir") or "workspace"),
                        "timeout_sec": int(spec.get("timeout_sec") or 7200),
                        "required_artifacts": list(spec.get("required_artifacts") or []),
                        "outcome_test": str(spec.get("outcome_test") or ""),
                        "cases_file": str(spec.get("cases_file") or ""),
                        "pass_threshold": float(
                            _load_pass_threshold(task_dir, spec)
                        ),
                    },
                )
            )
        return tasks

    # ── build_plan ──────────────────────────────────────────────────────────

    def build_plan(self, task: TaskSpec, req: RunRequest,
                   environment) -> HarnessBenchBenchmarkPlan:
        config = self.build_config(req)
        _ = environment
        task_dir = str(task.metadata["task_dir"])
        host_root = _host_workspace_root(task.task_id)
        workspace_host_dir = host_root / "workspace"
        grader_control_host_dir = host_root / "grader-control"
        workspace_host_dir.mkdir(parents=True, exist_ok=True)
        grader_control_host_dir.mkdir(parents=True, exist_ok=True)
        return HarnessBenchBenchmarkPlan(
            tasks_dir=config.tasks_dir,
            task_dir=task_dir,
            workspace_dir=config.workspace_dir,
            workspace_host_dir=str(workspace_host_dir),
            grader_control_host_dir=str(grader_control_host_dir),
            agent_image=config.agent_image,
            grader_image=config.grader_image,
            eval_timeout=config.eval_timeout,
        )

    # ── prepare_task ────────────────────────────────────────────────────────

    async def prepare_task(self, task: TaskSpec, env: EnvironmentSession,
                           req: RunRequest, plan: HarnessBenchBenchmarkPlan) -> PreparedTask:
        _ = req
        task_dir = Path(plan.task_dir)
        seed = task_dir / task.metadata["workspace_dir"]
        workspace_host = Path(plan.workspace_host_dir)

        # 清空 + 复制 seed（host 端直接写挂载源，agent 容器 /workspace 立即可见）
        if workspace_host.exists():
            shutil.rmtree(workspace_host)
        workspace_host.mkdir(parents=True, exist_ok=True)
        if seed.is_dir():
            shutil.copytree(seed, workspace_host, dirs_exist_ok=True)

        prompt = self._render_prompt(task, plan)
        return PreparedTask(
            task_id=task.task_id,
            category=task.category,
            ground_truth=task.ground_truth,
            input=TaskInput(prompt=prompt, workspace=plan.workspace_dir),
            output=TaskOutput(answer="工作区产物（required_artifacts）"),
            metadata=dict(task.metadata),
        )

    # ── collect_artifacts ───────────────────────────────────────────────────

    async def collect_artifacts(self, task, prepared, result, env, req, plan) -> RunResult:
        """MVP：/workspace 通过 host mount 已同步，无需 download。

        第二阶段在此生成 mutation report（before/after sha256 + 变更清单）。
        """
        _ = task, prepared, env, req, plan
        return result

    # ── evaluate ────────────────────────────────────────────────────────────

    async def evaluate(
        self,
        task: TaskSpec,
        prepared: PreparedTask,
        result: RunResult,
        req: RunRequest,
        plan: ExecutionPlan,
        env: EnvironmentSession | None = None,
    ) -> RunResult:
        _ = req
        benchmark_plan = self._require_plan(plan.benchmark_plan)

        if env is None:
            return self._error_result(
                prepared, result, "harness_bench 评测需要独立的 grader 环境（fresh 模式）"
            )

        task_dir = Path(benchmark_plan.task_dir)
        cases_file = str(task.metadata.get("cases_file") or "")
        outcome_test = str(task.metadata.get("outcome_test") or "")
        required_artifacts = list(task.metadata.get("required_artifacts") or [])

        # cases.yaml → JSON（grader 通过 HARNESSBENCH_CASES_JSON 读取）
        cases_obj: dict[str, Any] = {}
        if cases_file:
            cases_path = task_dir / cases_file
            if cases_path.is_file():
                cases_obj = yaml.safe_load(cases_path.read_text(encoding="utf-8")) or {}
        cases_json = json.dumps(cases_obj)
        required_json = json.dumps(required_artifacts)

        grader_env = {
            "HARNESSBENCH_TASK_ID": task.task_id,
            "HARNESSBENCH_CASES_JSON": cases_json,
            "HARNESSBENCH_REQUIRED_ARTIFACTS": required_json,
        }
        if outcome_test:
            grader_env["HARNESSBENCH_OUTCOME_TEST"] = outcome_test

        exec_result = await env.exec(
            ["python3", "/opt/harnessbench/grade_entrypoint.py"],
            env=grader_env,
            timeout=benchmark_plan.eval_timeout,
        )

        if exec_result.returncode != 0:
            return self._error_result(
                prepared,
                result,
                f"grader 失败 rc={exec_result.returncode}: {exec_result.stderr.strip()[-2000:]}",
                extra={"grader_stdout": exec_result.stdout, "grader_stderr": exec_result.stderr},
            )

        grader_result = self._parse_grader_json(exec_result.stdout)
        if grader_result is None:
            return self._error_result(
                prepared,
                result,
                f"grader 输出无法解析 JSON: {exec_result.stdout.strip()[-2000:]}",
            )

        outcome_score = float(grader_result.get("outcome_score", 0.0))
        task_success = grader_result.get("task_success")
        pass_threshold = float(task.metadata.get("pass_threshold") or 0.0)
        if task_success is None:
            correct = outcome_score >= pass_threshold if pass_threshold else outcome_score > 0
        else:
            correct = bool(task_success)

        status = TaskStatus.RUN_ERROR if result.error else TaskStatus.COMPLETED
        return RunResult(
            task_id=prepared.task_id,
            category=prepared.category,
            status=status,
            metrics={"correct": bool(correct and not result.error)},
            final_answer=result.final_answer,
            ground_truth=prepared.ground_truth,
            trajectory=result.trajectory,
            error=result.error or "",
            artifacts=dict(result.artifacts),
            telemetry=dict(result.telemetry),
            meta=result.meta,
            extra={
                "outcome_score": outcome_score,
                "task_success": task_success,
                "pass_threshold": pass_threshold,
                "grader_result": grader_result,
            },
        )

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _require_plan(plan: BenchmarkPlan) -> HarnessBenchBenchmarkPlan:
        if not isinstance(plan, HarnessBenchBenchmarkPlan):
            raise TypeError("harness_bench requires HarnessBenchBenchmarkPlan")
        return plan

    @staticmethod
    def _render_prompt(task: TaskSpec, plan: HarnessBenchBenchmarkPlan) -> str:
        required = list(task.metadata.get("required_artifacts") or [])
        lines = [str(task.question or "").strip()]
        if required:
            lines.append("\n要求产出的文件（required_artifacts）：")
            lines.extend(f"- {item}" for item in required)
        lines.append(f"\n在 {plan.workspace_dir} 目录下完成上述任务。")
        return "\n".join(lines)

    @staticmethod
    def _parse_grader_json(stdout: str) -> dict[str, Any] | None:
        text = (stdout or "").strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 兜底：取最后一个以 { 开头的行
            for line in reversed(text.splitlines()):
                stripped = line.strip()
                if stripped.startswith("{"):
                    try:
                        return json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
        return None

    @staticmethod
    def _error_result(prepared, result, error, extra=None) -> RunResult:
        return RunResult(
            task_id=prepared.task_id,
            category=prepared.category,
            status=TaskStatus.EVAL_ERROR,
            metrics={"correct": False},
            final_answer=result.final_answer,
            ground_truth=prepared.ground_truth,
            trajectory=result.trajectory,
            error=result.error or error,
            artifacts=dict(result.artifacts),
            telemetry=dict(result.telemetry),
            meta=result.meta,
            extra=extra or {},
        )


def _load_pass_threshold(task_dir: Path, spec: dict[str, Any]) -> float:
    """从 cases.yaml 读 pass_threshold（task.yaml 里不直接存）。"""
    cases_file = str(spec.get("cases_file") or "")
    if not cases_file:
        return 0.0
    cases_path = task_dir / cases_file
    if not cases_path.is_file():
        return 0.0
    try:
        cases_obj = yaml.safe_load(cases_path.read_text(encoding="utf-8")) or {}
        return float(cases_obj.get("pass_threshold") or 0.0)
    except Exception:
        return 0.0
