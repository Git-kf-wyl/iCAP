# metaAgent × harness-bench：10 题环境验证清单（badcase 归因探针）

> 目的：正式全量 274 题之前，先用 10 道**环境要求最高 / 历史最易被误判**的题验证「运行环境干净」，
> 确保后续低分是 agent 真实能力问题，而不是断网、缺二进制、镜像拉取失败、端口冲突等外部因素。
>
> 选定日期：2026-11-05　适用 harness：`metaagent`（同样适用于 openjiuwen 复核）
> **最近更新：2026-11-05 11:40 —— 完成环境预验与镜像修复，`004` 因版本硬冲突被 `097` 替换**

---

## 一、选题原则

1. **环境依赖最重**：需要本地 HTTP 服务、需要跨镜像取二进制（node）、需要 ffmpeg、需要钉版本 Python 包。
2. **历史上出现过假 badcase**：`262-265` 曾在全量跑分中反复被判 `infrastructure_error`，根因是宿主机
   `PermissionError: .../case/environment/sandbox_contract.json`（root 属主残留）与 `docker pull` 失败，
   **不是 agent 犯错**。
3. **含对照组**：至少 2 道历史能通过的题（262、202），一旦它们失败，即可判定为环境/模型侧问题。
4. **覆盖不同故障域**：容器构建、端口/健康检查、二进制缺失、Python 包版本、VCS 工具链、SQLite 恢复。

---

## 二、十条用例清单

| # | task_id | 环境风险点 | 历史基线（openjiuwen） | 归因用途 |
|---|---|---|---|---|
| 1 | `262-user-service-registration-repair` | candidate 镜像（python 3.11 sandbox）+ 容器内 python 服务注册；宿主 artifact 属主 | infra_error ×4（PermissionError），修复后 **1.0 通过** | **对照组**：应通过 |
| 2 | `263-stateful-python-rpc-service` | candidate 镜像 = pinned `python@sha256:6c4dd3…` + 有状态 RPC 端点 | infra_error ×4 → r2 **0.0**（2 core fail） | 真/假失败判别 |
| 3 | `264-node-record-processing-contract` | 需 node **v22.22.3**（candidate 镜像从 pinned digest 跨镜像 COPY） | infra_error ×4 → r2 **0.0** | **二进制缺失**探针 |
| 4 | `265-weekly-operations-brief-generator` | 三产物 + pinned `python@sha256:efcdfa…` | infra_error（docker pull cloudfront 失败）→ **0.0** | **镜像可用性**探针 |
| 5 | `272-video-compression-fidelity-delivery` | tool_contract 要求 `/usr/bin/ffmpeg` + `/usr/bin/ffprobe`，harness 与 grader 双侧都要 | **0.0**（2 core fail） | **必然假 badcase** 验证 |
| 6 | `052-local-html-dom-form-extract` | 隔离网络内 appointment 服务 `:8080` + `/healthz`（20s）+ `.ics` 生成 | 0.75（1 core fail） | **服务健康**探针 |
| 7 | `094-alert-routing-repair` | 隔离网络内 alertmanager 模拟服务 `:8080` + `/healthz`（30s）+ **PyYAML 6.0.2 精确比对** + sha256 校验器 | 0.62（1 core fail） | **服务+校验器**探针 |
| 8 | `097-kubernetes-ca-trust-rotation-recovery` | 完全离线状态机 + `cactl.py` 受控命令 + append-only JSONL + 策略约束（替换 004，见 §3.2） | 未在此 harness 跑过（新补） | **多步状态恢复**探针 |
| 9 | `005-repository-regression-bisect-repair` | `git>=2.39,<3` + `pytest 8.3.5` + `prepare_workspace.py` 预置 | 0.6（1 core fail） | **工具链版本**探针 |
| 10 | `202-smart-meter-billing-correction-recovery` | SQLite 中断日志回放 + 7 个产物 + DST/多源冲突 + long_horizon | **0.92 通过** | **对照组**：应通过 |

### 覆盖矩阵

