# 04 · API 层与后端接口契约

> 本文档只描述**前端调用契约**（URL、方法、请求体、响应结构），不涉及后端实现。

---

## 一、基础地址（硬编码）

全部定义在 `src/utils/Constants.js`：

```js
export const URLS = {
    BASE: 'http://icap.rnd.huawei.com',
    BASE_HTTPS: 'https://icap.rnd.huawei.com',
    SESSION: '/unisess/v1/auth/session',
    WS: '/websocket/ccnfaultrecovery/v1/ws',
};

// ★ 主 API 基址：按当前页面协议自动切换 http/https
export const API_BASE_URL = window.location.protocol.startsWith('https')
    ? URLS.BASE_HTTPS + '/v1/'
    : URLS.BASE + '/v1/';

export const API_AGENT_URL  = 'http://icap.rnd.huawei.com/v1/';
export const AI_SCHOOL_URL  = 'http://icap.rnd.huawei.com/v1/';
export const AI_SCHOOL_INDIVIDUAL_YELLOW_URL = 'http://7.216.57.45:11600/v1/';
export const AI_SCHOOL_INDIVIDUAL_GREEN_URL  = 'http://100.100.136.146:11600/v1/';
export const DATA_FACTORY_API = 'http://icap.rnd.huawei.com/v2/';
export const DATA_FACTORY_LOG_WS = 'ws://icap.rnd.huawei.com/v2/';
export const DEPLOY_API_BASE = 'http://7.216.57.45:10910/';
export const API_MENSHEN_URL = 'https://menshen-gamma.tool.huawei.com/api/AICollect/detail';
export const PAYLOAD_MENSHEN = { beginTime: null, endTime: null, product: "LLM" };
```

### 1.1 基址一览

| 常量 | 值 | 用途 |
|---|---|---|
| `URLS.BASE` | `http://icap.rnd.huawei.com` | HTTP 场景根 |
| `URLS.BASE_HTTPS` | `https://icap.rnd.huawei.com` | HTTPS 场景根 |
| `API_BASE_URL` | `${root}/v1/` | **主 API**（绝大多数模块） |
| `API_AGENT_URL` | `http://icap.rnd.huawei.com/v1/` | Agent 对话 |
| `AI_SCHOOL_URL` | `http://icap.rnd.huawei.com/v1/` | AI School |
| `AI_SCHOOL_INDIVIDUAL_YELLOW_URL` | `http://7.216.57.45:11600/v1/` | AI School 单机（黄区） |
| `AI_SCHOOL_INDIVIDUAL_GREEN_URL` | `http://100.100.136.146:11600/v1/` | AI School 单机（绿区） |
| `DATA_FACTORY_API` | `http://icap.rnd.huawei.com/v2/` | 数据工厂 VLA（**v2**） |
| `DATA_FACTORY_LOG_WS` | `ws://icap.rnd.huawei.com/v2/` | 数据工厂日志 WebSocket |
| `DEPLOY_API_BASE` | `http://7.216.57.45:10910/` | 模型部署服务（**独立端口 10910**） |
| `API_MENSHEN_URL` | `https://menshen-gamma.tool.huawei.com/api/AICollect/detail` | 门神平台采集 |
| `VITE_API_BASE_URL` | 环境变量（可空） | dataPipeline 模块前缀 |

### 1.2 全局超时与请求头

```js
export const DEFAULT_CONFIG = {
    headers: { 'Content-Type': 'application/json' },
    timeout: 5000,          // 5 秒
};

export const AXIOS_POST_CONFIG = {
    headers: { 'Content-Type': 'application/json' },
    timeout: 20000,         // 20 秒
};
```

### 1.3 其他常量

```js
export const STRINGS = { EMPTY: '', DASH: '-' };
export const INTERPRETATION_TAGS  = ["ASR", "MT", "TTS"];
export const INTERPRETATIONS_TYPES = ["ASR", "MT", "TTS", "ASR+MT", "ASR+MT+TTS"];
```

> ⚠️ 注意 `runService.js:25` 存在 `API_BASE_URL + '/v1/run_mt'`，
> 而 `API_BASE_URL` 已含 `/v1/`，最终路径为 `/v1/v1/run_mt`（**疑似 Bug**）。

---

## 二、`src/api/dataService.js` — 主数据服务

基址：`API_BASE_URL`（`/v1/`）

