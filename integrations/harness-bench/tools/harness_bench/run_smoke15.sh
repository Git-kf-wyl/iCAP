#!/usr/bin/env bash
# Execute five groups / fifteen tasks. --dry-run never connects to paid services.
set -euo pipefail
# Configuration comes exclusively from the invoking process environment.
# This script never reads or sources .env files.
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'HELP'
Usage: bash run_smoke15.sh [--dry-run] [all|remaining|regression|deck|core|office|media|services|frontend|preflight|diagnose]
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
remaining runs the ten non-core tasks; regression runs only task 005; deck runs only task 259.
No .env file or source command is required. Use preflight before running tasks.
Use diagnose for credential-free direct/proxy TLS comparisons.
HELP
  exit 0
fi
script_dir="${_HB_SMOKE15_SOURCE_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)}"
# Bash reads long-running scripts incrementally. Freeze this invocation so an
# editor updating the source during a task cannot change later shell commands.
if [[ "${_HB_SMOKE15_FROZEN:-0}" != 1 ]]; then
  snapshot_file="$(mktemp "${TMPDIR:-/tmp}/metaagent-smoke15-runner.XXXXXX")"
  trap 'rm -f -- "$snapshot_file"' EXIT
  cp -- "${BASH_SOURCE[0]}" "$snapshot_file"
  snapshot_status=0
  _HB_SMOKE15_FROZEN=1 _HB_SMOKE15_SOURCE_DIR="$script_dir" bash "$snapshot_file" "$@" || snapshot_status=$?
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
case "$selected" in all|remaining|regression|deck|core|office|media|services|frontend|preflight|diagnose) ;; *)
  echo 'Usage: run_smoke15.sh [--dry-run] [all|remaining|regression|deck|core|office|media|services|frontend|preflight|diagnose]' >&2; exit 2;; esac
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
export HB_SMOKE_RUN="${HB_SMOKE_RUN:-$bench_root/artifacts/evaluations/metaagent-smoke15-$(date +%Y%m%d-%H%M%S)-$$}"
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
      echo "Missing or placeholder config: $name; export it in this terminal (see bash run_smoke15.sh --help)" >&2; exit 2
    fi
  done
  for name in HB_LLM_API_KEY HB_JUDGE_API_KEY; do
    value="${!name:-}"
    if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
      echo "Invalid multiline key: $name" >&2; exit 2
    fi
  done
  if [[ -e "$HB_SMOKE_RUN" ]]; then
    echo 'HB_SMOKE_RUN already exists; choose a new directory to avoid cached trials.' >&2; exit 2
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
  secret_dir="$(mktemp -d "${TMPDIR:-/tmp}/metaagent-smoke15-keys.XXXXXX")"
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
  mkdir -p -- "$HB_SMOKE_RUN"
  cp -- "${BASH_SOURCE[0]}" "$HB_SMOKE_RUN/runner.snapshot.sh"
  export ARK_BASE_URL="$HB_LLM_BASE_URL" ARK_MODEL="$HB_LLM_MODEL" ARK_API_KEY_FILE="$llm_key_file"
  echo '[preflight] Checking model TLS/auth with the controller transport, then judge JSON mode'
  if ! "$python_bin" "$bench_root/tools/smoke_volcano.py" model --transport controller --proxy "$service_proxy" > "$HB_SMOKE_RUN/preflight-model.log" 2>&1; then
    head -n 1 -- "$HB_SMOKE_RUN/preflight-model.log" >&2
    tail -n 20 -- "$HB_SMOKE_RUN/preflight-model.log" >&2
    echo "Model preflight failed. No task was started. Logs: $HB_SMOKE_RUN" >&2
    exit 2
  fi
  if ! "$python_bin" "$bench_root/tools/smoke_volcano.py" judge --proxy "$service_proxy" > "$HB_SMOKE_RUN/preflight-judge.log" 2>&1; then
    tail -n 20 -- "$HB_SMOKE_RUN/preflight-judge.log" >&2
    echo "Judge preflight failed. No task was started. Logs: $HB_SMOKE_RUN" >&2
    exit 2
  fi
  echo 'Model and judge preflight passed'
  if [[ "$selected" == preflight ]]; then exit 0; fi
  docker info --format '{{.ServerVersion}}' 
