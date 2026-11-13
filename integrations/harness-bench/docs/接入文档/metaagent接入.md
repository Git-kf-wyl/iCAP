# metaAgent 接入 harness-bench 文档

> 接入时间：2026-11-04。状态：**已完成**（镜像构建成功、契约级冒烟全绿、单测 38/38 通过）。
> 姊妹篇：`openjiuwen接入.md`（第 8 个 harness）、`openjiuwen-filelock写文件锁bug定位.md`、`openjiuwen-workspace污染修复.md`。
> 工作副本：WSL `/home/gt_14/harness-bench-main`（本文档同步维护于两处）。

## 一、背景与目标

metaAgent（`Bingli-Liao/metaAgent`，私有仓）是 OpenJiuwen 之上的编排层：主/快双路径路由、Team DAG、子代理、checkpoint 恢复、Skill 进化。目标是把它作为 harness-bench 的第 9 个被测 harness，用 274 道通用任务 + grader 评估「metaAgent 作为 coding agent 的能力」。

与 openjiuwen 接入的一个根本差异：

| | openjiuwen harness | metaAgent |
|---|---|---|
| 被测内核 | PyPI wheel `openjiuwen[cli]==0.1.19` | gitcode `agent-core@4cd9df838`（pin 在 metaAgent 的 pyproject/uv.lock） |
| 驱动入口 | `openjiuwen run` CLI | **无 CLI**，`MetaBaseAgent.invoke(query, session_id, request_id)` 进程内单发 |
| 审批语义 | 运行时 rail（`AskUserRail`/`ConfirmInterruptRail`，代码里摘除） | 配置包声明（MCP 权限/团队审批/HITT/ask_user → `result_type: input_required`） |

因此**不能复用** `harnessbench/openjiuwen:0.1.19` 镜像，必须新建镜像并从源码安装。

## 二、接入 harness 的扩展点（3 处）

与 openjiuwen 完全同构，主流程零改动：

1. `docker/harnesses/metaagent/`：新增 harness 目录（Dockerfile / entrypoint.sh / eval 入口 / eval 配置包 / vendor 源码）。
2. `tools/harness_runtime.py`：`SPECS["metaagent"]` 登记 + `render_harness_config` 加 metaagent 分支。
3. `tests/test_harness_runtime.py`：verify_toolchain 豁免集合 `VERIFY_SKIPPED_HARNESSES` 加 `metaagent`（原因见 5.1）。

## 三、方案（选型记录）

评估过三个方案：

| 方案 | 原理 | 结论 |
|---|---|---|
| **A：进程内 invoke（采用）** | 入口脚本 boot 配置包 → `await agent.invoke(prompt)` → stdout 打 answer JSON | 非交互天然满足（单发缓冲）、工作量小、契约贴合度高 |
| B：openjiuwen SerializedTurnHarness provider | 走内核 harness 协议（TurnResult/Checkpoint/Resume） | 依赖 pin 内核的 provider SPI，entry-point 发现只在 gitcode pin 内核才有，未验证，不确定性大 |
| C：A2A/HTTP worker | 容器内起服务、外部驱动 | 契约最绕（要求"执行恰好一个 agent turn"），轨迹需自抓 |

方案 A 的审批问题用「eval 专用配置包」从源头消掉：包里不声明任何审批点，入口层对 `input_required`/`error` 一律 fail-fast 非零退出（双保险之二）。

## 四、关键设计

### 4.1 import 之前切 cwd（防日志污染，核心）

内核日志默认 `log_path: "./logs/"` **相对 cwd 解析，且 import 时即初始化并缓存**。入口脚本 import meta_agent 必然连带 import openjiuwen 内核 → 日志系统初始化。所以 `metaagent_eval.py` 的第一批代码（在 `from meta_agent.boot import ...` 之前）：

```python
_STATE_DIR = os.environ.get("HARNESSBENCH_STATE", "/state")
os.makedirs(_STATE_DIR, exist_ok=True)
os.chdir(_STATE_DIR)
```

这是 `openjiuwen-workspace污染修复.md` 3.2 节的同款做法——import 后再改配置不彻底，必须抢在 import 前。

### 4.2 cwd 与 workspace 声明式分离

openjiuwen 那次是运行时改 `cfg.cwd`/`cfg.workspace`；metaAgent 的 spec 原生支持分离，直接在 eval 配置包里声明：

