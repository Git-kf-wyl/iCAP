# MetaAgent 系统设计文档

**2026-11-04 返回接口增补**：`PluginOutcome` 增加可选 `data: JsonValue = None`，允许业务自定义 JSON 对象、数组及标量；`output: str = ""` 保留为文字说明。成功/终止错误的 data 经 `FastPathOutcomeComp → MergeComp → End → AgentResult.data` 传递，普通流式 final 事件显式携带 data，耐久响应与 HTTP/A2A 使用完整结果序列化。旧响应缺失 data 时默认 None。允许 fallback 时 data 仅进入有来源的失败上下文，DeepAgent 的最终结果默认 data=None。额外业务字段应放入 data；JSON 之外的 Python 对象和非有限数值不属于传输契约。详见 [ADR-0003](docs/adr/0003-m3-fastpath-contract.md) 与 [README](README.md)。

**2026-10-22 成员审批恢复增补**：PostgreSQL 已接通 native Team DB、A2A tasks 与 native 文件快照。本批支持未完成成员停在工具审批点：先恢复原成员 execution/tool call ID，再由 Leader approve_tool 批准或拒绝。A2A 交接保留原 task 与累计 usage，不重复委派；停止交互不视为审批答案。业务包/配置路径须一致，成员普通 ask_user、其他写入组合及实际跨主机部署仍待完成。 固定口径仍为 **13/20 ≈ 65%**，#10 待补部署证据。见 [团队 worker](examples/team_worker/README.md)与 [PLAN](PLAN.md)。

| 项目 | 内容 |
|---|---|
| 文档版本 | V1.1（2026-10-20 修订；2026-10-22 未完成成员工具审批接续增补） |
| 前置文档 | [MetaAgent 架构设计文档 V1.1](MetaAgent-架构设计文档.md) |
| 目标读者 | MetaAgent 与 CSP adapter 的开发者 |
| 代码依据 | `../openjiuwen-latest/agent-core`，`develop@4cd9df83855c0504af314655fbd7e2f34a0442fa` |
| 状态 | 双路径、本地 L1/L2/L3、团队组件/worker 审批交接及单 Agent/团队 A2A 已实现局部链路；单 Agent 与 Team/A2A PostgreSQL 审批交接已接通，完整成员恢复与真实平台继续实施 |

> 约定：标注【内核】的接口须以固定提交的源码签名为准；标注【新建】的接口为本期开发内容。代码块用于描述接口/控制流，省略项及辅助函数不是已存在的内核 API，也不代表可直接运行的实现。

## 0. 本轮修订与源码核对

| 修订项 | 固定提交下的依据 | 本文处理 |
|---|---|---|
| Workflow 条件路由 | `core/workflow/_workflow.py::add_conditional_connection`；`core/graph/graph.py::add_conditional_edges` | Router 只首次分派；插件包装节点返回结果后再选择 fallback；每个源节点只注册一个 router |
| Harness 配置 | `harness/schema/deep_agent_spec.py::DeepAgentSpec`、`resolve_parts/build`；`harness/factory.py::DeepAgentParts` | 全量 MetaAgentSpec 交给装配器；tools/rails/subagents 先物化，checkpoint/evolution/budget 独立注入 |
| 团队扩展 | `harness_providers/factory.py::register_harness_provider`；`agent_teams/external/member_runtime.py::ExternalHarnessMemberRuntime`；`agent_teams/schema/team.py::ExternalCliAgentSpec` | 使用真实 provider/runtime 扩展点；Leader/单成员目标仍有集成门禁，不伪造 `factory_name` |
| Runner 团队入口 | `core/runner/team_runner.py::run_agent_team` / `run_agent_team_streaming` | 常规入口传 TeamAgentSpec 或已激活的 team_name；不传已 build 的 TeamAgent |
| Rail 回调 | `core/single_agent/rail/base.py::ToolCallInputs`；`harness/rails/AGENTS.md` | 工具参数/结果位于 `ctx.inputs`；priority 越大越先，不能声称 priority=10 最先执行；耐久执行由工具包装器保证 |
| 恢复/互斥/A2A | MetaAgent 自身契约，不能由内核接口存在直接推导 | 操作 ID + durable journal、快慢路径统一副作用包装、续约/fencing、worker 内部 A2A listener |

上下游辅助仓固定为 `agent-runtime main@34ed6e86b99fab9b3f07d9f063efc1692ab365d2`（agent-studio 子模块 `3d86cdeed137e5ebe19ba7f8bd03273768e480b3`）和 `jiuwenswarm develop@f7e7dd5c82d4908276a8524fe94ceda41a8ae354`。本轮未完成这些仓库与拟建 CSP/AgentGov 服务的端到端兼容验证。

M1 的实测证据与未验收项见 [风险原型验证记录](docs/compatibility/m1-validation.md) 和 [ADR-0001](docs/adr/0001-m1-integration-boundaries.md)。原型与测试位于 `spikes/` / `tests/`，不是下文生产接口已经实现的证明；配置物化、预算记录绑定与经验 rails 安装不能替代完整行为验收。

**M2/M3 已实现接口**：当前 wheel 的公开入口为 `MetaBootLoader`、`MetaAgentSpec`、`MetaBaseAgent`、`AgentResult`、`AgentEvent` 和 `ExecutionIdentity`；插件构建/路由类型位于 `meta_agent.registry`、`meta_agent.routing`、`meta_agent.spec.fastpath`，CLI 为 `meta-agent validate/draw`。实际样例见 `examples/minimal_agent/` 和 `examples/refund_fastpath/`。实现决策见 [ADR-0002](docs/adr/0002-m2-local-runtime.md)、[ADR-0003](docs/adr/0003-m3-fastpath-contract.md)，证据见 [M2 记录](docs/compatibility/m2-validation.md)、[M3 记录](docs/compatibility/m3-validation.md)。下文完整接口仍含 M4–M7 设计草案，以已实现入口及 ADR 为准。

```python
from meta_agent import MetaBootLoader

async def main():
    async with await MetaBootLoader("./business_package").boot() as agent:
        result = await agent.invoke("你好", session_id="s1", request_id="r1")
        print(result.result_type, result.output, result.usage)
```

M2 配置中 `deep_agent` 使用完整原生 DeepAgentSpec 类型，未知字段与未支持的启用项直接拒绝；必须提供显式 agent ID、模型、workspace、skills 和 trace 目录。`load()` 不分配运行时资源；`boot()` 物化 provider 并管理 Runner。相同 product/agent 只允许一个存活对象，同 session 拒绝并发；同一事件循环的不同 Agent 共享 Runner，checkpoint 配置必须相同，宿主不得另外操纵该单例。

`stream()` 直接转发 child 的增量文本，外层 End 产生唯一最终结果。用户输入中断返回 `input_required`；续跑使用原 session、新 request ID 和答案，execution ID 不变。活动 TaskLoop 的 `follow_up` 进入原生队列；空闲会话的后续轮次使用 `invoke`。失败/取消后的 session 不重放，重复 request ID 被拒绝。默认模式正常关闭取消并等待任务、释放本对象的 checkpoint；普通 persistence 配置不提供冷恢复。显式 LocalRecovery 模式保留 checkpoint，并提供下述 resume 契约。

M2 JSONL 仅记录元数据和真实模型回调计数；token 数来自模型实际 usage，未报告时 `usage_reports=0`，不能推导预算已执行。trace 运行中写入失败在 `usage.trace_errors` 中暴露。M2 交付时 operation journal/lease 只有类型接口；M4 首批现已实现本地独立效果边界，见下段。skills 的原生读取已接入，默认附加的 shell/file 工具被关闭；子代理暂时拒绝，避免默认系统能力超出本期边界。

**M3 可执行契约**：`fastpath.enabled: true` 与 `plugins_dir` 启用插件。manifest 使用 `name/version/entry/intent`，入口为 `async build(context)`；返回 `context.workflow()` 创建的 PluginWorkflow。加载时保存源文件/资源字节与 digest，按逻辑名选择最高三段数字版本或显式 name@version。每会话建立独立原生图；禁止嵌套 DeepAgentComp、环、不可达节点、不透明 graph-invoker、stream edges 和自动重试。工厂是受信任构图代码，不得执行业务副作用。

`invoke/stream(..., context={...})` 接收可信 JSON 上下文。Skill 元数据/regex/可选 embedding/独立 when/可选 classifier 依次匹配；所有候选及缓存命中都通过 when。缓存隔离 scope、query、context、配置/插件版本和自适应 generation。embedding/classifier 通过宿主注册函数调用；未配置时零模型路由开销。`route_stats()` 暴露 provider 调用及插件结果，自适应根据完成结果窗口提高 threshold 或停用，不重路由已暂停请求。

插件 End 返回 `result: PluginOutcome`。显式 failed/PluginFailure 保留来源、partial 与 completed_operations，包装器正常返回后才走 fallback 条件边；白名单或禁用 fallback 产生 `result_type="error"`。GraphInterrupt、取消、控制异常及其 cause/context 链继续传播；未知程序异常不转主路径。每次只支持一个原生交互，同时多问会拒绝而非广播答案。公开流只接收主路径专用 delta 通道和外层 End；插件内部输出不会成为第二个最终答案。`AgentResult.route` 保存实际路由，`usage.deep_agent_calls` 为真实主路径调度计数。

`meta-agent validate/draw` 校验受信任插件 import/build 并输出 JSON/Mermaid，不调用 Agent 模型。退款样例为本地内存账本：审批续跑保留 execution，成功快路径为 0 次 DeepAgent/模型调用，普通失败为 1 次。M3 `effects` 必须为空；操作 ID 上下文不代替耐久 journal，热更新/版本持久化 pin、真实外部模型和平台权限仍待后续验收。

**M4 首批已实现接口**位于 `meta_agent.checkpoint`：SQLiteRecoveryStore、DurableExecution、SideEffectExecutor、LeaseGuard、RecoverySnapshot、EffectAdapter；原生组件/工具适配器位于 `checkpoint.adapters`。JSON 参数、name/version 和操作 ID 在调用前提交，结果确认后再提交 completed；prepared/unknown 恢复只用原 ID 和原版本，缺失契约则暂停。逻辑 key 由宿主分配，参数 hash 不作为幂等身份。

```python
from meta_agent.checkpoint import DurableExecution

async def execute_approved_step(store, scope, execution_id, snapshot, adapter, args):
    async with DurableExecution(store, scope, execution_id, snapshot) as execution:
        result = await execution.executor.execute("refund/invoice-100", adapter, args)
        await execution.finish()
        return result
```

LeaseGuard 自动续约并取消失租/续约断连时的受管在途调用。lease 校验与 journal/状态写入处于同一 SQLite 事务；取消会等待 SQL 工作线程结束。关闭只释放 lease，保留 journal、逻辑身份与版本引用。制品按字节 SHA-256 保存，快照变更/制品缺失拒绝，pin 未退休禁止删除。恢复可直接枚举原效果参数，不能换 key 或切新版本绕过未知结果。

