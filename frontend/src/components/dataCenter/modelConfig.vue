<template>
  <div class="app-container">
    <div class="app-header">
      <h1>模型部署配置管理</h1>
      <p>管理 modelinfo.json 中的服务器 IP、认证信息、NPU 卡及模型配置</p>
    </div>

    <!-- 操作栏 -->
    <div class="card">
      <div class="toolbar">
        <el-button type="primary" @click="refreshConfig" :loading="loading">
          刷新配置
        </el-button>
        <el-button type="success" @click="openAddIpDialog">
          新增服务器 IP
        </el-button>
      </div>
    </div>

    <!-- 错误提示 -->
    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      show-icon
      :closable="true"
      @close="errorMsg = ''"
      style="margin-bottom: 20px;"
    />

    <!-- IP 配置列表 -->
    <div v-if="configData && Object.keys(configData).length" class="card">
      <div v-for="(ipConfig, ip) in configData" :key="ip" class="ip-section">
        <div class="ip-header">
          <div class="ip-title">
            <el-icon><Monitor /></el-icon>
            <span class="ip-text">{{ ip }}</span>
          </div>
          <div class="ip-tags">
            <el-tag type="info" size="small">auth: {{ ipConfig.auth }}</el-tag>
            <el-tag type="warning" size="small">NPU: {{ ipConfig.npuinfo?.join(', ') }}</el-tag>
          </div>
          <div class="ip-actions">
            <el-button size="small" @click="openEditIpDialog(ip, ipConfig)">编辑</el-button>
            <el-button size="small" type="danger" @click="confirmDeleteIp(ip)">删除</el-button>
            <el-button size="small" type="success" @click="openAddModelDialog(ip)">+ 模型</el-button>
          </div>
        </div>

        <!-- 模型列表 -->
        <div v-if="ipConfig.modelinfo && Object.keys(ipConfig.modelinfo).length" class="model-table">
          <div class="model-row model-header">
            <span class="col-name">模型名称</span>
            <span class="col-img">镜像 / 镜像ID</span>
            <span class="col-card">最小卡数</span>
            <span class="col-path">路径</span>
            <span class="col-cmd">启动命令</span>
            <span class="col-actions">操作</span>
          </div>
          <div v-for="(modelConfig, modelName) in ipConfig.modelinfo" :key="modelName" class="model-row">
            <span class="col-name" :title="modelName">{{ modelName }}</span>
            <span class="col-img" :title="modelConfig[0]">{{ modelConfig[0] || '-' }}</span>
            <span class="col-card">{{ modelConfig[1] ?? '-' }}</span>
            <span class="col-path" :title="modelConfig[2]">{{ modelConfig[2] || '-' }}</span>
            <span class="col-cmd" :title="modelConfig[3]">{{ modelConfig[3] ? modelConfig[3].substring(0, 40) + '...' : '-' }}</span>
            <span class="col-actions">
              <el-button size="small" link @click="openEditModelDialog(ip, modelName, modelConfig)">编辑</el-button>
              <el-button size="small" link type="danger" @click="confirmDeleteModel(ip, modelName)">删除</el-button>
            </span>
          </div>
        </div>
        <div v-else class="no-model">
          暂无模型配置
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="card" style="text-align: center; color: #909399; padding: 60px;">
      暂无配置数据，请点击"刷新配置"或"新增服务器 IP"
    </div>

    <!-- ===== 新增/编辑 IP 对话框 ===== -->
    <el-dialog
      v-model="ipDialogVisible"
      :title="isEditingIp ? '编辑服务器 IP' : '新增服务器 IP'"
      width="550px"
      :close-on-click-modal="false"
    >
      <el-form :model="ipForm" label-width="120px" label-position="left">
        <el-form-item label="IP 地址" required>
          <el-input v-model="ipForm.ip" placeholder="例如：10.90.114.59" :disabled="isEditingIp" />
        </el-form-item>
        <el-form-item label="认证密码" required>
          <el-input v-model="ipForm.auth" placeholder="SSH 密码" />
        </el-form-item>
        <el-form-item label="NPU 卡列表" required>
          <el-select v-model="ipForm.npuinfo" multiple placeholder="选择可用 NPU 卡" style="width: 100%;">
            <el-option v-for="n in 8" :key="n - 1" :label="`卡 ${n - 1}`" :value="n - 1" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ipDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitIpForm" :loading="ipSubmitting">确认</el-button>
      </template>
    </el-dialog>

    <!-- ===== 新增/编辑模型对话框 ===== -->
    <el-dialog
      v-model="modelDialogVisible"
      :title="isEditingModel ? '编辑模型' : '新增模型'"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form :model="modelForm" label-width="120px" label-position="left">
        <el-form-item label="所属 IP">
          <el-input :model-value="modelForm.ip" disabled />
        </el-form-item>
        <el-form-item label="模型名称" required>
          <el-input v-model="modelForm.model_name" placeholder="例如：Qwen3-72B" :disabled="isEditingModel" />
        </el-form-item>
        <el-form-item label="镜像 / 镜像ID" required>
          <el-input v-model="modelForm.image_name" placeholder="镜像ID（如 0fa7e4550d22）" />
        </el-form-item>
        <el-form-item label="最小卡数" required>
          <el-input-number v-model="modelForm.min_cards" :min="1" :max="8" />
        </el-form-item>
        <el-form-item label="模型路径" required>
          <el-input v-model="modelForm.model_math" placeholder="例如：/data/z00659899/Qwen3-72B" />
        </el-form-item>
        <el-form-item label="启动命令" required>
          <el-input
            v-model="modelForm.runcmd"
            type="textarea"
            :rows="3"
            placeholder="例如：serve {model_math} --port {port} ..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitModelForm" :loading="modelSubmitting">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Monitor } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { modelConfig } from '@/api/deployApi.js'

