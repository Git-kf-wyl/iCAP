<script setup>
import { ref, nextTick, computed, onMounted, watch, provide } from "vue";
import planeSvg from "@/assets/plane.svg";
import planeDisableSvg from "@/assets/planeDisable.svg";
import stopSvg from "@/assets/stop.svg";
import ChatPanelAgent from "@/components/agentCenter/ChatPanelAgent.vue";
import { AgentChatService } from "@/services/AgentChatService.js";
import { useRoute } from "vue-router";
import { useAIModelStore } from "@/stores/aiModel.js";
import {
  isModelAvailableById,
  isLocalChatModelById,
} from "@/utils/ModelUtils.js";
import { useDeepSearchChatStore } from "@/stores/deepResearchChat.js";
import { API_AGENT_URL } from "@/utils/Constants.js";
import { Monitor, Back, Plus, Minus } from "@element-plus/icons-vue";
import { marked } from "marked";
import ChatPanelPc from "@/components/agentCenter/ChatPanelPc.vue";
import { getLogData, modifyLogData } from "@/api/dataService.js";
// import MarkdownIt from "markdown-it";

// const markdown = new MarkdownIt();
const token = ref("");

const chatStore = useDeepSearchChatStore();
const modelStore = useAIModelStore();

const route = useRoute();
const inputBarContent = ref("");
const textareaRef = ref(null);
const modelList = ref([]); // 拉下来可选的模型名列表
// 参数滑条的范围设定
const paramRanges = ref({
  max_tokens: { min: 100, max: 100000, step: 1 },
  temperature: { min: 0, max: 1, step: 0.01 },
  top_p: { min: 0, max: 1, step: 0.01 },
  top_k: { min: 0, max: 100, step: 10 },
});

const sessionType = ref("deepSearch");
const sendType = ref("1"); // 默认值为“固定模板生成”
const deepResearchType = ref("fast");
// 当前会话的 agent 列表
const agents = computed(() => {
  return chatStore.currentSession ? chatStore.currentSession.agents : [];
});

const sendStatus = ref({
  loading: false,
  controller: null, // AbortController 用于中断流式
});
// 自动滚动状态
const isAutoScrolling = ref(true);

// 处理用户滚动事件
const handleScroll = () => {
  if (isAutoScrolling.value) {
    isAutoScrolling.value = false;
  }
};

const loadLog = async () => {
  const response = await getLogData({
    user_id: token.value,
    type: "deepResearch",
  });
  const logData = response.data.data;

  // console.log('logData');
  // console.log(logData);

  chatStore.loadHistory(logData);
};

function onInput(e) {
  const ta = e.target;
  ta.style.height = "auto";
  ta.style.height = ta.scrollHeight + "px";
}

function handleKeyDown(e) {
  if (e.key === "Enter") {
    if (e.ctrlKey) {
      e.preventDefault();
      const startPos = textareaRef.value.selectionStart;
      const endPos = textareaRef.value.selectionEnd;
      inputBarContent.value =
        inputBarContent.value.substring(0, startPos) +
        "\n" +
        inputBarContent.value.substring(endPos);
      // 更新光标位置（需要nextTick确保DOM已更新）
      nextTick(() => {
        textareaRef.value.selectionStart = textareaRef.value.selectionEnd =
          startPos + 1;
        textareaRef.value.focus();
      });
      return;
    }
    e.preventDefault();
    sendDeepSearch();
  }
}

async function send() {
  console.log("send-->");
  const content = inputBarContent.value;
  if (!content) return;
  inputBarContent.value = "";
  await nextTick();
  if (textareaRef.value) {
    textareaRef.value.style.height = "auto";
  }
  sendStatus.value.loading = true;
  sendStatus.value.controller = new AbortController();

  // 添加用户消息
  chatStore.addUserMessage(content);
  const session = chatStore.currentSession;
  if (session) {
    const tasks = session.agents.map((agent) => {
      // 生成唯一 task_id（毫秒时间戳）
      const task_id = Date.now().toString();

      const msg = chatStore.addAssistantMessage("加载中...", agent.threadId);

      AgentChatService.startDeepResearchMessage({
        endpoint: API_AGENT_URL + "start_deep_research",
        taskid: task_id,
        query: content,
      })
        .then((response) => {
          if (response.status === 202) {
            console.log("深度研究已启动 (202 Accepted)");

            console.log("send deep research-->");
            AgentChatService.sendDeepResearchMessage(
              {
                endpoint: API_AGENT_URL + "deep_research_stream_chat",
                taskid: task_id,
              },
              // 流数据回调
              (message) => {
                msg.content = message;
              },
              // 完成回调
              (finalMessage, error) => {
                console.log("finish deep research--<");
                msg.isFinished = true; // 标记完成
                sendStatus.value.loading = false; // 关闭加载状态

                if (error) {
                  msg.content = "深度研究失败：" + (finalMessage || "未知错误");
                  console.error("deep research 请求失败");
                } else {
                  console.log("deep research 请求成功");
                }
              }
            );
          } else {
            console.error("非预期状态码:", response.status);
            // 处理其他状态码
          }
        })
        .catch((error) => {
          console.error("请求失败:", error);
          // 处理网络错误
        });
    });
  }
}