fi

cd -- "$bench_root"
failed=0
run_group() {
  local name="$1" suite="$2" environment="$3" tasks="$4"
  if [[ "$selected" == remaining ]]; then
    if [[ "$name" == core ]]; then return; fi
  elif [[ "$selected" != all && "$selected" != "$name" ]]; then
    return
  fi
  local -a command=("$python_bin" tools/run_benchmark.py
    --harness metaagent --suite-root "$suite"
    --base-url "${HB_LLM_BASE_URL:-<LLM_BASE_URL>}" --model "${HB_LLM_MODEL:-<LLM_MODEL>}"
    --upstream-api-key-file "$llm_key_file"
    --tasks "$tasks" --workers "${HB_WORKERS:-1}"
    --max-agent-turns "${HB_MAX_AGENT_TURNS:-40}" --max-tokens "${HB_MAX_TOKENS:-8192}"
    --context-window "${HB_CONTEXT_WINDOW:-65536}" --timeout "${HB_TASK_TIMEOUT:-2400}"
    --temperature "${HB_TEMPERATURE:-0}" --thinking "${HB_THINKING:-high}"
    --run-root "$HB_SMOKE_RUN/$name")
  if [[ "$environment" == yes ]]; then command+=(--experimental-task-environments); fi
  printf '\n[%s]\n' "$name"
  if (( dry_run )); then
    printf '%q ' "${command[@]}"; printf '\n'
  else
    if "${command[@]}" > "$HB_SMOKE_RUN/$name.log" 2>&1; then
      local result_status=0
      "$python_bin" "$script_dir/check_smoke_results.py" "$HB_SMOKE_RUN/$name/summary.json" || result_status=$?
      if (( result_status != 0 )); then
        failed=1
        if (( result_status == 2 )) && [[ "${HB_CONTINUE_ON_ERROR:-0}" != 1 ]]; then
          echo "Infrastructure failure in $name; stopping remaining groups. Results: $HB_SMOKE_RUN" >&2
          exit 2
        fi
      fi
    else
      printf 'Command failed; see %s/%s.log\n' "$HB_SMOKE_RUN" "$name" >&2
      tail -n 20 -- "$HB_SMOKE_RUN/$name.log" >&2 || true
      failed=1
      if [[ "${HB_CONTINUE_ON_ERROR:-0}" != 1 ]]; then
        echo "Stopping after command failure; remaining groups were not started. Results: $HB_SMOKE_RUN" >&2
        exit 1
      fi
    fi
  fi
}
if [[ "$selected" == regression ]]; then
  run_group regression "$bench_root" yes '005-repository-regression-bisect-repair'
elif [[ "$selected" == deck ]]; then
  run_group deck "$bench_root" no '259-editable-management-review-deck'
else
run_group core "$bench_root" yes '001-meeting-summary,005-repository-regression-bisect-repair,011-calendar-scheduling-conflict,030-sql-query-report,110-ooxml-revision-adjudication-recovery'
run_group office "$bench_root" no '004-office-docs,259-editable-management-review-deck,261-sales-analysis-formula-workbook,267-eldercare-research-evidence-report'
run_group media "$bench_root" no '272-video-compression-fidelity-delivery,273-safe-skill-archive-packaging'
run_group services "$bench_root" yes '052-local-html-dom-form-extract,094-alert-routing-repair'
run_group frontend "$bench_root/suites/multimodal26" no '010-support-ticket-router,014-accessibility-retrofit'
fi
printf '\nResults root: %s\n' "$HB_SMOKE_RUN"
exit "$failed"
