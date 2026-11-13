# MetaAgent 仓库实施计划

| 项目 | 内容 |
|---|---|
| 计划版本 | V1.26 · 2026-11-03（LF3 真实 Terminal-Bench 实验接通；Langfuse 三阶段完成） |
| 当前状态 | **功能架构基线完成（Functional architecture baseline complete）**：基于 OpenJiuwen 的核心功能已实现，并有已支持配置下的正常路径运行证据；本期实施阶段结项 |
| 已有成果 | V1.1 设计与标红审阅版、锁定工程、M1 风险原型、M2/M3 双路径、M4 本地 L1/L2/L3 fencing、整 Agent 重启与快慢路径共享操作身份、B0–B8 边界清单与恢复取消修复 |
| 功能证据 | §7 的 F1b/F2/F3 定向功能检查与 [完整链路样例](examples/architecture_demo/README.md)；[真实模型业务](examples/repository_review/README.md)补充 Team/Skill/MCP 运行证据；[本机 Docker](examples/docker_local/README.md)已通过真实 A2A 快路径与模型委派 |
| 后置实现与验收 | 已补齐 goal、声明只读 MCP、同步子任务与真人任务的完整暂停恢复、Skill 审阅/版本恢复、生成 workflow 治理恢复、并发子任务完整边界恢复及固定 workload 质量评估；本批接通源 Skill 文件发布、审阅快照与完整版本回滚，新 session 采用批准版本；时延目标暂不作为当前工作要求；运行中队列、异步子待答、平台写入恢复与跨主机/真实平台互通保持开放 |
| 仓库位置 | 当前 `metaAgent/` 目录；已初始化独立 Git 仓库，保留已有设计资料 |
| 后续范围 | 本期核心功能开发已结束；只在明确需求或具体功能缺陷出现时安排增量。恢复/部署/性能验收及特定业务示例优化另行立项，不作为本期结项条件 |

依据：[架构设计 V1.1](MetaAgent-架构设计文档.md)、[系统设计 V1.1](MetaAgent-系统设计文档.md)。[原始提案](MetaAgent-design.md)保留作历史参考。本文把设计拆成实施任务，不把文档中的伪代码视为现有实现；如原型否定设计假设，先记录 ADR 并同步修订设计。

## 0. 功能架构基线结项

2026-10-22 按确认的本期范围结项：复用 OpenJiuwen 执行内核，完成 MetaAgent 配置装配、双路径与 fallback、Team/成员 DAG、MCP/权限/交互、Skills/子代理/预算、插件更新及观测/进化的正常功能连接。实现基线为 `c3b257a`，真实模型业务使用补充为 `7758d12`；直接证据见 §7 各功能批次。本次仅确认阶段状态，不新增功能或重跑测试。

| 原架构目标 | 已交付功能 | 本次未关闭的原目标范围 |
|---|---|---|
| G1 开箱即用 | 配置业务包启动、组件与 worker 入口、本机 Docker Team/A2A 部署 | 真实平台部署与平台 SDK 互通 |
| G2 低时延 | 同一 DAG 双路径，快路径零 DeepAgent；本机规则路由 P95 < 0.1ms | Team/A2A 完整终态 P95 为 2.402s/2.158s；优化按用户要求后置，不阻塞当前里程碑 |
| G3 复杂任务 | 原生 DeepAgent 与 fallback；固定 6 题质量基线：原生 5/6、主路径 6/6、fallback 6/6 | 小样本不外推生产分布、长视界任务或其他模型 |
| G4 状态恢复 | 本机/单 Agent 共享恢复；goal、只读 MCP、同步子任务父暂停及子代理内部待答/审批；并发子任务队列排空后的状态/结果保存与原会话接续；Skill 审阅、源文件发布/回滚与固定 session 版本；团队审批与 HITT 接续；生成 workflow 治理与固定 execution 版本 | 运行中异步队列、异步子待答、平台写入等组合及完整跨主机接管 |
| G5 插件定制 | Skills/rails/workflow/路由扩展，加载/切换/回滚/卸载 | 本机已验证范围以外的部署验收 |
| G6 多 Agent | 原生 Team、Leader/成员 DAG、MCP/权限/HITT、团队更新 | 完整 GATE-TEAM 的恢复与平台门禁 |
| G7 观测进化 | 本地 trace/JSONL、Skill/Team 进化及审批/回滚 | 真实平台联调与恢复组合 |

**结项的是功能架构基线，不是全部 G1–G7 指标或生产发布。** 原 20 项综合验收在结项时为 14/20 = 70%；本次完成 #6 的固定 workload 质量评估后为 **15/20 = 75%**。这不是架构代码百分比，也不等于生产成功率。质量基线的题集、评分、失败项和适用范围均有记录，不以增加 demo 或测试数量计分。

2026-10-26 按 EVAL 需求补齐 [OpenJiuwen 原生工具接线](examples/native_tools/README.md)：移除早期全局 system tools 禁用和 MCP 强制网关限制；普通模式保留原生 SysOperation、SkillUseRail 工具策略及子代理工具，直接使用 `core.web_search` / `core.web_fetch`，MCP 可原生直连 HTTP/stdio，也可按 CSP 配置经网关。恢复仅约束 LocalRecovery 配置，通用 shell/文件写入未宣称具备耐久效果恢复。本批工具接线完成 **100%（限定上述范围）**；真实数据集成绩、公网/付费搜索与远端 sandbox 验收未完成，原综合验收仍为 **75%（15/20）**，不因新增工具测试上调。

定向验证：原生/MetaAgent CSV 文件读写和 PowerShell 计算、子代理读文件、本机 HTTP 搜索/抓取、HTTP/stdio MCP 及恢复配置分界；复查已有平台权限、预算/子代理与只读 MCP 恢复。本批未增加恢复功能或穷举恢复组合。

2026-11-03 新需求：[Langfuse 原生支持方案](docs/proposals/0002-langfuse-native-integration.md)。直接复用当前 OpenJiuwen 已有的 Langfuse OTLP/HTTP exporter、鉴权、span 映射和 provider 生命周期，按 **LF1 单 Agent tracing → LF2 Team/快路径/fallback → LF3 EVAL 实验与评分** 三批实现。**LF1/LF2/LF3 已完成，实施 3/3 = 100%**；不调整原综合验收 **75%（15/20）**。EVAL 使用可选 Langfuse SDK 5.1.0，既有内核与 OTEL 锁定版本不变。

同日按用户要求完成本机部署：官方 Langfuse **4.72.0**，Compose 项目 `metaagent-langfuse` 的 6 个服务均 healthy；UI 为 `http://localhost:3000`，已创建组织 `MetaAgent Local` 与项目 `MetaAgent Test`。实际账号登录、数据库/readiness，以及 OpenJiuwen 原生 exporter 的 root/tool 两节点 trace 写入和 API 读回均通过；工具结果为 42，没有模型调用。本机测试环境准备 **100% 完成**；该独立连通性检查与后续 LF1 验收分开记录。部署文件和凭据位于仓库同级 `langfuse/`，凭据不进入 Git；操作方式见方案 §5。

