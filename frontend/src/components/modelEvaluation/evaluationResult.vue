<template>
  <div class="container" v-loading.fullscreen.lock="downloadLoading" element-loading-text="下载中...">
    <div style="height: 10px;"></div>
    <div class="cardContainer" style="margin-top: 0;">
      <!-- 筛选栏 -->
      <div class="filter-bar">
        <div class="filter-item">
          <span class="filter-label">模型：</span>
          <el-select
            v-model="filterModelValue"
            clearable
            placeholder="全部模型"
            style="width: 200px;"
            @change="applyFilters"
          >
            <el-option v-for="item in modelOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <div class="filter-item">
          <span class="filter-label">测试集：</span>
          <el-select
            v-model="filterDatasetValue"
            clearable
            placeholder="全部测试集"
            style="width: 200px;"
            @change="applyFilters"
          >
            <el-option v-for="item in datasetOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
        <div style="flex: 1; text-align: right;">
          <span v-if="selectedTasks.length > 0" style="margin-right: 10px;">
            已选 {{ selectedTasks.length }} 条报告
            <el-tooltip content="清空选择" placement="top">
              <el-button type="danger" @click="clearSelection" :icon="Delete" circle size="small" />
            </el-tooltip>
          </span>
          <el-button
            type="success"
            size="small"
            @click="batchUpdateTopChart"
            :disabled="selectedTasks.length === 0"
            style="margin-right: 8px;"
          >
            <el-icon style="margin-right: 4px;">
              <Upload />
            </el-icon>更新榜单
          </el-button>
          <el-button type="warning" size="small" @click="openUploadDialog" style="margin-right: 8px;">
            <el-icon style="margin-right: 4px;">
              <UploadFilled />
            </el-icon>上传本地结果
          </el-button>
          <el-button type="primary" size="small" @click="getTasksList" :loading="loading">
            <el-icon style="margin-right: 4px;">
              <Refresh />
            </el-icon>刷新
          </el-button>
        </div>
      </div>
      <el-table
        ref="tableRef"
        :data="paginatedTasks"
        fit
        stripe
        size="small"
        show-header
        class="TaskInfoTable"
        :header-cell-style="tableHeaderStyle"
        :default-sort="{ prop: 'create_time', order: 'descending' }"
        v-loading="loading"
        @sort-change="handleSortChange"
        @selection-change="handleSelectionChange"
        row-key="rowId"
      >
        <el-table-column
          type="selection"
          width="50"
          align="center"
          fixed="left"
          :reserve-selection="true"
        />
        <el-table-column
          prop="task_name"
          label="任务名称"
          show-overflow-tooltip
          align="center"
          fixed="left"
        />
        <el-table-column label="模型" sortable show-overflow-tooltip align="center" prop="model_id">
          <template #default="{ row, $index }">
            <template v-if="editingRowIndex === $index">
              <el-input
                v-model="editingModelName"
                size="small"
                style="width: 140px;"
                @keyup.enter="confirmInlineEdit(row, $index)"
                @blur="confirmInlineEdit(row, $index)"
              />
            </template>
            <span
              v-else
              @click="startInlineEdit(row, $index)"
              style="cursor: pointer; border-bottom: 1px dashed #ccc;"
            >{{ row.model_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="model_type" label="模型类型" min-width="80" align="center" />
        <el-table-column label="测试集" show-overflow-tooltip align="center">
          <template #default="scope">
            {{ scope.row.dataset === scope.row.task_dataset
            ? scope.row.dataset
            : `${scope.row.dataset}(${scope.row.task_dataset})` }}
          </template>
        </el-table-column>
        <el-table-column label="分数" align="center">
          <template #default="{ row }">{{ (row.score * 100).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" align="center" />
        <el-table-column label="耗时" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'running'">统计中</el-tag>
            <el-tag type="danger" v-else-if="!row.running_time">未统计</el-tag>
            <span v-else>{{ formatSeconds(row.running_time) || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" align="center">
          <template #default="{ row }">
            <el-tooltip content="评测详情" placement="top">
              <el-button
                link
                type="primary"
                size="large"
                @click="showRowResult(row)"
                v-show="row.assessmentType != 'AISF发布评估'"
              >
                <el-icon>
                  <Document />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="下载测评文件" placement="top">
              <el-button link type="primary" size="large" @click="downloadData(row)">
                <el-icon>
                  <Download />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除结果信息" placement="top">
              <el-button link type="primary" size="large" @click="openDeleteByID(row.id)">
                <el-icon>
                  <Delete />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="更新榜单" placement="top">
              <el-button
                link
                type="primary"
                size="large"
                @click="asyncScore(row)"
                :disabled="row.assessmentType === 'AISF开发评估'"
              >
                <el-icon>
                  <Upload />
                </el-icon>
              </el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <!-- 单条更新榜单弹窗 -->
      <el-dialog
        v-model="modelEditDialogVisible"
        title="更新榜单"
        :close-on-click-modal="false"
        width="30%"
      >
        <div>
          <el-form label-width="100px" label-position="left" size="small">
            <el-form-item label="模型名称">
              <el-input v-model="editingModelName" placeholder="请输入模型名称" style="width: 100%;" />
            </el-form-item>
          </el-form>
          <div
            style="font-size: 12px; color: #909399; margin-top: -8px; margin-left: 100px;"
          >修改后将以此名称更新榜单</div>
        </div>
        <template #footer>
          <el-button @click="modelEditDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmModelEdit">确认并更新</el-button>
        </template>
      </el-dialog>

      <!-- 批量更新榜单弹窗 -->
      <el-dialog
        v-model="batchUpdateDialogVisible"
        title="批量更新榜单"
        :close-on-click-modal="false"
        width="50%"
      >
        <div>
          <el-alert
            title="以下任务将被提交至榜单，请确认模型名称"
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 16px;"
          />
          <el-table :data="batchTasks" size="small" stripe max-height="400">
            <el-table-column prop="task_name" label="任务名称" align="center" />
            <el-table-column label="测试集" align="center">
              <template #default="{ row }">{{ row.datasets.join(', ') }}</template>
            </el-table-column>
            <el-table-column label="模型名称" align="center">
              <template #default="{ row, $index }">
                <el-input
                  v-model="batchTasks[$index].modelName"
                  size="small"
                  style="width: 160px;"
                />
              </template>
            </el-table-column>
          </el-table>
        </div>
        <template #footer>
          <el-button @click="batchUpdateDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmBatchUpdate" :loading="batchUpdating">确认批量更新</el-button>
        </template>
      </el-dialog>

      <!-- 上传本地结果弹窗 -->
      <el-dialog
        v-model="uploadDialogVisible"
        title="上传本地结果（尺子二）"
        :close-on-click-modal="false"
        width="500px"
      >
        <el-form label-width="100px" label-position="left" size="small">
          <el-form-item label="tag">
            <el-select
              v-model="uploadForm.tag"
              placeholder="请选择 tag"
              style="width: 100%;"
              @change="handleTagChange"
            >
              <el-option
                v-for="item in tagOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
                :disabled="item.disabled"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="model_id">
            <el-input v-model="uploadForm.model_id" placeholder="请输入模型名称" />
          </el-form-item>

          <!-- 多文件 tag（记忆 / 伴学提参）：选择子任务/子业务 -->
          <el-form-item
            v-if="isMultiSubtaskTag(uploadForm.tag)"
            :label="subtaskLabel(uploadForm.tag)"
          >
            <el-checkbox-group v-model="memorySubtaskKeys">
              <el-checkbox
                v-for="item in subtaskOptionsFor(uploadForm.tag)"
                :key="item.value"
                :value="item.value"
                :label="item.label"
              />
            </el-checkbox-group>
          </el-form-item>

          <!-- 单文件 tag（非多文件类型）：单文件上传 -->
          <el-form-item
            v-if="!isMultiSubtaskTag(uploadForm.tag)"
            label="结果Excel"
          >
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".xlsx,.xls"
              :on-change="handleFileChange"
              :on-exceed="handleFileExceed"
            >
              <el-button type="primary" plain>
                <el-icon style="margin-right: 4px;">
                  <UploadFilled />
                </el-icon>选择本地 Excel
              </el-button>
              <template #tip>
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  仅支持 .xlsx / .xls 格式文件
                </div>
              </template>
            </el-upload>
          </el-form-item>

          <!-- 多文件 tag（记忆 / 伴学提参）：每个子任务/子业务对应一个 Excel 文件
               注：selectedMemorySubtasks 仅在多文件 tag 下非空，单文件 tag 下为空无需渲染 -->
          <el-form-item
            v-for="item in selectedMemorySubtasks"
            :key="item.value"
            :label="item.label"
            label-position="top"
          >
            <el-upload
              :ref="(el) => setSubtaskUploadRef(item.value, el)"
              :auto-upload="false"
              :limit="1"
              accept=".xlsx,.xls"
              :on-change="(file) => handleSubtaskFileChange(item.value, file)"
              :on-exceed="handleFileExceed"
              class="subtask-upload"
            >
              <el-button type="primary" plain :icon="UploadFilled">
                选择该子任务的 Excel
              </el-button>
              <template #tip>
                <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                  上传「{{ item.label }}」的结果文件
                </div>
              </template>
            </el-upload>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="uploadDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmUpload" :loading="uploading">
            确认上传
          </el-button>
        </template>
      </el-dialog>

      <div class="pagination">
        <span class="total-text">总计: {{ totalItems }}</span>
        <el-pagination
          background
          layout="sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20]"
          :page-size="pageSize"
          :total="totalItems"
          :current-page="currentPage"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        ></el-pagination>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, computed, reactive } from "vue";
import { useRouter, useRoute } from "vue-router";
import { ElMessage, ElMessageBox, ElLoading } from "element-plus";
import {
  Delete,
  Document,
  Download,
  Upload,
  UploadFilled,
  Refresh,
} from "@element-plus/icons-vue";
import { getList, deleteResultById } from "@/api/runService.js";
import { downloadFile, getFilePath, updateScore } from "@/api/runService.js";
import { uploadLocalResult } from "@/api/runService.js";
import { INTERPRETATIONS_TYPES } from "@/utils/Constants.js";
import { useStore } from "vuex";
import { getEvaluationResult } from "@/api/dataService";

const store = useStore();

// 筛选相关
const filterModelValue = ref("");
const filterDatasetValue = ref("");

const modelOptions = computed(() => {
  const values = [
    ...new Set(
      data_list.arr
        .map((item) => item.model_id)
        .filter((v) => v !== null && v !== "" && v !== undefined)
    ),
  ];
  return values;
});

const datasetOptions = computed(() => {
  const values = [
    ...new Set(
      data_list.arr
        .map((item) => item.dataset)
        .filter((v) => v !== null && v !== "" && v !== undefined)
    ),
  ];
  return values;
});

const applyFilters = () => {
  // 切换分页到第一页
  store.dispatch("resultTable/updatePageNum", 1);
};

const filteredTaskData = computed(() => {
  return data_list.arr.filter((row) => {
    if (filterModelValue.value && row.model_id !== filterModelValue.value) {
      return false;
    }
    if (filterDatasetValue.value && row.dataset !== filterDatasetValue.value) {
      return false;
    }
    return true;
  });
});

const formatSeconds = computed(() => (seconds) => {
  if (seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;
    const padZero = (value) => value.toString().padStart(2, "0");
    const integerSeconds = Math.floor(remainingSeconds);
    return `${padZero(hours)}:${padZero(minutes)}:${padZero(integerSeconds)}`;
  } else {
    return "00:00:00";
  }
});

// 模型名称编辑弹窗与行内编辑
const modelEditDialogVisible = ref(false);
const editingModelName = ref("");
const editingRow = ref(null);
const editingRowIndex = ref(-1);

const asyncScore = (row) => {
  editingModelName.value = row.model_id || row.model_name || "";
  editingRow.value = row;
  modelEditDialogVisible.value = true;
};

const confirmModelEdit = () => {
  const row = editingRow.value;
  if (!row) return;

  modelEditDialogVisible.value = false;
  updateScore({
    task_id: [row.task_id],
    testcase: [row.dataset],
    model_id: editingModelName.value,
  }).then(
    (res) => {
      // 更新本地数据，使表格立即反映修改
      const target = data_list.arr.find(
        (item) => item.task_id === row.task_id && item.dataset === row.dataset
      );
      if (target) {
        target.model_id = editingModelName.value;
      }
      ElMessage({ type: "success", message: "更新成功" });
    },
    (err) => {
      ElMessage({ type: "error", message: "更新失败" + err });
    }
  );
};

// 行内编辑
const startInlineEdit = (row, index) => {
  editingRowIndex.value = index;
  editingModelName.value = row.model_id;
};

const confirmInlineEdit = (row, index) => {
  if (editingRowIndex.value === -1) return;
  const newName = editingModelName.value.trim();
  if (!newName) {
    ElMessage({ type: "warning", message: "模型名称不能为空" });
    return;
  }
  // 更新本地数据
  row.model_id = newName;
  editingRowIndex.value = -1;
};

// 多选与批量更新榜单
const tableRef = ref(null);
const selectedTasks = ref([]);
const batchUpdateDialogVisible = ref(false);
const batchTasks = ref([]);
const batchUpdating = ref(false);

const handleSelectionChange = (selection) => {
  // selection 只包含当前页的选中行，但 reserve-selection 保留了跨页选中
  // 使用 tableRef 的 getSelectionRows() 获取所有页面的完整选中行
  if (tableRef.value) {
    selectedTasks.value = tableRef.value.getSelectionRows();
  } else {
    selectedTasks.value = selection;
  }
};

const clearSelection = () => {
  if (tableRef.value) {
    tableRef.value.clearSelection();
  }
  selectedTasks.value = [];
};

const batchUpdateTopChart = () => {
  if (selectedTasks.value.length === 0) {
    ElMessage({ type: "warning", message: "请先选择要更新榜单的任务" });
    return;
  }
  // 准备批量任务列表，按 task_id 去重（同一 task_id 不同 dataset 合并）
  const taskMap = new Map();
  selectedTasks.value.forEach((row) => {
    const key = row.task_id;
    if (!taskMap.has(key)) {
      taskMap.set(key, {
        task_id: row.task_id,
        task_name: row.task_name,
        model_id: row.model_id,
        modelName: row.model_id || "",
        datasets: [],
      });
    }
    if (row.dataset && !taskMap.get(key).datasets.includes(row.dataset)) {
      taskMap.get(key).datasets.push(row.dataset);
    }
  });
  batchTasks.value = Array.from(taskMap.values());
  batchUpdateDialogVisible.value = true;
};

const confirmBatchUpdate = () => {
  if (batchTasks.value.length === 0) return;
  batchUpdating.value = true;

  const taskIds = batchTasks.value.map((t) => t.task_id);
  // 收集所有测试集（所有选中任务的 dataset 并集）
  const allTestcases = [
    ...new Set(batchTasks.value.flatMap((t) => t.datasets)),
  ];

  updateScore({
    "task_id[]": taskIds,
    "testcase[]": allTestcases,
  }).then(
    (res) => {
      batchUpdating.value = false;
      batchUpdateDialogVisible.value = false;
      ElMessage({ type: "success", message: "批量更新榜单成功" });
      // 清空选中状态
      if (tableRef.value) {
        tableRef.value.clearSelection();
      }
      getTasksList();
    },
    (err) => {
      batchUpdating.value = false;
      ElMessage({
        type: "error",
        message:
          "批量更新失败: " + (err.response?.data?.error || err.message || err),
      });
    }
  );
};

const downloadLoading = ref(false);

// 上传本地结果
const uploadDialogVisible = ref(false);
const uploading = ref(false);
// 当前后端所有 tag 均已实现本地结果上传（儿童伴读 / 意图 / 记忆 / 改写 /
// skill提参 / GUI提参 / 伴学提参 / Coordinator）
const tagOptions = [
  { label: "儿童伴读", value: "儿童伴读", disabled: false },
  { label: "意图", value: "意图", disabled: false },
  { label: "记忆", value: "记忆", disabled: false },
  { label: "改写", value: "改写", disabled: false },
  { label: "skill提参", value: "skill提参", disabled: false },
  { label: "GUI提参", value: "GUI提参", disabled: false },
  { label: "伴学提参", value: "伴学提参", disabled: false },
  { label: "Coordinator", value: "Coordinator", disabled: false },
];

// 记忆子任务：每个子任务对应一个结果 Excel 文件
const memorySubtaskOptions = [
  { label: "记忆萃取-信息点提取", value: "记忆萃取-信息点提取" },
  { label: "记忆召回-总结过滤", value: "记忆召回-总结过滤" },
  { label: "记忆萃取-更新", value: "记忆萃取-更新" },
  { label: "记忆召回-查询扩写", value: "记忆召回-查询扩写" },
];

// 伴学提参子任务：固定 提醒 / 总结 / 提参 三个，每个对应一个结果 Excel 文件
const banxueSubtaskOptions = [
  { label: "提醒", value: "提醒" },
  { label: "总结", value: "总结" },
  { label: "提参", value: "提参" },
];

// 当前 tag 是否为多文件（多子任务）上传类型：记忆 / 伴学提参
const isMultiSubtaskTag = (tag) => tag === "记忆" || tag === "伴学提参";
// 多文件 tag 的子任务展示名
const subtaskLabel = (tag) => {
  if (tag === "伴学提参") return "伴学提参子任务";
  return "记忆子任务";
};

// 多文件 tag 对应的子任务选项列表
const subtaskOptionsFor = (tag) => {
  if (tag === "伴学提参") return banxueSubtaskOptions;
  return memorySubtaskOptions;
};

const uploadForm = reactive({
  tag: "",
  model_id: "",
  file: null,
  // 多文件 tag（记忆 / 伴学提参）子任务 key -> File 映射，FormData 字段名为 file_<key>
  memoryFiles: {},
});

const memorySubtaskKeys = ref([]);

const selectedMemorySubtasks = computed(() =>
  subtaskOptionsFor(uploadForm.tag).filter((item) =>
    memorySubtaskKeys.value.includes(item.value)
  )
);

// 单 tag（非记忆）上传 ref，用于弹窗关闭时清空
const uploadRef = ref(null);
// 记忆子任务上传 ref 集合，key 为子任务 value，值为 element 上传实例
const subtaskUploadRefs = {};

const setSubtaskUploadRef = (key, el) => {
  if (el) {
    subtaskUploadRefs[key] = el;
  } else {
    delete subtaskUploadRefs[key];
  }
};

const handleSubtaskFileChange = (key, file) => {
  uploadForm.memoryFiles[key] = file.raw;
};

const clearSubtaskUploads = () => {
  Object.keys(subtaskUploadRefs).forEach((key) => {
    try {
      subtaskUploadRefs[key]?.clearFiles();
    } catch (e) {
      // 忽略已销毁的实例
    }
  });
};

const openUploadDialog = () => {
  uploadForm.tag = "";
  uploadForm.model_id = "";
  uploadForm.file = null;
  uploadForm.memoryFiles = {};
  memorySubtaskKeys.value = [];
  if (uploadRef.value) {
    uploadRef.value.clearFiles();
  }
  clearSubtaskUploads();
  uploadDialogVisible.value = true;
};

const handleTagChange = (val) => {
  // 切换 tag 时清空上一 tag 已选文件
  uploadForm.file = null;
  uploadForm.memoryFiles = {};
  memorySubtaskKeys.value = [];
  if (uploadRef.value) {
    uploadRef.value.clearFiles();
  }
  clearSubtaskUploads();
};

const handleFileChange = (file) => {
  uploadForm.file = file.raw;
};

const handleFileExceed = () => {
  ElMessage({ type: "warning", message: "仅可上传一个文件" });
};

const confirmUpload = () => {
  if (!uploadForm.tag) {
    ElMessage({ type: "warning", message: "请选择 tag" });
    return;
  }
  if (!uploadForm.model_id.trim()) {
    ElMessage({ type: "warning", message: "请输入 model_id" });
    return;
  }

  const formData = new FormData();
  formData.append("tag", uploadForm.tag);
  formData.append("model_id", uploadForm.model_id.trim());

  if (!isMultiSubtaskTag(uploadForm.tag)) {
    // 单文件 tag：单个 file 字段
    if (!uploadForm.file) {
      ElMessage({ type: "warning", message: "请选择要上传的 Excel 文件" });
      return;
    }
    formData.append("file", uploadForm.file);
  } else {
    // 多文件 tag（记忆 / 伴学提参）：每个子任务对应 file_<子任务key> 字段
    const missing = memorySubtaskKeys.value.filter(
      (key) => !uploadForm.memoryFiles[key]
    );
    if (memorySubtaskKeys.value.length === 0) {
      ElMessage({ type: "warning", message: "请选择至少一个子任务" });
      return;
    }
    if (missing.length > 0) {
      ElMessage({
        type: "warning",
        message: "以下子任务未选择 Excel 文件：" + missing.join("、"),
      });
      return;
    }
    memorySubtaskKeys.value.forEach((key) => {
      formData.append("file_" + key, uploadForm.memoryFiles[key]);
    });
  }

  uploading.value = true;
  uploadLocalResult(formData).then(
    (res) => {
      uploading.value = false;
      uploadDialogVisible.value = false;
      ElMessage({ type: "success", message: res.data?.message || "上传成功" });
      getTasksList();
    },
    (err) => {
      uploading.value = false;
      ElMessage({
        type: "error",
        message:
          "上传失败: " + (err.response?.data?.error || err.message || err),
      });
    }
  );
};

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
};

const router = useRouter();
const route = useRoute();

const showRowResult = (task) => {
  router.push({
    name: "resultDetail",
    query: {
      taskId: task.task_id,
      model_name: task.model_name,
      dataset: task.task_dataset,
      score: task.score,
      assessmentType: task.assessmentType,
    },
  });
};

const openDeleteByID = (ID) => {
  ElMessageBox.confirm("确认删除 ID 为 " + ID + " 的评估任务信息？", "提示", {
    confirmButtonText: "确认",
    cancelButtonText: "取消",
    type: "warning",
  })
    .then(() => {
      deleteResultById({ id: ID }).then(
        (res) => {
          ElMessage({ type: "success", message: "删除成功" });
          getTasksList();
        },
        (err) => {
          ElMessage({
            type: "error",
            message: "删除失败：" + err,
          });
        }
      );
    })
    .catch(() => {});
};

const downloadData = (row) => {
  const dataset = row.dataset;
  getFilePath({
    task_id: row.task_id,
    dataset: dataset,
    assessmentType: row.assessmentType,
    evaluationType: row.evaluationType ?? "INTERPRETATION",
  }).then(
    (res) => {
      if (res.data.length === 0) {
        ElMessage({ type: "error", message: "无文件" });
        return;
      }
      if (res.data.length === 1) {
        downloadFile({ filepath: res.data[0] }).then(
          (response) => {
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const a = document.createElement("a");
            a.href = url;
            a.download = res.data[0].split("/").pop().split("\\").pop();
            a.click();
            window.URL.revokeObjectURL(url);
            ElMessage({ type: "success", message: "下载成功" });
          },
          (err) => {
            ElMessage({
              type: "error",
              message: "下载失败: " + err.response.data.error,
            });
          }
        );
      }
    },
    (err) => {
      ElMessage({
        type: "error",
        message: "获取文件列表失败: " + err.response.data.error,
      });
    }
  );
};

const sortConfig = ref({ prop: "", order: "" });

const handleSortChange = ({ column, prop, order }) => {
  sortConfig.value = { prop, order };
};

const sortedTaskData = computed(() => {
  if (!Array.isArray(data_list.arr) || data_list.arr.length === 0) {
    return [];
  }
  let { prop, order } = sortConfig.value;
  if (!prop || !order) {
    prop = "create_time";
    order = "descending";
  }
  const isAsc = order === "ascending";
  return [...filteredTaskData.value].sort((a, b) => {
    const strA = String(a[prop] || "");
    const strB = String(b[prop] || "");
    return isAsc ? strA.localeCompare(strB) : strB.localeCompare(strA);
  });
});

const pageSize = ref(10);
const currentPage = computed(() => store.getters["resultTable/getPageNum"]);
const totalItems = computed(() => sortedTaskData.value.length);

const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return sortedTaskData.value.slice(start, end);
});

