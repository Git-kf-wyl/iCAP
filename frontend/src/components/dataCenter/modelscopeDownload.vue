<template>
  <div class="app-container">
    <div class="app-header">
      <h1>ModelScope Download Server</h1>
      <p>输入 ModelScope 仓库链接，下载公开文件并保存到当前账号的资源库（单次最多 2 GiB）</p>
    </div>

    <!-- 输入区域 -->
    <div class="card">
      <div class="url-row">
        <div class="url-input">
          <el-input
            v-model="msUrl"
            placeholder="请输入 ModelScope 链接，例如：https://modelscope.cn/datasets/AI-ModelScope/climbmix-400b-shuffle"
            clearable
            :disabled="loading"
            @keyup.enter="fetchFiles"
          >
            <template #prepend>MS URL</template>
          </el-input>
        </div>
        <div class="limit-select">
          <el-select v-model="maxFiles" placeholder="下载数量" :disabled="loading" @change="onMaxFilesChange">
            <el-option label="全部下载" value="full" />
            <el-option label="1 个文件" value="1" />
            <el-option label="2 个文件" value="2" />
            <el-option label="5 个文件" value="5" />
            <el-option label="10 个文件" value="10" />
            <el-option label="20 个文件" value="20" />
            <el-option label="序号范围" value="range" />
          </el-select>
        </div>
        <el-button type="primary" @click="fetchFiles" :loading="loading" :disabled="!msUrl.trim()">
          获取文件列表
        </el-button>
      </div>
    </div>

    <!-- 文件信息区域 -->
    <div v-if="fileInfo" class="card">
      <h3 style="margin: 0 0 12px; font-size: 16px; color: #303133;">
        仓库信息
        <el-tag v-if="fileInfo.repo_type === 'dataset'" type="warning" size="small" class="status-tag">Dataset</el-tag>
        <el-tag v-else type="primary" size="small" class="status-tag">Model</el-tag>
      </h3>
      <div class="info-grid">
        <span class="label">仓库名称：</span>
        <span class="value">{{ fileInfo.repo_name }}</span>
        <span class="label">文件总数：</span>
        <span class="value">{{ fileInfo.total_count }} 个</span>
        <span class="label">本次操作：</span>
        <span class="value">{{ displayFileList.length }} 个文件（共 {{ fileInfo.total_count }} 个）</span>
      </div>

      <!-- 序号范围筛选条 -->
      <div v-if="maxFiles === 'range'" class="range-bar">
        <span class="range-label">文件序号范围：</span>
        <input v-model.number="rangeStart" class="range-num" placeholder="起始序号" type="number" min="1" />
        <span class="range-sep">—</span>
        <input v-model.number="rangeEnd" class="range-num" placeholder="终止序号" type="number" min="1" />
        <el-tag type="info" size="small" effect="plain">1 ~ {{ fileInfo.total_count }}</el-tag>
      </div>

      <!-- 文件列表 -->
      <div v-if="displayFileList.length" class="file-list">
        <div v-for="(f, idx) in displayFileList.slice(0, 200)" :key="idx" class="file-item">
          <span class="file-index">{{ fileInfo.files_list.indexOf(f) + 1 }}.</span>
          <span class="file-name">{{ f }}</span>
          <span v-if="displayFileSizeList[idx] !== undefined" class="file-size">
            {{ (displayFileSizeList[idx] / (1024 * 1024)).toFixed(2) }} MB
          </span>
        </div>
        <div v-if="displayFileList.length > 200" class="file-item" style="color: #909399; text-align: center;">
          ... 仅显示前 200 个，共 {{ displayFileList.length }} 个文件
        </div>
      </div>

      <div class="btn-group">
        <el-button type="success" @click="startDownload" :loading="downloading" :disabled="!canDownload">
          开始下载
        </el-button>
      </div>

      <!-- 下载进度 -->
      <div v-if="downloading || downloadResult" class="progress-section">
        <el-alert
          v-if="downloading"
          title="下载中..."
          type="info"
          show-icon
          :closable="false"
        >
          <template #default>
            <div style="margin-top: 8px;">
              <el-progress
                :percentage="downloadTotal > 0 ? Math.round(liveDownloadedFiles.length / downloadTotal * 100) : 0"
                :stroke-width="12"
              />
              <div style="font-size: 13px; color: #909399; margin-top: 6px;">
                已完成 {{ liveDownloadedFiles.length }} / {{ downloadTotal }} 个文件
              </div>
            </div>
          </template>
        </el-alert>
        <el-alert
          v-if="downloadResult && !downloading"
          :title="downloadResult.fail_count > 0 ? `下载完成（${downloadResult.success_count} 成功，${downloadResult.fail_count} 失败）` : '下载完成'"
          :type="downloadResult.fail_count > 0 ? 'warning' : 'success'"
          show-icon
          :closable="false"
        />
        <div v-if="liveDownloadedFiles.length" class="file-list">
          <div v-for="(f, idx) in liveDownloadedFiles" :key="'dl-' + idx" class="file-item">
            ✅ {{ f }}
          </div>
        </div>
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

    <!-- 保存到资源库弹窗 -->
    <el-dialog v-model="uploadDialogVisible" title="保存到资源库" width="420px" :close-on-click-modal="false">
      <div class="upload-dialog-content">
        <p>是否将本次下载的文件纳入资源库？</p><el-switch v-model="shareResource" active-text="对所有用户开放" inactive-text="仅自己可见" />
        <p class="sub-text">共 {{ downloadResult?.downloaded_files?.length || 0 }} 个文件</p>
      </div>
      <template #footer>
        <el-button @click="uploadDialogVisible = false; uploadAfterDownload = false">取消</el-button>
        <el-button type="primary" @click="confirmUpload" :loading="uploading">确认保存</el-button>
      </template>
    </el-dialog>

    <!-- 保存结果 -->
    <el-dialog v-model="uploadResultVisible" title="保存结果" width="500px">
      <el-alert
        v-if="uploadResult"
        :title="`保存完成：${uploadResult.success_count} 成功，${uploadResult.fail_count} 失败`"
        :type="uploadResult.fail_count > 0 ? 'warning' : 'success'"
        show-icon
        :closable="false"
      />
      <div v-if="uploadResult?.dataset_id" style="margin-top:12px"><el-button type="primary" @click="$router.push('/datasets/manage')">管理资源与下载文件</el-button></div>
      <template #footer>
        <el-button @click="uploadResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import axios from 'axios'
