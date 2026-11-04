<template>
  <div class="api-key-page">
    <!-- API 基础信息 -->
    <el-card shadow="never" class="info-card">
      <template #header>
        <span class="card-title">API 接入信息</span>
      </template>
      <div class="info-item">
        <span class="info-label">调用地址（黄区）：</span>
        <el-tag type="info" class="info-value">{{ apiBaseUrlYellow }}</el-tag>
        <el-button
          text
          type="primary"
          size="small"
          @click="copyText(apiBaseUrlYellow)"
          style="margin-left: 8px"
        >
          复制
        </el-button>
      </div>
      <div class="info-item">
        <span class="info-label">调用地址（绿区）：</span>
        <el-tag type="info" class="info-value">{{ apiBaseUrlGreen }}</el-tag>
        <el-button
          text
          type="primary"
          size="small"
          @click="copyText(apiBaseUrlGreen)"
          style="margin-left: 8px"
        >
          复制
        </el-button>
      </div>
      <div class="info-item">
        <span class="info-label">兼容接口：</span>
        <el-space>
          <el-tag>OpenAI API</el-tag>
          <el-tag>Anthropic API</el-tag>
        </el-space>
      </div>
    </el-card>

    <!-- API Key 管理 -->
    <el-card shadow="never" class="api-key-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">我的 API Key</span>
          <el-button type="primary" @click="handleApplyKey" :disabled="!!userApiKey" :loading="loading">
            申请 API Key
          </el-button>
        </div>
      </template>

      <div v-if="userApiKey" class="api-key-display">
        <div class="key-row">
          <span class="key-label">API Key：</span>
          <el-input
            :model-value="maskedKey"
            :type="showKey ? 'text' : 'password'"
            readonly
            style="width: 420px"
          />
          <el-button
            text
            type="primary"
            size="small"
            @click="showKey = !showKey"
            style="margin-left: 8px"
          >
            {{ showKey ? '隐藏' : '显示' }}
          </el-button>
          <el-button
            text
            type="primary"
            size="small"
            @click="copyText(userApiKey)"
            style="margin-left: 4px"
          >
            复制
          </el-button>
        </div>
        <div class="key-hint">
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="请妥善保管您的 API Key，请勿泄露给他人。每个用户仅允许申请一个 API Key。"
          />
        </div>
      </div>
      <div v-else class="api-key-empty">
        <el-empty description="暂未申请 API Key" />
      </div>
    </el-card>

    <!-- 支持的模型列表 -->
    <el-card shadow="never" class="model-card">
      <template #header>
        <span class="card-title">当前支持模型</span>
      </template>
      <el-table :data="modelList" stripe style="width: 100%">
        <el-table-column prop="model_id" label="模型 ID" width="400" />
        <el-table-column prop="model_name" label="模型名称" width="300" />
      </el-table>
    </el-card>

    <!-- 调用示例 -->
    <el-card shadow="never" class="example-card">
      <template #header>
        <span class="card-title">调用示例</span>
      </template>

      <!-- curl 示例 -->
      <div class="example-section">
        <h4>1. cURL</h4>
        <pre class="code-block"><code>{{ curlExample }}</code></pre>
        <el-button text type="primary" size="small" @click="copyText(curlExample)">
          复制
        </el-button>
      </div>

      <!-- Python 示例 -->
      <div class="example-section">
        <h4>2. Python</h4>
        <pre class="code-block"><code>{{ pythonExample }}</code></pre>
        <el-button text type="primary" size="small" @click="copyText(pythonExample)">
          复制
        </el-button>
      </div>

      <!-- Postman 示例 -->
      <div class="example-section">
        <h4>3. Postman</h4>
        <el-table :data="postmanExample" stripe style="width: 100%">
          <el-table-column prop="method" label="Method" width="100">
            <template #default>
              <el-tag type="success">POST</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="url" label="URL" />
        </el-table>
        <div style="margin-top: 12px">
          <p><strong>Headers：</strong></p>
          <pre class="code-block"><code>{{ postmanHeaders }}</code></pre>
        </div>
        <div style="margin-top: 12px">
          <p><strong>Body (raw / JSON)：</strong></p>
          <pre class="code-block"><code>{{ postmanBody }}</code></pre>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import { ElMessage } from "element-plus";
import axios from "axios";
import { API_BASE_URL } from "@/utils/Constants.js";

const apiBaseUrlYellow = "http://7.216.57.45:50424/v1";
const apiBaseUrlGreen = "http://100.100.136.146:50424/v1";

