# 前后端接口映射表

> 本文件维护前端所有 API 调用与后端代码仓位置的对应关系。
> 前端代码仓：`D:\code_ailab\icap\FrontEnd\frontEnd`
> 后端代码仓：`D:\code_ailab\CCNRulerEvalScope\CCNModelEvalService\backend`

---

## 架构概览

请求链路：`前端 -> adapter.py(:8081) -> server.py(:7300) / run_test_server.py(:7301) / 其他子服务`

```
前端 (Constants.js)
  │
  ├── API_BASE_URL ──────────► adapter.py (:8081) ──► server.py (:7300) [Flask主服务]
  │                          │                      ├── run_test_server.py (:7301) [测评任务调度]
  │                          │                      ├── huggingface_download_adapter.py [HF下载]
  │                          │                      └── ... (自身处理)
  │                          │
  │                          ├── AGENT_SERVER_URL ──► 8510 [Agent服务: PPT助手/DeepResearch/机器猫]
  │                          ├── AI_SCHOOL_SERVER_URL ──► 12600 [AI School推理中转]
  │                          ├── PHONE_MONITOR_MGR_URL ──► 15000 [手机监控]
  │                          ├── VLA_DATA_BACKEND_URL ──► 12321 [VLA数据后端]
  │                          └── DF_BACKEND_URL ──► 10.189.206.203:8765 [数据治理Pipeline/FastAPI]
  │
  ├── AI_SCHOOL_URL ─────────► 直接到45服务器:12600 (不经过adapter)
  ├── AI_SCHOOL_INDIVIDUAL_*  ► 直接到黄/绿区服务器 (不经过adapter)
  ├── DATA_FACTORY_API ──────► 同API_BASE_URL (v2路径走adapter转到15000)
  └── 其他硬编码URL ─────────► 直接指向对应服务
```

---

## 如何填写后端代码仓位置

> **格式说明**：`后端文件路径:行号`（相对于 `D:\code_ailab\CCNRulerEvalScope\CCNModelEvalService\backend\`）
>
> - 如果该接口在后端**已有实现**，请填写对应的文件路径和行号
> - 如果该接口在后端**尚无对应实现**，请标注 `TODO`，并写上预计在哪个文件实现
> - 如果该接口**不经过本后端代码仓**（如转发到外部服务），请注明转发目标

---

## 1. 模型管理

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `register_model` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |
| `modify_model` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |
| `get_model_info` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |
| `get_one_model_info` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |
| `delete_model` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |
| `apply_deploy_model` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |
| `get_apply_deploy_list` | [src/services/modelService.js](src/services/modelService.js) | `API_BASE_URL` | |

---

## 2. 用户认证

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `login` | [src/api/userMgr.js](src/api/userMgr.js) | `API_BASE_URL` | |
| `user` | [src/api/userMgr.js](src/api/userMgr.js) | `API_BASE_URL` | |
| `logout` | [src/api/userMgr.js](src/api/userMgr.js) | `API_BASE_URL` | |
| `get_pubkey` | [src/api/userMgr.js](src/api/userMgr.js) | `API_BASE_URL` | |

---

## 3. 对话/Chat

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `chat` | [src/services/chatService.js](src/services/chatService.js) | `API_BASE_URL` | |
| `chat/upload_file` | [src/services/chatService.js](src/services/chatService.js) | `API_BASE_URL` | |
| `stream_chat` (POST) | [src/services/chatService.js](src/services/chatService.js) | 动态endpoint | |
| Agent流式聊天 | [src/services/agentChatService.js](src/services/agentChatService.js) | 动态endpoint | |

---

## 4. 测评任务 (Ruler)

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `run_testcase_ruler1` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `run_testcase_ruler2` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `run_aisf_release` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `run_testcase_dev` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `run_vlm_ruler1` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `/v1/run_mt` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_run_test_progress_list` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `check_run_test_progress/{task_id}` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `delete_test_progress` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `pause_test_task` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `resume_test_task` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_result` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `download/file` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_file_path` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `logs` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `update_top_chart` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `update_score` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `async_score` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_one_test_task` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_min_test_chart` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `delete_single_result` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_eld_statistics` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `download_agent_file` | [src/api/runService.js](src/api/runService.js) | `API_AGENT_URL` | |

---

## 5. 报告管理

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `generate_report` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `download/report` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `query_report_status` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_latest_report` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `delete_report_task` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_report_tasks_by_name` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_all_report_tasks` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `direct_publish_report` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `publish_report_from_task` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `get_all_published_tasks` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `preview/report` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |
| `delete_published_task` | [src/api/runService.js](src/api/runService.js) | `API_BASE_URL` | |

