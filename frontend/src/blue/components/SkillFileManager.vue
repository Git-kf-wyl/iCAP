<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, downloadFile } from '../api'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, selectable: Boolean, compact: Boolean, textOnly: Boolean, allowUse: { type: Boolean, default: true } })
const emit = defineEmits(['update:modelValue', 'use'])
const items = ref([]), loading = ref(false), uploading = ref(false), filter = ref(''), folder = ref(''), limits = ref({})
const page = ref(1)
const folders = computed(() => items.value.filter(f => f.kind === 'directory'))
const shown = computed(() => items.value.filter(f => (!folder.value || f.id === folder.value || f.parent_id === folder.value) && (!filter.value || `${f.name} ${f.relative_path} ${f.path}`.toLowerCase().includes(filter.value.toLowerCase()))).sort((a,b) => a.path.localeCompare(b.path)))
const pageRows = computed(() => shown.value.slice((page.value - 1) * 50, page.value * 50))
watch([filter, folder], () => { page.value = 1 })
const size = (n) => n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(0, Math.round(n / 1024))} KB`
async function load() {
  loading.value = true
  try { const data = await api.get('/skill-evolution/files'); items.value = data.items || []; limits.value = data.limits || {} }
  catch { /* API displays the failure; preserve the last list */ }
  finally { loading.value = false }
}
function select(row, checked) {
  if (props.textOnly && !isText(row)) return
  emit('update:modelValue', checked ? [...new Set([...props.modelValue, row.id])] : props.modelValue.filter(id => id !== row.id))
}
async function upload(event) {
  uploading.value = true
  const added = []
  try {
    for (const file of event.target.files) {
      if (file.size > (limits.value.upload_bytes || 90 * 1024 * 1024)) throw new Error(`${file.name} 超过单次上传上限`)
      const body = new FormData(); body.append('file', file)
      const result = await api.post('/skill-evolution/files/upload', body, { timeout: 300000 })
      added.push(...result.items.filter(item => item.kind !== 'directory' && (!props.textOnly || isText(item))).map(item => item.id))
    }
    ElMessage.success('已保存至服务器；ZIP 内目录结构保持不变')
  } catch (error) { if (!error.response) ElMessage.error(error.message || '文件上传失败') }
  finally {
    if (props.selectable) emit('update:modelValue', [...new Set([...props.modelValue, ...added])])
    event.target.value = ''; uploading.value = false; await load()
  }
}
async function copy(path) {
  try { await navigator.clipboard.writeText(path); ElMessage.success('服务器路径已复制') }
  catch { ElMessage.info('浏览器未允许自动复制，请选中路径文字后复制') }
}
async function use(row, kind) {
  try {
    const data = await api.get(`/skill-evolution/files/${row.id}/content`)
    select(row, true); emit('use', { ...data, id: row.id, kind })
  } catch { /* API shows error */ }
}
async function remove(row) {
  try { await ElMessageBox.confirm(`删除“${row.name}”${row.kind === 'directory' ? '及其所有文件' : ''}？已有任务保存的输入副本不受影响。`, '删除文件', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) }
  catch { return }
  await api.delete(`/skill-evolution/files/${row.id}`)
  const ids = items.value.filter(f => f.id === row.id || f.parent_id === row.id).map(f => f.id)
  emit('update:modelValue', props.modelValue.filter(id => !ids.includes(id)))
  if (folder.value === row.id) folder.value = ''
  await load()
}
async function download(row) {
  try { await downloadFile(`/skill-evolution/files/${row.id}/download`, row.name) }
  catch (error) { ElMessage.error(error.message) }
}
const isText = row => /\.(md|txt|json|jsonl|csv|tsv|py|js|sh|ya?ml)$/i.test(row.name)
onMounted(load)
</script>

<template>
  <div class="file-manager" :class="{ compact }" v-loading="loading">
    <div class="file-toolbar">
      <div><strong>服务器文件库</strong><p>文件私有保存。上传 ZIP 后可逐项查看路径，将所需路径粘贴到用例的 input_path 或 onlyllm.data。</p></div>
      <label class="upload-button" :class="{ disabled: uploading }">{{ uploading ? '上传中…' : '＋ 上传文件 / ZIP' }}<input type="file" multiple :disabled="uploading" accept=".zip,.md,.txt,.json,.jsonl,.csv,.tsv,.xlsx,.xls,.pdf,.docx,.py,.js,.sh,.yaml,.yml" @change="upload" /></label>
    </div>
    <div class="file-filters"><el-input v-model="filter" clearable placeholder="搜索文件名或服务器路径" /><el-select v-model="folder" clearable placeholder="所有上传目录"><el-option v-for="f in folders" :key="f.id" :label="`${f.name} · ${f.id.slice(-6)}`" :value="f.id" /></el-select><el-button @click="load">刷新</el-button></div>
    <p class="file-hint">单次上传 {{ size(limits.upload_bytes || 94371840) }}；ZIP 解压后最多 {{ size(limits.expanded_bytes || 1073741824) }}。{{ selectable ? `已关联 ${modelValue.length} 个文件，运行前会保存任务副本。` : '上传文件不会自动启动任务或执行脚本。' }}</p>
    <el-table :data="pageRows" :max-height="compact ? 320 : 600" empty-text="还没有文件。上传 Skill、JSON 用例、Rubric 或工作簿 ZIP 开始使用。" row-key="id">
      <el-table-column v-if="selectable" width="46"><template #default="{row}"><el-checkbox v-if="row.kind !== 'directory'" :model-value="modelValue.includes(row.id)" :disabled="textOnly && !isText(row)" :aria-label="`关联 ${row.name}`" @change="select(row,$event)" /></template></el-table-column>
      <el-table-column label="文件 / 目录" min-width="180"><template #default="{row}"><div class="file-name">{{ row.kind === 'directory' ? '▤' : '▧' }} {{ row.relative_path || row.name }}</div><small>{{ row.kind === 'directory' ? '上传目录' : size(row.size) }}</small></template></el-table-column>
      <el-table-column label="服务器绝对路径" min-width="270"><template #default="{row}"><code class="server-path">{{ row.path }}</code><el-button link type="primary" @click="copy(row.path)">复制路径</el-button></template></el-table-column>
      <el-table-column label="操作" :width="selectable ? 230 : 130"><template #default="{row}"><el-dropdown v-if="selectable && allowUse && row.kind !== 'directory' && isText(row)" trigger="click" @command="use(row,$event)"><el-button link type="primary">用作输入 ▾</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item command="dataset">优化用例 JSON</el-dropdown-item><el-dropdown-item command="skill">Skill 内容</el-dropdown-item><el-dropdown-item command="rubric">统一 Rubric</el-dropdown-item></el-dropdown-menu></template></el-dropdown><el-button v-if="row.kind !== 'directory'" link @click="download(row)">下载</el-button><el-button link type="danger" @click="remove(row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-if="shown.length > 50" v-model:current-page="page" :page-size="50" :total="shown.length" layout="total, prev, pager, next" style="margin-top:14px" />
  </div>
</template>

<style scoped>
.file-toolbar{display:flex;justify-content:space-between;gap:16px;align-items:center}.file-toolbar p,.file-hint{font-size:12px;line-height:1.8;color:#909399;margin:5px 0}.file-toolbar strong{font-size:15px}.upload-button{flex-shrink:0;padding:8px 12px;border:1px solid #409eff;color:#409eff;border-radius:4px;cursor:pointer;font-size:13px}.upload-button input{display:none}.upload-button.disabled{opacity:.6;cursor:wait}.file-filters{display:flex;gap:10px;margin:15px 0 8px}.file-filters>.el-input{flex:1}.file-filters>.el-select{width:210px}.server-path{display:block;font:12px/1.65 Consolas,monospace;word-break:break-all;user-select:all}.file-name{word-break:break-word;font-size:13px}small{color:#909399}.compact{padding:16px;background:#fafafa;border:1px solid #ebeef5;border-radius:4px;margin-top:12px}@media(max-width:650px){.file-toolbar{align-items:flex-start;flex-direction:column}.file-filters{flex-wrap:wrap}.file-filters>.el-select{width:150px}}
</style>