const sendDeepSearch = async () => {
  const content = inputBarContent.value;
  const task_id = Date.now().toString();

  if (!content) return;
  inputBarContent.value = "";
  await nextTick();
  if (textareaRef.value) {
    textareaRef.value.style.height = "auto";
  }
  sendStatus.value.loading = true;
  sendStatus.value.controller = new AbortController();

  console.log("深度研究已启动");

  console.log("send deep research-->");
  // 添加用户消息
  chatStore.addUserMessage(content);
  const session = chatStore.currentSession;
  if (session) {
    const tasks = session.agents.map((agent) => {
      const msg = chatStore.addAssistantMessage("加载中...", agent.threadId);
      AgentChatService.sendDeepResearchMessage(
        {
          // endpoint: "http://127.0.0.1:8500/v1/" + "deep_research/stream",
          endpoint: API_AGENT_URL + "deep_research/stream",
          taskid: task_id,
          query: content,
          user_id: token.value,
          deepResearchType: deepResearchType.value,
          url_list:resultArray.value.join(';'),
          is_search:is_search.value
        },
        // 流数据回调
        (message) => {
          msg.content = message;
        },
        // 完成回调
        (finalMessage, error) => {
          console.log("finish deep research--<");
          msg.isFinished = true; // 标记完成
          sendStatus.value.loading = false; // 关闭加载状态

          if (error) {
            msg.content = "深度研究失败：" + (finalMessage || "未知错误");
            console.error("deep research 请求失败");
          } else {
            console.log("deep research 请求成功");
          }
        }
      );
    });
  }
};

async function stopSend() {
  if (sendStatus.value.controller) {
    sendStatus.value.controller.abort(); // 直接中断 fetch
    sendStatus.value.controller = null;
  }
  sendStatus.value.loading = false;
}

function deleteSession(id) {
  chatStore.deleteSession(id);
  modifyLogData({ user_id: token.value, chat_id: id });
  // 如果想额外确认，可加 confirm 弹窗
}

const pcTabs = ref("computer");
const embeddedUrl = ref(
  "http://6080-i8krpwxsq09vouwbnvtee.service.consul:3002/vnc.html?autoconnect=true&resize=scale"
);

const thinkLabelOpen = ref("<p><ROUND1><think>");
const thinkLabelClose = ref("</think>");

const processAgentResult = async (rawResult) => {
  const loadingPattern = /<p>\S\sLoading\.*<\/p>/gs;
  if (loadingPattern.test(rawResult)) {
    return [
      {
        id: 1,
        think: "",
        content: rawResult,
      },
    ];
  } else {
    // console.log(rawResult);
  }
  rawResult = rawResult.replace(/<a/g, '<a target="_blank"');
  rawResult = rawResult.replace(/<hr>/g, "");
  rawResult = rawResult.replace(/<tool_search_result>/g, "<div>");
  rawResult = rawResult.replace(/<\/tool_search_result>/g, "</div>");

  // const regex = /<ROUND(\d+)><think>(.*?)<\/think>(.*?)(?=<ROUND\d+>|$)/gs;
  const regex =
    /<ROUND(\d+)><think>(.*?)(?=<\/think>|<\/p>)(.*?)(?=<ROUND\d+>|$)/gs;

  let matches;
  const result = [];

  while ((matches = regex.exec(rawResult)) !== null) {
    const id = parseInt(matches[1], 10);
    const think = matches[2].trim();
    const content = matches[3].trim();

    result.push({
      id,
      think,
      content,
    });
  }
  // console.log("result");
  // console.log(result);

  return result;
};

