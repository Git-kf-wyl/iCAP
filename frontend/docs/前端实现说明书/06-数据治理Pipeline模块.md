# 06 · 数据治理 Pipeline 模块（Agentic Data Flywheel）

> 本模块**并非主工程原生代码**，而是从独立仓库
> `AgenticDataFlywheel/frontend` 迁移并适配进来的（见 `router/index.js:61` 注释）。
> 原仓库的 `App.vue`、`main.ts`、`router.ts`、`styles.css`、`env.d.ts` **被有意丢弃**，
> 由主工程统一接管入口与路由。

---

## 1. 模块概览

| 项 | 值 |
|---|---|
| 目录 | `src/dataPipeline/` |
| 文件数 | 约 105 |
| 代码行数 | 约 **14,300** |
| 路由前缀 | `/dataPipeline/*` |
| 布局壳 | `DataPipelineLayout.vue`（仅 `<router-view/>`） |
| 样式隔离 | `.dp-root` 作用域 + `dataPipeline.global.css` |
| HTTP 客户端 | 原生 `fetch`（非 axios） |
| 3D 引擎 | three.js（`overview/`） |
| 测试 | 19 个 `*.test.ts`（Vitest 风格，**当前无法运行**） |

### 1.1 目录结构

```
src/dataPipeline/
├── api.ts                     # 主 API 客户端（48 个端点）
├── phoneFactoryApi.ts         # 手机工厂 API（2 个实例 × 20 端点）
├── collectionBatchesApi.ts    # 采集批次 API（4 端点）
├── types.ts                   # 全部 TS 类型（774 行，约 60 个 interface）
├── DataPipelineLayout.vue     # 布局壳
├── dataPipeline.global.css    # 全局样式（127 行）
├── assets/overview-icons/     # ★ 19 个 App 图标 .jpg（二进制）
├── views/                     # 19 个页面
├── components/                # 22 个组件
├── composables/               # 4 个组合式函数（+4 测试）
├── utils/                     # 13 个工具模块（+10 测试）
└── overview/                  # ★ three.js 3D 引擎（5 个文件）
```

---

## 2. 业务域：数据飞轮 8 阶段

`views/HomeView.vue:41-50` 定义 8 个阶段，构成飞轮环形导航：

| # | 阶段 | 路由 | 图标 | 页头说明 |
|---|---|---|---|---|
| 1 | 任务生成 | `/dataPipeline/task-generation/generate` | `Plus` | 从场景树生成新任务 |
| 2 | 轨迹采集 | `/dataPipeline/collection/tree-building` | `Collection` | 手机工厂并行采集 → 轨迹树 |
| 3 | 轨迹质检 | `/dataPipeline/quality` | `DataAnalysis` | Rubrics 生成与相对排序 |
| 4 | 轨迹纠偏 | `/dataPipeline/correction/expert-action` | `EditPen` | 专家介入修正动作 / 生成 CoT |
| 5 | 数据发布 | `/dataPipeline/data-publishing/archive` | `Upload` | 训练数据归档 |
| 6 | 模型训练 | `/dataPipeline/model-training/launch` | `Cpu` | 数据配比 → 划分 → 训练 → 验证 |
| 7 | 模型发布 | `/dataPipeline/model-publishing` | `Promotion` | 增训模型归档 |
| 8 | 迭代评估 | `/dataPipeline/model-iteration-evaluation` | `TrendCharts` | 回到阶段 1 闭环 |

**飞轮视觉**（`HomeView.vue`）：

- `.flywheel-visual` 圆形，`aspect-ratio: 1`，中心 `.flywheel-visual__core`（`DATA / FLYWHEEL`）。
- `nodeStyle(index)` 按角度布局节点：
  ```js
  const angle = (index / stages.length) * Math.PI * 2 - Math.PI / 2
  return { left: `${50 + Math.cos(angle)*43}%`, top: `${50 + Math.sin(angle)*43}%` }
  ```
- 三层同心圆：外圈（本体边框）、`::before` `inset: 14%`、`::after` `inset: 27%`（虚线）。
- 下方 `.journey-grid` 用 `repeat(8, minmax(105px,1fr))` 展示 8 张卡片。
- 响应式：`max-width: 1100px` 时飞轮隐藏、网格 4 列；`800px` 时 2 列。

**Hub 按钮**（`HomeView.vue:9-13`）：查看总览 / 进入自动 Pipeline / 进入专家工作台 /
训练数据总览 / 手机工厂监控。

---

## 3. 页面（views/）详解

### 3.1 `HomeView.vue`（71 行）

飞轮导航首页，见上节。

### 3.2 `PipelineView.vue`（253 行）— 自动 Pipeline

**状态机**

```ts
type PipelineStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed'
type StepStatus     = 'pending' | 'running' | 'completed' | 'failed'
```

**接口**

```ts
interface PipelineConfig   { iterationName: string; seedTaskSet: string; targetModel: string }
interface PersistedPipeline {
  version: number; config: PipelineConfig; status: PipelineStatus;
  activeStepIndex: number; stepStatuses: Record<string, StepStatus>
}
```

