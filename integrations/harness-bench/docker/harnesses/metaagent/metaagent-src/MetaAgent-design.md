# MetaAgent 设计方案（基于 OpenJiuwen core）

> **文档状态：历史提案，已由 V1.1 架构/系统设计草案替代。** 本文保留初始方案的推导，不作为当前接口或交付范围的依据。当前决策见 [架构设计](MetaAgent-架构设计文档.md) 与 [系统设计](MetaAgent-系统设计文档.md)。
>
> 2026-10-20 复核基线：`../openjiuwen-latest/agent-core`，`develop@4cd9df83855c0504af314655fbd7e2f34a0442fa`。下文 `/tmp/ojw/` 路径、源码行号及“源码树不在盘上”等表述只记录原提案形成时的环境。
>
> 已替代的关键假设：
> - 多 Agent 已从“仅原生 subagent、Team 预留”进入 AgentTeams 集成设计；MetaAgent 成员适配仍需原型验收，不能用 prompt/extras 或 `SubAgentSpec.factory_name` 代替团队运行时接线。
> - fallback 必须从插件执行包装节点出边；路由节点仅负责首次分派。中断、取消、租约失效及结果未决的副作用不进入普通 fallback。
> - 幂等性基于持久化的逻辑操作 ID、执行前后耐久提交和下游去重契约；不能用同 session 的工具名与参数哈希替代操作身份。
> - AgentGov 是唯一**公开** A2A 入口；agentworker 保留仅供 AgentGov 访问的内部 A2A 服务。
> - “免主路径开销”是单个 MetaBaseAgent 的分支调度保证，不代表团队 Leader 的协调成本为零。

## Context

基于 OpenJiuwen core 构建通用 Agent「MetaAgent」：以 DeepAgent 的 Harness 深度 Loop 为主路径（深度、自治、可进化），以业务开发的 workflow 插件为快路径（低时延、确定性），两条路径通过两级路由串联成一张 DAG。业务发布 MetaAgent 后有两种接入方式：

1. **开发 skills + agent 配置**（DeepAgentSpec YAML/JSON + skills 目录）→ 插入 harness 主路径，得到业务自己的深度 Agent；
2. **开发 workflow 插件**（带 intent 描述的 Workflow）→ 注册为快路径，命中时直接返回、不等 harness。

已确认的关键决策：
- 快路径/主路径执行语义 = **串行两级路由**（路由→命中则返回；未命中→进 DeepAgent），非竞速；
- 多 Agent 协同默认 = **DeepAgent 内置子代理**（`create_subagent` + async task loop）；
- 本次交付 = **设计方案文档**（不产出代码）。

> 代码依据说明：agent-core 完整源码树当前不在盘上，以下接口均来自 `/tmp/ojw/src/` 预提取源码（deep_agent.py 3708 行、factory.py、kv_cache_hooks.py、goal_schema.py 等，标注【源码】）或 `/tmp/ojw/agent-core-main/docs/` API 文档（标注【文档】）。源码仓路径为 `openjiuwen/` 包。

---

## 1. MetaAgent 是什么：与 DeepAgent / WorkflowAgent 的关系

OpenJiuwen core 现有两类 Agent 抽象，MetaAgent 是二者的超集：

| | DeepAgent（harness） | WorkflowAgent（core/application） | **MetaAgent** |
|---|---|---|---|
| 本质 | 双层 Loop：外层 TaskLoop（分解/编排/停止判定）+ 内层 ReAct Loop【源码 deep_agent.py:249, :2398】 | 把预定义 workflow（DAG）包装成 agent，WorkflowController 做多 workflow 意图路由与中断续跑【文档 workflow_agent.md】 | 在 DeepAgent 之上加**两级路由层**与**插件注册中心**，workflow 只是它的一个前置切面 |
| 擅长 | 深度、开放域、长任务、自进化 | 确定性、低时延、流程固定 | 两者兼得：命中快路径走 DAG，未命中走深度 Loop |
| 扩展方式 | rails / skills / subagents / 热加载插件 | 组件（ComponentComposable）+ 连接 | skills（进化）+ rails（行为）+ workflow 插件（快路径）+ 子代理（协同） |