独立 Effect API 的宿主仍须在发布模型答案前 finish。新增 `MetaBaseAgent.create(..., recovery=LocalRecovery(...))` / `MetaBootLoader.boot(recovery=...)` 自动绑定 Agent execution，并把终态响应与无未决效果检查原子提交。`resume(session_id, request_id, answer=...)` 从原输入、路由、插件字节、L1/L2 和 L3 恢复；已完成结果直接读取，审批答案在使用前持久化。

L1 graph/state/updates 同事务提交；L2 通过公开 hook 暂存，在 DeepAgentComp 得到 answer/interrupt 时与 child outcome 一起提交。checkpoint 记录答案代次，消费后清理桥接层旧答案，防止崩溃后错答新问题。native graph 仅在错误/交互边界持久化，未提交模型/只读计算可重做。缺失/损坏 checkpoint、配置或 skills 漂移会停止恢复；旧 owner 不得写入。正常关闭保留状态，失去续约取消整个执行。

恢复模式的 stream 缓冲为一个终态；follow_up 尚无耐久 inbox，暂时拒绝。任意 HTTP/skill/子代理写入、工作区辅助文件、共享存储仍未统一受控；主 spec 的通用 effects/分布式开关保持关闭。M4-01/02 已验收，其余 M4 项的全部范围仍开放。[运行时证据](docs/compatibility/m4-runtime-recovery-validation.md) · [ADR-0005](docs/adr/0005-local-runtime-recovery.md) · [运行手册](docs/runbooks/local-runtime-recovery.md)。此前效果层证据：[本地记录](docs/compatibility/m4-local-effects-validation.md) · [ADR](docs/adr/0004-local-durable-effects.md) · [恢复手册](docs/runbooks/local-effects-recovery.md)。

**M4 快路径效果绑定（2026-10-22）**：`LocalRecovery.plugin_effects` 接收宿主 `EffectBinding(name, adapter, logical_key)`，adapter 必须注册在 recovery.adapters。插件 manifest 的 effects 可声明这些能力名；缺少宿主绑定时 import 前拒绝。工厂用 `context.effect(name)` 创建 EffectWorkflowComponent，公开构图记录递归验证嵌套效果节点。fallback 的 BoundEffectTool 用同一绑定的 `binding.tool(card)` 创建；同 execution/logical_key 共享 operation_id，重复调用读已提交结果，参数漂移拒绝。绑定参与恢复指纹；没有 plugin_effects 的旧配置指纹保持兼容。

FastPathOutcomeComp 在选择成功/终止/fallback 前检查全部 journal 记录；prepared/unknown 阻止路径切换，即使自定义节点吞掉效果异常也不能进入 DeepAgent。恢复模式的 completed_operations 被 journal 中的完成记录替换，另附 durable_operations（原操作 ID、适配器版本、参数、结果）；上下文仅供模型参考，防重由执行器执行。普通 M3 的无恢复上下文契约不变。带 effects 的包当前通过 Python 宿主绑定启动；CLI validate/draw 没有绑定注入入口，仍拒绝这类包。

退款样例现支持 `examples/recoverable_agent/run.py --fastpath` 和 `--fastpath --fallback`。原生审批与保留版本恢复、嵌套退款、真实进程终止、fallback 重复工具请求和未知结果暂停分别验收；全部写入面及跨主机共享存储继续开放。详见 [ADR-0006](docs/adr/0006-fastpath-effect-bindings.md) 和 [本批验证](docs/compatibility/m4-fastpath-recovery-validation.md)。

**M4 提交边界核对（2026-10-22）**：已整理 [B0–B8 支持清单](docs/compatibility/m4-supported-boundaries.md)，逐项区分 admission、route、L3 prepare/回执/completed、L1、L2+child_result、response 和 pending reconciliation。原生 post_agent 回调仅暂存状态，L2 与 child 结果共同落盘才是耐久边界；成功 super-step 的内存 state.commit 不等于 graph checkpoint。取消可能发生在事务提交之后，必须读取已存状态；B7 已提交时 resume 返回原结果，B6 未提交时模型可能重做，但受管退款不重发。

边界故障测试覆盖取消、续约断连、旧 owner 接管后恢复及各阶段冷重建，发现并修复 reconciliation 的整段取消缺口：`recover_pending` 现在由 `LeaseGuard.run` 包裹，恢复 observer 等待也随续约失败取消，之后才进入原 workflow。[本批证据](docs/compatibility/m4-boundary-validation.md)。更细成功步骤/Agent 迭代快照已形成[公开接口提案](docs/proposals/0001-native-checkpoint-boundaries.md)，尚未提交上游或实现；本次不扩展 HTTP/RPC/skill/子代理写入面和共享存储范围。

---

## 1. 总体设计约束

1. `MetaBaseAgent` 组合原生 `DeepAgent`，行为注入经 Rail；图校验/包装可继承公开 Workflow/SubWorkflowComponent 扩展点，保持原生调度与 checkpoint，不修改私有内核或重写执行循环；
2. 快路径插件子图禁止包含 `DeepAgentComp`（编译期校验，违反即拒绝注册）；
3. 一切跨组件共享状态走 `session.update_global_state()`（组件边界提交，checkpoint 语义一致）；
4. 一切外部副作用必须经过 SideEffectExecutor 的执行前/后耐久提交，覆盖主路径、子代理及快路径工具/HTTP/skill 脚本；未接入的插件拒绝进入自动恢复模式；
5. 同 `(product_id, agent_id, session_id)` 严格串行；本地锁 + 多副本必选的可续约租约，冲突排队/409；
6. 所有配置模型用 Pydantic，YAML/JSON 双格式，`model_validate()` 解析；
7. 快路径普通错误按白名单结束或转主路径；INPUT_REQUIRED、取消、失租、存储不可用和副作用未决不得转为普通 fallback（KAR-12）；
8. 无插件包注入时 DAG 必须退化为纯主路径（Start→DeepAgentComp→End），不得残留路由组件。

## 2. 代码结构

```
platform-repo/
├── meta_agent/
│   ├── __init__.py                    # 导出 create_meta_base_agent / create_meta_agent_team / MetaBootLoader
│   ├── spec/
│   │   ├── meta_agent_spec.py         # MetaAgentSpec
│   │   ├── meta_team_spec.py          # MetaAgentTeamSpec
│   │   ├── plugin_manifest.py         # WorkflowPluginManifest / 校验器
│   │   └── csp_config.py              # CspAdapterConfig
│   ├── base_agent/
│   │   ├── meta_base_agent.py         # MetaBaseAgent
│   │   ├── router/
│   │   │   ├── fast_path_router.py    # FastPathRouter
│   │   │   ├── decision.py            # RouteDecision / RouteStats
│   │   │   ├── strategy.py            # RouterStrategy SPI + 3 内置实现
│   │   │   └── threshold.py           # AdaptiveThreshold
│   │   └── harness_wrap.py            # DeepAgent 装配（复用 resolve_deep_agent_parts）
│   ├── orchestrator/
│   │   ├── meta_orchestrator.py       # MetaOrchestrator（持有 Workflow + 写锁）
│   │   ├── dag_compiler.py            # DAGCompiler
│   │   └── comps/
│   │       ├── fastpath_outcome_comp.py # 插件执行包装；结果归一化与后置路由
│   │       ├── deep_agent_comp.py     # DeepAgentComp
│   │       ├── router_comp.py         # RouterComp
│   │       └── merge_comp.py          # MergeComp
│   ├── registry/
│   │   ├── meta_registry.py           # MetaRegistry（三槽位 + DAG 写锁）
│   │   └── plugin_loader.py           # 插件包扫描/构建/版本管理
│   ├── checkpoint/
│   │   ├── meta_checkpoint_manager.py # CheckpointManager（L3 编排 + 版本迁移）
│   │   ├── idempotency.py             # IdempotencyJournal
│   │   ├── side_effect_log.py         # SideEffectLog
│   │   └── side_effect_executor.py    # 工具/HTTP/RPC/skill 写入的统一耐久执行边界
│   ├── trace/
│   │   ├── trace_file_sink.py         # MetaTraceFileSink（JSONL）
│   │   └── evolution_telemetry.py     # 进化事件打点
│   ├── team/
│   │   ├── meta_agent_team.py         # MetaAgentTeam
│   │   ├── recovery.py                # 团队恢复封装
│   │   └── harness_provider.py        # MetaAgentHarnessProvider（集成门禁项）
│   ├── rails/
│   │   ├── fast_path_bridge_rail.py   # FastPathBridgeRail
│   │   └── checkpoint_rail.py         # CheckpointRail（关联操作上下文/观测，不替代执行包装）
│   ├── boot/
│   │   ├── boot_loader.py             # MetaBootLoader
│   │   ├── path_contract.py           # 固定路径约定
│   │   └── validators.py              # 包校验（meta-agent validate CLI 复用）
│   └── cli.py                         # meta-agent validate / draw / doctor
├── meta_agent_adapter/
│   ├── agent_gov/client.py            # AgentGovClient（注册/心跳/下线，契约见 5.2）
│   ├── model/infer_schedule_client.py # InferScheduleModelAdapter
│   ├── memory/memory_service.py       # MemoryServiceAdapter
│   ├── mcp/mcp_gateway.py             # McpGatewayAdapter
│   ├── skills_runtime/skills_rt.py    # SkillsRuntimeAdapter
│   └── ops/ops_reporter.py            # OpsAdapter
└── agentworker/
    ├── main.py                        # Runner + 仅供 AgentGov 的内部 A2A + 探针
    └── Dockerfile
```

## 3. 配置与数据模型

### 3.1 MetaAgentSpec（单个 MetaBaseAgent 的配置）

内嵌【内核】`openjiuwen.harness.schema.deep_agent_spec.DeepAgentSpec`（agent_teams 侧为兼容再导出；字段以固定提交为准，不硬编码“26 字段”）：

```python
class MetaAgentSpec(BaseModel):
    # ===== 内核段：直接透传 create_deep_agent / DeepAgentSpec =====
    deep_agent: DeepAgentSpec                      # model/system_prompt/tools/mcps/subagents/rails/
                                                   # enable_task_loop/enable_async_subagent/max_iterations/
                                                   # workspace/skills 等；不包含下面的 MetaAgent 扩展段
    # ===== MetaAgent 扩展段 =====
    fastpath: FastPathConfig = FastPathConfig()    # 快路径路由配置（3.3）
    evolution: EvolutionConfig = EvolutionConfig() # 进化配置（3.4）
    budget: BudgetConfig = BudgetConfig()          # GoalStopConfig 透出（3.5）
    checkpoint: CheckpointConfig = CheckpointConfig()  # （3.6）
    concurrency: SessionLeaseConfig = SessionLeaseConfig()
    trace: TraceConfig = TraceConfig()             # （3.7）
    csp: CspAdapterConfig = CspAdapterConfig()     # adapter 绑定（3.8）
```

业务包中的 `meta_agent.yaml`（skills + agent 配置包，**必选**）：