| 故障域 | 覆盖题 |
|---|---|
| 自建 per-task 镜像 / candidate sandbox 契约 | 262, 263, 264, 265 |
| 二进制缺失（node / ffmpeg） | 264, 272 |
| pinned digest 基础镜像可用性 | 263, 264, 265 |
| 本地服务 + 健康检查（隔离网络 sidecar） | 052, 094 |
| Python 包精确版本 | 094(PyYAML 6.0.2), 005(pytest 8.3.5) |
| 版本控制工具链 | 005 |
| 数据库恢复（SQLite journal） | 202 |
| 长时任务（timeout 7200） | 097, 202, 262-265 |

---

## 三、环境预验结论（实测，2026-11-05 11:20–11:40）

### 3.1 模型端点

| 项 | 结果 |
|---|---|
| `GET /models` | **200**，0.23s |
| `POST /chat/completions`（非流式） | **200**，1.05s，`content="pong"`（附 `reasoning_content`） |
| `POST /chat/completions`（`stream:true`） | **200**，ttfb **0.46s**，32 帧，`data: [DONE]` 正常收尾 |
| `tools` / `tool_choice:auto` | **200**，`finish_reason=tool_calls`，正确返回 `{"name":"bash_exec","arguments":"{\"cmd\":\"ls -la /workspace\"}"}` |
| 端点 | `https://ws-fonpfytrgypb84s5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| 模型 | `qwen3.8-27b` |

> 结论：端点/模型/流式/函数调用四项全通。`reasoning_content` 字段存在但不干扰 openjiuwen 内核解析（冒烟 4 次调用 0 错误）。

### 3.2 镜像缺口与修复（本次实际改动）

预验发现三类缺口，均已修复并重建镜像：

| 缺口 | 现象 | 影响题 | 修复 |
|---|---|---|---|
| **harness 镜像缺 ffmpeg/ffprobe** | `metaagent:0.1.0` 内两者 MISSING | 272 | `docker/harnesses/metaagent/Dockerfile` 末段 apt 增装 `ffmpeg` → 现 **ffmpeg 5.1.9 / ffprobe 5.1.9** |
| **grader 镜像缺 ffmpeg/ffprobe** | `grader:local` 内两者 MISSING，`tests/test_outcome.py:138` 显式 `shutil.which` 校验 → 直接抛 `runtime is not qualified` | 272 | `docker/grader/Dockerfile` 增 `apt-get install ffmpeg` |
| **harness 镜像缺 node** | agent 侧无法执行 `node`，264 只能盲改无法自测 | 264 | metaagent 镜像新增 `AS node-bin` stage，从 pinned `node@sha256:e21fc3…` COPY 二进制 + `libstdc++`/`libgcc_s` → 现 **node v22.22.3** |
| **PyYAML 版本不符** | 镜像内 6.0.3，094 的 verifier 精确要求 **6.0.2** → 环境准备阶段直接判 fail | 094 | metaagent 镜像钉 `PyYAML==6.0.2`（metaAgent 内核不依赖 6.0.3 新特性，冒烟已验证正常） |
| **004 版本硬冲突** | verifier 精确要求 `lxml 5.3.1` / `python-docx 1.1.2` / `typing_extensions 4.12.2`；但 metaAgent 内核声明 `python-docx>=1.2.0`，且 004 无 overlay Dockerfile → **无法两全** | 004 | **从选集剔除，替换为 097**（见 §3.4） |
| **grader 依赖 quay.io 的 amtool** | `FROM quay.io/prometheus/alertmanager` 在国内 12 分钟零进展，daocloud/1panel/rat.dev 三个镜像站均失败 → **grader 镜像完全无法构建** | 全部题（阻断性） | 全库 grep 确认 274 题 **0 处**引用 amtool，已从 grader Dockerfile 移除该 stage（见 §3.8） |

镜像 tag 随之递进：`harnessbench/metaagent:0.1.0 → 0.2.0`（`tools/harness_runtime.py` 与 `smoke.sh` 已同步）。

### 3.3 verifier 逐题实测

复刻 `tools/task_environment_runtime.py::_run_verifier` 的容器约束（`--network none --read-only --cap-drop ALL --user 1000:1000`）逐题执行：

| task | agent 侧 | grader 侧 | 备注 |
|---|---|---|---|
| 005 | **PASS** | **PASS** | git 2.39.5 / pytest 8.3.5 |
| 052 | **PASS** | SKIP（无 verifier） | cookie_jar / html.parser / urljoin |
| 094 | **PASS** | SKIP（无 verifier） | PyYAML 6.0.2 生效 |
| 097 | **PASS** | **PASS** | append-only JSONL / digest |
| 202 | **PASS** | **PASS** | sqlite 3.40.1 |
| 004 | **FAIL** | PASS | agent 侧版本冲突 → 已替换 |
| 262/263/264/265/272 | SKIP（无 verifier） | — | 由 hooks/candidate 契约保障 |

### 3.4 candidate 镜像可离线构建（262 / 264）

历史 `infrastructure_error` 的两个根因都已消除：

| 项 | 验证方式 | 结果 |
|---|---|---|
| 262 candidate | `docker build --network none` + pinned `python:3.11.9-slim@sha256:8fb099…` | **构建成功**（`hb-preflight-262-candidate:tmp`） |
| 264 candidate | `docker build --network none` + `NODE_IMAGE`/`PYTHON_IMAGE` 双 digest | **构建成功**，`node v22.22.3` + `Python 3.12.13` 共存 |
| 263 / 265 的 `pull` 型 candidate | pinned digest 在本地 image store 已存在 | ✅ 无需联网拉取 |

> 注意：262/264 的 `native.json` 里 `candidate_image` 是 `sha256:<image-id>`。本地手工 build 出的 ID 与之不同是**正常的** ——
> `hooks.py` 走 `try inspect → except 重建` 的自愈路径，并把实际 ID 写回 contract，不依赖硬编码 ID 相等。

### 3.5 契约级冒烟（metaagent:0.2.0）

用新镜像 + 新 key 重跑 `docker/harnesses/metaagent/smoke.sh`：

```
[5/5] 结果（exit=0）
hello.txt 内容 = "hello from metaagent"     ← 精确匹配
污染检查 PASS：/workspace 只有 hello.txt，无 logs/memory
trace：metaagent/…/trajectories_*.jsonl + meta-agent-*.jsonl 双落盘
usage：model_calls=4，model_errors=0，trace_errors=0
```

单元测试：`tests/test_harness_runtime.py` **38 passed, 34 subtests passed**。

### 3.6 服务 sidecar 端到端实测（052）

用 `--experimental-task-environments` 起了一次 052 真实 trial，观察链路：

```
hb-metaagent-052-r1-1c6848          harnessbench/metaagent:0.2.0   Up
hb-svc-052-appointment-1c684847     harnessbench/metaagent:0.2.0   Up
network: hb-net-052-local-html-dom-f-1c684847（隔离网络，agent 与 service 同网）
```

**踩到一个假警报**：直接请求 `http://appointment:8080/healthz` 返回 **404**，一度被误判为服务没起来。实际
`task.yaml` 的 `health_path` 是**逻辑路径**，真实 URL 要拼上 runtime 动态生成的 `--base-path`：

