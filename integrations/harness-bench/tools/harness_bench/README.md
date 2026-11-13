# Harness-Bench 接入与火山冒烟

当前目录布局：`metaAgent/` 内嵌于 `harness-bench/`（harness-bench 为工程根；旧版同级布局仍受支持）。新增 `--harness metaagent`：控制器准备任务、代理模型和评分；容器通过 `MetaBootLoader.boot()` → `agent.invoke()` → `agent.aclose()` 执行真实 MetaAgent，启用原生文件/shell 工具、强制 skill 包和内存 checkpoint，不启用耐久恢复。每轮保留原生 trace、最终答案和 session summary，失败以非零退出码报告。当前执行策略是单个有界 ReAct 回合，不启用 task loop。

镜像复用原生 OpenJiuwen 的任务工具层，但 MetaAgent 自身用 `uv sync --locked --no-dev` 安装其锁定内核，不能把原生 baseline 的 0.1.19 当作 MetaAgent 的内核版本。控制器自动先构建父镜像，再打包同级 MetaAgent 的 src、pyproject、lock 和 README；源代码及父镜像源码摘要参与缓存失效。构建需要 Docker、公网/镜像源以及 GitCode 可达。修改源码后重新运行会自动重建。

## 1. 无密钥接入检查

以下均从共同工作目录运行：

```bash
cd /root/db4/metaAgent-harness-bench/harness-bench
python metaAgent/benchmarks/harness_bench/verify.py
# 单独重跑真实工具执行；只替换模型 HTTP 回复，不替换工具执行器。
metaAgent/.venv/bin/python metaAgent/benchmarks/harness_bench/check_adapter.py --case tools
```

四个离线用例分别覆盖回答、原生文件写入/读取/shell、火山搜索工具接线、模型鉴权失败的退出/清理。搜索用例只替换远端 HTTP 回复，真正执行 VolcanoSearch 的请求构造和解析。每次验证保存独立 workspace、trace、日志及 results.json。

已修复此前的锁等待：根因是当前沙箱禁止 asyncio socketpair 写入，线程完成事件无法唤醒事件循环；不是 filelock 版本问题。入口检测该限制，仅在需要时加入 50ms 事件轮询，覆盖执行与 executor 退出阶段，不降级依赖或替换文件锁。四个真实 MetaAgent 生命周期用例均已通过。还修复了单独运行 pytest 时的 src 导入路径，并重新生成了过期的目录统计。

`verify.py` 会尝试全部 harness-bench 控制面测试，且不会把受权限限制的失败当作通过。当前沙箱不允许本地监听端口，网络测试因此失败；详见 [验证记录](VALIDATION.md)。

## 2. 火山参数模板

模型与裁决均使用火山方舟 OpenAI-compatible Chat Completions 地址。填写你账户已开通的模型 ID 或推理接入点 ID；执行模型需支持工具调用，裁决模型需支持 `response_format: json_object`。二者可相同，但独立配置。模型 token 限制按实际部署调整，裁决配置还受任务 rubric 约束。

```bash
cd /root/db4/metaAgent-harness-bench/harness-bench
# Python/urllib/aiohttp 和构建阶段分别配置；代理不进入受测任务的网络。
export HTTP_PROXY='http://127.0.0.1:7890'
export HTTPS_PROXY="$HTTP_PROXY"
export http_proxy="$HTTP_PROXY" https_proxy="$HTTP_PROXY"
export NO_PROXY='localhost,127.0.0.1,::1'
export no_proxy="$NO_PROXY"
export HARNESSBENCH_UPSTREAM_PROXY="$HTTP_PROXY"
export HARNESSBENCH_DOCKER_BUILD_PROXY="$HTTP_PROXY"
# Linux 本机代理只监听 127.0.0.1 时，构建阶段需使用 host 网络。
export HARNESSBENCH_DOCKER_BUILD_NETWORK=host
export UV_CACHE_DIR="$PWD/metaAgent/.artifacts/uv-cache"
export ARK_BASE_URL='https://ark.cn-beijing.volces.com/api/v3'
export ARK_MODEL='<执行模型ID或ep-ID>'
export ARK_API_KEY_FILE="$HOME/.config/harness-bench/ark.key"
export HARNESSBENCH_JUDGE_BASE_URL="$ARK_BASE_URL"
export HARNESSBENCH_JUDGE_MODEL='<裁决模型ID或ep-ID>'
export HARNESSBENCH_JUDGE_API_KEY_FILE="$ARK_API_KEY_FILE"
export HARNESSBENCH_JUDGE_TIMEOUT_SEC=300
# 用你自己的编辑器把 API key 写入上述文件，仅一行；不要写入仓库。
mkdir -p "$(dirname "$ARK_API_KEY_FILE")"
# 文件创建后：chmod 600 "$ARK_API_KEY_FILE"

# 火山搜索 Custom 服务单独开通、单独凭证，通常不等同于方舟 key。
read -rsp 'Volcano Search API Key: ' VOLC_SEARCH_API_KEY; echo
export VOLC_SEARCH_API_KEY
export VOLC_SEARCH_QPS=5
```

