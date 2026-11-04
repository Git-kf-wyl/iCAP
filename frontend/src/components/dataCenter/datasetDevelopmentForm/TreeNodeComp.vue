<template>
  <div class="file-card" :class="cardDepthClass" :style="{ marginLeft: depth * 24 + 'px' }">
    <div class="file-header" @click="handleClick">
      <span class="tree-arrow" :class="{ expanded: node._expanded }">
        <svg viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
          <path
            d="M5.5 3.5l5 4.5-5 4.5"
            stroke="currentColor"
            stroke-width="1.5"
            fill="none"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <span class="file-icon">{{ fileIcon }}</span>
      <span class="file-name">{{ node.file_name }}</span>

      <!-- 类型标签 -->
      <span
        v-if="node._type === 'directory' && node.child_count !== undefined"
        class="file-badge badge-dir"
      >📁 {{ node.child_count }} 项</span>
      <span v-else-if="node._type === 'excel'" class="file-badge badge-excel">xlsx</span>
      <span v-else-if="node._type === 'txt'" class="file-badge badge-txt">txt</span>
      <span
        v-else-if="node._type === 'other' && node.file_extension"
        class="file-badge badge-other"
      >{{ node.file_extension.replace('.', '') }}</span>
      <span v-else-if="node._type === 'json'" class="file-badge badge-json">json</span>

      <!-- loading 图标 -->
      <span v-if="node._loading" class="file-loading-icon">
        <svg
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          class="spin-icon"
        >
          <path d="M12 2a10 10 0 0 1 10 10" />
        </svg>
      </span>
    </div>

    <!-- 展开区域 -->
    <transition name="expand">
      <div v-if="node._expanded" class="file-body">
        <!-- 文件夹 -->
        <template v-if="node._type === 'directory'">
          <div class="tree-children">
            <TreeNodeComp
              v-for="(child, ci) in node.children"
              :key="ci"
              :node="child"
              :depth="depth + 1"
              :localPath="localPath"
              :isField="isField"
              :datasetId="datasetId"
              :pageSize="pageSize"
            />
            <div v-if="!node.children || node.children.length === 0" class="empty-dir">
              <span class="empty-dir-icon">📂</span>
              <span>此文件夹为空</span>
            </div>
          </div>
        </template>

        <!-- Excel -->
        <template v-else-if="node._type === 'excel'">
          <div v-if="node.error" class="file-error">{{ node.error }}</div>
          <div v-else-if="!node._loaded" class="loading-skeleton">
            <el-skeleton :rows="5" animated />
          </div>
          <div v-else class="preview-content">
            <div class="preview-bar">
              <span v-if="node.sheets && node.sheets.length > 1" class="sheet-selector">
                <span class="preview-bar-label">工作表：</span>
                <el-select
                  :model-value="node.activeSheet"
                  size="small"
                  style="width: 200px"
                  @update:model-value="node.activeSheet = $event"
                  @change="onSheetChange"
                >
                  <el-option
                    v-for="sheet in node.sheets"
                    :key="sheet.sheet_name"
                    :label="sheet.sheet_name"
                    :value="sheet.sheet_name"
                  />
                </el-select>
              </span>
              <span v-else-if="node.sheets && node.sheets.length === 1" class="sheet-name-only">
                <span class="preview-bar-label">工作表：</span>
                <span class="sheet-value">{{ node.sheets[0].sheet_name }}</span>
              </span>
              <span class="preview-bar-meta">📊 共 {{ activeSheetTotalRows }} 行</span>
            </div>
            <div class="table-wrapper">
              <el-table
                :data="activeSheetData"
                border
                stripe
                style="width: 100%"
                size="small"
                max-height="800"
                :highlight-current-row="true"
              >
                <el-table-column label="序号" width="60px" align="center">
                  <template #default="scope">
                    <span>{{ (getExcelPage(node) - 1) * pageSize + scope.$index + 1 }}</span>
                  </template>
                </el-table-column>
                <el-table-column
                  v-for="(col, colIndex) in activeSheetColumns"
                  :key="colIndex"
                  :prop="col"
                  :label="col"
                  min-width="120"
                  show-overflow-tooltip
                />
              </el-table>
            </div>
            <div v-if="activeSheetTotalRows > localPageSize" class="file-pagination">
              <el-pagination
                background
                layout="sizes, prev, pager, next, jumper"
                :page-sizes="[100, 200]"
                :page-size="localPageSize"
                :total="activeSheetTotalRows"
                :current-page="getExcelPage(node)"
                @size-change="(s) => handlePageSizeChange(node, s)"
                @current-change="(p) => handlePageChange(node, p)"
              />
            </div>
          </div>
        </template>

        <!-- TXT -->
        <template v-else-if="node._type === 'txt'">
          <div v-if="node.error" class="file-error">{{ node.error }}</div>
          <div v-else-if="!node._loaded" class="loading-skeleton">
            <el-skeleton :rows="5" animated />
          </div>
          <div v-else class="preview-content">
            <div class="preview-bar">
              <span>📄 共 {{ node.line_count || 0 }} 行</span>
            </div>
            <div class="txt-content-wrapper">
              <pre class="txt-content">{{ node.content }}</pre>
            </div>
          </div>
        </template>

        <!-- JSON / JSONL -->
        <template v-else-if="node._type === 'json'">
          <div v-if="node.error" class="file-error">{{ node.error }}</div>
          <div v-else-if="!node._loaded" class="loading-skeleton">
            <el-skeleton :rows="5" animated />
          </div>
          <div v-else class="preview-content">
            <div class="preview-bar">
              <span>📋 共 {{ node.total_rows || 0 }} 条记录</span>
              <span
                v-if="node._fullPath && node._fullPath.endsWith('.jsonl')"
                class="preview-bar-meta"
              >JSONL 格式</span>
            </div>
            <div class="table-wrapper">
              <el-table
                :data="node.data"
                border
                stripe
                style="width: 100%"
                size="small"
                max-height="800"
                :highlight-current-row="true"
              >
                <el-table-column label="序号" width="60px" align="center">
                  <template #default="scope">
                    <span>{{ ((node._page || 1) - 1) * pageSize + scope.$index + 1 }}</span>
                  </template>
                </el-table-column>
                <el-table-column
                  v-for="(col, colIndex) in (node.columns || [])"
                  :key="colIndex"
                  :label="col"
                  min-width="120"
                  show-overflow-tooltip
                >
                  <template #default="scope">
                    <span
                      :class="{ 'json-cell': isNestedValue(scope.row[col]) }"
                    >{{ isNestedValue(scope.row[col]) ? formatCellValue(scope.row[col]) : scope.row[col] }}</span>
                  </template>
                  <template #tooltip="scope">
                    <pre class="json-tooltip-content">{{ isNestedValue(scope.row[col]) ? formatJSON(scope.row[col]) : scope.row[col] }}</pre>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div v-if="node.total_rows > localPageSize" class="file-pagination">
              <el-pagination
                background
                layout="sizes, prev, pager, next, jumper"
                :page-sizes="[100, 200]"
                :page-size="localPageSize"
                :total="node.total_rows"
                :current-page="node._page || 1"
                @size-change="(s) => handlePageSizeChange(node, s)"
                @current-change="(p) => handlePageChange(node, p)"
              />
            </div>
          </div>
        </template>

        <!-- other -->
        <template v-else-if="node._type === 'other'">
          <div class="unsupported-box">
            <span class="unsupported-icon">📎</span>
            <span class="unsupported-text">
              文件类型
              <strong>{{ node.file_extension || '未知' }}</strong> 暂不支持预览
            </span>
          </div>
        </template>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { getDatasetFileData } from "@/api/dataSetApi";