```yaml
workspace:
  root_path: "${ENV:META_AGENT_WORKSPACE}"   # entrypoint 注入 $STATE/metaagent-workspace
cwd: "${ENV:HARNESSBENCH_WORKSPACE}"          # /workspace，文件工具落点，即题目工作区
```

rail state（memory/todo/skills 等 Workspace schema）与文件工具 cwd 彻底分开，state 永不进 `/workspace`。

### 4.3 boot() 不挂 recovery（实施中发现的新坑）

最初照 `examples/http_agent/run.py` 挂了 `LocalRecovery(SQLiteRecoveryStore(...))`，容器里直接被拒：

```
META_SYS_OPERATION_RECOVERY_UNSUPPORTED
```

源码依据：内核规定原生 shell/文件工具只能跑在 **ordinary execution**；durable 恢复模式需要显式 effect bindings。单发评测用不上 checkpoint 恢复，最终 `boot()` 无参（recovery=None）。

### 4.4 entrypoint 契约

`entrypoint.sh` 按 harness OCI contract：读 `HARNESSBENCH_CONFIG`（JSON）→ 注入模型 env（`META_MODEL_PROVIDER/BASE_URL/KEY/NAME`）→ 设 `META_AGENT_WORKSPACE`/`META_AGENT_TRACE` → 跑入口脚本，stdout/stderr tee 到 `/trace/events.log`、`/trace/stderr.log`。

两个细节：

- 模型 key：config 里**可选** `api_key` 字段（仅冒烟用，key 不落盘不进 argv）；正式跑 harness-bench 时走 budget proxy，端点不校验 key，缺省占位符 `local-vllm-no-auth`（与 openjiuwen 一致）。
- `HOME`/`XDG_CACHE_HOME` 重定向到 `$STATE`，防止非 root 用户往只读 rootfs 写缓存。

### 4.5 eval 入口（metaagent_eval.py）

```
chdir /state → MetaBootLoader(eval-package).boot() → agent.invoke(prompt) →
  result_type == "answer"      : print({"result","route","usage"})，exit 0
  result_type != "answer"      : print({"error", detail})，exit 1（绝不挂起等 resume）
```

### 4.6 SPECS 与 config 渲染

```python
# tools/harness_runtime.py
"metaagent": HarnessSpec(
    harness_id="metaagent",
    version="0.1.0",
    image="harnessbench/metaagent:0.1.0",
    protocol="chat_completions",
    config_name="config.json",
    docker_context=HARNESS_DOCKER_DIR / "metaagent",
    trace_complete=True,
),
```

`render_harness_config` 的 metaagent 分支渲染 `base_url/model/max_tokens/context_window/max_turns/thinking`（字段与 openjiuwen 分支相同；`thinking` 当前由 eval 包层面忽略）。

## 五、踩坑实录（按发生顺序）

### 5.1 filelock 写文件锁 bug —— 事前钉版本，未复发（但有条件）

历史坑（详见 `openjiuwen-filelock写文件锁bug定位.md`）逐条核对 pin 内核 4cd9df838：`_async_read_write_lock.py` 的 acquire（:135）与 release（:154）仍拆进两个 `asyncio.create_task`，与 filelock>=4.1.0 的 task 归属校验冲突 → 复发条件不变。

**关键差异**：metaAgent 的 `uv.lock` 把 filelock 锁在 **3.32.7**（3.x 系，无 `_owners` 校验，安全）。因此：

- Dockerfile 显式 `pip install "filelock==3.32.7"`（同时满足内核声明的 `>=3.25.0` 下限）→ **不会复发**
- 若图省事裸 `pip install .` 让 filelock 浮到 4.x → **必然复发**，症状一模一样：`write_file` 报 `Cannot close an active file lock` → 锁永久卡死 → 任务超时 0 分

**实测**：定位文档 3.2 节 minirepro 三行 `w1 write OK / w2 write OK / r1 read OK`，通过。

### 5.2 workspace 污染 —— 事前规避，实测零污染

两条污染路径在 pin 内核里都活着：日志 `./logs/` 相对 cwd（`default/constant.py:12` 仍默认 `log_path: "./logs/"`）、Workspace schema（memory/todo/skills）随 `workspace.root_path` 落盘。对策即 4.1 + 4.2。

**实测**：冒烟后 `/workspace` 顶层只有题目产物 `hello.txt`，无 `logs/`、`AGENT.md`、`memory/` 等，`workspace_mutation_contract` 语义干净。

### 5.3 LocalRecovery 拒绝原生 sys_operation（新坑）

