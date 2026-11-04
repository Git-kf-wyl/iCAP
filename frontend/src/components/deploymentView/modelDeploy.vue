<template>
  <div class="app-container">
    <div class="app-header">
      <h1>模型部署管理</h1>
      <p>提交部署任务、查询容器状态、停止模型服务、管理服务器配置</p>
    </div>

    <!-- 错误提示 -->
    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      show-icon
      :closable="true"
      @close="errorMsg = ''"
      style="margin-bottom: 16px;"
    />

    <!-- ===================== 快捷操作 ===================== -->
    <div class="card">
      <div class="toolbar">
        <el-button type="primary" @click="refreshStatus" :loading="statusLoading">
          刷新状态
        </el-button>
        <el-button type="success" @click="showDeployDialog = true">
          新建部署
        </el-button>
        <el-button type="warning" @click="showConfigDialog = true">
          管理配置
        </el-button>
      </div>
    </div>

    <!-- ===================== 部署状态总览 ===================== -->
    <div class="card">
      <h3 style="margin: 0 0 16px; font-size: 16px; color: #303133;">
        部署状态总览
        <el-tag size="small" style="margin-left: 8px;" type="info">容器列表</el-tag>
        <el-tag v-if="hasDeploying" size="small" type="warning" style="margin-left: 6px;" effect="dark">部署中...</el-tag>
      </h3>

      <!-- 容器列表 -->
      <div v-if="containerList.length > 0">
        <el-table :data="containerList" stripe style="width: 100%;" max-height="320">
          <el-table-column prop="ip" label="IP" width="140" />
          <el-table-column prop="container_name" label="容器名称" min-width="280" show-overflow-tooltip />
          <el-table-column label="状态" width="200">
            <template #default="{ row }">
              <div style="display: flex; flex-direction: column; gap: 2px;">
                <el-tag :type="row.status === 'UP' ? 'success' : row.status === 'EXIT' ? 'danger' : 'info'" size="small" style="width: fit-content;">
                  {{ row.status }}
                </el-tag>
                <!-- 有进度数据时显示实时进度 -->
                <span v-if="deployProgressMap[row.ip]" style="font-size: 12px; color: #909399;">
                  {{ deployProgressMap[row.ip].progress || 0 }}% - {{ deployProgressMap[row.ip].message || '' }}
                </span>
                <!-- 容器已 UP 且无进度数据（部署完成已久，进度已过期），显示完成 -->
                <span v-else-if="row.status === 'UP'" style="font-size: 12px; color: #67C23A;">100% - 模型部署完成</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="raw_status" label="详情" min-width="160" show-overflow-tooltip />
          <el-table-column label="API 接口" width="180">
            <template #default="{ row }">
              <span v-if="row.status === 'UP'">{{ apiEndpoint(row) }}</span>
              <span v-else style="color: #909399;">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="danger" link @click="confirmStop(row)">停止</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-else-if="!statusLoading" style="text-align: center; color: #909399; padding: 30px;">
        暂无运行中的容器
      </div>
      <div v-else style="text-align: center; padding: 30px;">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span style="margin-left: 8px; color: #909399;">加载中...</span>
      </div>

      <!-- 空闲卡信息（按 IP 分组） -->
      <div style="margin-top: 16px;">
        <span style="font-weight: 500; font-size: 14px; display: block; margin-bottom: 8px;">空闲 NPU 卡:</span>
        <div v-if="idleCardsByIp.length > 0" style="display: flex; flex-direction: column; gap: 6px;">
          <div v-for="item in idleCardsByIp" :key="item.ip" style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 13px; font-weight: 500; min-width: 110px;">{{ item.ip }}:</span>
            <span v-if="item.cards.length > 0">
              <el-tag
                v-for="card in item.cards"
                :key="card"
                type="success"
                size="small"
                style="margin-right: 4px;"
              >卡 {{ card }}</el-tag>
            </span>
            <span v-else style="color: #909399; font-size: 13px;">无空闲卡</span>
          </div>
        </div>
        <span v-else style="color: #909399; font-size: 13px;">暂无空闲卡</span>
      </div>
    </div>

    <!-- ===================== 新建部署对话框 ===================== -->
    <el-dialog v-model="showDeployDialog" title="新建部署" width="620px" @close="resetDeployForm">
      <el-form :model="deployForm" label-width="110px">
        <el-form-item label="服务器 IP" required>
          <el-select v-model="deployForm.ip" placeholder="选择服务器 IP" style="width: 100%;">
            <el-option v-for="ip in ipList" :key="ip" :label="ip" :value="ip" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称" required>
          <el-select v-model="deployForm.model_name" placeholder="选择模型" style="width: 100%;" :disabled="!deployForm.ip">
            <el-option v-for="m in modelListForSelectedIp" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="NPU 卡数">
          <el-select v-model="deployForm.npunum" placeholder="选择 NPU 卡数" style="width: 100%;" :disabled="!deployForm.model_name">
            <el-option v-for="opt in npuCardOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <span style="font-size: 12px; color: #909399; margin-top: 4px; display: block;">
            最少需 <strong>{{ selectedModelMinCards }}</strong> 卡部署 <strong>{{ deployForm.model_name || '...' }}</strong>
          </span>
        </el-form-item>
        <el-form-item label="端口号">
          <el-input-number v-model="deployForm.port" :min="-1" :max="65535" placeholder="-1 自动分配" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="上下文长度">
          <el-input-number v-model="deployForm.context" :min="1" :max="262144" :step="4096" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="最大并发数">
          <el-input-number v-model="deployForm.maxreq" :min="1" :max="256" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="启动命令(可选)">
          <el-input v-model="deployForm.runcmd" type="textarea" :rows="2" placeholder="留空使用默认启动命令" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeployDialog = false">取消</el-button>
        <el-button type="primary" @click="submitDeployTask" :loading="deployLoading">提交部署</el-button>
      </template>
    </el-dialog>

    <!-- ===================== 配置管理对话框 ===================== -->
    <el-dialog v-model="showConfigDialog" title="模型配置管理" width="900px">
      <div style="margin-bottom: 12px;">
        <el-button size="small" type="primary" @click="loadConfig">刷新配置</el-button>
        <el-button size="small" type="success" @click="showAddIpDialog = true">新增 IP</el-button>
      </div>

      <div v-if="configLoading" style="text-align: center; padding: 40px;">
        <el-icon class="is-loading" :size="20"><Loading /></el-icon>
        <span style="margin-left: 8px; color: #909399;">加载中...</span>
      </div>

      <div v-else-if="configData && Object.keys(configData).length" class="config-tree">
        <div v-for="(cfg, ip) in configData" :key="ip" class="config-ip-section">
          <div class="config-ip-header">
            <el-icon><Monitor /></el-icon>
            <strong>{{ ip }}</strong>
            <el-tag size="small" type="info">auth: {{ cfg.auth }}</el-tag>
            <el-tag size="small" type="warning">NPU: {{ cfg.npuinfo?.join(', ') }}</el-tag>
            <div style="margin-left: auto;">
              <el-button size="small" link @click="openEditIp(ip, cfg)">编辑</el-button>
              <el-button size="small" link type="danger" @click="confirmDeleteIp(ip)">删除</el-button>
              <el-button size="small" link type="primary" @click="openAddModel(ip)">+ 模型</el-button>
            </div>
          </div>
          <div v-if="cfg.modelinfo && Object.keys(cfg.modelinfo).length" class="config-model-table">
            <div class="config-model-row config-model-header">
              <span class="cfg-name">模型名称</span>
              <span class="cfg-img">镜像</span>
              <span class="cfg-card">卡数</span>
              <span class="cfg-actions">操作</span>
            </div>
            <div v-for="(mc, mn) in cfg.modelinfo" :key="mn" class="config-model-row">
              <span class="cfg-name" :title="mn">{{ mn }}</span>
              <span class="cfg-img" :title="mc[0]">{{ mc[0] || '-' }}</span>
              <span class="cfg-card">{{ mc[1] ?? '-' }}</span>
              <span class="cfg-actions">
                <el-button size="small" link @click="openEditModel(ip, mn, mc)">编辑</el-button>
                <el-button size="small" link type="danger" @click="confirmDeleteModel(ip, mn)">删除</el-button>
              </span>
            </div>
          </div>
          <div v-else class="config-no-model">暂无模型</div>
        </div>
      </div>
      <div v-else style="text-align: center; color: #909399; padding: 40px;">
        暂无配置数据
      </div>
    </el-dialog>

    <!-- 新增/编辑 IP 对话框 -->
    <el-dialog v-model="showAddIpDialog" :title="editingIp ? '编辑 IP' : '新增 IP'" width="500px">
      <el-form :model="ipForm" label-width="100px">
        <el-form-item label="IP 地址" required>
          <el-input v-model="ipForm.ip" placeholder="例如 10.90.114.53" :disabled="!!editingIp" />
        </el-form-item>
        <el-form-item label="认证密码" required>
          <el-input v-model="ipForm.auth" placeholder="SSH 密码" />
        </el-form-item>
        <el-form-item label="NPU 卡列表" required>
          <el-input v-model="ipForm.npuinfo" placeholder="例如 0,1,2,3,4,5,6,7" />
          <span style="font-size: 12px; color: #909399;">逗号分隔的 NPU 卡 ID</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddIpDialog = false">取消</el-button>
        <el-button type="primary" @click="saveIpConfig" :loading="ipSaving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑模型对话框 -->
    <el-dialog v-model="showAddModelDialog" :title="editingModelName ? '编辑模型' : '新增模型'" width="600px">
      <el-form :model="modelForm" label-width="110px">
        <el-form-item label="模型名称" required>
          <el-input v-model="modelForm.model_name" placeholder="例如 Qwen3.5-122B-A10B" :disabled="!!editingModelName" />
        </el-form-item>
        <el-form-item label="镜像名称" required>
          <el-input v-model="modelForm.image_name" placeholder="docker 镜像名" />
        </el-form-item>
        <el-form-item label="最小卡数" required>
          <el-input-number v-model="modelForm.min_cards" :min="1" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="模型路径" required>
          <el-input v-model="modelForm.model_path" placeholder="远程服务器上的模型路径" />
        </el-form-item>
        <el-form-item label="启动命令" required>
          <el-input v-model="modelForm.run_cmd" type="textarea" :rows="3" placeholder="vllm serve ..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddModelDialog = false">取消</el-button>
        <el-button type="primary" @click="saveModelConfig" :loading="modelSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, Monitor } from '@element-plus/icons-vue'