const handleSizeChange = (val) => {
  pageSize.value = val;
  store.dispatch("resultTable/updatePageNum", 1);
};

const handleCurrentChange = (val) => {
  store.dispatch("resultTable/updatePageNum", val);
};

const data_list = reactive({
  arr: [],
});

const loading = ref(true);

const getTasksList = () => {
  loading.value = true;
  getEvaluationResult().then((res) => {
    // 如果 res.data 是对象，则提取值为数组；如果是数组，保持不变
    data_list.arr = (
      Array.isArray(res.data) ? res.data : Object.values(res.data)
    ).map((item) => ({
      ...item,
      rowId: String(item.task_id) + "__" + (item.dataset || ""),
    }));
    // 从 localStorage 读取任务列表页传递过来的模型名称覆盖（跨页面、跨标签页共享）
    try {
      const modelOverrides = JSON.parse(
        localStorage.getItem("evalModelOverrides") || "{}"
      );
      data_list.arr.forEach((item) => {
        const key = item.rowId;
        if (modelOverrides[key] && modelOverrides[key] !== item.model_id) {
          item.model_id = modelOverrides[key];
        }
      });
    } catch (e) {
      console.warn("读取 evalModelOverrides 失败", e);
    }
    loading.value = false;
  });
};

onMounted(() => {
  getTasksList();
});
</script>

<style>
.filter-bar {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
  align-items: center;
}

.filter-item {
  display: flex;
  align-items: center;
}

.filter-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

.TaskInfoTable {
  font-size: medium;
}

.TaskInfoTable .el-table__row {
  height: 4rem;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.total-text {
  color: #666;
  font-size: 16px;
}

/* 上传弹窗：长文件名超出弹窗范围时省略显示 */
.subtask-upload {
  width: 100%;
}

.subtask-upload .el-upload,
.subtask-upload .el-upload--text {
  width: 100%;
}

.subtask-upload .el-upload-list,
.el-upload-list {
  width: 100%;
}

.subtask-upload .el-upload-list__item,
.el-upload-list__item {
  position: relative;
  box-sizing: border-box;
  padding-right: 60px;
  width: 100%;
  overflow: hidden;
}

.subtask-upload .el-upload-list__item-name,
.el-upload-list__item-name {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subtask-upload .el-upload-list__item .el-icon--close,
.el-upload-list__item .el-icon--close {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
}
</style>