见 4.3。教训：**不要照 examples 抄 boot 参数**——examples 场景是交互式/可恢复，评测是单发、无需恢复。`META_SYS_OPERATION_RECOVERY_UNSUPPORTED` 的判定在 `src/meta_agent/base_agent/runtime.py`。

### 5.4 state volume 属主（新坑）

state volume 默认属主 root，非 root（1000:1000）容器首写即 `Permission denied`。harness-bench 正式跑之前会由 run_benchmark.py（约 ：1957）起 root 容器 `chown -R 1000:1000` 该 volume——**手写冒烟脚本时容易漏这一步**，漏了会误判为 harness 自身故障。

### 5.5 内核日志混入 events.log

openjiuwen 同款现象：内核把启动/运行日志打到 stdout，与最终 answer JSON 混在 events.log 里。grader 的提取逻辑（读最后一个合法 JSON 行/对象）与 openjiuwen 路径一致，兼容；无需额外处理。

### 5.6 python-docx 版本冲突（沿用 openjiuwen 先例）

pin 内核依赖 `python-docx>=1.2.0`，会升级 task-toolchain 锁定的 1.1.2（功能向后兼容）。与 openjiuwen 一样跳过 `verify_toolchain.py` 版本检查，并在 `tests/test_harness_runtime.py` 加豁免：

```python
VERIFY_SKIPPED_HARNESSES = frozenset({"openjiuwen", "metaagent"})
```

顺带修掉了 openjiuwen 遗留的那个红测试（豁免集合化后 openjiuwen 也不再 FAIL）。

### 5.7 模型凭证（环境相关，非代码坑）

历史 `MODEL_API_KEY` 已失效；从 bash 历史里找回对 `ws-fonpfytrgypb84s5.cn-beijing.maas.aliyuncs.com` 有效的 workspace key 用于冒烟。**key 不写入任何文件**，仅经 env 注入。

### 5.8 `run_benchmark` 自动重建镜像时 pip 直连 pypi.org 失败

单题实测时框架会按 Dockerfile 自动重建镜像（此前手动 build 传过 `--build-arg PIP_INDEX_URL`，框架重建不带该参数）。Dockerfile 原来只写了 `ARG PIP_INDEX_URL` 而**没落成 `ENV`**——ARG 不进 pip 的环境变量，等于裸连 pypi.org，pypi.org 不可达时 aiohttp 等依赖解析直接失败。修法：`ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple` + `ENV PIP_INDEX_URL=${PIP_INDEX_URL}`，任何方式 build 都默认走 tuna。

### 5.9 内核 workflow 默认 60 秒超时（单题实测踩中）

冒烟题小（<60s）不会暴露；028-excel-like-cleaning 多轮工具调用在 60s 处被内核掐死：`[100101] workflow execution exceeded time limit of 60 seconds`。内核 `openjiuwen/core/session/config/base.py` 从 env 读 `WORKFLOW_EXECUTE_TIMEOUT`（默认 60s），另有流帧超时 `WORKFLOW_STREAM_FRAME_TIMEOUT`/`WORKFLOW_STREAM_FIRST_FRAME_TIMEOUT`。metaAgent 自己的 terminal_bench 接入（`harbor_agent.py`）也是同款 env 方案。修法：entrypoint 注入 `WORKFLOW_EXECUTE_TIMEOUT=1700`、两个 stream frame timeout=600（均允许 env 覆盖）。注意保持 < benchmark 轮超时 1800s 留 kill 余量。

### 5.10 ws 临时端点流式连接不稳（基础设施级）

一次 trial 中第 2 次请求 178 秒后被上游断开（BrokenPipeError，`provider_downstream_disconnect_count: 1`），框架判 model_error oracle=0。属 ws 临时端点网关的流式超时/抖动，非接入问题；用 `--retry-infrastructure` 让框架自动重试即可。

## 六、改动清单

### 新增