| 导出函数 | 方法 | 路径 | 请求 | 说明 |
|---|---|---|---|---|
| `getCurrentFullRes` | GET | `get_current_full_res` | — | 全量榜单数据（ruler1+ruler2） |
| `startRun` | POST | `run_testcase_ruler1` | body | 启动尺子一评测 |
| `startRunTest` | POST | `run_testcase_ruler1` | body | ⚠️ 与 `startRun` **同端点** |
| `addmodelSelect` | POST | `register_special_model` | body | 注册特殊模型 |
| `deletemodelSelectionByID` | POST | `delete_special_model_info` | body | 删除特殊模型 |
| `modifymodelSelect` | POST | `modify_special_model_info` | body | 修改特殊模型 |
| `getAllmodelSelect` | GET | `get_special_model_info` | — | 特殊模型列表 |
| `getMultiModelRuler2Data` | GET | `get_current_multi_full_res` | — | 多模型 ruler2 数据 |
| `getReportContent` | GET | `get_current_multi_full_res` | — | ⚠️ **复用同一端点** |
| `getMultiModelData` | GET | `get_current_multi_full_res` | — | ⚠️ **复用同一端点** |
| `getEvalReport` | GET | `get_eval_report` | — | 评测报告 |
| `modifyEvalReport` | POST | `modify_eval_report` | body | 修改评测报告 |
| `getEvalModelList` | GET | `get_eval_model_list` | — | 评测模型列表 |
| `modifyEvalModelList` | POST | `modify_eval_model_list` | body | 修改评测模型列表 |
| `getAIPerformanceData` | GET | `get_current_multi_full_res` | — | ⚠️ **复用同一端点** |
| `getModelsFileData` | POST | `get_models_file_data` | body | 模型文件数据 |
| `downloadModelsFile` | GET | `download_models_file` | `responseType:'blob'` | 下载模型文件 |
| `uploadModelsFile` | POST | `upload_models_file` | body | 上传模型文件 |
| `getFeedbackInfo` | POST | `get_feedback_info` | body | 查询反馈 |
| `modifyFeedbackInfo` | POST | `modify_feedback_info` | body | 修改反馈 |
| `deleteFeedbackInfo` | POST | `delete_feedback_info` | body | 删除反馈 |
| `registerFeedbackInfo` | POST | `register_feedback_info` | body | 新增反馈 |
| `addLogData` | POST | `add_log_data` | body | 新增日志 |
| `getLogData` | POST | `get_log_data` | body | 查询日志 |
| `modifyLogData` | POST | `modify_log_data` | body | 修改日志 |
| `addModelProgress` | POST | `add_model_progress` | body | 新增模型进度 |
| `getModelProgress` | GET | `get_model_progress` | — | 查询模型进度 |
| `modifyModelProgress` | POST | `modify_model_progress` | body | 修改模型进度 |
| `getEvaluationResult` | GET | `get_evaluation_result` | — | 评测结果 |
| `writeEvaluationResult` | POST | `write_evaluation_result` | body | 写入评测结果 |

> ⚠️ `getMultiModelRuler2Data` / `getReportContent` / `getMultiModelData` / `getAIPerformanceData`
> **四个函数调用完全相同的端点** `get_current_multi_full_res`，属历史遗留。

---

## 三、`src/api/runService.js` — 评测任务与报告

基址：`API_BASE_URL`

### 3.1 任务启动

| 函数 | 方法 | 路径 |
|---|---|---|
| `startRun` | POST | `run_testcase_ruler1` |
| `startRun2` | POST | `run_testcase_ruler2` |
| `startRunAisfRelease` | POST | `run_aisf_release` |
| `startRun3` | POST | `run_testcase_dev` |
| `startRunMul` | POST | `run_vlm_ruler1` |
| `startRunMt` | POST | `/v1/run_mt` ⚠️ 双 `/v1/` |
| `startRunMul2` | POST | `run_testcase_ruler1` |
| `startMCPAtlas` | POST | `run_testcase_mcp_atlas` |

### 3.2 任务管理

| 函数 | 方法 | 路径 | 说明 |
|---|---|---|---|
| `getList` | GET | `get_run_test_progress_list` | 任务列表 |
| `getProgress` | GET | `check_run_test_progress/{task_id}` | 任务进度 |
| `deleteById` | POST | `delete_test_progress` | 删除任务 |
| `pauseOneTask` | POST | `pause_test_task` | 暂停 |
| `resumeOneTask` | POST | `resume_test_task` | 继续 |
| `getResult` | POST | `get_result` | 获取结果 |
| `getFilePath` | POST | `get_file_path` | 获取文件路径 |
| `getLogs` | POST | `logs` | 日志 |
| `getOneTestTask` | POST | `get_one_test_task` | 单任务详情 |