```yaml
# /opt/meta_agent/skills_agent_cfg/meta_agent.yaml
meta_agent:
  deep_agent:
    model:
      model_client_config: { client_provider: OpenAI, api_base: "http://inferschedule.csp:8080/v1", api_key: "${ENV:IS_KEY}" }
      model_request_config: { model: qwen-max } # 示例：平台提供 OpenAI-compatible 端点；适配器仍负责平台策略
    system_prompt: |
      你是 X 产品的智能助手……
    skills: ["./skills"]                # 相对包根目录；SKILL.md frontmatter: name/description
    tools: []
    subagents:
      - agent_card: { id: researcher, name: researcher, description: "研究子代理" }
        system_prompt: "完成分配的研究任务并提供依据。"
        skills: ["./skills/researcher"]
    enable_task_loop: true
    enable_async_subagent: true
    max_iterations: 15
  fastpath:
    enabled: true
    plugins_dir: ./fastpath_plugins     # 可选；缺省读全局 META_AGENT_FASTPATH_DIR
    router:
      default_strategy: rule_embedding  # rule_embedding | llm | skill_meta
      llm_classifier: { model_name: qwen-turbo, threshold: 0.8 }
      session_cache_ttl: 600            # query+上下文/权限/插件版本缓存；使用前重验 when
      adaptive: { min_hit_rate: 0.6, down_weight_after: 50 }  # 命中率低于 60% 且样本≥50 自动降权
  evolution:
    enabled: true
    auto_save: false                    # 经验写入 evolutions.json 是否免审批
    language: cn
  budget: { max_attempts: 20, token_budget: 200000, stop_strategy: hybrid }
  checkpoint: { backend: redis, schema_version: 1 }
  concurrency: { distributed: true, lease_ttl_s: 300, renew_interval_s: 60, conflict: reject }
  trace: { file_dir: /var/log/meta_agent/trace, rollout: daily, buffer_size: 256 }
  csp:
    infer_schedule: { endpoint: http://inferschedule.csp:8080, api_key: "${ENV:IS_KEY}" }
    memory_service: { enabled: true, endpoint: http://memory.csp:8081 }
    mcp_gateway:    { enabled: true, endpoint: http://mcp.csp:8082 }
    skills_runtime: { enabled: false, endpoint: "" }
    agent_gov:      { enabled: true, endpoint: http://agentgov.csp:9000,      # 镜像模式必选：注册/心跳
                      heartbeat_interval_s: 30, heartbeat_ttl_s: 90 }
    ops:            { enabled: true, endpoint: http://ops.csp:8083 }
```

Boot 先解析顶层 `meta_agent` 与 `${ENV:...}`，再校验 MetaAgentSpec。上例使用内核 TeamModelConfig 的 `model_client_config/model_request_config` 结构和 SubAgentSpec 的必需字段；如平台使用自定义 Model client，必须先注册并验证相应 provider，不能仅写一个虚构的 provider 名称。

### 3.2 MetaAgentTeamSpec（多 Agent 编排配置，最上层）

```python
class MetaAgentTeamSpec(BaseModel):
    team: TeamAgentSpec                          # 【内核】openjiuwen.agent_teams.TeamAgentSpec
    members: dict[str, MetaAgentSpec]            # MetaAgent 侧期望成员配置，不是内核直接支持的成员类型
    binding: dict[str, str] = {}                 # MetaAgent 自定义映射；须由已验收的 team adapter 解释
```

`meta_team.yaml`（单成员目标配置示意；§4.7 门禁通过前不可宣称开箱可用）：

```yaml
team:
  team_name: default_team
  lifecycle: persistent
  teammate_mode: build_mode
  spawn_mode: inprocess
  leader: { member_name: team_leader, persona: 任务协调专家 }
  agents:
    leader: <内嵌或引用 members.agent_main>
  storage: { type: sqlite, params: { connection_string: /var/lib/meta_agent/team.db } } # 单实例验证用
  enable_hitt: true
  enable_permissions: false
members:
  agent_main: { <MetaAgentSpec，见 3.1> }
binding: { leader: agent_main }
```

> `team.agents` 是 role→DeepAgentSpec，不是任意 MetaBaseAgent 实例注册表。多成员的 provider、启动、序列化和恢复映射见 §4.7；仅增加 `members` 不会使内核自动调用 MetaAgent DAG。多副本部署还须有跨实例可恢复的 team DB，Redis checkpoint 不能替代本地 SQLite 数据。

### 3.3 FastPathConfig 与插件 manifest

```python
class FastPathConfig(BaseModel):
    enabled: bool = True
    plugins_dir: str | None = None
    plugins: list[str] = []                      # 显式启用的插件名；空=全部加载
    router: RouterConfig = RouterConfig()

class RouterConfig(BaseModel):
    default_strategy: Literal["rule_embedding", "llm", "skill_meta"] = "rule_embedding"
    llm_classifier: LlmClassifierConfig | None = None
    session_cache_ttl: int = 600
    adaptive: AdaptiveConfig = AdaptiveConfig()

class WorkflowPluginManifest(BaseModel):         # 插件包根 manifest.json（packageType=plugin 对齐内核）
    name: str                                    # 插件唯一名；本期只允许 [a-z][a-z0-9_-]*
    version: str                                 # semver
    packageType: Literal["plugin"] = "plugin"    # MetaAgent 自有 manifest 字段，不直接交给内核解析器
    entry: str                                   # "workflow.py:build" — 返回 Workflow 实例的工厂
    intent: IntentMetadata
    fallback_to_harness: bool = True             # 失败兜底总开关：false = 全部错误直接结束
    fallback_whitelist: list[str] = []           # 错误码/异常类名白名单：命中即直接结束，不进主路径
    min_meta_agent: str | None = None            # 兼容的底座最低版本
    effects: list[EffectContract] = []           # 外部写入注册名、去重键传递/查询方式；详见 4.8

class IntentMetadata(BaseModel):
    description: str                             # 供 LLM 分类器的类别描述
    examples: list[str] = []                     # 供 embedding 库的例句
    rules: list[str] = []                        # 正则规则（rule_embedding 策略）
    when: str | None = None                      # 声明式条件表达式（对 session 全局状态求值）
    threshold: float = 0.8                       # 该插件的命中阈值 θ_i
    tags: list[str] = []
```

插件包目录结构（**可选**业务包）：

```
fastpath_plugins/
└── refund_fastpath/
    ├── manifest.json            # 如上
    └── workflow.py              # async def build(**ctx) -> Workflow
```

`workflow.py` 契约（Executable）：

```python
async def build(**ctx) -> Workflow:
    """由 MetaBootLoader/Registry 调用；ctx 注入: session_factory, resource_mgr, model_provider, effect_executor。
    约束（编译期校验）：
    - 子图只能含 Start/End/LLMComponent/ReActAgentComp/ToolComponent/HttpRequestComponent/
      IntentDetectionComponent/Branch/Loop/SubWorkflow（后者深度受 workflow_max_nesting_depth 约束）
    - 禁止含 DeepAgentComp / 任何 harness 节点
    - 外部写入必须调用 effect_executor；嵌套子图、ReAct 工具与 skill 脚本也受此约束
    """
```

### 3.4 EvolutionConfig

```python
class EvolutionConfig(BaseModel):
    enabled: bool = True
    auto_save: bool = False
    language: Literal["cn", "en"] = "cn"
    skills_dir: str = "./skills"                 # 经验文件 evolutions.json 所在 skill 目录
    reviewer_subagent: bool = True               # evolution_reviewer 稳定子代理审批
```

映射【内核】：`SkillUseRail(skills_dir, skill_mode, ...)`、`configure_skill_evolution(agent, skills_dir, llm, model, trajectory_span_processor, auto_save, ...)`、`SkillEvolutionRail`(priority 80)、`SkillCreateRail`(priority 85)、`EvolutionInterruptRail`。

### 3.5 BudgetConfig

```python
class BudgetConfig(BaseModel):
    max_attempts: int = 20
    token_budget: int = 200000
    stop_strategy: Literal["agent_report", "transcript", "hybrid"] = "hybrid"
```

目标映射【内核】`GoalStopConfig` / `GoalRecord(max_attempts, token_budget)` / `GoalAssessment`【源码 harness/goal/schema.py】。

**M1 验证修正**：GoalManager 可绑定并恢复 max_attempts/token_budget，但固定基线的 `TaskCompletionRail.set_goal_manager()` 内部创建默认 `GoalEvaluator()`，尚无已验证的非默认 stop_strategy 注入路径。原型只接受 hybrid，其他策略明确拒绝；不得静默忽略配置。token 计量、实际预算停止及 TaskLoop 集成仍须验收，不能由 GoalRecord 保存成功推导预算已经生效。

### 3.6 CheckpointConfig

```python
class CheckpointConfig(BaseModel):
    backend: Literal["in_memory", "persistence", "redis"] = "redis"
    schema_version: int = 1
    redis: RedisConf | None = None               # url, cluster_mode, ttl: {default_ttl, refresh_on_read: true}
    persistence: PersistenceConf | None = None   # db_type: sqlite|shelve, db_path, db_timeout, db_enable_wal
    side_effect: SideEffectConf = SideEffectConf()   # L3
class SideEffectConf(BaseModel):
    enabled: bool = True
    journal_namespace: str = "meta-side-effect"      # checkpoint key 命名空间
    replay_on_recover: bool = True
    require_durable_ack: bool = True             # prepare/result 提交返回前必须获得耐久确认
    unknown_policy: Literal["interrupt"] = "interrupt"

class SessionLeaseConfig(BaseModel):
    distributed: bool = True                    # 多副本部署强制 true；单实例才可关闭
    lease_ttl_s: int = 300
    renew_interval_s: int = 60                   # 校验：0 < interval < TTL / 3
    conflict: Literal["reject", "queue"] = "reject"
```

注入点：`RunnerConfig.checkpointer_config = CheckpointerConfig(type=backend, conf={...})` → `Runner.set_config(); await Runner.start()`【内核 Checkpointer 机制】；Redis 后端需 `from openjiuwen.extensions.checkpointer.redis import checkpointer` 预导入注册 provider。

L3 存储另需原子 insert-if-absent/CAS、耐久确认与 fencing 能力；不能因 `graph_store()` 可读写就认定它满足这些条件。Redis AOF/复制确认、TTL 和恢复保留期由部署契约指定；仅设置 `refresh_on_read` 不构成耐久性证明。Runner 是进程级共享配置，成员 backend 冲突时 boot 拒绝启动。

### 3.7 TraceConfig

```python
class TraceConfig(BaseModel):
    otel: OtelConf | None = None                 # exporter_type/endpoint/service_name/sample_rate/redaction…
    file_dir: str = "/var/log/meta_agent/trace"  # 平台独立日志轨迹文件目录
    rollout: Literal["hourly", "daily"] = "daily"
    buffer_size: int = 256                       # 双缓冲异步刷盘条数
    include_categories: set[str] = {"llm", "tool", "evolution", "route"}
```

### 3.8 CspAdapterConfig

```yaml
csp:
  infer_schedule: { endpoint: str, api_key: str, timeout_s: 30, retry: {max: 3, backoff: exponential},
                    circuit_breaker: {failure_rate: 0.5, window_s: 60} }
  memory_service: { enabled: bool, endpoint: str, scope_ttl_days: 30 }     # 可选
  mcp_gateway:    { enabled: bool, endpoint: str, server_name: "csp-mcp" } # 必选
  skills_runtime: { enabled: bool, endpoint: str, timeout_s: 10 }          # 可选独立进程
  agent_gov:      { enabled: bool, endpoint: str, register_retry: 5,       # 镜像模式必选：实例注册/心跳
                    heartbeat_interval_s: 30, heartbeat_ttl_s: 90 }
  ops:            { enabled: bool, endpoint: str, report_interval_s: 60 }
```

