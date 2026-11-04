<template>
  <div class="container">
    <div class="titleContainer">
      <span style="padding: 0 5px"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:10px;" />
      <span style="padding: 0 20px;"></span>
      <span style="font-size:18px;font-weight:600;">报告预览</span>
      <span style="flex: 1;"></span>
      <el-tooltip
        effect="dark"
        :content="!reportPreviewStore.isFullscreen?'全屏':'退出全屏'"
        placement="bottom"
      >
        <el-button
          class="fullscreen-btn"
          icon="FullScreen"
          @click="toggleFullscreen"
          circle
          type="primary"
        />
      </el-tooltip>
    </div>
    <div
      v-loading="loading"
      :class="['preview-body', { 'preview-body--fullscreen': reportPreviewStore.isFullscreen }]"
    >
      <template v-if="pdfUrl">
        <iframe
          :src="pdfUrl"
          style="width: 100%; height: 100%; border: none;"
          @load="onIframeLoad"
        />
      </template>
      <el-empty v-else-if="!loading" description="暂无预览" style="margin-top: 10vh;" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { previewReportFile, getAllPublishedTasks } from "@/api/runService.js";
import { API_BASE_URL } from "@/utils/Constants.js";
import { useReportPreviewStore } from "@/stores/reportPreview.js";

const reportPreviewStore = useReportPreviewStore();

const toggleFullscreen = () => {
  reportPreviewStore.toggleFullscreen();
};

const route = useRoute();
const router = useRouter();

const loading = ref(false);
const pdfUrl = ref("");
let loadTimer = null;
const LOAD_TIMEOUT = 30000;

const goBack = () => {
  if (route.query.taskId) {
    // 来自 ReportGenerationPanel：直接返回，无需操作全屏状态
    router.back();
  } else {
    toggleFullscreen();
    router.push("/PublishedReport");
  }
};

/**
 * 根据 filepath 调用预览接口，加载 PDF 预览
 */
const loadPreviewByFilepath = async (filepath) => {
  const resp = await previewReportFile({ filepath });
  const data = resp.data;
  if (data.preview_type === "pdf" && data.url) {
    pdfUrl.value = API_BASE_URL.replace(/\/v1\/$/, "") + data.url;
    loadTimer = setTimeout(() => {
      if (loading.value) {
        loading.value = false;
      }
    }, LOAD_TIMEOUT);
  } else {
    ElMessage({ type: "error", message: "不支持的预览类型" });
  }
};

onMounted(async () => {
  const reportId = route.query.id;
  const directFilepath = route.query.filepath;

  if (!reportId && !directFilepath) {
    ElMessage({ type: "warning", message: "缺少报告参数" });
    return;
  }

  loading.value = true;
  try {
    if (directFilepath) {
      // 来自 ReportGenerationPanel：直接使用 filepath 预览
      await loadPreviewByFilepath(directFilepath);
    } else if (reportId) {
      // 来自 publishedReport：从已发布列表中查找 published_filepath
      const listResp = await getAllPublishedTasks();
      const report = (listResp.data || []).find(
        (item) => String(item.id) === String(reportId)
      );
      if (!report || !report.published_filepath) {
        ElMessage({ type: "warning", message: "未找到该报告或报告文件不存在" });
        return;
      }
      await loadPreviewByFilepath(report.published_filepath);
    }
  } catch (err) {
    loading.value = false;
    ElMessage({
      type: "error",
      message: "预览加载失败: " + (err.response?.data?.error || err.message),
    });
  }
  document.addEventListener('keydown', handleKeydown);
});

const onIframeLoad = () => {
  if (loadTimer) {
    clearTimeout(loadTimer);
    loadTimer = null;
  }
  loading.value = false;
};

const handleKeydown = (e) => {
  if (e.key === 'Escape' && reportPreviewStore.isFullscreen) {
    reportPreviewStore.setFullscreen(false);
  }
};

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeydown);
  reportPreviewStore.setFullscreen(false);
});
</script>

<style scoped>
.container {
  max-width: 100%;
}

.titleContainer {
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  position: relative;
}

.preview-body {
  width: 100%;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: all 0.3s ease;
}

.preview-body.preview-body--fullscreen {
  overflow: hidden;
}

.preview-body--fullscreen {
  position: fixed;
  top: 50px;
  left: 0;
  width: 100vw;
  height: calc(100vh - 50px) !important;
  background: #fff;
  padding: 0;
  margin: 0;
}

.preview-body--fullscreen :deep(.el-loading-mask) {
  height: calc(100vh - 50px);
}

.fullscreen-btn {
  margin-right: 20px;
}
</style>