### 3.3 评分与结果

| 函数 | 方法 | 路径 |
|---|---|---|
| `updateScore` | POST | `update_score` |
| `updateResult` | POST | `update_top_chart` |
| `asyncScore` | POST | `async_score` |
| `deleteResultById` | POST | `delete_single_result` |
| `uploadLocalResult` | POST | `upload_local_result` |
| `downloadFile` | POST | `download/file` |
| `getMinTestChart` | POST | `get_min_test_chart` |
| `getEldStatistics` | POST | `get_eld_statistics` |
| `getAgentFile` | POST | `get_file_path` ⚠️ 与 `getFilePath` 同端点 |

### 3.4 报告相关

| 函数 | 方法 | 路径 |
|---|---|---|
| `genReport` | POST | `generate_report` |
| `downloadEvalReport` | POST | `download/report` |
| `queryReportStatus` | GET | `query_report_status` |
| `getLatestReport` | GET | `get_latest_report` |
| `deleteReportTask` | DELETE | `delete_report_task` |
| `getReportTasksByName` | GET | `get_report_tasks_by_name` |
| `getAllReportTasks` | GET | `get_all_report_tasks` |
| `directPublishReport` | POST | `direct_publish_report` |
| `publishReportFromTask` | POST | `publish_report_from_task` |
| `getAllPublishedTasks` | GET | `get_all_published_tasks` |
| `previewReportFile` | POST | `preview/report` |
| `deletePublishedTask` | DELETE | `delete_published_task` |
| `updatePublishedReport` | POST | `update_published_report` |

---

## 四、`src/api/dataSetApi.js` — 数据集服务

基址：`API_BASE_URL`

### 4.1 测试集 CRUD

| 函数 | 方法 | 路径 | 参数 |
|---|---|---|---|
| `get_datasets` | GET | `get_testcase_info` | `params: { is_field }` |
| `get_count` | GET | `dataset/counts` | `params` |
| `get_dataset_files` | GET | `get_dataset_file_path` | `params` |
| `edit_datasets` | POST | `edit_testcase_ruler1` | body |
| `delete_datasets` | POST | `delete_testcase_ruler1` | body |
| `updateTestcaseInUse` | POST | `update_testcase_in_use` | body |
| `save_datasets` | POST | `register_testcase_ruler1` | body |
| `save_datasets2` | POST | `register_testcase_ruler2` | body |

### 4.2 文件管理

| 函数 | 方法 | 路径 | 备注 |
|---|---|---|---|
| `upload_file` | POST | `upload/file` | |
| `delete_folder` | POST | `delete/folder` | |
| `edit_file` | POST | `edit/file` | |
| `retrieve_files` | POST | `retrieve/files` | |
| `update_download` | POST | `dataset/update/download` | |
| `update_view` | POST | `dataset/update/view` | |
| `getDatasetFileData` | GET | `get_dataset_file_data` | |
| `getDatasetTree` | GET | `get_dataset_tree` | |
| `downloadExcell` | GET | `get_excel_file` | `responseType:'blob'` |
| `downloadDatasetZip` | GET | `download/dataset_zip` | `responseType:'blob'` |
| `downloadAisfReport` | GET | `download_aisf_release_result` | `responseType:'blob'` |

### 4.3 同传/翻译相关

| 函数 | 方法 | 路径 |
|---|---|---|
| `getIntepretationDatasets` | GET | `get_simultaneous_interpretation_cases` |
| `runInterpretation` | POST | `run_simultaneous_interpretation` |
| `uploadMOSFile` | POST | `upload_mos_file` |
| `addInterpretationFile` | POST | `add_interpretation_file` |
| `addInterpretationDirectory` | POST | `add_interpretation_directory` |
| `deleteInterpretationDirectory` | POST | `delete_interpretation_directory` |
| `uploadTestResult` | POST | `upload_test_result` |

---

## 五、`src/api/deployApi.js` — 模型部署

基址：`DEPLOY_API_BASE = http://7.216.57.45:10910/`

