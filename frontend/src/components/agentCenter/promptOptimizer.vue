<template>
  <div class="prompt-optimizer-container">
    <!-- 加载中 -->
    <div v-if="status === 'loading'" class="prompt-status">
      <el-icon class="loading-icon" :size="48"><Loading /></el-icon>
      <p class="status-text">正在连接 Prompt优化器 服务...</p>
    </div>

    <!-- 加载成功 -> 用 iframe 内嵌目标页面 -->
    <iframe
      v-else-if="status === 'loaded' && targetUrl"
      :src="targetUrl"
      class="prompt-iframe"
      frameborder="0"
    ></iframe>

    <!-- 全部不可达 -->
    <div v-else-if="status === 'unreachable'" class="prompt-error">
      <el-icon :size="64" color="#E6A23C"><WarningFilled /></el-icon>
      <h2>您的页面已丢失，请联系管理员（w00649384）排查</h2>
      <el-button type="primary" @click="retry" style="margin-top: 20px;">重新连接</el-button>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import { Loading, WarningFilled } from '@element-plus/icons-vue';

const URL_CANDIDATES = [
  'http://100.100.50.160:5173/',
  'http://100.100.136.146:10129/',
];

const status = ref<'loading' | 'loaded' | 'unreachable'>('loading');
const targetUrl = ref('');

/** 检测单个 URL 是否可达 */
async function checkUrl(url: string, timeoutMs = 5000): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    await fetch(url, {
      method: 'HEAD',
      mode: 'no-cors',
      signal: controller.signal,
    });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function tryConnect() {
  status.value = 'loading';

  // 并行检测所有 URL，哪个先返回 true 就用哪个
  const result = await Promise.any(
    URL_CANDIDATES.map(async (url) => {
      const reachable = await checkUrl(url);
      if (reachable) return url;
      throw new Error(`unreachable: ${url}`);
    })
  );

  targetUrl.value = result;
  status.value = 'loaded';
}

function retry() {
  tryConnect();
}

onMounted(() => {
  tryConnect();
});
</script>

<style scoped>
.prompt-optimizer-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  width: 100%;
  min-height: 400px;
}

.prompt-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.loading-icon {
  animation: rotating 1.5s linear infinite;
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-text {
  font-size: 16px;
  color: #606266;
}

.prompt-iframe {
  width: 100%;
  height: 100%;
  border: none;
  min-height: calc(100vh - 80px);
}

.prompt-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.prompt-error h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
</style>