LF1 交付：`trace.observability` 接受原生配置并沿用 ENV 展开；远端 export 与本地 `trajectories` 解耦，单 Agent 的 root/Agent/model/tool spans 自动关联，关闭时沿用原生 flush。相同配置的 Agent 共享 provider，不同配置或本地 `_NoExport` 先启动时明确报配置冲突。无新增运行依赖、exporter 或恢复队列。两次真实 SiliconFlow GLM-5.1 运行均在 Langfuse 读回 9 个 observations、2 次 generation、1 次工具和答案 `42`，每次 1150 input / 17 output tokens；仅远端与本地归档并存均通过。11 项定向功能/相邻检查及目标 Ruff、格式、Mypy 通过。使用方式、报告与 trace ID 见 [Langfuse 样例](examples/observability/README.md#langfuse-原生接入lf1)。

LF2 交付：`meta_team.observability` 统一配置原生 Team/成员观测；实际成员执行、同步/异步子 Agent、模型和工具保持父子关联。增加路由、快路径、fallback 节点和业务身份、package/Skill manifest/plugin 版本属性；正常暂停续跑保留 execution ID，纯 workflow 不生成虚假模型记录。原生外部 Harness turn 摘要仍为独立 trace，按同一 session 关联，不重复 generation/token；Team 根 output 为生命周期事件，回答在成员节点。

真实 GLM-5.1 → 本机 Langfuse 验证：Team 委派含 calculator/加法工具，9 次模型调用、答案 `42`；快路径 0 次、fallback 1 次模型调用。输入/输出 token 合计分别为 46512/216、0/0、3185/47，与 MetaAgent 一致；已处理 Langfuse 缓存/reasoning 分桶的对账口径。原生 shell、Web/MCP 本机传输、并发子 Agent、暂停续跑与采样关闭通过定向检查。配置、展示边界及报告见 [LF2 使用说明](examples/observability/README.md#team路由和版本关联lf2)。LF3 结果见下文；跨主机仍按部署条件后置。

LF2 最终定向验收 **16 项通过**（`.artifacts/langfuse-lf2-complete.log`），目标 Ruff、格式与 Mypy 通过；真实 Langfuse 读回证据为 `.artifacts/langfuse-team-readback-final.log`。没有新增 Python 依赖。

LF3 交付（2026-11-03）：按用户要求，以 **Terminal-Bench 2.1** 的 `openssl-selfsigned-cert` 与 `fix-git` 验收。轻量 Harbor adapter 启动真实 MetaBootLoader/MetaBaseAgent，原生 LocalFunction 将 terminal 请求交给题目容器；官方 Langfuse experiment runner 负责本地/托管数据项、实验和评分，W3C 上下文连接既有原生模型/工具 trace。官方题目、容器资源与 verifier 保持不变，版本/摘要、模型/Skill、item/score 和失败记录均可追溯。

本地首轮遇到原生 Workflow 默认 60 秒超时，保留为未评分错误；通过内核已有配置对齐官方 900 秒后，首题 6/6、reward=1.0。随后两题做两次同配置托管实验：两轮 fix-git 均 2/2、reward=1.0；证书题均 5/6、reward=0.0（生成脚本依赖的 cryptography 在 verifier Python 环境缺失）。四条正式结果与两条 pilot 全部保留，不改测试、不覆盖失败；这是接口验收完成，不是题目全部通过。

真实 Langfuse API 已核对两次 experiment 的 item/版本、官方 reward、完整父子 trace、模型/terminal 次数与 inclusive tokens；本地和托管读回均通过。另有 **7 项**定向内核检查、Ruff/格式及离线 lock 检查通过；未扩大恢复矩阵或时延工作。使用命令、实验链接、全部成绩及证据目录见 [LF3 运行与结果](benchmarks/terminal_bench/README.md)。本批完成 **100%**，Langfuse 实施 **3/3 = 100%**；原综合验收保持 **75%**。后续按实际数据集/质量问题迭代，不以两题结果外推完整 benchmark。

M0 验收：Windows / Python 3.11.15，16 项测试通过；Ruff、格式、mypy、sdist/wheel 构建及独立运行时环境安装验证通过。CI 矩阵已配置，远端矩阵尚未执行。详见 [M0 验收记录](docs/compatibility/m0-validation.md)。

M1 最终本地检查：51 项测试通过（M0 16 + M1 35），Ruff/格式/mypy 通过。实测范围、未运行项和接缝缺口见 [M1 验证记录](docs/compatibility/m1-validation.md)；实现边界见 [ADR-0001](docs/adr/0001-m1-integration-boundaries.md)。测试通过包含“明确拒绝未支持配置”，不能按测试总数判定所有产品门禁通过。

M2 已交付 `src/meta_agent` 中的配置与启动、无插件三节点图、真实增量流/交互/活动 follow-up/取消、身份与 JSONL 轨迹，以及 minimal_agent 的脚本模型/真实端点模板。验证细节见 [M2 记录](docs/compatibility/m2-validation.md)，本地运行时边界见 [ADR-0002](docs/adr/0002-m2-local-runtime.md)。M2 是独立单 Agent 开发里程碑，不是默认团队或完整生产发布。

M3 已交付 manifest/插件字节快照、公开构图校验、Skill/规则/embedding/when/classifier 路由、有界缓存与自适应统计、原生子图和后置 fallback、单一结果出口、validate/draw CLI 及退款测试账本。成功退款经审批续跑仍为 0 次 DeepAgent 调度/模型调用。证据见 [M3 记录](docs/compatibility/m3-validation.md)，受信任插件与恢复边界见 [ADR-0003](docs/adr/0003-m3-fastpath-contract.md)。

M4 前两批本地增量：`375fd37` 的耐久效果层，以及 `3473c00` 的 LocalRecovery 运行时装配。最新整 Agent 重启样例保留原 execution，账本记录和写入尝试均为 1。上述测试数与构建结果对应该实现快照，不代表全部 M4 门禁通过；证据见 [M4 运行时记录](docs/compatibility/m4-runtime-recovery-validation.md)。

## 1. 交付目标与边界

原设计的完整交付目标保留如下；本次结项范围以 §0 的功能架构基线为准：

- `meta_agent`：MetaBaseAgent、统一 Workflow DAG、插件与路由、恢复与可观测、经验证的 MetaAgentTeam。
- `meta_agent_adapter`：CSP 推理、MCP、运维、AgentGov 客户端；记忆和独立 Skills 运行时按配置启用。
- `agentworker`：独立容器入口、内部 A2A listener、启动/就绪/摘流与关闭流程。
- 组件 wheel、worker 镜像、业务配置与插件样例、校验 CLI、管理 API 和验收证据。

默认单成员与多成员 Team 的正常接线均已有运行证据；完整团队发布仍需通过 GATE-TEAM 的剩余门禁。

本机 `meta_agent.team` 入口使用原生 Runner/HarnessProvider，已接通单 Leader、leader+researcher 及普通权限/MCP/HITT 路径；完整恢复和真实平台验收仍待完成。

本期功能架构实施已结束。下列 M0–M7 编号继续记录原设计完整范围；未完成的恢复组合、平台/部署接线与质量指标保持明确缺口，不因阶段结项提前勾选。后续仅按明确需求或已发现的具体功能缺陷安排工作。

AgentGov 服务、平台 MCP 网关、InferSchedule 等外部服务由平台提供；本仓实现其客户端/适配器、契约测试和本地测试替身。MateMind 三语言 SDK 的发布归属需与平台确定，本仓提供版本化协议夹具和互通样例；完整交付仍需验证三语言链路。

## 2. 固定基线与复现要求

以下提交已与本地 checkout HEAD 核对；它们是本计划的兼容基线，不表示实施时自动跟随远端最新分支。

| 仓库 | 固定提交 | 用途 |
|---|---|---|
| agent-core | `4cd9df83855c0504af314655fbd7e2f34a0442fa` | 必需内核：DeepAgent、Workflow、Runner、AgentTeams、A2A |
| agent-runtime | `34ed6e86b99fab9b3f07d9f063efc1692ab365d2` | 平台对接参考；不默认打包进运行时 |
| jiuwenswarm | `f7e7dd5c82d4908276a8524fe94ceda41a8ae354` | 对接与行为参考；不默认引入服务端依赖 |

- Python 初始基线选 3.11；固定内核声明支持 `>=3.11,<3.14`，发布前补齐声明支持版本的安装与核心行为验证。
- M0 生成依赖锁与兼容记录；同时固定传递依赖中的 Git 提交，不能只固定 agent-core 而保留浮动分支依赖。
- CI/发布使用锁定依赖和可构建来源；开发可引用本地 checkout，发布不能依赖开发者的绝对路径。
- 只通过公开组合/适配接口扩展内核。原型若需要上游新增扩展点，先形成明确提案；不以 monkey-patch 或 prompt/extras 伪装执行器接入。
- 每次升级内核单独提交，重新跑接口、路由、团队、恢复和 A2A 契约测试。

## 3. 仓库布局

下列目录是工程布局；M0 已建立工程基础，M2/M3 实现配置、双路径、插件/路由与轨迹，M4 提供本地存储、效果执行器、租约与原生恢复适配。agentworker 已提供单 Agent HTTP 及单 Agent/团队 A2A 入口，team 已实现配置成员协作、权限/MCP 本地链路及组件/worker Leader 审批交接；共享后端及成员工具审批接续已实现，其他恢复位置与真实平台联调仍待完成。采用 `src/` 布局，逻辑包名和职责沿用系统设计。

```text
metaAgent/
├── PLAN.md
├── MetaAgent-架构设计文档.md
├── MetaAgent-系统设计文档.md
├── MetaAgent-design.md
├── review/                        # 已有修订审阅版
├── README.md                      # 安装、最小运行、两种部署方式
├── pyproject.toml
├── uv.lock
├── src/
│   ├── meta_agent/
│   │   ├── spec/                  # MetaAgentSpec、TeamSpec、manifest、CSP 配置
│   │   ├── boot/                  # MetaBootLoader 与包校验
│   │   ├── base_agent/            # MetaBaseAgent、harness_wrap、router
│   │   ├── orchestrator/          # DAGCompiler、组件与结果出口
│   │   ├── registry/              # Skill / FastPath / Team 槽位
│   │   ├── routing/               # when、策略、缓存、自适应与统计
│   │   ├── checkpoint/            # L3 journal、executor、恢复计划与租约
│   │   ├── rails/                 # 观测/关联上下文与快路径桥接
│   │   ├── trace/                 # JSONL、事件与进化打点
│   │   ├── team/                  # provider、成员适配、团队恢复
│   │   └── cli.py
│   ├── meta_agent_adapter/        # model、mcp、ops、agent_gov、memory、skills
│   └── agentworker/               # HTTP、单 Agent/团队 A2A、AgentGov 与管理面
├── examples/
│   ├── minimal_agent/             # 必选配置包 + 一个 skill
│   ├── refund_fastpath/           # 使用测试账本的退款插件
│   ├── http_agent/                # 本机 HTTP 主路径/快路径/fallback/审批恢复
│   └── team_demo/                 # 单成员与 leader + researcher
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contracts/
│   ├── fault_injection/
│   └── e2e/
├── spikes/                        # M1 可运行的架构验证
├── deploy/                        # Dockerfile、开发服务配置、部署样例
├── docs/
│   ├── adr/
│   ├── compatibility/
│   ├── contracts/
│   └── runbooks/
└── .github/workflows/             # 若采用 GitHub；CI 行为不依赖该平台
```

M0 已初始化独立 Git 仓库与 CI 配置，当前开发版本为 `0.1.0.dev0`；尚未创建远端或发布制品。正式版本号规则、许可证、远端与制品仓库在实际发布前确定。

## 4. 阶段、依赖与验收

| 阶段 | 可审阅交付物 | 依赖 | 阶段退出条件 |
|---|---|---|---|
| M0 仓库与依赖 | 包骨架、依赖锁、兼容记录、测试入口、CI | 无 | 干净环境可安装、构建 wheel，运行真实内核导入/最小调用 smoke |
| M1 风险原型 | DAG/Harness、Team provider、恢复与租约三个原型及 ADR | M0 | 每个原型有可复现结果；失败项给出具体阻断范围，不能按文档推断通过 |
| M2 主路径 | MetaAgentSpec、BootLoader、MetaBaseAgent、DeepAgentComp、基础轨迹 | M0；M1 的 DAG/Harness 原型 | 无插件请求、流式、交互/取消经过真实 Workflow + DeepAgent |
| M3 双路径 | manifest、Registry、Router、FastPathOutcomeComp、统一出口 | M2 | 命中/未命中/fallback/终止/控制状态都符合设计；成功快路径不调度 DeepAgent |
| M4 耐久恢复 | operation identity、L3、SideEffectExecutor、lease/fencing、版本保留 | M3；M1 恢复原型 | 故障窗口矩阵通过，所有声明支持的写入面受控，未知效果不会盲重放 |
| M5 CSP 与服务化 | 平台适配器、内部 A2A、AgentGov 注册/心跳、管理面 | M2/M3 与现有 M4；恢复部署集成按 §7 补齐 | 单 Agent 组件/镜像链路通过；本地替身与真实平台验证分别记录 |
| M6 团队正式接入 | provider/runtime、Leader/单成员接线、权限、团队恢复 | M1 Team 原型与 M2/M3；MCP/恢复随对应集成步骤补齐 | GATE-TEAM 全部通过后才开启团队目标及默认单成员团队 |
| M7 完整交付 | 热更新、进化链路、SDK 互通、运维文档、发布候选 | M2–M6 | 系统设计 §11/§12 全量追踪，wheel/镜像及端到端验收通过 |

原型发现阻塞时，可继续不依赖该阻塞的单 Agent 工作；受影响阶段保留未完成状态。团队原型要在 M1 做，不能等到 M6 才第一次验证。排期与人员分配在 M1 得到实际集成成本后估算，本文不把未知工作量写成确定日期。

M0–M7 保留为任务归属与完整验收编号，不要求按编号串行完成全部工作。当前阶段状态以 §0 为准，已交付功能证据见 §7；完整 GATE-TEAM 保持原验收要求，局部通过只标注对应范围。

## 5. 可执行任务清单

任务勾选继续按原设计完整范围保留；各里程碑附带的验证说明是当时快照。当前正常功能状态以 §0、§7 为准，历史说明中的缺口不覆盖后续已交付功能；尚未关闭的完整范围任务仍保持未完成。

### M0：把仓库做成可重复构建的工程

- [x] M0-01 保留现有设计资料，建立独立仓库、包骨架、README、忽略规则；不纳入凭据与上游源码副本。
- [x] M0-02 固定内核和传递依赖，记录 Python/存储/A2A 版本；选择所需 extras 并实际验证导入。
- [x] M0-03 配置格式/静态检查、pytest、异步测试、wheel 构建及干净环境安装；共享一套本地与 CI 命令。
- [x] M0-04 建立可编程模型客户端、测试 MCP 网关/外部服务、可观测测试账本；测试替身位于边界，真实 Workflow/Runner 不被整体 mock 掉。

### M1：先验证三个可能改变设计的接线点

- [ ] M1-01 **GATE-DAG**：全量 MetaAgentSpec 经装配器建立真实 DeepAgent；验证 tools/rails/subagents 物化及 checkpoint/budget/evolution 注入。
- [x] M1-02 同一原型验证 DeepAgentComp、插件子图包装、后置条件边、invoke/缓冲模式下的单一最终输出出口、INPUT_REQUIRED 的 child session 续跑，以及调用取消；token 流和并发消费者仲裁另行验收。
- [x] M1-03 **GATE-TEAM 原型**：provider 的发现/注册、不可变配置引用与 digest、子进程序列化、事件归属及成员实际执行 MetaAgent DAG。
- [ ] M1-04 分别验证 Leader 接线、默认单成员目标、平台 MCP 通道与权限/HITT；逐项记 pass/fail/未运行，不能由 teammate 成功推导其余成功。
- [x] M1-05 **GATE-RECOVERY 原型**：制造“下游已生效、结果未提交”的进程退出；验证同一 operation_id 对账/去重与未知结果暂停，并验证旧 fencing 写入被拒。
- [x] M1-06 输出兼容报告与 ADR；明确哪些 API 可直接复用、哪些代码需新建、哪些能力依赖上游变更。

M1-01 已证明声明物化、SQLite checkpoint 选择、goal 记录创建/恢复及 evolution rails 绑定；M2 已补充当前支持范围的严格外层 spec，但预算计量/停止、非默认 stop_strategy 和完整子代理执行仍未完成。M1-03 的 entry-point 发现使用临时发行元数据，子进程显式 bootstrap；正式 provider wheel 与团队冷恢复留在 M6。M1-04 只证明 Leader 的公开 runtime 构造接缝和 provider 用户输入，默认单成员生命周期、平台网关/权限仍未运行。M1-05 为本机双 SQLite + 注入时钟，不等于 M4 生产恢复或完整 GATE-LEASE。

### M2：先跑通最小主路径

- [x] M2-01 落地配置校验、必选 skills+agent 包、路径契约与启动失败语义。
- [x] M2-02 建立 MetaBaseAgent/harness_wrap，复用 DeepAgent 的 TaskLoop/ReAct；无插件时只编译 `Start → DeepAgentComp → End`。
- [x] M2-03 支持 invoke、stream、INPUT_REQUIRED、follow-up 与取消；建立 product/agent/session/request/execution 的身份映射。
- [x] M2-04 从首个 demo 接入 JSONL trace、关联 ID、错误分类与模型调用计数；定义 operation journal/lease 接口，供后续两条路径共用。
- [x] M2-05 完成 minimal_agent 的无外部模型 smoke 和可配置真实模型集成样例。

此阶段用只读或可回滚测试工具验证计算链路；生产外部写入自动恢复能力须等 M4 验收。

M2 的启动预检覆盖配置和 provider/rail 物化，不代表外部模型可达性或异步 rail 首次初始化已验证。真实模型模板已提供，未执行真实模型请求。仅支持一个 child interrupt；多个同时中断、子代理及未来功能开关明确拒绝。JSONL 的调用/token 计数不执行预算；SQLite 后端不提供对象重建/进程重启恢复。技能 digest 是加载时快照，运行期间应保持业务包不变。

### M3：再加快路径与后置 fallback

- [x] M3-01 实现 MetaAgent 自有 manifest、Workflow 构建校验、防嵌套 DeepAgentComp 和插件版本标识。
- [x] M3-02 实现 Skill 元数据、规则/embedding、声明式 when 的路由策略；可选 LLM 分类；缓存带上下文、权限与配置/插件版本。
- [x] M3-03 插件在 FastPathOutcomeComp 内运行，普通错误正常返回后再决定 fallback；保留带来源的中间上下文和已完成操作身份。
- [x] M3-04 精确实现白名单终止、禁用 fallback、INPUT_REQUIRED/取消/失租/存储失败/副作用未决的分离处理。
- [x] M3-05 快路径输出在成功或 INPUT_REQUIRED 确认后发布；失败缓冲内容不形成第二个最终答案；统一主/快路径输出出口。
- [x] M3-06 实现 RouteStats、阈值调整、`validate/draw` CLI；refund demo 使用测试账本，验证快路径成功时 DeepAgent 调度次数为零。

M3 的 embedding/classifier 由宿主显式注册，当前仅以可编程边界验证；权限 context 由可信调用方提供。插件必须返回可审查的 PluginWorkflow；不透明 Loop、重试、stream edges 和多个同时交互暂时拒绝。effects 必须为空，completed_operations 仅作为来源明确的上下文，不构成耐久防重保证。版本快照固定到运行时，热更新与持久化 pin 未在本期开放。

### M4：把恢复做成有证据的能力

- [x] M4-01 定义每个逻辑操作的 operation_id；同操作重试复用，不同操作即使参数相同也必须有不同 ID；同 ID 参数漂移明确拒绝（本地显式 Effect API）。
- [x] M4-02 L3 journal 支持 prepared/completed/unknown，prepare 与 result 返回前等待耐久确认；轨迹日志不能承担该职责（SQLite WAL/FULL，本机进程终止窗口验收）。
- [ ] M4-03 将主路径、子代理、快路径工具/HTTP/RPC、嵌套 workflow、skill 外部写入统一纳入 SideEffectExecutor；未接入写入面不能标记可自动恢复。
- [ ] M4-04 实现 session 租约获取、续约、释放与 fencing；存储和可控调用边界拒绝旧 owner。外部系统无法执行 fencing 时，仍按幂等/去重/查询契约处理在途效果。
- [ ] M4-05 恢复 L1/L2 的最近耐久提交和原路由决策；保留原 graph/plugin/digest/child session。实现持久化版本 pin 和卸载拒绝规则。
- [ ] M4-06 完成 prepare 前后、外部生效后、result 提交前后、超 TTL、双实例竞争、续约断连、旧 owner 恢复及未知结果的故障注入。
- [ ] M4-07 验证选定共享存储的耐久/保留期配置；单机本地存储结果与跨实例漂移结果分开标记，输出恢复 runbook。

M4 首批成果：`SQLiteRecoveryStore` 实现原子 lease/journal 写入、持久化逻辑 key→operation_id、原参数存储与枚举；`SideEffectExecutor` 仅按查询/下游去重契约恢复，未知结果阻止新操作。`LeaseGuard` 实测长于 TTL 的续约、竞争、断连取消和旧 owner 拒绝。`RecoverySnapshot` 与 artifact store 保留原路由/版本字节引用，未退休 pin 拒绝删除。原生 Workflow、嵌套子图和 DeepAgent 工具可通过显式适配器使用同一执行器；测试与样例使用独立本地账本。

M4 第二批已交付 LocalRecovery：通过公开 Checkpointer/Store 接口将原生 L1/L2 写入接到 SQLite 原子 fencing；MetaBaseAgent 自动绑定自身 execution、耐久 admission/答案/终态，显式 resume 恢复原输入、路由、插件字节及 child session。L1 graph/state/updates 一起提交，L2 与 child outcome 一起提交；旧答案不会回答后续新问题。关闭保留状态，续约失联取消整个运行。真实进程终止、原生审批与保留 v1 插件恢复已有验证。[运行时记录](docs/compatibility/m4-runtime-recovery-validation.md) · [ADR-0005](docs/adr/0005-local-runtime-recovery.md)。

M4 第三批实现快路径写入与 fallback：EffectBinding 把宿主能力名、适配器和逻辑 key 绑定在一起；manifest 声明 effects，嵌套插件节点和 fallback 工具共用原操作身份。路径切换前检查 journal，未决效果禁止 fallback；已完成操作/回执由 journal 提供。加入退款审批、保留插件版本、真实进程终止、fallback 重复工具调用和未知效果暂停用例。此项属于 M4-03/05/06 的本机增量，不勾选其全部范围。[本批记录](docs/compatibility/m4-fastpath-recovery-validation.md) · [ADR-0006](docs/adr/0006-fastpath-effect-bindings.md)。

M4 第四批核对 B0–B8 提交/写入边界，列明已保存状态、允许重做和禁止行为。增加取消、续约断连、接管后的旧 owner 提交与冷恢复矩阵；修复原 workflow 启动前 pending reconciliation 未整体纳入租约取消作用域的问题。更细成功步骤/Agent 迭代 checkpoint 已写本地公开接口提案，尚未提交上游或实现。[支持清单](docs/compatibility/m4-supported-boundaries.md) · [验证记录](docs/compatibility/m4-boundary-validation.md) · [提案](docs/proposals/0001-native-checkpoint-boundaries.md)。

以下拆分用于区分已验收的本机能力和父任务剩余范围；不改变 M4-03 至 M4-07 的整体状态。

| 父任务 | 已交付的本机范围 | 尚待验收的范围 |
|---|---|---|
| M4-03 写入面 | 显式 Effect API、主路径 BoundEffectTool、整 Agent 快路径/嵌套子图及 fallback 的共享绑定与恢复 | HTTP/RPC、skill 外部写入、子代理等其余写入面 |
| M4-04 租约与 fencing | SQLite 原子 fencing 覆盖 journal、原生 checkpoint、admission 和终态；续约断连取消原生运行及 pending reconciliation，旧 owner 写入被拒 | 扩展写入面与共享存储上的相同契约，包括跨主机竞争和在途效果处理 |
| M4-05 原状态/版本恢复 | 已提交的 L1/L2、原输入/路由/插件字节/child session、审批和版本 pin；提交边界已列清，公开扩展提案已写 | 更细提交边界的上游扩展验收、完整支持面和跨实例版本漂移；未提交计算仍可能重做 |
| M4-06 故障矩阵 | 本机真实进程终止、效果窗口、审批、TTL/竞争/断连、未知结果暂停、checkpoint 损坏；快慢路径提交前后及 reconciliation 的取消/续约/旧 owner 矩阵 | 对新增受控写入面与共享存储逐项复测，完成跨主机故障矩阵 |
| M4-07 存储与运维 | 本地 SQLite 配置、schema 迁移与[运行时恢复 runbook](docs/runbooks/local-runtime-recovery.md) | 选定共享存储，验证耐久/备份/保留期、故障切换与跨主机漂移 |

M4-03/04/05/06/07 保持未勾选：本机支持范围已扩展，但全部写入面、任意中间步 checkpoint、跨主机共享存储/漂移和完整故障矩阵尚未验收。原生内核仅在错误/交互边界保存 graph position；未提交计算可能重做。主 spec 的通用 effects/分布式/子代理开关继续拒绝；插件 manifest 的 effects 仅随显式 LocalRecovery 宿主绑定开放。stream 缓冲终态，活动 follow_up 未开放。

### M5：打通平台与两种部署形态

本机 HTTP worker 与单 Agent A2A/AgentGov 本地契约增量已交付，具备消息/SSE/审批续跑/取消/查询、注册生命周期和只读管理接口，见 §7。下列任务还包含团队、完整恢复/管理、镜像与真实平台验收，因此仍保留未完成状态。

- [ ] M5-01 对接 InferSchedule、McpGateway、Ops；验证超时/鉴权/限流/故障映射。启用 Memory/SkillsRuntime 时也须有契约测试。
- [ ] M5-02 实现 worker 内部 A2A listener、消息/task/context/session 映射、流、取消和交互续跑；限制网络入口并验证 AgentGov 身份。
- [ ] M5-03 实现加载→内部 listener 自检→就绪→AgentGov 注册/心跳→可路由，以及摘流/关闭；注册失败标记 degraded。
- [ ] M5-04 管理面提供健康、DAG、插件、统计和轨迹查询；写接口与实际能力同步开放并鉴权。
- [ ] M5-05 同一业务包通过本地 Python 调用和镜像链路；断连后按原请求身份查询/恢复，网关不盲重放未知写入。
- [ ] M5-06 记录真实平台的端点契约和版本；测试替身通过只算开发集成通过，真实平台验收保留单独状态。

### M6：通过门禁后启用团队

- [ ] M6-01 将 M1 已证明的 provider/runtime 接线产品化；入口传 TeamAgentSpec 或已激活 team_name，遵守 Runner 生命周期。
- [ ] M6-02 验证成员 DAG、模型配置、请求/session 归属、单事件消费者、权限/HITT 与 MCP 网关桥接。
- [ ] M6-03 独立验收 Leader、单成员默认团队和 leader+researcher；Leader 模型开销与成员快路径收益分别计量。
- [ ] M6-04 验证 spawn、重启、warm/cold recovery、团队共享存储与固定配置版本；经 worker A2A 链路复测团队目标。
- [ ] M6-05 GATE-TEAM 未通过时启动给出明确的适配不可用错误；不得静默切成不执行 MetaAgent DAG 的原生团队。

本机增量已实现 M6-01/03 的配置包装配、正式 provider/runtime、单 Leader 与双成员 DAG、调用计量，以及 M6-02 的单活动请求/session 归属。使用原生团队消息与事件消费，Leader 审批/fallback 和取消已验证。仅开放已配置成员；本地绑定过期明确拒绝启动，不静默使用原生 DeepAgent 替代成员。权限/HITT、平台 MCP、团队恢复、默认生产入口尚未完成，因此父任务保持未勾选。

### M7：补齐完整设计范围并形成发布候选

- [x] M7-01 本机热更新构建不可变插件/索引快照后原子切换；新 execution 用 v2，在途/暂停/LocalRecovery 恢复仍用 v1；运行引用及耐久恢复 pin 全部解除后允许卸载。共享存储/团队整体更新归后续 M4/M6 集成。
- [x] M7-02 接入 skill 进化信号、审批/回滚/固化与事件观测；Skill 转 workflow 经宿主审批，执行显式绑定的工具，复用原插件激活/回滚。恢复组合单列后续验收。
- [ ] M7-03 完成可选适配能力、管理面生命周期接口、配置/业务包开发规范和部署 runbook。
- [ ] M7-04 对接平台的 MateMind Python/C++/Rust 最小调用、流式和错误语义样例；记录 SDK 与 A2A 协议版本。
- [ ] M7-05 测量快路径/主路径时延、token 和模型调用数；按固定 workload 验证设计中快路径 P95 ≤ 2s 等目标，记录环境与样本，不把目标写成实测结果。
- [ ] M7-06 系统设计 §11 测试矩阵、§12 DoD 逐项关联用例与证据；覆盖率按新增模块 ≥85% 检查，同时保留关键行为与故障验收。
- [ ] M7-07 从干净环境构建/安装 wheel 和启动镜像，验证默认包、双模式 demo、迁移/回滚与重启；准备版本说明与制品清单。

## 6. 测试证据与完成判定

| 门禁 | 必须看到的证据 | 不能替代的证据 |
|---|---|---|
| GATE-DAG | 真实 Workflow 调度轨迹、配置物化、输出/控制状态断言 | Python 片段能解析、字段名存在 |
| GATE-ROUTING | 命中/未命中/fallback/终止及控制状态矩阵；成功快路径不调用 DeepAgent | Mermaid 图看起来正确 |
| GATE-RECOVERY | 真实进程终止 + 下游测试账本 + 重启/漂移结果；不确定效果暂停 | 只 mock 一个异常或仅写内存日志 |
| GATE-LEASE | 长于 TTL 的运行、并发竞争、失租取消、旧 fencing 拒绝 | 只有进程内锁或 key 的 TTL |
| GATE-TEAM | provider→成员 DAG 的实际调用、Leader/单成员、权限/MCP/恢复证据 | 配置能解析或原生团队能回答 |
| GATE-A2A | AgentGov→内部 listener→Runner，鉴权、流、取消、交互与断连处理 | 本地调用 Runner 成功 |
| GATE-RELEASE | wheel/镜像、双模式、真实平台和 SDK 互通、全量 DoD | 只有单 Agent 开发 demo |

里程碑验收记录内核提交、MetaAgent 提交、配置/插件 digest、环境/存储配置、执行命令、测试结果和必要轨迹；日常功能迭代按 §7 更新 PLAN/README 并运行相关检查。未运行、被外部环境阻塞与通过必须分别记录；只有实际通过的任务才勾选。

## 7. 交付记录与基线结项

本节保留各批次当时的实现与验收记录；历史段落中的“尚未完成”“下一步”对应当时快照，当前状态以 §0 结项表及本节末尾为准。实施过程按用户要求优先复用 OpenJiuwen、完成核心功能，后置扩展 hardening。

### 已实现：最小 worker + 一个贯通样例

| 交付 | 完成判据 |
|---|---|
| 薄 HTTP worker | `agentworker.server` 与 `meta-agent-worker` / `python -m agentworker`；默认监听 127.0.0.1，health/invoke/resume 直接使用现有 MetaBaseAgent 和 LocalRecovery |
| 模型配置 | `examples/http_agent/run.py --real-model` 复用原生 OpenAI-compatible 客户端，从环境变量加载端点/模型/key；SiliconFlow 使用说明已提供，真实调用待配置凭据 |
| 贯通样例 | `examples/http_agent/run.py` 同包跑通主路径、快路径、fallback、审批/恢复；`--smoke` 使用本机 HTTP，并重建 worker 验证已存响应和审批恢复 |

使用与接口见 [HTTP MVP README](examples/http_agent/README.md)。新增验收覆盖三路 HTTP 结果、重复请求、审批/重建、输入校验、并发冲突、断连取消与关闭；不新增恢复框架或设计报告。

本批验证：351 项测试、86 个 Python 文件格式检查、38 个源码模块 mypy、构建通过；独立 wheel 安装后 CLI 和真实本机 HTTP smoke 通过。日志保存在 `.artifacts/http-worker-check.log`、`http-worker-pytest.xml`、`http-worker-wheel.log`。未调用真实模型；本批没有重跑独立安装中的全部旧样例，旧功能已由上述全量回归覆盖。

### 原实施顺序（历史记录）

下表保留早期分批安排及当时状态；后续完成情况记录在各交付批次，本表不作为下一轮默认任务清单。

| 顺序 | 架构能力与任务归属 | 最小可运行交付与验收 |
|---|---|---|
| 1 · 本机增量已完成 | MetaAgentTeam（M6-01/03/05） | 正式 MetaBaseAgent provider/runtime、单 Leader 与 leader+researcher、成员零模型快路径、消息回复与汇总、Leader 交互和取消关闭；完整团队门禁继续按下列步骤集成 |
| 2 · 本地增量已完成 | Harness 配置与 CSP/MCP（M1-01、M5-01、M6-02） | 原生 goal 预算、同步子代理、InferSchedule/MCP 本地契约、团队工具权限/审批和 passive human 消息往返；剩余范围见下文 |
| 3 · 本地单 Agent/团队增量已完成 | 服务化与双部署（M5-02～06、M7-03） | A2A 消息/SSE/任务查询/审批/取消、团队审批重启恢复、AgentGov 注册/心跳/下线、服务鉴权、同包组件/worker、只读管理已通过本地链路；本机 Docker 的普通快路径与真实模型 Team 委派已通过；完整团队恢复与真实平台待验收 |
| 4 · 本机增量已完成 | 插件热更新（M7-01、M4-05） | 加载/激活/回滚/停用/卸载、原子快照切换、同会话新 execution 更新、暂停/在途保留原版本；worker 保存激活目录，LocalRecovery 复用现有 artifact/pin |
| 5 · 本地增量已完成 | 观测、进化与可选适配（M5-01、M7-02/03） | 元数据 JSONL、Ops、原生 OTLP 与宿主 Skill 提议/审批/回滚；Memory/SkillsRuntime 可选工具接入与写入→重建/新会话读取→远程 Skill 本地样例。自动进化/固化、真实平台与恢复组合仍未完成 |
| 6 · 团队审批交接增量已完成 | 架构内恢复集成（M4-03～07、M6-04） | Leader 审批暂停/跨进程重建、成员稳定身份与协调 journal 已贯通；继续推进共享后端上的实例接管、未决成员工作与版本恢复。核实迭代/步骤 checkpoint 缺口，通过公开接口实现或明确上游阻断 |
| 7 | 整体贯通（M7-04～07） | 串起业务配置→团队/双路径→平台工具→A2A→部署与恢复，跑一次全量回归/构建和基本性能测量；按平台 SDK 的实际可用情况完成三语言互通样例，不在本仓重建 SDK |

第 1 步使用原生进程内团队协调工具；业务平台工具仍须经第 2 步的 MCP 网关接入。完整任务保留未完成状态，完成相应行为验证后逐项更新；本地服务替身通过不代表真实平台已接通。

### 本批交付：本机 MetaAgentTeam

- [x] 增加本机 MetaAgentTeamSpec、正式 provider/runtime 与启动装配，复用 `spikes/team_adapter.py` 已验证的公开接缝，不自建团队调度内核。配置绑定只在宿主内存中，原生团队持久化配置不包含模型 key。
- [x] 提供 `examples/team_demo`：单 Leader 完整一轮与关闭，以及 leader + researcher 的消息委派/结果汇总和成员快路径；原生协调工具限定为已配置成员及消息，角色/roster 通知不额外调度模型。
- [x] 覆盖单活动请求/session 归属、单 Leader 继续对话、审批/fallback 与取消关闭；复用原生单事件消费者。权限/MCP 与团队恢复明确保留到后续步骤，成员交互转发尚未完成。

使用说明与 SiliconFlow 命令见 [团队样例](examples/team_demo/README.md)。真实模型 key 从仓库父目录只读加载，不写入配置或 Git。业务工具使用最小示例辅助验证架构，无需先确定实际业务 API。真实平台契约未确认的部分以明确的本地契约验证，待联调确认后完成平台验收。

本批验证：全量 356 项测试通过；最终工具接线及 session/并发检查的 5 项团队测试再次通过；Ruff、93 个文件格式检查、42 个源码模块 mypy 和 sdist/wheel 构建通过。SiliconFlow `Qwen/Qwen3-30B-A3B-Instruct-2507` 实际双成员运行成功：Leader 2 轮、5 次模型调用；researcher 1 轮、0 次 DeepAgent 调度/模型调用。该结果验证团队主路径与成员快路径；真实模型 fallback、性能和平台联调仍未验收。日志：`.artifacts/team-check.log`、`team-focused.log`、`team-live.log`；成员结果：`.artifacts/team-demo-live/result.json`。

独立 wheel 已在现有隔离依赖环境重新安装，验证包导入位置、HarnessProvider entry point 和双成员样例通过，见 `.artifacts/team-wheel.log`。本批不重复运行该环境中的全部旧样例；旧功能由上述全量回归覆盖。

### 本批交付：原生 goal 预算与同步子代理

- [x] `budget.enabled` 接到原生 GoalManager/TaskCompletionRail/GoalEvaluator，支持 hybrid、max_attempts、token_budget；在尝试边界停止继续，返回部分回答与明确的预算错误。新请求重置预算，成功快路径不启动 goal。
- [x] 配置式同步 `task_tool` 子代理实际执行，保留独立模型/工具/rails/skills/workspace；子代理模型回调及报告 usage 计入父请求和父 GoalRecord。未开放异步/持久子代理、自动 general-purpose 或自定义工厂。
- [x] 代表性行为覆盖尝试/token 停止、目标完成及新请求、流式终态、快路径/fallback、子代理委派/计量与取消；复用原生调度，不新增预算调度框架。

完整 GATE-DAG 继续保持未通过：固定内核只有默认 hybrid 的公开接线；transcript assessor 绕过 model rail 与 GoalRecord usage，尚不构成完整计费上限。目标停止在尝试边界判断，单次尝试可越过 token 阈值；已确认完成优先返回成功。原生 goal 的交互恢复尚未贯通，遇到交互明确停止；现有不带预算的审批流程仍可使用。预算/子代理的 LocalRecovery 集成及异步子代理留在后续架构步骤。运行与限制见 [Harness 样例](examples/harness_demo/README.md)。

本批验证：全量 363 项测试通过；Ruff、97 个 Python 文件格式检查、44 个源码模块 mypy 和 sdist/wheel 构建通过。三个脚本模型样例（预算停止、同步委派、目标完成）均通过；在现有隔离依赖环境重新安装 wheel，确认导入位置和包源码一致，预算停止样例通过。日志：`.artifacts/harness-check.log`、`harness-goal.log`、`harness-wheel.log`。

SiliconFlow `Qwen/Qwen3-30B-A3B-Instruct-2507` 实际完成一次 researcher 委派与目标评估，正确返回快路径、DeepAgent 主路径和普通失败 fallback 三条执行路径：1 次子代理执行、1 次 goal 尝试，rail 记录 4 次模型调用及 9525 tokens。这些数字不包含上文说明的 assessor 开销，不作为完整账单。日志及结果：`.artifacts/harness-live.log`、`.artifacts/harness-live/result.json`；父目录 key 只读加载，源码及本批输出未包含该凭据。

### 本批交付：CSP/MCP 与团队权限

- [x] InferSchedule 适配复用原生 OpenAI-compatible chat/SSE、鉴权与 usage，映射认证/限流/超时/5xx 错误；不新增重试/熔断框架。
- [x] MCP 声明统一改写到平台 Streamable HTTP 网关，按逻辑 server 名路由；显式注册原生 Runner 资源，工具元数据轨迹带 gateway 标识。连接由同一 task 开关，满足原生 MCP 客户端生命周期要求。
- [x] 原生 PermissionInterruptRail / TeamPermissionRail 执行 allow/ask/deny；Leader 的 approve_tool 通过原始 tool-call ID 恢复成员 DAG，批准执行一次、拒绝不执行。
- [x] 预配置 passive human 成员通过原生 HITT inbox 接收/发送消息；宿主回调接收团队回信。真人身份认证归宿主，不由模型或消息正文决定。

运行见 [平台样例](examples/platform_demo/README.md)。本地 `X-Meta-Mcp-Server` 路由头是待平台确认的契约；不宣称已连接真实 CSP。Ops、真实平台联调、完整 HITT avatar/任务控制、子代理 MCP/权限转发、MCP 耐久效果与团队恢复尚未完成，M5-01/M6-02 与完整 GATE-TEAM 保持未勾选。预算的 assessor 计量/目标交互限制继续按对应运行时集成推进。

本批验证：新增 13 项平台集成用例通过。全量 376 项首轮为 375 通过、1 项旧 TraceRail 回调集合断言需更新；加入新增的 MCP 工具回调后，16 项轨迹用例全部通过，生产代码未再修改，376 项用例已在全量与定向运行中完成验证。未重复整套进程故障测试。Ruff、104 个 Python 文件格式检查、47 个源码模块 mypy、sdist/wheel 构建通过。记录：`.artifacts/platform-check.log`、`platform-pytest.xml`、`platform-focused.log`、`platform-trace.log`、`platform-build.log`。

独立依赖环境重新安装 wheel，确认导入来自 site-packages、wheel 与 47 个源码文件一致，完整批准样例通过：9 次本地推理请求、1 次网关工具执行；拒绝样例为 9 次推理请求、0 次工具执行。二者连接关闭无 cancel-scope 错误。日志：`.artifacts/platform-wheel.log`、`platform-deny.log`；结果位于 `.artifacts/platform-wheel-demo/` 和 `.artifacts/platform-demo/` 各运行目录。此验证使用本地脚本服务，真实 CSP 联调仍待接入。

### 本批交付：A2A / AgentGov 与 worker 部署入口

- [x] 固定 A2A SDK 1.0.0，复用原生 JSON-RPC routes、SQLite DatabaseTaskStore、TaskUpdater 和 OpenJiuwen Card/Part 转换；消息、流式增量/终态、查询、审批答案和取消接入 MetaBaseAgent DAG。SDK 默认 handler 暂停后没有关闭接口，选择其公开 LegacyRequestHandler，避免改私有状态。
- [x] context/message/task 身份和结果保存在 A2A store；中断使用原 task/context 与新 messageId。拒绝换 context、重复答案、不同包/恢复模式续跑；不把消息 metadata 当可信权限/路由 context。取消实际停止模型；断连后继续保存原任务，通过查询获取结果，重复请求不重跑模型。
- [x] AgentGov 本地契约：callback listener 自检后注册、周期心跳、失败 degraded/重新注册、CLI 关闭前摘流。worker/admin/card 统一 Bearer 服务身份校验；仅最小存活探针公开。
- [x] 提供健康/DAG/插件/路由统计/轨迹文件列表只读接口；组件与 A2A worker 使用相同业务包。原 HTTP CLI 保留；增加 `--protocol a2a` 与 opt-in `--durable`。
- [x] 提供 Dockerfile、白名单 .dockerignore、运行时配置/卷/凭据说明。源码构建入口已准备；Docker engine 未运行，镜像构建与运行未验收。

运行见 [A2A worker 样例](examples/a2a_worker/README.md)。默认 task store 持久化不等于 Agent 运行时恢复；`--durable` 已验收审批跨重建续跑，沿用 LocalRecovery 的结果缓冲及支持边界。未完成：处理中崩溃的 A2A 自动接管/未知效果恢复、团队目标、共享存储/跨主机漂移、管理写操作、真实 AgentGov 和镜像执行。M5-02～06、M6-04 与完整 GATE-A2A 保持未勾选。

本批验证：全量 382 项测试通过；最终 6 项 A2A 定向测试再次通过。Ruff、110 个 Python 文件格式检查、50 个源码模块 mypy、sdist/wheel 构建通过。代表性验收覆盖三条路由、SSE 增量、审批/任务查询跨重建、原始 ID 校验、取消、真实断连后查询/防重放、AgentGov 转发/心跳/故障后重注册与下线。日志：`.artifacts/a2a-check.log`、`a2a-pytest.xml`、`a2a-final-focused.log`。

在已有隔离依赖环境重新安装 wheel，确认导入来自 site-packages，wheel 与 50 个源码文件一致；同包组件→worker、AgentGov 转发、审批、心跳和下线样例通过。记录：`.artifacts/a2a-wheel.log`、`a2a-wheel-import.log`；结果：`.artifacts/a2a-wheel-demo/<run>/result.json`。未调用真实模型/平台，也未重新运行隔离环境中的全部旧样例；旧功能由上述全量回归覆盖。Docker CLI 存在，但 Linux engine pipe 不存在，镜像构建/运行保留未验收。

### 本批交付：插件热更新

- [x] 复用 PluginPackage、MetaRegistry 和 FastPathRouter，加载时固定字节并预检；激活时构建完整 registry/index 后一次替换当前快照。拒绝同名同版本不同字节；构建或目录保存失败保留原快照。
- [x] execution admission 选定快照，运行中/暂停/fallback 保留旧版本；已完成会话的新一轮采用新版本。流式路径共用引用规则。停用全部插件后退化为主路径，可再次激活。
- [x] 单 Agent worker 加入鉴权的加载、激活/显式回滚、停用与卸载 API；GET 返回实际加载版本/active/live_references，DAG 和路由统计对应当前快照。
- [x] worker 的 `plugins.json` 保存插件字节及激活选择，重启恢复；组件可显式指定同类目录文件。LocalRecovery 继续使用已有 artifact/pin 保留原 graph；没有新建恢复 journal。活动版本、有运行引用或耐久 pin 的版本不能卸载，保留期由既有 retire_pins API 显式结束。

运行见[插件热更新样例](examples/plugin_updates/README.md)。本机功能关闭 M7-01；M4-05 的共享存储/跨主机范围、M6 团队恢复与更新仍未完成。每次激活重新建立当前路由缓存、统计窗口与阈值状态；旧快照统计不合并到新快照。目录属于一个 worker/业务包，暂不支持多进程共享修改、Git/文件上传 watcher、整个业务包 reload 或强制绕过保留期卸载。插件写入口处理可信宿主代码，复用现有服务凭据，不向普通用户开放。

2026-10-22 验证：新增 6 个集成测试覆盖新旧 execution、流式审批、在途 fallback、失败保留原快照、LocalRecovery 跨重启及鉴权管理 API。全量 `scripts/check.py --build` 通过：388 tests passed，Ruff/113 文件格式检查、Mypy/51 个源码模块和 sdist/wheel 构建全部通过。日志：`.artifacts/hotupdate-check.log`，JUnit：`.artifacts/hotupdate-pytest.xml`。

在已有隔离依赖环境重新安装 wheel，确认 lifecycle 导入来自 site-packages，wheel 与 51 个源码文件一致；热更新样例完成 v2 激活、重启后 v1 审批、回滚及解除保留 pin 后卸载。记录：`.artifacts/hotupdate-wheel.log`、`hotupdate-wheel-import.log`；结果：`.artifacts/hotupdate-wheel-demo/433073768cbf4011ba576fd8e24cbb34/result.json`。本批未调用真实模型/平台；隔离环境仅运行新增样例，其余功能由上述全量回归覆盖。

### 本批交付：元数据观测与 Ops 本地契约

- [x] JSONL v2 保留原 event/关联字段，加入 category、稳定 execution 轨迹 ID 和本次执行耗时；本地/MCP/同步子代理工具复用原生 Rail 回调，插件与宿主生命周期补齐事件。
- [x] trace.rollout 默认 UTC daily，可显式 none。按 runtime 隔离文件、跨日重开、sequence 连续；复用同步 append/flush，写失败计数，不引入异步缓冲或观测队列。
- [x] 流式原生 TraceSchema 消费只取 trace/invoke/parent/loop/component/status 元数据，内部帧不转发为用户 token。正文、工具参数/结果、异常消息和凭据不进入 MetaAgent JSONL 或 Ops。
- [x] csp.ops 启用 boot/周期 metrics/trace 错误 alerts；关闭时最后上报并释放后台任务/客户端。HTTP 本地契约有 Bearer 身份、超时和可见失败计数，服务故障不改变 Agent 结果。
- [x] agent.observability() 与鉴权 `/admin/stats/observability` 暴露同一快照；health 附带 Ops 状态。事件/请求/usage 按 runtime 累计，路由窗口继续遵守热更新重置语义。
- [x] 新增默认字段不改变原配置摘要；旧格式插件目录及 LocalRecovery 暂停状态重开后，原 v1 审批续跑、新请求保持已激活的 v2。显式配置变更继续执行原一致性检查。

运行见[观测样例](examples/observability/README.md)。这一批不是完整 OTEL/进化交付：原生 TrajectorySpanProcessor/FileTrajectoryStore 归档、进化事件和真实 Ops 平台仍待集成；M7-02/03 及相关平台父任务保持未勾选。当前记录不承担恢复 journal 或平台计费的语义。

2026-10-22 验证：全量采集的 391 项测试通过，Ruff、116 个 Python 文件格式检查、Mypy/52 个源码模块、sdist/wheel 构建通过。随后补充的旧配置摘要兼容调整由最终 52 项定向测试验证，包含新增的旧目录/暂停恢复兼容用例及受影响的 LocalRecovery/热更新路径；全部通过。轮转失败后重试、Ops 503 后恢复、写入告警、元数据脱敏、原生 TRACE/工具回调和管理面鉴权均有实际用例。日志：`.artifacts/observability-check.log`、`observability-final-focused.log`；JUnit：`.artifacts/observability-pytest.xml`。

最终 wheel 在已有隔离依赖环境重新安装，确认 Ops 导入来自 site-packages，制品与 52 个源码文件一致；本地观测样例通过，两次请求/两次模型调用/一次工具调用、五类事件及关闭上报均被确认。记录：`.artifacts/observability-wheel-final.log`、`observability-wheel-import.log`；结果：`.artifacts/observability-wheel-final-demo/56fe84ffad6d4064a1616a121c9c0edb/result.json`。未调用真实模型或 Ops 平台；此次隔离环境只运行新增样例。

### 本批交付：原生轨迹与宿主 Skill 进化

- [x] `trace.trajectories` 显式启用原生 run span、AgentObservabilityRail、共享 TrajectorySpanProcessor 与 TrajectoryRail/FileTrajectoryStore；OTLP 按 runtime/UTC 日期归档，关联 MetaAgent execution，支持 invoke、stream 和暂停续跑增量。
- [x] `evolution.enabled` 开启宿主 user_intent 信号→原生优化器提案→待审→批准/拒绝。使用当前 CSP/model 配置及真实轨迹投影证据，不重复建立审批状态机、不向业务模型挂载治理写工具。
- [x] 复用原生 EvolutionArchiveService 在审批前保存配对版本；批准经验由 SkillUseRail 下一次调用读取。部分写入保留待审尾部，重试仍返回审批前回滚版本；重启后已批准经验/归档可读取，回滚还原原生文件。
- [x] evolution 元数据事件进入原 JSONL；原生含正文 OTLP 独立保存。归档写失败可见且不改变业务输出。多 Agent 共用原生观测生命周期，各自保存执行归档；默认配置摘要继续兼容旧目录/恢复状态。

运行见[Skill 进化样例](examples/skill_evolution/README.md)。本批范围为单进程独占可写 Skill 副本、显式宿主触发/审批，待审提案不跨重启保存。运行中/暂停请求阻止 Skill 修改；evolution+LocalRecovery 显式拒绝，等待 Skill 版本恢复集成。自动信号发现、受限 reviewer 子代理、`/evolve*` 对话命令、团队进化、管理写入口及 Skill 固化为 workflow 保留未完成；M7-02/03 继续未勾选。

2026-10-22 验证：全量 `scripts/check.py --build` 通过，397 tests passed（404.18s），Ruff、120 文件格式检查、Mypy/54 个源码模块和 sdist/wheel 构建通过。新增 5 个集成测试覆盖真实模型/工具轨迹证据、审批前不生效/审批后上下文更新、拒绝/回滚、多 Agent 流式隔离与观测重开、暂停续跑、归档失败不改变业务结果、部分写入重试及重启后经验/配对版本读取。旧配置摘要兼容用例继续通过。日志：`.artifacts/evolution-check.log`；JUnit：`.artifacts/evolution-pytest.xml`。

独立样例和隔离 wheel 样例均通过；隔离环境按更新的 uv.lock 加入六个 OTEL 包，其他依赖版本及上游提交未变化。确认导入来自 site-packages，wheel 与 54 个源码文件一致；`uv pip check` 通过。日志：`.artifacts/evolution-source-demo.log`、`evolution-wheel.log`、`evolution-wheel-import.log`；wheel 结果：`.artifacts/evolution-wheel-demo/13768a578b4e49ec97f3048cf00926a5/result.json`。本批未调用真实模型或平台，隔离环境只运行新增样例。脚本模型缺少 provider context-window commit 事件，原生投影回退到记录的提示词/回答，并把 missing_context_window 返回给审阅者；没有宣称完整无缺口采集。

### 本批交付：Memory / SkillsRuntime 可选适配

- [x] `csp.memory_service` / `csp.skills_runtime` 可独立配置；通过原生 LocalFunction 装入主 Agent，复用已有权限审批、流式与工具观测，客户端由 runtime 关闭。默认继续使用原生上下文及本地 SkillUseRail。
- [x] 记忆显式读/写，写入等待确认；scope/user 来自可信启动配置，session/request/execution 来自当前执行，模型和路由 context 不覆盖。存储/提取/保留由服务负责，不另建数据库或自动对话同步。
- [x] 远程 Skill resolve/execute 携带宿主配置的名称和版本，返回值检查版本；本地插件快路径、版本快照和进化流程继续保持自己的归属。没有下载执行远程代码。
- [x] 本地服务样例贯通写入→Agent 关闭/重建→新会话读取→远程 Skill→流式输出；错误、用户隔离和原生审批有代表性用例。新增默认字段不改变旧插件目录/LocalRecovery 配置摘要。

运行见 [Memory / SkillsRuntime 样例](examples/memory_skills/README.md)。这是显式工具接入的首个可用增量，未把整个 native memory backend / SkillSlot 换为平台代理。自动记忆注入/提取、远程 Skill 进化/插件化、子代理传播与真实平台联调未完成。RPC 尚未接入 SideEffectExecutor，LocalRecovery 组合显式拒绝；超时/取消不声称远端未提交，不引入重试队列。M5-01 与完整 M7 父任务继续未勾选。

2026-10-22 验证：全量 `scripts/check.py --build` 通过，405 tests passed（387.95s），Ruff、123 文件格式检查、Mypy/55 个源码模块、sdist/wheel 构建通过。新增 8 项集成用例验证重建后新会话读取/远程执行、两类写操作批准与拒绝、当前 execution 身份/用户隔离、服务失败/版本错误和关闭适配器后的原生行为；旧配置目录与暂停恢复兼容用例继续通过。日志：`.artifacts/memory-skills-check.log`，JUnit：`.artifacts/memory-skills-pytest.xml`。

在已有隔离依赖环境重新安装 wheel，确认导入来自 site-packages，wheel 与 55 个源码文件一致，`uv pip check` 通过；新样例实际完成写入、Agent 重建、新会话检索与远程 Skill 流式结果。日志：`.artifacts/memory-skills-wheel-install.log`、`memory-skills-wheel-import.log`、`memory-skills-wheel.log`；结果：`.artifacts/memory-skills-wheel-demo/4a61e6008b234a9288c08ea30a43aa7e/result.json`。本批未调用真实模型/平台；隔离环境只运行新增样例，旧功能由全量回归覆盖。

### 本批交付：团队审批跨进程交接

- [x] `MetaAgentTeam.create/from_package(recovery=...)` 复用 LocalRecovery，固定团队 epoch、成员/session 身份与配置摘要。团队外层 checkpoint 和独占租约保存在已有 SQLiteRecoveryStore，每个成员继续使用原 L1/L2、journal 与插件 pin。
- [x] `suspend()` 在 Leader 待答且其他成员已结束时交接；消费流至结束后持久化 suspended 状态，`resume()` 重现同一个 interaction/execution。覆盖原对象续跑与宿主关闭/新进程重建，Leader 主路径和插件快路径审批均可使用。
- [x] 原生 build_team/send_message/approve_tool 接入已有效果执行器，list_members 显式只读；未知结果保留未决。当前每个成员 execution、每类协调工具一个逻辑操作，不新增通用消息 journal 或调度框架。
- [x] 两进程样例完成 Leader 委派→researcher 回复→Leader 审批暂停→新进程回答；恢复后仅新增 Leader 收尾模型调用，原成员工作和协调写入未重复。

运行和接口见[团队恢复样例](examples/team_recovery/README.md)。固定内核的 Runner 冷恢复工厂不能保留自定义 Leader harness；本批使用公开 `TeamAgent.stream/recover_for_existing_session`，继续由原生内核协调，不访问私有状态。

该组件交接批次验证显式、完整的本机审批交接；处理中直接终止或提前关闭流不视为可恢复交接。当时尚未接通团队 worker；其后续服务接入见下文。非 Leader 待答、成员快路径自动回复、passive human、共享后端和跨主机仍未完成，现有 LocalRecovery 对 MCP/平台写入、goal/子代理和 evolution 的限制保持。M6-04 与完整 GATE-TEAM 继续未勾选。

2026-10-22 验证：全量 `scripts/check.py --build` 通过，410 tests passed（440.46s），Ruff、126 文件格式检查、Mypy/56 个源码模块、sdist/wheel 构建通过。最终待答标记与事件流关闭调整另由 10 项团队/恢复定向测试通过；覆盖同宿主与双进程交接、原交互/执行身份、未重复委派、原配置校验、单宿主竞争及未完整交接拒绝。日志：`.artifacts/team-recovery-check.log`、`team-recovery-final-lifecycle.log`；JUnit：`.artifacts/team-recovery-pytest.xml`。

在已有隔离依赖环境重新安装 wheel，确认导入来自 site-packages、制品与 56 个源码文件一致，`uv pip check` 通过；两个独立进程的委派/审批恢复样例通过。日志：`.artifacts/team-recovery-wheel-install.log`、`team-recovery-wheel-import.log`、`team-recovery-wheel.log`；结果：`.artifacts/team-recovery-wheel-demo/848fb4cb48b446aaadc5dbb71b361a2d/result.json`。本批未调用真实模型或平台；隔离环境只运行新增样例，旧功能由全量回归覆盖。

### 本批交付：团队接入 A2A / AgentGov worker

- [x] 复用现有 A2A worker，按 `meta_team.yaml` 装配团队；启动时校验成员包并固定快照，每个 context 创建并复用一份 MetaAgentTeam。
- [x] 新业务输入经过 Team → Leader MetaBaseAgent DAG；原生协作消息进入成员 DAG，单成员快路径为零 DeepAgent/模型调用，保留直接单 Agent 组件入口。
- [x] 复用 A2A task store / TaskUpdater，输出成员完成轮次与最终结果；Leader 待答时保留唯一后台事件消费者，回答复用原 execution，活动/待答取消等待团队关闭。
- [x] 同一配置包提供组件、SSE 和本地 AgentGov 转发样例，覆盖注册/心跳/下线；`/admin/team` 提供鉴权只读状态。

运行见[团队 worker 样例](examples/team_worker/README.md)。首次服务交付验证同进程链路、按轮次缓冲的成员输出和旧 task 跨重启查询，当时团队包拒绝 `--durable`；后续审批恢复接入见下一节。passive-human inbox API、团队管理写接口、真实平台与完整 GATE-TEAM 继续保留未完成。

2026-10-22 验证：全量 `scripts/check.py --build` 通过，415 tests passed（445.20s），Ruff、129 文件格式检查、Mypy/57 个源码模块及 sdist/wheel 构建通过。新增 5 项 TCP 集成用例覆盖单成员主/快/fallback、会话隔离、委派→Leader 审批续跑、活动/待答取消、同 context 冲突、断连查询不重放和旧 task 跨重启查询边界。日志：`.artifacts/team-a2a-check.log`；JUnit：`.artifacts/team-a2a-pytest.xml`。

源码与隔离 wheel 的双成员/单成员样例均通过，实际比较组件、A2A SSE 和本地 AgentGov 转发结果。隔离环境确认导入来自 site-packages、制品与 57 个源码文件一致，`uv pip check` 通过。日志：`.artifacts/team-a2a-wheel-install.log`、`team-a2a-wheel-import.log`、`team-a2a-wheel-demo.log`、`team-a2a-wheel-single.log`；结果目录：`.artifacts/team-a2a-wheel-demo/4c423931fe034f17a66ea3142ee4fdf2/`、`team-a2a-wheel-single/404e65d2b1874e36a884def3a1168220/`。本批无需真实模型 key，未运行真实平台或容器；隔离环境只运行新增样例，旧功能由全量回归覆盖。

### 本批交付：团队审批恢复接入 worker

- [x] 团队包 `--durable` 复用 LocalRecovery 与现有 suspend/resume。Leader 待答且其他成员结束后，完整消费暂停流，再发布可恢复的 `input_required`；交接失败不返回可恢复审批。
- [x] 复用 A2A task artifact 保存 task/context/execution 对应关系、原 interaction、已完成成员结果和暂停阶段 usage；新 worker 只从已存任务读取恢复数据，客户端仅提交答案。
- [x] 每个 context 使用稳定且独立的团队恢复身份/租约，继续共享同一个 SQLiteRecoveryStore 与 Runner。重启后拒绝漏传 taskId、错误 context、重复 messageId 和已取消任务续跑。
- [x] 两个 worker 进程的真实 TCP A2A 样例保留原 task/execution，恢复后只新增一次 Leader 收尾模型调用，researcher 工作和协调写入不重复；成员结果及累计 usage 保留。

运行：`uv run --locked python examples/team_worker/recovery.py`，说明见[团队 worker](examples/team_worker/README.md)。非 Leader 待答/快路径自动回复、passive human、LocalRecovery 尚未支持的能力组合、任意执行位置崩溃接管、共享后端与真实平台仍未完成。本批只接通审批点完整交接，不扩大恢复模型；M6-04 与完整 GATE-TEAM 继续未勾选。

2026-10-22 验证：全量 `scripts/check.py --build` 通过，421 tests passed（479.34s），Ruff、131 文件格式检查、Mypy/57 个源码模块、sdist/wheel 构建通过。6 项新增集成用例覆盖同宿主/重建审批、委派结果和跨交接 usage、两个待答 context、重启后取消、失败交接不报告可恢复，以及两个真实 worker 进程的原 task 续跑；17 项 A2A 定向测试全部通过。日志：`.artifacts/team-worker-recovery-check.log`、`team-worker-recovery-focused.log`；JUnit：`.artifacts/team-worker-recovery-pytest.xml`。

在已有隔离依赖环境重新安装 wheel，确认导入来自 site-packages、制品与 57 个源码文件一致，`uv pip check` 通过；两个独立 worker 进程的 A2A 审批恢复样例通过。日志：`.artifacts/team-worker-recovery-wheel-install.log`、`team-worker-recovery-wheel-import.log`、`team-worker-recovery-wheel-demo.log`；结果：`.artifacts/team-worker-recovery-wheel-demo/f9f40d636dc149a09329a57fd1b06702/result.json`。本批未调用真实模型或平台；隔离环境只运行新增恢复样例，旧功能由全量回归覆盖。

### 本批交付：PostgreSQL 单 Agent 共享恢复

- [x] 选择 PostgreSQL，将现有关系型恢复操作抽出复用；服务端时间、会话行锁和 fencing 同事务检查，沿用既有 journal/租约/原生 Checkpointer。
- [x] L1/L2、runtime admission/response、操作身份与 intent/result、插件字节和 pin 同库提交；保留 SQLite schema 与 `LocalRecovery` 兼容入口，新宿主可使用 `Recovery(PostgresRecoveryStore(...))`。
- [x] 真实 PostgreSQL 验证连接竞争、旧 owner 拒写、未决效果与 pin、主路径审批、原插件/路由、后续会话记忆。两个独立进程采用不同目录，实际终止第一进程后接管原 execution，账本只写一次，快路径审批仍零模型调用。
- [x] 添加可选 postgres 依赖、可运行样例和针对性 CI job；远端 CI 未执行。

该批范围为单 Agent **组件 API**；当时团队共享后端明确拒绝。后续 Team/A2A 审批交接见下一节。未决成员、实际跨物理主机/Kubernetes、平台效果/goal/子代理/evolution 的恢复组合保持未完成；新后端不增加上游原生 checkpoint 的提交粒度。见 [ADR-0007](docs/adr/0007-postgres-shared-recovery.md)、[样例](examples/shared_recovery/README.md)。

2026-10-22 验证：7 项 PostgreSQL 集成测试通过，包括两个真实进程接管；此前共享契约及 SQLite 存储/执行器回归 37 项通过。全量 `scripts/check.py --build` 通过：**428 tests passed（587.01s）**、Ruff、134 文件格式检查、Mypy/59 个源码模块、sdist/wheel 构建。日志 `.artifacts/pg-full-1.log`，JUnit `.artifacts/pg-full-1.xml`。

隔离环境重新安装 wheel，确认导入来自 site-packages、wheel 与 59 个源码模块逐字节一致，195 个依赖兼容检查通过。wheel 的 PostgreSQL 双进程快路径审批样例保留同一 execution/route，零模型调用，测试账本仅一次写入；结果 `.artifacts/pg-wheel-demo/result.json`，日志 `pg-wheel-install.log`、`pg-wheel-import.log`、`pg-wheel-demo.log`。数据库为真实 PostgreSQL 17 容器，同机 TCP；未调用真实模型/平台、未验收跨物理主机与应用镜像。

### 本批交付：PostgreSQL Team/A2A 审批交接

- [x] 复用原生 Team PostgreSQL backend 和 A2A SDK `DatabaseTaskStore`，与 MetaAgent recovery 使用同一数据库/schema；没有增加调度器或任务存储协议。
- [x] 原生 Team 即使使用 PostgreSQL 仍把消息/任务正文写到文件；完整暂停后将该 Team 的 native home 快照写入共享 checkpoint，恢复时在新 worker 目录还原，再恢复协调。文件快照失败不会发布可恢复交接。
- [x] A2A CLI 增加 `--durable --postgres --postgres-schema`，DSN 通过 `META_AGENT_POSTGRES_DSN` 提供；单 Agent worker 同样支持共享 A2A task 与审批续跑。
- [x] 双进程样例先委派 researcher，再暂停于 Leader 审批；第一 worker 完整退出，其运行目录与示例成员 workspace 移到离线证据目录。第二 worker 从 PostgreSQL 查询原 task、还原消息正文并回答，只增加一次 Leader 收尾调用，不重复委派/研究。

本批仅支持 **停止旧 worker 后，在 Leader 审批点完整交接**。业务包、provider、Skill 和配置路径须一致；`state_dir` 可以变化。任意成员 workspace/外部文件不自动迁移，示例无需这些文件。未决成员工作、运行中崩溃接管、同一任务的并发多 worker 写入、实际跨物理主机/Kubernetes 尚未验收。

完整检查点 #10 仍有未决成员与跨主机部分，故本批 **65% → 65%（13/20）**，不将局部接通计为全部完成。运行命令和边界见 [团队 worker](examples/team_worker/README.md)。

2026-10-22 验证：`scripts/check.py --build` 全部通过，**431 tests passed（585.26s）**，含 10 项真实 PostgreSQL 集成、SQLite/A2A/Team 回归；Ruff、134 文件格式检查、Mypy/59 个源码模块、sdist/wheel 构建通过。日志 `.artifacts/pg-team-full-1.log`，JUnit `.artifacts/pg-team-full-1.xml`。本地数据库为 PostgreSQL 17，同机 TCP；脚本模型不使用 SiliconFlow key，未执行远端 CI 或真实平台验收。

隔离环境安装新 wheel 后，59 个源码模块与制品逐字节一致，196 个依赖兼容检查通过。wheel 的 PostgreSQL 双 worker A2A 样例通过，第二目录恢复 2 份原生消息正文，保留原 task/execution/研究结果，仅一次 Leader 收尾调用。结果 `.artifacts/pg-team-wheel-demo/5bd2ac6afdf9438b8b9481d53d7d3bea/result.json`；日志 `.artifacts/pg-team-wheel-demo.log`、`pg-team-wheel-install.log`、`pg-team-wheel-check.log`。

### 本批交付：未完成成员的工具审批接续

- [x] Leader 询问用户时，允许其他成员停在原生工具权限审批点；保存各自 execution、tool call ID 和 pending usage，复用既有 checkpoint 与 Team manifest。
- [x] 原生 Team 启动后，先重建并唤醒待答成员，再继续 Leader；批准通过原生 `approve_tool`，协调效果沿用原 journal 操作身份。取消交互/停止宿主不会被误作审批答案。
- [x] 组件测试验证批准只发送一次 `send_message`，拒绝不发送；同一成员 execution 在重建前后保持一致。
- [x] A2A 样例新增 `--pending-member`；双进程分别用 SQLite 和 PostgreSQL 交接同一 task，汇总暂停前后 usage，不重复委派或提出同一工具请求。PostgreSQL 样例沿用分离 worker 目录和旧文件离线方式。

范围限于完整暂停交接：成员在等待原生工具审批，Leader 通过 ask_user 询问用户。成员普通 ask_user、计算中崩溃、MCP 等其他写入组合与实际跨主机部署仍待完成。固定检查点 #10 还需部署证据，故本批 **65% → 65%（13/20）**；已完成子项单列，不提前计整项。

2026-10-22 验证：`scripts/check.py --build` 全部通过，**435 tests passed（607.58s）**，含 11 项真实 PostgreSQL 集成及成员批准/拒绝、SQLite/A2A/Team 回归；Ruff、135 文件格式、Mypy/59 个源码模块、sdist/wheel 构建通过。日志 `.artifacts/member-full-1.log`，JUnit `.artifacts/member-full-1.xml`。

隔离环境安装新 wheel，59 个源码模块与制品逐字节一致，196 个依赖兼容。wheel 的 `--pending-member --postgres` 双 worker 样例通过：旧文件离线后恢复原 task 与待答成员 execution，Leader 批准后只发送一次成员消息，累计 usage 与调用日志一致。结果 `.artifacts/member-wheel-demo/530d5362acb34c408495c6e5533de4a3/result.json`；日志 `.artifacts/member-wheel-demo.log`、`member-wheel-install.log`、`member-wheel-check.log`。使用本机 PostgreSQL 17 与脚本模型，未调用真实模型/平台，也未外推为跨物理主机验收。

### 本批交付：HITT 真人协作服务入口

- [x] 团队 worker 接受配置的 passive human，提供受 worker token 保护的 context/member 收件箱与消息发送 API；宿主负责终端用户身份及会话归属。
- [x] 原生 build_team 创建真人成员后接入 inbox，再继续模型调用；团队消息可按 cursor 获取，真人意见沿原生消息通道进入成员 DAG。
- [x] 普通业务验证：Leader 发起评审 → 宿主读取 inbox → 真人回复 → Leader 使用反馈并回信，A2A task 完成。另确认原单成员快/慢/fallback 入口可用。

该批完成 #17 的真人消息服务子项时，任务控制、团队更新与剩余 GATE-TEAM 尚未完成，历史综合分数维持 **65% → 65%（13/20）**。后续功能进展见下节；真人 inbox 的重启恢复后置。

2026-10-22 仅运行相关正常路径：**2 passed（17.37s）**，日志 `.artifacts/hitt-functional-2.log`；4 个变更 Python 文件的 Ruff/格式与 3 个变更源码文件的 Mypy 通过。本批未运行恢复测试、全量回归或 wheel 安装验证。

### 本批交付：F1b–F4 正常业务架构贯通

| 部分 | 已交付正常功能 | 直接证据 | 综合分数变化 |
|---|---|---|---|
| F1b HITT/团队管理 | 真人 view/claim/complete task 原生工具；团队包 reload 对新 context 生效，旧 context 保留配置/digest；成员 DAG 跨空闲周期保留，整 Team 关闭时释放；审批前后 usage 合并 | 4 项正常功能检查：`.artifacts/f1b-team-3.log` 中 3 项通过，reload 问题修复后在 `f1b-team-4.log`、`f1b-team-5.log` 通过；完整业务样例复用同一 context 的治理状态及插件 | 65% → 65%；#17 的完整 GATE-TEAM 仍含后续验收 |
| F2 Harness | 原生异步子代理并发/等待/汇总、子代理 MCP 网关及权限；三个 goal stop 策略、assessor 计量、原 execution 内 ask_user 继续；独立子代理审批宿主 API | 13 项功能检查：`.artifacts/harness-functional-5.log`（12）及 `harness-session-1.log`（1）；62 项配置检查；异步样例实际运行两个子代理，7 次模型调用、105 tokens | 65% → 65%；补齐既有 Harness 检查点内的功能缺口 |
| F3 进化/供给 | 自动轨迹信号→待审 Skill；真实 native Team Skill rail 合并成员证据；宿主绑定工具、审批声明式 recipe、生成原生 Workflow、插件激活/回滚 | 3 项功能检查，`.artifacts/evolution-functional-test-2.log`；真实 Team 业务样例同时使用 Skill 与 Team Skill 提议 | 65% → **70%（14/20）**；关闭 #20 |
| F4 完整业务 | A2A→Leader/成员 DAG→批准 MCP→真人评审→自动/团队进化→批准 workflow→同会话再委派；第二次实际重新查询 MCP，researcher 模型/DeepAgent 调用均为 0 | [运行命令与流程图](examples/architecture_demo/README.md)；`.artifacts/architecture-demo-verified.log` 通过，断言查询返回事实、两次真实工具调用、成员 usage 与审批结果 | 70% → 70%；正常业务贯通不替代性能/质量/平台验收 |

本批只完成原设计的正常运行路径，不扩展为恢复组合或部署验收。真人头像代理（LLM avatar）不是原三份设计文档要求，移出 F1 的必需范围。Team reload 以新 context 为生效边界；恢复中的版本 pin 保持既有语义。workflow 由受信宿主批准具体工具步骤，不做任意 Skill 文本自动执行代码的额外系统。

最终业务结果：`.artifacts/architecture-demo/6d7c4c33d8664f3da653646400e1f8ed/result.json`。Ruff 检查与 135 个 Python 文件格式检查通过；Mypy 检查 62 个源码文件通过。本批没有新增恢复测试、运行全量回归或重复 wheel 安装验证。

### 历史综合验收完成度（保留原口径）

2026-10-22 真实使用补充：GLM-5.1 的 Leader（5 次模型调用）和 researcher（3 次）实际完成四组本仓源码读取与汇总。原始报告及人工复核在 `.artifacts/repository-review/8f6c426382f94ad3a4a70417320e7966/`；模型对团队进化/恢复范围的部分判断需要纠正，不能作为独立架构审计。结果格式检查修正后对原始 `result.json` 验证通过，日志 `.artifacts/repository-review-verified.log`。本批仅交付业务配置、Skill、MCP 读取工具和运行入口；**70% → 70%**，不通过新增样例提高架构分数。

按下列 **20 个功能检查点，每项 5%** 估算；只对已实现且有对应本地运行证据的检查点计分，部分完成暂不计分。它不是代码覆盖率、工期百分比或完整生产验收。各检查点工作量不同，原设计详细门禁仍为验收依据；若范围变化，另记口径版本，不通过重划任务提高比例。

单 Agent 共享恢复曾使估算由 **12/20 ≈ 60%** 升至 **13/20 ≈ 65%**；自动/团队进化与 workflow 供给关闭 #20，达到 **14/20 ≈ 70%**；本次固定质量评估后为 **15/20 = 75%**。这份清单混合了功能实现、恢复、部署、性能与质量验收，不能用它决定当前开发顺序，也不能把它当作纯架构代码完成比例。保留历史分数；同时报告具体功能进展及尚未关闭的整项，不靠重新分组提高百分比。

| # | 对应目标 | 固定检查点 | 已计入 |
|---|---|---|---|
| 1 | G1 | 配置业务包启动、组件/服务入口 | ✓ |
| 2 | G1 | 实际平台/容器部署与平台 SDK 最小互通验收 | — 本机 Docker Team/A2A 已通过；真实平台与平台 SDK 待验收 |
| 3 | G2 | 双路径路由、零模型快路径与调用计量 | ✓ |
| 4 | G2 | 固定 workload 的 P95 时延目标实测 | — 已测；优化按用户要求后置。保留原目标，不阻塞当前里程碑 |
| 5 | G3 | 原生 DeepAgent 主循环与后置 fallback 语义 | ✓ |
| 6 | G3 | 代表性复杂任务的成功率与 fallback 质量评估 | ✓ 本地固定 6 题多工具 workload，原生 5/6、主路径/fallback 各 6/6；仅计评估基线，不外推生产成功率 |
| 7 | G4 | 本机 L1/L2/journal、租约与效果恢复 | ✓ |
| 8 | G4 | 冷恢复保留 route/插件版本、会话与请求身份 | ✓ |
| 9 | G4 | 单 Agent 共享后端与独立进程接管 | ✓ |
| 10 | G4/G6 | Team/worker 共享状态、未决成员与跨主机代表性交接 | — 共享审批及未完成成员工具审批接续已实现；跨主机验收待完成 |
| 11 | G4 | 平台写入、goal/子代理、evolution 与恢复组合贯通 | — goal、声明只读 MCP、同步子代理完整暂停/待答、并发子任务排空后的状态与结果恢复、Skill 审阅/源文件发布/版本和生成 workflow 治理已实现；平台写入/运行中队列/异步子交互及完整组合保持开放 |
| 12 | G5 | Skills/rails/workflow/路由扩展接线 | ✓ |
| 13 | G5 | 本机插件加载/原子切换/回滚/引用保留与卸载 | ✓ |
| 14 | G6 | 原生 Team 调度真实 Leader/成员 DAG，单/多成员配置 | ✓ |
| 15 | G6 | 配置成员权限/MCP、Leader 工具审批与真人消息本地链路 | ✓ |
| 16 | G6 | A2A/AgentGov 本地服务生命周期与 Leader 审批重启续跑 | ✓ |
| 17 | G6 | 完整 HITT 服务控制面、团队更新与剩余 GATE-TEAM | — 普通真人消息/任务、团队更新与本机 HITT 暂停恢复已完成；平台/其余恢复门禁后置 |
| 18 | G7 | JSONL、原生轨迹、Ops 指标与错误观测本地链路 | ✓ |
| 19 | G7 | 宿主显式 Skill 提议/审批/拒绝/回滚闭环 | ✓ |
| 20 | G7/G5 | 自动进化信号、团队进化和 Skill 固化 workflow | ✓ |

| 批次 | 本次关闭 | 估算变化 | 证据 |
|---|---|---|---|
| 2026-10-22 评审基线 | 已有本地实现，12 项 | 60% | 本文各批次与原 421 项回归记录 |
| 2026-10-22 共享恢复 | #9 单 Agent PostgreSQL 组件与双进程接管 | 60% → 65% | 7 项 PG 集成、428 项全量回归、构建与隔离 wheel 接管样例通过 |
| 2026-10-22 Team/A2A 共享审批 | #10 部分：共享数据库、native 文件与双 worker 审批交接 | 65% → 65% | 10 项 PG 集成、431 项全量回归与构建通过；未决成员和跨主机部分不计分 |
| 2026-10-22 成员审批接续 | #10 部分：未完成成员 execution、原生批准/拒绝及累计 usage | 65% → 65% | 435 项回归、构建及隔离 wheel 的 PostgreSQL 双进程样例通过；实际跨主机证据待补 |
| 2026-10-22 真人服务入口 | #17 部分：worker inbox、真人回复与成员 DAG 贯通 | 65% → 65% | 正常真人协作及单成员入口通过；团队更新与完整控制面未完成 |
| 2026-10-22 功能主线贯通 | #20；另补齐 #17 普通控制面/更新及 Harness 功能 | **65% → 70%** | F1b/F2/F3 定向功能检查 + 同会话完整业务演示 |
| 2026-10-22 本机 Docker | #2 部分：镜像构建、Linux worker 就绪、A2A 快路径与真实模型 Team 委派 | **70% → 70%** | 本次部署范围 100%；真实平台与平台 SDK 尚未验收，不提前关闭整项 |
| 2026-10-22/23 HITT 暂停恢复 | #17 部分：inbox/cursor、原生任务归属及真人消息接续 | 70% → 70% | 本次限定功能 100%；4 项功能/交接检查及 9 项相邻团队恢复检查通过 |
| 2026-10-22 goal / MCP 读取恢复 | #11 部分：原生 goal/attempt/tokens/report 保留；声明只读 MCP 的证据复用与调用前校验 | 70% → 70% | 两个限定功能均 100%；17 项 goal/预算、7 项 MCP/权限检查通过 |
| 2026-10-22 固定质量基线 | #6：同题、同模型、真实工具的原生/主路径/fallback 对比 | **70% → 75%** | 评估工作完成；MetaAgent 12/12，原生 5/6；保留失败，不外推统计等价或生产分布 |
| 2026-10-22 时延测量 | #4 路由达标，完整 Team 终态未达标 | 75% → 75% | 两组各 100 样本，2 秒原生 idle 等待有独立事件时序证据；目标仍开放 |
| 2026-10-23 同步子代理恢复 | #11 部分：父子 checkpoint 原子保存、完成证据复用、sticky 对话恢复、子工具合约和 Skill 固定 | 75% → 75% | 本次限定功能 100%；9 项新增检查、22 项相邻检查通过；异步/子交互等完整范围未关闭 |
| 2026-10-23 Skill 审阅恢复 | #11 部分：待审/批准/拒绝/partial/回滚持久化、单 owner、session Skill 版本固定与自动提案保留 | 75% → 75% | 本次限定功能 100%；生成 workflow 治理、跨主机与完整组合继续开放 |
| 2026-10-23 生成 workflow 恢复 | #11 部分：待审/拒绝/激活/回滚与插件字节保留、宿主重绑、旧 execution 版本固定 | 75% → 75% | 本次限定功能 100%；6 项新增检查与 21 项相邻回归通过，完整 #11 继续开放 |
| 2026-10-23 同步子代理待答恢复 | #11 部分：子 `ask_user` / 工具审批持久化、冷读取原问题、回答后继续原来的子任务 | 75% → 75% | 本次限定功能 100%；13 项子代理检查与 20 项相邻回归通过；异步/后台及运行中断恢复继续开放 |
| 2026-10-23 并发子代理完整边界恢复 | #11 部分：原生运行中/排队任务在父边界排空、父子状态原子保存、冷读取结果与继续原有子会话 | 75% → 75% | 本次限定功能 100%；6 项新增检查与 22 项相邻回归通过；运行中队列重放与异步子交互未关闭 |
| 2026-10-23 源 Skill 发布与版本迁移 | #11 部分：精确源文件快照、宿主批准/拒绝、完整文件与经验回滚；新 session 采用发布版本 | 75% → 75% | 本次限定功能 100%；3 项新增功能检查与 13 项相邻回归通过；完整 Team/跨主机组合仍开放 |

### 本期结项：功能架构基线完成

F1–F4 的正常功能已交付，本期实施阶段结项：

- [x] F1a HITT 消息入口：已有真人消息组件接到受认证的 worker API，提供上下文内的收件箱与回复。
- [x] F1b HITT/团队管理：原生真人任务控制、团队配置/业务包更新（新 context 生效），保持旧 context 配置与治理状态。
- [x] F2 Harness：异步子代理并发/汇总、MCP/权限、预算计量/策略与目标交互正常路径。
- [x] F3 进化：轨迹自动触发 Skill 提议、native 团队进化、审批后声明式 workflow 供给，复用现有审批与插件注册。
- [x] F4 功能贯通：代表性业务串起 Team、成员 DAG、MCP/权限、真人协作、进化与下一轮快路径。

F1–F4 是本期收尾任务，不作为新百分比分母。本次结项复用已有功能证据；不继续优化仓库评审等特定案例，也不自动开启恢复、部署或性能工作。

### 本机 Docker 部署：已完成

用户明确选择本机 Docker 后，完成一次独立部署验收。将不可用的 `uv:0.11.19-python3.11-bookworm-slim` 基础镜像改为已发布的 `uv:0.11.19-python3.11-trixie-slim`，保留 Python/uv 版本、依赖锁及原有运行时；未修改 MetaAgent 执行代码。

- [x] Docker Desktop Linux engine 构建 `meta-agent:local`，镜像 ID `sha256:cf2fb6a89318136527f34005b79607ee9dcdb80ff9f112f57036662f7199024f`。
- [x] `meta-agent-local` 以 UID 10001 运行，业务包只读挂载、状态使用命名卷，宿主仅开放 `127.0.0.1:8080`；Docker health 和认证 `/admin/health` 均通过。
- [x] 现有 `team_demo` 通过 A2A 进入 Leader Workflow，模型/DeepAgent 调用均为 0。
- [x] SiliconFlow `Pro/zai-org/GLM-5.1` 完成 Leader → researcher Workflow → Leader 汇总：4 次模型调用、2 次 Leader DeepAgent 调度；researcher 模型/DeepAgent 均为 0；成员 SSE 和 `tasks/get` 通过。

复现命令及运行范围见 [本机 Docker](examples/docker_local/README.md)；证据为 `.artifacts/docker-local/build.log`、`verify.log`、`result.json`。本次部署范围 **100% 完成**；原综合验收仍为 **14/20 = 70%**。未启用真实 AgentGov、共享恢复或跨主机环境，不新增恢复矩阵。§7 较早批次“镜像未验收”的描述是当时记录，由本次普通部署结果补充。

### 本机后置项：2026-10-22 增量

用户确认仅使用本机，按实际可用环境处理后置项：

- **HITT 完整暂停恢复**：既有 A2A artifact 保存真人 inbox/cursor，原生快照保存任务/归属；继续原 task 时恢复消息回调。真人操作在暂停前排空。`tests/integration/test_hitt_recovery.py` 与既有真人功能 3 项通过，`.artifacts/hitt-recovery-5.log`；相邻审批/待决成员恢复 9 项通过，`.artifacts/deferred-adjacent-tests.log`。10 月 23 日复核补上真人 HTTP 请求首次启动成员时的 Team recovery context；复现修复前 `META_TEAM_UNSUPPORTED` 后，新增 1 项检查通过，`.artifacts/hitt-human-start-after.log`。
- **Goal 完整暂停恢复**：复用 native SessionGoalStore 和 fenced checkpoint，保留 goal/revision、attempt、tokens、已提交报告和 transcript assessor 状态；未完成 attempt/resume 不自动重放。新恢复与原预算功能 17 项通过，`.artifacts/goal-recovery-tests.log`。
- **声明只读 MCP 恢复**：Python 宿主显式提供 `LocalRecovery(read_only_tools=(...))`；每次调用经原生工具 hook 校验动态工具名，未声明工具使用公开 AbortError 契约阻止执行。普通与 goal 的 read→pause→重建保留原 execution/证据且不重复 read；3 项新用例和 4 项既有权限检查通过，`.artifacts/mcp-recovery-tests.log`。这不开放 MCP 写入或平台恢复契约。
- **质量评估**：[固定 workload](benchmarks/quality/README.md)覆盖依赖规划、约束选择、多源核对，6 题×3 模式；真实 GLM-5.1 调用。原生 5/6、主路径 6/6、fallback 6/6；原生超额支付核对失败保留。18 次均带解释/Markdown，纯 JSON 格式通过数为 0，事实与格式分别记录。计入 #6 的是本地质量评估基线，不是任意复杂任务质量保证。
- **时延测量**：[两组固定 100 样本](benchmarks/latency/README.md)均正确且零模型；规则路由 P95 0.079/0.080ms，通过；E2E P95 2402/2158ms，未通过。首个成员结果约 201–211ms 后，还需约 2s 等待内核 team.idle；固定版本没有公开 debounce 配置。没有修改私有常量或提前截断团队结束语义。#4 保持开放。
- **本机部署复核（2026-10-23）**：镜像重建并替换本机容器，保留状态卷；Docker healthy 与认证 ready 通过。公共 A2A 快路径为 0 模型/DeepAgent，真实 GLM-5.1 Team 委派为 4 次模型调用；结果 `.artifacts/docker-local/deferred-result.json`，日志 `deferred-verify.log`。仍为默认非 durable 业务包；新恢复功能的验收来自上述定向集成检查，不将普通部署请求算作恢复验收。

只运行直接相关的 37 项功能/相邻回归检查、目标文件 Ruff/格式/Mypy 与实际 workload；不重跑全量恢复矩阵或重复 wheel 安装。功能基线继续完成，综合验收 **15/20 = 75%**。

### 同步子代理暂停恢复：2026-10-23

复用原生 `task_tool` 与 Session checkpoint，不新增子任务调度器。`LocalRecovery` 接受同步子代理配置，仍拒绝两个异步模式。父子状态和 bridge 结果在同一租约下原子提交；父暂停后冷重建保留 execution 和已完成子任务证据，native `verification_agent` 的 sticky 会话可继续旧对话。父 goal 继续沿用原 attempt 与包含子模型的累计 tokens。

子代理 tools 与父工具使用同一 recovery 合约校验；子 MCP 的未声明动态工具在执行前拒绝。子 Skill 文件纳入固定快照；配置指纹排除父子模型自动生成的连接 ID，以支持重新解析原配置。只开放已完成子任务后的父暂停；子代理内部交互、运行中断、未完成 resume 不被误报为可恢复暂停。

验证：9 项新增检查通过（`.artifacts/subagent-recovery-final-2.log`）；22 项相邻原生 checkpoint、goal、MCP、同步/异步普通功能检查通过（`.artifacts/subagent-focused-checks.log`，其中初次子交互检查失败已由最终 9 项修复验证覆盖）。目标文件 Ruff/格式/Mypy 通过；无全量回归、额外真实模型评测或时延优化。使用方式见 [Harness 说明](examples/harness_demo/README.md#同步子代理的暂停恢复)。本次范围 **100% 完成**，原综合验收 **15/20 = 75%**，#11 仍为部分完成。

### Skill 审阅与版本恢复：2026-10-23

`evolution.enabled` 可与 `LocalRecovery` 同时使用。复用 OpenJiuwen 的普通/Team Skill Rail、待审快照、经验应用与配对归档；复用既有 RecoveryStore/LeaseGuard 保存 Skill 文件和审阅元数据，不增加优化器、调度器或数据库表。数据库提交是激活边界；原生写入发生在私有工作副本，未提交的激活在重建后丢弃。

原业务包只作首次导入。新 session 读取当时已提交版本，旧 session 的后续轮次和冷恢复从固定制品物化文件；批准/回滚不会修改旧会话的文件或经验。待审、拒绝、partial 未写尾部及原回滚版本跨重启保留；稳定命名的本地轨迹目录支持重启后取证，自动扫描记录保留。治理使用单 owner 租约。该批次尚未开放的生成 workflow 治理恢复由下列增量补齐。

7 项新增检查覆盖 session 版本、重启审阅、partial 接续、提交失败、单 owner、普通/team-skill 和自动提案；相邻原生进化/workflow、同步子代理、会话 checkpoint 检查共 22 项通过。日志：`.artifacts/evolution-recovery-2.log`、`evolution-recovery-final.log` 与修正测试调用参数后的 `evolution-recovery-guard.log`；自动扫描互斥的最终复核见 `evolution-auto-final.log`。目标文件 Ruff/格式/Mypy 通过。本次限定功能 **100% 完成**；原综合验收保持 **15/20 = 75%**，#11 仍为部分完成。使用方式见 [Skill 审阅与版本恢复](examples/skill_evolution/README.md#skill-审阅与版本恢复)。

### 生成 workflow 治理与版本恢复：2026-10-23

声明式 recipe 的待审、拒绝、激活选择、回滚关系与精确插件字节接到既有 evolution checkpoint。仍由原生 Workflow 执行步骤，使用现有插件快照和 execution pin；不增加调度器或第二个治理存储。新 execution 使用当前激活版本，已有 execution 的 `resume` 保留原路由和插件字节。

恢复模式用 `await stage_workflow(...)` 和 `await reject_workflow(...)` 提交审阅状态，批准/回滚继续使用异步 API。宿主声明只读 callback 后绑定同名能力；重启后在业务请求前调用 `await restore_workflows()`。函数不被序列化，语义变化需更新 `contract_version`；写操作使用既有 `EffectBinding` 与 journal。数据库提交前不发布激活，导出的 `.meta-workflows/` 仅供检查，不作为恢复来源；不同时使用独立 `plugin_catalog`。

新增 `tests/integration/test_workflow_recovery.py` 的 6 项检查覆盖待审/拒绝重建、删除导出后恢复、重绑门禁、v1/v2 与旧 execution、回滚、提交失败和受管效果复用。6 项新增检查与 21 项相邻回归通过（共 27 项）。相邻历史配置检查修正了旧版本 fixture 误含后加自动进化默认字段的问题，单项复测通过；日志为 `.artifacts/workflow-recovery-final.log` 与 `workflow-recovery-compat.log`。目标文件 Ruff、格式与 Mypy 通过。本次限定功能 **100% 完成**；原综合验收保持 **15/20 = 75%**，#11 仍为部分完成。使用方式见 [生成 workflow 的恢复](examples/skill_evolution/README.md#生成-workflow-的恢复)。

### 同步子代理待答恢复：2026-10-23

同步 `task_tool` 接入父代理的小型 BaseInterruptRail bridge，调用 OpenJiuwen 公开的 `create_subagent` / `Runner.run_agent`；原生 ToolInterruptHandler 负责嵌套交互。子代理的 `ask_user` 或工具审批成为正常的 `AgentResult(result_type="input_required")`，父子原生状态和稳定子 session 映射在既有 checkpoint 一起提交。重启后 `resume` 不带答案读取原问题，带答案继续原来的子代理，再由父代理汇总；native verification sticky 对话沿用原会话。

恢复模式使用原生 PermissionInterruptRail，无需内存中的审批 Future。普通模式保留已有 `pending_subagent_approvals` / `answer_subagent_approval`；父 `task_tool` 权限仍在子代理启动前生效。该增量只开放已完整保存的同步子交互边界，不扩大到异步/后台队列、运行中断或未完成的 resume，也不新增调度器。

定向验收通过：`test_subagent_recovery.py` 的 13 项检查覆盖子 `ask_user` 冷恢复、子工具允许/拒绝、父 `task_tool` 拒绝、错误子代理名称的修正及既有同步子任务功能；另有异步普通模式、预算与 goal 恢复的 20 项相邻检查通过，共 33 项不同检查。首次合并运行通过 32 项，审阅修正后复测全部 13 项子代理检查；日志为 `.artifacts/child-interaction-recovery-final.log` 与 `.artifacts/child-interaction-review.log`。目标文件 Ruff、格式与 Mypy 通过。本次限定功能 **100% 完成**；原综合验收保持 **15/20 = 75%**，#11 的完整恢复范围仍未关闭。使用方式见 [同步子代理的暂停恢复](examples/harness_demo/README.md#同步子代理的暂停恢复)。

### 并发子代理完整边界恢复：2026-10-23

`LocalRecovery` 接受 `enable_subagent_runtime`，继续由 OpenJiuwen 原生 spawn/wait/list/resume/send_input、worker 和队列执行并发子任务。父代理生成暂停或最终结果后，先等待已有运行中和排队任务结束并关闭该批 worker，再将原生记录、结果与子会话状态同父状态原子提交。父代理的 `input_required` 或最终结果在队列排空后才返回。

冷重建后，`subagent_wait` 读取已保存的子结果，不重复已完成任务；原生 `subagent_resume` 配合 `subagent_send_input` 继续原来的子对话。复用既有 Session/checkpoint 与公开原生子代理控制接口，不引入新的调度器或队列表。工具、MCP、Skill 和权限继续遵守现有 recovery 合约。

该批只保存**队列排空后的完整边界**，不接管运行中崩溃后未提交的 worker/队列。固定内核的异步子代理 `ask_user` / 工具审批冷恢复仍有接缝缺口，需要待答时使用已支持的同步 `task_tool`。旧式仅 `enable_async_subagent` 的 SessionToolkit 不与 LocalRecovery 组合，改用 `enable_subagent_runtime`。未完成的父 resume、完整 Team/跨主机组合继续开放。

验证：6 项新增检查覆盖并发结果冷读取、原来的子会话追加工作、运行中和排队任务排空、异步子待答边界、父取消时关闭 worker，以及失败后续任务不复用前次成功。同步子代理、普通异步模式与 goal 恢复的 22 项相邻回归通过，共 28 项不同检查。最终批次通过 5 项，另一项修正了对内核模型重试次数的 fixture 假设后单项通过；日志为 `.artifacts/async-subagent-recovery-final.log`、`.artifacts/async-subagent-failed-followup.log` 与 `.artifacts/async-subagent-adjacent.log`。目标文件 Ruff、格式与 Mypy 通过。本次限定功能 **100% 完成**；原综合验收保持 **15/20 = 75%**，#11 仍为部分完成，不将此批次计为全部异步/后台恢复完成。使用方式见 [Harness 说明](examples/harness_demo/README.md#并发子代理的完整边界恢复)。

### 源 Skill 发布与版本迁移：2026-10-23

`LocalRecovery` 中，宿主通过 `stage_source(skill_name, directory)` 暂存已配置 Skill 的新说明及配套文件，检查文件清单、`SKILL.md` 差异和精确内容后再批准。复用 OpenJiuwen 源包的文件筛选与 pristine Skill 内容规则；源目录后续修改不影响已暂存快照，也不会直接激活。待审、拒绝、批准和回滚数据复用现有 evolution 租约与 checkpoint，没有新增发布服务或数据库表。

批准发布的是不含本地经验和归档的干净基线；批准前的完整工作目录（含配套文件和学习历史）按内容版本保留，回滚可恢复新增/删除文件与经验。新 session 使用当前批准版本，已有 session（包括已完成后的新一轮和暂停续跑）保留原版本；这就是本批的迁移边界，不强制改写已有会话。源发布限现有父 Agent Skill 的同名、同 kind 更新，不包括新增/重命名 Skill 或业务包配置迁移。同 Skill 的待审进化/workflow 需先处理；已批准 workflow 是独立制品，仍需独立更新或回滚。

验证：3 项新增功能检查覆盖待审快照重启后批准、原生源包筛选及 YAML 元数据、暂停/已有 session 与新 session 的版本分离、配套文件替换、含学习历史的完整回滚及拒绝保留；Skill/workflow 治理的 13 项相邻回归通过，共 16 项不同检查。首轮修正了测试对原生 pristine 内容换行规范化的预期，最终新增文件 3 项全部通过；日志为 `.artifacts/skill-publication-1.log` 与 `.artifacts/skill-publication-2.log`。目标文件 Ruff、格式与 Mypy 通过。本次限定功能 **100% 完成**；原综合验收保持 **15/20 = 75%**，#11 的完整 Team/跨主机组合仍未关闭。使用方式见 [源 Skill 发布与版本迁移](examples/skill_evolution/README.md#源-skill-发布与版本迁移)。

### 尚待实现 / 外部条件

2026-10-23 用户确认当前无需追求目标时延：停止安排 #4 的调优、内核升级或重复时延测量，已有结果仅作参考；不将该项计为已达标，也不以其阻塞当前功能与本机部署工作。

| 范围 | 剩余具体工作 |
|---|---|
| #2 真实平台 / SDK | 需要真实 AgentGov 端点/契约/版本与 MateMind Python/C++/Rust SDK；当前相邻仓库只有不同用途的旧推理/DataBus SDK，不能冒充此 A2A 互通 |
| #10 跨主机 | 需要第二主机、可达共享 PostgreSQL 和相同业务制品；同机容器或独立进程不计实际跨主机 |
| #4 端到端时延 | 按用户要求后置；当前不安排优化或重测，未来有实际性能需求时再处理 |
| #11 子代理 | 已支持同步 child 命名空间、同步子代理待答/审批及并发子任务排空后的父边界保存、结果读取和原会话接续；剩余为运行中 worker/队列重放、异步子待答及未完成 resume；固定内核尚缺对应持久化/中断接缝，原生 idle child resume 不等于中断工作恢复 |
| #11 进化 | 本机 Skill 版本物化、提议/审批/回滚、源文件发布及 session 版本边界已实现；生成 workflow 治理恢复已有本机验收；剩余为完整 Team/跨主机组合 |
| #11 平台写入 | MCP/Memory/SkillsRuntime 的稳定操作 ID、去重或结果查询契约，再绑定既有 EffectAdapter；本机替身不能证明真实服务契约 |
| #17 完整 Team 门禁 | 上述平台/跨主机与未覆盖的成员恢复位置；本次完整暂停 HITT 已完成 |

### 达到完整验收的执行顺序

沿用原 20 项清单，不新增百分比分母。每批先交付缺失功能，再运行直接相关的验收；子项完成不提前关闭其所属完整条目。

| 顺序 | 工作 | 关闭条件 |
|---|---|---|
| 1 · 当前本机工作 | 同步子待答、并发子任务完整边界恢复与源 Skill 发布/session 版本边界 | 已完成已安排的本机增量及定向验收；运行中队列和异步子交互缺口保留，待上游公开接缝可用后再接入 |
| 2 · 平台环境就绪后 | 真实 AgentGov/MateMind SDK 互通与 MCP/Memory/SkillsRuntime 写入合约 | 使用真实 SDK/服务验证互通、操作身份和结果查询/去重，关闭 #2 并补齐 #11 平台部分 |
| 3 · 第二主机就绪后 | 共享 PostgreSQL 上的实际跨主机交接 | 同一 Team 任务在另一主机接续，关闭 #10 并补齐恢复组合 |
| 4 · 汇合验收 | Team 串起子代理、进化、平台和交接 | 一个代表性链路覆盖已完成能力，按原 #11 / #17 的条件关闭完整范围 |
| 5 · 用户重新安排时 | 固定 workload 的端到端时延目标 | 达到原 #4 指标；当前不安排优化或重复测量 |

原清单尚余 #2、#4、#10、#11、#17，每项关闭贡献 5%。仅有本机不能完成真实平台与跨主机验收；时延继续后置时，其余条目全部关闭对应 **95%**，达到原清单 **100%** 仍需关闭 #4。

完成本批后，下一步是用当前组件与本机 worker 承载实际业务，按使用中发现的具体缺口迭代。同时收集上述平台/SDK、第二主机和上游接缝条件；条件具备后再关闭相应完整条目。当前不继续扩充本机恢复矩阵或安排时延调优。

### 后续验收：恢复、平台部署、性能与质量

代表性跨主机交接（#10）、Team→MCP 写入/子代理/进化的剩余恢复组合（#11）、平台联调（#2）继续开放。时延（#4）按用户要求后置，不属于当前工作；#6 已有固定 workload 评估，真实业务/长视界质量按对应部署另行测量。后续仍以具体功能缺口为范围，不增加无关恢复矩阵或每批全量回归。

### 后续变更规则

- 只有明确需求或具体功能缺陷触发后续增量；优先复用 OpenJiuwen 与已有 MetaAgent 代码。
- 保留已有操作身份、未决效果暂停、取消和必要输入校验；新增能力只补与其直接相关的正确性与权限检查。
- 每个变更只运行直接相关的检查；只有发现具体问题才补必要回归。全量回归、构建及恢复验证按发布需求另行安排，不因文档结项重复执行。
- 日常只更新 PLAN/README 的使用说明；确有架构决策变化才新增 ADR 或刷新设计审阅页。以可运行功能作为进展，不以文档或测试数量作为交付目标。

### 保留的后置范围

原设计中的恢复组合、实例漂移及平台写入接线仍包含实际功能缺口，不能统称为“只剩测试”。这些缺口保留在完整范围的任务清单中，按后续明确需求安排，不阻止已确认范围的功能基线结项。新增写入面届时按实际实现接入现有执行器；更细 checkpoint 接缝若受上游限制，记录具体缺口。

多种共享后端、存储高可用/灾备演练、长时间压力测试、穷举故障组合、无指标依据的性能调优、额外熔断/重试层和零丢失观测队列后置到部署要求或实测问题出现时。保留与功能直接相关的代表性故障检查，不以扩大这些检查代替架构实现。

功能可用、本地契约通过、真实平台联调和生产验收分别记录；M1/M4/M5/M6/M7 的父任务继续反映各自完整范围，不因计划调整提前勾选。