**MetaAgent 与 workflow agent 的关系**（核心回答）：
- WorkflowAgent 是"workflow 包装成 agent"——DAG 即全部智能，无深度推理回路；
- MetaAgent 是"agent 编排 workflow"——workflow 插件是 MetaAgent 的可插拔快路径节点，是 MetaAgent 能力的一个切面而非主体；
- 包含关系：MetaAgent ⊃ WorkflowAgent 的能力（快路径路由可退化为纯多 workflow 路由），反向不成立。MetaAgent 内部将 workflow 引擎（`openjiuwen.core.workflow.Workflow`）作为执行原语使用，而不是继承 WorkflowAgent；
- 在 DAG 视角下，MetaAgent 的运行图 = 一张条件分派的图：Start → 路由节点 →（命中）→ 业务 workflow 子图 → End；（未命中）→ DeepAgent TaskLoop 子图 → End。条件边保证快路径命中时 DeepAgent 节点**根本不会被调度**——这是"不需要等待 harness 结果"的机制保证。

---

## 2. 总体架构

```
┌─────────────────────────── MetaAgent ───────────────────────────┐
│  接入层  invoke / stream / follow_up / steer / abort            │
│     │（BaseAgent 标准接口，deep_agent.py:2674/:2715/:2781/:2813）│
│  编排层  MetaOrchestrator（外层 Workflow DAG，见 §4）            │
│     ├─ 路由节点  FastPathRouter（IntentDetection + BranchRouter）│
│     ├─ 快路径节点  WorkflowComp（业务 workflow 插件，动态注册）   │
│     └─ 主路径节点  DeepAgentComp（包装 harness DeepAgent）        │
│  主路径  DeepAgent（enable_task_loop=True）                     │
│     ├─ 外层 TaskLoop：LoopCoordinator + TaskLoopController      │
│     │   + EventQueue（子代理异步 task 化）                       │
│     ├─ 内层 ReActAgent（模型调用 / 工具执行 / 思考-行动-观察）    │
│     ├─ Rails：SkillUseRail / SkillEvolutionRail / SubagentRail  │
│     │   / TaskPlanningRail / SecurityRail / FastPathBridgeRail  │
│     └─ 子代理：create_subagent（DeepAgent 递归嵌套）             │
│  注册中心（MetaRegistry）                                        │
│     ├─ SkillSlot：skills 目录扫描 / 热加载 / 进化               │
│     ├─ FastPathSlot：workflow 插件注册 / 意图索引 / 动态加载     │
│     └─ TeamSlot：SubAgentConfig 注册 / 协同策略                 │
└─────────────────────────────────────────────────────────────────┘
```

分层说明：
- **编排层**用 `openjiuwen.core.workflow.Workflow` 实现（【文档】workflow.md）：`set_start_comp` / `add_workflow_comp` / `add_conditional_connection(router)` / `set_end_comp`。router 是普通 Python 函数，从 session 全局状态读路由结果决定下一节点——天然支持"命中→workflow 分支 / 未命中→DeepAgent 分支"。
- **主路径节点 DeepAgentComp** 是自封装组件（继承 `WorkflowComponent`，实现 `invoke`/`stream`），内部持有 MetaAgent 的 DeepAgent 实例并透传调用（【文档】components.md；模式四态 INVOKE/STREAM/COLLECT/TRANSFORM，可让 harness 的流式 chunk 经 `add_stream_connection` 流式边透出，End 组件 `response_mode='streaming'`）。
- **防环约定**：DeepAgent 内的 skill/工具可以反向调用快路径 workflow（通过 `ToolComponent` 或注册为 DeepAgent 工具）；但快路径 workflow 内部只允许轻量节点（LLMComponent / ReActAgentComp / ToolComponent），不允许再嵌套 DeepAgentComp；外层 DAG 嵌套深度用 `workflow_max_nesting_depth`（默认 5，范围 (0,10]）兜底。

---

## 3. 用到的 OpenJiuwen core 能力清单（接口级）