```bash
docker inspect hb-svc-052-appointment-... --format '{{json .Config.Cmd}}'
# --base-path /appointment/S70wJTw2DwgkO3BHemYfWLjV
```

带 base-path 请求即 **200 `{"ok":true}`**。因此手工探活必须读容器 Cmd 里的 `--base-path`，不能硬编码 `/healthz`
—— 否则会把正常环境误判成 (A) 类假 badcase。094 同理（其 base-path 由 harness 另行注入）。

### 3.7 内核「全局首帧超时」——052 的真凶（已修）

052 的第一次端到端跑返回：

```
status = infrastructure_error
error  = TaskEnvironmentError: service appointment health check failed:
         Error response from daemon: No such container: hb-svc-052-appointment-1c684847
```

`No such container` 只是**次生症状**（agent 异常退出后 hook 清理了 sidecar）。真凶在 agent 的 events.log 末尾：

```
{"error": "ExecutionError: [111134] stream output first stream chunk timeout, timeout=600.0s, error=''"}
Traceback ... [111123] post agent execute error ... error='agent store not found'   ← abort 路径的次生异常
```

对照 provider-trace 逐次事务：

| 项 | 数值 |
|---|---|
| 模型调用次数 | 20 次**全部** `upstream_response / complete=True` |
| 单次耗时 | 2.0s – 121.5s，累计约 580s |
| 工具调用 | 230 次 |
| 失败时刻 | 622s |