**7 个阶段 / 12 个步骤**（`PipelineView.vue:14-22`）

| # | 阶段 | 步骤 id | 步骤名 |
|---|---|---|---|
| 1 | 迭代评估 | `seed-evaluation` | 种子任务集评测 |
| | | `badcase-extraction` | BadCase 提取 |
| 2 | 任务生成 | `badcase-augmentation` | BadCase 扩增 |
| 3 | 轨迹采集 | `phone-factory` | 手机工厂并行采集 |
| | | `bounding-box` | 标框 |
| | | `page-summary` | 页面总结 |
| | | `tree-building` | 轨迹树构建 |
| 4 | 轨迹质检 | `rubrics-generation` | Rubrics 生成 |
| | | `rubrics-ranking` | Rubrics 相对排序 |
| 5 | 数据发布 | `training-data-archive` | 训练数据归档 |
| 6 | 模型训练 | `data-mixture` | 训练数据配比 |
| | | `dataset-split` | 训练集/验证集划分 |
| | | `model-training` | 模型训练 |
| | | `training-validation` | 训练有效性验证 |
| 7 | 模型发布 | `trained-model-archive` | 增训模型归档 |

**核心机制**

```js
const STEP_DURATION = 1800      // 每步 1800ms（纯前端演示节奏）
const STORAGE_KEY = 'automatic-pipeline-circuit-v3'
const executionQueue = stages.flatMap((stage, stageIndex) =>
  stage.steps.map(step => ({ ...step, stageId, stageName, stageIndex })))
```

| 函数 | 行号 | 说明 |
|---|---|---|
| `stageStatus(stage)` | 39 | failed > running > 全 completed > pending |
| `branchStatus(stage, i)` | 46 | 前置全完成且阶段已启动 → `running` |
| `connectorStatus(i)` | 51 | 阶段完成的连线状态 |
| `clearTimer()` | 54 | 清 `setTimeout` |
| `scheduleNext()` | 55 | **递归 setTimeout** 推进步骤 |
| `openCreate()` | 67 | 打开新建对话框（重置 draft） |
| `createAndStart()` | 72 | 全部重置 → 步骤 0 running → `scheduleNext()` |
| `pausePipeline()` | 79 | 清 timer，status = paused |
| `resumePipeline()` | 80 | status = running，重新 schedule |
| `retryPipeline()` | 81 | 失败步骤重跑 |
| `restorePipeline()` | 82 | 读 localStorage；**version ≠ 3 则丢弃** |

**持久化**（`:92-96`）：深度 watch，`status === 'idle'` 时不写入；
`onMounted(restorePipeline)`；`onBeforeUnmount(clearTimer)`。

**关键防错**：恢复时若 `saved.status === 'running'` → 降级为 `'paused'`（避免刷新后"幽灵运行"）。

**UI 结构**：`.circuit-shell`（深色→浅色工程电路板风格，源码中含 3 轮主题覆盖样式）

- `.run-strip`：运行信号灯 + 迭代名 + 当前步骤 + 暂停/继续/重试按钮
- `.circuit-board`：`grid-template-columns: repeat(7,180px)`，主总线 + 阶段圆环节点 + 分支步骤卡
- 动画：`@keyframes current`（总线电流）、`@keyframes signal`（信号闪烁）
- 配色：运行中 `#22d3ee`/`#06b6d4`/`#6366f1`，完成 `#10b981`/`#34d399`，失败 `#ef4444`

### 3.3 `OverviewView.vue`（100 行）— 3D 全景总览

```ts
type SceneDatum = { name: string; apps?: string[]; children?: SceneDatum[] }
type OverviewState = { path: Array<{level, name, apps?}>; rootExpanded: boolean }
type OverviewManager = { init, dispose, toggleRoot, collapseAll, reset }
```

**数据加载**（`onMounted`）：

```js
let data = fallbackSceneData                       // 兜底示例数据
try {
  const tree = await api.taskGenerationTree()
  if (tree.scenes.length) data = tree.scenes.map(toSceneDatum)
  else source.value = 'fallback'
} catch { source.value = 'fallback' }
```

`toSceneDatum(node)`：取 `node.label` 为 name，`node.app_configs[].app` 过滤空值为 apps，
递归 children；**空数组则不输出该字段**。

**生命周期**：`new SceneManager(viewer.value, { data, onState })` → `init()` → `toggleRoot()`；
`onBeforeUnmount` → `manager.dispose()`。

**注意**：`SceneManager` 与 `fallbackSceneData` 用 `@ts-expect-error` 导入
（因为它们是**纯 ES Module 的 JS**，非 TS）。

**UI**：全屏深色 `#07111f`，含 `overview-header`（标题 + 查看详情按钮）、
`overview-status`（状态胶囊）、`overview-tools`（重置视图 / 收起场景）。

### 3.4 `TaskGenerationView.vue`

