#!/usr/bin/env bash
set -euo pipefail

: "${HARNESSBENCH_PROMPT:?}"
: "${HARNESSBENCH_CONFIG:?}"
: "${HARNESSBENCH_WORKSPACE:?}"
: "${HARNESSBENCH_STATE:?}"
: "${HARNESSBENCH_TRACE:?}"

read_config() {
  python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' \
    "${HARNESSBENCH_CONFIG}" "$1"
}

# 模型凭证走 env（key 不进 argv）。kernel 的 OpenAI-compatible 客户端消费这组变量。
export HOME="${HARNESSBENCH_STATE}/home"
export XDG_CACHE_HOME="${HARNESSBENCH_STATE}/cache"
export META_MODEL_PROVIDER="OpenAI"
export META_MODEL_BASE_URL="$(read_config base_url)"
# config 里可选 api_key（仅冒烟用）；正式跑 harness-bench 时走 budget proxy，
# 端点不校验 key，缺省占位符与 openjiuwen harness 一致。
export META_MODEL_API_KEY="$(read_config api_key 2>/dev/null || echo local-vllm-no-auth)"
export META_MODEL_NAME="$(read_config model)"

# 内核会话超时（openjiuwen/core/session/config/base.py 从 env 读取，默认 60s）。
# 评测任务需多轮工具调用，放宽到 benchmark 轮超时（1800s）以内、留 kill 余量；
# 流帧超时同步放宽，防止长 reasoning 静默期误杀。
# 052 实测（2026-11-05）：agent 做完 20 次模型调用/230 次工具调用共 580s 后，
# 内核在 622s 处报 [111134] stream output first stream chunk timeout(600s) —— 该计时器
# 是 workflow 级全局计时、不随成功请求重置，028(347s) 没撞线、052(622s) 撞线。
# 因此三个值都必须 >= 最长题的 timeout_sec（262-265/094/202 均为 7200），
# 真正的死任务由 run_benchmark 的题级 timeout 兜底。
export WORKFLOW_EXECUTE_TIMEOUT="${WORKFLOW_EXECUTE_TIMEOUT:-7200}"
export WORKFLOW_STREAM_FRAME_TIMEOUT="${WORKFLOW_STREAM_FRAME_TIMEOUT:-900}"
export WORKFLOW_STREAM_FIRST_FRAME_TIMEOUT="${WORKFLOW_STREAM_FIRST_FRAME_TIMEOUT:-7200}"

# rail state（Workspace schema / recovery SQLite / 日志）全部落 /state，
# 题目工作区只通过 deep_agent.cwd=/workspace 暴露（见 eval-package/meta_agent.yaml）。
export META_AGENT_WORKSPACE="${HARNESSBENCH_STATE}/metaagent-workspace"
export META_AGENT_TRACE="${HARNESSBENCH_TRACE}/metaagent"
mkdir -p "${HOME}" "${XDG_CACHE_HOME}" "${META_AGENT_WORKSPACE}" "${META_AGENT_TRACE}"

prompt="$(<"${HARNESSBENCH_PROMPT}")"
set +e
python3 /opt/harnessbench/metaagent_eval.py \
  "${prompt}" \
  > >(tee "${HARNESSBENCH_TRACE}/events.log") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e

chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