import { API_BASE_URL } from "@/utils/Constants.js";

const API_BASE = API_BASE_URL

const shareResource = ref(false)

function validateAndNormalizeUrl(url: string): { valid: boolean; url?: string; error?: string } {
  url = url.trim()
  if (!url) return { valid: false, error: '链接不能为空' }

  if (!url.includes('modelscope.cn')) {
    return { valid: false, error: '链接必须包含 modelscope.cn' }
  }

  const parsed = new URL(url)
  /* if (!parsed.pathname.includes('/tree/main') && !parsed.pathname.includes('/tree/')) {
    url = url.replace(/\/$/, '') + '/tree/main'
  } */

  return { valid: true, url }
}

const msUrl = ref('')
const maxFiles = ref('full')
const rangeStart = ref<number | null>(null)
const rangeEnd = ref<number | null>(null)
const loading = ref(false)
const downloading = ref(false)
const uploading = ref(false)
const errorMsg = ref('')

const fileInfo = ref<any>(null)
const downloadResult = ref<any>(null)
const uploadResult = ref<any>(null)

const uploadDialogVisible = ref(false)
const uploadResultVisible = ref(false)
const uploadAfterDownload = ref(false)

/** 根据当前下拉框模式 + 序号范围，计算出实际要操作的 files_list */
const displayFileList = computed(() => {
  if (!fileInfo.value || !fileInfo.value.files_list) return []
  const all = fileInfo.value.files_list
  if (maxFiles.value === 'range') {
    const s = String(rangeStart.value ?? '').trim()
    const e = String(rangeEnd.value ?? '').trim()
    const start = s ? Math.max(1, parseInt(s, 10)) : 1
    const end = e ? Math.min(all.length, parseInt(e, 10)) : all.length
    if (start > end) return []
    return all.slice(start - 1, end)
  }
  if (maxFiles.value !== 'full') {
    const limit = parseInt(maxFiles.value, 10)
    if (!isNaN(limit) && limit > 0) {
      return all.slice(0, limit)
    }
  }
  return all
})

