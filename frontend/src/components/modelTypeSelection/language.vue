<template>
  <div>
    <div class="tableBox">
      <div class="buttonRow">
        <div class="update-info">
          <span class="update-label">更新频率：每半个月</span>
          <span class="update-divider"></span>
          <span class="update-label">更新时间：{{ updateTime }}</span>
        </div>
        <el-button class="createTaskbtn" @click="handleFileUpload">导入数据</el-button>
        <el-button class="createTaskbtn" @click="exportToExcel">导出数据</el-button>
      </div><el-table :data="paginatedInfo" max-height="100%" :header-cell-style="tableHeaderStyle"
        :cell-style="tableCellStyle" v-loading="loading" border stripe>
        <el-table-column prop="strategy" label="策略" width="80px"></el-table-column>
        <el-table-column prop="year" label="发布年" width="100px"></el-table-column>
        <el-table-column prop="month" label="发布月" width=100px></el-table-column>
        <el-table-column prop="company" label="发布机构"></el-table-column>
        <el-table-column prop="model_name" label="模型名称"></el-table-column>
        <el-table-column prop="config" label="模型参数（B）" width="120px"></el-table-column>
        <el-table-column prop="activate" label="激活参数（B）" width="120px"></el-table-column>
        <el-table-column prop="token" label="训练数据Token（B）" width="200px"></el-table-column>
        <el-table-column prop="route" label="模型路线" width="120px"></el-table-column>
        <el-table-column prop="architecture" label="模型架构"></el-table-column>
      </el-table>
      <div class="pagination">
        <span class="total-text">总计: {{ totalItems }}</span>
        <el-pagination background layout="sizes, prev, pager, next, jumper" :page-sizes="[10, 20]" :page-size="pageSize"
          :total="totalItems" :current-page="currentPage" @size-change="handleSizeChange"
          @current-change="handleCurrentChange"></el-pagination>
      </div>
    </div>
    <el-dialog v-model="dialogVisible" title="上传Excel文件" width="30%" :before-close="handleClose">
      <el-upload ref="upload" drag action :http-request="uploadFile" :on-success="handleSuccess" :on-error="handleError"
        :before-upload="beforeUpload" multiple :limit="1" :on-exceed="handleExceed" accept=".xlsx">
        <el-icon class="el-icon--upload">
          <upload-filled />
        </el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或
          <em>点击上传</em>
        </div>
        <div class="el-upload__tip" slot="tip">只能上传Excel文件</div>
      </el-upload>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleClose">取消</el-button>
          <el-button type="primary" @click="handleConfirm">确认</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import {
  ElMessage,
  UploadInstance,
  UploadProps,
  UploadRawFile,
  genFileId,
} from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";
import { getModelsFileData, downloadModelsFile, uploadModelsFile } from '@/api/dataService.js'

const dialogVisible = ref(false);

const tableHeaderStyle = {
  textAlign: "center",
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
};

const tableCellStyle = {
  textAlign: "center",
}

const updateTime = ref('');

const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const refreshUpdateTime = () => {
  updateTime.value = formatDate(new Date());
  // 持久化到 localStorage 以便跨会话保持
  localStorage.setItem('languageModelUpdateTime', updateTime.value);
};

const loadPersistedUpdateTime = () => {
  const saved = localStorage.getItem('languageModelUpdateTime');
  if (saved) {
    updateTime.value = saved;
  } else {
    updateTime.value = '2026-06-30';
  }
};

// 判断今天是否是自动刷新日（每月15号和30号，2月取28号）
const isRefreshDay = (): boolean => {
  const now = new Date();
  const day = now.getDate();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();

  // 检查是否为2月且当天是28号
  if (month === 2 && day === 28) return true;
  // 检查是否为15号或30号
  if (day === 15 || day === 30) return true;
  return false;
};

// 检查上次更新时间，避免在同一天内重复刷新
const checkScheduledRefresh = () => {
  if (isRefreshDay()) {
    const saved = localStorage.getItem('languageModelUpdateTime');
    const today = formatDate(new Date());
    if (saved !== today) {
      refreshUpdateTime();
    }
  }
};