- 加载知识库 + 场景树：`Promise.all([api.taskGenerationKnowledgeBases(), api.taskGenerationTree()])`
- 上传知识库：`api.replaceTaskGenerationKnowledgeBase(kind, file, version?)`
- 创建任务：`api.createTaskGeneration(selections, generateN, version)`
- 使用 `useTaskGenerationReview` composable
- 组件：`TaskGenerationScope`、`TaskGenerationResults`、`TaskGenerationResultRow`、`ScenarioTreeCanvas`

### 3.5 `TaskAugmentationView.vue`（352 行）— BadCase 扩增

- 持久化：`localStorage['task-augmentation:selected-job']`（try/catch 包裹，容忍 storage 不可用）
- 使用 `useAugmentationPreview` composable
- 组件：`AugmentationSceneTree`、`AugmentationSceneTreeBranch`、`CollectionBatchSubmission`
- 关联工具：`augmentationReview.ts`、`augmentationSceneTree.ts`

### 3.6 `CollectionView.vue`（220 行）— 轨迹树构建

```js
const ACTIVE_JOB_KEY = 'trajectory-tree-active-job'

// 创建构建
job.value = await api.createBuild(selected.value)
localStorage.setItem(ACTIVE_JOB_KEY, job.value.job_id)

// 恢复轮询
const jobId = job.value?.job_id || localStorage.getItem(ACTIVE_JOB_KEY)
job.value = await api.build(jobId)
// 完成/失败时 removeItem
onMounted: if (localStorage.getItem(ACTIVE_JOB_KEY)) await pollJob()
```

- 数据加载：`api.tasks()` → `api.trajectories(taskId)` → `api.trajectory(taskId, trajectoryId)`
- 内部导航：`-> /dataPipeline/collection/phone-factory`（`CollectionBatchSubmission.vue:23`）
- 组件：`TrajectoryExplorer`、`ReferenceTrajectoryTree`、`Treeview`

### 3.7 `PhoneFactoryView.vue`（366 行）— 手机工厂监控

| 行号 | 定时器 | 间隔 | 说明 |
|---|---|---|---|
| 277 | `monitorTimer = setInterval(refreshMonitor, 1000)` | 1 秒 | 画面刷新 |
| 291 | `timer = setInterval(pollConnections, 10000)` | 10 秒 | ADB 连接状态 |

- API：`phoneFactoryApi`（base `/api/phone-factory`，runMode `generate`）
- 组件：`ActionImage`、`TrendCharts`

### 3.8 `PhoneFactoryCollectionView.vue`（598 行）

| 行号 | 定时器 | 间隔 |
|---|---|---|
| 530 | `statusTimer = setInterval(pollStatuses, 3000)` | 3 秒 |
| 532 | `connectionTimer = setInterval(pollConnections, 10000)` | 10 秒 |

- 使用 `useCollectionBatchSubmission`
- 组件：`CollectionBatchSubmission`、`DatasetUploadReceipts`

### 3.9 `QualityView.vue`（~180 行）— 轨迹质检

```js
runs.value = await api.runs()                      // 树运行列表
api.runQuality(selectedRunId)                       // 各任务质检汇总
api.qualityJobs()                                   // 质检任务列表
api.correctionRecommendation(runId)                 // 纠偏推荐
api.tree(runId, taskId) / api.taskQuality(runId, taskId)
api.createQuality(runId, checkedTasks) → startPolling()

function startPolling() { stopPolling(); pollTimer = window.setInterval(() => void pollJobs(), 1200) }
```

- 支持 `route.query.run` 指定运行 id（校验存在性，否则取首个）
- 内部导航：`/dataPipeline/collection`（`:129`）、`/dataPipeline/correction`（`:133`，带 query）
  → ⚠️ **这两个路径在 router 中不存在**（见 08 文档第 4 节）

### 3.10 `CorrectionView.vue`（201 行）— 专家纠偏

```js
const sessions = await api.correctionSessions()
const saved    = await api.correctionSession(existing.session_id)
const recommendation = await api.correctionRecommendation(treeRunId)
const created  = await api.createCorrectionSession(treeRunId)
const result   = await api.correctionBatches()
```

- 使用 `useCorrectionWorkspace` composable
- 组件：`CorrectionWorkbench`、`CorrectionActionEditor`
- 内部导航：`-> /dataPipeline/quality`

### 3.11 `CotGenerationView.vue`（336 行）— CoT 生成

| 行号 | 逻辑 |
|---|---|
| 84 | `api.correctionSessionCot(sessionId)` |
| 100 | `api.correctionCotJob(jobId)` 轮询 |
| 119 | `timer = window.setInterval(() => void pollJob(), 1200)` |
| 126 | `api.correctionSessions()` |
| 164/192 | `api.patchCorrectionRow(sessionId, row.excel_row, {...})` |
| 208/233 | `api.createCorrectionCotJob(...)` |
| 245 | `api.correctionDatasetExport(sessionId)` |

`patchCorrectionRow` 的典型补丁：`{ actions_box: serializeBBox(row, box) }` 或 `{ [field]: textDraft }`。