## 4. 核心类接口设计

### 4.1 MetaBootLoader【新建】

```python
class MetaBootLoader:
    def __init__(self, cfg_root: str, env: Mapping[str, str] | None = None): ...

    async def boot(self) -> BootResult:
        """启动主流程：
        1. 读 META_AGENT_CFG_ROOT 下 meta_team.yaml / meta_agent.yaml / csp.yaml
        2. 装配 CspAdapters（推理→记忆→MCP→SkillsRT→Ops，按 enabled）
        3. RunnerConfig(checkpointer_config=...) → Runner.set_config → await Runner.start()
        4. 初始化 OTEL tracer + TrajectorySpanProcessor 注册 + MetaTraceFileSink
        5. _load_mandatory_package(): skills+agent 配置包（缺则 raise BootError，进程不 ready）
        6. _load_fastpath_plugins(): 扫描 plugins_dir，逐包 validate+build+注册（可选，失败告警不阻断）
        7. 创建 MetaBaseAgent；启用 Team 时检查 §4.7 能力门禁并构造 TeamAgentSpec（未通过则明确拒绝 Team）
        8. 校验 L3/租约/后端一致性；有外部写入的生产配置禁止关闭 L3
        9. 启动并自检内部 A2A listener → 本地 ready → AgentGovClient.register()（镜像模式且 enabled；
           重试 register_retry 次，失败进 degraded + 告警）
           → 启动心跳任务；AgentGov 不可用不影响组件模式与本地管理面
        10. OpsAdapter.report_boot()
        """

    def _load_mandatory_package(self) -> MetaAgentSpec: ...
    def _load_fastpath_plugins(self) -> list[LoadRecord]: ...

@dataclass
class BootResult:
    agent: MetaBaseAgent | None                  # 单 Agent 入口
    team: MetaAgentTeam | None                   # 通过 GATE-TEAM 后才可启用
    registry: MetaRegistry
    orchestrators: dict[str, MetaOrchestrator]     # member_name -> orchestrator（管理面用）
    adapters: CspAdapters
    agent_gov: AgentGovClient | None
    trace_sink: MetaTraceFileSink
```

### 4.2 MetaBaseAgent【新建】

```python
class MetaBaseAgent:
    """单 Agent 底座：FastPathRouter + 快路径插件集 + DeepAgent 主路径，统一由 MetaOrchestrator DAG 调度。"""

    def __init__(self, spec: MetaAgentSpec, registry: MetaRegistry,
                 adapters: CspAdapters, checkpoint: CheckpointManager,
                 trace_sink: MetaTraceFileSink): ...

    @classmethod
    async def create(cls, spec: MetaAgentSpec, *, services) -> MetaBaseAgent:
        """装配顺序：
        1. harness = harness_wrap.build(spec, adapters, services)   # 传完整 MetaAgentSpec，见 4.3
        2. plugins = await load_enabled_plugins(spec.fastpath)      # enabled=false 则为空
        3. router = build_router(...) if plugins else None         # 无插件时零路由实例
        4. orchestrator = await DAGCompiler().compile(spec, router, plugins, harness)  # 见 4.5
        """

    # ===== 对外标准接口（对齐【内核】BaseAgent 语义）=====
    async def invoke(self, inputs: dict, session: str | Session = None,
                     context: ModelContext = None) -> MetaAgentOutput: ...
    async def stream(self, inputs: dict, session=None, context=None,
                     stream_modes=None) -> AsyncIterator[WorkflowChunk]: ...
    async def follow_up(self, msg: str, session: str) -> None: ...     # 透传 DeepAgent.follow_up
    async def steer(self, session: str) -> None: ...                   # 透传 DeepAgent.steer
    async def abort(self, session: str) -> None: ...                   # 透传 DeepAgent.abort
    async def switch_mode(self, session: str, mode: Literal["plan", "auto"]) -> None: ...

    # ===== 插件管理（管理面）=====
    async def load_plugin(self, pkg_path: str) -> LoadRecord: ...      # 版本化+增量编译+原子切换
    async def unload_plugin(self, name: str, version: str | None = None) -> list[str]: ...
    async def list_plugins(self) -> list[PluginInfo]: ...

    async def draw(self, output_format: str = "mermaid") -> str | bytes:
        """导出统一 DAG（含快路径子图标记 expand_subgraph=True）。"""

@dataclass
class MetaAgentOutput:
    result: dict | list[WorkflowChunk]
    state: WorkflowExecutionState           # COMPLETED / INPUT_REQUIRED
    route: RouteDecision                    # 本请求实际走路径（观测）
    usage: TokenUsage                       # 从 DeepAgentState / TRACE 汇总
```

**session 串行保证**（`SessionLeaseManager` 为【新建】，与 checkpointer 分离）：

```python
async def invoke(self, inputs, session=None, context=None):
    session_id = normalize_session_id(session, inputs)  # Session 对象取其 ID，不能直接当锁 key
    key = (self.product_id, self.agent_id, session_id)
    async with self._session_locks.acquire(key):
        async with self._leases.hold(key, self.spec.concurrency) as lease:
            # hold: 获取失败抛 SessionConflict；成功后带 owner+fencing token 并自动续约
            execution = await self._executions.open_or_resume(inputs, key, lease)
            # 恢复沿用 execution_id、固定图/插件版本和 operation_id；新请求另分配
            runtime = await self._runtimes.for_session(key, execution.graph_version)
            return await lease.run_guarded(runtime.invoke(execution, context))
```

`hold` 在 finally 中按 owner 比较后释放，禁止删掉后来者的锁；续约失败/存储不可用使 `run_guarded` 取消任务并拒绝继续派发工具。checkpoint 与 journal 写入必须原子验证 fencing，不能仅执行前查一次锁。外部服务若不能检查 fencing，必须支持业务去重/结果查询；无法判断的在途写操作暂停对账，不允许新 owner 盲重放。`stream` 的锁/租约覆盖整个 async iterator 生命周期，客户端断开/取消也走 finally；控制消息通过队列进入当前运行时，不另外启动一次 invoke。

### 4.3 Harness 装配（harness_wrap）【新建】

装配入口接收完整 MetaAgentSpec。内核 `DeepAgentSpec.resolve_parts()` / `build()` 会解析 RailSpec、BuiltinToolSpec、SubAgentSpec；不能把这些声明对象未经物化直接传给低层工厂。下例 `resolve_meta_parts`、`install_effect_wrappers`、`configure_goal_budget`、`services` 均为【新建】MetaAgent 接缝；内核依据为 `harness/factory.py` 与 `harness/schema/deep_agent_spec.py`。

```python
def build(spec: MetaAgentSpec, adapters: CspAdapters, services) -> DeepAgent:
    # 返回已物化的 DeepAgentParts；保留全部内核字段，CSP model/MCP 在此绑定
    parts = resolve_meta_parts(spec.deep_agent, adapters, services.build_context)
    parts.rails.append(FastPathBridgeRail(services.registry))
    if spec.checkpoint.side_effect.enabled:
        install_effect_wrappers(parts, services.effects)   # 主路径及递归子代理的工具执行边界
        parts.rails.append(CheckpointRail(services.effects))
    agent = DeepAgent(parts.config.card)
    apply_deep_agent_parts(agent, parts)
    configure_goal_budget(agent, spec.budget)              # 每个逻辑任务绑定/恢复其 GoalRecord
    if spec.evolution.enabled:
        configure_skill_evolution(agent, skills_dir=spec.evolution.skills_dir,
                                  llm=services.evolution_model,
                                  model=services.evolution_model_name,
                                  trajectory_span_processor=services.trajectory_processor,
                                  auto_save=spec.evolution.auto_save,
                                  language=spec.evolution.language)
    return agent
```

`resolve_meta_parts` 的实现要求：按内核 spec 物化 tools/rails/subagents/workspace，递归绑定 CSP 模型/MCP；把最终模型和已物化参数交给 `resolve_deep_agent_parts`，默认 rail 仅由内核装配一次。不能只构建一半字段或静默丢失配置。`checkpoint/evolution/budget` 始终从外层 spec 读取；`checkpoint.side_effect.enabled` 是唯一 L3 开关。budget 的创建/恢复与实际 token 计量映射须单测，不以“字段存在”代替预算生效。

### 4.4 FastPathRouter【新建】

```python
@dataclass
class RouteDecision:                      # 一切路由产出的统一结构，须可序列化（checkpoint L2）
    matched: bool
    plugin: str | None                    # 插件名
    plugin_version: str | None
    strategy: str                         # skill_meta | rule | embedding | llm | condition
    confidence: float
    threshold: float                      # 实际使用的 θ（自适应调整后）
    reason: str
    latency_ms: int
    ts: float

class RouterStrategy(Protocol):           # SPI：未来支持业务插件化加载
    name: str
    async def match(self, query: str, session: Session, ctx: RouterContext) -> RouteDecision | None: ...

class FastPathRouter:
    def __init__(self, cfg: RouterConfig, registry: MetaRegistry,
                 checkpoint: CheckpointManager, llm_classifier: IntentDetectionComponent | None): ...

    async def route(self, query: str, session: Session) -> RouteDecision:
        """三层匹配（命中即返回）：
        1. 缓存键=query_hash+上下文/权限/图版本；命中仍重验动态 when
        2. SkillMetadataStrategy   — skills 常驻元数据精确/前缀命中（免 LLM）
        3. RuleEmbeddingStrategy   — 规则正则 → embedding 相似度（θ_i 可每插件不同）
        4. DeclarativeConditionStrategy — intent.when 对 session 全局状态求值；
           所有前序策略选中的插件也必须通过该条件，不能提前绕过
        5. （可选）LlmClassifierStrategy — IntentDetectionComponent，category=插件意图描述
        全部未命中 → RouteDecision(matched=False)
        副作用：decision 写 session 全局状态 __route_decision__；checkpoint.save_route_decision()；
                trace_sink.emit_route(decision)
        """

    def on_result(self, decision: RouteDecision, outcome: Literal["hit", "miss", "fail"]) -> None:
        """RouteStats 计数；AdaptiveThreshold 判定降权（提高 θ_i / 摘除，转 Harness 兜底）。"""

class AdaptiveThreshold:
    def adjust(self, plugin: str, stats: RouteStats) -> float | None:
        """窗口内样本 ≥ down_weight_after 且命中率 < min_hit_rate → 返回提升后的 θ；连续 N 窗口 → None（摘除）。"""
```

### 4.5 DAGCompiler / MetaOrchestrator【新建】

编译器先生成不可变的 graph_version 和插件版本/digest 快照，再按以下边表构图。`WP_i = FastPathOutcomeComp` 是【新建】组件，组合内核 `components/flow/workflow_comp.py::SubWorkflowComponent`（`invoke` 输入为 `inputs/config`，内部 `is_sub=True`）并处理普通执行失败；不得丢掉内核子图会话及 graph-invoker 语义。每个源节点只调用一次 `add_conditional_connection`。

