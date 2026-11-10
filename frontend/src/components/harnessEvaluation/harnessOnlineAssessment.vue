<!-- harness 在线评估：harness-bench 的任务枚举、发起运行、运行历史与日志 -->
<template>
  <div class="hv-wrap">
    <div class="hv-head">
      <div>
        <h2 class="hv-title">harness 在线评估</h2>
        <p class="hv-sub">
          基于 harness-bench（固定 harness 镜像 + 挂载任务数据）。当前仓库：
          <code>{{ catalog.repo || '-' }}</code>
          <el-tag v-if="catalog.repo_ready" type="success" size="small" effect="plain">工程就绪</el-tag>
          <el-tag v-else type="danger" size="small" effect="plain">工程缺失</el-tag>
        </p>
      </div>
      <el-button size="small" :loading="loadingCatalog" @click="loadCatalog">刷新</el-button>
    </div>

    <el-row :gutter="12">
      <el-col :span="14">
        <el-card shadow="never" class="hv-card">
          <template #header><span class="hv-card-title">发起运行</span></template>
          <el-form label-width="96px" size="small">
            <el-form-item label="任务">
              <el-select v-model="form.task_id" filterable allow-create default-first-option
                         placeholder="选择或输入 task id" style="width:100%">
                <el-option v-for="t in catalog.tasks" :key="t.id" :label="t.id" :value="t.id">
                  <span>{{ t.id }}</span>
                  <span class="hv-opt-meta">{{ t.category }}</span>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="harness">
              <el-select v-model="form.harness" style="width:100%" placeholder="选择被测 harness">
                <el-option v-for="h in catalog.harnesses" :key="h.id" :value="h.id" :label="h.id">
                  <span>{{ h.id }}</span>
                  <span class="hv-opt-meta">{{ h.image_ready ? '镜像就绪' : '镜像未构建' }}</span>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="模型">
              <el-input v-model="form.model" placeholder="如 deepseek-flash" />
            </el-form-item>
            <el-form-item label="base_url">
              <el-input v-model="form.model_base_url" placeholder="如 https://api.deepseek.com/v1" />
            </el-form-item>
            <el-form-item label="api_key">
              <el-input v-model="form.model_api_key" type="password" show-password
                        placeholder="仅写入运行目录 600 权限文件，不落库" />
            </el-form-item>
            <el-form-item label="并发">
              <el-input-number v-model="form.workers" :min="1" :max="32" size="small" />
              <span class="hv-hint">workers</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="submitting" @click="submit">开始运行</el-button>
              <span v-if="!catalog.repo_ready" class="hv-hint">工程未就绪时无法发起</span>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never" class="hv-card">
          <template #header><span class="hv-card-title">可用组件</span></template>
          <p class="hv-line">任务数：<b>{{ catalog.task_count || 0 }}</b></p>
          <p class="hv-line">grader 镜像：
            <el-tag :type="catalog.grader && catalog.grader.image_ready ? 'success' : 'info'" size="small" effect="plain">
              {{ catalog.grader && catalog.grader.image_ready ? '已构建' : '未构建' }}
            </el-tag>
          </p>
          <div class="hv-chips">
            <el-tag v-for="h in catalog.harnesses" :key="h.id" size="small"
                    :type="h.image_ready ? 'success' : 'info'" effect="plain" class="hv-chip">
              {{ h.id }}
            </el-tag>
            <span v-if="!catalog.harnesses.length" class="hv-hint">未发现 docker/harnesses</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="hv-card hv-card-table">
      <template #header>
        <span class="hv-card-title">运行记录</span>
        <el-button size="small" text @click="loadRuns">刷新</el-button>
      </template>
      <el-table :data="runs" size="small" stripe @row-click="openRun" style="width:100%">
        <el-table-column prop="id" label="运行 ID" min-width="200" />
        <el-table-column prop="task_id" label="任务" min-width="180" show-overflow-tooltip />
        <el-table-column prop="harness" label="harness" width="120" />
        <el-table-column prop="model" label="模型" width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="96" align="center">
          <template #default="scope">
            <el-tag size="small" :type="statusType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="190" />
      </el-table>
      <div v-if="!runs.length" class="hv-empty">还没有运行记录</div>
    </el-card>

    <el-drawer v-model="drawer" :title="current.id || '运行详情'" size="62%">
      <div class="hv-detail" v-if="current.id">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="状态">{{ current.status }}</el-descriptions-item>
          <el-descriptions-item label="任务">{{ current.task_id }}</el-descriptions-item>
          <el-descriptions-item label="harness">{{ current.harness }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ current.model }}</el-descriptions-item>
          <el-descriptions-item label="退出码">{{ current.exit_code ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="结果目录">{{ current.run_root || '-' }}</el-descriptions-item>
        </el-descriptions>
        <div class="hv-log-head">
          <span>运行日志（尾部）</span>
          <span>
            <el-button size="small" text @click="pollRun">刷新</el-button>
            <el-button v-if="current.status === 'running'" size="small" text type="danger" @click="stopRun">停止</el-button>
          </span>
        </div>
        <pre class="hv-log">{{ current.log_tail || '（暂无日志）' }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/blue/api'

const catalog = ref({ tasks: [], harnesses: [], grader: {} })
const runs = ref([])
const loadingCatalog = ref(false)
const submitting = ref(false)
const drawer = ref(false)
const current = ref({})
let timer = null

const form = reactive({
  task_id: '',
  harness: '',
  model: 'deepseek-flash',
  model_base_url: 'https://api.deepseek.com/v1',
  model_api_key: '',
  workers: 1,
})

function statusType(status) {
  return { running: 'warning', finished: 'success', failed: 'danger', stopped: 'info' }[status] || 'info'
}

async function loadCatalog() {
  loadingCatalog.value = true
  try {
    catalog.value = await api.get('/harness-eval/catalog')
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    loadingCatalog.value = false
  }
}

async function loadRuns() {
  try {
    const data = await api.get('/harness-eval/runs')
    runs.value = data.runs || []
  } catch (e) {
    /* ignore */
  }
}

async function submit() {
  if (!form.task_id || !form.harness || !form.model || !form.model_base_url) {
    ElMessage.warning('任务 / harness / 模型 / base_url 都需要填写')
    return
  }
  submitting.value = true
  try {
    const run = await api.post('/harness-eval/runs', { ...form })
    ElMessage.success(`已发起运行 ${run.id}`)
    await loadRuns()
    openRun(run)
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    submitting.value = false
  }
}

async function openRun(row) {
  drawer.value = true
  current.value = { ...row }
  await pollRun()
}

async function pollRun() {
  if (!current.value.id) return
  try {
    current.value = await api.get(`/harness-eval/runs/${current.value.id}`)
  } catch (e) {
    /* ignore */
  }
}

async function stopRun() {
  try {
    await api.post(`/harness-eval/runs/${current.value.id}/stop`)
    ElMessage.success('已请求停止')
    await pollRun()
    await loadRuns()
  } catch (e) {
    /* ignore */
  }
}

onMounted(async () => {
  await Promise.all([loadCatalog(), loadRuns()])
  timer = setInterval(async () => {
    if (current.value.id && current.value.status === 'running') await pollRun()
    if (runs.value.some((r) => r.status === 'running')) await loadRuns()
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.hv-wrap { padding: 16px 20px 28px; }
.hv-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.hv-title { margin: 0; font-size: 18px; font-weight: 600; }
.hv-sub { margin: 6px 0 0; font-size: 12px; color: #6b7280; }
.hv-sub code { background: #f3f4f6; padding: 1px 6px; border-radius: 4px; }
.hv-card { margin-bottom: 12px; }
.hv-card-title { font-weight: 600; }
.hv-card-table :deep(.el-card__header) { display: flex; justify-content: space-between; align-items: center; }
.hv-line { margin: 4px 0; font-size: 13px; }
.hv-hint { margin-left: 8px; font-size: 12px; color: #9ca3af; }
.hv-chips { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.hv-chip { cursor: default; }
.hv-opt-meta { float: right; color: #9ca3af; font-size: 12px; margin-left: 12px; }
.hv-empty { text-align: center; color: #9ca3af; padding: 18px 0; font-size: 13px; }
.hv-detail { padding: 0 4px; }
.hv-log-head { display: flex; justify-content: space-between; align-items: center; margin: 14px 0 6px; font-size: 13px; }
.hv-log { background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 6px;
          max-height: 520px; overflow: auto; font-size: 12px; line-height: 1.55; white-space: pre-wrap; }
</style>