生成 BBox 的调用：`createCorrectionCotJob(sid, undefined, undefined, { generateBBox: true, forceOverwrite: true })`。

### 3.12 `DataPublishingView.vue`（350 行）— 数据发布

```js
const ACTIVE_UPLOAD_KEY = 'agentic-data-flywheel.active-internal-dataset-upload'

Promise.all([
  api.datasetReleaseCandidates(),
  api.datasetReleases(),
  api.datasetUploadCapabilities().catch(() => ({
    internal: { configured: false, reason: '无法读取云道S3上传配置，请刷新重试' }
  })),
])

api.createDatasetRelease(name, selectedSessionIds)
api.uploadDatasetRelease(release.release_id, 'internal')
api.datasetUploadJob(jobId)
// job.mode !== 'internal' → removeItem(ACTIVE_UPLOAD_KEY)
// 恢复：localStorage.getItem(ACTIVE_UPLOAD_KEY)
```

- 组件：`DatasetUploadReceipts`
- 工具：`datasetUploadMessage.ts`

### 3.13 `TrainingDataOverviewView.vue`

训练数据总览（发布结果的汇总视图）。

### 3.14 `TrainingDataMixtureView.vue`（264 行）

```js
datasets.value = await api.datasetReleases()
```

- 使用 `trainingMixtureStore.ts`

### 3.15 `ModelTrainingView.vue`（248 行）

- 内部导航：`-> /dataPipeline/model-publishing`（`:198`）
- 使用 `modelPublishingStore`、`trainingValidationStore`

### 3.16 `TrainingValidationView.vue`（179 行）

- 使用 `trainingValidationStore.ts`

### 3.17 `ModelPublishingView.vue`

- 使用 `modelPublishingStore.ts`（含 `createTrainingMonitor`）

### 3.18 `ModelIterationEvaluationView.vue`（686 行）

```js
statusTimer = window.setInterval(pollStatuses, 3000)   // :608
```

- API：`modelIterEvalApi`（base `/api/model-iter`，runMode **`modeliter`**）

### 3.19 `ScenarioStudioView.vue`（213 行）

```js
const payload = await api.taskGenerationTree()   // :50
```

- 支持 `mode` query（`'treeHome' | 'editor'`）
- 组件：`ScenarioTreeHome`、`ScenarioTreeWorkbench`、`ScenarioEditor`、`ScenarioColumn`

### 3.20 `ScenarioTreeEditorView.vue`

- 组件：`ScenarioEditor`、`ScenarioTreeCanvas`、`CapabilityTree`

---

## 4. 组件（components/）清单

| 文件 | 行数 | 职责 |
|---|---|---|
| `ActionImage.vue` | 256 | 动作截图 + BBox 叠加绘制 |
| `AugmentationSceneTree.vue` | | 扩增场景树 |
| `AugmentationSceneTreeBranch.vue` | | 扩增树分支 |
| `CapabilityTree.vue` | | 能力树 |
| `CapabilityTreeNode.vue` | | 能力树节点 |
| `CollectionBatchSubmission.vue` | | 采集批次提交（+ 测试） |
| `CorrectionActionEditor.vue` | 239 | 纠偏动作编辑器 |
| `CorrectionWorkbench.vue` | | 纠偏工作台 |
| `DatasetUploadReceipts.vue` | | 上传回执列表 |
| `ReferenceTrajectoryTree.vue` | 246 | 参考轨迹树 |
| `ScenarioAppBindingPopover.vue` | | 场景-App 绑定气泡 |
| `ScenarioColumn.vue` | | 场景列 |
| `ScenarioEditor.vue` | | 场景编辑器 |
| `ScenarioTreeCanvas.vue` | | 场景树画布 |
| `ScenarioTreeHome.vue` | | 场景树首页 |
| `ScenarioTreeWorkbench.vue` | **682** | 场景树工作台（最大组件） |
| `TaskGenerationResultRow.vue` | | 任务生成结果行 |
| `TaskGenerationResults.vue` | | 任务生成结果列表 |
| `TaskGenerationScope.vue` | | 任务生成范围选择 |
| `TrajectoryExplorer.vue` | | 轨迹浏览器 |
| `TreeNodeCard.vue` | | 树节点卡片 |

---

## 5. 组合式函数（composables/）

| 文件 | 导出 | 说明 |
|---|---|---|
| `useAugmentationPreview.ts` | `useAugmentationPreview(api, feedback)` | 扩增预览状态机（+ 测试 221 行） |
| `useCollectionBatchSubmission.ts` | `useCollectionBatchSubmission(api, options)`；type `RunCollectionBatchAction` | 采集批次提交（+ 测试） |
| `useCorrectionWorkspace.ts` | `useCorrectionWorkspace(api, feedback)`；type `ActionDecision = 'save'\|'discard'\|'cancel'` | 纠偏工作区（+ 测试 222 行） |
| `useTaskGenerationReview.ts` | `useTaskGenerationReview(api, feedback)` | 任务生成复核（+ 测试） |

**设计模式**：全部采用 **依赖注入**（`api` 与 `feedback` 由调用方传入），
便于在测试中传入假实现（这也是为什么这些文件几乎都有配套测试）。