| 源节点 | 目标/条件 | 说明 |
|---|---|---|
| Start | RouterComp（有启用插件）/ DeepAgentComp（无插件） | 无插件时不实例化 router |
| RouterComp | 选定的 WP_i / DeepAgentComp | 首次分派；不判断尚未发生的插件错误 |
| WP_i | MergeComp / TerminalEndComp / DeepAgentComp | 包装节点正常返回成功/普通错误后，唯一条件边求值 |
| DeepAgentComp | MergeComp | 未命中或允许 fallback |
| MergeComp | End | OR 汇合；每操作仅一个最终输出 |
| TerminalEndComp | End | 白名单/禁用 fallback 的错误结果 |

`MergeComp` 使用 `wait_for_all=False`，不得等待未选中的分支；显式传递 `query/execution_id` 输入及最终输出。`when` 检查、图/版本选择与结果路由使用同一份快照，禁止在旧图执行中查询当前激活版本的 manifest。

```python
class DAGCompiler:
    def __init__(self, max_nesting_depth: int = 5): ...

    async def compile(self, spec: MetaAgentSpec, router: FastPathRouter | None,
                      plugins: list[LoadedPlugin], harness: DeepAgent) -> "MetaOrchestrator": ...

def route_fn(session) -> str:
    d = session.get_global_state("__route_decision__")  # 持久化的是 dict
    if d["matched"]:
        return f"wp_{d['plugin']}"
    return "harness"

def make_outcome_router(manifest):
    # manifest 为本图固定版本快照。内核回调只传 session，不能再要求 registry 参数。
    def outcome_router(session) -> str:
        outcome = session.get_global_state("__fastpath_outcome__")
        if outcome["status"] == "success":
            return "merge"
        if outcome["status"] != "failed":
            raise RuntimeError("control/unknown state must suspend before routing")
        err = outcome["error"]
        if not manifest.fallback_to_harness:
            return "terminal"
        if err["code"] in manifest.fallback_whitelist or err["exc_type"] in manifest.fallback_whitelist:
            return "terminal"
        return "harness"
    return outcome_router
```

`FastPathOutcomeComp` 的执行契约：

1. 新逻辑操作初始化 `__fastpath_outcome__` / `__fastpath_partial__`，恢复同一操作保留原状态；不能把上轮失败带到新请求。
2. 插件成功时保存结果并返回 `success`；显式失败/允许捕获的普通异常转 `failed`，再走上面的条件边。取消、失租、持久化故障和 SideEffectUnresolved 必须向上抛给控制层，禁止兜底。
3. INPUT_REQUIRED 不是错误：保留 child workflow/session 的稳定 ID 和交互位置，用外层 `session.interact()` 桥接；恢复输入映射回原子图。失败时不能新建 child session 重跑。此桥接是实现验收项。
4. 自动 fallback 前先检查 L3：若任何写操作结果未决，暂停对账；已完成操作可引用其 operation_id/结果，主路径只能复用该身份，不能凭自然语言提示自行重复写入。
5. 快路径输出默认暂存，成功/INPUT_REQUIRED 后才发布。若以后支持提前输出，必须新增 attempt/replace/commit 消费协议并验收；本期不做失败后无标记拼接两段最终答案。

**MetaOrchestrator**：

```python
class MetaOrchestrator:
    workflow: Workflow
    _dag_lock: asyncio.Lock                    # 插件热更新写屏障

    async def invoke_with_plugin_swap(self, *args, **kwargs): ...
    async def swap_plugin(self, old: LoadedPlugin, new: LoadedPlugin) -> None:
        """构造不可变新图+意图索引快照 → 获取 _dag_lock → 原子替换 active snapshot → 释放锁。
        新操作用新图；在途/暂停/恢复操作固定旧 graph_version。旧图资源须等运行引用和持久化 pin 都释放后卸载。"""

    def draw(self, fmt="mermaid") -> str | bytes:
        return self.workflow.draw(title="MetaAgent DAG", output_format=fmt,
                                  expand_subgraph=True)      # 需 WORKFLOW_DRAWABLE=true
```

**DeepAgentComp**（自封装组件，继承【内核】`WorkflowComponent`，实现 INVOKE+STREAM）：

```python
class DeepAgentComp(WorkflowComponent):
    def __init__(self, agent: DeepAgent, budget: BudgetConfig): ...

    async def invoke(self, inputs, session, context) -> Output:
        # 1. 读取带 plugin/version/execution_id 来源的 partial 和已完成 operation_id，
        #    作为工具执行上下文；避免重复副作用靠 L3，而不是靠拼接 query 的文字承诺
        # 2. 调 DeepAgent（TaskLoop 已随 enable_task_loop 装配）；预算经 GoalStopConfig 生效
        # 3. 写全局状态：{final_output, __harness_trace_ref__}
        # 4. DeepAgentState 由内核 save_state 落 checkpoint（迭代边界）
        ...

    async def stream(self, inputs, session, context) -> AsyncIterator[Chunk]:
        # 映射 DeepAgent.stream() chunk 到统一输出；持有租约直至 iterator 结束
        ...
```

**RouterComp**：

```python
class RouterComp(WorkflowComponent):
    def __init__(self, router: FastPathRouter, trace_sink): ...
    async def invoke(self, inputs, session, context) -> Output:
        try:
            d = await self.router.route(inputs["query"], session)
            session.update_global_state({"__route_decision__": asdict(d)})
        except RouteClassificationError as e:       # 【新建】仅分类失败可降级；存储/租约/取消必须传播
            # no_match_decision【新建】补齐全部字段，输出可序列化 RouteDecision
            d = no_match_decision(reason=str(e))
            session.update_global_state({"__route_decision__": asdict(d)})
            self.trace_sink.emit_error("router", e)
        return {"route_decision": session.get_global_state("__route_decision__")}
```

### 4.6 MetaRegistry / 插件加载【新建】

```python
class MetaRegistry:
    skill_slot: SkillSlot          # 包装【内核】SkillManager / SkillUtil
    fastpath_slot: FastPathSlot    # 插件版本台账 + 意图索引
    team_slot: TeamSlot            # SubAgentConfig / 团队成员物化缓存

    async def load_plugin(self, pkg_dir: str) -> LoadedPlugin:
        """1. manifest.json → WorkflowPluginManifest.model_validate（含 min_meta_agent 版本检查）
        2. importlib 加载 entry → await build(**ctx) → Workflow 实例
        3. DAGCompiler.validate_fastpath_subgraph（防环）
        4. 版本台账登记 (name, version, path, load_record)；同名不同版本并存
        5. Runner.resource_mgr.add_workflow(WorkflowCard(...), lambda: workflow, tag=f"fastpath:{name}")
        6. 暂存该版本意图索引；activate 时与新图一起切换，load 不改变当前路由"""

    async def activate(self, name: str, version: str) -> None:
        """MetaOrchestrator.swap_plugin 原子切换；RouteStats 该插件计数重置。"""

    async def unload_plugin(self, name: str, version: str | None = None) -> list[str]:
        """检查运行引用及持久化 session pin；仍被使用则拒绝卸载。
        查版本台账取 LoadRecord → Runner.resource_mgr.remove_workflow → 对应版本索引摘除。
        （DeepAgent 侧能力卸载用内核 unload_extension(record) 对齐语义）"""

class LoadedPlugin(BaseModel):
    name: str; version: str; workflow: Any; manifest: WorkflowPluginManifest
    load_record: LoadRecord | None
```

### 4.7 MetaAgentTeam【新建】

**2026-10-22 当前装配**：`MetaAgentTeamSpec.from_package` 解析 `meta_team.yaml`；worker 启动时固定已校验的成员 LoadedPackage，按 A2A context 通过 `MetaAgentTeam.from_loaded` 创建独立团队。新消息走 Team → Leader MetaBaseAgent DAG，配置成员通过 MetaAgentHarnessProvider 执行各自 DAG，原生内核负责消息和协调。单成员快路径不增加模型调用。

**A2A 生命周期映射**：每个 context 只有一个活动请求和一个团队事件消费者。新消息分配团队 execution，成员 execution 保留在嵌套结果。默认模式在 `input_required` 后保留后台流；durable 模式等待成员结束，调用 suspend 并完整消费流后，才发布可恢复的待答 task。A2A task artifact 保存原 interaction、身份、已完成结果与暂停段 usage；新 worker 按稳定的 context 团队身份调用 resume，重现原 interaction 后提交答案。回答使用原 taskId/contextId 与新 messageId，团队 execution 不变。取消关闭团队，已取消 task 不接受续跑；最终 `meta-result` 汇总成员结果与跨交接 usage。

**服务边界与下一步**：成员输出按轮次缓冲；团队 `--durable` 已支持审批点完整交接与 worker 重启，沿用组件恢复范围。成员普通 ask_user、非 Leader 快路径自动回复、passive human 和 LocalRecovery 尚未支持的能力组合仍未开放；执行中直接崩溃不自动视为可恢复审批。恢复须保留原业务包及配置路径；PostgreSQL 模式允许替换 native state-dir，并支持成员原生工具审批接续。下一步验证隔离部署交接；团队管理写接口、完整 HITT 和真实平台另行集成。见[团队 worker 样例](examples/team_worker/README.md)与 [PLAN](PLAN.md)。

**已确认的内核能力与设计缺口必须分开**：

- `TeamAgentSpec.agents` 是 role→DeepAgentSpec；其 build 不识别 MetaAgentSpec。把扩展字段写进 prompt/extras 不会替换成员执行器。
- 新基线有 `HarnessProtocol` / `HarnessProvider`、进程内 `register_harness_provider(name, factory)` 和包 entry point `openjiuwen.harness_providers`；`ExternalCliAgentSpec.cli_agent` 支持已安装的三方 provider，运行由 `ExternalHarnessMemberRuntime` 适配。
- 本期新建 `MetaAgentHarnessProvider`（候选名 `meta_agent`），创建一个持有 MetaBaseAgent 的协议实现；使用内核串行 turn 骨架时只实现生命周期/单轮调用及事件映射，不重写 DeepAgent 推理循环。能力卡必须按已实现的交互、取消、模型配置、checkpoint 能力声明。
- 三方成员 spawn 只传通用配置（cwd/env/skills 等），不能直接塞任意 MetaAgentSpec。需要用平台提供的不可变配置引用和 digest 找到成员 spec，并在新进程注册/发现 provider；恢复时必须引用同版本。该加载器是新建代码，不是现成内核字段。
- 三方成员默认团队工具通道是 stdio MCP；本项目要求所有 MCP 经平台网关，须验证网关桥接或受支持的工具注入方案，不能静默放宽 KAR-5。
- 公开三方 teammate 路径不能证明 Leader 可以替换为 MetaBaseAgent。Leader 运行时接线、默认单成员 MetaAgentTeam、权限/HITT 及冷恢复均为 **GATE-TEAM**。如固定提交没有覆盖完整目标的扩展点，应明确修订架构或提出上游扩展，不可用 monkey-patch 或 prompt 伪装已实现。

