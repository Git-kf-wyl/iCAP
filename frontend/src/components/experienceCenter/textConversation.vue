<script setup lang="ts">
import { ref, nextTick, computed, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import planeSvg from '@/assets/plane.svg'
import planeDisableSvg from '@/assets/planeDisable.svg'
import stopSvg from '@/assets/stop.svg'
import ChatPanel from '@/components/experienceCenter/chat/ChatPanel.vue'
import { ChatService } from "@/services/chatService.js";
import { ModelService } from "@/services/modelService.js";
import { useRoute } from "vue-router";
import { useAIModelStore } from "@/stores/aiModel.js";
import { API_BASE_URL } from "@/utils/Constants.js";
import { isModelAvailableById, isLocalChatModelById } from "@/utils/ModelUtils.js"
import { getLogData, modifyLogData } from '@/api/dataService.js'
import { Plus, Close, Warning, Picture, Search, Tickets, Download } from '@element-plus/icons-vue'
import { ElMessage,UploadProps,UploadRawFile,UploadInstance } from 'element-plus'
import PPTGenerator from '@/components/agentCenter/officeAssistant.vue'
import DeepResearch from '@/components/agentCenter/deepResearch.vue'
import {getLocalISOString} from "@/utils/TimeUtils.js";
import Recorder from 'js-audio-recorder';

const token = ref("");
const chatStore = useChatStore()
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
  if (!modelConfig) return paramRanges.value.max_tokens.max;

  const maxTokenParam = modelConfig.api_params_available[0]?.params.find(
    param => param.key === "max_tokens"
  );
  return maxTokenParam?.value ?? paramRanges.value.max_tokens.max;
}

const sessionType = ref('text');

// 当前会话的 agent 列表
const agents = computed(() => {
  return chatStore.currentSession
      ? chatStore.currentSession.agents
      : []
})

const curModelId = ref('')
const curModelIds = ref([])

const sendStatus = ref({
  loading: false,
  controller: null, // AbortController 用于中断流式
});

const modelWhiteName = [
    "DeepSeek-V4.1-Flash-w8a8",
    "DeepSeek-V4-Flash-0731-w8a8",
    "DeepSeek-V4-Flash_w8a8_mtp",
    "MiniMax-M2.5",
    "Qwen3.5-27B",
    "Qwen3.5-122B-A10B",
    "Qwen3-32B",
    "gpt-5-thinking-all",
    "Qwen3-Next-80B-A3B-Thinking",
    "Qwen3-4B-0918",
    "Qwen3-Next-80B-A3B-Instruct",
    "Qwen3-Omni-30B-A3B-Instruct",
    "Qwen3-VL-32B-Instruct",
    // "gemini-3-pro-preview(外网api,请注意信息安全)",
    // "gemini-3-pro-preview-thinking(外网api,请注意信息安全)",
    "DeepSeek-V3.2(chat模型,外网api,请注意信息安全)",
    "DeepSeek-V3.2(reasoner模型,外网api,请注意信息安全)",
    "GLM-5(外网api,请注意信息安全)",
    'Qwen2.5-Omni-7B',
    'Qwen3.6-27B',
    'Qwen3.6-35B-A3B',
    'gemma-4-12B-it',
    'gemma-4-31B-it',
    'openpangu-2.0-flash',
    'openpangu-2.0-pro',
    'LongCat-2.0',
];

const imageModelWhiteName = [
  "Qwen3.5-27B",
  "Qwen3.5-122B-A10B",
  "Qwen3-VL-32B-Instruct",
  "Qwen3-Omni-30B-A3B-Instruct",
  "Qwen2.5-Omni-7B",
  'Qwen3.6-27B',
  "Qwen3.8-27B",
  'Qwen3.6-35B-A3B',
  'gemma-4-12B-it',
  'gemma-4-31B-it'
];

const audioModelWhiteName = [
    "Qwen3.5-27B",
    "Qwen3.5-122B-A10B",
    "Qwen3-Omni-30B-A3B-Instruct",
    "Qwen2.5-Omni-7B"
];

const videoModelWhiteName = [
  "Qwen3-VL-32B-Instruct",
  "Qwen3-Omni-30B-A3B-Instruct",
  'Qwen2.5-Omni-7B',
  'gemma-4-12B-it',
  'gemma-4-31B-it'
];

const initLoading=ref(true)

// 按时间标签对会话进行分组
const groupedSessions = computed(() => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  const groups = {};

  chatStore.sessions.forEach(sess => {
    const createdDate = new Date(sess.createdAt);
    let label;

    if (createdDate >= today) {
      label = '今天';
    } else if (createdDate >= sevenDaysAgo) {
      label = '7天内';
    } else if (createdDate >= thirtyDaysAgo) {
      label = '30天内';
    } else {
      const year = createdDate.getFullYear();
      const month = String(createdDate.getMonth() + 1).padStart(2, '0');
      label = `${year}-${month}`;
    }

    if (!groups[label]) {
      groups[label] = [];
    }
    groups[label].push(sess);
  });

  // 定义标签排序顺序
  const labelOrder = ['今天', '7天内', '30天内'];
  const sortedGroups = [];
  Object.keys(groups).sort((a, b) => {
    const idxA = labelOrder.indexOf(a);
    const idxB = labelOrder.indexOf(b);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    // For YYYY-MM format, sort descending (newest first)
    return b.localeCompare(a);
  }).forEach(label => {
    sortedGroups.push({ label, sessions: groups[label] });
  });

  return sortedGroups;
});

