"""openjiuwen-eval — 非交互 coding agent 一次性入口，绕过审批 rail。

复制 ``factory.create_agent`` 的逻辑，但【去掉】 ``AskUserRail`` 与
``ConfirmInterruptRail``，使 ``write_file`` / ``edit_file`` 在非交互下直接放行，
不再触发 ``ToolCallInterruptRequest``。供 harness-bench 的 harness entrypoint 调用。

用法:
    python3 openjiuwen_eval.py "<prompt>" [--workspace DIR] [--output-format json|stream-json]

模型凭证走环境变量（key 不进 argv）:
    OPENJIUWEN_API_BASE / OPENJIUWEN_API_KEY / OPENJIUWEN_MODEL / OPENJIUWEN_PROVIDER

输出（stdout 单份 JSON）:
    {"result": "...", "chunks": N, "model": "..."}
    stream-json 时额外带 "trajectory": [...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from uuid import uuid4

# 在 import openjiuwen 之前把 process cwd 切到 /state：openjiuwen 日志系统默认
# log_path="./logs/"（相对 cwd），若不 chdir 会解析到 /workspace/logs 污染题目工作区
# （被判 unexpected_created）。文件工具 cwd 由 cfg.cwd（=/workspace）显式控制，
# 不受 process cwd 影响。
_STATE_DIR = os.environ.get("HARNESSBENCH_STATE", "/state")
os.makedirs(_STATE_DIR, exist_ok=True)
os.chdir(_STATE_DIR)

import openjiuwen.harness.cli.agent.factory as F
from openjiuwen.core.foundation.llm import init_model
from openjiuwen.core.runner import Runner
from openjiuwen.harness import create_deep_agent
from openjiuwen.harness.cli.agent.config import load_config
from openjiuwen.harness.cli.prompts import build_system_prompt
from openjiuwen.harness.cli.rails import TokenTrackingRail
from openjiuwen.harness.cli.rails.tool_tracker import ToolTrackingRail
from openjiuwen.harness.cli.ui.renderer import CHUNK_ANSWER, CHUNK_LLM_OUTPUT, _extract_content
from openjiuwen.harness.rails import SkillUseRail
from openjiuwen.harness.rails.sys_operation_rail import SysOperationRail
from openjiuwen.harness.tools import create_web_tools

# 注意：不 import AskUserRail / ConfirmInterruptRail —— 这是本脚本的核心。


def create_agent_no_confirm(cfg):
    """复制 factory.create_agent，去掉 AskUserRail + ConfirmInterruptRail。

    与 factory.create_agent (openjiuwen 0.1.19) 保持同步；唯一差异是
    rails 列表里没有两个审批 rail。
    """
    model = init_model(
        provider=cfg.provider,
        model_name=cfg.model,
        api_key=cfg.api_key,
        api_base=cfg.api_base,
        max_tokens=cfg.max_tokens,
    )
    system_prompt = build_system_prompt(
        cwd=cfg.cwd,
        model=cfg.model,
        provider=cfg.provider,
    )

    # --- rails（无审批 rail）---
    rails = [TokenTrackingRail(), ToolTrackingRail(), SysOperationRail()]
    rails.append(
        SkillUseRail(
            skills_dir=F._default_skill_dirs(),
            skill_mode="all",
            include_tools=False,
        )
    )
    try:
        from openjiuwen.harness.rails.context_engineer import (  # noqa: PLC0415
            ContextAssembleRail,
            ContextProcessorRail,
        )
        rails.append(ContextProcessorRail(preset=True))
        rails.append(ContextAssembleRail())
    except ImportError:
        pass

    _memory_rail = F._build_memory_rail(cfg)
    if _memory_rail is not None:
        rails.append(_memory_rail)

    web_tools = create_web_tools(language="en")
    mcp_configs = F._load_mcp_configs()
    vision_config = F._load_vision_config(cfg)
    audio_config = F._load_audio_config(cfg)
    subagents = F._build_subagents(model)

    extra_kwargs: dict = {}
    if mcp_configs:
        extra_kwargs["mcps"] = mcp_configs
    if vision_config is not None:
        extra_kwargs["vision_model_config"] = vision_config
    if audio_config is not None:
        extra_kwargs["audio_model_config"] = audio_config

    workspace = F._build_cli_workspace(cfg, language="en")

    agent = create_deep_agent(
        model,
        system_prompt=system_prompt,
        tools=web_tools,
        subagents=subagents or None,
        rails=rails,
        enable_task_loop=True,
        enable_task_planning=True,
        enable_async_subagent=bool(subagents),
        max_iterations=cfg.max_iterations,
        workspace=workspace,
        restrict_to_work_dir=False,
        language="en",
        **extra_kwargs,
    )
    if agent.deep_config.workspace is not None:
        agent.deep_config.workspace.root_path = cfg.workspace
    return agent


def _chunk_payload(chunk) -> object:
    payload = getattr(chunk, "payload", None)
    if isinstance(payload, (str, dict, list, int, float, bool)) or payload is None:
        return payload
    return str(payload)


async def run(prompt: str, workspace: str | None, output_format: str) -> int:
    state_dir = os.environ.get("HARNESSBENCH_STATE", "/state")

    cfg = load_config(workspace=workspace)
    cfg.cwd = cfg.workspace  # 文件系统工具在 workspace 内操作
    # rail state（memory/todo/skills/context/messages/agents 等 Workspace schema）
    # 写到 /state，避免被 harness-bench 的 workspace_mutation_contract 判为越界。
    cfg.workspace = os.path.join(state_dir, "openjiuwen-workspace")

    agent = create_agent_no_confirm(cfg)
    await Runner.start()
    try:
        result_text = ""
        has_llm_output = False
        chunk_count = 0
        trajectory: list = []
        session_id = f"eval-{uuid4().hex[:8]}"

        async for chunk in Runner.run_agent_streaming(
            agent, {"query": prompt}, session=session_id
        ):
            chunk_count += 1
            chunk_type = getattr(chunk, "type", "")
            if output_format == "stream-json":
                trajectory.append(
                    {
                        "type": chunk_type,
                        "index": getattr(chunk, "index", None),
                        "payload": _chunk_payload(chunk),
                    }
                )
            if chunk_type == CHUNK_LLM_OUTPUT:
                has_llm_output = True
                result_text += _extract_content(chunk)
            elif chunk_type == CHUNK_ANSWER and not has_llm_output:
                result_text += _extract_content(chunk)

        out: dict = {"result": result_text, "chunks": chunk_count, "model": cfg.model}
        if output_format == "stream-json":
            out["trajectory"] = trajectory
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    finally:
        await Runner.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", default=None)
    parser.add_argument("--workspace", "-w", default=None)
    parser.add_argument(
        "--output-format",
        "-f",
        choices=["json", "stream-json"],
        default="json",
    )
    args = parser.parse_args()

    prompt = args.prompt
    if prompt == "-" or (prompt is None and not sys.stdin.isatty()):
        prompt = sys.stdin.read().strip()
    if not prompt:
        parser.error("A prompt argument is required, or pipe via stdin.")

    try:
        exit_code = asyncio.run(run(prompt, args.workspace, args.output_format))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