### 3.1 Harness 主路径【源码 factory.py:454 / deep_agent.py】
- `create_deep_agent(model, *, system_prompt, tools, mcps, subagents, rails, enable_task_loop=True, enable_async_subagent=True, skills, workspace, max_iterations=15, parallel_tool_calls=True, ...)` — MetaAgent 主路径工厂，全部业务配置经此注入；
- `resolve_deep_agent_parts() -> DeepAgentParts` + `apply_deep_agent_parts()` — 装配/应用两步拆分（factory.py:162-185），MetaAgent 在 DeepAgentComp 里复用同一套 parts 机制做自己的预装配；
- 默认 rail 自动装配表（factory.py:391-403）：SecurityRail / ModelAnomalyDetectionRail / TaskPlanningRail / SkillUseRail（条件 `bool(skills) or enable_skill_discovery`）/ SubagentRail（条件 `bool(subagents)`）/ ToolCallResilienceRail——MetaAgent 的 rail 插拔遵循同一约定（同类型业务 rail 存在则不重复注入）；
- `_run_task_loop`（deep_agent.py:2398）：外层 loop，`coordinator.should_continue()` 停止判据 + `controller.submit_round / wait_round_completion(timeout=600s)`；follow_up 缓冲支持并发流入；
- `agent.follow_up(msg)`（:2781）、`agent.steer()`（:2813）、`agent.abort()`（:2903）——交互控制原样上抛给 MetaAgent 接入层；
- `agent.switch_mode(session, "plan"/"auto")`（:2266）——plan/auto 模式作为 MetaAgent 的可选运行模式透出；
- 热更新：`_hot_reconfigure`（:434，不重启更新 rails/模型/工具/系统提示词）、`_hot_reload_rails(config)`（:463-489，按类型局部替换）；
- 插件热加载：`load_plugin(path)`（manifest.json / legacy harness_config.yaml）、`load_plugin_spec(spec)`、`load_agent_template(path)`、`load_plugin_ability(tools=..., rails=..., skills=ResolvedSkill|list)`、`unload_extension(record)`（deep_agent.py:1804-1975）——LoadRecord 台账精确卸载；
- KV cache 三级语义（kv_cache_hooks.py）：sticky 子代理白名单 → `prefetch_sticky_subagent` 预热（子 session id `{parent}_sub_{task_id}`）→ 成功 offload / 失败 evict；
- Goal 预算停止（goal_schema.py）：`GoalRecord(max_attempts, token_budget)` + `GoalAssessment` + 三种停止策略 `agent_report/transcript/hybrid`——MetaAgent 把 token/轮次预算作为业务配置项透出。

### 3.2 Workflow 引擎（快路径与编排层）【文档 workflow.md 等】
- `Workflow(card=WorkflowCard, workflow_max_nesting_depth=5)` + `set_start_comp` / `set_end_comp(response_mode='streaming')` / `add_workflow_comp(comp_id, comp, wait_for_all=..., inputs_schema={"k": "${上游.字段}"})` / `add_connection(src|list, target)`（list = 并行汇入）/ `add_conditional_connection(src, router)` / `add_stream_connection(src, target)`；
- `invoke(inputs, session, context) -> WorkflowOutput(result, state)`；`state=INPUT_REQUIRED` 时 result 为中断帧列表（人机交互断点续跑）；
- `stream(inputs, session, stream_modes=[OUTPUT|TRACE|CUSTOM]) -> AsyncIterator[WorkflowChunk]`——TRACE 帧带 `traceId/invokeId/parentInvokeId/loopIndex`，MetaAgent 用它做全链路追踪与慢路径沉淀的数据源；
- `draw(title, output_format="mermaid", expand_subgraph, enable_animation)`——**MetaAgent 的 DAG 对业务可视化**：业务注册快路径后可直接导出整张两级 DAG 的 mermaid 图；
- 内置组件：`Start/End/BranchComponent+BranchRouter/LoopGroup+LoopComponent/SubWorkflowComponent`（子工作流嵌套）、`LLMComponent`、`ReActAgentComp`（工作流内嵌 ReAct agent，`react_component.executable.ability_manager.add(tool.card)` 挂工具）、`IntentDetectionComponent`（LLM 意图分类，输出 classification_id/name/reason）、`ToolComponent`、`HttpRequestComponent`、记忆读写组件；
- 自定义组件：继承 `WorkflowComponent` 只实现 `async invoke(inputs, session, context) -> Output`——DeepAgentComp / FastPathRouterComp 均按此封装；
- 资源注册：`Runner.resource_mgr.add_workflow(card, WorkflowProvider)` + `Runner.resource_mgr.add_tool()`——快路径 workflow 与工具统一进资源管理器，支持延迟构建。