| 函数 | 方法 | URL |
|---|---|---|
| `submitDeploy` | POST | `${DEPLOY_BASE}create` |
| `queryDeployStatus` | POST | `${DEPLOY_BASE}deploystatus` |
| `queryAllStatus` | POST | `${DEPLOY_BASE}...` |
| `stopModel` | POST | `${DEPLOY_BASE}...` |
| `downloadModel` | POST | `${DEPLOY_BASE}...` |
| `modelConfig` | POST | `${DEPLOY_BASE}...` |

> `BASE = API_BASE_URL` 也在该文件中定义（部分函数可能走主 API）。

---

## 六、`src/api/userMgr.js` — 用户与登录

基址：`API_BASE_URL`

| 函数 | 方法 | 路径 | 说明 |
|---|---|---|---|
| `userLogin` | POST | `login` | 登录（密码 **RSA 加密**后传输） |
| `getUserInfo` | GET | `user` | 当前用户信息 |
| `userLogout` | POST | `logout` | 登出 |
| `getPublicKey` | GET | `get_pubkey` | 获取 RSA 公钥 |

**登录流程**（`src/components/login.vue:61-97`）：

```
1. GET  get_pubkey          → res.data = publicKey (PEM)
2. new JSEncrypt().setPublicKey(publicKey)
3. encryptedPassword = encrypt.encrypt(password)
4. POST login { username, password: encryptedPassword }
5. 若 response.data.status === true
     → localStorage.setItem('username', response.data.user.username)
     → emit('update:token_value', ...)
   否则 errorMessage = response.data.info
```

---

## 七、`src/api/userStatistics.js` — 用户运营统计

路径前缀统一 `/v1/user_statistics/`，返回格式 `{ code: 0, data: {...}, message: "success" }`。

| 函数 | 方法 | 路径 | 参数 |
|---|---|---|---|
| `getOverview` | GET | `user_statistics/overview` | `start_date`、`end_date` |
| `getTrend` | GET | `user_statistics/trend` | 同上 |
| `getTypeDistribution` | GET | `user_statistics/type_distribution` | 同上 |
| `getDepartmentStats` | GET | `user_statistics/department_stats` | 同上 |
| `getTopUsers` | GET | `user_statistics/top_users` | 同上 |
| `getDetails` | GET | `user_statistics/details` | 同上 |
| `getUserCandidates` | GET | `user_statistics/user_candidates` | 同上 |
| `getModelCandidates` | GET | `user_statistics/model_candidates` | — |
| `getTypeCandidates` | GET | `user_statistics/type_candidates` | — |

**`overview` 响应结构**（源码 JSDoc）：

```ts
{ code: 0, data: {
    total_operations: number,   // 总操作次数
    active_users: number,       // 活跃用户数
    daily_avg: number,          // 日均操作次数
    peak_day: { date: string, count: number } | null
}, message: string }
```

---

## 八、`src/api/dataFactory.js` — 数据工厂（VLA）

基址：`DATA_FACTORY_API = http://icap.rnd.huawei.com/v2/`

### 8.1 `DataFileManager`（默认导出）

| 项 | 说明 |
|---|---|
| `dataCacheFile` | `'device_data_cache.json'` |
| `updateInterval` | `30000` ms（30 秒） |
| `startAutoUpdate()` | 构造时立即执行 + `setInterval` 30s |
| `updateDataFile()` | 防重入（`isUpdating`），距上次 < 5s 跳过 |

> ⚠️ 源码中 `Promise.all([...])` 的 axios 调用**已被注释**，实际只做空转。
> `setInterval` 在 constructor 中启动且**从不清理**，属资源泄漏。

### 8.2 `useVlaDataApi()` 组合式 API

| 函数 | 方法 | 路径 | 参数 |
|---|---|---|---|
| `fetchSources` | GET | `sources` | — |
| `fetchDateRange` | GET | `date_range` | params |
| `fetchScenes` | GET | `scenes` | params |
| `fetchApps` | GET | `apps` | params |
| `fetchData` | GET | `data` | params |
| `fetchSceneStats` | GET | `scene_stats` | params |
| `fetchDistributions` | GET | `distributions` | params |

---

## 九、`src/services/` — 有状态服务类

### 9.1 `ModelService`（`services/modelService.js`）

基址：`API_BASE_URL`，配置：`DEFAULT_CONFIG`

