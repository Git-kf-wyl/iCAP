# MetaAgent

**新版架构正在实施：AgentFlow 外层调度 + MetaAgent 包内装配 + OpenJiuwen 原生执行。** N1 已接通新版包的 Workflow、DeepAgent-only、Hybrid 三种运行模式，验收清单完成 **4/4 = 100%**。Hybrid 复用已有路由，命中运行 Workflow，未命中才创建 DeepAgent；每个新请求只路由一次。原 `meta_agent.yaml` 包及现有入口继续有效。N4 交付模板与打包也已完成，四阶段路线完成 **2/4**；这是阶段计数，不是整体代码完成率，N2/N3 真实平台范围仍开放。

从仓库根目录运行本地高码示例：

```console
uv run --locked meta-agent validate examples/workflow_only/python
uv run --locked meta-agent draw examples/workflow_only/python
uv run --locked meta-agent run examples/workflow_only/python --input-file examples/workflow_only/python/inputs.json --session-id demo
```

示例计算购物车总价并保留结构化结果；另有 JSON `Start → End` 映射示例。包格式、Python API、支持范围见 [独立 Workflow 使用说明](examples/workflow_only/README.md)。新版 N1–N4 路线与验收清单见 [PLAN](PLAN.md#new-architecture)。`AgentFlow` 和 `SysAgent` 保持只读参考；真实平台联调按 staff 接口继续推进。

运行 [DeepAgent / Hybrid 包示例](examples/manifest_agents/README.md)：`uv run --locked python examples/manifest_agents/run.py`。默认复用本地脚本模型，无需 API key；原生 Workflow、DeepAgent 和路由真实执行。

N2a 已提供 **SidecarApp 宿主接口 + FusionMindModelClient / InferenceTransport 推理接口**，本批交接清单 **3/3 = 100%**。staff 实现真实宿主与 UDS/SDK 适配即可接入原生执行链，不需重写 Agent 工具循环。[平台交接文档与模板](examples/platform_handoff/README.md)说明完整消息/工具/usage 字段及待对齐项。运行 `uv run --locked python examples/platform_handoff/run.py` 可验证本地原生工具闭环；实际平台联调仍未完成，N2 整阶段保持开放。

N3a 已接通 [14 项原生组件的低码装配](examples/workflow_components/README.md)（含 LoopGroup 容器），并支持 Workflow/Hybrid 的 Questioner 待答续跑。运行 `uv run --locked python examples/workflow_components/run.py` 可体验输入 → 分支 → 工具/模型或子工作流 → 输出；模型为本地脚本。组件清单 **14/14 = 100%**。

N3b 已接通 [新版包的 Memory / Context / SkillsRuntime 配置](examples/package_services/README.md)，本批限定清单 **3/3 = 100%**。Memory / Skills 使用原生 tools；Context 使用原生 ContextEngine，远端 ContextService hook 当前只接 DeepAgent 分支。真实 SDK/gRPC 留有 staff 绑定接口，未宣称平台联调完成。运行 `uv run --locked python examples/package_services/run.py` 可验证关闭 runtime 后，新会话读取服务记忆并执行固定版本 Skill。

N4 已交付 [四类模板、ZIP 打包与 Linux Docker 说明](examples/delivery/README.md)，清单 **6/6 = 100%**。`uv run --locked meta-agent-package create hybrid .artifacts/my-agent --name my-agent` 生成可编辑包；`meta-agent-package pack` 按文件清单打包，不展开环境变量。`examples/delivery/run.py` 已在 Windows 和本机 Linux 容器运行解压后的四类模板及高码 Workflow；外层宿主通信仍由 staff 适配，不把本地 Node 调用计为真实 AgentFlow 调度。

以下记录既有功能架构基线；其综合验收百分比与新版实施清单分开计算。

MetaAgent 的独立工程仓库，基于固定版本的 OpenJiuwen。已有配置包、主/快双路径、后置 fallback、原生 Team 成员 DAG、A2A worker、平台适配、插件热更新与观测/进化的本地实现。恢复支持本机 SQLite、单 Agent PostgreSQL，以及 Team/A2A 特定审批点的共享交接；完整恢复组合与真实平台验收另行安排。

**功能架构基线完成（Functional architecture baseline complete）**。本期核心功能实施已结项：HITT/团队管理、异步子代理与预算、自动/团队进化和 workflow 固化已接到运行时，并有已支持配置下的正常路径运行证据。

已补齐 goal、声明只读 MCP、同步 `task_tool` 子代理和 HITT 的完整暂停恢复；同步子代理内部的 `ask_user` 与工具审批也可在保存完整交互后重建，使用父代理的 `resume` 继续原来的子任务。原生并发子代理现支持在父代理完整边界排空任务队列、保存结果与子会话，重建后读取结果并继续原来的子会话；执行中崩溃后的队列重放和异步子代理待答恢复仍后置。固定质量 workload 主路径/fallback 各 6/6、原生 5/6。综合验收估算 **75%（15/20）**，不代表架构代码或生产成功率。完整恢复组合、真实平台/SDK、跨主机仍开放；Team E2E 时延优化按用户要求后置，不阻塞当前里程碑，见 [PLAN](PLAN.md#0-功能架构基线结项)。

[Skill 审阅恢复](examples/skill_evolution/README.md#skill-审阅与版本恢复)已支持待审、批准/拒绝、partial 接续与回滚的本机重启保留。新 session 采用已激活版本，旧 session 保留固定 Skill 文件与经验。[生成 workflow 治理恢复](examples/skill_evolution/README.md#生成-workflow-的恢复)接入同一 checkpoint，保留 recipe、激活/回滚与插件字节；重启后宿主重绑工具并显式恢复，已有 execution 继续原版本。本批定向验收状态见 PLAN。

[源 Skill 发布](examples/skill_evolution/README.md#源-skill-发布与版本迁移)支持把已有 Skill 的新说明及配套文件暂存为待审快照，宿主批准后供新 session 使用；修改源目录本身不会激活。新发布采用不含本地进化历史的干净基线，原文件和经验完整保留用于回滚；已有 session 继续固定原版本。

[时延实测](benchmarks/latency/README.md)：规则路由 P95 <0.1ms，完整 Team/A2A P95 2.402s/2.158s，高于 2s 目标；固定内核的 idle 等待尚无公开配置。[质量基线](benchmarks/quality/README.md)保留全部 18 次结果及原生失败，只说明固定小样本的观察，不外推真实业务。

[Langfuse 原生观测](examples/observability/README.md)已接通单 Agent、Team/路由与真实数据集实验。使用 OpenJiuwen 原生 exporter；[Terminal-Bench 2.1 样例](benchmarks/terminal_bench/README.md)提供本地/托管 dataset、官方 Harbor verifier、两次实验比较及 score/trace/token 核对，成功与失败全部保留。Langfuse 三阶段接线完成，原综合验收仍为 75%。

设计与实施依据：

本机 MetaAgentTeam、原生 goal 预算、同步/异步子代理、CSP/MCP 本地契约、团队审批/真人任务、单 Agent 与团队 A2A/AgentGov worker、插件热更新、观测/Ops、自动 Skill 提议和 Memory/SkillsRuntime 已有可运行实现。团队 worker 支持真人收件箱/消息/任务操作及面向新 context 的配置重载，见[用法](examples/team_worker/README.md#真人协作-api)。功能证据与包含后续验收的综合完成度分别记录在 [PLAN](PLAN.md)。

- [实施计划与任务状态](PLAN.md)
- [团队技术讲解：如何基于 OpenJiuwen 构建 MetaAgent（12 页，可离线展示）](review/MetaAgent-staff-guide.html)
- [Langfuse 接入与 Trace 阅读指南（架构图、真实调用树，可离线交互）](review/MetaAgent-langfuse-guide.html)
- [架构设计 V1.1](MetaAgent-架构设计文档.md)
- [系统设计 V1.1](MetaAgent-系统设计文档.md)
- [设计修订审阅版](review/index.html)
- [依赖与兼容基线](docs/compatibility/baseline.md)
- [M1 原型结果与剩余门禁](docs/compatibility/m1-validation.md)
- [M1 接线决策](docs/adr/0001-m1-integration-boundaries.md)
- [M2 主路径验证](docs/compatibility/m2-validation.md)
- [M2 生命周期与接口边界](docs/adr/0002-m2-local-runtime.md)
- [M3 验证记录](docs/compatibility/m3-validation.md)
- [M3 插件与路由契约](docs/adr/0003-m3-fastpath-contract.md)

## 完整业务示例

真实模型读取本仓设计和源码、生成带引用的评审报告：

```console
uv run --locked python examples/repository_review/run.py --key-file ../siliconflow_key.txt
```

[仓库评审业务](examples/repository_review/README.md)使用现有 Team、Skill 和 MCP，两个成员都调用 SiliconFlow。以下脚本模型样例用于演示包含审批与进化的完整链路：

```console
uv run --locked python examples/architecture_demo/run.py
```

同一业务链路经过 A2A → Team Leader/成员 DAG → MCP 权限审批 → 真人评审 → 自动 Skill 提议/团队进化 → 宿主批准 workflow → 同一会话再次委派。第二次 researcher 走实际 Workflow、重新查询 MCP，模型和 DeepAgent 调用均为零。模型与评审输入使用确定性脚本，无需 key；其余组件使用真实本地运行时。结果、配置及流程图见[架构贯通样例](examples/architecture_demo/README.md)。

## 本机 HTTP MVP

一条命令启动 `health` / `invoke` / `resume`，复用现有运行时和 SQLite 恢复：

```console
uv run --locked python examples/http_agent/run.py
```

默认 `http://127.0.0.1:8080`，使用脚本模型，无需 API key。`hello` / `fast` / `fallback` 分别演示主路径、快路径和回退；`approve` 演示交互续跑。增加 `--real-model` 并配置模型环境变量即可使用原生 OpenAI-compatible 客户端；SiliconFlow 配置、PowerShell 调用与完整接口见 [HTTP 样例](examples/http_agent/README.md)。现有业务包可用 `meta-agent-worker path/to/package --state-dir .artifacts/worker` 启动。

`uv run --locked python examples/http_agent/run.py --smoke` 通过真实本机 HTTP 检查路由、重建后的结果读取和审批恢复。此接口为本机单 Agent、缓冲响应。A2A/AgentGov 使用下面的独立入口。

## A2A / AgentGov worker

```console
uv run --locked python examples/a2a_worker/run.py
```

同一个业务包通过组件调用和本地 AgentGov→A2A worker 链路运行。支持鉴权、原生 A2A 消息/SSE/任务查询/取消、审批续跑、SQLite task store、注册/心跳/下线，以及健康/DAG/插件/统计/轨迹文件只读管理接口。已有包通过 `meta-agent-worker path/to/package --protocol a2a` 启动，凭据与 callback 地址由环境变量注入；`--durable` 开启原有 LocalRecovery。

[配置、协议与容器说明](examples/a2a_worker/README.md)。[本机 Docker 部署](examples/docker_local/README.md)已通过镜像构建、健康检查及真实 SiliconFlow Team/A2A 调用。团队包使用同一个 A2A worker 入口：

```console
uv run --locked python examples/team_worker/run.py
uv run --locked python examples/team_worker/run.py --single
```

加载 `meta_team.yaml` 后，新业务输入进入 Team → Leader MetaBaseAgent DAG；原生团队委派仍进入成员 DAG。不同 context 使用独立团队，支持成员结果 SSE、审批续跑和取消，单成员快路径无需模型调用。[团队 worker 配置与范围](examples/team_worker/README.md)：`/admin/team` 提供状态，真人 API 支持原生任务操作，`POST /admin/team/reload` 为新 context 加载更新后的业务包。默认模式的成员 DAG、Skill 提议及插件保留至整个 Team 关闭。`--durable` 的既有审批交接范围保持独立；真实 AgentGov 和跨主机恢复属于后续验收。

```console
uv run --locked python examples/team_worker/recovery.py
```

两个独立 worker 进程经 A2A 验证原 task/execution 续跑，已完成的成员工作不重复。等待中的审批须先完整持久化；任意执行位置崩溃接管不在本批范围。

## PostgreSQL 单 Agent 共享恢复

```console
uv run --locked --extra postgres python examples/recoverable_agent/run.py --postgres
uv run --locked --extra postgres python examples/recoverable_agent/run.py --postgres --fastpath --approval
```

设置 `META_AGENT_POSTGRES_DSN`，宿主通过 `Recovery(PostgresRecoveryStore(...))` 注入组件。租约、原生 checkpoint、操作 journal、请求/响应与插件 pin 共用 PostgreSQL；两个独立目录的进程通过同一数据库接管原 execution。A2A worker 可加 `--durable --postgres`，Team 审批交接同步恢复原生数据库与正文文件；旧 worker 须先退出；支持待答成员工具审批接续，实际跨主机验收待完成。[共享恢复](examples/shared_recovery/README.md)、[团队 worker](examples/team_worker/README.md)。

## 插件热更新

```console
uv run --locked python examples/plugin_updates/run.py
```

加载、激活、回滚、停用和卸载已有组件 API 与鉴权管理接口。新 execution 使用当前版本，运行中/暂停/fallback 保留原版本；同一会话的新一轮可切换到 v2。worker 保存版本目录和激活选择，LocalRecovery 复用原有 artifact/pin 保证重启后的 v1 审批续跑，恢复保留期未结束时拒绝卸载。配置与接口见[热更新样例](examples/plugin_updates/README.md)。

## 观测与 Ops

```console
uv run --locked python examples/observability/run.py
```

元数据 JSONL 按 UTC 日轮转，关联路由、模型、工具、运行/插件生命周期和流式原生 TraceSchema。配置 `csp.ops` 可上报启动、指标与轨迹写入告警；组件 `observability()` 与 worker `/admin/stats/observability` 提供相同快照。运行及字段说明见[观测样例](examples/observability/README.md)。真实 Ops 平台仍待联调。

## 原生轨迹与 Skill 进化

创建全新 Skill 的独立示例已接入原生 `SkillCreateRail`：

```console
uv run --locked python examples/skill_creation/run.py
```

演示建议创建 → 用户同意 → 原生工具写入并读回 → 后续任务及 Agent 重新加载后读取。模型回复为固定脚本，不需要 key；配置、各模块职责和验证范围见 [创建新 Skill](examples/skill_creation/README.md)。它与下面改进已有 Skill 的接口分别配置。

```console
uv run --locked python examples/skill_evolution/run.py
```

显式启用 `trace.trajectories` 后，将含正文的原生 OTLP 轨迹写入独立目录。`evolution.enabled` 开启宿主提议→审批/拒绝→下次调用生效→配对回滚，复用当前模型与原生 SkillEvolutionRail/FileTrajectoryStore/EvolutionArchiveService；治理元数据继续进入 JSONL。样例无需 key，验证改进经验实际进入模型上下文。配置、宿主 API 和单进程范围见[Skill 进化样例](examples/skill_evolution/README.md)。

`evolution.auto_propose=true` 与 `auto_skill` 让正常执行结束后扫描已捕获轨迹，由原生信号检测器发现纠正/失败线索并形成待审提议。`TeamEvolution` 可汇合成员执行证据改进 `kind: team-skill` 的团队 Skill。宿主绑定具体工具、审批声明式 workflow 后，通过原有插件机制激活和回滚；workflow 每次调用真实工具，不重放历史答案。业务模型不能自行批准或提交任意 Python 代码。

## Memory / SkillsRuntime

```console
uv run --locked python examples/memory_skills/run.py
```

通过配置选用记忆服务和指定版本的远程 Skill，复用原生工具、权限审批与轨迹。样例验证写入确认→Agent 重建/新会话读取→远程 Skill 解析与执行；不需要 API key。未配置适配器时保留原生上下文及本地 Skills。宿主设置记忆归属与远程版本，服务持有存储和执行；当前为本地 HTTP 契约，LocalRecovery 写入绑定与真实平台仍待集成。详见[配置与样例](examples/memory_skills/README.md)。

## 本机 MetaAgentTeam

```console
uv run --locked python examples/team_demo/run.py --single
uv run --locked python examples/team_demo/run.py
```

原生 Runner/AgentTeams 负责协作，Leader 和 researcher 均执行正式 MetaBaseAgent DAG。样例演示配置包装配、消息委派、成员零模型快路径与 Leader 汇总；集成测试还覆盖主路径成员、Leader 交互/fallback、继续对话和取消关闭。加入 `--real-model --key-file ../siliconflow_key.txt` 可运行 SiliconFlow 验证。接口、配置及当前范围见 [团队样例](examples/team_demo/README.md)。

当前为同进程、本机配置成员团队；已接通成员工具 allow/ask/deny、Leader 审批续跑、预配置 passive human 消息往返和平台 MCP 本地契约。可选 `LocalRecovery` 已支持其他成员完成后的 Leader 审批暂停、进程重建与原 execution 续跑：

```console
uv run --locked python examples/team_recovery/run.py
```

[团队恢复样例](examples/team_recovery/README.md) 使用两个独立进程验证不重复委派。恢复支持未完成成员的原生工具审批接续，暂不包含 passive human、成员快路径回复或成员普通 ask_user；协调工具每类每 execution 一个逻辑操作。普通 HITT 消息/任务与团队更新已有功能路径，恢复组合、实际跨主机部署与真实平台继续按 PLAN 后续验收；完整 GATE-TEAM 尚未通过。

## CSP / MCP 与团队权限

```console
uv run --locked python examples/platform_demo/run.py
uv run --locked python examples/platform_demo/run.py --deny
```

样例经过本地 InferSchedule-compatible HTTP → Leader 委派/审批 → 成员 MCP 网关 → 团队汇总；批准执行一次，拒绝不执行。复用原生模型、MCP、权限 rail 和 HITT API。真实平台端点/路由契约尚待联调；配置、错误码、真人成员消息接口和当前限制见 [平台样例](examples/platform_demo/README.md)。

## 开发环境

使用 Python 3.11 和 uv 0.11.19 或更新版本。安装依赖需要访问 PyPI 与 GitCode；运行确定性 smoke 测试不需要模型 API key。

```console
uv sync --locked
uv run --locked python scripts/check.py
uv run --locked python examples/kernel_smoke.py
```

`uv.lock` 固定完整依赖；OpenJiuwen 和其 Git 依赖 intelli-router 都固定到提交。首次安装可能较大，因为当前 OpenJiuwen 的基础依赖包含模型、文档处理及检索库。不要用 `--no-deps` 跳过内核依赖以制造通过结果。

在禁止写入默认缓存的环境中，可把 `UV_CACHE_DIR` 指向工作目录内的缓存目录；不需要修改系统配置。

## 运行最小 Agent

```console
uv run --locked python examples/minimal_agent/run.py
uv run --locked python examples/minimal_agent/run.py --stream
```

默认样例使用本地可编程模型，但执行的是已安装的 `meta_agent` API、真实 Workflow 和 DeepAgent。配置包必须包含 `meta_agent.yaml` 和有效的 skills。样例会把业务包及工作区复制到独立的 `.artifacts/minimal-agent-*` 目录，并打印结果与轨迹位置。真实模型端点模板和环境变量见 [minimal_agent 说明](examples/minimal_agent/README.md)。

```python
from meta_agent import MetaBootLoader

async def answer():
    async with await MetaBootLoader("path/to/package").boot() as agent:
        result = await agent.invoke("你好", session_id="chat-1", request_id="request-1")
        print(result.output, result.usage)
```

`load()` 只校验和计算配置包 digest；`boot()` 物化 provider 并启动本地运行时。无插件图固定为 `Start → DeepAgentComp → End`。`stream()` 产生 `delta`，然后产生一个 `final` 或 `input_required` 控制事件；结束事件包含调用计数。提前停止消费时使用 `contextlib.aclosing(agent.stream(...))`，确保取消底层任务。

每次调用都必须传入 session/request ID。同 session 的并发调用及重复 request ID 被拒绝；同一会话的后续轮次使用新 request ID。收到 `input_required` 后，用原 session ID、新 request ID 和答案再次调用；execution ID 在暂停与续跑之间保持不变。`follow_up(text, session_id=...)` 只给正在执行的原生 TaskLoop 排队消息；空闲会话的新轮次使用 `invoke()`。`abort(session_id)` 取消并等待当前执行，失败或取消后的会话需要新 session ID。

本地运行时共享一个受管 Runner，并要求在同一事件循环上使用相同 checkpoint 配置。同一 product/agent 身份只能有一个存活对象。宿主不得同时自行启动、停止或重配置全局 Runner；退出时使用 `aclose()` 或 async context manager。SQLite 配置选择内核 checkpoint 存储，尚不提供对象/进程重建后的业务恢复；正常关闭会释放该对象的会话状态。

普通 EVAL 可直接启用原生 shell/文件操作、网络搜索和网页抓取；`enable_sys_operation: true` 配合 `core.sys_operation` 暴露完整文件工具与 shell，保留显式配置的 SysOperation 后端。已有 `false` 配置继续只读 Skill。MCP 支持原生直连（含 stdio），配置 CSP Gateway 时才经网关改写。具体配置、搜索环境变量和运行证据见 [原生工具对齐](examples/native_tools/README.md)。

自定义 tools/rails/plugins 属于受信任业务代码。通用 shell/文件写入与 LocalRecovery 暂不组合，恢复要求不再限制普通 EVAL 的工具范围。原生 goal 预算与配置式子代理见下节；进化使用上文显式配置，分布式及外部 effects 通用开关仍未开放。本机团队使用独立的 `meta_agent.team` 入口。

## Harness 预算与子代理

```console
uv run --locked python examples/harness_demo/run.py
uv run --locked python examples/harness_demo/run.py --mode subagent
uv run --locked python examples/harness_demo/run.py --mode complete
```

`budget.enabled=true` 将主路径/fallback 接到原生 GoalManager、TaskCompletionRail 和 GoalEvaluator；`max_attempts` / `token_budget` 在尝试边界停止继续执行，保留部分回答及 `META_BUDGET_EXHAUSTED` 错误。配置式同步子代理使用原生 `task_tool`，模型调用及报告的 token 汇入父请求；成功快路径仍不调度 DeepAgent。

支持 `hybrid` / `agent_report` / `transcript` 策略；assessor 调用进入 usage 和预算判断。预算目标可经 `ask_user` 暂停并在原 execution/goal 内继续。配置 `enable_async_subagent` / `enable_subagent_runtime` 可使用原生并发子任务、等待和结果汇总；子代理沿用 MCP 网关、权限与调用计量，普通模式下宿主可处理独立子代理的待审批请求。token 额度仍在尝试边界检查。LocalRecovery 支持 goal、同步子代理的完整交互暂停恢复，以及 `enable_subagent_runtime` 并发任务的完整边界保存：返回父代理暂停/结果前等待已有运行中与排队任务结束并关闭 worker，再原子保存父子状态；重建后的 `subagent_wait` 可读原结果，`subagent_resume` 配合 `subagent_send_input` 可继续原来的子会话。仅启用旧式 `enable_async_subagent` 的 SessionToolkit、执行中崩溃后的队列重放和异步子代理待答恢复尚未开放。完整配置与边界见 [Harness 样例](examples/harness_demo/README.md)。

## 快路径与退款样例

```console
uv run --locked python examples/refund_fastpath/run.py
uv run --locked meta-agent validate path/to/package
uv run --locked meta-agent draw path/to/package
```

退款样例使用内存测试账本，演示原生审批暂停/续跑、成功快路径 **0 次 DeepAgent/模型调用**，以及找不到订单时的普通失败 fallback。没有实际付款或退款。配置与开发约定见 [refund_fastpath](examples/refund_fastpath/README.md)。`validate/draw` 会执行受信任插件的 import/build 来验证图结构，不启动 Agent 模型；模型 provider 可达性不在该检查内。

启用 `fastpath.plugins_dir` 后，插件按 `manifest.json` 加载。`build(context)` 返回 `context.workflow()` 创建的 `PluginWorkflow`，仍由真实内核执行。插件的 End 输出为 `{"result": {"status": "success", "output": "...", "data": {...}}}` 或显式 failed outcome。`output` 是可选的文字说明，默认空字符串；`data` 保留业务结构化结果，默认 `null`，旧插件无需修改。只有 `PluginFailure`/failed outcome 可以 fallback；白名单或关闭 fallback 会产生 `AgentResult(result_type="error", error=...)`。暂停、取消、失租、存储故障、副作用未决与未知程序异常不会转主路径。

业务结果不必转换成文字。例如节点返回：

```python
return {"result": {
    "status": "success",
    "output": "订单查询成功",
    "data": {"order_id": "100", "amount": 2500, "items": []},
}}
# End 的 inputs_schema 将该节点的 result 映射到 result。
# 调用方：result = await agent.invoke(...)
# 金额：result.data["amount"]
```

`data` 支持 JSON 对象、数组、字符串、有限数值、布尔值及 null；业务字段及结构由业务定义，不在 MetaAgent 中硬编码。日期、Decimal、自定义 Python 对象等应由业务显式转换为 JSON 值，NaN/Infinity 被拒绝。框架不会从 `output` 文本猜测或解析业务 JSON。结构化结果经 Merge / End 原样传到 `AgentResult.data`，普通及耐久 `stream()` 的 final 事件为 `event.data["data"]`，HTTP 返回体为 `data`，A2A 的 `meta-result` artifact 中为 `data`；A2A 文本 artifact 仍只包含 `output`。A2A 数据遵循底层 protobuf Struct 数值表示，超大整数/高精度金额可由业务编码为字符串。

明确终止的 failed outcome 也保留其 `data`，调用方应先检查 `result_type`。允许 fallback 时，失败插件的 `data` 仅随来源信息交给 DeepAgent；最终回答不自动继承它，避免把失败数据当成成功结果。纯 DeepAgent 路径目前返回 `data=null`。已完成响应的保存和读取、暂停后的恢复均保留该字段；旧的已存响应缺失此字段时按 null 读取。Team 的成员结果记录包含 `data`，Leader 的自然语言汇总不承诺透传成员业务数据。

调用时通过 `context={...}` 传递可信路由上下文，例如权限和历史版本；所有策略和缓存命中都检查 `when`。这不是平台权限验证器，调用方负责提供可信上下文。插件版本/内容、路由配置、scope/query/context 和自适应策略版本隔离缓存。规则、Skill 元数据、条件路由无需模型；embedding/classifier 必须由宿主显式注册，调用数单独出现在 `route_stats()`。`usage.deep_agent_calls` 衡量每个请求片段的主路径调度次数。

## 本机 Agent 重启恢复

通过 `MetaBaseAgent.create(spec, recovery=LocalRecovery(store, adapters=(...)))` 或 `MetaBootLoader(...).boot(recovery=...)` 显式启用。未完成轮次用 `agent.resume(session_id=..., request_id=..., answer=...)` 恢复；不必重传原 query/context。已完成轮次读取保存的响应。关闭保留耐久 checkpoint；下一轮 invoke 保留会话记忆并创建新 execution。

恢复模式在发布最终响应前确认 journal 已无未决效果；stream 暂为缓冲终态，follow_up 暂不支持。配置的其它工具须声明 read_only_tools，宿主 provider/rail/plugin 仍是受信代码。原生 graph 仅在错误/交互边界提交，未提交的模型和只读计算可能重做。完整边界见 [ADR-0005](docs/adr/0005-local-runtime-recovery.md) 和 [运行手册](docs/runbooks/local-runtime-recovery.md)。

运行 `uv run --locked python examples/recoverable_agent/run.py`，实际终止 Agent 子进程后重启；同一 execution 完成，独立测试账本只有一笔。无需 SiliconFlow key。

M4 已进一步接通快路径写入：宿主用 `EffectBinding(name, adapter, logical_key)` 在 `LocalRecovery.plugin_effects` 注册操作；插件 manifest 声明 `effects` 能力名，`context.effect(name)` 创建受管节点，fallback 使用同一绑定的 `binding.tool(card)`。嵌套子图与主路径共享操作身份。未决效果阻止 fallback；传给模型的完成操作列表与回执由 journal 生成。通用 effects/分布式配置开关仍未开放。

运行 `uv run --locked python examples/recoverable_agent/run.py --fastpath`，或再加 `--fallback`，验证插件写入后进程终止与恢复。成功快路径零 DeepAgent 调度；fallback 重复请求工具仍只写一次。带效果声明的插件需要 Python 宿主绑定，当前 CLI validate/draw 会拒绝无绑定启动。见 [ADR-0006](docs/adr/0006-fastpath-effect-bindings.md) 与 [验证记录](docs/compatibility/m4-fastpath-recovery-validation.md)。

当前支持的提交/重做/禁止写入见 [B0–B8 边界清单](docs/compatibility/m4-supported-boundaries.md)。恢复前的 pending reconciliation 也纳入整段租约取消作用域；续约断连会取消 observer 等待及查询/调用。终态提交后即使客户端等待被取消，resume 仍读取已存结果。更细成功步骤/Agent 迭代 checkpoint 的[公开接口提案](docs/proposals/0001-native-checkpoint-boundaries.md)尚未实现。[本批验证](docs/compatibility/m4-boundary-validation.md)。

## 构建和安装验证

本地耐久效果样例：`uv run --locked python examples/durable_effects/run.py`。它演示“独立测试账本已提交、响应丢失”后的重建与查询恢复，账本只保留一笔。宿主通过 `DurableExecution` 显式绑定业务身份和版本，`finish()` 成功后再发布结果；不是 MetaBaseAgent 的自动冷恢复入口。[开发说明](examples/durable_effects/README.md) · [设计决策](docs/adr/0004-local-durable-effects.md) · [运行手册](docs/runbooks/local-effects-recovery.md)。

```console
uv run --locked python scripts/check.py --build
uv run --locked python scripts/verify_wheel.py
```

`check.py` 统一执行 Ruff、格式检查、源码类型检查和测试；`--build` 额外构建 sdist/wheel。`verify_wheel.py` 在独立环境同步锁定的运行时依赖，再安装本项目 wheel，从隔离 Python 进程运行内核 smoke、M2 流式样例、M3 退款样例、M4 耐久效果及整个 Agent 进程终止/重启样例，避免 editable 安装掩盖打包遗漏。

制品输出到 `dist/`，独立安装验证环境位于 `.artifacts/`，二者不纳入 Git。wheel 必须与锁文件一起用于当前开发验证；发布策略及制品仓库将在后续阶段确定。

## 测试边界

真实 Workflow/Runner/DeepAgent 运行时由固定内核提供；模型与外部服务使用确定性边界替身。测试账本和故障点用于本机效果恢复验收；本机原生冷恢复已有测试，真实下游契约、任意 TaskLoop 中间步恢复和跨主机共享存储仍须另行验证。

`spikes/` 中的 M1 原型已组合真实 Workflow/DeepAgent，验证成员 provider/runtime，并使用独立 SQLite 账本和真实进程终止验证本地恢复窗口。它们不作为 wheel 的生产 API；详细用法见 [原型说明](spikes/README.md)。

当前支持的 native spec 装配、预算交互和子代理正常路径已有运行证据；完整 GATE-DAG/GATE-TEAM 的恢复组合及平台范围仍未验收。JSONL 元数据日志记录关联 ID、状态与计数，不保存提示词/工具参数，也不承担耐久 journal 职责；显式开启的原生轨迹采集另存正文。模型调用数来自原生 rail 回调；token 计数仅使用模型实际提供的 usage，`usage_reports=0` 表示未报告。`trace_errors` 暴露运行期间的观测写入失败，成功计算不会因此被改成可重试错误。