/** 根据当前下拉框模式，计算出对应的 files_len_list 子集 */
const displayFileSizeList = computed(() => {
  if (!fileInfo.value || !fileInfo.value.files_len_list) return []
  const all = fileInfo.value.files_len_list
  if (maxFiles.value === 'range') {
    const s = String(rangeStart.value ?? '').trim()
    const e = String(rangeEnd.value ?? '').trim()
    const start = s ? Math.max(1, parseInt(s, 10)) : 1
    const end = e ? Math.min(all.length, parseInt(e, 10)) : all.length
    if (start > end) return []
    return all.slice(start - 1, end)
  }
  if (maxFiles.value !== 'full') {
    const limit = parseInt(maxFiles.value, 10)
    if (!isNaN(limit) && limit > 0) {
      return all.slice(0, limit)
    }
  }
  return all
})

const canDownload = computed(() => displayFileList.value.length > 0)

function onMaxFilesChange(val: string) {
  if (val !== 'range') {
    rangeStart.value = null
    rangeEnd.value = null
  }
}

async function fetchFiles() {
  const validation = validateAndNormalizeUrl(msUrl.value)
  if (!validation.valid) {
    errorMsg.value = validation.error!
    return
  }
  msUrl.value = validation.url!
  errorMsg.value = ''
  downloadResult.value = null
  uploadResult.value = null

  loading.value = true
  try {
    const resp = await axios.get(`${API_BASE}ms_download/files_info`, {
      params: { url: msUrl.value, max_files: 'full' }
    })
    if (resp.data.status === 'success') {
      fileInfo.value = resp.data
    } else {
      errorMsg.value = resp.data.message || '获取文件列表失败'
    }
  } catch (err: any) {
    errorMsg.value = '获取文件列表失败：' + (err.response?.data?.message || err.message)
  } finally {
    loading.value = false
  }
}

// 实时下载状态
const liveDownloadedFiles = ref<string[]>([])
const downloadTotal = ref(0)
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const downloadTaskId = ref('')

onUnmounted(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
})

async function startDownload() {
  if (!fileInfo.value) return
  errorMsg.value = ''
  downloadResult.value = null
  liveDownloadedFiles.value = []
  downloadTotal.value = 0

  downloading.value = true
  try {
    const resp = await axios.post(`${API_BASE}ms_download/download_files`, {
      url: msUrl.value,
      repo_type: fileInfo.value.repo_type,
      repo_name: fileInfo.value.repo_name,
      files_list: displayFileList.value,
      files_len_list: displayFileSizeList.value
    })
    if (resp.data.status === 'success') {
      downloadTaskId.value = resp.data.task_id
      downloadTotal.value = resp.data.total
      pollTimer.value = setInterval(pollDownloadStatus, 2000)
    } else {
      errorMsg.value = resp.data.message || '启动下载失败'
      downloading.value = false
    }
  } catch (err: any) {
    errorMsg.value = '启动下载失败：' + (err.response?.data?.message || err.message)
    downloading.value = false
  }
}