import {
  submitDeploy,
  queryDeployStatus,
  queryAllStatus,
  stopModel,
  modelConfig
} from '@/api/deployApi.js'

// ===================== 状态变量 =====================
const errorMsg = ref('')
const statusLoading = ref(false)
const containerList = ref([])
const idleCards = ref([])
const modelInfoMap = ref({})
const ipList = ref([])

// 部署进度查询
const queryIp = ref('')
const progressLoading = ref(false)
const progressData = ref(null)

/** 将空闲卡数据 idleCards（平铺卡 ID 数组）按 IP 分组 */
const idleCardsByIp = computed(() => {
  const idleSet = new Set(idleCards.value)
  const result = []
  for (const [ip, info] of Object.entries(modelInfoMap.value)) {
    const cards = (info.npuinfo || []).filter(c => idleSet.has(c))
    result.push({ ip, cards })
  }
  return result
})

// 根据选中的 IP 动态获取可选的模型名称列表
const modelListForSelectedIp = computed(() => {
  const ip = deployForm.value.ip
  if (!ip || !modelInfoMap.value[ip]) return []
  return Object.keys(modelInfoMap.value[ip].modelinfo || {})
})

// 根据选中的 IP + 模型名称，获取该模型的最小卡数
const selectedModelMinCards = computed(() => {
  const ip = deployForm.value.ip
  const model = deployForm.value.model_name
  if (!ip || !model || !modelInfoMap.value[ip]) return 0
  const mc = modelInfoMap.value[ip].modelinfo?.[model]
  return mc?.[1] ?? 0
})

