<script setup>
import {ref, nextTick, computed, onMounted} from 'vue'
import {useVideoChatStore} from '@/stores/videoChat.js'
import planeSvg from '@/assets/plane.svg'
import planeDisableSvg from '@/assets/planeDisable.svg'
import stopSvg from '@/assets/stop.svg'
import ChatPanel from '@/components/experienceCenter/chat/ChatPanel.vue'
import {ChatService} from "@/services/chatService.js";
import {ModelService} from "@/services/modelService.js";
import {useRoute} from "vue-router";
import {useAIModelStore} from "@/stores/aiModel.js";
import {API_BASE_URL} from "@/utils/Constants.js";
import {ElMessage} from "element-plus";
import {CircleCheck, Close, Upload, Warning} from "@element-plus/icons-vue";
import {isModelAvailableById, isMLLMModelById, isLocalChatModelById} from "@/utils/ModelUtils.js"
import { getLogData, modifyLogData } from "@/api/dataService.js";

const token = ref("");

const chatStore = useVideoChatStore()
const modelStore = useAIModelStore()

const route = useRoute()
const inputBarContent = ref('')
const textareaRef = ref(null)
const modelList = ref([])        // 拉下来可选的模型名列表
// 参数滑条的范围设定
const paramRanges = ref({
  max_tokens: {min: 100, max: 100000, step: 1},
  temperature: {min: 0, max: 1, step: 0.01},
  top_p: {min: 0, max: 1, step: 0.01},
  top_k: {min: 0, max: 100, step: 10},
})

const curMaxToken = (modelId) => {
  const modelConfig = modelStore.getModelById(modelId)?.config;

  const maxTokenParam = modelConfig?.api_params_available[0].params.find(
    param => param.key === "max_tokens"
  );
  return maxTokenParam?.value ?? paramRanges.value.max_tokens.max;
}


const previewUrl = ref(null);
const filePath = ref('');
const fileNameOriginal = ref('');
const fileUploadStatus = ref('');
const sessionType = ref('video');
const fileInput = ref(null);
const isDragging = ref(false);

// 当前会话的 agent 列表
const agents = computed(() => {
  return chatStore.currentSession
      ? chatStore.currentSession.agents
      : []
})

const curModelId = ref('')
const curModelIds = ref([]);

const modelWhiteName = [
    "Qwen3.5-27B",
    "Qwen3.5-122B-A10B",
    "Qwen3-VL-32B-Instruct",
    "Qwen3-Omni-30B-A3B-Instruct",
    "Qwen2.5-Omni-7B",
    "Qwen3.6-27B",
    "Qwen3.8-27B",
    "Qwen3.6-35B-A3B",
];
const sendStatus = ref({
  loading: false,
  controller: null, // AbortController 用于中断流式
});
const initLoading=ref(true)
const hasModel = ref(true)

onMounted(async () => {
  try {
    if (modelStore.allIds.length === 0) {
      await modelStore.fetchModels()
    }
    // 过滤多模态模型
    modelList.value = modelStore.allIds.filter((id) => isMLLMModelById(id)
        && isModelAvailableById(id) && isLocalChatModelById(id) && modelWhiteName.includes(id));
  } catch (e) {
    console.error("获取模型列表失败", e)
  }
  token.value = localStorage.getItem('username');
  if(!chatStore.getHasLoadedLog){
    console.log("开始读取日志记录")
    await loadLog()
    chatStore.setHasLoadedLog(true)
  }
  // （2）处理 modelId
  let modelId = route.query.modelId
  if (modelId) {
    curModelId.value = modelId;
    curModelIds.value.push(curModelId.value);
    console.log('createSession1', modelId)
    const model = modelStore.getModelById(modelId)
    const modelParams = model.config.api_params_available[0].params.reduce((acc, item) => {
      if (item.key) {
        acc[item.key] = item.value;
      }
      return acc;
    }, {});
    chatStore.createSession('体验会话', modelId, modelParams)
  } else if (chatStore.currentSession === '' || chatStore.currentSession === null) {
    console.log("createSession2")
    // 默认要更新第一个模型的参数
    modelId = modelList.value[0]
    curModelId.value = modelId;
    curModelIds.value.push(curModelId.value);
    const model = modelStore.getModelById(modelId)
    if (!model) {
      hasModel.value = false
    }
    // 数组转对象
    const modelParams = model?.config.api_params_available[0].params.reduce((acc, item) => {
      if (item.key) {
        acc[item.key] = item.value;
      }
      return acc;
    }, {});
    chatStore.createSession('体验会话', modelId, modelParams)
  } else if (chatStore.currentSession.agents.length > 0) {
    //TODO模型对比时逻辑需更正
    curModelId.value = chatStore.currentSession.agents[0].modelId;
    curModelIds.value.push(curModelId.value);
  } else {
    curModelId.value = modelList.value[0];
    curModelIds.value.push(curModelId.value);
  }
  initLoading.value = false;
});