方舟地址依据 [官方 OpenAI SDK 兼容文档](https://docs.volcengine.com/docs/ark/compatible-with-openai-sdk?lang=en)。搜索复用 benchmark 已有 VolcanoSearch（默认 `https://open.feedcoopapi.com/search_api/web_search`）；没有启用其他搜索引擎或自动回退。

## 3. 从宿主机分别检查三个服务

```bash
metaAgent/.venv/bin/python tools/smoke_volcano.py model --proxy http://127.0.0.1:7890
metaAgent/.venv/bin/python tools/smoke_volcano.py judge --proxy http://127.0.0.1:7890
metaAgent/.venv/bin/python tools/smoke_volcano.py search --proxy http://127.0.0.1:7890
```

预期各自输出 PASS。model 检查鉴权/文本响应；judge 额外检查 JSON 模式；search 要求真实非空结果。模型工具调用由下一步的真实任务检查。不要把文本服务连通视为完整任务验收。

## 4. 容器端到端用例

```bash
cd /root/db4/metaAgent-harness-bench/harness-bench
# 冻结任务要求离线，容器默认禁止公网，不开启搜索。
unset HARNESSBENCH_WEB_SEARCH
export HB_SMOKE_RUN="artifacts/evaluations/metaagent-volcano-$(date +%Y%m%d-%H%M%S)"
python tools/run_benchmark.py \
  --harness metaagent \
  --base-url "$ARK_BASE_URL" --model "$ARK_MODEL" \
  --upstream-api-key-file "$ARK_API_KEY_FILE" \
  --tasks 009-safe-archive-extraction,001-meeting-summary \
  --workers 1 --max-agent-turns 30 --max-tokens 8192 \
  --context-window 32768 --temperature 0 --thinking off \
  --timeout 1200 --run-root "$HB_SMOKE_RUN"
```

`009-safe-archive-extraction` 检查代码修复、文件/shell 工具与确定性评分；`001-meeting-summary` 检查文件交付和语义裁决。首次构建较慢；可先只跑 `--tasks 009-safe-archive-extraction`。更改模型或配置后使用新 run-root，避免复用旧结果。

```bash
cat "$HB_SMOKE_RUN/summary.json"
find "$HB_SMOKE_RUN" -name result.json -o -name session-summary.json -o -name final-answer.txt
```

接入成功证据：配置/结果 harness 为 metaagent；round trace 的 `session-summary.json` 为 `status=completed` 且 `result_type=answer`；存在 MetaAgent 原生 trace 和模型代理事务；任务 result 有 oracle 评分，001 的 semantic_judge 指向所设火山模型且无调用/解析错误。任务分数失败需要结合 oracle 诊断：模型答错与基础设施失败分别排查，不能仅凭命令返回码宣布通过。

搜索由第 3 步宿主机真实检查。`HARNESSBENCH_WEB_SEARCH=volc` 会注册火山搜索工具，但基准的隔离网络不允许它访问公网；不要通过放开冻结任务网络来做搜索验收。搜索 key 只在显式开启该工具时进入每轮控制配置，应保护 run-root 权限。

## 一条命令重跑

填好上述参数后，从共同工作目录执行：

```bash
python metaAgent/benchmarks/harness_bench/verify.py --live --proxy http://127.0.0.1:7890
```

依次检查代理/Docker、四个离线接入用例、全部控制面测试、真实执行模型/裁决/搜索；服务和 Docker 可用后才运行两个端到端任务。结果写入 `metaAgent/.artifacts/harness-bench-<时间>/results.json`，每条命令保留日志。退出码 0 表示全部通过，1 表示有失败，2 表示仍有权限或配置阻塞。`--live` 会产生真实模型与搜索费用。

当前仍受沙箱策略约束：代理 TCP、Docker socket、本地服务监听均返回 EPERM；缺少真实火山模型 ID 和凭证。普通代理配置不能解除这些系统权限限制。详情和已执行结果见 [验证记录](VALIDATION.md)。
