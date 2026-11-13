#!/usr/bin/env bash
# 原生断点续测:旧端点 ws-fonpfytrgypb84s5 + 旧 key,结果直接写回原 run 目录
set -euo pipefail
cd /home/gt_14/harness-bench-main

KEYFILE=/tmp/upstream_key.txt
RUN_ROOT=artifacts/evaluations/20261027-210532-qwen3.8-27b-openjiuwen-harnessbench

[ -s "$KEYFILE" ] || { echo "缺少 $KEYFILE(旧 key 文件)"; exit 1; }

echo "[1/2] 检查 docker..."
docker version --format '{{.Server.Version}}' >/dev/null 2>&1 || { echo "  docker 不可用,先起 docker"; exit 1; }
echo "  docker ok"

echo "[2/2] 后台启动 resume(旧端点 + --run-root,自动跳过已完成的 97 题)..."
nohup .venv/bin/python tools/run_benchmark.py \
  --base-url "https://ws-fonpfytrgypb84s5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1" \
  --model qwen3.8-27b \
  --harness openjiuwen \
  --workers 4 \
  --timeout 600 \
  --thinking high \
  --temperature 1.0 \
  --upstream-api-key-file "$KEYFILE" \
  --run-root "$RUN_ROOT" \
  > /home/gt_14/harness-bench-main/resume_native.log 2>&1 &

echo ""
echo "已后台启动,PID=$!"
echo "日志: /home/gt_14/harness-bench-main/resume_native.log"
echo "查看: tail -f /home/gt_14/harness-bench-main/resume_native.log"
echo ""
echo "预期:resume 校验通过后,跳过 97 completed,重置 4 running,只跑剩余 177 题,结果写回原目录。"