**M1 阶段发现（历史记录）**：公开 `TeamAgent.configure(spec, context, member_runtime=...)` 能在 Leader 角色接受自定义 runtime，M1 当时只验证配置接线。后续本机实现已通过 Leader/单成员执行与组件审批交接；权限/MCP 和服务能力按下述实际范围验证，不能外推完整 GATE-TEAM。

以下是原设计的 Runner 门面示意，不能作为当前冷恢复实现使用。当前非恢复团队用 LocalTeamRuntimeSpec 注入 Leader runtime；组件 LocalRecovery 为保留自定义 Leader harness，使用公开 `TeamAgent.stream/recover_for_existing_session` 完成显式审批交接。A2A worker 复用这一机制，在原 task 上恢复，不能以重新 invoke 代替 suspend/resume。

```python
class MetaAgentTeam:
    def __init__(self, spec: MetaAgentTeamSpec, team_adapter):
        self._runtime_spec = team_adapter.validate_team_binding(spec)

    async def invoke(self, inputs: dict, session: str) -> Any:
        return await Runner.run_agent_team(
            agent_team=self._runtime_spec, inputs=inputs, session=session)

    async def stream(self, inputs: dict, session: str):
        async for chunk in Runner.run_agent_team_streaming(
                agent_team=self._runtime_spec, inputs=inputs, session=session):
            yield chunk

    async def recover(self, inputs: dict, session: str):
        # 正常调用交给 Runner 判定冷/热恢复；不先 build 一个独立 TeamAgent 再交给 Runner
        return await self.invoke(inputs, session)
```

验收必须覆盖：成员确实执行 MetaOrchestrator（不是仅跑普通 DeepAgent）、请求/交互/取消的正确 session 归属、只有一个输出事件消费者、序列化→子进程→重启后配置保持、审批与 MCP 约束仍生效、Leader 与单成员目标、持久化后端漂移恢复。上游存在接口不是这些用例已通过的证据。

### 4.8 CheckpointManager（L3）【新建】

**操作身份**：`execution_id` 标识一个用户逻辑请求，`operation_id` 标识该请求内的一次业务副作用。两者在发起外部调用前持久化，进程重启/重试必须复用。同参数的第二次合法业务操作分配新 operation_id；canonical args hash 只检查同一操作的参数是否被意外改写。不能用 `sha256(tool_name + args + session_id)` 去重整个会话，也不能每次重试生成新 UUID。

```python
class CheckpointManager:
    def __init__(self, cfg: CheckpointConfig, store: DurableJournalStore): ...

    async def prepare(self, scope, execution_id: str, operation_id: str,
                      tool_name: str, args: dict, contract: EffectContract,
                      fencing_token: int) -> SideEffectTicket:
        """原子登记/读取同一操作，校验参数 hash 与 fencing 并等待耐久确认。
        key=(scope, execution_id, operation_id)，scope 含 product/agent/session/member。
        同 key 异参拒绝；completed 返回已持久化结果；in_flight 先查询/对账，禁止盲执行。"""

    async def complete(self, ticket: SideEffectTicket, result: Any) -> None:
        """CAS+fencing 校验并耐久保存 completed/result，成功后才能向调用者返回。"""

    async def mark_unknown(self, ticket: SideEffectTicket, error: str) -> None:
        """超时/断连/取消不意味着外部未生效；保存 unknown 并暂停自动续跑。"""

    async def save_route_decision(self, scope, execution_id: str, decision: RouteDecision) -> None: ...
    async def load_route_decision(self, scope, execution_id: str) -> RouteDecision | None: ...

    async def recover(self, scope, execution_id: str, fencing_token: int) -> RecoveryPlan:
        """确认 lease/版本/存储 → 恢复 L1/L2 → 对账 L3。
        completed: 返回原结果；未决: 下游同键去重/可靠查询/真正幂等时才重试，
        无法判断则 interrupts；未提交的新调用不得凭参数匹配猜测身份。"""

    async def migrate(self, data: dict, from_version: int) -> dict: ...
```

**统一执行边界**：新建 `SideEffectExecutor.execute(call, contract)`，所有有副作用的 Tool/RPC/HTTP/skill 写调用均由包装器执行：

```text
解析/持久化 operation_id → 校验权限与有效 lease → journal.prepare（耐久）
  ├ completed：返回旧结果
  ├ 未决：先对账；无安全重试依据则 INPUT_REQUIRED/人工处理
  └ 可执行：携带稳定下游幂等键调用 → journal.complete（耐久）→ 返回结果
      └ 超时/断连/崩溃窗口：保留未决，不当作“未执行”转 Harness
```

`EffectContract` 是【新建】注册契约：调用名、read_only / naturally_idempotent / downstream_dedup / reconcile_only / non_replayable 分类、业务去重键生成与传递位置、查询接口及去重保留期。单个 `idempotent=True` 标志不足以证明业务安全；去重保留期必须覆盖恢复窗口。补偿必须是业务显式定义的另一操作，不能默认回滚已发生的副作用。

**CheckpointRail 的范围**：仅关联已持久化的 operation_id、校验工具已安装包装器、记录观察信息；不把 before/after 钩子当作覆盖全部路径的执行事务。内核参数为 `ctx.inputs.tool_call/tool_name/tool_args/tool_result`，异常为 `ctx.exception`，不能假定有 `ctx.ticket`。并发工具的 ticket 必须按 call/operation ID 分开。Rail priority 越大越先，数值 10 并非“最先”；无论回调顺序怎样，包装器都在真正外部调用之前完成 prepare。此设计不依赖改变内核 rail 执行顺序。

**快路径覆盖**：插件构图 ctx 注入同一个 effect_executor；ToolComponent、HttpRequestComponent、ReActAgentComp 工具、嵌套 workflow 与 skill 脚本的写操作都需使用受控包装器。仅校验节点类型或 Python import 无法证明没有直接 I/O，须结合插件审核与执行隔离。fallback 带上已完成 operation_id，复用结果；存在 unknown 时暂停，不启动可能重复操作的 DeepAgent。

**耐久性边界**：prepare/result 可做 group commit，但每个调用必须等待所属批次耐久确认；观测事件可以异步缓冲。L1/L2 checkpoint、路由/图版本与操作账本通过稳定身份关联，不能假定多个独立写入天然原子。“恢复成功”指重建最近提交状态，外部效果的 exactly-once 仍依赖下游契约。

**M1 证据范围**：两个独立 SQLite 文件中已验证 prepare/下游效果/result 边界后的真实进程终止、原 ID 查询/去重、unknown 暂停及事务内 fencing 拒绝。重启调用者仍提供原身份和参数；租约使用注入时钟。该原型不证明 L1/L2 冷恢复、共享存储耐久性、真实续约断连或跨实例漂移。

### 4.9 MetaTraceFileSink【新建】

基于【内核】`TrajectorySpanProcessor` + `FileTrajectoryStore`（JSONL）：

```python
class MetaTraceFileSink:
    def __init__(self, cfg: TraceConfig): ...

    def attach(self, tracer_provider, span_processor: TrajectorySpanProcessor) -> None:
        """共享 span_processor 已注册 TracerProvider；本 sink 只消费归档与自定义事件。"""

    def emit_route(self, d: RouteDecision) -> None: ...           # category="route"
    def emit_evolution(self, record: EvolutionRecord) -> None: ... # category="evolution"
    def emit_team_event(self, event) -> None: ...                  # category="team"
    async def flush(self) -> None: ...                             # 双缓冲→append→按日滚动
```

**轨迹文件格式**（`{file_dir}/trajectory-{yyyyMMdd}.jsonl`，每行一个 JSON）：

```json
{
  "trajectory_id": "uuid",
  "session_id": "s-123",
  "team_id": "default_team | null",
  "member_id": "leader | agent_main | null",
  "category": "llm | tool | route | evolution | team",
  "ts": 1730000000.123,
  "span": { "...": "OTLP 语义（Trajectory.to_otlp 子集）" },
  "event": { "category=route 时": "RouteDecision 全字段",
             "category=evolution 时": "{skill, action, score, usage_stats, command}" }
}
```

写入要求：append-only、进程内双缓冲（buffer_size 条或 5s 刷盘）、文件句柄按日滚动重开、写失败降级为内核 logger 并 OpsAdapter 计数告警。此模式允许进程崩溃时丢失未刷盘轨迹，不能宣称 100% 落盘；需要零丢失时另配耐久事件队列并验收。轨迹文件不作为 L3 的恢复真相源。

### 4.10 CSP Adapters【新建，平台仓】

```python
# ---- 推理：实现内核 Model 客户端契约（chat/stream/embedding），供 create_deep_agent(model=...) 使用 ----
class InferScheduleModelAdapter:
    def __init__(self, cfg): ...
    def get_model(self, team_model_cfg: TeamModelConfig) -> Model: ...
    """REST 映射：POST {endpoint}/v1/chat/completions（SSE stream）；鉴权 api_key；
    重试（幂等 5xx/429，指数退避）、熔断（窗口失败率）、并发连接池、usage 回填 TokenUsage。"""

# ---- 记忆：可选；启用时替换内核记忆后端 ----
class MemoryServiceAdapter:
    async def retrieve(self, scope_id, user_id, query, top_k, threshold=0.3) -> list[MemResult]: ...
    async def write(self, scope_id, user_id, messages, session_id, agent_config) -> bool: ...
    """映射 MemoryRetrievalComponent / MemoryWriteComponent 的 memory 参数；缺省回退内核 LongTermMemory。"""

# ---- MCP：必选通道 ----
class McpGatewayAdapter:
    def build_mcps(self, spec_mcps: list[McpServerConfig]) -> list[McpServerConfig]:
        """统一改写/收敛到平台 MCP 网关 endpoint；登记 Runner.resource_mgr.add_mcp_server()；
        工具调用审计日志写入 trace（category=tool，gateway=true）。"""

# ---- Skills 运行时：可选独立进程 ----
class SkillsRuntimeAdapter:
    async def resolve_skill(self, name: str) -> ResolvedSkill: ...     # RPC → 平台 skills runtime
    async def execute(self, name: str, args: dict) -> Any: ...
    """启用时 SkillSlot 的加载/执行改经此适配；缺省内核 SkillManager 本地实现。"""

# ---- AgentGov：镜像模式必选（组件模式可不启用）----
class AgentGovClient:
    """MetaAgent → AgentGov 注册/心跳/优雅下线（契约见 5.2）。"""
    def __init__(self, cfg): ...
    async def register(self, agent_card: dict, instance: dict) -> None:
        """POST /v1/agents/register；instance.callback_endpoint = worker 内部 A2A JSON-RPC 地址。
        由 WorkerA2AService【新建】装配内核 A2A server/executor；仅对 AgentGov 可达并校验其身份。"""
    async def heartbeat_loop(self) -> None: ...      # 周期 PUT /heartbeat；连续失败 N 次 → 告警
    async def deregister(self) -> None: ...          # 优雅下线 DELETE /v1/agents/{instance_id}

# ---- 告警运维：必选 ----
class OpsAdapter:
    async def report_boot(self, boot_info: dict) -> None: ...
    async def report_alert(self, level: Literal["info","warn","critical"], source: str, payload: dict) -> None: ...
    async def report_metrics(self, metrics: dict) -> None: ...
    """指标集：QPS、路由命中率/时延、fallback 率、token 用量、checkpoint 恢复次数与耗时、
    轨迹文件写入失败数、LLM 意图路由占比。"""
```