// ===== API Key 状态 =====
const userApiKey = ref("");
const showKey = ref(false);
const loading = ref(false);

const maskedKey = ref("");

/** 获取当前用户的 work_id（从 localStorage） */
function getWorkId() {
  return localStorage.getItem("username") || "";
}

// 监听 userApiKey 变化，更新掩码显示
watch(userApiKey, (val) => {
  if (val) {
    maskedKey.value = val.substring(0, 6) + "****" + val.substring(val.length - 4);
  } else {
    maskedKey.value = "";
  }
});

/** 获取当前用户已申请的 API Key */
async function fetchApiKey() {
  const workId = getWorkId();
  if (!workId) return;
  try {
    const { data } = await axios.get(API_BASE_URL + "user_statistics/get_api_key", {
      params: { work_id: workId },
    });
    if (data.code === 0 && data.data && data.data.api_key) {
      userApiKey.value = data.data.api_key;
    }
  } catch (e) {
    console.error("获取 API Key 失败", e);
  }
}

/** 申请 API Key */
async function handleApplyKey() {
  const workId = getWorkId();
  if (!workId) {
    ElMessage.warning("未获取到用户信息，请重新登录");
    return;
  }
  loading.value = true;
  try {
    const { data } = await axios.post(API_BASE_URL + "user_statistics/apply_api_key", {
      work_id: workId,
    });
    if (data.code === 0) {
      userApiKey.value = data.data.api_key;
      ElMessage.success("API Key 申请成功！");
    } else {
      ElMessage.error(data.message || "申请失败");
    }
  } catch (e) {
    console.error("申请 API Key 失败", e);
    ElMessage.error("申请 API Key 失败，请稍后重试");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchApiKey();
});

// ===== 支持模型列表 =====
const modelList = [
  { model_id: "DeepSeek-V4-Flash-w8a8-mtp", model_name: "dsv4" },
];

// ===== 调用示例 =====
const curlExample = `curl http://7.216.57.45:50424/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "dsv4",
    "messages": [
      {
        "role": "user",
        "content": "1+1=?"
      }
    ],
    "max_token": 131000,
    "chat_template_kwargs": {
      "thinking": true,
      "reasoning_effort": "max"
    },
    "temperature": 0.5
  }'`;

const pythonExample = `import requests

url = "http://7.216.57.45:50424/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_API_KEY"
}
payload = {
    "model": "dsv4",
    "messages": [
        {
            "role": "user",
            "content": "1+1=?"
        }
    ],
    "max_token": 131000,
    "chat_template_kwargs": {
        "thinking": true,
        "reasoning_effort": "max"
    },
    "temperature": 0.5
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`;

const postmanExample = [
  { method: "POST", url: "http://7.216.57.45:50424/v1/chat/completions" },
];

const postmanHeaders = `Authorization: Bearer YOUR_API_KEY
Content-Type: application/json`;

const postmanBody = `{
    "model": "dsv4",
    "messages": [
        {
            "role": "user",
            "content": "1+1=?"
        }
    ],
    "max_token": 131000,
    "chat_template_kwargs": {
        "thinking": true,
        "reasoning_effort": "max"
    },
    "temperature": 0.5
}`;

/** 复制文本到剪贴板（优先 Clipboard API，失败时回退到 execCommand） */
function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      ElMessage.success("已复制到剪贴板");
    }).catch(() => {
      legacyCopyText(text);
    });
  } else {
    legacyCopyText(text);
  }
}

function legacyCopyText(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    document.execCommand("copy");
    document.body.removeChild(textarea);
    ElMessage.success("已复制到剪贴板");
  } catch (err) {
    document.body.removeChild(textarea);
    ElMessage.error("复制失败，请手动复制");
    console.error("复制失败:", err);
  }
}
</script>

<style scoped>
.api-key-page {
  padding: 16px 0;
}

.info-card,
.api-key-card,
.model-card,
.example-card {
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
  min-width: 100px;
}

.info-value {
  font-family: monospace;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.api-key-display {
  padding: 12px 0;
}

.key-row {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.key-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
  min-width: 100px;
}

.api-key-empty {
  padding: 20px 0;
}

.example-section {
  margin-bottom: 24px;
}

.example-section h4 {
  font-size: 15px;
  margin-bottom: 8px;
  color: #303133;
}

.code-block {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre;
  font-family: "Courier New", Courier, monospace;
  margin: 0 0 8px 0;
}

.key-hint {
  margin-top: 8px;
}
</style>