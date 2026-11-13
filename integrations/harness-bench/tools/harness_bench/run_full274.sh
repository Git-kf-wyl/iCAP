#!/usr/bin/env bash
# Execute the 274-task main suite in two environment-compatible batches. --dry-run never connects to paid services.
set -euo pipefail
# Configuration comes exclusively from the invoking process environment.
# This script never reads or sources .env files.
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'HELP'
Usage: bash run_full274.sh [--dry-run] [all|standard254|legacy20|preflight|diagnose]
Manually export these variables in the same terminal before running:
  HB_LLM_BASE_URL       LLM OpenAI-compatible base URL
  HB_LLM_MODEL          LLM model/endpoint ID
  HB_LLM_API_KEY        LLM API key
  HB_JUDGE_BASE_URL     judge base URL
  HB_JUDGE_MODEL        judge model/endpoint ID
  HB_JUDGE_API_KEY      optional; empty/unset reuses HB_LLM_API_KEY
Proxy settings:
  HB_PROXY_URL         build/download proxy; empty explicitly disables it
  HB_SERVICE_PROXY_URL LLM/judge proxy; empty explicitly selects DIRECT
If an HB proxy variable is unset, existing corresponding proxy exports are respected.
Model/judge hostnames are automatically added to NO_PROXY and no_proxy.
all runs 254 declared-environment tasks plus 20 legacy tasks; excludes multimodal26.
Full-run defaults: HB_FULL_WORKERS=1, HB_FULL_MAX_AGENT_TURNS=150, HB_FULL_MAX_TOKENS=32768.
Timeout defaults to each task definition; HB_FULL_TASK_TIMEOUT optionally overrides it.
No .env file or source command is required. Use preflight before running tasks.
Use diagnose for credential-free direct/proxy TLS comparisons.
HELP
  exit 0
fi
script_dir="${_HB_FULL274_SOURCE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
# Bash reads long-running scripts incrementally. Freeze this invocation so an
# editor updating the source during a task cannot change later shell commands.
if [[ "${_HB_FULL274_FROZEN:-0}" != 1 ]]; then
  snapshot_file="$(mktemp "${TMPDIR:-/tmp}/metaagent-full274-runner.XXXXXX")"
  trap 'rm -f -- "$snapshot_file"' EXIT
  cp -- "${BASH_SOURCE[0]}" "$snapshot_file"
  snapshot_status=0
  _HB_FULL274_FROZEN=1 _HB_FULL274_SOURCE_DIR="$script_dir" bash "$snapshot_file" "$@" || snapshot_status=$?
  exit "$snapshot_status"
fi
project_root="$(cd -- "$script_dir/../.." && pwd)"         # tools/harness_bench -> 仓库根
# metaAgent 内嵌于 harness-bench 时，项目根就是 bench 根
bench_root="$project_root"
[[ -f "$bench_root/tools/run_benchmark.py" ]] || bench_root="$project_root/harness-bench"
meta_root="$bench_root/metaAgent"
[[ -d "$meta_root" ]] || meta_root="$bench_root/docker/harnesses/metaagent/metaagent-src"
python_bin="${HB_PYTHON:-python}"
dry_run=0
if [[ "${1:-}" == --dry-run ]]; then dry_run=1; shift; fi
selected="${1:-all}"
case "$selected" in all|standard254|legacy20|preflight|diagnose) ;; *)
  echo 'Usage: run_full274.sh [--dry-run] [all|standard254|legacy20|preflight|diagnose]' >&2; exit 2;; esac