关键推论：580s 内 20 次请求全部正常返回，**第 21 次才撞上 600s 首帧超时** —— 说明
`WORKFLOW_STREAM_FIRST_FRAME_TIMEOUT` 是 **workflow 级全局计时器，不随成功请求重置**。
这也解释了为什么 028 单题（347s）能过、052（622s）必死。

原 entrypoint 的三个值（1700 / 600 / 600）对 timeout_sec=7200 的题（262-265、094、202）根本不够。
已改为：

```bash
export WORKFLOW_EXECUTE_TIMEOUT=7200          # 原 1700
export WORKFLOW_STREAM_FRAME_TIMEOUT=900      # 原 600
export WORKFLOW_STREAM_FIRST_FRAME_TIMEOUT=7200   # 原 600 ← 关键
```

> 副作用：真死锁的题会拖到题级 `timeout_sec` 才被杀，由 run_benchmark 兜底，属可接受代价。

#### 3.7.1 还有第二个 600s —— `DeepAgentConfig.completion_timeout`

改完首帧超时后重跑，**6 道题依然成批失败，且 elapsed 全部落在 613–673s**：

| 题 | 状态 | 分数 | elapsed |
|---|---|---|---|
| 005 | model_error | 0.8 | 615.9s |
| 265 | model_error | 0.0 | 625.9s |
| 272 | model_error | 0.4 | 614.0s |

events.log 里统一是 `{"error": "result_type=error", "detail": "completion_timeout"}`。查内核发现是**另一个独立的 600s**：

```python
# openjiuwen/harness/schema/config.py:275
completion_timeout: Optional[float] = 600.0        # DeepAgentConfig 整体完成超时
# openjiuwen/harness/deep_agent.py:2881
timeout = self._deep_config.completion_timeout if self._deep_config else 600.0
```

它与首帧超时**互不相干**，只覆盖整体完成。`extension_loader._LEGACY_AGENT_CONTROL_KEYS`
里含 `completion_timeout`，因此可由 eval-package 的 manifest 覆盖。已在
`eval-package/meta_agent.yaml` 的 `deep_agent:` 下加 `completion_timeout: 7200`。

> 两个 600s 叠加导致「凡是超过 10 分钟的题必失败」，这正是 262-265 / 094 / 202（timeout_sec=7200）
> 历史低分的系统性原因之一，与 agent 能力无关。

#### 3.7.2 native hooks 的 controller 镜像缺失（262/263/264）

这三题的 `infrastructure_error` 是第三种成因：

```
TimeoutExpired: Command '['/usr/bin/docker', 'create', ... ,
  'python:3.12-slim-bookworm@sha256:d50fb7611f86...', 'python3', '/entry.py', '--mode', 'model']
  ' timed out after 60 seconds
```

`hooks.py` 里 `docker()` 的 `timeout=60`，而 controller 镜像按 **digest** 引用
（`python:3.12-slim-bookworm@sha256:d50fb7…`），本地只有 tag 版本（另一 digest）→
`docker create` 隐式触发 registry 解析与拉取 → 国内网络下 60s 必然超时。

修复：`docker pull python@sha256:d50fb7611f86…` 预置该 digest，并 `docker run` 一次预热快照
（预热后 `docker create` 耗时 0.47s）。

> 注意：`d50fb7` 与 263/265 的 `6c4dd3`/`efcdfa`、262 的 `8fb099`、264 的 `e21fc3` 是**五个不同 digest**，
> 缺任何一个都会在 hooks 阶段炸成 infrastructure_error。重建环境后必须逐个核对。

### 3.8 Docker Desktop 自动升级导致镜像全丢（阻断性，已恢复）

预验中途 Docker Desktop 从 **29.6.2 升到 29.9.2**，并把存储驱动从 `overlay2` 换成
`overlayfs / io.containerd.snapshotter.v1`，结果 `docker images` 归零 —— metaagent、grader、
openjiuwen、全部 candidate 镜像一次性消失（`docker system df` 四项全 0B）。

恢复动作：

