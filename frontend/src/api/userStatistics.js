import axios from 'axios';
import { API_BASE_URL } from "@/utils/Constants.js";

/**
 * 用户操作统计 - API 接口
 *
 * 所有接口均基于 API_BASE_URL，路径前缀统一使用 /v1/user_statistics/
 * 返回格式: { code: 0, data: {...}, message: "success" }
 */

/**
 * 1. 获取概览统计数据（统计卡片）
 * GET /v1/user_statistics/overview
 * @param {Object} params
 * @param {string} [params.start_date] - 起始日期 YYYY-MM-DD
 * @param {string} [params.end_date]   - 结束日期 YYYY-MM-DD
 * @returns {Promise<AxiosResponse<{code:0, data:{
 *   total_operations: number,    // 总操作次数
 *   active_users: number,        // 活跃用户数
 *   daily_avg: number,           // 日均操作次数
 *   peak_day: { date: string, count: number } | null // 峰值日
 * }, message:string}>>}
 */
export const getOverview = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/overview', { params });
};

/**
 * 2. 获取用户操作趋势（折线图）
 * GET /v1/user_statistics/trend
 * @param {Object} params
 * @param {string} [params.start_date]
 * @param {string} [params.end_date]
 * @param {string} [params.type] - 操作类型筛选，不传则返回全部类型
 * @returns {Promise<AxiosResponse<{code:0, data:{
 *   series: Array<{ name: string, data: number[] }>, // 每条折线
 *   xAxis: string[]  // 日期标签 ["07-01", "07-02", ...]
 * }, message:string}>>}
 */
export const getTrend = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/trend', { params });
};

/**
 * 3. 获取操作类型分布（饼图）
 * GET /v1/user_statistics/type_distribution
 * @param {Object} params
 * @param {string} [params.start_date]
 * @param {string} [params.end_date]
 * @returns {Promise<AxiosResponse<{code:0, data:{
 *   items: Array<{ name: string, value: number }>
 * }, message:string}>>}
 */
export const getTypeDistribution = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/type_distribution', { params });
};

/**
 * 4. 获取部门使用统计（柱状图）
 * GET /v1/user_statistics/department_stats
 * @param {Object} params
 * @param {string} [params.start_date]
 * @param {string} [params.end_date]
 * @param {number} [params.top_n=15]
 * @returns {Promise<AxiosResponse<{code:0, data:{
 *   dept4: { names: string[], counts: number[] },
 *   dept5: { names: string[], counts: number[] },
 *   dept6: { names: string[], counts: number[] },
 * }, message:string}>>}
 */
export const getDepartmentStats = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/department_stats', { params });
};

/**
 * 5. 获取活跃用户排行（柱状图）
 * GET /v1/user_statistics/top_users
 * @param {Object} params
 * @param {string} [params.start_date]
 * @param {string} [params.end_date]
 * @param {number} [params.top_n=10]
 * @returns {Promise<AxiosResponse<{code:0, data:{
 *   users: string[],    // 用户ID或姓名
 *   counts: number[]    // 操作次数
 * }, message:string}>>}
 */
export const getTopUsers = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/top_users', { params });
};

/**
 * 6. 获取操作明细列表（底表分页）
 * GET /v1/user_statistics/details
 * @param {Object} params
 * @param {string} [params.start_date]
 * @param {string} [params.end_date]
 * @param {string} [params.user_id]      - 按用户筛选
 * @param {string} [params.type]         - 按操作类型筛选
 * @param {string} [params.model_id]     - 按模型筛选
 * @param {string} [params.keyword]      - 用户名模糊搜索（不限大小写）
 * @param {string} [params.types]        - 操作类型多选，逗号分隔
 * @param {number} [params.page=1]
 * @param {number} [params.page_size=20]
 * @returns {Promise<AxiosResponse<{code:0, data:{
 *   total: number,
 *   page: number,
 *   page_size: number,
 *   records: Array<{
 *     user_id: string,
 *     timestamp: string,      // "2026-07-09 14:30:00"
 *     type: string,           // 操作类型
 *     model_id: string,
 *     dept: string,           // 部门信息 "四级部门-五级部门-六级部门"
 *     content: string,        // 内容摘要
 *     query: string,          // 完整请求（可展开）
 *     response: string,       // 完整响应（可展开）
 *   }>
 * }, message:string}>>}
 */
export const getDetails = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/details', { params });
};

/**
 * 7. 搜索用户（远程搜索下拉）
 * GET /v1/user_statistics/user_candidates
 * @param {Object} params
 * @param {string} [params.keyword]
 * @returns {Promise<AxiosResponse<{code:0, data:{ users: string[] }, message:string}>>}
 */
export const getUserCandidates = (params) => {
  return axios.get(API_BASE_URL + 'user_statistics/user_candidates', { params });
};

/**
 * 8. 获取模型列表（筛选器用）
 * GET /v1/user_statistics/model_candidates
 * @returns {Promise<AxiosResponse<{code:0, data:{ models: string[] }, message:string}>>}
 */
export const getModelCandidates = () => {
  return axios.get(API_BASE_URL + 'user_statistics/model_candidates');
};

export const getTypeCandidates = () => {
  return axios.get(API_BASE_URL + 'user_statistics/type_candidates');
}