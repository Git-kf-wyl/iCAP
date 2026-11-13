# openJiuwen 接入 harness-bench 文档

> 记录把 openJiuwen（openjiuwen，`github.com/openJiuwen-ai/agent-core`，PyPI `openjiuwen==0.1.19`）作为第 8 个被测 harness 接入 harness-bench 的完整过程。
> 本文假设读者已了解 harness-bench 的「harness 是镜像、任务是数据、评分在 grader 容器」的架构（见 `docker/README.md`）。

---

## 一、背景与目标

harness-bench 内置 7 个被测 harness：OpenClaw / Claude Code / Codex / Goose / Hermes / Nanobot / OpenCode，分别对应 `docker/harnesses/<id>/` 下的一个 OCI 镜像。

openJiuwen 是一个开源 coding agent 内核（Python SDK），自带 bash/file 工具（`SysOperationRail`），CLI 提供非交互入口 `openjiuwen run PROMPT`。本接入让它能跑 harness-bench 的 274 道通用任务，复用 harness-bench 的 task 数据 + grader 评分链路。

---

## 二、接入 harness 的扩展点（3 处）

harness-bench 对「新增一个被测 harness」有清晰的扩展点，**改 3 处即可，不动主流程**：

| 扩展点 | 位置 | 作用 |
|---|---|---|
| 注册表 `SPECS` 字典 | `tools/harness_runtime.py:53-106` | 登记一个 `HarnessSpec`（image/协议/config 名/docker context） |
| config 渲染器 | `tools/harness_runtime.py` 的 `render_harness_config`（:182 起） | 为每个 harness 生成模型配置，末尾 `raise ValueError`（:390 前） |
| harness 镜像目录 | `docker/harnesses/<id>/` | Dockerfile + entrypoint.sh（+ 可选入口脚本） |

关键：CLI 的 `--harness` 参数 choices 是**动态生成**的：

```python
# tools/run_benchmark.py:3403-3407
parser.add_argument(
    "--harness",
    choices=("openclaw", *sorted(OCI_HARNESS_SPECS)),  # 从 SPECS 动态读
    ...
)
```

所以只要在 `SPECS` 登记一条，`--harness openjiuwen` 就自动可用，**无需改 `run_benchmark.py`、catalog、grader、task 数据**。

---

## 三、方案（3 个新增文件 + 2 处修改）

### 新增文件

```
docker/harnesses/openjiuwen/
├── Dockerfile           # python:3.12 + 17 包 task-toolchain + pip install openjiuwen + COPY 入口
├── entrypoint.sh        # 读 config → 设 OPENJIUWEN_* env → 跑 openjiuwen_eval.py → exit code
└── openjiuwen_eval.py   # 去审批 rail 的入口脚本
```

### 修改

```
tools/harness_runtime.py
├── SPECS 加 1 条 openjiuwen HarnessSpec
└── render_harness_config 加 1 个 openjiuwen 分支
```

---

## 四、关键设计

### 4.1 入口脚本：绕 write_file 审批（核心）

openjiuwen 本身的 `openjiuwen run PROMPT` 是非交互单次运行入口（`harness/cli/cli.py:323-354`），但它不能直接用于 harness-bench 的 coding 任务：

**根因**：`factory.create_agent` **无条件**挂审批 rail（openjiuwen 0.1.19）：

```python
# openjiuwen/harness/cli/agent/factory.py:553-557
rails.append(AskUserRail())
rails.append(ConfirmInterruptRail(tool_names=["write_file", "edit_file"]))
```

非交互下第一次遇到 `write_file`，`ConfirmInterruptRail.resolve_interrupt`（`rails/interrupt/confirm_rail.py:69-76`）会 `self.interrupt(...)` 弹「Please approve or reject?」，无人审批 → 文件不写、`result` 为空。

**对策**：复制 `create_agent` 的逻辑、**去掉 `AskUserRail` + `ConfirmInterruptRail`**（入口脚本 `openjiuwen_eval.py`，其余 rails——`SysOperationRail` 的 bash/file 工具、`ToolTrackingRail`、`SkillUseRail`、web 工具、subagents——原样保留）。

> 备选方案（未采用）：`confirm_rail.py:102-106` 支持 `auto_confirm_config`（dict 里 `write_file: true` 自动放行），但它是 per-session state，CLI 层无预置入口，侵入性高。去 rail 干净彻底。

入口脚本输入/输出契约：

- 输入：prompt（argv[1] 或 stdin `-`）、`--workspace`（agent 文件系统工具 cwd）、`--output-format json|stream-json`
- 模型凭证：环境变量 `OPENJIUWEN_API_BASE / OPENJIUWEN_API_KEY / OPENJIUWEN_MODEL / OPENJIUWEN_PROVIDER`（key 不进 argv）
- 输出（stdout 单份 JSON）：`{"result": "...", "chunks": N, "model": "..."}`，`stream-json` 时附 `trajectory`
- 退出码：0 成功 / 1 异常

### 4.2 entrypoint 契约（harness OCI contract）