---

## 6. 数据集管理

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `get_testcase_info` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `dataset/counts` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `get_dataset_file_path` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `edit_testcase_ruler1` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `delete_testcase_ruler1` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `register_testcase_ruler1` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `register_testcase_ruler2` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `upload/file` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `delete/folder` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `edit/file` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `retrieve/files` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `dataset/update/download` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `dataset/update/view` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `get_excel_file` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `download_aisf_release_result` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |

---

## 7. 数据服务（特殊模型/评估报告/反馈/日志）

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `get_current_full_res` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_current_multi_full_res` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `register_special_model` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `delete_special_model_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `modify_special_model_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_special_model_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_eval_report` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `modify_eval_report` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_eval_model_list` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `modify_eval_model_list` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_models_file_data` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `download_models_file` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `upload_models_file` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_feedback_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `modify_feedback_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `delete_feedback_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `register_feedback_info` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `add_log_data` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_log_data` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `modify_log_data` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `add_model_progress` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_model_progress` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `modify_model_progress` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `get_evaluation_result` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `write_evaluation_result` | [src/api/dataService.js](src/api/dataService.js) | `API_BASE_URL` | |
| `API_MENSHEN_URL` (POST) | [src/api/dataService.js](src/api/dataService.js) | `API_MENSHEN_URL` | 不经过本后端，直接调用华为门神API |

---

## 8. 同声传译/MOS

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `get_simultaneous_interpretation_cases` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `run_simultaneous_interpretation` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `upload_mos_file` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `add_interpretation_file` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `add_interpretation_directory` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `delete_interpretation_directory` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |
| `upload_test_result` | [src/api/dataSetApi.js](src/api/dataSetApi.js) | `API_BASE_URL` | |

---

## 9. 用户统计 & API Key

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `user_statistics/overview` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/trend` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/type_distribution` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/department_stats` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/top_users` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/details` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/user_candidates` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/model_candidates` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/type_candidates` | [src/api/userStatistics.js](src/api/userStatistics.js) | `API_BASE_URL` | |
| `user_statistics/get_api_key` | [src/components/userStatistics/apiKeyPage.vue](src/components/userStatistics/apiKeyPage.vue) | `API_BASE_URL` | |
| `user_statistics/apply_api_key` | [src/components/userStatistics/apiKeyPage.vue](src/components/userStatistics/apiKeyPage.vue) | `API_BASE_URL` | |

---

## 10. 数据中心 (Data Factory / V2 API)

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `sources` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `date_range` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `scenes` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `apps` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `data` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `scene_stats` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `distributions` (v2) | [src/api/dataFactory.js](src/api/dataFactory.js) | `DATA_FACTORY_API` | |
| `stats` (v2) | [src/components/dataCenter/DeviceDetailVisualization.vue](src/components/dataCenter/DeviceDetailVisualization.vue) | `DATA_FACTORY_API` | |
| `info/{deviceId}` (v2) | [src/components/dataCenter/DeviceDetailVisualization.vue](src/components/dataCenter/DeviceDetailVisualization.vue) | `DATA_FACTORY_API` | |
| `task/{deviceId}` (v2) | [src/components/dataCenter/DeviceDetailVisualization.vue](src/components/dataCenter/DeviceDetailVisualization.vue) | `DATA_FACTORY_API` | |
| `refresh-devices` (v2) | [src/components/dataCenter/HomeVisualization.vue](src/components/dataCenter/HomeVisualization.vue) | `DATA_FACTORY_API` | |

