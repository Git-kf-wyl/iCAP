import axios from 'axios';
import { API_BASE_URL } from "@/utils/Constants.js";

export const get_datasets = (is_field) => {
  return axios.get(API_BASE_URL + 'get_testcase_info', { params: { is_field: is_field } });
};

export const get_count = (requestData) => {
  return axios.get(API_BASE_URL + 'dataset/counts', { params: requestData });
};

export const get_dataset_files = (requestData) => {
  return axios.get(API_BASE_URL + 'get_dataset_file_path', { params: requestData });
};

export const edit_datasets = (requestData) => {
  return axios.post(API_BASE_URL + 'edit_testcase_ruler1', requestData);
};

export const delete_datasets = (requestData) => {
  return axios.post(API_BASE_URL + 'delete_testcase_ruler1', requestData);
};

export const updateTestcaseInUse = (requestData) => {
  return axios.post(API_BASE_URL + 'update_testcase_in_use', requestData);
};

export const save_datasets = (requestData) => {
  return axios.post(API_BASE_URL + 'register_testcase_ruler1', requestData);
};

export const save_datasets2 = (requestData) => {
  return axios.post(API_BASE_URL + 'register_testcase_ruler2', requestData);
};

export const upload_file = (requestData) => {
  return axios.post(API_BASE_URL + 'upload/file', requestData);
};

export const delete_folder = (requestData) => {
  return axios.post(API_BASE_URL + 'delete/folder', requestData);
};

export const edit_file = (requestData) => {
  return axios.post(API_BASE_URL + 'edit/file', requestData);
};

export const retrieve_files = (requestData) => {
  return axios.post(API_BASE_URL + 'retrieve/files', requestData);
};

export const update_download = (requestData) => {
  return axios.post(API_BASE_URL + 'dataset/update/download', requestData);
};

export const update_view = (requestData) => {
  return axios.post(API_BASE_URL + 'dataset/update/view', requestData);
};

export const downloadExcell = (requestData) => {
  return axios.get(API_BASE_URL + 'get_excel_file', { params: requestData, responseType: 'blob' });
}

export const downloadAisfReport = (requestData) => {
  return axios.get(API_BASE_URL + 'download_aisf_release_result', { params: requestData, responseType: 'blob' });
}

export const getIntepretationDatasets = () => {
  return axios.get(API_BASE_URL + 'get_simultaneous_interpretation_cases');
}

export const runInterpretation = (requestData) => {
  return axios.post(API_BASE_URL + 'run_simultaneous_interpretation', requestData);
}

export const uploadMOSFile = (requestData) => {
  return axios.post(API_BASE_URL + 'upload_mos_file', requestData);
}

export const addInterpretationFile = (requestData) => {
  return axios.post(API_BASE_URL + 'add_interpretation_file', requestData);
}

export const addInterpretationDirectory = (requestData) => {
  return axios.post(API_BASE_URL + 'add_interpretation_directory', requestData);
}

export const deleteInterpretationDirectory = (requestData) => {
  return axios.post(API_BASE_URL + 'delete_interpretation_directory', requestData);
}

export const downloadDatasetZip = (requestData) => {
  return axios.get(API_BASE_URL + 'download/dataset_zip', {
    params: requestData,
    responseType: 'blob',
    paramsSerializer: { indexes: null },
  });
};

export const uploadTestResult = (requestData) => {
  return axios.post(API_BASE_URL + 'upload_test_result', requestData);
}

export const getDatasetFileData = (requestData) => {
  return axios.get(API_BASE_URL + 'get_dataset_file_data', { params: requestData });
};

export const getDatasetTree = (requestData) => {
  return axios.get(API_BASE_URL + 'get_dataset_tree', { params: requestData });
};