import { ElMessage } from "element-plus";

// ============ Props ============
interface FileNode {
  file_name: string;
  _type: string;
  _fullPath?: string;
  _expanded?: boolean;
  _loading?: boolean;
  _loaded?: boolean;
  _page?: number;
  _pageSize?: number;
  _pageMap?: Record<string, number>;
  children?: FileNode[];
  file_extension?: string;
  child_count?: number;
  error?: string;
  // excel
  sheets?: any[];
  sheet_names?: string[];
  activeSheet?: string;
  // txt
  content?: string;
  lines?: string[];
  line_count?: number;
  // json
  data?: any[];
  columns?: string[];
  total_rows?: number;
  [key: string]: any;
}

const props = withDefaults(
  defineProps<{
    node: FileNode;
    depth?: number;
    pageSize?: number;
    localPath?: string;
    isField?: string | boolean;
    datasetId?: string;
  }>(),
  {
    depth: 0,
    pageSize: 100,
    localPath: "",
    isField: "",
    datasetId: "",
  }
);

// ============ 局部状态 ============
const localPageSize = ref(props.pageSize);

// ============ 计算属性 ============
const DEPTH_COLORS = ["#409eff", "#67c23a", "#e6a23c", "#909399"];

const cardDepthClass = computed(() => {
  const idx = Math.min(props.depth, DEPTH_COLORS.length - 1);
  return "depth-level-" + idx;
});

