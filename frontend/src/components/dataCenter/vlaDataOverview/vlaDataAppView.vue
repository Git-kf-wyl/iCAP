<template>
  <div class="app-view">
    <h1>VLA训练数据概览 - App视角</h1>

    <!-- 视图切换导航 -->
    <div class="view-switch">
      <router-link to="/dataCenter/vlaDataOverview/vlaDataSceneView" class="view-link">场景视角</router-link>
      <router-link to="/dataCenter/vlaDataOverview/vlaDataAppView" class="view-link">App视角</router-link>
    </div>


    <!-- 筛选栏 -->
    <div class="filters">
      <div class="filter-item">
        <label>数据来源：</label>
        <select v-model="filters.source" @change="onSourceChange">
          <option value="all">所有数据</option>
          <option v-for="s in sources" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div class="filter-item">
        <label>选择App：</label>
        <select v-model="filters.app" @change="onAppChange">
          <option value="all">全部App</option>
          <option v-for="app in apps" :key="app" :value="app">{{ app }}</option>
        </select>
      </div>
      <div class="filter-item">
        <label>一级场景：</label>
        <select v-model="filters.level1" @change="onLevel1Change">
          <option value="">全部</option>
          <option v-for="scene in sceneTree" :key="scene.name" :value="scene.name">{{ scene.name }}</option>
        </select>
      </div>
      <div class="filter-item">
        <label>二级场景：</label>
        <select v-model="filters.level2" :disabled="!level2Options.length" @change="onLevel2Change">
          <option value="">全部</option>
          <option v-for="l2 in level2Options" :key="l2" :value="l2">{{ l2 }}</option>
        </select>
      </div>
      <div class="filter-item">
        <label>起始日期：</label>
        <input type="date" v-model="filters.start_date" />
      </div>
      <div class="filter-item">
        <label>结束日期：</label>
        <input type="date" v-model="filters.end_date" />
      </div>
      <div class="filter-item">
        <label>快捷选择：</label>
        <div style="display: flex; gap: 8px;">
          <button @click="setRecentDays(7)">最近一周</button>
          <button @click="setRecentDays(30)">最近一个月</button>
        </div>
      </div>
      <div class="filter-item">
        <button class="search-btn" @click="handleSearch" :disabled="loading">搜索</button>
      </div>
    </div>

    <!-- 卡片区 -->
    <div class="cards">
      <div class="card" v-for="item in cardItems" :key="item.title">
        <div class="card-title">{{ item.title }}</div>
        <div class="card-value">{{ formatValue(item.key) }}</div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts">
      <div class="chart-container" ref="trendChartRef"></div>
      <div class="chart-container" ref="sceneBarChartRef"></div>
    </div>

    <!-- 两个扇形图 -->
    <div class="pie-row">
      <div class="pie-card">
        <h3>操作类型分布</h3>
        <div class="pie-chart" ref="actionChartRef"></div>
      </div>
      <div class="pie-card">
        <h3>任务步数分布</h3>
        <div class="pie-chart" ref="stepChartRef"></div>
      </div>
    </div>

    <!-- Loading 遮罩 -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div>加载中...</div>
    </div>

    <!-- 成功提示 -->
    <div v-if="successMessage" class="success-toast">{{ successMessage }}</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import {useVlaDataApi} from "@/api/dataFactory.js";

const {
  fetchSources,
  fetchDateRange,
  fetchScenes,
  fetchApps,
  fetchData,
  fetchSceneStats,
  fetchDistributions,
} = useVlaDataApi()

const sources = ref([])
const sceneTree = ref([])
const apps = ref([])
const overview = ref({})
const trendData = ref([])
const sceneStats = ref([])
const actionStats = ref([])
const stepStats = ref([])

const filters = reactive({
  source: 'all',
  app: 'all',
  level1: '',
  level2: '',
  start_date: '',
  end_date: '',
})

const level2Options = ref([])

const loading = ref(false)
const successMessage = ref('')
let messageTimer = null

const showSuccess = (msg) => {
  if (messageTimer) clearTimeout(messageTimer)
  successMessage.value = msg
  messageTimer = setTimeout(() => {
    successMessage.value = ''
  }, 2000)
}

let trendChart = null
let sceneBarChart = null
let actionChart = null
let stepChart = null

const trendChartRef = ref(null)
const sceneBarChartRef = ref(null)
const actionChartRef = ref(null)
const stepChartRef = ref(null)

const cardItems = [
  { title: '轨迹总数', key: 'total_trajectories' },
  { title: '子任务轨迹数', key: 'subtask_trajectories' },
  { title: 'Step总数', key: 'total_steps' },
  { title: '1级场景总数', key: 'level1_scenes' },
  { title: '2级场景总数', key: 'level2_scenes' },
  { title: 'App总数', key: 'total_apps' },
  { title: '轨迹平均Step数', key: 'avg_steps_per_trajectory' },
]