---

## 6. 工具模块（utils/）

### 6.1 场景树 —— `scenarioTree.ts`（179 行）

**常量**

```js
export const NODE_LABELS = { ... }   // 节点层级中文名
export const NODE_LEVELS = { ... }   // 节点层级枚举
```

**导出函数**

| 函数 | 行号 | 说明 |
|---|---|---|
| `appNodes(taskType)` | 27 | 从 taskType 提取 app 节点 |
| `normalizeTree(nodes)` | 42 | 规范化树结构 |
| `withInlineAddActions(nodes)` | 54 | 注入「内联添加」操作节点 |
| `leaves(nodes)` | 65 | 取所有叶子 |
| `findNode(nodes, id)` | 69 | 按 id 查找 |
| `nodePath(nodes, id, prefix=[])` | 77 | 返回从根到节点的路径 |
| `parentOf(nodes, id)` | 87 | 查父节点 |
| `editableTree(nodes)` | 95 | 转为可编辑副本 |
| `appConfigs(apps, existing)` | 105 | 构造 `TaskTypeAppConfig[]` |
| `selectionsFor(nodes, checked, selectedApps)` | 111 | 生成 `TaskGenerationSelection[]` |
| `executionUnitCount(selections)` | 118 | 计算执行单元数 |
| `descendantIds(node)` | 122 | 全部后代 id |
| `canMove(node, target)` | 126 | 移动合法性（防循环） |
| `moveNode(nodes, nodeId, targetId)` | 133 | 移动 |
| `reorderNode(nodes, nodeId, targetId)` | 144 | 同级重排 |
| `removeNode(nodes, id)` | 163 | 删除 |
| `searchNodes(nodes, text)` | 169 | 搜索 |

### 6.2 任务生成 —— `taskGeneration.ts`

```ts
export type AppSelection = Record<string, string[]>
export function generationDirectory(tree)                       // 可生成目录
export function generationCandidates(tree, scope, query)        // 候选过滤
export function reconcileApps(tree, selected)                   // 对齐选择
export function selectCandidates(selected, nodes): AppSelection
export const jobLabels: Record<TaskGenerationJob['status'], string>   // 状态中文
```

### 6.3 扩增 —— `augmentationSceneTree.ts` / `augmentationReview.ts`

`augmentationSceneTree.ts`：

```js
export const AUGMENTATION_STATE_LABELS = { ... }
export type AugmentationNodeState = keyof typeof AUGMENTATION_STATE_LABELS
export type AugmentationTreeDisplayMode = 'related' | 'all'
```

| 函数 | 说明 |
|---|---|
| `visibleAugmentationScenes(model, mode)` | 按模式过滤可见场景 |
| `augmentationNodeState(status)` | `generation_status` → 节点状态 |
| `indexAugmentationSceneTree(tree)` | 建索引 |
| `associateAugmentationSeeds(index, seeds)` | 关联种子 |
| `buildAugmentationSceneTree(tree, seeds)` | **主入口**：树 + 种子 → 模型 |
| `expandNewAugmentationSeeds(model, previous)` | 自动展开新增种子 |
| `expandFocusedAugmentationSeed(model, expanded, seedId?)` | 展开定位种子 |

`augmentationReview.ts`：`augmentationResultGroupId(row)`、`groupAugmentationResults(results, seeds)`。

### 6.4 动作叠加 —— `actionOverlay.ts`

| 导出 | 说明 |
|---|---|
| `interface BBox` | 解析后的边界框 |
| `interface Point` | 归一化坐标点 |
| `parseBBox(value)` | 字符串 → `BBox \| null` |
| `normalizedPoint(value, width, height)` | 原始坐标 → 归一化 `Point \| null` |
| `actionKind(action)` | 动作类型字符串 |
| `swipeDirection(actionsBox)` | `'left'\|'right'\|'up'\|'down'\|null` |
| `fallbackSwipePoints(box, direction)` | 无坐标时的兜底滑动起止点 |

### 6.5 场景总览 —— `scenarioOverview.ts`

| 导出 | 说明 |
|---|---|
| `interface ScenarioMetrics` | 场景指标（数量、App 数等） |
| `interface ScenarioDomainSummary` | 领域汇总 |
| `interface ScenarioSpotlightSummary` | 焦点摘要 |
| `interface CapabilityTreePosition` | 能力树节点坐标 |
| `interface CapabilityTreeGeometry` | 能力树几何 |
| `scenarioMetrics(nodes)` | 计算指标 |
| `scenarioDomains(nodes)` | 领域分组 |
| `scenarioSpotlight(domain, limit=6)` | 焦点摘要 |
| `capabilityNodeHeight(domain, expanded=false)` | 节点高度 |
| `scenarioIcon(label)` | 图标映射 |
| `capabilityTreeGeometry(domains, availableWidth=1000, expandedId='')` | 几何计算 |
| `capabilityTreeLayout(domains)` | 布局坐标 |

