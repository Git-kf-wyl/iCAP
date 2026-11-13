"""metaagent-eval — metaAgent 非交互单发入口。

加载镜像内打包好的 eval 专用配置包（/opt/harnessbench/eval-package），
对 prompt 执行一次 ``MetaBaseAgent.invoke``，stdout 输出单份 JSON：
    {"result": "...", "route": {...}, "usage": {...}}
``result_type != "answer"``（input_required / error）按失败退出非 0。

防 workspace 污染（见 docs/接入文档/openjiuwen-workspace污染修复.md）：
进程 cwd 必须在 import 之前切到 /state —— 内核日志默认 ``log_path="./logs/"``
相对 cwd 解析，且 import 时即初始化缓存；rail state（Workspace schema）由
配置包 workspace.root_path 指到 /state，文件工具 cwd 由配置包 cwd 字段指到
/workspace，两者分离。

用法:
    python3 metaagent_eval.py "<prompt>"
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import uuid4

# 在 import meta_agent（连带 import openjiuwen 内核、初始化日志）之前切 cwd。
_STATE_DIR = os.environ.get("HARNESSBENCH_STATE", "/state")
os.makedirs(_STATE_DIR, exist_ok=True)
os.chdir(_STATE_DIR)

from meta_agent.boot import MetaBootLoader  # noqa: E402

EVAL_PACKAGE = "/opt/harnessbench/eval-package"


async def run(prompt: str) -> int:
    loader = MetaBootLoader(EVAL_PACKAGE, env=dict(os.environ))
    # 单发评测：不挂 LocalRecovery（内核规定原生 shell/文件工具只能跑在
    # 「ordinary execution」；durable 恢复需要 effect bindings，评测用不上）。
    agent = await loader.boot()
    try:
        result = await agent.invoke(
            prompt,
            session_id=f"hb-{uuid4().hex[:12]}",
            request_id="start",
        )
    finally:
        await agent.aclose()

    if result.result_type != "answer":
        # 非交互契约：任何审批/提问/错误都视为 harness 失败，绝不挂起等 resume。
        detail = result.error or (result.interactions[:1] if result.interactions else None)
        print(
            json.dumps(
                {"error": f"result_type={result.result_type}", "detail": detail},
                ensure_ascii=False,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "result": result.output,
                "route": result.route,
                "usage": result.usage,
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> None:
    args = sys.argv[1:]
    prompt = args[0] if args and args[0] != "-" else None
    if prompt is None:
        prompt = sys.stdin.read().strip() if not sys.stdin.isatty() else None
    if not prompt:
        print(json.dumps({"error": "a prompt argument is required, or pipe via stdin"}))
        sys.exit(2)

    try:
        exit_code = asyncio.run(run(prompt))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        sys.exit(1)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