---

## 11. HuggingFace 下载

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `hg_download/files_info` | [src/components/dataCenter/huggingfaceDownload.vue](src/components/dataCenter/huggingfaceDownload.vue) | `API_BASE_URL` | |
| `hg_download/download_files` | [src/components/dataCenter/huggingfaceDownload.vue](src/components/dataCenter/huggingfaceDownload.vue) | `API_BASE_URL` | |
| `hg_download/download_status` | [src/components/dataCenter/huggingfaceDownload.vue](src/components/dataCenter/huggingfaceDownload.vue) | `API_BASE_URL` | |
| `hg_download/upload_files` | [src/components/dataCenter/huggingfaceDownload.vue](src/components/dataCenter/huggingfaceDownload.vue) | `API_BASE_URL` | |

---

## 12. AI School

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `execute_block` | [src/components/aiSchool/Desktop.vue](src/components/aiSchool/Desktop.vue) | `AI_SCHOOL_URL` | |
| `terminate/{sessionId}` | [src/components/aiSchool/Desktop.vue](src/components/aiSchool/Desktop.vue) | `AI_SCHOOL_URL` | |
| `plot/{sessionId}` | [src/components/aiSchool/Desktop.vue](src/components/aiSchool/Desktop.vue) | `AI_SCHOOL_URL` | |
| `judge_school_busy/{sessionId}` | [src/components/aiSchool/Desktop.vue](src/components/aiSchool/Desktop.vue) | `AI_SCHOOL_URL` | |
| `stream_train_log/{sessionId}` | [src/components/aiSchool/Desktop.vue](src/components/aiSchool/Desktop.vue) | `AI_SCHOOL_URL` | |
| `execute_block` | [src/components/aiSchool/ModelArchitecture.vue](src/components/aiSchool/ModelArchitecture.vue) | `AI_SCHOOL_INDIVIDUAL_*` | 直接访问黄/绿区服务器，不经过本后端 |
| `execute_block` | [src/components/aiSchool/Inference.vue](src/components/aiSchool/Inference.vue) | `AI_SCHOOL_URL` | |

---

## 13. paperAgent（arXiv论文助手）

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `paper_agent/status` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_BASE_URL` | `adapter.py:1061-1063` → `paper_agent_server.py:345-348` |
| `paper_agent/fetch_and_analyze` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_BASE_URL` | `adapter.py:1066-1068` → `paper_agent_server.py:351-369` |
| `paper_agent/quick_demo` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_BASE_URL` | `adapter.py:1071-1073` → `paper_agent_server.py:372-391` |
| `paper_agent/results` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1089-1091` → `paper_agent_server.py:666-690` |
| `paper_agent/results/<filename>` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1094-1096` → `paper_agent_server.py:693-716` |
| `paper_agent/latest_excel` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1099-1101` → `paper_agent_server.py:719-743` |
| `paper_agent/latest_demo` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1104-1106` → `paper_agent_server.py:746-775` |
| `paper_agent/health` | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1109-1111` → `paper_agent_server.py:778-784` |
| `paper_agent/search` (POST) | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1115-1117` → `paper_agent_server.py:789-915` 定制化搜索 |
| `paper_agent/search_csv` (GET) | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1120-1122` → `paper_agent_server.py:918-935` 获取用户最新搜索结果 |
| `paper_agent/search_results/<filename>` (GET) | [src/components/agentCenter/paperAgent.vue](src/components/agentCenter/paperAgent.vue) | `API_AGENT_URL` | `adapter.py:1125-1127` → `paper_agent_server.py:938-953` 下载搜索结果文件 |