### 3.3 Skills 体系【文档 skills.README.md / Agent Skills.md / rails 文档】
- 定义约定：`<skill-name>/SKILL.md`（frontmatter: `name`, `description`）+ 可选 `scripts/ references/ assets/`；渐进式披露三层（metadata ~100 token 常驻 → SKILL.md 触发后加载 → 引用资源按需）；
- `SkillManager.register(skill_path, session_id, overwrite)` / `get/get_all/has/unregister`（registry 为 `dict[name -> Skill]`）；
- `SkillUtil.register_skills(path, agent)` + `get_skill_prompt()`（生成注入 system prompt 的 skill 摘要）；
- `SkillUseRail(skills_dir, skill_mode, disabled_skills, include_tools)`（factory.py:360-386）——发现与调用 skill，priority 95；
- **进化**：`SkillEvolutionRail`（priority 80）+ 一键装配 `configure_skill_evolution(agent, skills_dir, llm, model, trajectory_span_processor, auto_save, ...)`；经验层 `evolutions.json`（`id/source/context/change{section,action,target,content}/score/usage_stats`），与 SKILL.md 本体分离，仅 `/evolve_rebuild` 重组进主体；审批走 `EvolutionInterruptRail` + 稳定子代理 `evolution_reviewer`；用户命令 `/evolve /evolve_list /evolve_simplify /evolve_rebuild /evolve_rollback`；
- **从零创建**：`SkillCreateRail`（priority 85）把任务轨迹固化为新 skill。

### 3.4 多 Agent 协同
- 默认：DeepAgent 内置子代理——`create_subagent(subagent_type, subsession_id)`（deep_agent.py:1307，子代理独立 workspace `{workspace}/subagents/{subsession_id}`），`SubAgentConfig` 携带各自的 model/tools/skills/rails，`max_parallel_sub_agents` 控并发，子代理为 DeepAgent 可递归；
- 预留插槽（设计层抽象，MVP 不实现）：`core/multi_agent` 的 handoff（`transfer_to_{target}` 工具 + `handoff_orchestrator` 状态机 + `max_handoffs`）与 msgbus P2P（`message_bus.py`/`supervisor_agent.py`）；跨进程用 `Runner.spawn_agent()` 或 A2A（`extensions/a2a/a2a_server.py` 的 `A2AServer` + AgentCard.interface_url）。

### 3.5 动态能力
- 动态加载 workflow 插件：`load_plugin(manifest)` 声明 workflow 路径热加载，或 MetaRegistry 扫描插件目录后 `Runner.resource_mgr.add_workflow()` 注册；
- 动态生成 workflow：`openjiuwen.dev_tools.agent_builder` 的 `WorkflowBuilder`（意图检测→WorkflowDesigner 三段式设计→DLGenerator→Reflector 校验→CycleChecker）产出平台 DSL JSON——注意 **DSL→运行时 Workflow 的 loader 未文档化，需自研**（树中 builder 目录无 loader 文件）；
- 第二语义"动态 workflow"：DeepAgent 在 task loop 内由 LLM 即时构建 Workflow 并执行（代码内动态构图，非 DSL）——这是"动态 workflow"在 harness 路径内的低成本实现，无需 DSL loader。

---

## 4. 两级 DAG 的构成（核心机制）

```
            ┌───────────────── MetaOrchestrator DAG ─────────────────┐
            │                                                        │
 (query) → Start → FastPathRouter ──命中(intent=i, conf≥θ)──→ WP_i ──┤→ Merge → End(流式/批量)
            │              │                                           │
            │              └──未命中 / conf<θ / 插件执行失败(fallback)──→ DeepAgentComp ──┘
            │                                                        │
            └────────────────────────────────────────────────────────┘
```

- **路由节点**：优先 `IntentDetectionComponent`（LLM 分类，输出 classification_id + reason）；同时提供零 LLM 的降级路由（规则正则 / embedding 相似度，命中阈值 θ 可配），把分类时延压到毫秒级，也避免每个请求都付出一次 LLM 调用；
- **条件边**：`add_conditional_connection("router", router_fn)`，router_fn 读 session 全局状态里的路由结果返回目标 comp_id；**快路径命中时 DeepAgentComp 节点不被调度**——"不等 harness"由 DAG 调度语义保证，无需显式取消；
- **fallback 语义**（路由后仍可兜底，保证正确性优先）：
  - workflow 插件执行返回 `state=INPUT_REQUIRED` → 按中断续跑协议处理（透传给用户）；
  - workflow 插件显式声明失败 / 抛出可路由异常 → 条件边转向 DeepAgentComp（同一 session，query 原样传入，TRACE 帧已沉淀的中间结果经 session 状态传给主路径，避免重复劳动）；
