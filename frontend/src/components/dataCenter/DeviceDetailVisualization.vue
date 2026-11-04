<template>
  <div class="device-detail-page">
    <router-link to="/dataCenter/collectionVisualization" class="back-link">← 返回设备列表</router-link>
    <div id="connection-status" :style="connectionStatusStyle">
      {{ connectionStatus }}
    </div>
    <div class="container">
      <!-- 左侧：嵌入 scrcpy-web 画面（需单独运行）: 该接口预留，不作修改 -->
      <div class="left">
        <iframe src="about:blank" allowfullscreen></iframe>
      </div>
      <!-- 右侧：信息与日志 -->
      <div class="right">
        <div class="info-box">
          <h3>手机基本信息</h3>
          <div id="device-info" :class="{ 'loading': isLoading.deviceInfo, 'error': deviceInfo.error }">
            <div v-if="deviceInfo.error" class="error-message" style="color: #e74c3c; background: #fadbd8; padding: 10px; border-radius: 5px; margin: 10px 0;">❌ {{ deviceInfo.error }}</div>
            <div v-else-if="isLoading.deviceInfo" style="color: #3498db; font-style: italic;">加载中...</div>
            <div v-else-if="Object.keys(deviceInfo).length > 0">
              <div v-for="(value, key) in deviceInfo" :key="key" v-if="key !== 'error'">
                <strong>{{ key }}：</strong>{{ formatValue(key, value) }}
              </div>
            </div>
            <div v-else style="color: #7f8c8d;">暂无设备信息</div>
          </div>
        </div>
        <div class="info-box">
          <h3>当前进行的任务</h3>
          <div id="task-info" :class="{ 'loading': isLoading.taskInfo, 'error': taskInfo.error }">
            <div v-if="taskInfo.error" class="error-message" style="color: #e74c3c; background: #fadbd8; padding: 10px; border-radius: 5px; margin: 10px 0;">❌ {{ taskInfo.error }}</div>
            <div v-else-if="isLoading.taskInfo" style="color: #3498db; font-style: italic;">加载中...</div>
            <div v-else-if="Object.keys(taskInfo).length > 0">
              <div v-for="(value, key) in taskInfo" :key="key" v-if="key !== 'error'">
                <strong>{{ key }}：</strong>{{ value }}
              </div>
            </div>
            <div v-else style="color: #7f8c8d;">暂无任务信息</div>
          </div>
        </div>
        <div class="log-box">
          <h3>自动化采集日志</h3>
          <div class="log-content" ref="logContent"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { DATA_FACTORY_API, DATA_FACTORY_LOG_WS } from "@/utils/Constants.js";