> **说明**：paperAgent 服务（`paper_agent_server.py`）运行在独立端口 7303，在 `adapter.py` 中以 `PAPER_AGENT_SERVER_URL` 注册转发。原始代码基于 `D:\code_ailab\CCNDataGovernanceTool\publicTool\paperAgent\`。

---

## 14. LM Arena 排行榜

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `lmarena/leaderboard` | [src/components/rankingScore/rankingScore.vue](src/components/rankingScore/rankingScore.vue) | `API_BASE_URL` | 已实现：`server.py:3411`（路由），`adapter.py:954`（转发） |
| `lmarena/leaderboard` | [src/components/rankingScore/LMArenaDetails.vue](src/components/rankingScore/LMArenaDetails.vue) | `API_BASE_URL` | 同上 |

---

## 15. 数据治理 Pipeline（Agentic Data Flywheel）

前端模块位于 [src/dataPipeline/](src/dataPipeline/)，与「首页」「数据&评测」平级。
该模块的接口**已统一**走 `Constants.js` 的 `API_BASE_URL`，与主工程其余模块一致。

### 15.1 前端 API 客户端与 URL 拼接规则

| 客户端文件 | 拼接方式 | 后端前缀 |
|-----------|---------|---------|
| [src/dataPipeline/api.ts](src/dataPipeline/api.ts) | `${API_BASE_URL(去掉尾部斜杠)}${'/api'}${path}` | `/v1/api/...` |
| [src/dataPipeline/collectionBatchesApi.ts](src/dataPipeline/collectionBatchesApi.ts) | `${API_BASE_URL(去掉尾部斜杠)}/api/task-generation` | `/v1/api/task-generation/...` |
| [src/dataPipeline/phoneFactoryApi.ts](src/dataPipeline/phoneFactoryApi.ts) | `${API_BASE_URL(去掉尾部斜杠)}${base}${path}` | `/api/phone-factory`、`/api/model-iter` ⚠️ 后端未适配 |

拼接结果示例：

```
API_BASE_URL              = http://7.194.131.207:30101/v1/   (dev, 来自 Constants.js)
API_BASE (去尾斜杠)        = http://7.194.131.207:30101/v1
+ API_PREFIX '/api'
+ path '/task-generation/jobs'
────────────────────────────────────────────────────────────
最终请求                    = http://7.194.131.207:30101/v1/api/task-generation/jobs
                                                           │
                            adapter.py 路由 /v1/api/task-generation/jobs
                                                           │
                            DF_BACKEND_URL + '/api/task-generation/jobs'
                                                           ▼
                            http://10.189.206.203:8765/api/task-generation/jobs
```

> **注意**：`dataPipeline` 使用原生 `fetch`（其余模块多用 `axios`），
> 但 URL 常量来源已统一为 `Constants.js` 的 `API_BASE_URL`。

### 15.2 任务生成 (Task Generation)

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `task-generation/knowledge-bases` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1349-1351` → `DF_BACKEND_URL` |
| `task-generation/knowledge-bases/<kind>` | PUT | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1354-1356` → `DF_BACKEND_URL` |
| `task-generation/tree` | GET / PUT | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1359-1361` → `DF_BACKEND_URL` |
| `task-generation/tree/export` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1364-1366` → `DF_BACKEND_URL` |
| `task-generation/jobs` | GET / POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1299-1301` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1304-1306` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/results` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1334-1336` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/results/<result_id>` | PATCH | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1339-1341` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/export` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1324-1326` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/exports/<filename>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1329-1331` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/collection-input` | GET | — | `API_BASE_URL` | `adapter.py:1319-1321` → `DF_BACKEND_URL` |
| `task-generation/augmentation-jobs` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1279-1281` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/augmentation-preview` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1309-1311` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/start-augmentation` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1344-1346` → `DF_BACKEND_URL` |

