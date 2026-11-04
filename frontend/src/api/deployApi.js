import axios from 'axios'
import { API_BASE_URL, DEPLOY_API_BASE } from "@/utils/Constants.js";

const BASE = API_BASE_URL
const DEPLOY_BASE = DEPLOY_API_BASE

/**
 * 提交模型部署请求
 */
export function submitDeploy(data) {
  return axios.post(`${DEPLOY_BASE}create`, data)
}

/**
 * 查询指定 IP 的部署状态
 */
export function queryDeployStatus(data) {
  return axios.post(`${DEPLOY_BASE}deploystatus`, data)
}

/**
 * 查询所有模型部署状态（容器列表、空闲卡、模型信息）
 */
export function queryAllStatus(params) {
  return axios.post(`${DEPLOY_BASE}status`, params || {})
}

/**
 * 停止模型
 */
export function stopModel(data) {
  return axios.post(`${DEPLOY_BASE}stop`, data)
}

/**
 * 下载模型镜像
 */
export function downloadModel(data) {
  return axios.post(`${DEPLOY_BASE}download`, data)
}

/**
 * 模型配置管理（增删改查 modelinfo.json）
 */
export function modelConfig(data) {
  return axios.post(`${DEPLOY_BASE}modelconfig`, data)
}