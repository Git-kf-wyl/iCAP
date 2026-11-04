<template>
  <div id="app">
    <div class="header">
      <h1>📱 自动轨迹采集工程可视化</h1>
      <button @click="refreshDevices" class="refresh-btn" :disabled="isRefreshing">
        {{ isRefreshing ? '刷新中...' : '🔄 刷新设备' }}
      </button>
    </div>
    <div class="stats">正在运行手机：{{ devices.length }} 部</div>
    <div class="devices-container">
      <DeviceCard
        v-for="device in devices"
        :key="device['手机编号']"
        :device="device"
        @click="goToDeviceDetail"
      />
    </div>

    <div class="stats-cards">
      <StatCard icon="📊" label="已采集轨迹数" :value="stats.collected_trajectories" />
      <StatCard icon="✅" label="finished轨迹数" :value="stats.finished_trajectories" />
      <StatCard icon="📱" label="正在采集的APP数" :value="stats.active_apps" />
      <StatCard icon="⏳" label="今日采集总数" :value="'--'" />
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import dataFileManager from '../../api/dataFactory.js'

import DeviceCard from '../deviceVisualization/DeviceCard.vue'
import StatCard from '../deviceVisualization/StatCard.vue'
import { DATA_FACTORY_API } from "@/utils/Constants.js";

export default {
  name: 'Home',
  components: {
    DeviceCard,
    StatCard
  },
  setup() {
    const router = useRouter()
    const devices = ref([])
    const stats = ref({
      collected_trajectories: 0,
      finished_trajectories: 0,
      active_apps: 0
    })
    const isRefreshing = ref(false)

    const fetchDevices = async () => {
      try {
        const response = [] // await axios.get(`${DATA_FACTORY_API}devices`)
        devices.value = response.data
        console.log('从后端获取到设备数据:', response.data.length)
      } catch (error) {
        console.error('获取设备数据出错:', error)
      }
    }

    const refreshDevices = async () => {
      if (isRefreshing.value) return

      isRefreshing.value = true
      try {
        // 先从后端获取最新数据
        await axios.get(`${DATA_FACTORY_API}refresh-devices`)
        await fetchAndUpdateBackendData()

        console.log('设备数据已刷新')
      } catch (error) {
        console.error('刷新设备数据出错:', error)
      } finally {
        isRefreshing.value = false
      }
    }

    const fetchStats = async () => {
      try {
        const response = [] // await axios.get(`${DATA_FACTORY_API}stats`)
        stats.value = response.data
        console.log('从后端获取到统计数据:', response.data)
      } catch (error) {
        console.error('获取统计信息出错:', error)
      }
    }

    const goToDeviceDetail = (deviceId) => {
      console.log('=== 点击设备，准备跳转 ===')
      console.log('设备ID:', deviceId)
      console.log('当前URL:', window.location.href)

      // 使用Vue Router进行跳转，确保正确传递设备ID参数
      try {
        router.push(`/device/${deviceId}`)
          .then(() => {
            console.log('Vue Router跳转成功的设备:', deviceId)
          })
          .catch(err => {
            console.error('Vue Router跳转失败:', err)
            // 如果Vue Router失败，回退到传统跳转方式
            window.location.href = `/device/${deviceId}`
          })
      } catch (e) {
        console.error('Vue Router异常:', e)
        // 回退到传统跳转方式
        window.location.href = `/device/${deviceId}`
      }
    }

    // 初始化数据
    onMounted(() => {
      // 优先从本地数据文件加载
      loadLocalData()

      // 延迟后从后端获取最新数据并更新本地文件
      setTimeout(() => {
        fetchAndUpdateBackendData()
      }, 2000) // 2秒后从后端获取最新数据
    })

    /**
     * 从本地数据文件加载数据
     */
    const loadLocalData = () => {
      console.log('从本地数据文件加载...')

      // 从本地文件获取设备数据
      const localDevices = dataFileManager.getDevices()
      devices.value = localDevices

      // 从本地文件获取统计数据
      const localStats = dataFileManager.getStats()
      stats.value = localStats

      console.log('本地数据加载完成，设备数量:', localDevices.length)
    }

    /**
     * 从后端获取数据并更新本地文件
     */
    const fetchAndUpdateBackendData = async () => {
      try {
        console.log('从后端获取最新数据...')

        // 并行获取设备和统计数据
        await Promise.all([
          fetchDevices(),
          fetchStats()
        ])

        // 数据文件管理器会自动定期更新，这里手动触发一次更新
        await dataFileManager.forceUpdate()

        console.log('后端数据获取完成')
      } catch (error) {
        console.error('从后端获取数据失败:', error)
        // 如果后端获取失败，继续使用本地数据
      }
    }

    return {
      devices,
      stats,
      goToDeviceDetail,
      refreshDevices,
      isRefreshing
    }
  }
}
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

#app {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 20px;
}

.refresh-btn {
  padding: 8px 16px;
  background-color: #3498db;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.3s;
}

.refresh-btn:hover:not(:disabled) {
  background-color: #2980b9;
}

.refresh-btn:disabled {
  background-color: #95a5a6;
  cursor: not-allowed;
}

.stats {
  margin: 20px 0;
  font-size: 18px;
  color: #666;
}

.devices-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}
</style>