const loadLog = async () => {
 const response = await getLogData({
   user_id: token.value,
   type: "video",
 });
 const logData = response.data.data;

 console.log("logData");
 console.log(logData);

 chatStore.loadHistory(logData);
};

function onInput(e) {
  const ta = e.target
  ta.style.height = 'auto'
  ta.style.height = ta.scrollHeight + 'px'
}

function handleKeyDown(e) {
  if (e.key === 'Enter') {
    if (e.ctrlKey) {
      e.preventDefault();
      const startPos = textareaRef.value.selectionStart;
      const endPos = textareaRef.value.selectionEnd;
      inputBarContent.value =
          inputBarContent.value.substring(0, startPos) +
          '\n' +
          inputBarContent.value.substring(endPos);
      // 更新光标位置（需要nextTick确保DOM已更新）
      nextTick(() => {
        textareaRef.value.selectionStart = textareaRef.value.selectionEnd = startPos + 1;
        textareaRef.value.focus();
      });
      return;
    }
    e.preventDefault();
    send();
  }
}

// 支持的文件类型
const supportedFileTypes = ref([
  'mp4', 'webm', 'ogg'
])

// 处理拖拽进入
const handleDragOver = () => {
  if (!isDragging.value) {
    isDragging.value = true;
  }
};

// 处理拖拽离开
const handleDragLeave = (e) => {
  // 确保鼠标离开的是整个文档而不是子元素
  if (e.currentTarget.contains(e.relatedTarget)) return;
  isDragging.value = false;
};

// 处理文件放置
const handleDrop = async (e) => {
  isDragging.value = false;
  if (filePath !== '' && fileUploadStatus === '上传成功') {
    ElMessage.error('请删除当前文件再上传')
    return;
  }
  const files = Array.from(e.dataTransfer.files);
  await processFiles(files);
};

// 处理文件
const processFiles = async (files) => {
  if (files.length !== 1) {
    ElMessage.error('请选择单个文件')
    return;
  }
  if (!verifyFile(files[0])) {
    return
  }
  await uploadFile(files[0])
};

const verifyFile = (file) => {
  const allowedTypes = ['video/mp4', 'video/webm', 'video/ogg'];
  const maxSize = 50 * 1024 * 1024; // 50MB

  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('请选择mp4/webm/ogg格式文件')
    return false;
  }

  if (!supportedFileTypes.value.includes(file.name.split('.').pop().toLowerCase())) {
    ElMessage.error('请选择扩展名.mp4/.webm/.ogg的文件')
    return false;
  }

  if (file.size > maxSize) {
    ElMessage.error('请选择<50MB的文件')
    return false;
  }
  return true
}

const uploadFile = async (file) => {
  if (!file) {
    ElMessage.error('文件上传失败')
    console.error('获取选中文件失败')
    return
  }
  // 创建预览图
  const reader = new FileReader();
  reader.onload = (e) => {
    console.log('onload over')
    previewUrl.value = e.target.result;
  };
  reader.readAsDataURL(file);
  // 上传文件
  const formData = new FormData();
  formData.append('video', file);
  try {
    await ChatService.upLoadFile(formData, (response, isError) => {
      if (!isError) {
        filePath.value = response.filepath;
        console.log('filepath', filePath.value)
        fileUploadStatus.value = '上传成功'
        ElMessage.success('上传成功')
        fileNameOriginal.value = file.name.slice(-30)
      } else {
        fileUploadStatus.value = '上传失败'
        ElMessage.error('上传失败')
      }
    })
  } catch (error) {
    console.error('上传失败:', error);
    fileUploadStatus.value = '上传失败'
    ElMessage.error('上传失败')
  }
};

const selectFile = () => {
  fileInput.value.click();
};

const handleFileUpload = (event) => {
  processFiles(event.target.files)
}

const clearFile = () => {
  previewUrl.value = null;
  fileUploadStatus.value = ''
  filePath.value = ''
  fileNameOriginal.value = ''
}