### 6.6 场景工作室 —— `scenarioStudio.ts`

```ts
export type ScenarioStudioMode = 'treeHome' | 'editor'
export function queryValue(value)                                    // 归一化 query 值
export function scenarioStudioMode(query)                            // 解析 mode
export function scenarioStudioInitialNodeId(query)                   // 初始节点 id
export function sceneIdForNode(nodes, nodeId)                        // 节点 → 场景 id
export function legacyScenarioStudioQuery(query)                     // 旧版 query 兼容
```

### 6.7 纠偏任务 —— `correctionTasks.ts`

`correctionTasks(selection, groups)` → `CorrectionTaskItem[]`（合并推荐与分组）。

### 6.8 上传消息 —— `datasetUploadMessage.ts`

`datasetUploadMessage(message)` → 中文友好的提示文案（容错 `null`/`undefined`）。

### 6.9 三个「Store」工具（非 Pinia，纯函数 + localStorage）

这三个模块**不是 Pinia store**，而是「read/save + 事件广播」的轻量持久化层，
每个都支持注入 `StorageLike`（便于测试）。

#### `modelPublishingStore.ts`

```js
export const MODEL_PUBLISHING_STORAGE_KEY = 'agentic-data-flywheel.model-publishing.v1'
export const MODEL_PUBLISHING_EVENT       = 'agentic-data-flywheel:model-publishing-changed'

export interface StorageLike { getItem; setItem; removeItem }
export interface CreateMonitorInput { ... }

export function emptyModelPublishingState(): ModelPublishingState
export function readModelPublishingState(storage = browserStorage()): ModelPublishingState
export function saveModelPublishingState(state, storage = browserStorage()): void
export function createTrainingMonitor(...)     // 创建训练监控记录
```

- 读取失败时 `removeItem` 清理脏数据。
- 写入后广播 `MODEL_PUBLISHING_EVENT`（`window.dispatchEvent`）供跨组件刷新。

#### `trainingMixtureStore.ts`

```js
export const TRAINING_MIXTURE_STORAGE_KEY = 'agentic-data-flywheel.training-mixture.v1'
```

同样有 `empty/read/save` 三件套。

#### `trainingValidationStore.ts`

```js
export const TRAINING_VALIDATION_STORAGE_KEY = 'agentic-data-flywheel.training-validation.v1'
```

同样有 `empty/read/save` 三件套。

---

## 7. 3D 总览引擎（overview/）

### 7.1 `SceneManager.js`（682 行，three.js）

**类接口**

```js
export default class SceneManager {
  constructor(container, { data, onState })
  init()          // :40   初始化场景、相机、渲染器、事件
  dispose()       // :75   释放 geometry/material/texture/renderer
  toggleRoot()    // :428  展开/收起根节点
  collapseBelow(level)  // :444
  collapseAll()   // :453
  reset()         // :461  collapseAll + ...
  project(v)      // :485  3D → 2D 投影
}
```

**外部依赖**：`three`、`./textures.js`、`./tree.js`、`./icons.js`

**关键常量**

```js
const TAU = Math.PI * 2
const LEVEL_CFG = { y: 2.05, rCap: 0.3, baseR: 2.5,
                    stops: [[0,'#ecfeff'],[0.56,'#99f6e4'],[1,'#14b8a6']] }
const ROOT_CFG  = { y: 5.25, r: 0.5,
                    stops: [[0,'#f0fdfa'],[0.52,'#5eead4'],[1,'#0f766e']] }
const FLYWHEEL_STAGES = ['场景生成','数据生产','数据质检','轨迹修正','模型训练','模型评估']
const FLYWHEEL_ROUNDS = [
  { total: 34,  color: 0x7187a6 },
  { total: 48,  color: 0x7898ad },
  { total: 63,  color: 0x72a9ad },
  { total: 82,  color: 0x79bbb0 },
  { total: 100, color: 0x9ed8c2, latest: true },   // 最近一轮半径固定 3.2
]
```

**视觉结构**：

1. **场景树**：一级场景圆环直连 App（`LEVEL_CFG`，y=2.05，底半径 2.5）
2. **树根**：`ROOT_CFG`（y=5.25）
3. **数据飞轮**：树根下方 5 轮同心圆，最近一轮半径固定 3.2，其余按 `total` 相对缩放

**交互**：

- 点击 `kind === 'root'` 的物体 → `toggleRoot()`
- `Escape` 键 → `collapseAll()`（`:524`）
- 状态变化通过 `onState({ path, rootExpanded })` 回调给 Vue（`:481`）
- `update()` 中检查 `this._disposed` 后直接 return（`:610`）防渲染竞争

**资源释放**（`dispose()` + `:403-407`）：遍历释放 `geometry`、`material`、
`material.map`（**跳过 `__shared` 标记的共享纹理**）、`renderer.dispose()`。
`:501-504` 额外释放 vine 相关几何/材质。

### 7.2 `textures.js`（276 行，全部为 Canvas 程序化纹理）

