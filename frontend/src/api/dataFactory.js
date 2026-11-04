/**
 * 数据文件管理器
 * 负责定时从后端获取数据并保存为文本文件
 * 页面刷新时优先从本地文件读取数据
 */
import axios from 'axios';
import { DATA_FACTORY_API } from "@/utils/Constants.js";

class DataFileManager {
  constructor() {
    this.dataCacheFile = 'device_data_cache.json';
    this.isUpdating = false;
    this.lastUpdateTime = 0;
    this.updateInterval = 30000; // 30秒更新间隔

    // 在组件挂载时定时更新数据文件
    this.startAutoUpdate();
  }

  /**
   * 启动自动更新机制
   */
  startAutoUpdate() {
    // 立即执行一次更新
    this.updateDataFile();

    // 设置定时器，每30秒更新一次
    setInterval(() => {
      this.updateDataFile();
    }, this.updateInterval);
  }

  /**
   * 更新本地数据文件
   */
  async updateDataFile() {
    if (this.isUpdating) {
      return; // 如果正在更新，跳过
    }

    const now = Date.now();
    const timeSinceLastUpdate = now - this.lastUpdateTime;

    // 如果距离上次更新不到5秒，跳过更新
    if (timeSinceLastUpdate < 5000) {
      return;
    }

    this.isUpdating = true;

    try {
      // console.log('开始更新数据文件...');
      //
      // // 并行获取设备和统计数据
      // const [devicesResponse, statsResponse] = await Promise.all([
      //   axios.get(`${DATA_FACTORY_API}devices`), // `${API_BASE_URL}get_apply_deploy_list`
      //   axios.get(`${DATA_FACTORY_API}stats`)
      // ]);
      //
      // const devices = devicesResponse.data;
      // const stats = statsResponse.data;
      //
      // // 构建完整的数据结构
      // const fullData = {
      //   timestamp: new Date().toISOString(),
      //   devices: devices,
      //   stats: stats,
      //   metadata: {
      //     deviceCount: devices.length,
      //     collectedTrajectories: stats.collected_trajectories || 0,
      //     finishedTrajectories: stats.finished_trajectories || 0,
      //     activeApps: stats.active_apps || 0
      //   }
      // };
      //
      // // 保存到localStorage（文本文件形式）
      // this.saveToFile(fullData);
      //
      // this.lastUpdateTime = now;
      // console.log('数据文件更新完成');

    } catch (error) {
      console.error('更新数据文件失败:', error);
      // 可以在这里添加错误处理逻辑，比如重试机制
    } finally {
      this.isUpdating = false;
    }
  }

  /**
   * 将数据保存到localStorage（模拟文本文件）
   * @param {Object} data 要保存的数据
   */
  saveToFile(data) {
    try {
      // 将数据转换为JSON字符串，模拟文本文件
      const jsonData = JSON.stringify(data, null, 2);
      localStorage.setItem(this.dataCacheFile, jsonData);

      // 同时设置过期时间（1小时后过期）
      const expiryTime = Date.now() + 60 * 60 * 1000;
      localStorage.setItem(`${this.dataCacheFile}_expiry`, expiryTime.toString());

    } catch (error) {
      console.error('保存数据文件失败:', error);
    }
  }

  /**
   * 从localStorage读取数据文件
   * @returns {Object|null} 读取的数据，如果不存在或过期则返回null
   */
  loadFromFile() {
    try {
      // 检查文件是否过期
      const expiryTime = localStorage.getItem(`${this.dataCacheFile}_expiry`);
      const now = Date.now();

      if (expiryTime && now > parseInt(expiryTime)) {
        // 文件过期，删除旧文件
        localStorage.removeItem(this.dataCacheFile);
        localStorage.removeItem(`${this.dataCacheFile}_expiry`);
        return null;
      }

      // 读取数据文件
      const jsonData = localStorage.getItem(this.dataCacheFile);
      if (!jsonData) {
        return null;
      }

      const data = JSON.parse(jsonData);
      console.log('从本地文件加载数据，时间:', data.timestamp);
      return data;

    } catch (error) {
      console.error('读取数据文件失败:', error);
      return null;
    }
  }

  /**
   * 获取设备数据（优先从本地文件读取）
   * @returns {Array} 设备列表
   */
  getDevices() {
    const localData = this.loadFromFile();
    if (localData && localData.devices) {
      return localData.devices;
    }

    // 如果本地没有数据，返回空数组
    console.log('本地没有设备数据，返回空数组');
    return [];
  }

  /**
   * 获取统计数据（优先从本地文件读取）
   * @returns {Object} 统计信息
   */
  getStats() {
    const localData = this.loadFromFile();
    if (localData && localData.stats) {
      return localData.stats;
    }

    // 如果本地没有数据，返回默认统计信息
    console.log('本地没有统计数据，返回默认值');
    return {
      collected_trajectories: 0,
      finished_trajectories: 0,
      active_apps: 0
    };
  }

  /**
   * 获取元数据
   * @returns {Object} 元数据信息
   */
  getMetadata() {
    const localData = this.loadFromFile();
    if (localData && localData.metadata) {
      return localData.metadata;
    }

    return {
      deviceCount: 0,
      collectedTrajectories: 0,
      finishedTrajectories: 0,
      activeApps: 0
    };
  }

  /**
   * 检查数据文件是否存在且有效
   * @returns {boolean} 是否有有效的数据文件
   */
  hasValidDataFile() {
    const localData = this.loadFromFile();
    return localData !== null;
  }

  /**
   * 清理数据文件
   */
  clearDataFile() {
    try {
      localStorage.removeItem(this.dataCacheFile);
      localStorage.removeItem(`${this.dataCacheFile}_expiry`);
      console.log('数据文件已清理');
    } catch (error) {
      console.error('清理数据文件失败:', error);
    }
  }

  /**
   * 强制立即更新数据文件
   */
  async forceUpdate() {
    await this.updateDataFile();
  }
}

// 创建全局实例并导出
const dataFileManager = new DataFileManager();
export default dataFileManager;

export function useVlaDataApi() {
  const fetchSources = async () => {
    const res = await axios.get(`${DATA_FACTORY_API}sources`)
    return res.data
  }

  const fetchDateRange = async (params) => {
    const res = await axios.get(`${DATA_FACTORY_API}date_range`, { params })
    return res.data
  }

  const fetchScenes = async (params) => {
    const res = await axios.get(`${DATA_FACTORY_API}scenes`, { params })
    return res.data
  }

  const fetchApps = async (params) => {
    const res = await axios.get(`${DATA_FACTORY_API}apps`, { params })
    return res.data
  }

  const fetchData = async (params) => {
    const res = await axios.get(`${DATA_FACTORY_API}data`, { params })
    return res.data
  }

  const fetchSceneStats = async (params) => {
    const res = await axios.get(`${DATA_FACTORY_API}scene_stats`, { params })
    return res.data
  }

  const fetchDistributions = async (params) => {
    const res = await axios.get(`${DATA_FACTORY_API}distributions`, { params })
    return res.data
  }

  return {
    fetchSources,
    fetchDateRange,
    fetchScenes,
    fetchApps,
    fetchData,
    fetchSceneStats,
    fetchDistributions,
  }
}