const loading = ref(false)
const errorMsg = ref('')
const configData = ref<any>(null)

// IP 对话框
const ipDialogVisible = ref(false)
const isEditingIp = ref(false)
const ipSubmitting = ref(false)
const ipForm = ref({
  ip: '',
  auth: '',
  npuinfo: [] as number[]
})

// 模型对话框
const modelDialogVisible = ref(false)
const isEditingModel = ref(false)
const modelSubmitting = ref(false)
const modelForm = ref({
  ip: '',
  model_name: '',
  image_name: '',
  min_cards: 1,
  model_math: '',
  runcmd: ''
})

async function refreshConfig() {
  loading.value = true
  errorMsg.value = ''
  try {
    const resp = await modelConfig({ action: 'query' })
    if (resp.data.status === 'OK') {
      configData.value = resp.data.data
    } else {
      errorMsg.value = resp.data.error || '查询配置失败'
    }
  } catch (err: any) {
    errorMsg.value = '查询配置失败：' + (err.response?.data?.error || err.message)
  } finally {
    loading.value = false
  }
}

function openAddIpDialog() {
  isEditingIp.value = false
  ipForm.value = { ip: '', auth: '', npuinfo: [] }
  ipDialogVisible.value = true
}

function openEditIpDialog(ip: string, ipConfig: any) {
  isEditingIp.value = true
  ipForm.value = {
    ip,
    auth: ipConfig.auth || '',
    npuinfo: ipConfig.npuinfo || []
  }
  ipDialogVisible.value = true
}

async function submitIpForm() {
  const { ip, auth, npuinfo } = ipForm.value
  if (!ip || !auth || !npuinfo.length) {
    ElMessage({ type: 'warning', message: '请填写完整信息' })
    return
  }
  ipSubmitting.value = true
  try {
    const action = isEditingIp.value ? 'update_ip' : 'add_ip'
    const resp = await modelConfig({ action, ip, auth, npuinfo })
    if (resp.data.status === 'OK') {
      ElMessage({ type: 'success', message: resp.data.message })
      ipDialogVisible.value = false
      await refreshConfig()
    } else {
      ElMessage({ type: 'error', message: resp.data.error || '操作失败' })
    }
  } catch (err: any) {
    ElMessage({ type: 'error', message: err.response?.data?.error || err.message })
  } finally {
    ipSubmitting.value = false
  }
}