async function send() {
  const inputText = inputBarContent.value.trim()
  if (!inputText) return
  const content = {'text': inputText, 'previewUrl': previewUrl.value}
  if (!content.previewUrl) {
    console.error('send content is null', content)
    ElMessage.error('请上传视频，否则请选择文本对话')
    return
  }
  if (filePath.value === '' || fileUploadStatus.value !== '上传成功') {
    ElMessage.error('上传失败，请重新上传')
    return
  }
  inputBarContent.value = ''
  await nextTick()
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
  sendStatus.value.loading = true;
  // 新增：创建 AbortController
  sendStatus.value.controller = new AbortController();

  // 1. 广播用户消息到所有 agents
  chatStore.addUserMessage(content)
  // 2. 对每个 agent 调用后端或 OpenAI 接口
  const session = chatStore.currentSession
  if (session) {
    // 并发发出所有请求，每个 Promise 内部完成后就把消息写入或打印错误
    const tasks = session.agents.map((agent, index) => {

      chatStore.updateSessionTitle(session.id, session.agents[0].messages[0].content.text)

      const msg = chatStore.addAssistantMessage("加载中...", agent.threadId)

      const model = modelStore.getModelById(agent.modelId);

      const curConfig = {
        temperature: agent.params.temperature || model.config.api_params_available[0].params?.find(p => p.key === 'temperature')?.value,
        max_tokens: agent.params.max_tokens || model.config.api_params_available[0].params?.find(p => p.key === 'max_tokens')?.value,
        top_p: agent.params.top_p || model.config.api_params_available[0].params?.find(p => p.key === 'top_p')?.value,
        top_k: agent.params.top_k || model.config.api_params_available[0].params?.find(p => p.key === 'top_k')?.value,
        messages: agent.messages.slice(0, -1).map(({role, content}) => ({
          role,
          content
        })),
      }

      ChatService.sendMsgStream(
          {
            endpoint: `${API_BASE_URL}stream_chat`,
            model: model.model_id,
            config: curConfig,
            signal: sendStatus.value.controller?.signal,
            query: content.text,
            filePath: filePath.value
          },
          (message) => {
            msg.content = message
          },
          (message, error) => {
            console.log("finish", msg.content)
            msg.isFinished = true
            sendStatus.value.loading = false
            if (error) {
              if (sendStatus.value.controller) {
                msg.content = message
              }
              console.error('请求失败')
            } else {
              console.log('请求成功')
            }
          },
          // model.config.extra_headers.reduce(function (acc, item) {
          //       if (item.key && item.key !== '') {
          //         acc[item.key] = item.value;
          //         return acc;
          //       }
          //     }, {}
          // )
      )
    });
    // 等待所有请求都 settle（成功或失败）再退出
    await Promise.all(tasks);
  }
}

async function stopSend() {
  if (sendStatus.value.controller) {
    sendStatus.value.controller.abort(); // 直接中断 fetch
    sendStatus.value.controller = null;
  }
  sendStatus.value.loading = false;
}


// 新建／切换／删除会话 绑定到界面按钮
function createSession() {
  chatStore.createSessionFromCurrent()
}

function addAgent(modelId) {
  // chatStore.addAgent(modelId)
  const model = modelStore.getModelById(modelId);
  const modelParams = model.config.api_params_available[0].params.reduce(
    (acc, item) => {
      if (item.key) {
        acc[item.key] = item.value;
      }
      return acc;
    },
    {}
  );
  chatStore.addAgent(modelId, modelParams);
  curModelIds.value = [];
  chatStore.currentSession.agents.forEach((agent) => {
    curModelIds.value.push(agent.modelId);
  });
  // 如果想额外确认，可加 confirm 弹窗
}

function onDeleteAgent(threadId) {
  // 假设你的 store 里有一个 removeAgent(threadId) 方法
  chatStore.removeAgent(threadId)
  curModelId.value = chatStore.currentSession.agents[0].modelId;
  curModelIds.value = [];
  chatStore.currentSession.agents.forEach((agent) => {
    curModelIds.value.push(agent.modelId);
  });
}

function switchSession(id) {
  chatStore.switchSession(id)
  curModelId.value = chatStore.currentSession.agents[0].modelId;
  curModelIds.value = [];
  chatStore.currentSession.agents.forEach((agent) => {
    curModelIds.value.push(agent.modelId);
  });
}

function deleteSession(id) {
  chatStore.deleteSession(id)
  modifyLogData({ user_id: token.value, chat_id: id })
  curModelIds.value=[]
  chatStore.currentSession.agents.forEach(agent=>{
    curModelIds.value.push(agent.modelId);
  })
  // 如果想额外确认，可加 confirm 弹窗
}