// 根据选中的 IP 获取可用 NPU 卡总数（最大可选卡数）
const selectedIpMaxCards = computed(() => {
  const ip = deployForm.value.ip
  if (!ip || !modelInfoMap.value[ip]) return 0
  return modelInfoMap.value[ip].npuinfo?.length ?? 0
})

// NPU 卡数可选项：从 minCards ~ maxCards
const npuCardOptions = computed(() => {
  const min = selectedModelMinCards.value
  const max = selectedIpMaxCards.value
  if (!min || !max || max < min) return []
  const opts = []
  for (let i = min; i <= max; i++) {
    opts.push({ label: `${i} 卡`, value: i })
  }
  return opts
})

// 新建部署
const showDeployDialog = ref(false)
const deployLoading = ref(false)
const deployForm = ref({
  ip: '',
  model_name: '',
  npunum: '',
  port: -1,
  context: 81920,
  maxreq: 8,
  runcmd: ''
})

// 配置管理
const showConfigDialog = ref(false)
const configLoading = ref(false)
const configData = ref(null)

// 新增/编辑 IP
const showAddIpDialog = ref(false)
const editingIp = ref('')
const ipSaving = ref(false)
const ipForm = ref({ ip: '', auth: '', npuinfo: '' })

// 新增/编辑模型
const showAddModelDialog = ref(false)
const modelIp = ref('')
const editingModelName = ref('')
const modelSaving = ref(false)
const modelForm = ref({
  model_name: '',
  image_name: '',
  min_cards: 1,
  model_path: '',
  run_cmd: ''
})