### 15.3 采集批次 (Collection Batches)

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `task-generation/collection-batches` | GET | [collectionBatchesApi.ts](src/dataPipeline/collectionBatchesApi.ts) | `API_BASE_URL` | `adapter.py:1284-1286` → `DF_BACKEND_URL` |
| `task-generation/collection-batches/<batch_id>` | GET | [collectionBatchesApi.ts](src/dataPipeline/collectionBatchesApi.ts) | `API_BASE_URL` | `adapter.py:1289-1291` → `DF_BACKEND_URL` |
| `task-generation/collection-batches/<batch_id>/workbook` | GET | [collectionBatchesApi.ts](src/dataPipeline/collectionBatchesApi.ts) | `API_BASE_URL` | `adapter.py:1294-1296` → `DF_BACKEND_URL` |
| `task-generation/jobs/<job_id>/collection-batch` | POST | [collectionBatchesApi.ts](src/dataPipeline/collectionBatchesApi.ts) | `API_BASE_URL` | `adapter.py:1314-1316` → `DF_BACKEND_URL` |

### 15.4 轨迹 / 任务树 (Trajectories & Tree)

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `tasks` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1369-1371` → `DF_BACKEND_URL` |
| `tasks/<task_id>/trajectories` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1374-1376` → `DF_BACKEND_URL` |
| `tasks/<task_id>/trajectories/<trajectory_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1379-1381` → `DF_BACKEND_URL` |
| `tasks/<task_id>/trajectories/<trajectory_id>/steps/<step>/bbox` | PATCH | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1384-1386` → `DF_BACKEND_URL` |
| `tree-builds` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1389-1391` → `DF_BACKEND_URL` |
| `tree-builds/<job_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1394-1396` → `DF_BACKEND_URL` |
| `tree-runs` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1399-1401` → `DF_BACKEND_URL` |
| `tree-runs/<run_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1404-1406` → `DF_BACKEND_URL` |
| `tree-runs/<run_id>/tasks/<task_id>/tree` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1419-1421` → `DF_BACKEND_URL` |

### 15.5 质检 (Quality)

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `quality-jobs` | GET / POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1269-1271` → `DF_BACKEND_URL` |
| `quality-jobs/<job_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1274-1276` → `DF_BACKEND_URL` |
| `tree-runs/<run_id>/quality` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1409-1411` → `DF_BACKEND_URL` |
| `tree-runs/<run_id>/tasks/<task_id>/quality` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1414-1416` → `DF_BACKEND_URL` |

### 15.6 纠偏 (Correction)

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `correction/batches` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1154-1156` → `DF_BACKEND_URL` |
| `correction/recommendation` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1169-1171` → `DF_BACKEND_URL` |
| `correction/sessions` | GET / POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1174-1176` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1179-1181` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/cot` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1189-1191` → `DF_BACKEND_URL` |
| `correction/cot-jobs` | GET / POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1159-1161` → `DF_BACKEND_URL` |
| `correction/cot-jobs/<job_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1164-1166` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/tasks` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1214-1216` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/tasks/<group_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1219-1221` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/tasks/<group_id>/export` | PATCH | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1224-1226` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/rows/<excel_row>` | PATCH | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1209-1211` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/export` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1199-1201` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/dataset-export` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1194-1196` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/exports/<filename>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1204-1206` → `DF_BACKEND_URL` |
| `correction/sessions/<session_id>/assets/<image_path>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1184-1186` → `DF_BACKEND_URL` |

### 15.7 数据发布 (Dataset Release)

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `dataset-releases/candidates` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1234-1236` → `DF_BACKEND_URL` |
| `dataset-releases` | GET / POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1229-1231` → `DF_BACKEND_URL` |
| `dataset-releases/<release_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1239-1241` → `DF_BACKEND_URL` |
| `dataset-releases/<release_id>/upload` | POST | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1249-1251` → `DF_BACKEND_URL` |
| `dataset-upload-jobs/<job_id>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1259-1261` → `DF_BACKEND_URL` |
| `dataset-upload-capabilities` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1254-1256` → `DF_BACKEND_URL` |
| `dataset-releases/<release_id>/excels/<index>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1244-1246` → `DF_BACKEND_URL` |

### 15.8 资源与健康检查

| 前端路由 | 方法 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|------|---------|------------|--------------|
| `assets/<relative_path>` | GET | [api.ts](src/dataPipeline/api.ts) | `API_BASE_URL` | `adapter.py:1149-1151` → `DF_BACKEND_URL` |
| `health` | GET | — | `API_BASE_URL` | `adapter.py:1264-1266` → `DF_BACKEND_URL` |