| 静态方法 | 方法 | 路径 | 备注 |
|---|---|---|---|
| `registerModel` | POST | `register_model` | |
| `modifyModel` | POST | `modify_model` | |
| `getAllModelInfo` | GET | `get_model_info` | ⚠️ 第二参传 `payload` 而非 config（axios 会忽略） |
| `getOneModelInfo` | POST | `get_one_model_info` | body `{ model_id }` |
| `deleteModelInfo` | POST | `delete_model` | body **数组** `[modelId]` |
| `applyDeployModel` | POST | `apply_deploy_model` | |
| `getApplyDeployList` | GET | `get_apply_deploy_list` | |

**纯前端辅助方法（无网络请求）**

| 方法 | 说明 |
|---|---|
| `getParamName(paramId)` | 参数 ID → 中文名映射（`max_tokens`→最大Token数量、`temperature`→温度、`top_p`→Top P、`top_k`→Top K、`presence_penalty`→存在惩罚、`frequency_penalty`→频率惩罚） |
| `getModelIcon(modelId)` | 按模型名关键字匹配图标，默认 `pangu` |
| `getModelDesc(modelId)` | 返回占位描述 |
| `getModelColor(modelName)` | **全局固定颜色分配**（见下） |
| `resetModelColors()` | 清空颜色映射 |

**`getModelColor` 算法**（`modelService.js:108-133`）：

- 私有静态色池 `#colorPool`（**30 色**，顺序固定）：
  ```js
  ["#1F1F1F","#1C7FF8","#34A853","#EB3568","#FFBB00",
   "#9C27B0","#FF5722","#00BCD4","#795548","rgb(115, 108, 211)",
   "#3F51B5","#8BC34A","#FF9800","#009688","#673AB7",
   "#FFC107","#607D8B","#CDDC39","#D81B60","rgb(216, 152, 131)",
   "#5E35B1","#43A047","#FF7043","#26C6DA","#8D6E63",
   "#EC407A","#3949AB","#66BB6A","#FDD835","#7E57C2"]
  ```
- 私有静态 `#modelColorMap = new Map()`（**单例级缓存**，跨组件持久）
- 首次出现某模型时按 `map.size % 30` 分配颜色，之后固定不变。
- 保证「同一模型在所有图表中颜色一致」。

**图标映射表**（`modelService.js:77-93`，按小写包含匹配）：

| 关键字 | 资源 |
|---|---|
| `qwen`、`qwq` | `qwen.png` |
| `pangu` | `pangu.png`（**默认**） |
| `deepseek` | `deepseek.png` |
| `llama` | `llama.png` |
| `minicpm` | `openBmb.webp` |
| `mistral`、`ministral` | `mistral.jfif` |
| `gemini` | `gemini.svg` |
| `glm` | `z-icon.svg` |
| `minimax` | `minimax.png` |
| `openai` | `openai.jpg` |
| `gemma` | `gemma.png` |
| `doubao` | `doubao_avatar.png` |
| `longcat` | `longcat.png` |

### 9.2 `chatService`（`services/chatService.js`）

| 静态方法 | 说明 |
|---|---|
| `updateLoadingStatusByCallBack(updateMessage, timeInterval = 100, base = 0)` | 加载动画状态回调（每 100ms） |
| `sendMsgStream(...)` | **流式**对话（约 130 行） |
| `sendCompanyApiMessage(...)` | 公司 API 消息发送 |
| `sendMsgNotStream(payload, ...)` | 非流式，POST `${API_BASE_URL}chat` |
| `upLoadFile(payload, ...)` | POST `${API_BASE_URL}chat/upload_file` |
| `isEndpointReachable(...)` | 端点可达性探测 |

配置：`AXIOS_POST_CONFIG`（20s 超时）。

> **流式实现细节**：源码使用 `updateLoadingStatusByCallBack` 配合回调节流，
> 并未使用 `EventSource`/`WebSocket`（全工程仅 `DeviceDetailVisualization.vue:222`
> 有一处 `new WebSocket(DATA_FACTORY_LOG_WS + 'phone_app_run_log')`）。

### 9.3 `AgentChatService`（`services/AgentChatService.js`）

| 静态方法 | 行号 |
|---|---|
| `updateLoadingStatusByCallBack(...)` | 58 |
| `sendMsgStream(...)` | 69 |
| `sendDeepResearchMessage(...)` | 203 |
| `startDeepResearchMessage(...)` | 296 |

---

## 十、dataPipeline 模块 API