// 切换 IP 时清空已选的模型名称和卡数
watch(() => deployForm.value.ip, () => {
  deployForm.value.model_name = ''
  deployForm.value.npunum = 0
})

// 切换模型名称时重置卡数
watch(() => deployForm.value.model_name, () => {
  deployForm.value.npunum = 0
})

// ===================== 方法 =====================

/** 标记当前是否有部署任务正在执行中（RUNNING / PENDING） */
const hasDeploying = ref(false)
/** 各 IP 的部署进度数据 { ip: { status, progress, message, ... } } */
const deployProgressMap = ref({})

/** 刷新服务器状态（容器列表、空闲卡、IP 列表） */
async function refreshStatus() {
  statusLoading.value = true
  errorMsg.value = ''
  try {
    // 传空 body 查询所有 IP
    const res = await queryAllStatus({ ip: [] })
    if (res.data?.status === 'OK') {
      const envAll = res.data.env_all || {}
      containerList.value = envAll.model || []
      idleCards.value = envAll.idle_cards || []
      modelInfoMap.value = envAll.modelInfo || {}
      ipList.value = Object.keys(modelInfoMap.value)
    } else {
      errorMsg.value = res.data?.error || '查询失败'
    }
  } catch (e) {
    errorMsg.value = `请求异常: ${e.message}`
  } finally {
    statusLoading.value = false
  }

  // 刷新后检查所有 IP 的部署进度，判断是否还有任务在运行
  await checkDeployingStatus()
}

/** 记录已提交部署任务的 IP，用于进度轮询（不依赖 modelInfoMap） */
const deployedIps = ref([])

/** 轮询所有 IP 的部署进度，更新 hasDeploying 和 deployProgressMap */
let _checkingProgress = false
async function checkDeployingStatus() {
  if (_checkingProgress) return  // 避免并发覆盖
  _checkingProgress = true
  let deploying = false
  const map = {}
  // 优先用部署 IP 列表，兜底用 modelInfoMap
  let ips = deployedIps.value.length ? deployedIps.value : Object.keys(modelInfoMap.value)
  if (ips.length === 0) { _checkingProgress = false; return }
  for (const ip of ips) {
    try {
      const res = await queryDeployStatus({ ip })
      const st = res.data
      if (st) {
        map[ip] = st
        if (st.status === 'RUNNING' || st.status === 'PENDING') {
          deploying = true
        }
      }
    } catch {
      // 单个 IP 查询失败不影响整体判断
    }
  }
  // 只保留非 IDLE 的进度
  const filtered = {}
  for (const [ip, st] of Object.entries(map)) {
    if (st.status !== 'IDLE') {
      filtered[ip] = st
    }
  }
  deployProgressMap.value = filtered
  hasDeploying.value = deploying
  _checkingProgress = false
}

/** 查询指定 IP 的部署进度 */
async function queryProgress() {
  if (!queryIp.value) return
  progressLoading.value = true
  progressData.value = null
  try {
    const res = await queryDeployStatus({ ip: queryIp.value })
    progressData.value = res.data
  } catch (e) {
    errorMsg.value = `查询进度失败: ${e.message}`
  } finally {
    progressLoading.value = false
  }
}

/** 提交部署任务 */
async function submitDeployTask() {
  const form = deployForm.value
  if (!form.ip || !form.model_name) {
    ElMessage.warning('请填写 IP 和模型名称')
    return
  }
  deployLoading.value = true
  try {
    const res = await submitDeploy(form)
    if (res.data?.status === 'ACCEPTED') {
      ElMessage.success('部署任务已提交')
      showDeployDialog.value = false
      queryIp.value = form.ip
      // 记录部署 IP，确保进度轮询不依赖 modelInfoMap
      if (!deployedIps.value.includes(form.ip)) deployedIps.value.push(form.ip)
      // 刷新容器列表 + 查一次进度，触发 2 秒轮询
      await refreshStatus()
    } else {
      ElMessage.error(res.data?.error || '提交失败')
    }
  } catch (e) {
    ElMessage.error(`提交部署失败: ${e.message}`)
  } finally {
    deployLoading.value = false
  }
}