const formatValue = (key) => {
  let val = overview.value[key] ?? 0
  if (key === 'avg_steps_per_trajectory') return val.toFixed(1)
  return val.toLocaleString()
}

// ========== API 调用 ==========
const loadSources = async () => {
  const data = await fetchSources()
  sources.value = data
  filters.source = 'all'
}

const loadDateRange = async () => {
  const params = { ...filters }
  delete params.level2
  const range = await fetchDateRange(params)
  if (range.min_date && range.max_date) {
    filters.start_date = range.min_date
    filters.end_date = range.max_date
  } else {
    filters.start_date = ''
    filters.end_date = ''
  }
}

const loadScenes = async () => {
  const params = { ...filters }
  delete params.level2
  const data = await fetchScenes(params)
  sceneTree.value = data
  if (filters.level1 && !sceneTree.value.some(s => s.name === filters.level1)) {
    filters.level1 = ''
  }
  updateLevel2Options()
}

const updateLevel2Options = () => {
  const selected = sceneTree.value.find(s => s.name === filters.level1)
  if (selected && selected.level2_scenes.length) {
    level2Options.value = selected.level2_scenes
    if (filters.level2 && !level2Options.value.includes(filters.level2)) {
      filters.level2 = ''
    }
  } else {
    level2Options.value = []
    filters.level2 = ''
  }
}

const loadApps = async () => {
  const params = { ...filters }
  delete params.app
  const data = await fetchApps(params)
  apps.value = data
  if (filters.app !== 'all' && !apps.value.includes(filters.app)) {
    filters.app = 'all'
  }
}

const loadOverviewData = async () => {
  const params = { ...filters }
  const data = await fetchData(params)
  overview.value = data.overview
  trendData.value = data.trend
  renderTrendChart()
}

const loadSceneStats = async () => {
  const params = { ...filters }
  const data = await fetchSceneStats(params)
  sceneStats.value = data
  renderSceneBarChart()
}

const loadDistributions = async () => {
  const params = { ...filters }
  const data = await fetchDistributions(params)
  actionStats.value = data.action_stats
  stepStats.value = data.step_stats
  renderPieCharts()
}

const refreshAllData = async () => {
  await Promise.all([loadOverviewData(), loadSceneStats(), loadDistributions()])
}

// ========== 事件处理 ==========
const onSourceChange = async () => {
  filters.level1 = ''
  filters.level2 = ''
  filters.app = 'all'
  await loadDateRange()
  await loadApps()
  await loadScenes()
  // 不刷新数据
}

const onAppChange = async () => {
  filters.level1 = ''
  filters.level2 = ''
  await loadScenes()
  // 不刷新数据
}

const onLevel1Change = () => {
  filters.level2 = ''
  updateLevel2Options()
  // 不刷新数据
}

const onLevel2Change = () => {
  // 无下级，不刷新
}

const setRecentDays = (days) => {
  const today = new Date()
  const past = new Date(today)
  past.setDate(today.getDate() - days)
  const formatDate = (d) => d.toISOString().slice(0, 10)
  filters.start_date = formatDate(past)
  filters.end_date = formatDate(today)
}

const handleSearch = async () => {
  if (loading.value) return
  loading.value = true
  try {
    await refreshAllData()
    showSuccess('数据加载完成')
  } catch (error) {
    console.error('加载失败:', error)
    showSuccess('加载失败，请重试')
  } finally {
    loading.value = false
  }
}

// ========== 图表渲染 ==========
const renderTrendChart = () => {
  if (!trendChartRef.value) return
  if (trendChart) trendChart.dispose()
  trendChart = echarts.init(trendChartRef.value)
  trendChart.setOption({
    title: { text: '轨迹数量随时间变化趋势（累积）', left: 'center', textStyle: { fontSize: 20 } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 10 },
    grid: { left: '5%', right: '5%', bottom: '15%', containLabel: true },
    dataZoom: [{ type: 'slider', start: 0, end: 100, bottom: 40 }],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trendData.value.map(item => item.date),
      axisLabel: { rotate: 35, interval: 'auto', fontSize: 13, margin: 10 }
    },
    yAxis: { type: 'value', name: '累积数量' },
    series: [
      { name: '总轨迹数', type: 'line', data: trendData.value.map(item => item.total_trajectories), smooth: true, areaStyle: { opacity: 0.1 } },
      { name: '子任务轨迹数', type: 'line', data: trendData.value.map(item => item.subtask_trajectories), smooth: true },
      { name: 'Step总数', type: 'line', data: trendData.value.map(item => item.total_steps_cumulative), smooth: true, lineStyle: { type: 'dashed' } }
    ]
  })
}