## 5. 对外接口设计

### 5.1 产品调用方式总览

MetaAgent **默认遵守 A2A 协议标准**对外提供访问；平台额外提供 **MateMind SDK（C++/Python/Rust）** 通过 A2A 接口访问 MetaAgent。两种形态：

| 形态 | 链路 | SDK 后端 |
|---|---|---|
| 镜像模式 | 产品应用 → A2A JSON-RPC → **AgentGov 接入面** → 按注册表路由 → agentworker 实例 | MateMind SDK **A2A 远端后端** |
| 组件模式 | 产品应用进程内 → MetaAgent（in-process） | MateMind Python SDK **本地后端**（LocalChannel） |

> MateMind SDK 三语言统一语义：`send_message(agent, query, conversation_id)` / 流式回调 / task 状态查询；产品代码不感知部署形态差异。

```python
# MateMind SDK（Python）示例 —— 组件模式与镜像模式同一套代码
from matemind import Client
client = Client()                                   # 自动探测：有 META_AGENT_A2A_ENDPOINT 走 A2A，否则 in-process
resp = client.send_message(agent="default_team", query="我要退款", conversation_id="conv-42")
async for chunk in client.stream(agent="default_team", query="帮我写周报", conversation_id="conv-43"):
    ...                                             # A2A TaskUpdater 流式回推
```

### 5.2 服务化接口：A2A via AgentGov（镜像模式）

**设计要点**：AgentGov 是唯一**公开** A2A 接入面，负责鉴权、注册发现与路由。镜像模式下 agentworker 必须运行一个**内部** A2A listener（WorkerA2AService【新建】，装配 `extensions/a2a` 的 server/executor），接收 AgentGov 转发的 JSON-RPC/SSE；仅有 Runner 对象不能处理网络请求。内部端口由网络策略限制且校验 AgentGov 服务身份，产品不直连；组件模式不启动该 listener。

网关→worker 使用 A2A。当前 `MetaAgentExecutor` 调用 `MetaBaseAgent.stream` 或 `TeamWorker.stream`；后者按 context 管理 MetaAgentTeam，原生 Runner/AgentTeams 继续负责协调。消息、task/context/execution、交互续跑、取消与流结束映射由 worker 承担。

**（1）实例 → AgentGov 注册契约**（MetaBootLoader 拉起完成后执行，配置见 3.8 `csp.agent_gov`）：

```
POST {agent_gov_endpoint}/v1/agents/register
{
  "agent_card": {                       # 对齐 A2A AgentCard 语义
    "name": "default_team",             # 产品/Agent 名，路由键
    "version": "1.0.0",
    "description": "...",
    "capabilities": [...],
    "interface_url": "http://agentgov.csp:9000/a2a/jsonrpc/"   # AgentGov 对外挂载点
  },
  "instance": {
    "instance_id": "uuid",              # 实例唯一 id（Pod/进程）
    "callback_endpoint": "http://agentworker-7d9:9001/a2a/jsonrpc/", # 内部 A2A listener（生产使用认证传输）
    "product": "<product_id>",
    "mode": "agentworker",
    "meta_agent_version": "0.1.10+m1",
    "ready": true                       # 与 /admin/health 探针联动
  },
  "heartbeat": { "interval_s": 30, "ttl_s": 90 }
}
→ 200 { "registered": true }；之后周期 PUT /v1/agents/{instance_id}/heartbeat 续约
```

AgentGov 侧语义（实现归云平台）：注册表按 `(product_id, agent_card.name)` 索引多实例，心跳过期摘流；选择实例后经 callback_endpoint 转发 A2A JSON-RPC，执行互斥仍由 §4.2 租约保证，会话亲和不能代替锁。连接中断后先按 request/task 身份查询，不把未决的有副作用请求盲重放到别的实例。优雅下线先摘流、排空或持久化在途任务，再关闭内部 listener。

**（2）调用链路**：MateMind SDK / 产品应用 → AgentGov 公开 A2A → worker 内部 A2A listener → 对应 Runner 门面 → TaskUpdater 状态/artifact/SSE 回推。网关与 worker 必须固定同一 A2A 协议版本；AgentCard/方法/流帧使用该版本 SDK schema 校验。

**（3）请求映射**：`{"query": ..., "conversation_id": ..., "request_id": ...}` 是 SDK 到 MetaAgent 的内部输入模型，**不是**完整 A2A wire 请求。SDK 转成所选版本的 JSON-RPC `message/send` / `message/stream` 消息与 DataPart/metadata；conversation_id 映射到带 product/agent 命名空间的 session，request_id 识别逻辑 execution，同一请求重试复用。A2A task/context ID 映射须持久化；普通新一轮消息不复用旧 execution_id。

**（4）A2A Server 集成方式**：AgentGov 复用 OpenJiuwen `extensions/a2a` 的 request handler / task store / transformer 组件（`pip install "openjiuwen[all-a2a]"`），将 `A2AAgentExecutor` 的"按 agent_id 找本地 agent"替换为"按注册表路由到远端实例"。

### 5.3 管理面 HTTP API（平台界面/运维）