export default {
  name: 'DeviceDetail',
  setup() {
    const route = useRoute()
    const deviceId = ref(route.params.id)

    // 监听路由参数变化，当路由变化时重新获取数据
    watch(() => route.params.id, (newId) => {
      if (newId && newId !== deviceId.value) {
        console.log('路由参数变化，设备ID从', deviceId.value, '变为', newId)
        deviceId.value = newId
        // 重新获取数据
        fetchInfo().catch(error => {
          console.log('路由变化后数据获取失败:', error.message)
        })
      }
    })
    const deviceInfo = ref({})  // 恢复为空对象
    const taskInfo = ref({})  // 恢复为空对象
    const logContent = ref(null)
    const connectionStatus = ref('🔍 正在连接...')
    const connectionType = ref('info')
    const isLoading = ref({
      deviceInfo: false, // 改为false，初始化时默认不显示加载状态
      taskInfo: false
    })

    // 配置常量 - 统一使用localhost
    const REQUEST_TIMEOUT = 3000 // 3秒超时，减少等待时间

    const connectionStatusStyle = computed(() => ({
      position: 'fixed',
      top: '10px',
      right: '10px',
      padding: '10px',
      borderRadius: '5px',
      fontSize: '14px',
      zIndex: '1000',
      background: connectionType.value === 'success' ? '#2ecc71' :
                 connectionType.value === 'error' ? '#e74c3c' :
                 connectionType.value === 'warning' ? '#f39c12' : '#f39c12',
      color: 'white'
    }))

    // 强制重新渲染的方法，用于调试
    const forceRerender = () => {
      console.log('=== 强制重新渲染 ===')
      console.log('当前设备ID:', deviceId.value)
      console.log('当前设备信息:', deviceInfo.value)
      console.log('当前任务信息:', taskInfo.value)
    }

    // 创建带超时的axios请求 - 简化版
    const axiosWithTimeout = async (url, options = {}, timeout = REQUEST_TIMEOUT) => {
      return axios({
        ...options,
        url,
        timeout: timeout
      })
    }

    // 显示错误信息
    const showError = (target, message) => {
      if (target === 'deviceInfo') {
        deviceInfo.value = { error: message }
        isLoading.value.deviceInfo = false
      } else if (target === 'taskInfo') {
        taskInfo.value = { error: message }
        isLoading.value.taskInfo = false
      }
    }

    // 更新连接状态显示（简化版）
    const updateConnectionStatus = (message, type = 'info') => {
      connectionStatus.value = message
      connectionType.value = type
    }

    // 快速检查API连接（简化版）
    const checkApiStatus = async () => {
      try {
        console.log(`尝试连接API: ${DATA_FACTORY_API}stats`)
        const response = await axiosWithTimeout(`${DATA_FACTORY_API}stats`, {
          method: 'GET'
        })
        updateConnectionStatus('✅ API连接正常', 'success')
        return true
      } catch (error) {
        console.log('API连接失败，但仍尝试获取数据:', error.message)
        updateConnectionStatus('⚠️ API连接失败但仍尝试获取数据', 'warning')
        return false
      }
    }

    // 定时刷新手机信息和任务信息 - 优化版，并行执行
    const fetchInfo = async () => {
      console.log('=== 开始获取数据 ===')
      console.log('设备ID:', deviceId.value)

      // 开始加载
      isLoading.value.deviceInfo = true
      isLoading.value.taskInfo = true

      try {
        // 并行获取设备信息和任务信息，使用Promise.allSettled优化性能
        const [deviceResult, taskResult] = await Promise.allSettled([
          fetchDeviceInfo(),
          fetchTaskInfo()
        ])

        console.log('=== 数据获取完成 ===')
        console.log('设备结果状态:', deviceResult.status)
        console.log('任务结果状态:', taskResult.status)
      } catch (error) {
        // 记录错误但不中断流程
        console.error('数据刷新过程中出现错误:', error)
      } finally {
        // 无论成功或失败，都将加载状态设为false
        isLoading.value.deviceInfo = false
        isLoading.value.taskInfo = false
        console.log('=== 加载状态设为false ===')
        console.log('deviceInfo:', deviceInfo.value)
        console.log('taskInfo:', taskInfo.value)
      }
    }

    // 获取设备基本信息 - 简化版
    const fetchDeviceInfo = async () => {
      try {
        console.log('正在获取设备信息，设备ID:', deviceId.value)
        const response = await axiosWithTimeout(`${DATA_FACTORY_API}info/${deviceId.value}`, {
          method: 'GET'
        })

        // 直接赋值，确保触发响应式更新
        deviceInfo.value = response.data
        console.log('设备信息获取成功:', response.data)
      } catch (error) {
        console.error('设备信息加载失败:', error.message)
        deviceInfo.value = { error: `获取失败: ${error.message}` }
      }
    }

    // 获取当前任务信息 - 简化版
    const fetchTaskInfo = async () => {
      try {
        console.log('正在获取任务信息，设备ID:', deviceId.value)
        const response = await axiosWithTimeout(`${DATA_FACTORY_API}task/${deviceId.value}`, {
          method: 'GET'
        })

        // 直接赋值，确保触发响应式更新
        taskInfo.value = response.data
        console.log('任务信息获取成功:', response.data)
      } catch (error) {
        console.error('任务信息加载失败:', error.message)
        taskInfo.value = { error: `获取失败: ${error.message}` }
      }
    }

    // 优化版WebSocket连接管理，减少重连次数和日志输出
    const initWebSocket = () => {
      let reconnectAttempts = 0
      const maxReconnectAttempts = 3 // 减少最大重连次数

      function connectWebSocket() {
        try {
          const ws = new WebSocket(`${DATA_FACTORY_LOG_WS}phone_app_run_log`)

          ws.onopen = function() {
            reconnectAttempts = 0 // 重置重连计数
            updateConnectionStatus('✅ 日志连接成功', 'success')

            // 添加连接成功消息到日志视图
            if (logContent.value) {
              const entry = document.createElement('div')
              entry.className = 'log-entry'
              entry.style.color = '#2ecc71'
              entry.textContent = `🔗 已连接到日志服务`
              logContent.value.appendChild(entry)
              logContent.value.scrollTop = logContent.value.scrollHeight
            }
          }

          ws.onmessage = function(event) {
            // 只添加实际有意义的消息，去掉时间前缀以减少日志量
            if (event.data && logContent.value) {
              const entry = document.createElement('div')
              entry.className = 'log-entry'
              entry.textContent = event.data
              logContent.value.appendChild(entry)
              logContent.value.scrollTop = logContent.value.scrollHeight
            }
          }

          ws.onerror = function(error) {
            console.log('WebSocket错误:', error.type)
            // 简化错误信息，不显示详细错误类型
            if (logContent.value) {
              const entry = document.createElement('div')
              entry.className = 'log-entry'
              entry.style.color = '#e74c3c'
              entry.textContent = '❌ 日志连接错误'
              logContent.value.appendChild(entry)
            }
          }

          ws.onclose = function(event) {
            console.log('WebSocket断开连接')
            if (logContent.value) {
              const entry = document.createElement('div')
              entry.className = 'log-entry'
              entry.style.color = '#f39c12'
              entry.textContent = `⚠️ 日志连接断开`
              logContent.value.appendChild(entry)
              logContent.value.scrollTop = logContent.value.scrollHeight
            }

            // 简化的重连逻辑
            reconnectAttempts++
            if (reconnectAttempts <= maxReconnectAttempts) {
              // 减少重连延迟
              setTimeout(() => {
                connectWebSocket()
              }, 1000) // 从3秒减少到1秒
            } else {
              updateConnectionStatus('❌ 日志连接失败', 'error')
            }
          }

          return ws
        } catch (error) {
          console.log('无法创建WebSocket连接:', error.message)
          return null
        }
      }

      return connectWebSocket()
    }

    // 格式化值 - 优化版
    const formatValue = (key, value) => {
      // 空值检查前置，快速返回
      if (value === null || value === undefined || value === '') {
        return '—'
      }

      // 特殊格式化
      if (key === '负责生产的app列表') {
        return Array.isArray(value) ? value.join(', ') : String(value)
      }

      // 默认格式化，快速转换
      return String(value)
    }

    // 初始化 - 修复版本，确保正确启动
    onMounted(() => {
      console.log('DeviceDetail组件挂载，设备ID:', deviceId.value)

      // 延迟100ms后获取数据，确保组件完全加载
      setTimeout(() => {
        fetchInfo().catch(error => {
          console.log('数据获取失败:', error.message)
        })
      }, 100)

      // 每30秒刷新一次数据
      setInterval(() => {
        fetchInfo().catch(error => {
          console.log('数据刷新失败:', error.message)
        })
      }, 30000)

      // 初始化WebSocket
      initWebSocket()
    })

    onUnmounted(() => {
      // 清理定时器等资源
      console.log('页面即将卸载，清理资源...')
    })

    return {
      deviceId,
      deviceInfo,
      taskInfo,
      logContent,
      connectionStatus,
      connectionStatusStyle,
      isLoading,
      formatValue
    }
  }
}
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.device-detail-page {
  background: #f0f0f0;
  font-family: Arial, sans-serif;
  padding: 20px;
  min-height: 100vh;
}