onMounted(async () => {
  console.log('createSession')
  // （1）先做你原来要做的事情，比如拉模型列表
  try {
    if (modelStore.allIds.length === 0) {
      await modelStore.fetchModels()
    }
    modelList.value = modelStore.allIds.filter((id) => isModelAvailableById(id)
    //  && isLocalChatModelById(id)
     );
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
    const modelParams = model.config.api_params_available[0]?.params.reduce((acc, item) => {
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
    // 数组转对象
    const modelParams = model.config.api_params_available[0]?.params.reduce((acc, item) => {
      if (item.key) {
        acc[item.key] = item.value;
      }
      return acc;
    }, {});
    chatStore.createSession('体验会话', modelId, modelParams)
  }else if(chatStore.currentSession.agents.length>0){
    //TODO模型对比时逻辑需更正
    curModelId.value = chatStore.currentSession.agents[0].modelId;
    curModelIds.value.push(curModelId.value);
  }else{
    curModelId.value = modelList.value[0];
    curModelIds.value.push(curModelId.value);
  }
  initLoading.value=false;
  adjustHeight();
})

const loadLog=async()=>{
  const response=await getLogData({
    user_id:token.value,
    type:'text'
  })
  const logData=response.data.data

  // console.log('logData');
  // console.log(logData);

  chatStore.loadHistory(logData)
}

function onInput(e) {
  // const ta = e.target
  // ta.style.height = 'auto'
  // ta.style.height = ta.scrollHeight + 'px'
  adjustHeight()
}

const currentHeight = ref(72); // 初始高度
const overflowY = ref('hidden'); // 滚动条状态
const HEIGHT_LEVELS = [72, 96, 120, 144, 168, 192];
const MAX_HEIGHT = HEIGHT_LEVELS[HEIGHT_LEVELS.length - 1];
const adjustHeight = () => {
  nextTick(() => {
    const textarea = textareaRef.value;
    if (!textarea) return;

    // 关键修复：临时重置高度获取准确的scrollHeight
    const originalHeight = textarea.style.height;
    textarea.style.height = 'auto'; // 重置为最小高度

    const style = window.getComputedStyle(textarea);
    const borderHeight = parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
    const requiredHeight = textarea.scrollHeight + borderHeight;

    // 恢复原高度避免闪烁
    textarea.style.height = originalHeight;

    // 1. 确定目标挡位（精确匹配最小满足高度）
    let targetHeight = HEIGHT_LEVELS[0]; // 默认最小高度
    for (const level of HEIGHT_LEVELS) {
      if (requiredHeight <= level) {
        targetHeight = level;
        break;
      }
      // 确保不超过最大高度
      if (level === MAX_HEIGHT) {
        targetHeight = MAX_HEIGHT;
      }
    }

    // 2. 更新高度状态
    currentHeight.value = targetHeight;

    // 3. 智能滚动条控制
    overflowY.value = (requiredHeight > MAX_HEIGHT) ? 'auto' : 'hidden';
  });
};

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

const handlePaste = (event) => {
  // 获取剪贴板数据
  const clipboardData = event.clipboardData || window.clipboardData;
  console.log("clipboardData");
  console.log(clipboardData);
  if (!clipboardData) return;

  // 获取图片文件
  const imageFiles = Array.from(clipboardData.items)
    .filter((item) => item.type.includes("image"))
    .map((item) => item.getAsFile());
  console.log("imageFiles");
  console.log(imageFiles);

  // 如果没有图片则直接返回
  if (imageFiles.length === 0) return;

  // 阻止默认粘贴行为
  event.preventDefault();

  // 只处理第一张图片
  const imageFile = imageFiles[0];
  if (!imageFile) return;

  // 触发上传逻辑
  if(canUseImage.value){
    uploadFile(imageFile,'image');
  } else{
    ElMessage.warning("当前模型不支持图片上传");
  }
};

const isDeepResearch=ref(false)
const deepResearchType=ref('fast')
const isThink =ref(false)
const isOnline=ref(false)

async function send() {
  let inputText = inputBarContent.value.trim();
  if (!inputText) {
    console.error("send content is null");
    // ElMessage.error("请上传图片");
    // return;
    if(previewUrl.value===''){
      console.log('无文本')
      return;
    }
    if(previewUrl.value.startsWith('data:image/')){
      inputText = '提取图中的文字，不要输出任何其他内容'
    } else if(previewUrl.value.startsWith('data:audio/')){
      inputText = '使用音频使用的语言识别音频中内容，不要输出任何其他内容'
    } else if(previewUrl.value.startsWith('data:video/')){
      inputText = '识别视频内容，不要输出任何其他内容'
    }
    else{
      console.log('无文本')
      return;
    }
  }
  let content = null
  if (previewUrl.value) {
    if(previewUrl.value.startsWith('data:image/') && !canUseImage.value){
      ElMessage.warning("本模型不支持图片上传，仅进行文本对话");
      content = inputText
    } else if(previewUrl.value.startsWith('data:audio/') && !canUseAudio.value){
      ElMessage.warning("本模型不支持音频上传，仅进行文本对话");
      content = inputText
    } else if(previewUrl.value.startsWith('data:video/') && !canUseVideo.value){
      ElMessage.warning("本模型不支持视频上传，仅进行文本对话");
      content = inputText
    }
    else{
      content = { text: inputText, previewUrl: previewUrl.value }
    }
  }
  else {
    content = inputText
  }
  if (!content) return
  inputBarContent.value = ''
  await nextTick()
  // if (textareaRef.value) {
  //   textareaRef.value.style.height = 'auto'
  // }
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

      if(content.previewUrl){
        chatStore.updateSessionTitle(session.id, session.agents[0].messages[0].content.text)
      }
      else{
        chatStore.updateSessionTitle(session.id, session.agents[0].messages[0].content)
      }

      const msg = chatStore.addAssistantMessage("加载中...", agent.threadId)

      const model = modelStore.getModelById(agent.modelId);

      const curConfig = {
        temperature: agent.params.temperature ?? model.config.api_params_available[0]?.params?.find(p => p.key === 'temperature')?.value,
        max_tokens: agent.params.max_tokens || model.config.api_params_available[0]?.params?.find(p => p.key === 'max_tokens')?.value,
        top_p: agent.params.top_p ?? model.config.api_params_available[0]?.params?.find(p => p.key === 'top_p')?.value,
        top_k: agent.params.top_k ?? model.config.api_params_available[0]?.params?.find(p => p.key === 'top_k')?.value,
        messages: agent.messages.slice(0, -1).map(({role, content}) => ({
          role,
          content
        })),
      }

      return ChatService.sendMsgStream(
          {
            chatId:session.id,
            endpoint: `${API_BASE_URL}stream_chat`,
            model: model.model_id,
            config: curConfig,
            signal: sendStatus.value.controller?.signal,
            query: content.previewUrl?content.text:content,
            filePath: filePath.value,
            userId:token.value,
            isDeepResearch:isDeepResearch.value,
            deepResearchType:deepResearchType.value,
            isThink:isThink.value
          },
          (message) => {
            msg.content = message
          },
          (message, error) => {
            console.log("finish", msg.content)
            msg.isFinished = true
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
    await Promise.allSettled(tasks);
    sendStatus.value.loading = false;
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
  // 删除当前上传的文件
  // previewUrl.value=''
  // filePath.value=''
  chatStore.createSessionFromCurrent()
}

function addAgent(modelId) {
  const model = modelStore.getModelById(modelId)
  const modelParams = model.config.api_params_available[0]?.params.reduce((acc, item) => {
    if (item.key) {
      acc[item.key] = item.value;
    }
    return acc;
  }, {});
  chatStore.addAgent(modelId,modelParams)
  // 如果想额外确认，可加 confirm 弹窗
  curModelIds.value = [];
  chatStore.currentSession.agents.forEach(agent=>{
    curModelIds.value.push(agent.modelId);
  })
  // console.log('curModelIds')
  // console.log(curModelIds.value)
}

function onDeleteAgent(threadId) {
  // 假设你的 store 里有一个 removeAgent(threadId) 方法
  chatStore.removeAgent(threadId)
  curModelId.value=chatStore.currentSession.agents[0].modelId;
  curModelIds.value = [];
  chatStore.currentSession.agents.forEach(agent=>{
    curModelIds.value.push(agent.modelId);
  })
}

function switchSession(id) {
  chatStore.switchSession(id)
  curModelId.value = chatStore.currentSession.agents[0].modelId;
  curModelIds.value = [];
  chatStore.currentSession.agents.forEach(agent=>{
    curModelIds.value.push(agent.modelId);
  })
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

function sideEffectOfSwitchModel(threadId, modelId,val,index) {
  // console.log('modelId')
  // console.log(modelId)
  // console.log('val')
  // console.log(val)
  // console.log('chatStore.currentSession');
  // console.log(chatStore.currentSession);
  modelId = val

  const model = modelStore.getModelById(modelId)
  const modelParams = model.config.api_params_available[0]?.params.reduce((acc, item) => {
    if (item.key) {
      acc[item.key] = item.value;
    }
    return acc;
  }, {});

  // console.log('modelParams')
  // console.log(modelParams)

  if(chatStore.currentSession.agents&&chatStore.currentSession.agents.length>0 && chatStore.currentSession.agents[0].messages.length>0){
    chatStore.createSession('新对话',modelId,modelParams)
  }else{
    chatStore.currentSession.agents[index].modelId=val;
  }

  chatStore.clearThreadMessages(threadId)
  // 同时更新面板参数
  chatStore.resetParams(threadId, modelParams)

  nextTick(() => {
    if (previewUrl.value !== '') {
      // console.log('previewUrl.value');
      // console.log(previewUrl.value);
      if (!canUseImage.value && previewUrl.value.startsWith('data:image/')) {
        console.log('can\'t use image')
      } else if (!canUseAudio.value && previewUrl.value.startsWith('data:audio/')) {
        console.log('can\'t use audio')
      } else if (!canUseVideo.value && previewUrl.value.startsWith('data:video/')) {
        console.log('can\'t use video')
      } else {
        console.log('模型没问题')
      }
    }
  })
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

// const handleUploadCommand = (command) => {
//   // 根据选择的命令执行不同操作
//   switch (command) {
//     case 'document':
//       console.log('上传文档')
//       // 这里添加上传文档逻辑
//       break
//     case 'image':
//       console.log('上传图片')
//       // 这里添加上传图片逻辑
//       break
//     case 'audio':
//       console.log('上传音频')
//       // 这里添加上传音频逻辑
//       break
//     case 'video':
//       console.log('上传视频')
//       // 这里添加上传视频逻辑
//       break
//   }
// }

const uploadImage = ref<UploadInstance>()
const uploadAudio = ref(null);
const uploadVideo = ref(null);

const filePath = ref('')
const previewUrl = ref('')
const fileUploadStatus = ref('')
const fileNameOriginal = ref("");

const uploadFile = async (rawFile,type) => {
  // 判断 rawFile 本身是否是文件（File 对象）
  const isRawFileValid = rawFile instanceof File || rawFile instanceof Blob;

  // 判断是否是包含 file 属性的包装对象
  const isWrappedFile = rawFile && rawFile.file instanceof File;

  // 提取最终文件
  const file = isRawFileValid ? rawFile : (isWrappedFile ? rawFile.file : null);

  if (!file) {
    ElMessage.error("文件上传失败");
    console.error("获取文件对象失败", rawFile);
    return;
  }
  // 创建预览图
  const reader = new FileReader();
  reader.onload = (e) => {
    console.log("onload over");
    previewUrl.value = e.target.result;
  };
  reader.readAsDataURL(file);
  // 上传文件
  const formData = new FormData();
  formData.append(type, file);
  try {
    await ChatService.upLoadFile(formData, (response) => {
        filePath.value = response.filepath;
        console.log("filepath", filePath.value);
      fileUploadStatus.value = "上传成功";
      ElMessage.success("上传成功");
      fileNameOriginal.value = file.name.slice(-30);
    });
  } catch (error) {
    console.error("上传失败:", error);
    fileUploadStatus.value = "上传失败";
    ElMessage.error("上传失败");
  }
};

const handleExceed: UploadProps['onExceed'] = (files) => {
  uploadImage.value!.clearFiles();

  const file = files[0] as UploadRawFile;
  const uploadInstance = uploadImage.value;

  if (!uploadInstance) return;

  // 根据文件类型决定第二个参数
  let resourceType: 'image' | 'audio' | 'video';

  if (file.type.startsWith('image/')) {
    resourceType = 'image';
  } else if (file.type.startsWith('audio/')) {
    resourceType = 'audio';
  } else if (file.type.startsWith('video/')) {
    resourceType = 'video';
  } else {
    // 默认类型或处理未知类型
    resourceType = 'image'; // 可根据需求调整默认值
  }

  uploadInstance.handleStart(file);
  uploadFile({ file }, resourceType); // 传递动态类型
};

const clearFile = () => {
  filePath.value = "";
  previewUrl.value = '';
  fileUploadStatus.value = "";
  fileNameOriginal.value = "";
};

const canUseImage=computed(()=>{
  let imageSupport=true;
  agents.value.forEach((agent,index) => {
    if(!imageModelWhiteName.includes(curModelIds.value[index])){
      imageSupport = false;
    }
    if(!isLocalChatModelById(curModelIds.value[index])){
      imageSupport = false;
    }
  });
  return imageSupport;
})

const canUseAudio = computed(()=>{
  let audioSupport=true;
  agents.value.forEach((agent,index) => {
    if(!audioModelWhiteName.includes(curModelIds.value[index])){
      audioSupport = false;
    }
    if(!isLocalChatModelById(curModelIds.value[index])){
      audioSupport = false;
    }
  });
  return audioSupport;
})

const canUseVideo = computed(()=>{
  let vedioSupport=true;
  agents.value.forEach((agent,index) => {
    if(!videoModelWhiteName.includes(curModelIds.value[index])){
      vedioSupport = false;
    }
    if(!isLocalChatModelById(curModelIds.value[index])){
      vedioSupport = false;
    }
  });
  return vedioSupport;
})

const isDragging = ref(false);
// 支持的文件类型
const supportedFileTypes = ref(["jpg", "jpeg", "png", "gif",'mp3','wav','ogg','mp4','webm','ogg']);

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
  if(!canUseImage.value){
    ElMessage.warning("当前模型不支持图片上传");
    isDragging.value = false;
    return;
  }
  isDragging.value = false;
  if (filePath.value !== "" && fileUploadStatus.value === "上传成功") {
    ElMessage.error("请删除当前文件再上传");
    return;
  }
  const files = Array.from(e.dataTransfer.files);
  const file = files[0]
  let resourceType: 'image' | 'audio' | 'video';

  if (file.type.startsWith('image/')) {
    resourceType = 'image';
  } else if (file.type.startsWith('audio/')) {
    resourceType = 'audio';
  } else if (file.type.startsWith('video/')) {
    resourceType = 'video';
  } else {
    // 默认类型或处理未知类型
    resourceType = 'image'; // 可根据需求调整默认值
  }
  await uploadFile({ file }, resourceType); // 传递动态类型
};

const pageType=ref('text')
const changePageType=(val)=>{
  pageType.value=val;
}

const toPPTGenerator=()=>{
  pageType.value='pptGenerator'
}

const toDeepResearch=()=>{
  pageType.value='deepResearch'
}

let recorder = null;
const audioUrl = ref(null)
const isRecording = ref(false)
const recordingTime = ref(0)
const maxRecordingTime = 120 // 最大录制时间（秒）
const timer = ref(null)
const audioBlob = ref(null);

const isSecureContext = () => {
  return window.location.protocol === 'https:' ||
         window.location.hostname === 'localhost' ||
         window.location.hostname === '127.0.0.1';
}

// 初始化录音器
const initRecorder = async () => {
  try {
    recorder = new Recorder();
    await Recorder.getPermission();
    return true
  } catch (err) {
    console.error('录音初始化失败:', err);
    ElMessage.error('无法访问麦克风: ' + err.message)
    recorder = null
    return false
  }
};

// 开始录音
const startRecording = async () => {
  if (!isSecureContext()) {
    ElMessage.error('当前环境不支持麦克风访问');
    return;
  }

  if (recorder && isRecording.value) {
    stopRecording()
    return
  }

  if (!recorder && !await initRecorder()) {
    return
  }
  try {
    recorder.start();
    isRecording.value = true
    recordingTime.value = 0
    // 计时器
    timer.value = setInterval(() => {
      if (isRecording.value) {
        recordingTime.value++
        if (recordingTime.value >= maxRecordingTime) {
          stopRecording()
          ElMessage.warning('已达到最大录制时间')
        }
      }
    }, 1000)

    ElMessage.success('录音开始')
  } catch (error) {
    console.error('录音错误:', error)
    ElMessage.error('无法访问麦克风: ' + error.message)
  }
}

// const stopRecording = () => {
//   if (!recorder || !isRecording.value) return;
//   clearInterval(timer.value)
//   recorder.stop()
//   audioBlob.value = recorder.getWAVBlob()
//   audioUrl.value = URL.createObjectURL(audioBlob.value);
//   isRecording.value = false
//   ElMessage.success('录音已停止')
//   doUpload()
// }

// 停止录音
const stopRecording = () => {
  if (!recorder || !isRecording.value) return;

  clearInterval(timer.value);
  recorder.stop();
  isRecording.value = false;

  // 获取Blob对象
  audioBlob.value = recorder.getWAVBlob();

  // 创建FileReader读取Blob
  const reader = new FileReader();
  audioUrl.value = URL.createObjectURL(audioBlob.value);

  // 设置读取完成回调
  reader.onload = () => {
    // 获取Base64格式的URL (格式如：data:audio/wav;base64,UklGRl9...)
    previewUrl.value = reader.result;
    ElMessage.success('录音已停止');

    // 在回调中执行上传
    doUpload();
  };

  // 开始读取Blob（异步操作）
  reader.readAsDataURL(audioBlob.value);
};

// 下载录音
const downloadRecording = () => {
  if (!recorder) return
  recorder.downloadWAV(`录音-${getLocalISOString().slice(0, 16)}`)
}

const doUpload = async () => {
  if (!audioBlob.value) {
    ElMessage.error('没有可上传的录音文件')
    console.error('没有可上传的录音文件')
    return
  }

  // 生成带时间戳的文件名 (格式: 时间戳_recording.wav)
  const timestamp = Date.now();
  const fileName = `${timestamp}_recording.wav`;

  // 上传文件
  const formData = new FormData();
  formData.append('audio', audioBlob.value, fileName);

  try {
    await ChatService.upLoadFile(formData, (response, isError) => {
      if (!isError) {
        filePath.value = response.filepath;
        console.log('filePath', filePath.value)
        fileUploadStatus.value = '上传成功'
        ElMessage.success('上传成功')
        // 保留后30字符（原逻辑）
        fileNameOriginal.value = fileName.slice(-30)
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

  // console.log('previewUrl')
  // console.log(previewUrl.value)
};

const displayFileName = computed(() => {
      const fileName = fileNameOriginal.value
      // 查找最后一个句点的位置
      const lastDotIndex = fileName.lastIndexOf('.')

      if (lastDotIndex === -1) {
        // 没有后缀时直接截取前10字符
        return fileName.length > 10
          ? fileName.substring(0, 10) + '...'
          : fileName
      }

      // 分离文件名和扩展名
      const namePart = fileName.substring(0, lastDotIndex)
      const extension = fileName.substring(lastDotIndex)

      // 处理主文件名长度
      return namePart.length > 10
        ? namePart.substring(0, 10) + '...' + extension
        : fileName
    })
</script>

<template>
  <div class="chatCenterContainer" @dragover.prevent="handleDragOver" @dragleave="handleDragLeave"
    @drop.prevent="handleDrop" v-if="pageType==='text'">
    <!-- 拖拽提示框 -->
    <transition name="fade">
      <div v-if="isDragging" class="drop-overlay">
        <div class="drop-hint-box">
          <el-icon class="hint-icon">
            <upload-filled />
          </el-icon>
          <h3>松开上传文件</h3>
          <p>支持图片、音频、视频文件拖到当前页上传</p>
          <div class="supported-formats">
            <el-tag v-for="type in supportedFileTypes" :key="type" size="small">{{ type }}</el-tag>
          </div>
        </div>
      </div>
    </transition>

    <div class="pageContent" v-loading="initLoading" element-loading-text="加载中...">

      <div class="controlArea">
        <div class="controlPanel">
          <div class="panelTopButtons">
            <button class="newSessionButton" @click="createSession">
              开启新对话
            </button>
            <button class="addModelButton" :disabled="agents.length > 1" @click="openAddModelDialog">添加模型对比
            </button>
          </div>
          <div class="chatHistoryContainer">
            <template v-for="group in groupedSessions" :key="group.label">
              <div class="sessionGroupLabel">{{ group.label }}</div>
              <div class="chatHistoryItem" v-for="sess in group.sessions" :key="sess.id"
                @click="switchSession(sess.id)" :class="{ 'active': chatStore.currentSessionId === sess.id }">
                <div class="chatHistoryItemTitle">
                  {{ sess.title }}
                </div>
                <button class="chatHistoryItemDeleteButton" @click.stop="deleteSession(sess.id)">✖</button>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div class="chatArea">
        <div class="chatPanelContainer">
          <ChatPanel v-for="agent in agents" :key="agent.threadId" :thread-id="agent.threadId" :modelId="agent.modelId"
            :messages="agent.messages" :params="agent.params" :session-type="sessionType"
            @delete-thread="onDeleteAgent" />
        </div>

        <div class="inputPanelContainer">
          <div class="inputBar">
            <div class="functionsBtnBox">
              <el-button type="primary" :icon="Tickets" round @click="toPPTGenerator">PPT生成</el-button>
              <el-button type="primary" :icon="Search" round @click="toDeepResearch">DeepResearch</el-button>
            </div>
            <textarea ref="textareaRef" class="input" placeholder="请给我发送消息，Enter 发送 / Ctrl+Enter 换行" @input="onInput"
              @keydown="handleKeyDown" @paste="handlePaste" v-model="inputBarContent" rows="3"
              :style="{ height: currentHeight + 'px', overflowY }"></textarea>
            <div class="buttomBox">
              <div class="left-group">
                <el-dropdown trigger="click">
                  <el-button :icon="Plus" circle />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <!-- <el-dropdown-item command="document">
                        <el-icon>
                          <Document />
                        </el-icon>上传文档</el-dropdown-item> -->
                      <el-dropdown-item command="image" :disabled="!canUseImage">
                        <el-upload ref="uploadImage" action :http-request="(param) => uploadFile(param, 'image')"
                          :show-file-list="false" :on-exceed="handleExceed" :limit="1" accept=".jpg, .jpeg, .png, .gif"
                          :disabled="!canUseImage"><el-icon>
                            <Picture />
                          </el-icon>上传图片</el-upload></el-dropdown-item>
                      <el-dropdown-item command="audio" :disabled="!canUseAudio">
                        <el-upload ref="uploadAudio" action :http-request="(param) => uploadFile(param, 'audio')"
                          :show-file-list="false" :on-exceed="handleExceed" :limit="1" accept=".mp3, .wav, .ogg "
                          :disabled="!canUseAudio"><el-icon>
                            <Service />
                          </el-icon>上传音频</el-upload></el-dropdown-item>
                      <el-dropdown-item command="video" :disabled="!canUseVideo">
                        <el-upload ref="uploadVideo" action :http-request="(param) => uploadFile(param, 'video')"
                          :show-file-list="false" :on-exceed="handleExceed" :limit="1" accept=".mp4, .webm, .ogg"
                          :disabled="!canUseVideo"><el-icon>
                            <VideoCamera />
                          </el-icon>上传视频</el-upload></el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-checkbox-button v-model="isDeepResearch" label="DeepResearch" border class="deepResearchBtn"
                  :disabled="previewUrl !== ''">
                  <div class='buttomBoxInside'>
                    <div class="icon-transition">
                      <img src="/images/boshimao1.png" :class="{ 'show': !isDeepResearch }" />
                      <img src="/images/boshimao_white.png" :class="{ 'show': isDeepResearch }" />
                    </div>
                    DeepResearch
                    <el-select v-model="deepResearchType" placeholder="模式" class="drSelect"
                      :disabled="previewUrl !== ''">
                      <el-option label="快速" value="fast" />
                      <el-option label="专业" value="professional" />
                    </el-select>
                  </div>
                </el-checkbox-button>
                <el-checkbox-button v-model="isThink" label="深度思考" border class="thinkBtn">
                  <div class="icon-transition">
                    <img src="/images/shendusikao_white.png" :class="{ 'show': isThink }" />
                    <img src="/images/shendusikao.png" :class="{ 'show': !isThink }" />
                  </div>
                  深度思考
                </el-checkbox-button>
              </div>

              <!-- 右侧分组：包裹两个发送按钮 -->
              <div class="right-group">
                <div v-if="filePath === ''" class="audioRecordContainer">
                  <el-button circle type="primary" @click="startRecording" :disabled="previewUrl != '' || !canUseAudio">
                    <svg v-if="!isRecording" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" width="16"
                      height="16">
                      <path
                        d="M516.266667 657.066667c78.933333 0 142.933333-64 142.933333-142.933334V217.6a142.933333 142.933333 0 0 0-285.866667 0v296.533333c0 78.933333 64 142.933333 142.933334 142.933334z m-78.933334-439.466667c0-42.666667 36.266667-78.933333 78.933334-78.933333s78.933333 36.266667 78.933333 78.933333v296.533333c0 42.666667-36.266667 78.933333-78.933333 78.933334s-78.933333-36.266667-78.933334-78.933334V217.6z"
                        fill="#FFFFFF"></path>
                      <path
                        d="M774.4 409.6c-17.066667 0-32 14.933333-32 32v74.666667c0 125.866667-102.4 228.266667-228.266667 228.266666S288 640 288 514.133333v-74.666666c0-17.066667-14.933333-32-32-32s-32 14.933333-32 32v74.666666c0 149.333333 113.066667 273.066667 260.266667 290.133334v85.333333h-117.333334c-17.066667 0-32 14.933333-32 32s14.933333 32 32 32h296.533334c17.066667 0 32-14.933333 32-32s-14.933333-32-32-32h-117.333334v-85.333333c145.066667-14.933333 260.266667-140.8 260.266667-290.133334v-74.666666c0-17.066667-12.8-29.866667-32-29.866667z"
                        fill="#FFFFFF"></path>
                    </svg>

                    <svg v-else viewBox="0 0 1040 1024" xmlns="http://www.w3.org/2000/svg" width="16" height="16">
                      <path
                        d="M512 64c60.5 0 119.2 11.8 174.4 35.2 53.3 22.6 101.3 54.9 142.4 96 41.2 41.2 73.5 89.1 96 142.4C948.2 392.8 960 451.5 960 512s-11.8 119.2-35.2 174.4c-22.6 53.3-54.9 101.3-96 142.4-41.2 41.2-89.1 73.5-142.4 96C631.2 948.2 572.5 960 512 960s-119.2-11.8-174.4-35.2c-53.3-22.6-101.3-54.9-142.4-96-41.2-41.2-73.5-89.1-96-142.4C75.8 631.2 64 572.5 64 512s11.8-119.2 35.2-174.4c22.6-53.3 54.9-101.3 96-142.4 41.2-41.2 89.1-73.5 142.4-96C392.8 75.8 451.5 64 512 64m0-64C229.2 0 0 229.2 0 512s229.2 512 512 512 512-229.2 512-512S794.8 0 512 0z"
                        fill="#FFFFFF"></path>
                      <path
                        d="M716 304H308c-2.2 0-4 1.8-4 4v408c0 2.2 1.8 4 4 4h408c2.2 0 4-1.8 4-4V308c0-2.2-1.8-4-4-4z"
                        fill="#FFFFFF"></path>
                    </svg>
                  </el-button>
                </div>

                <div v-if="filePath !== ''" class="fileUploadContainer">
                  <el-image class="imgPreview" :src="previewUrl" :max-scale="7" :min-scale="0.2"
                    :preview-src-list="[previewUrl]" show-progress fit="contain"
                    v-if="fileUploadStatus === '上传成功' && previewUrl.startsWith('data:image/')">
                    <template #error>
                      <div class="image-viewer-slot image-slot"><el-icon>
                          <Picture />
                        </el-icon>
                      </div>
                    </template>
                  </el-image>
                  <audio v-else-if="fileUploadStatus === '上传成功' && previewUrl.startsWith('data:audio/')"
                    :src="previewUrl" controls controlsList="nodownload noplaybackrate" style="height:50px"></audio>
                  <video v-else-if="fileUploadStatus === '上传成功' && previewUrl.startsWith('data:video/')"
                    :src="previewUrl" controls controlsList="nodownload noplaybackrate" oncontextmenu="return false;"
                    style="max-width: 300px;max-height:50px; margin-bottom: 10px"></video>
                  <el-button circle type="danger" disabled :icon="Warning" v-else></el-button>
                  <el-button v-if="audioUrl != null" circle type="success" @click="downloadRecording"
                    :disabled="!audioUrl || isRecording" :icon="Download">
                  </el-button>
                  <el-tooltip class="box-item" effect="dark" :content="fileNameOriginal" placement="top">
                    <span style="margin-left: 5px; margin-right: 10px">{{ displayFileName }}{{ fileUploadStatus
                      }}</span>
                  </el-tooltip>
                  <el-button circle type="info" @click="clearFile" :icon="Close"></el-button>
                </div>
                <img v-if="!sendStatus.loading"
                  :class="inputBarContent || previewUrl ? 'sendButton' : 'sendButtonDisable'"
                  :src="inputBarContent || previewUrl ? planeSvg : planeDisableSvg" alt="send" @click="send" />
                <img v-else class="sendButton" :src="stopSvg" alt="send" @click="stopSend" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧参数设置区域 -->
      <div class="controlArea">
        <div class="controlPanel">
          <div class="threadSettingsContainer">
            <div v-for="(agent, index) in agents" :key="agent.threadId" class="thread-settings">
              <!-- 模型下拉切换 -->
              <div class="param-item">
                <label>模型</label>
                <el-select class="dropDown" v-model="curModelIds[index]"
                  @change="(val)=> sideEffectOfSwitchModel(agent.threadId, agent.modelId,val,index)"
                  placeholder="请选择模型" placement="bottom-end">
                  <template #prefix>
                    <span v-if="agent.modelId" style="display:flex; align-items:center; margin-right:6px;">
                      <img :src="ModelService.getModelIcon(agent.modelId)"
                        style="width:18px; height:18px; object-fit:cover; border-radius:4px;" alt="icon" />
                    </span>
                  </template>
                  <el-option v-for="m in modelList" :key="m" :value="m" :label="m"
                    :disabled="isModelDisabled(m, agent.threadId)">
                    <span style="display:flex; align-items:center; gap:6px;">
                      <img :src="ModelService.getModelIcon(m)"
                        style="width:18px; height:18px; object-fit:cover; border-radius:4px;"
                        alt="icon" />
                      <span>{{ modelStore.getModelName(m) }}</span>
                      <el-tag v-if="!isLocalChatModelById(m)" effect="light" hit round type="warning" size="small">外部模型</el-tag>
                    </span>
                  </el-option>
                </el-select>
              </div>
              <!-- 滑条参数 -->
              <template v-if="!agent.modelId.includes('信息安全')">
                <div v-for="(range, key) in paramRanges" :key="key" class="param-item">
                  <label :for="agent.threadId + '-' + key"
                    :class="{ 'disabled-label': !modelStore.getModelById(agent.modelId)?.config?.api_params_available?.[0]?.params?.find(item => item.key === key) }">
                    {{ ModelService.getParamName(key) }}
                  </label>
                  <div class="rangeInputContainer">
                    <input class="sliderInput" type="range" :id="agent.threadId + '-' + key" :min="range.min"
                      :max="key !== 'max_tokens' || !agent.modelId ? range.max : curMaxToken(agent.modelId)"
                      :value="agent.params[key]" :step="range.step" v-model="agent.params[key]" :style="{
                           '--min': range.min,
                           '--max': key !== 'max_tokens' || !agent.modelId ? range.max : curMaxToken(agent.modelId),
                           '--value': agent.params[key]
                        }"
                      :disabled="!modelStore.getModelById(agent.modelId)?.config.api_params_available[0]?.params.find(item => item.key === key)" />
                    <input class="textInput" type="number" :id="agent.threadId + '-' + key + '-text'" :min="range.min"
                      :max="key !== 'max_tokens' || !agent.modelId ? range.max : curMaxToken(agent.modelId)"
                      :step="range.step" v-model="agent.params[key]"
                      :disabled="!modelStore.getModelById(agent.modelId)?.config.api_params_available[0]?.params.find(item => item.key === key)" />
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <transition name="modal-fade-in" appear :duration="{ enter: 500, leave: 500 }" mode="out-in">
        <!-- —— 模态对话框 —— -->
        <div v-show="showAddModelDialog" class="modal-overlay">
          <transition name="modal-slide" appear :duration="{ enter: 500, leave: 500 }">
            <div class="modal" v-if="showAddModelDialog">
              <h3>选择对比模型</h3>
              <ul class="model-list">
                <li v-for="m in modelList" :key="m">
                  <!-- 注意：name 要统一，id 要唯一 -->
                  <input class="model-radio" type="radio" name="model" :id="`model-${m}`" v-model="selectedModel"
                    :disabled="isModelDisabled(m, '')" :value="m" />
                  <label class="model-label" :for="`model-${m}`">
                    <img class="modelIcon" :src="ModelService.getModelIcon(m)" />
                    <span>
                      <span class="modelName" style="display:flex; align-items:center; gap:6px;">
                        {{ modelStore.getModelName(m) }}
                        <el-tag v-if="!isLocalChatModelById(m)" effect="light" hit round type="warning" size="small">外部模型</el-tag>
                      </span>
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
  <PPTGenerator v-else-if="pageType==='pptGenerator'" @change-page-type="changePageType"></PPTGenerator>
  <DeepResearch v-else @change-page-type="changePageType"></DeepResearch>
</template>

<style scoped>

* {
  box-sizing: border-box;
}

.chatCenterContainer {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
}

.pageContent {
  flex: 1;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  align-items: stretch;
}

.chatArea {
  flex-grow: 1;
  flex-shrink: 1;
  flex-basis: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background-color: rgb(245, 245, 245);
}

.chatPanelContainer {
  flex: 1;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 0;
  min-height: 0;
}

.inputPanelContainer {
  width: 100%;
  background-color: rgb(245, 245, 245);
}

.inputBar {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12px;
  height: 100%;
  padding: 0 32px 12px 32px;
  width: 100%;
  background-color: rgb(245, 245, 245);
}

.inputBar > .input {
  --font-size: 14px;
  outline: none;
  border: 1px solid rgb(220, 220, 220);
  font-size: var(--font-size);
  width: 100%;
  line-height: 1.5;
  padding: 12px 16px;
  margin: 0;
  resize: none;
  color: black;
  min-height: 72px;
  max-height: 192px;
  overflow: auto;
  white-space: pre-wrap;
  font-family: "Arial", "Impact", sans-serif;
  transition: height 0.15s ease;
  overflow-wrap: break-word;
  background-color: #fff;
  border-radius: 12px;
}

.input[contenteditable]:empty:before {
  content: attr(data-placeholder);
  color: #ccc;
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

.controlArea {
  flex-grow: 0;
  flex-shrink: 0;
  width: 11%;
  min-width: 140px;
  display: flex;
  background-color: rgb(238, 238, 238);
}

.controlArea:first-of-type {
  border-right: 1px solid rgb(225, 225, 225);
}

.controlArea:last-of-type {
  border-left: 1px solid rgb(225, 225, 225);
}

.controlPanel {
  height: 100%;
  width: 100%;
  background-color: rgb(238, 238, 238);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panelTopButtons {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 0 8px 0;
  border-bottom: 1px solid rgb(215, 215, 215);
}

.newSessionButton,
.addModelButton {
  height: 32px;
  width: 100%;
  font-size: 12px;
  border: none;
  outline: none;
  border-radius: 6px;
  padding: 6px 10px;
  display: flex;
  justify-content: center;
  align-items: center;
  transition: all 0.1s ease-in-out;
  cursor: pointer;
}

.newSessionButton {
  background-color: rgb(0, 102, 216);
  color: white;
}

.newSessionButton:hover {
  filter: brightness(0.9);
}

.newSessionButton:active {
  filter: brightness(1.25);
}

.addModelButton {
  background-color: transparent;
  color: rgb(80, 80, 80);
  border: 1px solid rgb(200, 200, 200);
}

.addModelButton:hover {
  background-color: rgb(225, 225, 225);
}

.addModelButton:active {
  background-color: rgb(210, 210, 210);
}

.addModelButton[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
}

.chatHistoryContainer {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 100%;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.sessionGroupLabel {
  font-size: 11px;
  color: rgb(140, 140, 140);
  padding: 6px 4px 2px 4px;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.chatHistoryItem {
  width: 100%;
  display: flex;
  flex-direction: row;
  border-radius: 6px;
  padding: 6px 8px;
  gap: 4px;
  background-color: transparent;
  position: relative;
  transition: all 0.1s ease-in-out;
  cursor: pointer;
}

.chatHistoryItem:hover {
  background-color: rgb(215, 215, 215);
}

.chatHistoryItem.active {
  background-color: rgb(205, 205, 205);
}

.chatHistoryItem:active {
  background-color: rgb(195, 195, 195);
}

.chatHistoryItem > .chatHistoryItemTitle {
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 16px;
  vertical-align: middle;
  color: rgb(50, 50, 50);
}

.chatHistoryItemDeleteButton {
  border: none;
  outline: none;
  position: absolute;
  top: 4px;
  right: 4px;
  border-radius: 50%;
  background-color: transparent;
  font-size: 9px;
  line-height: 14px;
  width: 14px;
  height: 14px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  transition: all 0.1s ease-in-out;
  cursor: pointer;
  color: rgb(160, 160, 160);
}

.chatHistoryItemDeleteButton:hover {
  background-color: red;
  color: white;
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
  width: 100%;
  max-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
}

.thread-settings {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.param-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
}

.param-item .dropDown {
  margin-top: 2px;
  margin-bottom: 2px;
  width: 100%;
}

.param-item .dropDown :deep(.el-select__wrapper) {
  font-size: 12px;
  min-height: 30px;
}

.param-item .dropDown :deep(.el-select__placeholder) {
  font-size: 12px;
}

.param-item label {
  width: 100%;
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: rgb(60, 60, 60);
}

.disabled-label {
  color: rgb(160, 160, 160);
}

.rangeInputContainer {
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.rangeInputContainer .sliderInput {
  flex: 1 1 0;
}

.rangeInputContainer .textInput {
  flex: 0 0 1;
  width: 50px;
  text-align: right;
  border: 1px solid rgb(221, 221, 221);
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 12px;
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
  -webkit-appearance: none;
  width: 100%;
  height: 3px;
  margin: 0;
  background: rgb(215, 215, 215);
  border-radius: 2px;
  background-image: linear-gradient(rgb(0, 103, 209), rgb(0, 103, 209));
  background-repeat: no-repeat;
  background-size: calc((var(--value) - var(--min)) / (var(--max) - var(--min)) * 100%) 100%;
}


input[type=range]:focus {
  outline: none;
}

/* --------- Webkit 系列 (Chrome/Safari/Edge) ---------- */
input[type=range]::-webkit-slider-runnable-track {
  height: 3px;
  background: transparent;
}

input[type=range]::-webkit-slider-thumb {
  --thumb: 12px;
  --track: 2px;
  -webkit-appearance: none;
  width: var(--thumb);
  height: var(--thumb);
  background: rgb(255, 255, 255);
  border: var(--track) solid rgb(0, 103, 209);
  border-radius: 50%;
  margin-top: calc((var(--thumb) - var(--track)) / 2 * -1);
  cursor: pointer;
}

input[type=range][disabled] {
  background-image: linear-gradient(rgb(126, 126, 126), rgb(126, 126, 126));
}


input[type=range][disabled]::-webkit-slider-thumb {
  border: var(--track) solid rgb(126, 126, 126);
}

.buttomBox {
  display: flex;
  justify-content: space-between; /* 左右分组分别贴边 */
  align-items: center; /* 垂直居中 */
  height:50px;
  width: 100%;
  gap: 10px;
}

.left-group {
  display: flex;
  gap: 10px; /* 保持复选框之间的间隙 */
}

.right-group {
  display: flex;
  align-items: center;
  gap: 10px; /* 图片按钮之间的间隙 */
}

.buttomBox :deep(.el-checkbox) {
    margin-right: 0 !important;
}

.buttomBox :deep(.el-checkbox-button__inner){
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  border: 1px solid rgb(220, 223, 230) !important;
  padding: 5px;
  /* width:220px; */
}

.buttomBox img {
  height: 24px;
  margin-right: 6px; /* 可选：添加图片和文字的间距 */
}

.deepResearchBtn :deep(.el-checkbox-button__inner){
  padding: 0 0 0 5px !important;
}

.thinkBtn :deep(.el-checkbox-button__inner){
  width:150px;
}

.buttomBoxInside{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 100%;
}

.drSelect {
  margin-left: 5px;
  width: 80px
}

.drSelect :deep(.el-select__wrapper){
  border-radius: 0;
  box-shadow: none;
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

.imgPreview {
  max-width: 200px;
  height: 50px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.imgPreview :deep(.el-image) {
  overflow: hidden;
}

.imgPreview :deep(.el-image__inner) {
  max-width: 100% !important;
  max-height: 100% !important;
  width: auto !important;
  height: auto !important;
}

.image-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-direction: column;
  font-size: 30px;
  height: 70px;
  background: #fff;
}

.image-slot .el-icon {
  font-size: 30px;
}

.image-viewer-slot {
  background: var(--el-fill-color-light);
}

/* 图片容器 */
.icon-transition {
  display: inline-block;
  position: relative;
  width: 24px;       /* 根据实际图片尺寸调整 */
  height: 24px;      /* 根据实际图片尺寸调整 */
  margin-right: 8px; /* 图片和文字的间距 */
}

/* 图片通用样式 */
.icon-transition img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;        /* 默认隐藏 */
  transition: opacity 0.3s !important; /* 与Element的渐变动效同步 */
}

/* 显示图片的类 */
.icon-transition img.show {
  opacity: 1;
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

.functionsBtnBox {
  display: flex;
  align-items: center;
  /* justify-content: center; */
  width: 100%;
  flex-wrap: wrap;
  gap: .5rem;
}

.audioRecordContainer {
  display: flex;
  align-items: center;
  padding: 6px;
  border-radius: 8px;
}
</style>