function sideEffectOfSwitchModel(threadId, modelId, val, index) {
  // console.log('modelId')
  // console.log(modelId)
  // console.log('val')
  // console.log(val)
  // console.log('chatStore.currentSession');
  // console.log(chatStore.currentSession);
  modelId = val;

  const model = modelStore.getModelById(modelId);
  const modelParams = model.config.api_params_available[0].params.reduce(
    (acc, item) => {
      if (item.key) {
        acc[item.key] = item.value;
      }
      return acc;
    },
    {}
  );

  // console.log("modelParams");
  // console.log(modelParams);

  if (
    chatStore.currentSession.agents &&
    chatStore.currentSession.agents.length > 0 &&
    chatStore.currentSession.agents[0].messages.length > 0
  ) {
    chatStore.createSession("新对话", modelId, modelParams);
  } else {
    chatStore.currentSession.agents[index].modelId = val;
  }

  chatStore.clearThreadMessages(threadId);
  // 同时更新面板参数
  chatStore.resetParams(threadId, modelParams);
  // createSession()
}

function isModelDisabled(modelId, thisThreadId) {
  // 只要存在一个 agent.modelId 等于 modelId，且 threadId != 当前 threadId，就视为已被占用
  return agents.value.some(a => a.modelId === modelId && a.threadId !== thisThreadId)
}

// —— 新增：控制“添加模型”对话框的状态 ——
const showAddModelDialog = ref(false)


const selectedModel = ref(null)    // 当前选中的模型

// 打开对话框，异步获取模型列表
async function openAddModelDialog() {
  try {
    showAddModelDialog.value = true
  } catch (e) {
    console.error("获取模型列表失败", e)
  }
}

// 确认添加
function confirmAddModel() {
  if (selectedModel.value !== null) {
    addAgent(selectedModel.value)
  }
  showAddModelDialog.value = false
  selectedModel.value = null
}


// 取消添加
function cancelAddModel() {
  showAddModelDialog.value = false
  selectedModel.value = null
}

</script>

