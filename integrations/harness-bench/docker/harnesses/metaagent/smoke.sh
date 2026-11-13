#!/usr/bin/env bash
# metaagent harness 冒烟测试（契约级：与 tools/harness_runtime.py 的容器运行形态一致）
#
# 用法:
#   bash docker/harnesses/metaagent/smoke.sh <API_KEY> [MODEL] [BASE_URL]
#
#   <API_KEY>  必填。模型端点的 key（ws- 临时端点的 key 会轮换，用最新的）
#   [MODEL]    可选。缺省自动从 /models 探测第一个
#   [BASE_URL] 可选。缺省 https://ws-kquz5fqdzozumawz.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
#
# 环境变量:
#   DRY=1      只做准备工作，不起容器（校验脚本本身用）
#   KEEP=1     结束后保留临时目录与 volume（排查用）
#
# 与正式跑的差异（两处，均为刻意为之）:
#   1. 不加 --dns 127.0.0.1 —— 那是正式跑时 harness-bench DNS 面板容器的玩法，
#      冒烟直连模型端点需要正常 DNS。
#   2. config.json 里带 api_key —— 正式跑走 model_budget_proxy 不校验 key。
set -euo pipefail

KEY="${1:?usage: smoke.sh <API_KEY> [MODEL] [BASE_URL]}"
MODEL="${2:-}"
BASE_URL="${3:-https://ws-kquz5fqdzozumawz.cn-beijing.maas.aliyuncs.com/compatible-mode/v1}"
IMAGE="harnessbench/metaagent:0.2.0"
NAME="hb-metaagent-smoke"
VOL="hb-smoke-state"
WORK="/tmp/hb-metaagent-smoke"

# ---- 0. 前置检查 ----
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "FAIL: 镜像 $IMAGE 不存在，先 build"; exit 1; }

# ---- 1. 探测模型名 ----
if [ -z "$MODEL" ]; then
  echo "[1/5] 探测模型名 ..."
  code=$(curl -s -o /tmp/sm_models.json -w '%{http_code}' -H "Authorization: Bearer $KEY" "$BASE_URL/models" || true)
  [ "$code" = "200" ] || { echo "FAIL: /models 返回 $code —— key 或端点无效"; exit 1; }
  MODEL=$(python3 -c "import json;print(json.load(open('/tmp/sm_models.json'))['data'][0]['id'])")
fi
echo "  base_url=$BASE_URL"
echo "  model=$MODEL"

# ---- 2. 准备 controller/workspace/trace ----
echo "[2/5] 准备目录 ..."
rm -rf "$WORK"; mkdir -p "$WORK"/{controller,workspace,trace}
chmod 777 "$WORK"/workspace "$WORK"/trace
cat > "$WORK/controller/prompt.txt" <<'EOF'
Create a file named hello.txt in the current directory containing exactly one line: hello from metaagent
EOF
python3 - "$WORK/controller/config.json" "$BASE_URL" "$MODEL" "$KEY" <<'PY'
import json, sys
path, base_url, model, key = sys.argv[1:5]
json.dump(
    {"base_url": base_url, "model": model, "max_tokens": 4096,
     "context_window": 131072, "max_turns": 30,
     "thinking": "high", "api_key": key},
    open(path, "w", encoding="utf-8"), indent=2,
)
PY

# ---- 3. state volume 预备（root chown，等价 run_benchmark.py:1957）----
echo "[3/5] 预备 state volume ..."
docker volume rm -f "$VOL" >/dev/null 2>&1 || true
docker volume create "$VOL" >/dev/null
docker run --rm --user 0 --entrypoint sh -v "$VOL":/state "$IMAGE" \
  -c 'chown -R 1000:1000 /state' >/dev/null

if [ "${DRY:-0}" = "1" ]; then echo "(DRY=1：跳过容器启动)"; exit 0; fi

# ---- 4. 起容器（契约级参数）----
echo "[4/5] 启动容器（题目：写 hello.txt）..."
set +e
docker run --rm --name "$NAME" \
  --network bridge \
  --add-host host.docker.internal:host-gateway \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --pids-limit 512 --memory 4g --cpus 2 \
  --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --mount type=bind,src="$WORK/workspace",dst=/workspace \
  --mount type=volume,src="$VOL",dst=/state \
  --mount type=bind,src="$WORK/controller",dst=/run/harness,readonly \
  --mount type=bind,src="$WORK/trace",dst=/trace \
  --env HARNESSBENCH_PROMPT=/run/harness/prompt.txt \
  --env HARNESSBENCH_CONFIG=/run/harness/config.json \
  --env HARNESSBENCH_WORKSPACE=/workspace \
  --env HARNESSBENCH_STATE=/state \
  --env HARNESSBENCH_TRACE=/trace \
  --env GIT_CONFIG_GLOBAL=/state/gitconfig \
  --env PYTHONDONTWRITEBYTECODE=1 \
  --env NO_PROXY=* --env no_proxy=* \
  --workdir /workspace \
  "$IMAGE" > "$WORK/stdout.log" 2> "$WORK/stderr.log"
STATUS=$?
set -e

# ---- 5. 报告 ----
echo "[5/5] 结果（exit=$STATUS）"
echo "===== workspace 顶层 ====="
ls -A "$WORK/workspace"
echo "===== hello.txt ====="
cat "$WORK/workspace/hello.txt" 2>/dev/null || echo "(不存在)"
echo "===== 最终 answer（stdout 最后一段 JSON）====="
python3 - "$WORK/stdout.log" <<'PY'
import json, sys
lines = open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()
answer = None
for ln in reversed(lines):
    ln = ln.strip()
    if ln.startswith("{"):
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if "result" in d or "error" in d:
            answer = d
            break
if answer:
    print(json.dumps(answer, ensure_ascii=False)[:600])
else:
    print("(未提取到 answer JSON，原始 stdout 见 stdout.log)")
PY
echo "===== 污染检查 ====="
extra=$(ls -A "$WORK/workspace" | grep -v '^hello.txt$' || true)
[ -z "$extra" ] && echo "  PASS: /workspace 只有 hello.txt，无 logs/memory 等污染" \
               || echo "  WARN: 意外产物: $extra"
echo "===== trace ====="
find "$WORK/trace" -type f | sed "s|$WORK/trace/||" | head -10

if [ "${KEEP:-0}" != "1" ]; then
  docker volume rm "$VOL" >/dev/null
  echo "(volume 已清理；临时目录保留在 $WORK 供查看，下次运行自动重建)"
fi
exit $STATUS