const renderSceneBarChart = () => {
  if (!sceneBarChartRef.value) return
  if (sceneBarChart) sceneBarChart.dispose()
  sceneBarChart = echarts.init(sceneBarChartRef.value)
  sceneBarChart.setOption({
    title: { text: '各二级场景分布明细', left: 'center', textStyle: { fontSize: 20 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 10 },
    grid: { left: '5%', right: '5%', bottom: '20%', containLabel: true },
    dataZoom: [{ type: 'slider', start: 0, end: 100, bottom: 40 }],
    xAxis: {
      type: 'category',
      data: sceneStats.value.map(item => item.scene_name),
      axisLabel: { rotate: 35, interval: 0 }
    },
    yAxis: { type: 'value', name: '数量' },
    series: [
      { name: '轨迹总数', type: 'bar', data: sceneStats.value.map(item => item.total_trajectories) },
      { name: '子任务轨迹数', type: 'bar', data: sceneStats.value.map(item => item.subtask_trajectories) },
      { name: 'Step总数', type: 'bar', data: sceneStats.value.map(item => item.total_steps) }
    ]
  })
}

const renderPieCharts = () => {
  if (!actionChartRef.value || !stepChartRef.value) return
  if (actionChart) actionChart.dispose()
  actionChart = echarts.init(actionChartRef.value)
  actionChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 个 ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'center' },
    series: [{
      name: '操作类型',
      type: 'pie',
      radius: '50%',
      data: actionStats.value.map(item => ({ name: item.category, value: item.count })),
      label: { show: true, position: 'outside', formatter: '{b}: {c}' }
    }]
  })

  if (stepChart) stepChart.dispose()
  stepChart = echarts.init(stepChartRef.value)
  stepChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 个任务 ({d}%)' },
    legend: { orient: 'vertical', left: 'left', top: 'center' },
    series: [{
      name: '任务步数',
      type: 'pie',
      radius: '50%',
      data: stepStats.value.map(item => ({ name: item.steps + ' 步', value: item.count })),
      label: { show: true, position: 'outside', formatter: '{b}: {c}' }
    }]
  })
}

const handleResize = () => {
  trendChart?.resize()
  sceneBarChart?.resize()
  actionChart?.resize()
  stepChart?.resize()
}

onMounted(async () => {
  await loadSources()
  await loadDateRange()
  await loadApps()
  await loadScenes()
  await handleSearch()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  sceneBarChart?.dispose()
  actionChart?.dispose()
  stepChart?.dispose()
})
</script>

<style scoped>
.app-view {
  max-width: 98%;
  margin: 0 auto;
  font-family: 'Microsoft YaHei', sans-serif;
  background-color: #f5f7fa;
  padding: 10px;
}
h1 {
  margin: 15px 0;
  color: #333;
  text-align: center;
  font-size: 28px;
}
.view-switch {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin: 10px 0 20px 0;
}
.view-link {
  display: inline-block;
  padding: 8px 20px;
  background-color: #f0f2f5;
  color: #606266;
  border-radius: 20px;
  text-decoration: none;
  font-size: 16px;
  transition: all 0.2s;
}
.view-link:hover {
  background-color: #66b1ff;
  color: white;
}
.view-link.active {
  background-color: #409EFF;
  color: white;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: flex-end;
  margin-bottom: 20px;
  background: white;
  padding: 15px 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.filter-item {
  display: flex;
  flex-direction: column;
}
.filter-item label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 5px;
}
.filter-item select,
.filter-item input[type=date] {
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
  background-color: white;
  font-size: 14px;
  min-width: 160px;
  cursor: pointer;
  outline: none;
  font-family: inherit;
}
.filter-item select:disabled {
  background-color: #f5f7fa;
  cursor: not-allowed;
}
.filter-item button {
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
  background-color: #f5f7fa;
  font-size: 14px;
  cursor: pointer;
}
.filter-item button:hover {
  background-color: #e4e7ed;
}
.search-btn {
  background-color: #409EFF !important;
  color: white !important;
  border: none !important;
}
.search-btn:hover {
  background-color: #66b1ff !important;
}
.search-btn:disabled {
  background-color: #a0cfff !important;
  cursor: not-allowed;
}
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  margin-bottom: 20px;
}
.card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  padding: 20px;
  flex: 1 1 200px;
  text-align: center;
  transition: transform 0.2s;
}
.card:hover { transform: translateY(-3px); }
.card-title { font-size: 16px; color: #909399; margin-bottom: 10px; }
.card-value { font-size: 28px; font-weight: bold; color: #303133; }
.charts {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.chart-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  padding: 20px;
  width: 100%;
  height: 500px;
}
.pie-row {
  display: flex;
  gap: 20px;
  margin-top: 20px;
}
.pie-card {
  flex: 1;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  padding: 20px;
}
.pie-card h3 {
  font-size: 18px;
  color: #333;
  margin-bottom: 10px;
  text-align: center;
}
.pie-chart {
  width: 100%;
  height: 400px;
}
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  color: white;
  font-size: 20px;
  flex-direction: column;
}
.loading-spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin-bottom: 10px;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.success-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  background: #4caf50;
  color: white;
  padding: 12px 20px;
  border-radius: 4px;
  z-index: 10000;
  box-shadow: 0 2px 10px rgba(0,0,0,0.2);
}
</style>