if (( $# > 1 )); then echo 'Too many arguments' >&2; exit 2; fi
# Diagnose routing without requiring keys, creating tasks or invoking models.
if [[ "$selected" == diagnose ]]; then
  if (( dry_run )); then
    echo 'Would compare direct/proxy TLS with Python and curl; no credentials or model requests.'
    exit 0
  fi
  "$python_bin" "$bench_root/tools/diagnose_model_tls.py" \
    --base-url "${HB_LLM_BASE_URL:-}" --proxy "${HB_PROXY_URL-http://127.0.0.1:7890}" \
    --output "$bench_root/metaAgent/.artifacts/model-tls-$(date +%Y%m%d-%H%M%S)-$$.json"
  exit $?
fi
export HB_FULL_RUN_ROOT="${HB_FULL_RUN_ROOT:-$bench_root/artifacts/evaluations/metaagent-full274-$(date +%Y%m%d-%H%M%S)-$$}"
llm_key_file='/path/to/llm.key'
judge_key_file='/path/to/judge.key'
secret_dir=''
cleanup() {
  if [[ -n "$secret_dir" ]]; then
    rm -f -- "$secret_dir/llm.key" "$secret_dir/judge.key"
    rmdir -- "$secret_dir"
  fi
}
trap cleanup EXIT

if (( ! dry_run )); then
  for name in HB_LLM_BASE_URL HB_LLM_MODEL HB_LLM_API_KEY HB_JUDGE_BASE_URL HB_JUDGE_MODEL; do
    value="${!name:-}"
    if [[ -z "$value" || "$value" == *'<'* || "$value" == *'>'* ]]; then
      echo "Missing or placeholder config: $name; export it in this terminal (see bash run_full274.sh --help)" >&2; exit 2
    fi
  done
  for name in HB_LLM_API_KEY HB_JUDGE_API_KEY; do
    value="${!name:-}"
    if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
      echo "Invalid multiline key: $name" >&2; exit 2
    fi
  done
  if [[ -e "$HB_FULL_RUN_ROOT" ]]; then
    echo 'HB_FULL_RUN_ROOT already exists; choose a new directory to avoid cached trials.' >&2; exit 2
  fi
  # Build downloads and model APIs may require different routes. In
  # particular a domestic model endpoint need not traverse a download proxy.
  build_proxy="${HB_PROXY_URL-${HARNESSBENCH_DOCKER_BUILD_PROXY-${HTTPS_PROXY-${https_proxy-${HTTP_PROXY-${http_proxy-}}}}}}"
  # Resolve the service route before changing HTTP_PROXY below. Build-only
  # HB_PROXY_URL does not silently become the model API route.
  service_proxy="${HB_SERVICE_PROXY_URL-${HARNESSBENCH_UPSTREAM_PROXY-${HTTPS_PROXY-${https_proxy-${HTTP_PROXY-${http_proxy-}}}}}}"
  if [[ -n "$build_proxy" ]]; then
    export HARNESSBENCH_DOCKER_BUILD_PROXY="$build_proxy"
    if [[ "$(uname -s)" == Linux ]]; then
      export HARNESSBENCH_DOCKER_BUILD_NETWORK="${HARNESSBENCH_DOCKER_BUILD_NETWORK:-host}"
    fi
  else
    unset HARNESSBENCH_DOCKER_BUILD_PROXY HARNESSBENCH_DOCKER_BUILD_NETWORK
  fi
  # NO_PROXY takes hostnames, not full URLs. Preserve the caller's entries
  # and apply the same model/judge bypass to preflight and actual trials.
  if [[ -f "$bench_root/tools/proxy_env.py" ]]; then
    NO_PROXY="$("$python_bin" "$bench_root/tools/proxy_env.py" "$HB_LLM_BASE_URL" "$HB_JUDGE_BASE_URL")"
  else
    echo "warning: tools/proxy_env.py 缺失，退化为只放行 localhost" >&2
    NO_PROXY="localhost,127.0.0.1,::1,host.docker.internal"
  fi
  export NO_PROXY
  export no_proxy="$NO_PROXY"
  if [[ -n "$service_proxy" ]]; then
    export HTTP_PROXY="$service_proxy" HTTPS_PROXY="$service_proxy"
    export http_proxy="$service_proxy" https_proxy="$service_proxy"
    export HARNESSBENCH_UPSTREAM_PROXY="$service_proxy"
  else
    unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy HARNESSBENCH_UPSTREAM_PROXY
  fi
  if [[ "${HB_JUDGE_API_KEY:-}" == *'<'* || "${HB_JUDGE_API_KEY:-}" == *'>'* ]]; then
    echo 'Replace the judge API key placeholder or leave it empty to reuse the LLM key.' >&2; exit 2
  fi
  # Keep real model credentials out of command arguments and generated configs.
  umask 077
  secret_dir="$(mktemp -d "${TMPDIR:-/tmp}/metaagent-full274-keys.XXXXXX")"
  llm_key_file="$secret_dir/llm.key"
  judge_key_file="$secret_dir/judge.key"
  printf '%s\n' "$HB_LLM_API_KEY" > "$llm_key_file"
  printf '%s\n' "${HB_JUDGE_API_KEY:-$HB_LLM_API_KEY}" > "$judge_key_file"
  unset HARNESSBENCH_JUDGE_API_KEY
  export HARNESSBENCH_JUDGE_BASE_URL="$HB_JUDGE_BASE_URL"
  export HARNESSBENCH_JUDGE_MODEL="$HB_JUDGE_MODEL"
  export HARNESSBENCH_JUDGE_API_KEY_FILE="$judge_key_file"
  export UV_CACHE_DIR="${UV_CACHE_DIR:-$bench_root/metaAgent/.artifacts/uv-cache}"
  unset HARNESSBENCH_WEB_SEARCH
  mkdir -p -- "$HB_FULL_RUN_ROOT"
  cp -- "${BASH_SOURCE[0]}" "$HB_FULL_RUN_ROOT/runner.snapshot.sh"
  export ARK_BASE_URL="$HB_LLM_BASE_URL" ARK_MODEL="$HB_LLM_MODEL" ARK_API_KEY_FILE="$llm_key_file"
  echo '[preflight] Checking model TLS/auth with the controller transport, then judge JSON mode'
  if ! "$python_bin" "$bench_root/tools/smoke_volcano.py" model --transport controller --proxy "$service_proxy" > "$HB_FULL_RUN_ROOT/preflight-model.log" 2>&1; then
    head -n 1 -- "$HB_FULL_RUN_ROOT/preflight-model.log" >&2
    tail -n 20 -- "$HB_FULL_RUN_ROOT/preflight-model.log" >&2
    echo "Model preflight failed. No task was started. Logs: $HB_FULL_RUN_ROOT" >&2
    exit 2
  fi
  if ! "$python_bin" "$bench_root/tools/smoke_volcano.py" judge --proxy "$service_proxy" > "$HB_FULL_RUN_ROOT/preflight-judge.log" 2>&1; then
    tail -n 20 -- "$HB_FULL_RUN_ROOT/preflight-judge.log" >&2
    echo "Judge preflight failed. No task was started. Logs: $HB_FULL_RUN_ROOT" >&2
    exit 2
  fi
  echo 'Model and judge preflight passed'
  if [[ "$selected" == preflight ]]; then exit 0; fi
  docker info --format '{{.ServerVersion}}' 
fi

cd -- "$bench_root"
# Validate both manifests rather than relying on numeric folder-name assumptions.
legacy_tasks="$("$python_bin" - "$bench_root/catalog" <<'PYDATA'
import sys
from pathlib import Path
import yaml
catalog = Path(sys.argv[1])
all_ids = yaml.safe_load((catalog / 'standard274.yaml').read_text())['task_ids']
declared_ids = yaml.safe_load((catalog / 'standard254.yaml').read_text())['task_ids']
legacy = [task for task in all_ids if task not in set(declared_ids)]
assert len(all_ids) == len(set(all_ids)) == 274
assert len(declared_ids) == len(set(declared_ids)) == 254
assert len(legacy) == 20 and set(declared_ids).issubset(all_ids)
print(','.join(legacy))
PYDATA
)"
failed=0
run_batch() {
  local name="$1" environment="$2" selection_kind="$3" selection_value="$4"
  if [[ "$selected" != all && "$selected" != "$name" ]]; then return; fi
  local -a command=("$python_bin" tools/run_benchmark.py
    --harness metaagent --suite-root "$bench_root"
    --base-url "${HB_LLM_BASE_URL:-<LLM_BASE_URL>}" --model "${HB_LLM_MODEL:-<LLM_MODEL>}"
    --upstream-api-key-file "$llm_key_file"
    "$selection_kind" "$selection_value"
    --workers "${HB_FULL_WORKERS:-1}"
    --max-agent-turns "${HB_FULL_MAX_AGENT_TURNS:-150}"
    --max-tokens "${HB_FULL_MAX_TOKENS:-32768}"
    --context-window "${HB_FULL_CONTEXT_WINDOW:-65536}"
    --temperature "${HB_FULL_TEMPERATURE:-0}"
    --thinking "${HB_FULL_THINKING:-${HB_THINKING:-high}}"
    --run-root "$HB_FULL_RUN_ROOT/$name")
  if [[ "$environment" == yes ]]; then command+=(--experimental-task-environments); fi
  # Default to each task's declared timeout, not the shorter smoke override.
  if [[ -n "${HB_FULL_TASK_TIMEOUT:-}" ]]; then command+=(--timeout "$HB_FULL_TASK_TIMEOUT"); fi
  printf '\n[%s]\n' "$name"
  if (( dry_run )); then
    printf '%q ' "${command[@]}"; printf '\n'
  elif "${command[@]}" 2>&1 | tee "$HB_FULL_RUN_ROOT/$name.log"; then
    local result_status=0
    "$python_bin" "$script_dir/check_smoke_results.py" "$HB_FULL_RUN_ROOT/$name/summary.json" || result_status=$?
    if (( result_status != 0 )); then
      failed=1
      if (( result_status == 2 )) && [[ "${HB_CONTINUE_ON_ERROR:-0}" != 1 ]]; then
        echo "Infrastructure failure; stopping. Results: $HB_FULL_RUN_ROOT" >&2
        exit 2
      fi
    fi
  else
    failed=1
    tail -n 20 -- "$HB_FULL_RUN_ROOT/$name.log" >&2 || true
    if [[ "${HB_CONTINUE_ON_ERROR:-0}" != 1 ]]; then
      echo "Batch command failed; stopping. Results: $HB_FULL_RUN_ROOT" >&2
      exit 1
    fi
  fi
}
run_batch standard254 yes --task-set standard254
run_batch legacy20 no --tasks "$legacy_tasks"
printf '\n274-task results root: %s\n' "$HB_FULL_RUN_ROOT"
exit "$failed"
