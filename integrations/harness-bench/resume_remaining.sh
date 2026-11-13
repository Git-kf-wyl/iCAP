#!/usr/bin/env bash
# 续跑 HarnessBench 剩余 177 题(新端点,不 resume 旧 run)
# 用法: bash resume_remaining.sh
set -euo pipefail

cd /home/gt_14/harness-bench-main

OLD_SUMMARY="artifacts/evaluations/20261027-210532-qwen3.8-27b-openjiuwen-harnessbench/summary.json"
LITELLM="/mnt/d/app/pyProjects/agent-eval-agentCompass/litellm_config.yaml"

echo "[1/4] 从 litellm_config.yaml 提取 qwen3.8-27b 的新端点 + key(不打印 key)..."
.venv/bin/python - "$LITELLM" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
for m in d["model_list"]:
    if m["model_name"] == "qwen3.8-27b":
        base = m["litellm_params"]["api_base"]
        key  = m["litellm_params"]["api_key"]
        open("/tmp/hb_base_url.txt", "w").write(base)
        open("/tmp/upstream_key.txt", "w").write(key)
        print(f"  base_url = {base}")
        print(f"  key 长度 = {len(key)}")
        break
else:
    raise SystemExit("litellm_config.yaml 里没有 qwen3.8-27b")
PY

BASE_URL=$(cat /tmp/hb_base_url.txt)

echo "[2/4] 提取旧 run 里 queued+running 的剩余题..."
.venv/bin/python - "$OLD_SUMMARY" <<'PY'
import sys, json
j = json.load(open(sys.argv[1]))
ids = [t["task_id"] for t in j["tasks"] if t.get("status") in ("queued", "running")]
open("/tmp/remaining_tasks.txt", "w").write(",".join(ids))
print(f"  剩余 {len(ids)} 题")
PY

REMAINING=$(cat /tmp/remaining_tasks.txt)

echo "[3/4] 检查 docker..."
docker version --format '{{.Server.Version}}' >/dev/null 2>&1 || { echo "  docker 不可用,先起 docker"; exit 1; }
echo "  docker ok"

echo "[4/4] 后台启动续跑(新 run 目录,不 resume)..."
LOG=/home/gt_14/harness-bench-main/resume_remaining.log

nohup .venv/bin/python tools/run_benchmark.py \
  --base-url "$BASE_URL" \
  --model qwen3.8-27b \
  --harness openjiuwen \
  --workers 4 \
  --timeout 600 \
  --thinking high \
  --temperature 1.0 \
  --tasks "$REMAINING" \
  --upstream-api-key-file /tmp/upstream_key.txt \
  > "$LOG" 2>&1 &

echo ""
echo "已后台启动,PID=$!"
echo "日志: $LOG"
echo ""
echo "查看启动是否正常: tail -30 $LOG"
echo "实时看进度:        tail -f $LOG"
echo ""
echo "跑完后新结果在 artifacts/evaluations/<新时间戳> 目录,再和旧 97 题合并统计。"