- **DAG 即产品界面**：`MetaOrchestrator.draw()` 导出 mermaid/png，业务可看到"我的快路径挂在哪、主路径长什么样"；
- **DAG 动态演化**：新 workflow 插件注册 = 向编排层 DAG 增删条件边与节点（`add_workflow_comp` + `add_conditional_connection`），注册中心持有 DAG 写锁；与 DeepAgent 的 `load_plugin_ability` 热加载共用同一插件 manifest 约定。

---

## 5. Skills：扩展与进化的业务闭环

- **挂载**：业务 skills 目录挂到 `workspace/skills`（SkillUseRail 的默认扫描位，factory.py:360-386 同时扫描 team workspace 链接 `{target}/skills`）；MetaAgent 启动时 `SkillUtil.register_skills()` 扫描注册；
- **运行时使用**：skill 元数据常驻 system prompt（`get_skill_prompt()`），DeepAgent 经 `skill_tool` / `view_file` 渐进加载正文；
- **进化闭环**（主路径自动发生）：任务轨迹（TrajectorySpanProcessor 的 OTel span）→ SkillEvolutionRail 检测信号 → 经验写 `evolutions.json`（不回写本体）→ 用户 `/evolve*` 命令审批/重组/回滚；auto_save 可配置；
- **进化驱动快路径**（MetaAgent 特有闭环）：被 `/evolve_rebuild` 固化的稳定 skill，若命中频次高、流程高度确定，可由 `SkillCreateRail` 或人工将其 workflow 化为快路径插件——**skills 进化是快路径插件的供给来源之一**；
- **热更新**：新 skill 包经 `load_plugin_ability(skills=ResolvedSkill...)` 或 `_hot_reload_rails` 在运行中注入，无需重启。

## 6. 多 Agent 协同设计

- 默认走 DeepAgent 原生子代理：业务在 DeepAgentSpec 的 `subagents: list[SubAgentConfig]` 声明子代理（各自 system_prompt/tools/skills/model/workspace），`enable_async_subagent=True` 让子代理注册为异步 session 工具，非阻塞入 EventQueue（`DEEP_TASK_TYPE`/`SESSION_SPAWN_TASK_TYPE` 执行器），`max_parallel_sub_agents` 控并发；
- KV cache 亲和：把高频子代理类型加入 sticky 白名单（`is_sticky_subagent_type`），子 session 创建即 prefetch 预热，成功 offload 保留复用；
- 子代理与快路径的关系：子代理也可以注册自己的快路径（SubAgentConfig.skills 透传，deep_agent.py:1373），即"快路径可以下钻到子代理层"；
- MetaTeam 抽象（预留）：`MetaAgent.team(strategy="subagent"|"handoff"|"msgbus", members=[...])`，MVP 只实现 `subagent` strategy，接口按 core/multi_agent 的 TeamCard/HandoffOrchestrator 语义设计，避免后期重构。

## 7. 配置与发布形态（业务视角）

**方式一：skills + agent 配置 → 主路径**
```yaml
# meta_agent.yaml — DeepAgentSpec 子集 + MetaAgent 扩展
model: {provider, model_name, ...}
system_prompt: ...
skills: ["./skills"]            # 目录约定，SKILL.md frontmatter
tools: [...]
subagents:                      # 子代理即多 Agent 协同
  - type: researcher
    model: ...
    skills: [...]
evolution: {auto_save: false, language: cn}   # SkillEvolutionRail
budget: {max_attempts: N, token_budget: M}    # GoalStopConfig
```
MetaAgent 工厂 `create_meta_agent(spec)`：解析 spec → `create_deep_agent(...)` 建主路径 → 建 MetaOrchestrator DAG（注册中心装配）→ 返回 MetaAgent。