/** 从容器名提取端口，构造 API 接口地址 */
function apiEndpoint(row) {
  const parts = row.container_name.split('_FROM72165745_')[0] || ''
  const nameParts = parts.split('_')
  const port = nameParts.pop() || ''
  return port ? `7.216.57.45:${port}` : '-'
}

/** 确认停止模型 */
async function confirmStop(row) {
  // 从容器名解析 model_name 和 port
  // 格式: {model_name}_{port}_FROM72165745_...
  const parts = row.container_name.split('_FROM72165745_')[0] || ''
  const nameParts = parts.split('_')
  const port = nameParts.pop() || ''
  const model_name = nameParts.join('_')

  try {
    await ElMessageBox.confirm(
      `确定停止模型 "${model_name}"（端口: ${port}，IP: ${row.ip}）？`,
      '停止确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    const res = await stopModel({ ip: row.ip, port, model_name })
    if (res.data?.status === 'OK') {
      ElMessage.success('模型已停止')
      refreshStatus()
    } else {
      ElMessage.error(res.data?.error || '停止失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(`停止失败: ${e.message}`)
  }
}

// ===================== 配置管理方法 =====================

/** 加载配置 */
async function loadConfig() {
  configLoading.value = true
  try {
    const res = await modelConfig({ action: 'query' })
    if (res.data?.status === 'OK') {
      configData.value = res.data.data
    } else {
      ElMessage.error(res.data?.error || '加载配置失败')
    }
  } catch (e) {
    ElMessage.error(`加载配置失败: ${e.message}`)
  } finally {
    configLoading.value = false
  }
}

/** 打开编辑 IP 对话框 */
function openEditIp(ip, cfg) {
  editingIp.value = ip
  ipForm.value = {
    ip: ip,
    auth: cfg.auth || '',
    npuinfo: (cfg.npuinfo || []).join(',')
  }
  showAddIpDialog.value = true
}

/** 确认删除 IP */
async function confirmDeleteIp(ip) {
  try {
    await ElMessageBox.confirm(`确定删除 IP "${ip}" 及其所有模型配置？`, '删除确认', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
    })
    const res = await modelConfig({ action: 'delete_ip', ip })
    if (res.data?.status === 'OK') {
      ElMessage.success(`IP ${ip} 已删除`)
      loadConfig()
      refreshStatus()
    } else {
      ElMessage.error(res.data?.error || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(`删除失败: ${e.message}`)
  }
}

/** 保存 IP 配置（新增或修改） */
async function saveIpConfig() {
  if (!ipForm.value.ip || !ipForm.value.auth || !ipForm.value.npuinfo) {
    ElMessage.warning('请填写完整信息')
    return
  }
  ipSaving.value = true
  try {
    const npuArr = ipForm.value.npuinfo.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    if (editingIp.value) {
      const res = await modelConfig({
        action: 'update_ip',
        ip: ipForm.value.ip,
        auth: ipForm.value.auth,
        npuinfo: npuArr
      })
      if (res.data?.status === 'OK') {
        ElMessage.success('IP 配置已更新')
      } else {
        ElMessage.error(res.data?.error || '更新失败')
        return
      }
    } else {
      const res = await modelConfig({
        action: 'add_ip',
        ip: ipForm.value.ip,
        auth: ipForm.value.auth,
        npuinfo: npuArr
      })
      if (res.data?.status === 'OK') {
        ElMessage.success('IP 已添加')
      } else {
        ElMessage.error(res.data?.error || '添加失败')
        return
      }
    }
    showAddIpDialog.value = false
    editingIp.value = ''
    loadConfig()
    refreshStatus()
  } catch (e) {
    ElMessage.error(`保存失败: ${e.message}`)
  } finally {
    ipSaving.value = false
  }
}

/** 打开新增模型对话框 */
function openAddModel(ip) {
  modelIp.value = ip
  editingModelName.value = ''
  modelForm.value = { model_name: '', image_name: '', min_cards: 1, model_path: '', run_cmd: '' }
  showAddModelDialog.value = true
}

/** 打开编辑模型对话框 */
function openEditModel(ip, modelName, mc) {
  modelIp.value = ip
  editingModelName.value = modelName
  modelForm.value = {
    model_name: modelName,
    image_name: mc[0] || '',
    min_cards: mc[1] || 1,
    model_path: mc[2] || '',
    run_cmd: mc[3] || ''
  }
  showAddModelDialog.value = true
}

/** 保存模型配置 */
async function saveModelConfig() {
  const form = modelForm.value
  if (!form.model_name || !form.image_name || !form.model_path || !form.run_cmd) {
    ElMessage.warning('请填写完整模型信息')
    return
  }
  modelSaving.value = true
  try {
    const modelConfigArr = [form.image_name, form.min_cards, form.model_path, form.run_cmd]
    const action = editingModelName.value ? 'update_model' : 'add_model'
    const res = await modelConfig({
      action,
      ip: modelIp.value,
      model_name: form.model_name,
      model_config: modelConfigArr
    })
    if (res.data?.status === 'OK') {
      ElMessage.success(editingModelName.value ? '模型已更新' : '模型已添加')
      showAddModelDialog.value = false
      loadConfig()
    } else {
      ElMessage.error(res.data?.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error(`保存失败: ${e.message}`)
  } finally {
    modelSaving.value = false
  }
}

/** 确认删除模型 */
async function confirmDeleteModel(ip, modelName) {
  try {
    await ElMessageBox.confirm(`确定删除模型 "${modelName}"？`, '删除确认', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning'
    })
    const res = await modelConfig({ action: 'delete_model', ip, model_name: modelName })
    if (res.data?.status === 'OK') {
      ElMessage.success(`模型 ${modelName} 已删除`)
      loadConfig()
    } else {
      ElMessage.error(res.data?.error || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(`删除失败: ${e.message}`)
  }
}

/** 重置部署表单 */
function resetDeployForm() {
  deployForm.value = { ip: '', model_name: '', npunum: '', port: -1, context: 81920, maxreq: 8, runcmd: '' }
}

/** 状态颜色映射 */
function progressTagType(status) {
  const map = { IDLE: 'info', PENDING: 'warning', RUNNING: 'primary', SUCCESS: 'success', FAILED: 'danger' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { IDLE: '空闲', PENDING: '排队中', RUNNING: '部署中', SUCCESS: '已完成', FAILED: '失败' }
  return map[status] || status
}

// ===================== 自动刷新 =====================
const FAST_INTERVAL = 2000     // 有模型部署中 → 2 秒
const SLOW_INTERVAL = 600000   // 全空闲 → 10 分钟

let containerTimer = null      // 容器/空闲卡列表定时器
let progressTimer = null       // 部署进度定时器（有部署任务时独立运行）

function startContainerRefresh(interval) {
  if (containerTimer) clearInterval(containerTimer)
  containerTimer = setInterval(() => refreshStatus(), interval)
}

function stopContainerRefresh() {
  if (containerTimer) { clearInterval(containerTimer); containerTimer = null }
}

function startProgressPolling() {
  if (progressTimer) return  // 已在轮询中
  progressTimer = setInterval(() => checkDeployingStatus(), FAST_INTERVAL)
}

function stopProgressPolling() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
}

// 监听部署中状态，控制进度定时器和容器刷新间隔
watch(hasDeploying, (deploying) => {
  if (deploying) {
    startProgressPolling()
    startContainerRefresh(FAST_INTERVAL)
  } else {
    stopProgressPolling()
    startContainerRefresh(SLOW_INTERVAL)
  }
})

// ===================== 生命周期 =====================
onMounted(() => {
  refreshStatus()
  startContainerRefresh(SLOW_INTERVAL)
})

onUnmounted(() => {
  stopContainerRefresh()
  stopProgressPolling()
})
</script>

<style scoped>
.app-container {
  padding: 20px 24px;
  background-color: #f6f6f8;
  min-height: calc(100vh - 80px);
  box-sizing: border-box;
}

.app-header {
  margin-bottom: 20px;
}
.app-header h1 {
  font-size: 22px;
  margin: 0 0 6px;
  color: #1d2129;
}
.app-header p {
  margin: 0;
  color: #86909c;
  font-size: 14px;
}

.card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.progress-panel {
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
}

/* 配置管理树样式 */
.config-ip-section {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: 12px;
  overflow: hidden;
}

.config-ip-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  font-size: 14px;
}

.config-model-table {
  font-size: 13px;
}

.config-model-row {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
}
.config-model-row:last-child {
  border-bottom: none;
}
.config-model-header {
  background: #f8f9fb;
  font-weight: 600;
  color: #606266;
}

.cfg-name { flex: 2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cfg-img { flex: 2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cfg-card { flex: 0.5; text-align: center; }
.cfg-actions { flex: 1; text-align: right; white-space: nowrap; }

.config-no-model {
  padding: 12px 16px;
  color: #909399;
  font-size: 13px;
  text-align: center;
}
</style>