function confirmDeleteIp(ip: string) {
  ElMessageBox.confirm(`确定要删除 IP ${ip} 及其所有模型配置吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const resp = await modelConfig({ action: 'delete_ip', ip })
      if (resp.data.status === 'OK') {
        ElMessage({ type: 'success', message: resp.data.message })
        await refreshConfig()
      } else {
        ElMessage({ type: 'error', message: resp.data.error || '删除失败' })
      }
    } catch (err: any) {
      ElMessage({ type: 'error', message: err.response?.data?.error || err.message })
    }
  }).catch(() => {})
}

function openAddModelDialog(ip: string) {
  isEditingModel.value = false
  modelForm.value = {
    ip,
    model_name: '',
    image_name: '',
    min_cards: 1,
    model_math: '',
    runcmd: ''
  }
  modelDialogVisible.value = true
}

function openEditModelDialog(ip: string, modelName: string, modelConfig: any[]) {
  isEditingModel.value = true
  modelForm.value = {
    ip,
    model_name: modelName,
    image_name: modelConfig[0] || '',
    min_cards: modelConfig[1] ?? 1,
    model_math: modelConfig[2] || '',
    runcmd: modelConfig[3] || ''
  }
  modelDialogVisible.value = true
}

async function submitModelForm() {
  const { ip, model_name, image_name, min_cards, model_math, runcmd } = modelForm.value
  if (!model_name || !image_name) {
    ElMessage({ type: 'warning', message: '请填写模型名称和镜像ID' })
    return
  }
  modelSubmitting.value = true
  try {
    const action = isEditingModel.value ? 'update_model' : 'add_model'
    const model_config = [image_name, min_cards, model_math, runcmd]
    const resp = await modelConfig({ action, ip, model_name, model_config })
    if (resp.data.status === 'OK') {
      ElMessage({ type: 'success', message: resp.data.message })
      modelDialogVisible.value = false
      await refreshConfig()
    } else {
      ElMessage({ type: 'error', message: resp.data.error || '操作失败' })
    }
  } catch (err: any) {
    ElMessage({ type: 'error', message: err.response?.data?.error || err.message })
  } finally {
    modelSubmitting.value = false
  }
}

function confirmDeleteModel(ip: string, modelName: string) {
  ElMessageBox.confirm(`确定要删除模型 ${modelName} 吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      const resp = await modelConfig({ action: 'delete_model', ip, model_name: modelName })
      if (resp.data.status === 'OK') {
        ElMessage({ type: 'success', message: resp.data.message })
        await refreshConfig()
      } else {
        ElMessage({ type: 'error', message: resp.data.error || '删除失败' })
      }
    } catch (err: any) {
      ElMessage({ type: 'error', message: err.response?.data?.error || err.message })
    }
  }).catch(() => {})
}

onMounted(() => {
  refreshConfig()
})
</script>

<style scoped>
.app-container {
  max-width: 1100px;
  margin: 40px auto;
  padding: 0 20px;
}
.app-header {
  text-align: center;
  margin-bottom: 30px;
}
.app-header h1 {
  font-size: 24px;
  color: #303133;
}
.app-header p {
  color: #909399;
  font-size: 14px;
}
.card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  padding: 24px;
  margin-bottom: 20px;
}
.toolbar {
  display: flex;
  gap: 12px;
}
.ip-section {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  margin-bottom: 16px;
  overflow: hidden;
}
.ip-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  flex-wrap: wrap;
}
.ip-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.ip-text {
  font-family: monospace;
  font-size: 14px;
}
.ip-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.ip-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.model-table {
  font-size: 13px;
}
.model-row {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  border-bottom: 1px solid #f2f2f2;
  gap: 8px;
}
.model-row:last-child {
  border-bottom: none;
}
.model-header {
  background: #fafafa;
  font-weight: 600;
  color: #606266;
  font-size: 12px;
}
.col-name { flex: 1.5; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-img { flex: 1.5; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-card { flex: 0.5; text-align: center; }
.col-path { flex: 2; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-cmd { flex: 2.5; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-actions { flex: 1; text-align: right; white-space: nowrap; }
.no-model {
  padding: 16px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>