**方式二：workflow 插件 → 快路径**
```yaml
# fastpath.yaml — 插件 manifest（与 DeepAgent.load_plugin 的 manifest 约定对齐）
name: refund_fastpath
version: 0.1
workflow: workflow.py:build    # 返回 Workflow 实例的工厂入口
intent:
  description: "用户要求退款/退货的处理流程"
  examples: ["我要退款", "订单怎么退货"]
  threshold: 0.8
fallback_to_harness: true      # 插件失败是否回退主路径
```
插件 = 一个 Python 包（Workflow 构图代码 + manifest），经 `load_plugin` 热加载或启动扫描注册；意图描述进入路由索引（LLM 分类器的 category 列表 / embedding 库）。

## 8. 时延与性能设计

| 手段 | 机制 | 位置 |
|---|---|---|
| 快路径命中 | 条件边调度，DeepAgent 节点零开销 | 编排层 DAG |
| 路由免 LLM | 规则/embedding 降级路由，θ 阈值 | FastPathRouter |
| KV cache 亲和 | sticky 子代理 prefetch/offload/evict | kv_cache_hooks.py |
| 并行工具/子代理 | `parallel_tool_calls=True` 默认；子代理异步 task 化 | factory.py:533 / task_loop |
| 流式透出 | `add_stream_connection` + End `response_mode='streaming'`；DeepAgent `stream()` chunk 透传（_run_task_loop_stream :2558） | 编排层 |
| 预算停止 | GoalStopConfig 按 attempts/token 停 | goal_schema.py |
| 上下文 | core/context_engine 上下文池与压缩路由，长任务防膨胀 | core/context_engine |
| 路由结果缓存 | 同 session 内路由结果缓存，多轮对话免重复分类 | MetaRegistry |

## 9. 风险与边界

1. **DeepAgentComp 需自封装**：workflow 引擎没有现成的 DeepAgent 节点组件（只有 ReActAgentComp），需自行实现 `WorkflowComponent` 包装并处理流式四态——工作量集中在 invoke/stream 两态，MVP 可只实现 INVOKE + STREAM；
2. **DSL loader 缺口**：agent_builder 产出的平台 DSL 到运行时 Workflow 的反序列化 loader 未文档化，"自然语言生成 workflow"需自研转换器，或用"LLM 直接生成构图代码 + 安全执行"替代；
3. **路由误判成本**：θ 偏低会把深任务误送快路径（可用 fallback 兜底）；θ 偏高会漏命中（时延退化但正确性无损）。θ 应按业务灰度调参，并以 TRACE 命中率做监控；
4. **文档/源码不一致**：`load_expert_harness` 只在 auto_harness 文档出现、源码中实为 `load_plugin` 家族；core.skills 与 single_agent.skills 的 import 路径文档自相矛盾——实现时以源码为准；
5. **防环**：DeepAgent 工具回调 workflow + workflow 内嵌 DeepAgentComp 的双向调用必须用 `workflow_max_nesting_depth` + 约定（快路径不嵌 DeepAgentComp）双重约束。

## 10. 验证方式（设计评审后）

设计文档评审通过后，若进入实现阶段：
- 用 `mock://` model client（docs 示例同款）对两级路由写单测：命中/未命中/插件失败 fallback 三态；
- `examples/harness` + `examples/workflow_agent` 为参照搭端到端 demo：一个带 skill 的主路径 agent + 一个 refund 快路径插件；
- `MetaOrchestrator.draw()` 输出 mermaid 核对 DAG 结构；
- 时延对比：快路径命中 vs 纯 DeepAgent 端到端耗时；TRACE 帧校验 fallback 时中间结果传递。

## 附：本设计引用的关键文件

- 源码副本：`/tmp/ojw/src/deep_agent.py`、`/tmp/ojw/src/factory.py`、`/tmp/ojw/src/kv_cache_hooks.py`、`/tmp/ojw/src/goal_schema.py`、`/tmp/ojw/src/rsi_orchestrator.py`（对应仓内 `openjiuwen/harness/`、`openjiuwen/rsi/auto_harness/`）
- API 文档：`/tmp/ojw/agent-core-main/docs/en/2.Development Guide/API Docs/openjiuwen.core/workflow/workflow.md`、`.../components/llm/react_agent_comp.md`、`.../openjiuwen.core/application/workflow_agent/workflow_agent.md`、`.../openjiuwen.core/skills.README.md`、`.../openjiuwen.harness/rails/evolution/skill_evolution_rail.md`
- 文件树：`/tmp/ojw/agent_core_tree.json`（5362 文件，含 core/multi_agent、agent_teams、agent_evolving 全部路径）
