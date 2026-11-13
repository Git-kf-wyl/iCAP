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

model="$(read_config model)"
export HOME="${HARNESSBENCH_STATE}/home"
export XDG_CACHE_HOME="${HARNESSBENCH_STATE}/cache"
export OPENJIUWEN_API_BASE="$(read_config base_url)"
export OPENJIUWEN_API_KEY="local-vllm-no-auth"
export OPENJIUWEN_MODEL="${model}"
export OPENJIUWEN_PROVIDER="OpenAI"
mkdir -p "${HOME}" "${XDG_CACHE_HOME}" "${HARNESSBENCH_TRACE}"

prompt="$(<"${HARNESSBENCH_PROMPT}")"
set +e
python3 /opt/harnessbench/openjiuwen_eval.py \
  "${prompt}" \
  --workspace "${HARNESSBENCH_WORKSPACE}" \
  --output-format json \
  > >(tee "${HARNESSBENCH_TRACE}/events.log") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e

chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