.container {
  display: flex !important;
  flex-direction: row !important;
  gap: 20px;
  height: calc(100vh - 80px) !important;
  margin-top: 40px;
  width: 100%;
}

.left {
  flex: 1 !important;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
  height: 100% !important;
  border: 2px solid #ddd;
  min-height: 400px;
}

.left iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
  background-color: #000;
}

.right {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 20px;
  height: 100% !important;
  overflow-y: auto;
}

.info-box {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.info-box h3 {
  margin-bottom: 15px;
  color: #333;
  border-bottom: 1px solid #ddd;
  padding-bottom: 5px;
}

.log-box {
  background: #1e1e1e;
  color: #0f0;
  border-radius: 10px;
  padding: 20px;
  flex: 1;
  overflow-y: auto;
  font-family: monospace;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.log-box h3 {
  color: #fff;
  margin-bottom: 10px;
  border-bottom: 1px solid #444;
  padding-bottom: 5px;
}

.log-content {
  white-space: pre-wrap;
  word-wrap: break-word;
}

.log-entry {
  margin: 4px 0;
}

.back-link {
  margin-bottom: 10px;
  display: inline-block;
  color: #3498db;
  text-decoration: none;
}

.back-link:hover {
  text-decoration: underline;
}

.error-message {
  color: #e74c3c;
  background: #fadbd8;
  padding: 10px;
  border-radius: 5px;
  margin: 10px 0;
  border: 1px solid #e74c3c;
}

.loading {
  color: #3498db;
  font-style: italic;
}
</style>