const activeNames = Array.from({ length: 1000 }, () => "tab1");

function clickMonitor() {
  if (agents.value.length > 0 && agents.value[0].messages.length > 0) {
    agents.value[0].messages.at(-1).isShowAgent =
      !agents.value[0].messages.at(-1).isShowAgent;
    isShowMoni.value = !agents.value[0].messages.at(-1).isShowAgent;
    isShowAgent.value = agents.value[0].messages.at(-1).isShowAgent;
  }

  // console.log("selectedContent");
  // console.log(selectedContent.value);
  // isShowAgent.value = true; //DEV
  console.log("rawHtml");
  console.log(rawHtml.value);
  // testMarked()
}

function clickCloseMonitor() {
  if (agents.value.length > 0 && agents.value[0].messages.length > 0) {
    agents.value[0].messages.at(-1).isShowAgent = false;
    isShowMoni.value = true;
    isShowAgent.value = false;
  }
}

const addUserUrlOpen = ref(false);

// 输入框数组
const inputList = ref([{ value: '' }])

// 收集的数据数组
const resultArray = ref([])

// 打开对话框时重置
const openDialog = () => {
  addUserUrlOpen.value = true
  inputList.value = []
  if (resultArray.value.length > 0) {
    resultArray.value.forEach(item => {
      inputList.value.push({
        value: item
      })
    })
  } else {
    inputList.value = [{ value: '' }]
  }
}

// 添加输入框
const addInput = (index) => {
  inputList.value.splice(index + 1, 0, { value: '' })
}

// 移除输入框
const removeInput = (index) => {
  if (inputList.value.length > 1) {
    inputList.value.splice(index, 1)
  }
}

// 确认提交
const handleConfirm = () => {
  resultArray.value = inputList.value
    .map(item => item.value.trim())
    .filter(value => value !== '')
  
  console.log('收集的数据:', resultArray.value)
  addUserUrlOpen.value = false
}

// 关闭对话框时重置
const handleClose = () => {
  // inputList.value = [{ value: '' }]
}

const is_search=ref(true);

onMounted(async () => {
  try {
    if (modelStore.allIds.length === 0) {
      await modelStore.fetchModels();
    }
    modelList.value = modelStore.allIds.filter(
      (id) => isModelAvailableById(id) && isLocalChatModelById(id)
    );
  } catch (e) {
    console.error("获取模型列表失败", e);
  }
  token.value = localStorage.getItem("username");
  await loadLog();
  // （2）处理 modelId
  let modelId = route.query.modelId;
  if (modelId) {
    console.log("createSession1", modelId);
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
    chatStore.createSession("体验会话", modelId, modelParams);
  } else if (
    chatStore.currentSession === "" ||
    chatStore.currentSession === null
  ) {
    console.log("createSession2");
    // 默认要更新第一个模型的参数
    modelId = modelStore.allIds[0];
    const model = modelStore.getModelById(modelId);
    // 数组转对象
    const modelParams = model.config.api_params_available[0].params.reduce(
      (acc, item) => {
        if (item.key) {
          acc[item.key] = item.value;
        }
        return acc;
      },
      {}
    );
    chatStore.createSession("体验会话", modelId, modelParams);
  }
  if (agents.value.length > 0 && agents.value[0].messages.length > 0) {
    isShowMoni.value =
      !agents.value[0].messages.at(-1).isShowAgent &&
      agents.value[0].messages.at(-1).curTaskId !== "";
    isShowAgent.value = agents.value[0].messages.at(-1).isShowAgent;
    isAutoScrolling.value = true;
  }
});
</script>