const fileIcon = computed(() => {
  const n = props.node;
  if (n._type === "directory") return "📁";
  if (n._type === "excel") return "📊";
  if (n._type === "txt") return "📄";
  if (n._type === "json") return "📋";
  return "📎";
});

const activeSheetData = computed(() => {
  const n = props.node;
  if (!n.sheets || n.sheets.length === 0) return [];
  const active = n.sheets.find((s) => s.sheet_name === n.activeSheet);
  return active ? active.data : [];
});

const activeSheetColumns = computed(() => {
  const n = props.node;
  if (!n.sheets || n.sheets.length === 0) return [];
  const active = n.sheets.find((s) => s.sheet_name === n.activeSheet);
  if (active && active.column_order && active.column_order.length > 0) {
    return active.column_order;
  }
  const data = active ? active.data : [];
  return data.length > 0 ? Object.keys(data[0]) : [];
});

const activeSheetTotalRows = computed(() => {
  const n = props.node;
  if (!n.sheets || n.sheets.length === 0) return 0;
  const active = n.sheets.find((s) => s.sheet_name === n.activeSheet);
  return active ? active.total_rows : 0;
});

// ============ 请求参数构建 ============
function buildRequestParams(node: FileNode, page: number) {
  const filePath = props.localPath
    ? props.localPath + "/" + node._fullPath
    : node._fullPath;
  return {
    local_path: props.localPath,
    is_field: props.isField,
    dataset: props.datasetId,
    file_path: filePath,
    page: page,
    page_size: node._pageSize || localPageSize.value,
  };
}

// ============ 数据响应处理 ============
function applyFileData(n: FileNode, body: any) {
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (parseErr) {
      console.error("parseErr: " + parseErr);
      n.error = "响应数据解析失败：数据格式异常";
      return;
    }
  }

  if (n._type === "excel") {
    if (body.excel_files && body.excel_files.length > 0) {
      const item = body.excel_files[0];
      n.sheets = item.sheets;
      n.sheet_names = item.sheet_names;
      n.activeSheet =
        item.sheets && item.sheets.length > 0 ? item.sheets[0].sheet_name : "";
      n.error = item.error;
    } else {
      n.error = "文件数据为空";
    }
  } else if (n._type === "txt") {
    if (body.txt_files && body.txt_files.length > 0) {
      const item = body.txt_files[0];
      n.content = item.content;
      n.lines = item.lines;
      n.line_count = item.line_count;
      n.error = item.error;
    } else {
      n.error = "文件数据为空";
    }
  } else if (n._type === "json") {
    if (body.json_files && body.json_files.length > 0) {
      const item = body.json_files[0];
      n.data = item.data;
      n.columns = item.columns;
      n.total_rows = item.total_rows;
      n._page = item.page || 1;
      n.error = item.error;
    } else {
      n.error = "文件数据为空";
    }
  }
}