### 15.9 ⚠️ 未适配接口（phone-factory / model-iter）

| 前端路由 | 前端文件 | 使用URL常量 | 后端文件:行号 |
|---------|---------|------------|--------------|
| `api/phone-factory/*` | [src/dataPipeline/phoneFactoryApi.ts](src/dataPipeline/phoneFactoryApi.ts) | `API_BASE_URL` | **TODO**：`10.189.206.203:8765` 未实现（404） |
| `api/model-iter/*` | [src/dataPipeline/phoneFactoryApi.ts](src/dataPipeline/phoneFactoryApi.ts) | `API_BASE_URL` | **TODO**：`10.189.206.203:8765` 未实现（404） |

> **说明**：源工程中这两组接口由**开发期 Vite 中间件插件**（`frontend/vite-plugin-phone-factory.ts`）提供，
> 并非真实后端服务；生产后端 `DF_BACKEND_URL` 上不存在对应路由（已验证返回 404）。
> 如需在部署环境使用手机工厂数据采集 / 模型迭代评测页面，需要先在后端实现这两组接口，
> 再在 `adapter.py` 中补充 `/v1/api/phone-factory/...`、`/v1/api/model-iter/...` 转发路由。

### 15.10 后端服务说明

| 后端服务 | 地址/端口 | 说明 |
|---------|----------|------|
| 数据治理 Pipeline 后端 | `10.189.206.203:8765` | 独立部署的 FastAPI 应用「Agentic Data Flywheel」v1.0.0，全部路由自带 `/api` 前缀，共 55 个路径 |

> **adapter.py 转发实现**：见 `adapter.py` 第 1144-1422 行（`# ================== 数据治理 Pipeline ...` 段），
> 统一以 `/v1/api/...` 对外暴露，通过常量 `DF_BACKEND_URL`（`adapter.py:32`）转发。
> 其中 `/api/assets/<relative_path>` 与 `/api/correction/sessions/<session_id>/assets/<image_path>`
> 两个路径使用 Flask 的 `<path:...>` 通配转换器以兼容 FastAPI 的 `{param:path}`。

---

## 16. 硬编码URL（不经过 Constants.js）

| 目标URL | 前端文件 | 说明 | 后端代码仓位置 |
|---------|---------|------|--------------|
| `http://100.100.50.160:5173/` | [src/components/agentCenter/promptOptimizer.vue](src/components/agentCenter/promptOptimizer.vue) | prompt优化器，不经过本后端 | 不经过本后端 |
| `http://100.100.136.146:10129/` | [src/components/agentCenter/promptOptimizer.vue](src/components/agentCenter/promptOptimizer.vue) | prompt优化器备用 | 不经过本后端 |
| `http://7.194.131.207:30101/v1/delete/folder` | [src/components/dataCenter/datasetAnnotation.vue](src/components/dataCenter/datasetAnnotation.vue) | 硬编码的删除文件夹 | 同 `API_BASE_URL` path |
| `http://10.189.206.203:8000/` | [src/components/dataCenter/collectionVisualization.vue](src/components/dataCenter/collectionVisualization.vue) | iframe内嵌 | 不经过本后端 |
| `/data/deployableModel.xlsx` | [src/components/modelSquare/modelSquare.vue](src/components/modelSquare/modelSquare.vue) | 静态文件 | 前端静态资源 |
| `/data/EvaluationReport.docx` | [src/components/modelEvaluation/onlineAssessment.vue](src/components/modelEvaluation/onlineAssessment.vue) | 静态文件 | 前端静态资源 |
| `http://7.194.131.207:12901/` | [src/components/agentCenter/owl.vue](src/components/agentCenter/owl.vue) | iframe内嵌Owl服务 | 不经过本后端 |
| `http://7.194.131.207:10901/` | [src/components/agentCenter/dify.vue](src/components/agentCenter/dify.vue) | iframe内嵌Dify服务 | 不经过本后端 |
| `http://7.194.131.207:11901/` | [src/components/agentCenter/coze.vue](src/components/agentCenter/coze.vue) | iframe内嵌Coze服务 | 不经过本后端 |
| `https://hjfy.top/` | [src/components/agentCenter/hjfy.vue](src/components/agentCenter/hjfy.vue) | iframe内嵌HJFY | 不经过本后端 |
| `https://fuyao.rnd.huawei.com/...` | [src/components/deploymentView/deploymentView.vue](src/components/deploymentView/deploymentView.vue) | iframe内嵌 | 不经过本后端 |