<template>
  <div class="chatCenterContainer">
    <div class="pageContent">
      <div class="leftControlArea">
        <div class="controlPanel">
          <div class="upperControlPanel">
            <div class="chatHistoryContainer">
              <div
                class="chatHistoryItem"
                v-for="sess in chatStore.sessions"
                :key="sess.id"
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
        </div>
      </div>
      <div class="chatArea">
        <div class="chatPanelContainer">
          <ChatPanelAgent
            v-for="agent in agents"
            title="DeepResearch"
            :key="agent.threadId"
            :thread-id="agent.threadId"
            model-id="pangu"
            :messages="agent.messages"
            :params="agent.params"
            :session-type="sessionType"
          />
        </div>
        <div class="inputPanelContainer">
          <!-- <div class="inputBar">
            <div class="functionsBtnBox">
              <el-button type="primary" :icon="Back" round @click="$emit('change-page-type', 'text')">返回模型对话</el-button>
            </div>
            <el-select v-model="deepResearchType" placeholder="模式" class="drSelect">
              <el-option label="快速模式" value="fast" />
              <el-option label="专业模式" value="professional" />
            </el-select>
            <textarea ref="textareaRef" class="input" placeholder="请输入消息" @input="onInput" @keydown="handleKeyDown"
              v-model="inputBarContent" rows="3"></textarea>
            <img v-if="!sendStatus.loading" :class="inputBarContent ? 'sendButton' : 'sendButtonDisable'"
              :src="inputBarContent ? planeSvg : planeDisableSvg" alt="send" @click="sendDeepSearch" />
            <img v-else class="sendButton" :src="stopSvg" alt="send" @click="stopSend" />
            <el-button
              v-show="isShowMoni"
              circle
              type="success"
              @click="clickMonitor()"
              :icon="Monitor"
            ></el-button>
          </div>-->

          <div class="inputBar">
            <!-- 第一行：返回按钮 -->
            <div class="top-row">
              <el-button
                type="primary"
                :icon="Back"
                round
                @click="$emit('change-page-type', 'text')"
                class="backButton"
              >返回模型对话</el-button>
            </div>

            <!-- 第二行：输入框 -->
            <div class="middle-row">
              <textarea
                ref="textareaRef"
                class="input"
                placeholder="请输入消息"
                @input="onInput"
                @keydown="handleKeyDown"
                v-model="inputBarContent"
                rows="3"
              ></textarea>
            </div>

            <!-- 第三行：配置选择和发送按钮 -->
            <div class="bottom-row">
              <div class="bottom-left">
                <el-select v-model="deepResearchType" placeholder="模式" class="drSelect">
                  <el-option label="快速模式" value="fast" />
                  <el-option label="专业模式" value="professional" />
                </el-select>
                <el-button
                  type="primary"
                  style="margin-left: 20px;"
                  @click="openDialog"
                >添加搜索网站</el-button>
              </div>

              <div class="bottom-right">
                <img
                  v-if="!sendStatus.loading"
                  :class="inputBarContent ? 'sendButton' : 'sendButtonDisable'"
                  :src="inputBarContent ? planeSvg : planeDisableSvg"
                  alt="发送"
                  @click="sendDeepSearch"
                />
                <img v-else class="sendButton" :src="stopSvg" alt="停止" @click="stopSend" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <el-dialog
     v-model="addUserUrlOpen"
     title="添加搜索网站"
     width="600px"
     @close="handleClose"
    > 
     <div class="dynamic-inputs">
       <div v-for="(item, index) in inputList" :key="index" class="input-item">
         <el-input
           v-model="item.value"
           placeholder="请输入网址"
           style="flex: 1"
         />
         <div class="action-buttons">
           <el-button
             type="success"
             circle
             :icon="Plus"
             @click="addInput(index)"
             v-if="index === inputList.length - 1"
           />
           <el-button
             type="danger"
             circle
             :icon="Minus"
             @click="removeInput(index)"
             v-if="inputList.length > 1"
           />
         </div>
       </div>
     </div>

      <div style="margin-top: 20px; font-size: 16px;">
        是否搜索其他网站
        <el-tooltip
        effect="dark"
        content="关闭后仅搜索输入的网站"
        placement="top"
        >
          <el-switch v-model="is_search" active-text="是" inactive-text="否" style="margin-left: 20px;" :disabled = 'inputList.length===0 || (inputList.length===1&&inputList[0].value==="")'/>
        </el-tooltip>
      </div>

     <template #footer>
       <span class="dialog-footer">
         <el-button @click="addUserUrlOpen = false">取消</el-button>
         <el-button type="primary" @click="handleConfirm">确认</el-button>
       </span>
     </template>
    </el-dialog>
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

.leftControlArea {
  flex-grow: 0;
  flex-shrink: 0;
  /* flex-basis: 256px; */
  /* width: 256px; */
  width: 15%;
  display: flex;
}

.rightControlArea {
  flex-grow: 1;
  flex-shrink: 1;
  flex-basis: 0;
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
  flex-direction: column;
  /* 改为纵向布局 */
  gap: 12px;
  /* 行间距 */
  padding: 16px;
  border-radius: 6px;
  width: 100%;
  background-color: white;
  box-shadow: 0 2px 4px 0 rgb(0 0 0 / 20%);
}

