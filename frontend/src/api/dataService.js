import axios from 'axios';
import { API_BASE_URL, API_MENSHEN_URL, PAYLOAD_MENSHEN } from "@/utils/Constants.js";

export const getCurrentFullRes = () => {
  return axios.get(API_BASE_URL + 'get_current_full_res');
}

export const startRun = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_ruler1', requestData);
};

export const startRunTest = (requestData) => {
  return axios.post(API_BASE_URL + 'run_testcase_ruler1', requestData);
};

export const addmodelSelect = (requestData) => {
  return axios.post(API_BASE_URL + 'register_special_model', requestData);
}

export const deletemodelSelectionByID = (requestData) => {
  return axios.post(API_BASE_URL + 'delete_special_model_info', requestData);
};

export const modifymodelSelect = (requestData) => {
  return axios.post(API_BASE_URL + 'modify_special_model_info', requestData);
}

export const getAllmodelSelect = () => {
  return axios.get(API_BASE_URL + 'get_special_model_info');
}

export const getMultiModelRuler2Data = () => {
  return axios.get(API_BASE_URL + 'get_current_multi_full_res');
}

export const getReportContent = () => {
  return axios.get(API_BASE_URL + 'get_current_multi_full_res');
}

export const getMultiModelData = () => {
  return axios.get(API_BASE_URL + 'get_current_multi_full_res');
}

export const getEvalReport = () => {
  return axios.get(API_BASE_URL + 'get_eval_report');
}

export const modifyEvalReport = (requestData) => {
  return axios.post(API_BASE_URL + 'modify_eval_report', requestData)
}

export const getEvalModelList = () => {
  return axios.get(API_BASE_URL + 'get_eval_model_list');
}

export const modifyEvalModelList = (requestData) => {
  return axios.post(API_BASE_URL + 'modify_eval_model_list', requestData)
}

export const getAIPerformanceData = () => {
  return axios.post(API_MENSHEN_URL, PAYLOAD_MENSHEN)
}

export const getModelsFileData = (requestData) => {
  return axios.post(API_BASE_URL + 'get_models_file_data', requestData)
}

export const downloadModelsFile = () => {
  return axios.get(API_BASE_URL + 'download_models_file', { responseType: 'blob' })
}

export const uploadModelsFile = (requestData) => {
  return axios.post(API_BASE_URL + 'upload_models_file', requestData)
}

export const getFeedbackInfo = (requestData) => {
  return axios.post(API_BASE_URL + 'get_feedback_info', requestData)
}

export const modifyFeedbackInfo = (requestData) => {
  return axios.post(API_BASE_URL + 'modify_feedback_info', requestData)
}

export const deleteFeedbackInfo = (requestData) => {
  return axios.post(API_BASE_URL + 'delete_feedback_info', requestData)
}

export const registerFeedbackInfo = (requestData) => {
  return axios.post(API_BASE_URL + 'register_feedback_info', requestData)
}

export const addLogData = (requestData) => {
  return axios.post(API_BASE_URL + 'add_log_data', requestData)
}

export const getLogData = (requestData) => {
  return axios.post(API_BASE_URL + 'get_log_data', requestData)
}

export const modifyLogData = (requestData) => {
  return axios.post(API_BASE_URL + 'modify_log_data', requestData)
}

export const addModelProgress = (requestData) => {
  return axios.post(API_BASE_URL + 'add_model_progress', requestData)
}

export const getModelProgress = () => {
  return axios.get(API_BASE_URL + 'get_model_progress')
}

export const modifyModelProgress = (requestData) => {
  return axios.post(API_BASE_URL + 'modify_model_progress', requestData)
}

export const getEvaluationResult = () => {
  return axios.get(API_BASE_URL + 'get_evaluation_result')
}

export const writeEvaluationResult = (requestData) => {
  return axios.post(API_BASE_URL + 'write_evaluation_result', requestData)
}