| 导出函数 | 行号 | 说明 |
|---|---|---|
| `makeCanvas(w, h)` | 4 | 创建离屏 canvas |
| `makeSphereTexture(stops, text)` | 23 | 球体贴图（渐变 + 文字） |
| `makeCircleTexture(stops)` | 91 | 圆形渐变贴图 |
| `makeGlowTexture()` | 113 | 辉光贴图 |
| `makeCaptionTexture(text)` | 132 | 标题贴图 |
| `makeNodeLabelTexture(text)` | 175 | 节点标签贴图 |
| `makeLabelTexture(text, fontSize=44)` | 211 | 通用标签贴图 |
| `makeLetterIconTexture(name)` | 255 | **字母兜底图标**（首字母渲染） |

> ✅ **重要**：因为存在 `makeLetterIconTexture` 兜底，
> 即使 **19 个 `overview-icons/*.jpg` 缺失，3D 总览仍可运行**（显示字母图标）。

### 7.3 `icons.js`（27 行）

```js
import * as THREE from 'three';
import { makeLetterIconTexture } from './textures.js';

const modules = import.meta.glob('../assets/overview-icons/*.jpg',
                                 { eager: true, import: 'default' })
const cache = new Map();

export function getAppIconTexture(appName) {
  if (cache.has(appName)) return cache.get(appName);
  const url = modules[`../assets/overview-icons/${appName}.jpg`];
  let tex;
  if (url) {
    tex = new THREE.TextureLoader().load(url);
    tex.colorSpace = THREE.SRGBColorSpace;
  } else {
    tex = makeLetterIconTexture(appName);      // 兜底
  }
  cache.set(appName, tex);
  return tex;
}
```

- 使用 **`import.meta.glob`** 静态收集所有图标 URL（Vite 特性，构建时内联）。
- **纹理缓存**（`Map`）：同一 App 只加载一次。
- 文件名必须与 App 名**完全一致**（含中文），否则走字母兜底。

### 7.4 `tree.js`（~80 行）

```js
export const TREE_COLOR = 0xdce4f0;
export function buildTreeGroup()   // 构建树形 3D 分组
```

### 7.5 `fallbackSceneData.js`（518 行）

`export default [ ... ]` —— 静态兜底场景数据（默认导出数组）。
当 `api.taskGenerationTree()` 失败或返回空时使用。

---

## 8. 类型系统（types.ts，774 行）

约 60 个 `interface`，按域分组：

| 域 | 主要类型 |
|---|---|
| 基础 | `ActionPayload = Record<string, unknown>` |
| 任务/轨迹 | `TaskSummary`、`TrajectoryStep`、`TrajectoryRecord`、`TrajectorySummary` |
| 构建 | `BuildJob` |
| 质检 | `QualityJob`、`QualityTaskSummary`、`RunQualitySummary`、`DimensionEvaluation`、`StepQualityEvaluation`、`TrajectoryQualityEvaluation`、`TaskQualityResult` |
| 树运行 | `TreeRunTask`、`TreeRun`、`ClassificationResult`、`TreeOccurrence`、`AuditStep`、`SourceTrajectory`、`TrajectoryTreeNode` |
| 纠偏 | `CorrectionSource`、`CorrectionTop1Task`、`CorrectionRecommendation`、`CorrectionBatch`、`CorrectionRow`、`CorrectionGroupSummary`、`CorrectionGroup`、`CorrectionCotRow`、`CorrectionCotGroup`、`CorrectionCotResponse`、`CorrectionCotJob`、`CorrectionTrajectoryItem`、`CorrectionTaskItem`、`CorrectionExport`、`CorrectionSession` |
| 任务生成 | `KnowledgeBaseSummary`、`TaskTypeAppConfig`、`TaskGenerationTreeNode`、`TaskGenerationTree`、`TaskGenerationSelection`、`TaskGenerationResult`、`TaskGenerationJob`、`TaskGenerationExport` |
| 扩增 | `AugmentationSeed`、`AugmentationPreview` |
| 数据发布 | `DatasetReleaseCandidate`、`DatasetReleaseExcel`、`DatasetUploadStatus`（`'not_uploaded'\|'queued'\|'uploading'\|'succeeded'\|'failed'\|'interrupted'`）、`DatasetUploadCapabilities`、`DatasetUploadFileResult`、`DatasetInternalUpload`、`DatasetRelease`、`DatasetUploadJob` |
| 模型训练 | `ModelTrainingMonitor`、`ModelArtifact`、`ModelPublishingState`、`TrainingMixtureJob`、`TrainingMixtureState`、`TrainingValidationMetricGroup`、`TrainingValidationReport`、`TrainingValidationState` |

---

## 9. API 与存储

- **API 清单**：见 [04 文档](./04-API层与后端接口契约.md) 第十节（三个文件、约 72 个端点）。
- **localStorage 键**：