<template>
  <div class="chatCenterContainer"
       @dragover.prevent="handleDragOver"
       @dragleave="handleDragLeave"
       @drop.prevent="handleDrop">

    <!-- 拖拽提示框 -->
    <transition name="fade">
      <div v-if="isDragging" class="drop-overlay">
        <div class="drop-hint-box">
          <el-icon class="hint-icon">
            <upload-filled/>
          </el-icon>
          <h3>松开上传文件</h3>
          <p>支持视频文件拖到当前页上传</p>
          <div class="supported-formats">
            <el-tag v-for="type in supportedFileTypes" :key="type" size="small">
              {{ type }}
            </el-tag>
          </div>
        </div>
      </div>
    </transition>

    <div class="pageContent" v-loading="initLoading" element-loading-text="加载中...">

      <div class="controlArea">
        <div class="controlPanel">
          <h4 class="controlPanelTitle">会话历史</h4>
          <div class="upperControlPanel">
            <div class="chatHistoryContainer">
              <div
                  class="chatHistoryItem"
                  v-for="sess in chatStore.sessions"
                  :key="sess.id"
                  @click="switchSession(sess.id)"
                  :class="{ 'active': chatStore.currentSessionId === sess.id }"
              >
                <div class="chatHistoryItemTitle">
                  <span v-show="chatStore.currentSessionId === sess.id"></span>
                  {{ sess.title }}
                </div>
                <div class="chatHistoryItemTime">
                  {{
                    sess.createdAt.slice(0, 16).replace('T', ' ')
                  }}
                </div>
                <button class="chatHistoryItemDeleteButton" @click.stop="deleteSession(sess.id)">✖</button>
              </div>
            </div>
          </div>
          <div class="lowerControlPanel">
            <div class="newSessionButtonContainer">
              <button class="newSessionButton" @click="createSession">
                开启新对话
              </button>
            </div>
            <div class="addModelButtonContainer">
              <button class="addModelButton"
                      :disabled="agents.length > 1"
                      @click="openAddModelDialog">添加模型对比
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="chatArea">

        <div class="chatPanelContainer" v-if="hasModel">
          <ChatPanel
              v-for="agent in agents"
              :key="agent.threadId"
              :thread-id="agent.threadId"
              :modelId="agent.modelId"
              :messages="agent.messages"
              :params="agent.params"
              :session-type="sessionType"
              @delete-thread="onDeleteAgent"
          />
        </div>
        <div v-else class="hasNoModel">暂无模型可用</div>
        <div class="inputPanelContainer" v-if="hasModel">
          <div class="inputBar">
            <textarea
                ref="textareaRef"
                class="input"
                placeholder="支持视频文件拖到当前页上传，请给我发送消息，Enter 发送 / Ctrl+Enter 换行"
                @input="onInput"
                @keydown="handleKeyDown"
                v-model="inputBarContent"
                rows="3"
            ></textarea>

            <div v-if="filePath === ''" class="fileUploadContainer">
              <input type="file" accept="video/*" @change="handleFileUpload" ref="fileInput" style="display: none"/>
              <el-button
                  circle
                  type="primary"
                  @click="selectFile"
                  :icon="Upload"
              >
              </el-button>
            </div>
            <div v-else class="fileUploadContainer">
              <el-button
                  circle
                  :type="fileUploadStatus === '上传成功' ? 'success' : 'danger'"
                  disabled
                  :icon="fileUploadStatus === '上传成功' ? CircleCheck : Warning"
              >
              </el-button>
              <span style="margin-left: 5px; margin-right: 10px">{{ fileNameOriginal }}{{ fileUploadStatus }}</span>
              <el-button
                  circle
                  type="info"
                  @click="clearFile"
                  :icon="Close"
              >
              </el-button>
            </div>

            <img
                v-if="!sendStatus.loading"
                :class="inputBarContent ? 'sendButton' : 'sendButtonDisable'"
                :src="inputBarContent ? planeSvg : planeDisableSvg"
                alt="send"
                @click="send"
            />
            <img
                v-else
                class="sendButton"
                :src="stopSvg"
                alt="send"
                @click="stopSend"
            />
          </div>
        </div>
      </div>

      <!-- 右侧参数设置区域，整块替换 -->
      <div class="controlArea">
        <div class="controlPanel">
          <h4 class="controlPanelTitle">参数设置</h4>
          <div class="upperControlPanel">
            <div class="threadSettingsContainer">
              <div
                  v-for="(agent, index) in agents"
                  :key="agent.threadId"
                  class="thread-settings"
              >
                <!-- thread 名称 -->
                <div class="thread-title" v-if="agents.length > 1 && index > 0">
                </div>
                <!-- 模型下拉切换 -->
                <div class="param-item">
                  <label>模型</label>
                  <el-select
                      class="dropDown"
                      v-model="curModelIds[index]"
                      @change="(val) => sideEffectOfSwitchModel(agent.threadId, agent.modelId,val,index)"
                      placeholder="请选择模型"
                      placement="bottom-end"
                  >
                    <!-- 1. prefix 插槽用来给输入框前面加一个自定义元素 -->
                    <template #prefix>
                      <span
                          v-if="agent.modelId"
                          style="display:flex; align-items:center; margin-right:6px;"
                      >
                        <img
                            :src="ModelService.getModelIcon(agent.modelId)"
                            style="width:20px; height:20px; object-fit:cover; border-radius:4px;"
                            alt="icon"
                        />
                      </span>
                    </template>
                    <!-- 2. 下拉列表里还是正常渲染图标 + 文本 -->
                    <el-option
                        v-for="m in modelList"
                        :key="m"
                        :value="m"
                        :label="m"
                        :disabled="isModelDisabled(m, agent.threadId)"
                    >
                      <span style="display:flex; align-items:center;">
                        <img
                            :src="ModelService.getModelIcon(m)"
                            style="width:20px; height:20px; margin-right:6px; object-fit:cover; border-radius:4px;"
                            alt="icon"
                        />
                        {{ m }}
                      </span>
                    </el-option>
                  </el-select>
                </div>
                <!-- 滑条参数 -->
                <div
                    v-for="(range, key) in paramRanges"
                    :key="key"
                    class="param-item"
                >
                  <label
                      :for="agent.threadId + '-' + key"
                      :class="{ 'disabled-label': !modelStore.getModelById(agent.modelId)?.config.api_params_available[0].params.find(item => item.key === key) }"
                  >
                    {{ ModelService.getParamName(key) }}
                  </label>
                  <div class="rangeInputContainer">
                    <input
                        class="sliderInput"
                        type="range"
                        :id="agent.threadId + '-' + key"
                        :min="range.min"
                        :max="key !== 'max_tokens' || !agent.modelId ? range.max : curMaxToken(agent.modelId)"
                        :value="agent.params[key]"
                        :step="range.step"
                        v-model="agent.params[key]"
                        :style="{
                           '--min': range.min,
                           '--max': key !== 'max_tokens' || !agent.modelId ? range.max : curMaxToken(agent.modelId),
                           '--value': agent.params[key]
                        }"
                        :disabled="!modelStore.getModelById(agent.modelId)?.config.api_params_available[0].params.find(item => item.key === key)"
                    />
                    <!-- 数字输入框：lazy 模式（只有 blur 或 Enter 时才同步）-->
                    <input
                        class="textInput"
                        type="number"
                        :id="agent.threadId + '-' + key + '-text'"
                        :min="range.min"
                        :max="key !== 'max_tokens' || !agent.modelId ? range.max : curMaxToken(agent.modelId)"
                        :step="range.step"
                        v-model="agent.params[key]"
                        :disabled="!modelStore.getModelById(agent.modelId)?.config.api_params_available[0].params.find(item => item.key === key)"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <transition
          name="modal-fade-in"
          appear
          :duration="{ enter: 500, leave: 500 }"
          mode="out-in"
      >
        <!-- —— 模态对话框 —— -->
        <div v-show="showAddModelDialog" class="modal-overlay">
          <transition
              name="modal-slide"
              appear
              :duration="{ enter: 500, leave: 500 }"
          >
            <div class="modal" v-if="showAddModelDialog">
              <h3>选择对比模型</h3>
              <ul class="model-list">
                <li v-for="m in modelList" :key="m">
                  <!-- 注意：name 要统一，id 要唯一 -->
                  <input
                      class="model-radio"
                      type="radio"
                      name="model"
                      :id="`model-${m}`"
                      v-model="selectedModel"
                      :disabled="isModelDisabled(m, '')"
                      :value="m"
                  />
                  <label
                      class="model-label"
                      :for="`model-${m}`"
                  >
                    <img class="modelIcon" :src="ModelService.getModelIcon(m)"/>
                    <span>
                      <span class="modelName">{{ m }}</span>
                      <span class="modelDescription">{{ ModelService.getModelDesc(m) }}</span>
                    </span>
                  </label>
                </li>
              </ul>
              <div class="modal-actions">
                <button :class="['btn', 'cancel']" @click="cancelAddModel">取消</button>
                <button :class="['btn', 'confirm']" @click="confirmAddModel">确认</button>
              </div>
            </div>
          </transition>

        </div>
      </transition>

    </div>
  </div>