const handleFileUpload = () => {
  dialogVisible.value = true;
};

const uploadFile = async (file) => {
  const isLt2M = file.file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    ElMessage.error("上传文件大小不能超过 2MB!");
    upload.value!.clearFiles();
  } else {
    const formData = new FormData();
    formData.append('file', file.file);

    try {
      const response = await uploadModelsFile(formData)
      console.log('上传成功:', response.data);
      // 上传成功后更新更新时间
      refreshUpdateTime();
    } catch (error) {
      console.error('上传失败:', error);
    }
  }
};

const upload = ref<UploadInstance>();
const handleExceed: UploadProps["onExceed"] = (files) => {
  upload.value!.clearFiles();
  const file = files[0] as UploadRawFile;
  file.uid = genFileId();
  upload.value!.handleStart(file);
};

const handleClose = () => {
  upload.value!.clearFiles();
  dialogVisible.value = false;
};

const handleSuccess = (response, file, fileList) => {
  ElMessage.success("文件上传成功");
  console.log("文件上传成功", response, file, fileList);
};

const handleError = (error, file, fileList) => {
  ElMessage.error("文件上传失败");
  console.log("文件上传失败", error, file, fileList);
};

const handleConfirm = () => {
  // 这里可以添加确认后的逻辑，例如处理上传的文件

  ElMessage.success("确认上传");
  dialogVisible.value = false;
};

const exportToExcel = () => {
  downloadModelsFile()
    .then(res => {
      res.data;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "AI模型汇总.xlsx";
      a.click();
      window.URL.revokeObjectURL(url);
      ElMessage({
        type: "success",
        message: "下载成功",
      });
    })
    .catch(error => {
      console.error('下载失败:', error);
      ElMessage.error("下载失败");
    });
};

// 定义分页相关变量
const pageSize = ref(20);
const currentPage = ref(1);
const totalItems = computed(() => tableData.value.length);

// 分页数据计算属性
const paginatedInfo = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return tableData.value.slice(start, end);
});

// 处理每页数量变化
const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1; // 切换每页数量时回到第一页
};

// 处理页码改变
const handleCurrentChange = (val) => {
  currentPage.value = val;
};

const dataMap = {
  '发布年': 'year',
  '发布月': 'month',
  '发布机构': 'company',
  '模型参数（B）': 'config',
  "模型名称": 'model_name',
  '模型架构': 'architecture',
  '模型路线': 'route',
  '激活参数（B）': 'activate',
  '策略': 'strategy',
  '训练数据Token（B）': 'token',
}
const tableData = ref([])
const loading = ref(true)

const loadData = async () => {
  const res = await getModelsFileData({
    file_sheet: "LLM大语言模型"
  });
  let data = {}

  try {
    data = res.data.data.filter(item => {
      // 检查对象中的所有属性值
      return Object.values(item).some(value => value !== null);
    });
  } catch (error) {
    console.error('解析JSON字符串时出错:', error);
  }

  console.log('data:');
  console.log(data);

  tableData.value = data.map(item => {
    const transformedItem = {};
    for (const [oldKey, newKey] of Object.entries(dataMap)) {
      if (item.hasOwnProperty(oldKey)) {
        transformedItem[newKey] = item[oldKey];
      }
    }
    return transformedItem;
  });

  console.log('tableData:');
  console.log(tableData.value);
  loading.value = false
}

let refreshTimer: number | null = null;

onMounted(() => {
  loadData();
  loadPersistedUpdateTime();
  checkScheduledRefresh();
  // 每小时检查一次是否需要自动刷新
  refreshTimer = window.setInterval(checkScheduledRefresh, 3600000);
});

onBeforeUnmount(() => {
  if (refreshTimer !== null) {
    clearInterval(refreshTimer);
  }
});
</script>

<style scoped>
.tableBox {
  height: 100%;
  margin: 0px 10px;
}

.buttonRow {
  height: 36px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 12px;
}

.update-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: auto;
  color: #606060;
  font-size: 14px;
}

.update-label {
  font-weight: 500;
  white-space: nowrap;
}

.update-divider {
  width: 1px;
  height: 14px;
  background: #d0d0d0;
}
</style>