| Key | 写入点 |
|---|---|
| `automatic-pipeline-circuit-v3` | `PipelineView.vue:12` |
| `trajectory-tree-active-job` | `CollectionView.vue:9` |
| `agentic-data-flywheel.active-internal-dataset-upload` | `DataPublishingView.vue:10` |
| `task-augmentation:selected-job` | `TaskAugmentationView.vue:43` |
| `agentic-data-flywheel.model-publishing.v1` | `modelPublishingStore.ts:3` |
| `agentic-data-flywheel.training-mixture.v1` | `trainingMixtureStore.ts:4` |
| `agentic-data-flywheel.training-validation.v1` | `trainingValidationStore.ts:13` |

---

## 10. 测试

### 10.1 测试文件（19 个）

| 位置 | 文件 |
|---|---|
| 根 | `collectionBatchesApi.test.ts`、`datasetPublishingApi.test.ts` |
| `components/` | `CollectionBatchSubmission.test.ts` |
| `composables/` | `useAugmentationPreview.test.ts`、`useCollectionBatchSubmission.test.ts`、`useCorrectionWorkspace.test.ts`、`useTaskGenerationReview.test.ts` |
| `utils/` | `actionOverlay.test.ts`、`augmentationReview.test.ts`、`augmentationSceneTree.test.ts`、`datasetUploadMessage.test.ts`、`modelPublishingStore.test.ts`、`scenarioOverview.test.ts`、`scenarioStudio.test.ts`、`scenarioTree.test.ts`、`taskGeneration.test.ts`、`trainingMixtureStore.test.ts`、`trainingValidationStore.test.ts` |
| `views/` | `TaskAugmentationView.test.ts` |

### 10.2 测试风格（Vitest）

- `import { describe, it, expect } from 'vitest'`（或全局）
- 使用 `rejects.toThrow`
- 使用 `import.meta.env`
- 依赖注入的 `api` / `feedback` 假实现

### 10.3 ⚠️ 当前无法运行

- `package.json` **没有 `test` 脚本**
- **未安装 `vitest`**
- 因此这 19 个测试文件目前是**纯文本资产**，无法执行。

**恢复方式**：

```bash
npm i -D vitest
# 在 package.json scripts 中加入：
"test": "vitest run",
"test:watch": "vitest"
```

---

## 11. 样式隔离机制

`dataPipeline.global.css` 的关键设计：

1. **设计变量挂在 `.dp-root`**（而非 `:root`）：
   ```css
   .dp-root {
     --ink:#0f172a; --muted:#64748b; --line:#dce5eb;
     --accent:#14b8a6; --accent-deep:#0f766e;
     --panel:#ffffff; --accent-soft:rgba(20,184,166,.08);
     --shadow:0 18px 45px rgba(32,54,89,.08);
   }
   ```
   → 避免与 `public/llm_bench/styles.css` 的 `:root` 变量冲突。

2. **Element Plus 局部覆盖**全部加 `.dp-root` 前缀：
   `.dp-root .el-collapse`、`.dp-root .el-table` 等。

3. **Vue Flow 样式**（`:102-112`）：
   ```css
   .dp-root .vue-flow__node { border:none; padding:0; background:none; box-shadow:none; }
   .dp-root .vue-flow__node.selected .tree-node { outline: 2px solid #14b8a6; }
   ```
   > ⚠️ `@vue-flow/core` **未安装**。若某组件真的渲染了 Vue Flow 节点，
   > 需要补装；若只是历史样式残留，可忽略。

4. **响应式**：`@media (max-width: 900px)` 统一调整 padding 与 hero 布局。

---

## 12. 与原仓库的差异（迁移适配点）

| # | 文件 | 差异 |
|---|---|---|
| 1 | `components/CollectionBatchSubmission.vue:23` | 路由前缀改为 `/dataPipeline/collection/phone-factory` |
| 2 | `views/CollectionView.vue:149` | 路由前缀改为 `/dataPipeline/quality` |
| 3 | `views/ModelTrainingView.vue:198` | 路由前缀改为 `/dataPipeline/model-publishing` |
| 4 | `views/QualityView.vue:129,133` | 路由前缀改为 `/dataPipeline/*` |
| 5 | `views/HomeView.vue:11-12,42-49` | 全部路径加 `/dataPipeline` 前缀，并**新增**「查看总览」入口 |
| 6 | 模块新增（原仓库无） | `DataPipelineLayout.vue`、`dataPipeline.global.css`、`views/OverviewView.vue`、`overview/*`（5 文件）、`assets/overview-icons/*.jpg`（19 个） |
| 7 | 模块删除（原仓库有） | `App.vue`、`main.ts`、`router.ts`、`styles.css`、`env.d.ts` |
| 8 | 导入路径 | 全部 `@/...` 改写为 `@/dataPipeline/...`（经归一化比对，**0 处未解析**） |
| 9 | **遗漏** | 原 `router.ts` 中 `{path:'/collection', redirect:'/collection/tree-building'}` 与 `{path:'/correction', redirect:'/correction/expert-action'}` **未带入** → 2 处断链（见 08 文档） |

---

**上一篇：** [05 · 业务模块说明](./05-业务模块说明.md) ｜
**下一篇：** [07 · 静态资源与二进制文件清单](./07-静态资源与二进制文件清单.md)