</template>

<style scoped>

* {
  box-sizing: border-box;
}

.chatCenterContainer {
  box-sizing: border-box;
  padding: 28px;
  background-color: rgb(245, 245, 245);
  width: 100%;
  height: 100%;
  /* min-height: 100vh; */
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  gap: 16px;
  /* overflow: hidden; */
}

.pageTitle {
  flex: 0;
  color: #191919;
  font-size: 16px;
  font-weight: bold;
  font-family: '鸿蒙黑体', sans-serif;;
}

.pageContent {
  flex: 1;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  align-items: stretch;
  gap: 16px;
}

.chatArea {
  flex-grow: 1;
  flex-shrink: 1;
  flex-basis: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 16px;
}

.controlArea {
  flex-grow: 0;
  flex-shrink: 0;
  /* flex-basis: 256px; */
  /* width: 256px; */
  width:15%;
  display: flex;
}

.chatPanelContainer {
  flex: 1 1 0;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 16px;
}


.inputPanelContainer {
  flex: 0 0 64px;
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.inputBar {
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  gap: 16px;
  height: auto;
  padding: 16px 32px;
  border-radius: 6px;
  width: 100%;
  background-color: white;
  box-shadow: 0 2px 4px 0 rgb(0 0 0 / 20%);
}

.inputBar > .input {
  --font-size: 16px;
  flex: 1 1 0;
  outline: none;
  border: none;
  font-size: var(--font-size);
  line-height: 1.2;
  padding: 0;
  margin: 0;
  resize: none;
  color: black;
  min-height: calc(var(--font-size) * 1.2 * 1);
  height: calc(var(--font-size) * 1.2 * 1);
  max-height: calc(var(--font-size) * 1.2 * 5);
  overflow: auto;
  white-space: pre-wrap;
  font-family: "Arial", "Impact", sans-serif;
}

.input[contenteditable]:empty:before {
  content: attr(data-placeholder);
  color: #ccc;
}

.fileUploadContainer {
  display: flex;
  align-items: center;
  padding: 6px;
  border-radius: 8px;
}

.sendButtonDisable,
.sendButton {
  -webkit-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

.sendButton:hover {
  filter: brightness(1.2);
}

.sendButton:active {
  filter: brightness(1.5);
}

.controlPanel {
  height: 100%;
  width: 100%;
  background-color: white;
  border-radius: 16px;
  box-shadow: 0 2px 4px 0 rgb(0 0 0 / 20%);
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  gap: 16px;
}

.upperControlPanel {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  position: relative;
}

.lowerControlPanel {
  flex: 0 0 1;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 16px;
}

.controlPanelTitle {
  margin: 0;
  padding: 0;
}

.chatHistoryContainer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  max-height: 100%;
  min-height: 0; /* 同样要能收缩，否则 overflow 不生效 */
  height: 100%;
  overflow-y: auto; /* 打开纵向滚动 */
  overflow-x: hidden;
  position: relative;
  left: -8px;
  width: calc(100% + 16px);
}

.chatHistoryItem {
  width: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  padding: 8px 16px 8px 12px;
  gap: 4px;
  background-color: white;
  position: relative;
  transition: all 0.1s ease-in-out;;
}

.chatHistoryItem:hover {
  background-color: rgb(235, 235, 235, 0.5);
}

.chatHistoryItem.active {
  background-color: rgb(235, 235, 235, 0.65);
}

.chatHistoryItem:active {
  background-color: rgb(235, 235, 235, 0.8);
}

.chatHistoryItem > .chatHistoryItemTitle {
  font-size: 16px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 16px;
  vertical-align: middle;
}

.chatHistoryItem > .chatHistoryItemTitle span {
  display: inline-block;
  background-color: rgb(0, 210, 106);
  height: 12px;
  width: 12px;
  border-radius: 50%;
}

.chatHistoryItem > .chatHistoryItemTime {
  font-size: 14px;
  color: rgb(147, 147, 147);
}

.chatHistoryItemDeleteButton {
  border: none;
  outline: none;
  position: absolute;
  top: 8px;
  right: 8px;
  border-radius: 50%;
  background-color: transparent;
  font-size: 10px;
  line-height: 16px;
  width: 16px;
  height: 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  transition: all 0.1s ease-in-out;;
}

.chatHistoryItemDeleteButton:hover {
  background-color: red;
  color: white;
}

.addModelButton,
.newSessionButton {
  height: 40px;
  width: 100%;
  font-size: 14px;
  border: none;
  outline: none;
  border-radius: 8px;
  color: rgb(50, 50, 50);
  background-color: white;
  padding: 12px;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.1s ease-in-out;;
}

.newSessionButton {
  border: 1px solid rgb(201, 201, 201);
}

.newSessionButton:hover {
  background-color: rgb(240, 240, 240);
  border-color: rgb(171, 171, 171);
}

.newSessionButton:active {
  background-color: rgb(220, 220, 220);
  border-color: rgb(141, 141, 141);
}

.newSessionButtonContainer,
.addModelButtonContainer {
  margin: 0 15px;
}

.addModelButton {
  background-color: rgb(0, 102, 216);
  color: white;
}

.addModelButton:hover {
  filter: brightness(0.9);
}

.addModelButton:active {
  filter: brightness(1.25);
}

.addModelButton[disabled] {
  background-color: rgb(153, 153, 153);
}

.addModelButton[disabled]:hover {
  filter: unset;
}

.addModelButton[disabled]:active {
  filter: unset;
}

@keyframes fadeIn {
  0% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}

@keyframes fadeOut {
  0% {
    opacity: 1;
  }
  100% {
    opacity: 0;
  }
}

/* keyframes 已有 */
@keyframes slideIn {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

@keyframes slideOut {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(100%);
  }
}

/* enter */
.modal-fade-in-enter-active {
  animation: fadeIn .5s forwards;
}

/* leave */
.modal-fade-in-leave-active {
  animation: fadeOut .5s forwards;
}

/* enter */
.modal-slide-enter-active {
  animation: slideIn .5s forwards;
}

/* leave */
.modal-slide-leave-active {
  animation: slideOut .5s forwards;
}


/* 遮罩层 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  z-index: 999;
}

/* 弹窗框 */
.modal {
  background: #fff;
  padding: 24px;
  border-radius: 24px 0 0 24px;
  min-width: 400px;
  max-width: 80%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
}

.modal h3 {
  margin-top: 0;
}

.model-list {
  list-style: none;
  max-height: 100%;
  overflow-y: auto;
  margin-bottom: auto;
  position: relative;
  left: -16px;
  top: -16px;
  width: calc(100% + 16px * 2);
  padding: 16px;
}

.model-list li {
  margin-bottom: 8px;
  position: relative;
}

/* 隐藏原生圆点 */
.model-radio {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.model-radio[disabled] + .model-label {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #efefef;
}

.model-radio[disabled] + .model-label:hover {
  background-color: #efefef;
}

/* label 当作整个点击区域 */
.model-label {
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  padding: 16px 12px;
  background-color: rgb(240, 244, 253);
  border-radius: 16px;
  cursor: pointer;
  transition: all .2s;
  border: 1px solid transparent;
  gap: 16px;
}

/* hover 效果 */
.model-label:hover {
  background: rgb(224, 235, 250);
}

.model-label .modelIcon {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 8px;
}

.model-label .modelName {
  display: block;
  font-size: 16px;
}

.model-label .modelDescription {
  display: block;
  font-size: 12px;
  color: rgb(103, 103, 103);
}


/* 选中时高亮 */
.model-radio:checked + .model-label {
  border: 1px solid rgb(0, 103, 209);
  box-shadow: 0 0 4px 2px rgba(0, 0, 0, 0.15)
}

.model-radio:checked + .model-label .modelName {
  font-weight: bold;;
  color: rgb(0, 103, 209);
}

.model-radio:checked + .model-label .modelDescription {

}


.modal-actions {
  text-align: right;
}

.modal-actions .btn {
  margin-left: 8px;
  padding: 6px 24px;
  border: none;
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
}

.btn.confirm {
  background: #0066d8;
}

.btn.cancel {
  background: #aaa;
}

.modal-actions .btn:hover {
  filter: brightness(1.1);
}

.threadSettingsContainer {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: flex-start;
  width: calc(100% + 8px);
  position: relative;
  left: -4px;
  padding: 4px;
  max-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.thread-settings {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.thread-title {
  font-weight: bold;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 8px 0;
  font-size: 16px;
  border-bottom: 1px solid rgb(223, 223, 223);
  color: #a8a8a8;
  margin: 16px 24px;
}

.param-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.param-item .dropDown {
  margin-top: 6px;
  margin-bottom: 6px;
}

.param-item label {
  width: 100%;
  display: block;
  font-size: 14px;
  font-weight: bold;
}

.disabled-label {
  color: grey;
}

.rangeInputContainer {
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.rangeInputContainer .sliderInput {
  flex: 1 1 0;
}

.rangeInputContainer .textInput {
  flex: 0 0 1;
  width: 60px;
  text-align: right;
  border: 1px solid rgb(221, 221, 221);
  padding: 4px 4px;
  border-radius: 4px;
  font-size: 14px;
  appearance: textfield;
}

.rangeInputContainer .textInput:focus {
  border: 1px solid rgb(200, 200, 200);
  outline: none;
}

/* Chrome, Safari, Edge, Opera */
.rangeInputContainer .textInput::-webkit-outer-spin-button,
.rangeInputContainer .textInput::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Firefox */
.rangeInputContainer .textInput[type="number"] {
  -moz-appearance: textfield;
}


/* --------- 公共主样式 ---------- */
input[type=range] {
  -webkit-appearance: none; /* 去掉默认样式 */
  width: 100%;
  height: 4px; /* 轨道高度 */
  margin: 0;
  background: rgb(223, 223, 223); /* 用浅蓝做底色 */
  border-radius: 2px;
  /* 用 background‐image + background‐size 来画已滑过的深蓝部分 */
  background-image: linear-gradient(rgb(0, 103, 209), rgb(0, 103, 209));
  background-repeat: no-repeat;
  /* 下面三个变量我们在模板里挂上，让它能动态变化 */
  background-size: calc((var(--value) - var(--min)) / (var(--max) - var(--min)) * 100%) 100%;
}


input[type=range]:focus {
  outline: none;
}

/* --------- Webkit 系列 (Chrome/Safari/Edge) ---------- */
input[type=range]::-webkit-slider-runnable-track {
  height: 4px;
  background: transparent; /* 已经用外层 background 画了，这里透明即可 */
}

input[type=range]::-webkit-slider-thumb {
  --thumb: 16px;
  --track: 3px;
  -webkit-appearance: none;
  width: var(--thumb);
  height: var(--thumb);
  background: rgb(255, 255, 255);
  border: var(--track) solid rgb(0, 103, 209); /* 深蓝边框 */
  border-radius: 50%;
  margin-top: calc((var(--thumb) - var(--track)) / 2 * -1); /* =-(thumb/2 - track/2)，让 thumb 居中 */
  cursor: pointer;
}

input[type=range][disabled] {
  background-image: linear-gradient(rgb(126, 126, 126), rgb(126, 126, 126));
}


input[type=range][disabled]::-webkit-slider-thumb {
  border: var(--track) solid rgb(126, 126, 126); /* 深蓝边框 */
}

.drop-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 2000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.drop-hint-box {
  background-color: white;
  padding: 30px 40px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  max-width: 500px;
}

.hint-icon {
  font-size: 50px;
  color: var(--el-color-primary);
  margin-bottom: 15px;
}

.supported-formats {
  margin-top: 15px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

/* 过渡动画 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

</style>