### 10.1 `src/dataPipeline/api.ts`

- **基址**：`const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')`
- **请求器**：原生 `fetch`；非 `FormData` 时自动设 `Content-Type: application/json`
- **错误处理**：`ApiError extends Error`，携带 `status`；
  解析 FastAPI 风格 `detail`（字符串或 `[{msg}]` 数组，数组用「；」连接）

#### 任务生成 Task Generation

| 方法 | HTTP | 路径 |
|---|---|---|
| `taskGenerationKnowledgeBases()` | GET | `/api/task-generation/knowledge-bases` |
| `taskGenerationTree()` | GET | `/api/task-generation/tree` |
| `saveTaskGenerationTree(scenes, baseVersion)` | PUT | `/api/task-generation/tree` |
| `replaceTaskGenerationKnowledgeBase(kind, file, baseVersion?)` | PUT | `/api/task-generation/knowledge-bases/{kind}`（FormData） |
| `createTaskGeneration(selections, generateN, version)` | POST | `/api/task-generation/jobs` |
| `createAugmentation(file, generateN, autoStart=true)` | POST | `/api/task-generation/augmentation-jobs`（FormData） |
| `augmentationPreview(jobId, includeTree=true)` | GET | `/api/task-generation/jobs/{id}/augmentation-preview?include_tree=` |
| `startAugmentation(jobId)` | POST | `/api/task-generation/jobs/{id}/start-augmentation` |
| `taskGenerationJobs()` | GET | `/api/task-generation/jobs` |
| `taskGenerationJob(jobId)` | GET | `/api/task-generation/jobs/{id}` |
| `taskGenerationResults(jobId)` | GET | `/api/task-generation/jobs/{id}/results` |
| `patchTaskGenerationResult(jobId, resultId, {task?, deleted?})` | PATCH | `/api/task-generation/jobs/{id}/results/{rid}` |
| `taskGenerationExport(jobId)` | POST | `/api/task-generation/jobs/{id}/export` |

#### 轨迹采集 Trajectories

| 方法 | HTTP | 路径 |
|---|---|---|
| `tasks()` | GET | `/api/tasks` |
| `trajectories(taskId)` | GET | `/api/tasks/{id}/trajectories` |
| `trajectory(taskId, trajectoryId)` | GET | `/api/tasks/{tid}/trajectories/{trid}` |
| `updateBBox(taskId, trajectoryId, step, excelRow, bbox)` | PATCH | `/api/tasks/{tid}/trajectories/{trid}/steps/{step}/bbox` |
| `updateActionBBox(..., action?)` | PATCH | 同上（body 多带 `action`） |
| `createBuild(taskIds)` | POST | `/api/tree-builds` |
| `build(jobId)` | GET | `/api/tree-builds/{id}` |
| `runs()` | GET | `/api/tree-runs` |
| `tree(runId, taskId)` | GET | `/api/tree-runs/{rid}/tasks/{tid}/tree` |

#### 质检 Quality

| 方法 | HTTP | 路径 |
|---|---|---|
| `createQuality(runId, taskIds)` | POST | `/api/quality-jobs` |
| `qualityJob(jobId)` | GET | `/api/quality-jobs/{id}` |
| `qualityJobs()` | GET | `/api/quality-jobs` |
| `runQuality(runId)` | GET | `/api/tree-runs/{rid}/quality` |
| `taskQuality(runId, taskId)` | GET | `/api/tree-runs/{rid}/tasks/{tid}/quality` |

#### 纠偏 Correction

| 方法 | HTTP | 路径 |
|---|---|---|
| `correctionBatches()` | GET | `/api/correction/batches` |
| `correctionRecommendation(treeRunId?)` | GET | `/api/correction/recommendation?tree_run_id=` |
| `correctionSessions()` | GET | `/api/correction/sessions` |
| `createCorrectionSession(treeRunId)` | POST | `/api/correction/sessions` |
| `correctionSession(sessionId)` | GET | `/api/correction/sessions/{sid}` |
| `correctionSessionCot(sessionId)` | GET | `/api/correction/sessions/{sid}/cot` |
| `createCorrectionCotJob(sessionId, groupIds?, rowIds?, options?)` | POST | `/api/correction/cot-jobs` |
| `correctionCotJob(jobId)` | GET | `/api/correction/cot-jobs/{id}` |
| `correctionCotJobs()` | GET | `/api/correction/cot-jobs` |
| `correctionGroups(sessionId)` | GET | `/api/correction/sessions/{sid}/tasks` |
| `correctionGroup(sessionId, groupId)` | GET | `/api/correction/sessions/{sid}/tasks/{gid}` |
| `patchCorrectionRow(sessionId, excelRow, patch)` | PATCH | `/api/correction/sessions/{sid}/rows/{row}` |
| `patchCorrectionExport(sessionId, groupId, exportState)` | PATCH | `/api/correction/sessions/{sid}/tasks/{gid}/export` |
| `correctionExport(sessionId)` | POST | `/api/correction/sessions/{sid}/export` |
| `correctionDatasetExport(sessionId)` | POST | `/api/correction/sessions/{sid}/dataset-export` |