---

## 后端子服务分布总览

| 后端服务 | 文件 | 端口 | 说明 |
|---------|------|------|------|
| 主Flask服务 | `server.py` | 7300 | 包含大部分业务逻辑（模型CRUD、用户认证、对话、数据集、报告等） |
| API网关/转发 | `adapter.py` | 8081 | 对外统一入口，按路径转发到不同内部服务 |
| 测评任务调度 | `run_test_server.py` | 7301 | 运行测试任务（ruler1/ruler2/dev/vlm等） |
| HuggingFace下载 | `huggingface_download_adapter.py` | 21826 | 下载HF数据集/模型 |
| AI School训练推理 | `aischool_train_infer_server.py` | - | AI School的推理和训练逻辑 |
| paperAgent arXiv论文助手 | `paper_agent_server.py` | 7303 | arXiv论文获取、LLM分析、Excel报告生成、定制化搜索（按用户隔离） |
| 数据治理Pipeline后端 | 独立部署（非本仓） | 8765 (`10.189.206.203`) | FastAPI「Agentic Data Flywheel」，任务生成/轨迹采集/质检/纠偏/数据发布，路由自带 `/api` 前缀 |

> **adapter.py 的转发目标**：
> - `INTERNAL_URL` (127.0.0.1:7300) → server.py
> - `RUN_TEST_SERVER_URL` (127.0.0.1:7301) → run_test_server.py
> - `AGENT_SERVER_URL` (127.0.0.1:8510) → Agent服务
> - `AI_SCHOOL_SERVER_URL` (7.216.57.45:12600) → AI School
> - `PHONE_MONITOR_MGR_URL` (127.0.0.1:15000) → 手机监控
> - `VLA_DATA_BACKEND_URL` (127.0.0.1:12321) → VLA数据后端
> - `HG_DOWNLOAD_SERVER_URL` (127.0.0.1:21826) → HF下载服务
> - `PAPER_AGENT_SERVER_URL` (127.0.0.1:7303) → paperAgent arXiv论文助手
> - `DF_BACKEND_URL` (10.189.206.203:8765) → 数据治理Pipeline（FastAPI，透传 `/api` 前缀）

---

## 使用说明

### 当你需要修改前后端时：

1. **查找前端调用**：在上表中找到前端路由 → 确认前端文件和使用的URL常量
2. **跟踪到后端**：
   - 如果路由经过 `adapter.py`（大多数 `API_BASE_URL` 的调用都经过它），先在 `adapter.py` 中找到对应路由
   - `adapter.py` 中的转发目标（`INTERNAL_URL` → `server.py:7300`，`RUN_TEST_SERVER_URL` → `run_test_server.py:7301` 等）决定了实际处理请求的文件
3. **确认后端实现**：在后端对应文件中搜索对应的路由装饰器（如 `@app.route('/v1/xxx')`）
4. **同步修改**：根据确认的后端代码位置，同时修改前后端

### 新增接口时的规范：

1. **前端**：在 `Constants.js` 中已定义的 URL 常量基础上拼接路由，不要硬编码完整URL
2. **后端**：如果路由需要在 `adapter.py` 中注册转发，需同时修改 `adapter.py` 和实际处理文件
3. **路由命名**：尽可能详细、避免冲突，遵循 RESTful 风格

---

*最后更新时间：2026-09-20*