harness-bench 对每个非-OpenClaw harness 用统一契约（`docker/README.md:75-100` + `run_contract_round`）：

- 环境变量：`HARNESSBENCH_PROMPT`（prompt 路径）、`HARNESSBENCH_CONFIG`（config 路径）、`HARNESSBENCH_WORKSPACE`（`/workspace`）、`HARNESSBENCH_STATE`（`/state`）、`HARNESSBENCH_TRACE`（`/trace`）
- 挂载：`/workspace`（rw bind）、`/runtime`（rw）、`/state`（volume）、`/run/harness`（ro）、`/trace`（rw）
- 约束：`--read-only` 只读根文件系统、`--user 1000:1000`、`--cap-drop ALL`、`--tmpfs /tmp:noexec`
- 要求：执行**恰好一个 agent turn**，转发进程 exit code

`entrypoint.sh` 做的事：

```bash
model="$(read_config model)"
export HOME="${HARNESSBENCH_STATE}/home"            # 只读根 fs → HOME 指向可写 /state
export XDG_CACHE_HOME="${HARNESSBENCH_STATE}/cache"
export OPENJIUWEN_API_BASE="$(read_config base_url)"
export OPENJIUWEN_API_KEY="local-vllm-no-auth"
export OPENJIUWEN_MODEL="${model}"
export OPENJIUWEN_PROVIDER="OpenAI"
python3 /opt/harnessbench/openjiuwen_eval.py "${prompt}" \
  --workspace "${HARNESSBENCH_WORKSPACE}" --output-format json
exit $?
```

### 4.3 config 渲染（render_harness_config 的 openjiuwen 分支）

openjiuwen 用 `chat_completions` 协议，config 是简单 JSON（参考 claude-code 分支 `:358-367`）：

```python
if spec.harness_id == "openjiuwen":
    config = {
        "base_url": base_url, "model": model,
        "max_tokens": max_tokens, "context_window": context_window,
        "max_turns": max_agent_turns, "thinking": thinking,
    }
    return json.dumps(config, ensure_ascii=False, indent=2) + "\n"
```

### 4.4 HarnessSpec 登记

```python
"openjiuwen": HarnessSpec(
    harness_id="openjiuwen",
    version="0.1.19",
    image="harnessbench/openjiuwen:0.1.19",
    protocol="chat_completions",
    config_name="config.json",
    docker_context=HARNESS_DOCKER_DIR / "openjiuwen",
    trace_complete=True,
),
```

---

## 五、难点与风险

### 5.1 openjiuwen 依赖重 + gitcode git 依赖（Dockerfile build 最大难点）

`pyproject.toml`（openjiuwen 0.1.19）：

```
requires-python = ">=3.11,<3.14"        → base 用 python:3.12-slim-bookworm
依赖里两类硬骨头：
1. git 依赖：intelli-router @ git+https://gitcode.com/openJiuwen/agent-protocol.git
              #subdirectory=intelli_router
   → pip install 时 git clone gitcode.com，build 环境网络必须可达 gitcode
2. 重型包：transformers / pymilvus / matplotlib / numpy / opentelemetry / fastmcp ...
   → 依赖体量几百 MB，build 慢
```

Dockerfile 里 `pip install "openjiuwen[cli]==0.1.19"` 会拉全部依赖 + clone gitcode。

### 5.2 只读根文件系统

`run_contract_round` 用 `--read-only`。openjiuwen 运行时写 `~/.openjiuwen`（config/settings）、`~/.cache`、skill 目录，这些都要指向可写位置。对策：`HOME`、`XDG_CACHE_HOME` 指向 `/state`（volume，rw）。

### 5.3 模型端点 DNS（待实测）

`run_contract_round` 有 `--dns 127.0.0.1`（`harness_runtime.py:414-415`）劫持容器 DNS。harness-bench 原生假设模型是 host 上的 vLLM（走 `host.docker.internal:host-gateway`）。如果模型端点是外部域名（阿里云 MaaS `ws-*.maas.aliyuncs.com` 等），容器内域名可能解析不了。冒烟时重点验证。

### 5.4 实际踩坑记录（build 实录 2026-10-27）

**坑 1：python:3.12-slim-bookworm 镜像拉不动**

harness-bench 其他 harness 的 Dockerfile 用固定 digest `python:3.12-slim-bookworm@sha256:d50fb7611...`。这个 digest 的镜像层走 docker mirror（1ms.run / daocloud）拉不动（0B 持续几十秒，回源慢）；去掉 digest 用 latest 也一样卡（latest 已更新、本地无该层缓存）。

对策：base 复用本地已缓存的 `harnessbench/agent-tools:local`（内容 = python:3.12 + 17 包 task-toolchain + bash/git/sqlite3/ripgrep，与 task-toolchain 完全等价）。**这是临时方案**（依赖 agentcompass 之前 build 的镜像），网络恢复后应换回标准两段结构（`FROM python:3.12-slim-bookworm AS task-toolchain` + 主镜像）。

**坑 2：python-docx 版本冲突（verify_toolchain 失败）**