`patchCorrectionRow` 的 `patch` 允许字段：`sop`、`actions`、`actions_box`、`summary`、`thought`、`deleted`。

`createCorrectionCotJob` 的 `options`：`{ generateBBox?: boolean, forceOverwrite?: boolean }`。

#### 数据发布 Dataset Release

| 方法 | HTTP | 路径 |
|---|---|---|
| `datasetReleaseCandidates()` | GET | `/api/dataset-releases/candidates` |
| `datasetReleases()` | GET | `/api/dataset-releases` |
| `createDatasetRelease(name, sessionIds)` | POST | `/api/dataset-releases` |
| `datasetRelease(releaseId)` | GET | `/api/dataset-releases/{id}` |
| `datasetUploadCapabilities()` | GET | `/api/dataset-upload-capabilities` |
| `uploadDatasetRelease(releaseId, target?)` | POST | `/api/dataset-releases/{id}/upload` |
| `datasetUploadJob(jobId)` | GET | `/api/dataset-upload-jobs/{id}` |

#### URL 构造函数（返回字符串，用于 `<img>` / `<a download>`）

| 函数 | 返回 |
|---|---|
| `imageUrl(relativePath)` | `${API_BASE}/api/assets/{path}` |
| `correctionAssetUrl(sessionId, relativePath)` | `${API_BASE}/api/correction/sessions/{sid}/assets/{path}` |
| `correctionDownloadUrl(sessionId, filename)` | `${API_BASE}/api/correction/sessions/{sid}/exports/{file}` |
| `taskGenerationDownloadUrl(jobId, filename)` | `${API_BASE}/api/task-generation/jobs/{id}/exports/{file}` |
| `sceneTreeDownloadUrl()` | `${API_BASE}/api/task-generation/tree/export` |
| `datasetReleaseExcelUrl(releaseId, index)` | `${API_BASE}/api/dataset-releases/{id}/excels/{index}` |

> 所有路径段均经 `encodeURIComponent`，并统一把 `\` 转 `/`、去除前导 `/`。

### 10.2 `src/dataPipeline/phoneFactoryApi.ts`

工厂函数 `createPhoneFactoryApi(base, runMode)`，两个实例：

| 实例 | base | runMode |
|---|---|---|
| `phoneFactoryApi` | `/api/phone-factory` | `'generate'` |
| `modelIterEvalApi` | `/api/model-iter` | `'modeliter'` |

| 方法 | HTTP | 路径 | 说明 |
|---|---|---|---|
| `state()` | GET | `/state` | 一次性拉全部状态 |
| `addPhone(phoneId)` | POST | `/phones` | 追加 phones.json，不可重复 |
| `addApp(app)` | POST | `/apps` | 追加 apps.json |
| `addPhoneApp(phoneId, app)` | POST | `/phone-apps` | 建立关联 |
| `removePhoneApp(phoneId, app)` | DELETE | `/phone-apps` | 删除单对关联 |
| `saveVla(value)` | POST | `/vla` | 保存 VLA 接口 |
| `addTask(description, filename, contentBase64)` | POST | `/tasks` | 文件落盘至 `$HOME/Desktop/uuupppfffiiillleee` |
| `startTask(filename)` | POST | `/tasks/start` | 未运行 → 运行中 |
| `config()` | GET | `/config` | 采样/经验库配置 |
| `saveConfig(config)` | POST | `/config` | 保存配置 |
| `removeTask(filename)` | DELETE | `/tasks` | 从 tasks.json 移除 |
| `remoteAddPhone(phoneId)` | POST | `/remote/add-phone` | 通知 server |
| `remoteDelPhone(phoneId)` | POST | `/remote/del-phone` | 终止进程 + 删目录 |
| `remoteStartRun(filename, phoneId, app, vla, samplingEnabled?, temperature?, topP?, useExperienceLib?)` | POST | `/remote/start-run` | 下发任务与配置 |
| `phoneStatuses(phones)` | POST | `/remote/status` | **建议 3s 轮询** |
| `adbDevices()` | POST | `/remote/adb-devices` | **建议 10s 轮询** |
| `monitorPhone(phoneId)` | POST | `/remote/monitor` | 截图 base64 + 日志，**建议 2~3s** |
| `reportList()` | GET | `/reports` | 轮次报告列表 |
| `reportDownload(name, folder?)` | GET | `/report-download?name=&folder=` | 返回 `Blob` |

**错误处理**：`fetch` 后解析 JSON，若 `!response.ok` 或 `payload.error` 存在则抛 `Error`。

**类型**：`FactoryRunMode`、`PhoneAppRow`、`TaskRow`、`FactoryState`、`AdbDeviceInfo`、
`FactoryConfig`、`ReportFile`、`ReportFolder`、`ReportList`。

### 10.3 `src/dataPipeline/collectionBatchesApi.ts`

- `API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')`
- `BASE = ${API_BASE}/api/task-generation`
- 使用 `checkedFetch`（`cache: 'no-store'`）