| 步骤 | 内容 |
|---|---|
| 1 | 写 `~/.docker/daemon.json` 加 `"registry-mirrors": ["https://docker.m.daocloud.io"]`（备份 `daemon.json.bak-preflight`），重启 Docker Desktop 生效 |
| 2 | 重建 `harnessbench/metaagent:0.2.0`（2.36GB，比 0.1.0 的 1.56GB 大了 ffmpeg + node） |
| 3 | 重建 `harnessbench/grader:local`（移除 quay.io/amtool 后才能构建） |
| 4 | 预拉 4 个 pinned digest：`python@6c4dd3`(263/264) / `python@efcdfa`(265) / `python@8fb099`(262) / `node@e21fc3`(264) |

重建后逐项复核：ffmpeg 5.1.9 / ffprobe / node v22.22.3 / PyYAML 6.0.2 / grader PyYAML 6.0.2 全部 OK；
264 candidate 仍能 `--network none` 离线构建；verifier 结果与 §3.3 完全一致；冒烟 3 次调用 0 错误。

**踩坑提醒**：
- 直连 `registry-1.docker.io` 报 `EOF`，必须走 daocloud mirror。
- daocloud **不支持** quay.io 代理（`invalid repository ... source: "docker.io"`），也不在白名单里的
  镜像（如 `prometheus/alertmanager`）会明确拒绝 —— 这类镜像只能另找源或干脆不用。
- `rebuild_images.sh` 里对 quay 的 pull 若不加 `timeout`，脚本会无限挂起（本次实际卡了 17 分钟）。

---

## 四、执行方案

### 4.1 环境预检（不消耗模型 token，已执行完毕）

`tools/run_benchmark.py` 没有 dry-run 开关，因此预检以两个独立动作完成：

```bash
# (a) 逐题跑 verifier（复刻 _run_verifier 约束）
bash /tmp/run_verifiers.sh

# (b) 逐题探二进制/镜像（不需要模型）
docker run --rm --entrypoint bash harnessbench/metaagent:0.2.0 -c \
  'for c in ffmpeg ffprobe node git sqlite3 pytest python3; do printf "%-8s " $c; command -v $c || echo MISSING; done'
docker run --rm --entrypoint bash harnessbench/grader:local -c \
  'for c in ffmpeg ffprobe amtool git python3; do printf "%-8s " $c; command -v $c || echo MISSING; done'
```

判定表：

| 检查 | 判定 | 当前结果 |
|---|---|---|
| `verify_environment.py` 退出码 | 非 0 → 环境不合格 | 5 通过 / 1 冲突（004，已替换） |
| `verify_grader_environment.py` 退出码 | 非 0 → 判分侧不合格 | 4 PASS / 2 SKIP |
| 契约二进制（264→`node -v`、272→`ffmpeg -version`） | 缺失 → 不可跑 | ✅ v22.22.3 / 5.1.9 |
| 服务健康（052/094）`healthz` | 非 200 → 不可跑 | 服务跑在**隔离网络 sidecar**，不占宿主 8080；052 实测 `{"ok":true}`（见 §3.6 的 base-path 说明） |
| 基础镜像 pinned digest 是否本地已有 | 缺失 → 先 pull | ✅ 三个 digest 全在本地 |

### 4.2 正式跑这 10 题

> **重要约束（2026-11-05 实测）**：`--experimental-task-environments` 是**全选集强约束** ——
> 只要选集里有一道题没有 `environment:` 块，preflight 就直接失败：
> `task environment preflight failed: experimental task environments require an explicit environment mapping`。
> 本次 10 题里只有 **052 / 094** 有 `environment:`，其余 8 道（262-265、272、097、005、202）没有
> → **必须分两批跑**。052/094 的服务 sidecar 只有在该参数下才会被拉起，不能省。

**批 1 —— 8 道无服务依赖题（不加 `--experimental-task-environments`）**

```bash
cd /home/gt_14/harness-bench-main
printf '%s' 'sk-…' > /tmp/upstream_key.txt && chmod 600 /tmp/upstream_key.txt

.venv/bin/python tools/run_benchmark.py \
  --harness metaagent \
  --model qwen3.8-27b \
  --base-url https://ws-fonpfytrgypb84s5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1 \
  --upstream-api-key-file /tmp/upstream_key.txt \
  --retry-infrastructure \
  --tasks 262-user-service-registration-repair,263-stateful-python-rpc-service,264-node-record-processing-contract,265-weekly-operations-brief-generator,272-video-compression-fidelity-delivery,097-kubernetes-ca-trust-rotation-recovery,005-repository-regression-bisect-repair,202-smart-meter-billing-correction-recovery \
  --workers 2 2>&1 | tee /tmp/probe10a.log
```

