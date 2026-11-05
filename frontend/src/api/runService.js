import axios from 'axios';
import { API_AGENT_URL, API_BASE_URL } from "@/utils/Constants.js";

export const startRun = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_ruler1', requestData);
};

export const startRun2 = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_ruler2', requestData);
};

export const startRunAisfRelease = (requestData) => {
  return axios.post(API_BASE_URL + 'run_aisf_release', requestData);
};

export const startRun3 = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_dev', requestData);
};

export const startRunMul = (requestData) => {
  return axios.post(API_BASE_URL + 'run_vlm_ruler1', requestData);
};

export const startRunMt = (requestData) => {
  return axios.post(API_BASE_URL + '/v1/run_mt', requestData);
};

export const startRunMul2 = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_ruler2', requestData);
};

export const getList = () => {
  return axios.get(API_BASE_URL + 'get_run_test_progress_list');
};

export const getProgress = (task_id) => {
  return axios.get(API_BASE_URL + 'check_run_test_progress/' + task_id);
};

export const deleteById = (requestData) => {
  return axios.post(API_BASE_URL + 'delete_test_progress', requestData);
};

export const pauseOneTask = (requestData) => {
  return axios.post(API_BASE_URL + 'pause_test_task', requestData);
};

export const resumeOneTask = (requestData) => {
  return axios.post(API_BASE_URL + 'resume_test_task', requestData)
}

export const getResult = (requestData) => {
  return axios.get(API_BASE_URL + 'get_result', { params: requestData });
};

export const downloadFile = (requestData) => {
  return axios.get(API_BASE_URL + 'download/file', { params: requestData, responseType: 'blob' })
};

export const getFilePath = (requestData) => {
  return axios.get(API_BASE_URL + 'get_file_path', { params: requestData })
};

export const getLogs = (requestData) => {
  return axios.get(API_BASE_URL + 'logs', { params: requestData })
};

export const updateScore = (requestData) => {
  const array = value => Array.isArray(value) ? value : value == null ? [] : [value];
  return axios.get(API_BASE_URL + 'update_top_chart', { params: {
    'task_id[]': array(requestData['task_id[]'] ?? requestData.task_id),
    'testcase[]': array(requestData['testcase[]'] ?? requestData.testcase),
  } })
};

export const updateResult = (requestData) => {
  return axios.post(API_BASE_URL + 'update_score', requestData)
};

export const asyncScore = (requestData) => {
  return axios.post(API_BASE_URL + 'async_score', requestData)
};

export const getOneTestTask = (requestData) => {
  return axios.post(API_BASE_URL + 'get_one_test_task', requestData)
}

export const genReport = (requestData) => {
  return axios.post(API_BASE_URL + 'generate_report', requestData);
};

export const downloadEvalReport = (requestData) => {
  return axios.get(API_BASE_URL + 'download/report', { params: requestData, responseType: 'blob' })
};

export const queryReportStatus = (taskId) => {
  return axios.get(API_BASE_URL + 'query_report_status', { params: { task_id: taskId } });
};

export const getLatestReport = (modelId) => {
  return axios.get(API_BASE_URL + 'get_latest_report', { params: { model_id: modelId } });
};

export const deleteReportTask = (taskId) => {
  return axios.post(API_BASE_URL + 'delete_report_task', { task_id: taskId });
};

export const getReportTasksByName = (modelName) => {
  return axios.get(API_BASE_URL + 'get_report_tasks_by_name', { params: { model_name: modelName } });
};

export const getAllReportTasks = () => {
  return axios.get(API_BASE_URL + 'get_all_report_tasks');
};

export const getMinTestChart = (requestData) => {
  return axios.get(API_BASE_URL + 'get_min_test_chart', { params: requestData })
};

export const getAgentFile = (requestData) => {
  return axios.get(API_AGENT_URL + 'download_agent_file', { params: requestData, responseType: 'blob' })
}

export const directPublishReport = (requestData) => {
  return axios.post(API_BASE_URL + 'direct_publish_report', requestData);
}

export const publishReportFromTask = (requestData) => {
  return axios.post(API_BASE_URL + 'publish_report_from_task', requestData);
}

export const getAllPublishedTasks = () => {
  return axios.get(API_BASE_URL + 'get_all_published_tasks');
};

export const previewReportFile = (requestData) => {
  return axios.get(API_BASE_URL + 'preview/report', { params: requestData })
};

export const deletePublishedTask = (taskId) => {
  return axios.post(API_BASE_URL + 'delete_published_task', { id: taskId });
};

export const updatePublishedReport = (requestData) => {
  return axios.post(API_BASE_URL + 'update_published_report', requestData);
};

export const deleteResultById = (requestData) => {
  return axios.post(API_BASE_URL + 'delete_single_result', requestData);
};

export const getEldStatistics = (requestData) => {
  return axios.get(API_BASE_URL + 'get_eld_statistics', { params: requestData })
};

export const startMCPAtlas = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_mcp_atlas', requestData);
};

export const uploadLocalResult = (requestData) => {
  return axios.post(API_BASE_URL + 'upload_local_result', requestData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