| 方法/导出 | HTTP | 路径 |
|---|---|---|
| `collectionBatchesApi.list(jobId?)` | GET | `/collection-batches?job_id=` |
| `collectionBatchesApi.detail(batchId)` | GET | `/collection-batches/{id}` |
| `collectionBatchesApi.submit(jobId)` | POST | `/jobs/{id}/collection-batch` |
| `collectionBatchesApi.workbook(batchId)` | GET | `/collection-batches/{id}/workbook`（Blob） |
| `collectionBatchDownloadUrl(batchId)` | — | `${BASE}/collection-batches/{id}/workbook` |

**类型**：`CollectionBatchTask`、`CollectionBatchSnapshot`（`schema_version: 1`）、
`CollectionBatchSummary`、`CollectionBatchDetail`。

---

## 十一、接口调用统计

| 模块 | 端点数（约） |
|---|---|
| `dataService.js` | 28 |
| `runService.js` | 36 |
| `dataSetApi.js` | 26 |
| `deployApi.js` | 6 |
| `userMgr.js` | 4 |
| `userStatistics.js` | 9 |
| `dataFactory.js` | 7 |
| `modelService.js` | 7 |
| `chatService.js` | 4 |
| `dataPipeline/api.ts` | 48 |
| `phoneFactoryApi.ts` | 20 × 2 实例 |
| `collectionBatchesApi.ts` | 4 |
| **合计** | **约 200** |

---

## 十二、接口层已知问题

| # | 位置 | 问题 |
|---|---|---|
| 1 | `runService.js:25` | `API_BASE_URL + '/v1/run_mt'` 导致 `/v1/v1/` 双前缀 |
| 2 | `dataService.js:32-43` | 4 个函数共用 `get_current_multi_full_res` |
| 3 | `runService.js:60,116` | `getFilePath` 与 `getAgentFile` 同端点 |
| 4 | `dataService.js:8,12` | `startRun` 与 `startRunTest` 同端点同方法 |
| 5 | `modelService.js:36` | `axios.get(url, payload, DEFAULT_CONFIG)` 参数位置错误 |
| 6 | `dataFactory.js:18` | `setInterval` 在 constructor 启动且**从不清理** |
| 7 | `dataFactory.js:39-45` | 实际请求逻辑被注释，管理器空转 |
| 8 | `Constants.js:5` | `BASE_HTTPS = 'https://icap.rnd.huawei.com'` 与 HTTP 环境不同域，跨域需后端 CORS |
| 9 | dataPipeline | `VITE_API_BASE_URL` 未设时 `/api` 前缀与 vite 代理 rewrite 冲突（见 01 文档 3.2） |
| 10 | 全局 | **无统一 axios 实例**、无请求/响应拦截器、无 `Authorization` 头注入 |

> 复现时若要"完全一致"，保持原样；若要"可运行"，见 [08 文档](./08-复现指南与已知问题.md) 修复建议。

---

**上一篇：** [03 · 状态管理](./03-状态管理.md) ｜
**下一篇：** [05 · 业务模块说明](./05-业务模块说明.md)