// ============ 首次展开加载 ============
async function loadFileData(n: FileNode) {
  n._loading = true;
  try {
    const resp = await getDatasetFileData(
      buildRequestParams(n, n._type === "json" ? n._page || 1 : 1)
    );
    applyFileData(n, resp.data);
    n._loaded = true;
  } catch (e: any) {
    n.error = e.response?.data?.error || e.message || "读取失败";
  } finally {
    n._loading = false;
  }
}

// ============ 点击展开/折叠 ============
async function handleClick() {
  const n = props.node;

  if (n._expanded) {
    n._expanded = false;
    return;
  }

  n._expanded = true;

  if (n._type === "directory") {
    return;
  }

  if (n._type === "excel" || n._type === "txt" || n._type === "json") {
    if (n._loaded) return;
    await loadFileData(n);
  }
}

// ============ Excel 翻页 ============
async function onExcelPageChange(file: FileNode, page: number) {
  if (!file._pageMap) file._pageMap = {};
  file._pageMap[file.activeSheet!] = page;
  file._loaded = false;
  file._loading = true;
  try {
    const resp = await getDatasetFileData(buildRequestParams(file, page));
    let body = resp.data;
    if (typeof body === "string") {
      body = JSON.parse(body);
    }
    if (body.excel_files && body.excel_files.length > 0) {
      const newData = body.excel_files[0];
      if (newData.sheets) {
        file.sheets = newData.sheets;
        file.sheet_names = newData.sheet_names;
        if (!file.activeSheet && newData.sheets.length > 0) {
          file.activeSheet = newData.sheets[0].sheet_name;
        }
      }
      file._loaded = true;
    }
  } catch (e: any) {
    ElMessage({ type: "error", message: "翻页失败: " + (e.message || "") });
  } finally {
    file._loading = false;
  }
}

function getExcelPage(file: FileNode) {
  if (!file._pageMap) file._pageMap = {};
  return file._pageMap[file.activeSheet!] || 1;
}

// ============ JSON 翻页 ============
async function onJsonPageChange(node: FileNode, page: number) {
  node._page = page;
  node._loaded = false;
  node._loading = true;
  try {
    const resp = await getDatasetFileData(buildRequestParams(node, page));
    let body = resp.data;
    if (typeof body === "string") {
      body = JSON.parse(body);
    }
    if (body.json_files && body.json_files.length > 0) {
      const item = body.json_files[0];
      node.data = item.data;
      node.columns = item.columns;
      node.total_rows = item.total_rows;
      node._page = item.page || page;
      node.error = item.error;
    }
  } catch (e: any) {
    node.error = e.response?.data?.error || e.message || "翻页失败";
  } finally {
    node._loading = false;
    node._loaded = true;
  }
}

// ============ 工作表切换 ============
function onSheetChange() {
  const file = props.node;
  if (!file._pageMap) file._pageMap = {};
  file._pageMap[file.activeSheet!] = 1;
  onExcelPageChange(file, 1);
}

// ============ 统一的翻页入口 ============
function handlePageChange(node: FileNode, page: number) {
  if (node._type === "json") {
    onJsonPageChange(node, page);
  } else if (node._type === "excel") {
    onExcelPageChange(node, page);
  }
}

function handlePageSizeChange(node: FileNode, size: number) {
  localPageSize.value = size;
  handlePageChange(node, 1);
}

// ============ JSON 单元格展示 ============
function isNestedValue(val: unknown): boolean {
  return val !== null && val !== undefined && typeof val === "object";
}

function formatCellValue(val: unknown): string {
  const raw = JSON.stringify(val);
  if (raw.length <= 80) return raw;
  return raw.slice(0, 80) + "...";
}

function formatJSON(val: unknown): string {
  return JSON.stringify(val, null, 2);
}
</script>

<style scoped>
/* ========== 文件卡片 ========== */
.file-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 2px;
  background: #fff;
  overflow: hidden;
  transition: box-shadow 0.15s;
}
.file-card:hover {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

/* depth 左边框颜色 */
.file-card.depth-level-0 {
  border-left: 3px solid #409eff;
}
.file-card.depth-level-1 {
  border-left: 3px solid #67c23a;
}
.file-card.depth-level-2 {
  border-left: 3px solid #e6a23c;
}
.file-card.depth-level-3 {
  border-left: 3px solid #909399;
}

/* ========== 文件头部行 ========== */
.file-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.12s;
}
.file-header:hover {
  background: #f5f7fa;
}