**批 2 —— 2 道服务型题（必须加 `--experimental-task-environments`）**

```bash
.venv/bin/python tools/run_benchmark.py \
  --harness metaagent \
  --model qwen3.8-27b \
  --base-url https://ws-fonpfytrgypb84s5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1 \
  --upstream-api-key-file /tmp/upstream_key.txt \
  --experimental-task-environments --retry-infrastructure \
  --tasks 052-local-html-dom-form-extract,094-alert-routing-repair \
  --workers 2 2>&1 | tee /tmp/probe10b.log
```

> 264/272 不再依赖 `--experimental-task-environments` 提供 ffmpeg/node —— 这两个二进制已在
> `metaagent:0.2.0` 与 `grader:local` 内，批 1 直接跑即可公平评测。

预计墙钟：批 1 **1.5–2h**（含 262/264 candidate 构建），批 2 **30–60min**。

### 4.3 复跑确认（仅 4 道 infra 历史题）

262/263/264/265 各再跑一次，两次结果一致性作为「环境稳定」的判据：

```bash
# 同上命令，--tasks 只保留这 4 题，输出到 /tmp/probe10_rerun.log
```

---

## 五、badcase 归因规则（本次验证的核心产出）

对每道题，按下列顺序判定，**只有落到 (D) 才算真实 agent 犯错**：

| 判定 | 特征 | 结论 |
|---|---|---|
| (A) 环境不合格 | `status=infrastructure_error` / `verify_environment` 失败 / 契约二进制缺失 / 服务不健康 / 镜像拉取失败 | **假 badcase（环境）**，该题作废重跑 |
| (B) 模型侧故障 | `status=model_error`，或 `provider-trace` 出现 `provider_downstream_disconnect_count>0` / 401 / 403 / 429 / `APIConnectionError` | **假 badcase（模型链路）**，不计入 agent 成绩 |
| (C) 产物缺失但无报错 | `completed` 且 `required_artifacts.missing` 非空，且 `provider-trace` 显示 0 次工具调用成功 | 先怀疑工具/权限（如 ffmpeg 缺失），复核后再定 |
| (D) 真实能力失败 | `completed` + 产物齐备/部分齐备 + 模型调用正常（≥3 次、0 断连）+ 失败点在 `failed_core_count`/`failed_gate_count` | **真 badcase**，可进 badcase 库 |

### 期望结果（用于校验规则本身）

| 题 | 期望 |
|---|---|
| 262 | 通过（1.0）——若失败，先查环境 |
| 202 | 通过（≈0.92）——若失败，先查环境 |
| 272 | ffmpeg 已双侧就位，应「可解」；若仍 0.0 且无 `ffmpeg: not found`，则为真 badcase |
| 264 | 同上（node v22.22.3 已在 agent 侧） |
| 052 / 094 | 服务起来后失败应落在 grader 断言（真 badcase），而非 connection refused |
| 097 / 005 / 263 / 265 | 允许真失败，但必须在 trace 里看到正常工具调用序列 |

---

## 六、待办

- [x] 获取新的可用模型 key（`sk-gq-…` 已实测 200）
- [x] 跑 4.1 环境预检，产出逐题 verifier 结论（见 §3.3）
- [x] 补 ffmpeg（harness + grader）、node（harness）、钉 PyYAML 6.0.2
- [x] 重建 `metaagent:0.2.0` 与 `grader:local`，重跑冒烟 + 单测
- [x] 004 冲突判定 → 替换为 097
- [x] 放宽内核 workflow 超时（052 暴露的 600s 全局首帧计时器）
- [x] Docker Desktop 升级致镜像全丢 → 配 daocloud mirror、移除 amtool、重建全部镜像
- [ ] 跑 4.2 正式 10 题，产出 `probe10_result.md`
- [ ] 对 262-265 跑 4.3 复跑，确认结果可复现
- [ ] 全量 274 题 shard 跑（约 10h）