`pip install openjiuwen` 时，openjiuwen 依赖 `python-docx>=1.2.0`（pyproject.toml:58），把 task-toolchain 锁定的 `python-docx==1.1.2`（requirements.lock）升级到 1.2.0。`verify_toolchain.py` 的版本检查（EXPECTED dict）因此报 `task toolchain version mismatch`。

对策：openjiuwen 镜像跳过 `verify_toolchain.py` 的版本检查（1.2.0 向后兼容 1.1.2，功能不受影响）。

**坑 3：intelli-router git 依赖其实不存在**

源码 pyproject.toml:48 声明 `intelli-router @ git+https://gitcode.com/openJiuwen/agent-protocol.git#subdirectory=intelli_router`（git 依赖），但 PyPI 上 openjiuwen 0.1.19 wheel 的 metadata 里该依赖已被替换成 `gitcode-api>=1.2.20`（普通 PyPI 包）。实测 `import intelli_router` 报 ModuleNotFoundError，但入口脚本依赖的所有模块（factory/renderer/sys_operation_rail/config/prompts/tools/Runner/create_deep_agent）都能正常 import，不受影响。

结论：Dockerfile build **不需要** gitcode.com 可达（git 依赖实际不存在），只需清华 pip 源 + PyPI。

---

## 六、改动清单（本次接入）

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `docker/harnesses/openjiuwen/Dockerfile` | base 复用 agent-tools:local（python:3.12+17包，临时方案）+ pip install openjiuwen + COPY 入口（跳过 verify 版本检查） |
| 新增 | `docker/harnesses/openjiuwen/entrypoint.sh` | 设 OPENJIUWEN_* env → 跑 openjiuwen_eval.py → exit code |
| 新增 | `docker/harnesses/openjiuwen/openjiuwen_eval.py` | 去 AskUserRail + ConfirmInterruptRail 的入口 |
| 修改 | `tools/harness_runtime.py` | SPECS 加 openjiuwen + render 加分支 |

不碰：`run_benchmark.py`、catalog、grader、task 数据、评分/mutation/语义判分链路。

---

## 七、验证（已通过）

代码层：

```
python3 -m py_compile tools/harness_runtime.py          → syntax OK
openjiuwen in SPECS                                    → True
render_harness_config(openjiuwen)                      → 输出含 base_url/model/max_tokens/context_window/max_turns/thinking
--harness choices（run_benchmark.py:3404）              → 自动包含 openjiuwen
```

镜像层（`harnessbench/openjiuwen:0.1.19`，1.56GB）：

```
openjiuwen 内核 import                                  → 0.1.19 ✅
入口脚本依赖模块 import                                 → OK（factory/renderer/sys_operation_rail/config/prompts/tools/Runner/create_deep_agent）
入口脚本 --help                                         → argparse 正常
无凭证跑 prompt                                        → 正确报 {"error": "API key not set. ... OPENJIUWEN_API_KEY ..."}
```

---

## 八、build + 冒烟

### build（已完成 ✅）

```bash
cd harness-bench-main
docker build -t harnessbench/openjiuwen:0.1.19 \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -f docker/harnesses/openjiuwen/Dockerfile .
```

结果：`harnessbench/openjiuwen:0.1.19`（1.56GB，依赖体量大）。

前提：清华 pip 源可达（`PIP_INDEX_URL`）。**不需要** gitcode.com 可达（见 5.4 坑 3，git 依赖实际是 gitcode-api）。

注意：当前 Dockerfile 的 base 复用 `harnessbench/agent-tools:local`（5.4 坑 1 的临时方案），build 前需先有该镜像。

### 冒烟

```bash
python3 tools/run_benchmark.py --harness openjiuwen \
  --model <model> --base-url <模型端点> <suite 参数>
```

验证点：write_file 是否放行（不卡审批）、模型端点是否可达（5.3 的 DNS 风险）、评分链路是否正常出 `outcome_score`。

---

## 九、关键源码依据（openjiuwen 0.1.19）

| 依据 | 位置 |
|---|---|
| create_agent 无条件挂审批 rail | `openjiuwen/harness/cli/agent/factory.py:553-557` |
| ConfirmInterruptRail 拦截逻辑 | `openjiuwen/harness/rails/interrupt/confirm_rail.py:59-99` |
| auto-confirm 读 config | `confirm_rail.py:102-106` |
| 非交互 run 入口 | `openjiuwen/harness/cli/cli.py:323-354` |
| json 输出 | `openjiuwen/harness/cli/ui/runner.py:79-105` |
| 依赖声明（gitcode git 依赖） | `pyproject.toml:48`（intelli-router） |

## 十、待办

- [x] build 镜像（`harnessbench/openjiuwen:0.1.19`，1.56GB）
- [ ] 冒烟测试（验证 write_file 放行 + 模型端点可达 + 评分出分）
- [ ] 网络恢复后，把 Dockerfile 的 base 从 agent-tools:local 换回标准两段结构（5.4 坑 1）
- [ ] openjiuwen 版本升级时，同步 diff `openjiuwen_eval.py` 复制的 `create_agent` 逻辑