| 方法/路径 | 说明 |
|---|---|
| `GET /admin/health` | 就绪探针（boot 完成 + Runner 运行 + adapter 连通自检） |
| `GET /admin/dag?member=agent_main&format=mermaid` | 导出统一 DAG |
| `GET /admin/plugins` | 插件列表（名称/版本/状态/命中率/θ） |
| `POST /admin/plugins` (multipart 或 git 拉取） | 上传插件包 → 校验 → 版本化注册（本期走文件路径；界面上传为演进项） |
| `POST /admin/plugins/{name}/activate` `{version}` | 灰度激活（swap_plugin 原子切换） |
| `DELETE /admin/plugins/{name}?version=` | 卸载 |
| `POST /admin/reload` | 全量重载业务包（滚动重启语义，checkpoint 恢复在途会话） |
| `GET /admin/stats/router` | RouteStats（各插件命中/未中/失败、自适应 θ 现状） |
| `GET /admin/trace/files` | 轨迹文件列表与偏移（供平台采集） |

## 6. 关键流程时序

### 6.1 F1/F2/F3 请求路由主流程

```
产品/用户  接入层  MetaOrchestrator  RouterComp  FastPathRouter  WP_i(插件)  DeepAgentComp  DeepAgent内核  CheckpointManager
  │ 请求     │        │               │             │              │            │             │              │
  │─────────▶│session锁│               │             │              │            │             │              │
  │          │───────▶│invoke         │             │              │            │             │              │
  │          │        │──────────────▶│route(query) │              │            │             │              │
  │          │        │               │─session缓存?─▶             │            │             │              │
  │          │        │               │─L1 skill元数据──▶           │            │             │              │
  │          │        │               │─L2 规则/embedding─▶         │            │             │              │
  │          │        │               │─L3 when求值─────▶           │            │             │              │
  │          │        │               │◀─RouteDecision              │            │             │              │
  │          │        │               │update_global_state          │            │             │              │
  │          │        │               │──────────决策落盘───────────│────────────│────────────▶│save_route_decision
  │          │        │◀─条件边分发───│                             │            │             │              │
  │          │        │ 命中 ──────────────────────────────────────▶│插件子图执行  │             │              │
  │          │        │               │                             │ 显式持久化   │             │              │
  │          │◀──成功/交互确认后发布─────────────────────────────────│ 暂存结果     │             │              │
  │          │        │ 未命中 ─────────────────────────────────────────────────▶│TaskLoop     │              │
  │          │        │               │                             │            │Rails链→LLM │              │
  │          │        │               │                             │            │(infersched)│              │
  │          │        │               │                             │            │工具(经MCP网关│ prepare/complete（耐久）
  │          │◀──流式chunk───────────────────────────────────────────────────────│             │              │
  │          │        │◀─Merge→End    │                             │            │save_state   │              │
  │◀─响应────│        │               │                             │            │             │              │
```

### 6.2 F3 fallback 流程（白名单语义）

```
WP_i = FastPathOutcomeComp 执行插件 → 捕获允许的普通异常/显式失败
→ 检查 L3 无未决操作 → 写 __fastpath_outcome__={status:failed,error:...}
→ WP_i 正常返回后 outcome_router 求值（固定图版本中的 manifest）：
   ├─ fallback_to_harness=false ──────────────▶ TerminalEndComp：错误结果透传，直接结束
   ├─ code ∈ fallback_whitelist 或 exc_type ∈ fallback_whitelist
   │                                           ▶ TerminalEndComp：可接受失败透传，直接结束
   └─ 默认 ────────────────────────────────────▶ DeepAgentComp
        → 传递带来源的 __fastpath_partial__ 与已完成 operation_id；禁止用新身份重做同一操作
       → 主路径继续 → RouteStats.fail++
→ 白名单终止计入 fail_terminal（不参与 θ 自适应降权）；兜底失败计入 fail（触发降权评估）
INPUT_REQUIRED → 交互桥接，保留子图恢复位置；取消/失租/存储失败/副作用未决 → 控制层停止/暂停，不进 fallback
```

**退化形态**：`plugins` 为空时 DAGCompiler 编译 `Start → DeepAgentComp → End`（无 RouterComp），
FastPathRouter 不实例化，程序完全按 Harness 主路径执行（KAR-12）。

### 6.3 F6 崩溃恢复流程

```
实例重启 → boot 校验共享存储、配置/插件 digest、内部 listener
产品/AgentGov 以原 session_id + request_id 查询/恢复 → 获取有效 lease 与 fencing token
→ CheckpointManager.recover(scope, execution_id, fencing_token):
   L1/L2: 恢复最近耐久提交，固定原 graph_version/插件版本/child session
   L2: 恢复本 execution 的路由决策；新请求另分配 execution 并重验路由
   L3: completed 返回原结果；未决项按下游去重/可靠查询/真正幂等契约处理
   无法对账的写操作 → RecoveryPlan.interrupts，暂停并告警，禁止盲 fallback
→ 安全条件满足后继续；恢复时间/对账/中断分别打点，不承诺所有情况用户无感
```

### 6.4 F7 热更新流程

```
上传/放置 v2 包 → POST /admin/plugins (validate: manifest+防环+版本兼容)
→ registry.load_plugin(pkg) 构建 v2（与 v1 并存，意图索引暂存不激活）
→ POST /admin/plugins/{name}/activate {version: v2}
→ 构建不可变 v2 图/索引快照 → _dag_lock 内原子替换 active snapshot
→ 新 execution 走 v2；在途/暂停/恢复 execution pin v1，不能只保留内存引用
→ RouteStats 重置该插件窗口 → OpsAdapter.report_metrics
→ 运行引用、持久化 pin、恢复保留期均结束后允许旧版本卸载；否则管理面拒绝
```

### 6.5 F8 团队协同流程

```
请求 → Runner.run_agent_team_streaming(spec.team, session)
→ Leader（内核 TeamAgent）分解 → GATE-TEAM 已通过的 provider/runtime 接线派工
→ MetaAgent 成员执行其 DAG；是否可替换 Leader 必须独立验收，不能由 teammate 支持推导
→ 权限 ask → Leader approve_tool → teammate 从断点恢复
→ 团队 span：team.<name> > agent.<member> > llm.call > tool.<name>（agent_teams observability）
→ 结果汇总；persistent 团队 standby；崩溃 → cold_recover（4.7 recover）
```

## 7. 状态设计

### 7.1 session 全局状态键约定（MetaAgent 命名空间，双下划线前缀避免与业务冲突）

| 键 | 写入方 | 读取方 | 说明 |
|---|---|---|---|
| `__route_decision__` | RouterComp | route_fn / 观测 | RouteDecision 字典 |
| `__route_cache__` | FastPathRouter | FastPathRouter | key 含 query_hash/上下文/权限/图版本；使用前重验 when |
| `__fastpath_outcome__` | FastPathOutcomeComp | outcome_router | `{execution_id,plugin,version,status,result,error}`；manifest 固定为图版本快照 |
| `__fastpath_partial__` | WP_i 显式存储 | DeepAgentComp | 带来源/版本的中间结果与已完成 operation_id；TRACE 不自动等于可恢复状态 |
| `__execution__` | 接入层 | 全链路 | `{execution_id,request_id,graph_version,plugin_digests,operation_refs}`；fencing 不沿用旧值 |
| `__harness_trace_ref__` | DeepAgentComp | MergeComp/观测 | 主路径 TRACE 引用 |
| `__recovery_plan__` | CheckpointManager | 编排层入口 | 恢复计划（仅恢复后首轮存在） |

### 7.2 checkpoint key 布局（逻辑命名空间，不假定内核物理 key 编码）

```
{session_id}:agent:{agent_id}                     # 内核：agent 状态
{session_id}:workflow:{workflow_id}               # 内核：workflow 状态
{session_id}:workflow-graph:{graph_id}            # 内核：图执行状态
{product}:{agent}:{session}:{member}:meta-effect:{execution}:{operation} # L3 CAS 记录
{product}:{agent}:{session}:meta-execution:{execution} # 图/插件/路由/操作引用
{product}:{agent}:{session}:meta-route:cache       # 带上下文/权限/版本的缓存
{product}:{agent}:{session}:meta:schema_version    # 版本迁移
{product}:{agent}:{session}:meta:lease             # owner/expiry/fencing，由 lease store 管理
```

### 7.3 DeepAgentState（内核，恢复粒度）

DeepAgentState 由固定版本内核的 `to_session_dict()/from_session_dict()` 序列化，MetaAgent 不手工重建其字段。恢复到已提交边界，须验证迭代/任务计划/停止条件/待处理输入等实际状态。persistence/redis 的耐久配置、保留期、团队数据库与必要文件资源都必须满足恢复契约；`refresh_on_read=True` 只涉及 TTL。

## 8. 错误码与异常处理

| 错误码 | 场景 | 处理 |
|---|---|---|
| `META_BOOT_PKG_MISSING` | 必选业务包缺失/校验失败 | 启动失败，探针 not ready，Ops 告警 critical |
| `META_PLUGIN_INVALID` | manifest 非法/防环校验失败/版本不兼容 | 拒绝注册，告警 warn，不阻断其他插件 |
| `META_ROUTE_FALLBACK` | 快路径异常回退主路径 | 转主路径（info 打点 + RouteStats.fail++） |
| `META_FASTPATH_TERMINAL` | 快路径白名单/不兜底错误终止 | 错误作为结果直接透传（info 打点 + RouteStats.fail_terminal++），不进主路径 |
| `META_RECOVER_REFUSED` | checkpoint schema 不兼容 | 拒绝恢复 + critical 告警 + 建议清空会话 |
| `META_SESSION_CONFLICT` | 同 session 并发请求 | 接入层 409 或排队 |
| `META_SESSION_LEASE_LOST` | 续约失败/owner 变化 | 取消当前执行，拒绝旧 fencing 写入；在途副作用转对账 |
| `META_EFFECT_UNRESOLVED` | 下游可能已生效且无法确认 | 暂停并告警；不进入 Harness fallback |
| `META_TEAM_ADAPTER_UNAVAILABLE` | Team 成员/Leader 接线门禁未通过 | 拒绝启用该 Team 配置，不能静默丢弃快路径 |
| `META_ADAPTER_DOWN` | inferschedule/MCP 网关不可用 | 模型侧重试/熔断；MCP 工具返回结构化错误供 LLM 自愈；critical 告警 |
| `META_TRACE_WRITE_FAIL` | 轨迹文件写失败 | 降级内核日志 + warn 计数，不阻断请求 |
| `DEEPAGENT_LOAD_PLUGIN_ERROR` / `DEEPAGENT_UNLOAD_EXTENSION_ERROR` | 内核插件错误 | 透传内核语义 |

## 9. 性能与容量设计要点

1. **路由零 LLM 优先**：默认 rule_embedding；LLM 分类器按策略启用；缓存包含上下文/权限/图版本，动态条件总是复核；
2. **快路径零主路径开销**：条件边调度保证 DeepAgentComp 不命中不调度；DeepAgentComp 节点仅持有 harness 引用，无预热成本；
3. **流式**：主路径经统一输出适配直出；快路径按 §4.5 暂存后发布，延迟测量计入这一成本；
4. **checkpoint 写放大控制**：L3 prepare/result 可 group commit，但调用方必须等待耐久确认；路由/图/操作身份必须在对应执行前持久化，不能只入异步缓冲；
5. **轨迹写异步化**：独立于 L3 的双缓冲刷盘允许未刷盘事件丢失；零丢失模式需耐久队列及背压；
6. **KV cache 亲和**：高频子代理类型入 sticky 白名单（`is_sticky_subagent_type`），子 session `{parent}_sub_{task_id}` 预热/复用【内核 kv_cache_hooks.py】；
7. **扩容**：共享 checkpoint/L3/team DB、版本化插件与必要工作区齐备后才允许漂移；本地 SQLite 的默认示例不具备这一保证。

## 10. 安全设计

1. 插件包校验：manifest 白名单字段、entry 路径限制在包内、递归图结构校验禁止 harness 节点；静态 import/节点检查不能隔离任意 Python I/O，需插件审核及执行隔离保证写操作不绕过 SideEffectExecutor；
2. 工具权限：DeepAgentSpec.approval_required_tools / TeamPermissionRail（allow/ask/deny，Leader `approve_tool` 协议）；
3. MCP 收口：全部 MCP 调用经平台网关，审计入轨迹文件；
4. 敏感数据：OTEL redaction（prompt SHA-256）默认开启；轨迹文件落盘路径由平台控制，建议只写平台卷；
5. 配置密钥：环境变量注入（`${ENV:XXX}` 占位符在 boot 时解析），禁止明文入库。

## 11. 测试与验证方案

| 层级 | 内容 | 通过标准 |
|---|---|---|
| 单测 | 路由三态（命中/未命中/fallback）；θ 自适应降权；manifest 校验；防环校验 | 覆盖率 ≥ 85%（新增模块） |
| 单测 | CheckpointManager：prepare/complete/unknown、同参不同操作、同操作异参拒绝、schema 迁移 | 合法新操作不被吞；同一操作按下游契约去重；未决操作必须暂停 |
| 集成 | mock model client（`mock://`）跑通 MetaOrchestrator 全 DAG | draw() mermaid 结构核对 |
| 集成 | kill -9 冷恢复：prepare 前/后、下游已生效、result 提交前/后逐点注入 | 恢复最近提交边界；可确认操作不重复生效，无法确认的操作不盲重放 |
| 集成 | INPUT_REQUIRED 中断 → 续跑 | 从断点组件继续（TRACE 校验） |
| 集成 | 插件热更新：在途/暂停/崩溃恢复 v1，新操作 v2 | 图/manifest/缓存同版本；被 pin 的版本不能卸载 |
| 端到端 | demo：1 skill 主路径 agent + refund 快路径插件；多成员 team（leader+researcher） | 时延对比达标（快路径 P95 ≤ 2s） |
| 观测 | 轨迹文件 JSONL schema 校验；进化事件（/evolve* 全流程）完整性 | 字段齐备、可解析 |
| 故障注入 | inferschedule 5xx/超时、MCP 网关断开、Redis 抖动 | 熔断/降级/告警符合预期 |
| 集成 | 普通错误 fallback/白名单终止/禁用 fallback；INPUT_REQUIRED/取消/失租/unknown | 后四类不触发主路径；同一操作只产生一个最终输出 |
| 集成 | 主路径/子代理/快路径工具、HTTP、嵌套子图、skill 脚本的副作用覆盖 | 所有外部写入先完成 durable prepare，结果 durable 后返回 |
| 故障注入 | 运行超过 TTL、多实例同 session、续约断连、旧 owner 恢复 | 获取失败无执行；长任务续约；失租取消；旧 fencing 被拒绝 |
| 集成门禁 GATE-TEAM | provider 序列化/进程拉起/事件/权限/HITT/MCP 网关/Leader/单成员目标/恢复 | 实际经过 MetaAgent DAG；未通过禁止冻结团队能力基线 |
| 集成 | AgentGov→内部 A2A→单 Agent/Team Runner；消息/流/取消/中断续跑 | schema 合规；worker 未授权访问被拒；断连不会盲重放副作用 |

## 12. 交付检查清单（Definition of Done）

- [ ] MetaBootLoader 双模式（组件/镜像）启动加载通过
- [ ] 必选包缺失时启动失败并可观测
- [x] 快路径命中/未命中/fallback 三态与 θ 自适应（M3 本地真实 Workflow；模型路由采用可编程边界，真实模型/性能验收留在后续阶段）
- [ ] 统一 DAG `draw()` 导出（含子图展开）
- [ ] cold_recover 故障窗口矩阵全绿（L1+L2+L3；未决暂停也是预期结果）
- [ ] 轨迹文件按日滚动 JSONL 落盘，route/evolution/llm/tool 四类事件齐备
- [ ] CSP adapter 按配置及必选性装配，镜像模式包含 AgentGovClient；MCP 全部走平台网关
- [ ] GATE-TEAM 全部通过后，默认单成员与多成员目标方可标记可用；不得只靠配置解析通过验收
- [ ] 管理面 API 全量可用（健康/DAG/插件/统计/轨迹）
- [x] 无插件包时 DAG 退化为纯主路径并通过端到端用例（M2 本地脚本模型 + 真实 Workflow/DeepAgent；不是平台端到端验收）
- [ ] fallback 白名单三态用例：白名单内直接结束 / 白名单外兜底主路径 / fallback_to_harness=false 全终止
- [ ] 镜像模式：实例启动向 AgentGov 注册+心跳，AgentGov 路由 A2A 请求到实例（含摘流与重注册）
- [ ] MateMind SDK 三语言（C++/Python/Rust）最小调用样例通过 A2A 链路
- [ ] lease 续约/释放/fencing、主快路径统一副作用、同参不同操作、暂停后版本恢复用例通过
- [ ] 本文伪代码落地后做实际内核集成测试；文档静态核对不计为运行时验收