async function pollDownloadStatus() {
  if (!downloadTaskId.value) return
  try {
    const resp = await axios.get(`${API_BASE}ms_download/download_status`, {
      params: { task_id: downloadTaskId.value }
    })
    if (resp.data.status === 'success') {
      liveDownloadedFiles.value = resp.data.downloaded_files || []

      if (resp.data.task_status === 'completed') {
        if (pollTimer.value) {
          clearInterval(pollTimer.value)
          pollTimer.value = null
        }
        downloading.value = false
        downloadResult.value = {
          downloaded_files: resp.data.downloaded_files || [],
          failed_files: resp.data.failed_files || [],
          download_path: resp.data.download_path || '',
          backup_folder_path: resp.data.backup_folder_path || '',
          total: resp.data.total,
          success_count: (resp.data.downloaded_files || []).length,
          fail_count: (resp.data.failed_files || []).length
        }
        if (resp.data.downloaded_files && resp.data.downloaded_files.length > 0) {
          uploadDialogVisible.value = true
        }
      } else if (resp.data.task_status === 'failed') {
        if (pollTimer.value) {
          clearInterval(pollTimer.value)
          pollTimer.value = null
        }
        downloading.value = false
        errorMsg.value = resp.data.error || '下载任务异常失败'
      }
    }
  } catch (err) {
    console.warn('轮询下载状态失败：', err)
  }
}

async function confirmUpload() {
  uploadDialogVisible.value = false
  if (!downloadResult.value) return

  uploading.value = true
  try {
    const resp = await axios.post(`${API_BASE}ms_download/upload_files`, {
      repo_type: fileInfo.value.repo_type,
      repo_name: fileInfo.value.repo_name,
      backup_folder_path: downloadResult.value.backup_folder_path, visibility: shareResource.value ? 'public' : 'private'
    })
    if (resp.data.status === 'success') {
      uploadResult.value = resp.data
      uploadResultVisible.value = true
    } else {
      errorMsg.value = resp.data.message || '上传失败'
    }
  } catch (err: any) {
    errorMsg.value = '上传失败：' + (err.response?.data?.message || err.message)
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
body {
  margin: 0;
  background: #f5f7fa;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.app-container {
  max-width: 900px;
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
.url-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.url-row :deep(.url-input) {
  flex: 1;
}
.url-row :deep(.limit-select) {
  width: 130px;
  flex-shrink: 0;
}
.range-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
.range-bar .range-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}
.range-bar .range-num {
  width: 110px;
  height: 32px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 12px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
  text-align: center;
}
.range-bar .range-num:focus {
  border-color: #409eff;
}
.range-bar .range-sep {
  color: #909399;
  font-size: 14px;
}
.info-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 16px;
  margin-top: 12px;
}
.info-grid .label {
  color: #909399;
  font-size: 13px;
}
.info-grid .value {
  color: #303133;
  font-size: 13px;
  word-break: break-all;
}
.file-list {
  margin-top: 12px;
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 12px;
}
.file-item {
  font-size: 12px;
  color: #606266;
  padding: 2px 0;
  border-bottom: 1px solid #f2f2f2;
}
.file-item:last-child {
  border-bottom: none;
}
.file-item .file-index {
  color: #909399;
  margin-right: 6px;
}
.file-item .file-name {
  color: #606266;
}
.file-item .file-size {
  color: #909399;
  font-size: 11px;
  margin-left: 8px;
}
.progress-section {
  margin-top: 16px;
}
.result-section {
  margin-top: 16px;
}
.btn-group {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
.status-tag {
  margin-left: 8px;
}
.upload-dialog-content {
  text-align: center;
}
.upload-dialog-content p {
  font-size: 16px;
  margin-bottom: 8px;
}
.upload-dialog-content .sub-text {
  font-size: 13px;
  color: #909399;
}

@media (max-width: 640px) {
  .url-row {
    flex-direction: column;
  }
  .url-row :deep(.limit-select) {
    width: 100%;
  }
}
</style>