.top-row {
  display: flex;
  justify-content: flex-start;
  /* 左对齐 */
}

.middle-row {
  width: 100%;
}

.bottom-row {
  display: flex;
  justify-content: space-between;
  /* 左右分列 */
  align-items: center;
}

.bottom-left,
.bottom-right {
  display: flex;
  align-items: center;
}

/* 按钮样式 */
.sendButton,
.sendButtonDisable {
  width: 32px;
  height: 32px;
  cursor: pointer;
  transition: opacity 0.3s;
}

.sendButton:hover {
  opacity: 0.8;
}

.sendButtonDisable {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 返回按钮调整 */
.backButton {
  margin-bottom: 4px;
  /* 与下一行的间距 */
}

.inputBar .input {
  --font-size: 16px;
  flex: 1 1 0;
  outline: none;
  border: none;
  font-size: var(--font-size);
  line-height: 1.2;
  padding: 0;
  margin: 0;
  resize: none;
  width:100%;
  min-height: 48px;
  color: black;
  /* min-height: calc(var(--font-size) * 1.2 * 1); */
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
  min-height: 0;
  /* 同样要能收缩，否则 overflow 不生效 */
  height: 100%;
  overflow-y: auto;
  /* 打开纵向滚动 */
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
  transition: all 0.1s ease-in-out;
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
  transition: all 0.1s ease-in-out;
}

.chatHistoryItemDeleteButton:hover {
  background-color: red;
  color: white;
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

.modal h3 {
  margin-top: 0;
}

.model-list li {
  margin-bottom: 8px;
  position: relative;
}

.param-item label {
  width: 100%;
  display: block;
  font-size: 34px;
  font-weight: bold;
}

/* --------- 公共主样式 ---------- */
input[type="range"] {
  -webkit-appearance: none;
  /* 去掉默认样式 */
  width: 100%;
  height: 4px;
  /* 轨道高度 */
  margin: 0;
  background: rgb(223, 223, 223);
  /* 用浅蓝做底色 */
  border-radius: 2px;
  /* 用 background‐image + background‐size 来画已滑过的深蓝部分 */
  background-image: linear-gradient(rgb(0, 103, 209), rgb(0, 103, 209));
  background-repeat: no-repeat;
  /* 下面三个变量我们在模板里挂上，让它能动态变化 */
  background-size: calc(
      (var(--value) - var(--min)) / (var(--max) - var(--min)) * 100%
    )
    100%;
}

input[type="range"]:focus {
  outline: none;
}

/* --------- Webkit 系列 (Chrome/Safari/Edge) ---------- */
input[type="range"]::-webkit-slider-runnable-track {
  height: 4px;
  background: transparent;
  /* 已经用外层 background 画了，这里透明即可 */
}

input[type="range"]::-webkit-slider-thumb {
  --thumb: 16px;
  --track: 3px;
  -webkit-appearance: none;
  width: var(--thumb);
  height: var(--thumb);
  background: rgb(255, 255, 255);
  border: var(--track) solid rgb(0, 103, 209);
  /* 深蓝边框 */
  border-radius: 50%;
  margin-top: calc((var(--thumb) - var(--track)) / 2 * -1);
  /* =-(thumb/2 - track/2)，让 thumb 居中 */
  cursor: pointer;
}

input[type="range"][disabled] {
  background-image: linear-gradient(rgb(126, 126, 126), rgb(126, 126, 126));
}

input[type="range"][disabled]::-webkit-slider-thumb {
  border: var(--track) solid rgb(126, 126, 126);
  /* 深蓝边框 */
}

.message-row {
  margin-left: 16px;
  margin-right: 16px;
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 12px;
  max-width: 100%;
  height: calc(100vh - 315px);
  overflow: auto;
}

.bubble {
  max-width: 100%;
  padding: 8px 12px;
  word-wrap: break-word;
  line-height: 1;
  overflow-wrap: break-word;
  word-break: break-word;
  /* 或者 break-all，根据需求 */
  white-space: normal;
  /* 保证空格可折行 */
  background: #fafafa;
  color: #333;
  border-radius: 4px 16px 16px 16px;
  /* 增加右边 margin，避免太贴边 */
  margin-right: auto;
}

.bubble > * {
  max-width: 100% !important;
  white-space: pre-wrap;
  margin: 0;
}

.bubble > pre,
.bubble > code {
  font-family: "Consolas", "Courier New", monospace;
}

.bubble > *:first-child {
  margin-top: 10px;
}

.bubble :deep(p) {
  white-space: pre-wrap;
  line-height: 1.4;
  color: #333;
  /* margin: 10px 0; */
}

.bubble > *:last-child {
  margin-bottom: 10px;
}

.bubble :deep(div) {
  margin: 20px 0;
  padding: 20px;
  background-color: rgb(244, 244, 245);
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.25);
}

.bubble :deep(strong) {
  font-weight: 550;
}

.bubble :deep(h2) {
  color: #191919;
  font-size: 16px;
  line-height: 1;
  margin: 10px 0;
}

.bubble :deep(h3) {
  color: #191919;
  font-size: 16px;
  line-height: 1;
  margin: 20px 0;
}

.bubble :deep(ol) {
  list-style-type: none;
  padding-left: 15px;
  margin: 0;
  counter-reset: item;
  /* 初始化计数器 */
}

.bubble :deep(ol li) {
  position: relative;
  /* 使伪元素能够s相对于列表项定位 */
  padding-left: 20px;
  /* 为自定义前缀留出空间 */
}

.bubble :deep(ol li:has(> a)::before) {
  content: "[" counter(item, decimal) "]";
  position: absolute;
  color: #5c7bff;
  left: 0;
  counter-increment: item;
}

.bubble :deep(ul) {
  /* list-style: none; */
  /* padding-left: 10px; */
  padding-left: 20px;
  margin: 0;
}

.bubble :deep(ul li) {
  /* display: inline-block; */
  line-height: 20px;
  font-size: 14px;
}

.bubble :deep(code) {
}

.bubble :deep(pre) {
  /* background-color: rgb(214, 214, 214); */
  background-color: #282c34;
  border-radius: 5px;
  padding: 10px;
  margin: 20px 0 10px 0;
}

.bubble :deep(pre code) {
  font-family: "Microsoft YaHei";
  background-color: transparent;
  color: #abb2bf;
  padding: 1rem;
  border-radius: 0px;
}

.bubble :deep(table) {
  table-layout: fixed;
  min-width: 100%;
  width: fit-content;
  margin: 20px 0;
  text-align: start;
  border-radius: 2px 2px 0 0;
  border-collapse: separate;
  border-spacing: 0;
}

.bubble :deep(table tr th) {
  left: 0px;
  text-align: center;
  /* border-start-start-radius: 2px; */
  background-color: #f5f6fd;
  border: 1px rgba(39, 39, 42, 0.5) solid;
  padding: 10px;
}

.bubble :deep(table tr td) {
  left: 0px;
  text-align: center;
  /* text-align: right; */
  /* border-start-start-radius: 2px; */
  background-color: #f5f6fd;
  border: 1px rgba(39, 39, 42, 0.1) solid;
  padding: 10px;
}

.bubble :deep(table tr td code) {
  font-family: monospace;
  font-size: 14px;
}

.bubble :deep(a) {
  /* display: block; */
  color: #5c7bff;
  text-decoration: none;
}

#bubbleThink {
  /* background-color: rgb(244, 244, 245); */
  color: #555;
  line-height: 14px;
  border-left: 2px solid #f0f0f0;
  border-radius: 0;
}

.closeButton {
  border: none;
  background: transparent;
  font-size: 16px;
  line-height: 16px;
  cursor: pointer;
  color: #999;
  padding: 4px;
  outline: none;
  border-radius: 33%;
  width: 20px;
  height: 20px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  transition: all 0.1s ease-in-out;
}

.closeButton:hover {
  background-color: red;
  color: white;
}

.pcHeader {
  height: 72px;
  padding: 0 16px;
  background: linear-gradient(to bottom, #f2f5fe, #f6f8fe, #fff);
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  max-width: 100%;
  min-width: 0%;
}

.rightControlPanel {
  height: 100%;
  width: 100%;
  background-color: white;
  border-radius: 16px;
  box-shadow: 0 2px 4px 0 rgb(0 0 0 / 20%);
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  /* gap: 16px; */
}

.pcSlider {
  margin: 0 20px 10px 20px;
  width: 95%;
}

.inputBar select {
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ccc;
  background-color: white;
  color: black;
  cursor: pointer;
}

.rightRadios {
  margin: 10px 0 10px 10px;
}

.drSelect {
  width: 100px;
}

.dynamic-inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 4px;
}
</style>