/* ========== 箭头 ========== */
.tree-arrow {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bfc4cc;
  transition: color 0.15s, transform 0.2s;
  border-radius: 3px;
}
.file-header:hover .tree-arrow {
  color: #606266;
}
.tree-arrow.expanded {
  transform: rotate(90deg);
  color: #606266;
}

/* ========== 图标 ========== */
.file-icon {
  flex-shrink: 0;
  font-size: 16px;
  line-height: 1;
}

/* ========== 文件名 ========== */
.file-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

/* ========== 类型标签 ========== */
.file-badge {
  flex-shrink: 0;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  line-height: 1.6;
  white-space: nowrap;
  opacity: 0.75;
  transition: opacity 0.15s;
}
.file-header:hover .file-badge {
  opacity: 1;
}
.badge-dir {
  background: #f0f2f5;
  color: #909399;
}
.badge-excel {
  background: #e8f5e9;
  color: #2e7d32;
}
.badge-txt {
  background: #e3f2fd;
  color: #1565c0;
}
.badge-json {
  background: #fff3e0;
  color: #e65100;
}
.badge-other {
  background: #f5f5f5;
  color: #9e9e9e;
}

/* ========== loading 图标 ========== */
.file-loading-icon {
  flex-shrink: 0;
  color: #409eff;
  display: flex;
  align-items: center;
}
.spin-icon {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* ========== 展开/收起过渡 ========== */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
.expand-enter-to,
.expand-leave-from {
  max-height: 2000px;
  opacity: 1;
}

/* ========== 文件体（展开区域） ========== */
.file-body {
  border-top: 1px solid #f0f0f0;
}

/* ========== 子节点容器 ========== */
.tree-children {
  padding: 4px 0;
}

/* ========== 空文件夹 ========== */
.empty-dir {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 20px 0;
  color: #bfc4cc;
  font-size: 13px;
}
.empty-dir-icon {
  font-size: 16px;
}

/* ========== 预览内容区 ========== */
.preview-content {
  padding: 12px;
}

/* ========== 预览顶栏 ========== */
.preview-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #fafbfc;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
  flex-wrap: wrap;
}
.preview-bar-label {
  white-space: nowrap;
  color: #909399;
  font-size: 13px;
}
.preview-bar-meta {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}
.sheet-value {
  font-weight: 500;
  color: #303133;
}
.sheet-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}
.sheet-name-only {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ========== 表格 ========== */
.table-wrapper {
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

/* ========== 分页 ========== */
.file-pagination {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

/* ========== TXT 内容 ========== */
.txt-content-wrapper {
  max-height: 500px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fafbfc;
}
.txt-content {
  margin: 0;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: #303133;
  font-family: Menlo, Consolas, "Courier New", monospace;
}

/* ========== 不可预览提示 ========== */
.unsupported-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 16px;
  margin: 12px;
  background: #fafbfc;
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  color: #909399;
  font-size: 13px;
}
.unsupported-icon {
  font-size: 20px;
}
.unsupported-text strong {
  color: #606266;
}

/* ========== 错误信息 ========== */
.file-error {
  color: #f56c6c;
  padding: 12px 16px;
  font-size: 13px;
}

/* ========== Skeleton loading ========== */
.loading-skeleton {
  padding: 12px 16px;
}

/* ========== JSON 单元格 ========== */
.json-cell {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  cursor: default;
}

/* ========== JSON tooltip ========== */
:deep(.json-tooltip-popper) {
  max-width: 600px;
  max-height: 400px;
  overflow: auto;
}
:deep(.json-tooltip-popper .json-tooltip-content) {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  line-height: 1.5;
  font-family: Menlo, Consolas, "Courier New", monospace;
  white-space: pre;
  word-wrap: normal;
  overflow-x: auto;
}
</style>