| 文件 | 内容 |
|---|---|
| `docker/harnesses/metaagent/Dockerfile` | 标准两段结构：python:3.12-slim + 17 包 task-toolchain → COPY vendor 源码 `pip install /opt/metaagent-src`（内核走 gitcode pin 依赖，不依赖 github.com）→ `filelock==3.32.7` 钉版本 → `USER 1000:1000`；不跑 verify_toolchain |
| `docker/harnesses/metaagent/entrypoint.sh` | 契约读取 + env 注入 + tee 落 trace + 退出码透传 |
| `docker/harnesses/metaagent/metaagent_eval.py` | eval 入口（4.5） |
| `docker/harnesses/metaagent/eval-package/meta_agent.yaml` | eval 专用配置包：单 DeepAgent、`enable_sys_operation: true`、无 MCP/plugins/团队/审批、`max_iterations: 150`、workspace/cwd 分离（4.2）、trace 指 `/trace` |
| `docker/harnesses/metaagent/eval-package/skills/workspace-basics/SKILL.md` | 最小 skill（spec 的 skills 字段必填） |
| `docker/harnesses/metaagent/metaagent-src/` | vendor 的 metaAgent 源码（tar 排除 .git/benchmarks/tests/docs/examples 等，build context 内自包含） |

### 修改

| 文件 | 改动 |
|---|---|
| `tools/harness_runtime.py` | `SPECS["metaagent"]`（:115）+ `render_harness_config` metaagent 分支（:422） |
| `tests/test_harness_runtime.py` | `VERIFY_SKIPPED_HARNESSES`（:138），38/38 全绿 |

## 七、验证（已通过）

1. **单测**：`python -m unittest tests.test_harness_runtime` → 38/38 通过。
2. **镜像构建**：`harnessbench/metaagent:0.1.0`（1.56GB），全量 build 约 11 分钟（tuna pip 源 + gitcode git 依赖国内可达）。
3. **契约级冒烟**：完整复刻 harness-bench 运行形态（只读 rootfs、bind `/workspace`、volume `/state`、`/trace`、非 root、tmpfs 隔离、root 预 chown）。结果：exit 0，`hello.txt` 内容精确匹配，answer JSON 正常（3 次模型调用）。
4. **workspace 零污染**：见 5.2。
5. **filelock minirepro**：见 5.1。
6. **trace**：`/trace/metaagent/*.jsonl` + `trajectories/` 正常落盘。
7. **单题实测**（2026-11-05，`028-excel-like-cleaning`，qwen3.8-27b 直连 ws 端点）：`completed oracle=1.0`，耗时 347s，8 次模型调用 0 错误 0 断连。踩坑 5.8/5.9/5.10 已在过程中修复。

## 八、build + 冒烟（复现命令）

```bash
# build（WSL，harness-bench 根目录；Dockerfile 已带 tuna 默认索引，--build-arg 可省）
docker build -t harnessbench/metaagent:0.1.0 -f docker/harnesses/metaagent/Dockerfile .

# 正式评测（走 run_benchmark，state volume 由框架预备 chown；基础设施抖动加 --retry-infrastructure）
python3 tools/run_benchmark.py --harness metaagent --model <model> --base-url <endpoint> \
  --upstream-api-key-file <key_file> --tasks <task_id> --workers 1 --retry-infrastructure
```

冒烟要点（自建脚本时）：① root 容器 `chown -R 1000:1000` state volume；② `--read-only` rootfs + 题目产物 bind 只挂 `/workspace`；③ config JSON 传 `base_url/model`，可选 `api_key`。

## 九、关键源码依据

| 结论 | 位置 |
|---|---|
| pin 内核 commit | metaAgent pyproject/uv.lock → `agent-core@4cd9df838`（gitcode） |
| 锁拆 task 未改 | 内核 `core/sys_operation/local/_async_read_write_lock.py:135,154` |
| 日志相对 cwd | 内核 `core/common/logging/default/constant.py:12`（`log_path: "./logs/"`） |
| 恢复模式限制 | metaAgent `src/meta_agent/base_agent/runtime.py`（`META_SYS_OPERATION_RECOVERY_UNSUPPORTED`） |
| env 插值 | metaAgent `src/meta_agent/boot/boot_loader.py`（`${ENV:VAR}` → 模型/workspace/cwd/trace 全部可声明） |
| 返回语义 | `result_type: answer / input_required / error`，单发缓冲；`stream()` 有 delta/final 事件 |

## 十、待办

- [x] `run_benchmark.py --harness metaagent` 单题实测（028-excel-like-cleaning，oracle=1.0，2026-11-05）
- [ ] shard 全量 274 题（参考 openjiuwen 节奏约 10h；建议全程 `--retry-infrastructure` 应对 ws 端点流式抖动）
- [ ] vendor 源码随 metaAgent 上游更新需手动刷新（当前 tar 自 `git e9e2cef`）
- [ ] 若 grader 对 `route`/`usage` 字段有额外校验需求，再扩展 answer JSON 结构
