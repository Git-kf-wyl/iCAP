"""harness-bench 的 Docker recipe：注入 agent 镜像 + grader 镜像 + 挂载。"""

from __future__ import annotations

from copy import deepcopy

from agentcompass.benchmarks.harness_bench import HarnessBenchBenchmarkPlan
from agentcompass.runtime import RECIPES, BaseRecipe, ExecutionPlan, RunRequest, TaskSpec


@RECIPES.register()
class HarnessBenchDockerRecipe(BaseRecipe):
    id = "harness_bench_docker"

    def matches(self, req: RunRequest, task: TaskSpec, plan: ExecutionPlan) -> bool:
        if req.benchmark.id != "harness_bench" or req.environment.id != "docker":
            return False
        return True

    def apply(self, plan: ExecutionPlan, req: RunRequest, task: TaskSpec) -> ExecutionPlan:
        _ = req, task
        updated_plan = deepcopy(plan)
        bp = updated_plan.benchmark_plan
        if not isinstance(bp, HarnessBenchBenchmarkPlan):
            raise TypeError("harness_bench_docker requires HarnessBenchBenchmarkPlan")

        # ── agent 容器：镜像 + workspace rw 挂载 ─────────────────────────────
        updated_plan.environment.params["image"] = bp.agent_image
        agent_mounts = list(updated_plan.environment.params.get("mounts") or [])
        agent_mounts.append({
            "source": bp.workspace_host_dir,
            "target": bp.workspace_dir,
            "mode": "rw",
        })
        updated_plan.environment.params["mounts"] = agent_mounts

        # ── grader 容器：镜像 + workspace/hidden ro 挂载 ─────────────────────
        eval_env = updated_plan.evaluation_environment
        if eval_env is None:
            eval_env = deepcopy(updated_plan.environment)
            updated_plan.evaluation_environment = eval_env
        eval_env.params["image"] = bp.grader_image
        eval_mounts = list(eval_env.params.get("mounts") or [])
        eval_mounts.append({
            "source": bp.workspace_host_dir,
            "target": bp.workspace_dir,
            "mode": "ro",
        })
        eval_mounts.append({
            "source": bp.task_dir,
            "target": "/hidden",
            "mode": "ro",
        })
        eval_env.params["mounts"] = eval_mounts

        return updated_plan
