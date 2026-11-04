<script setup>
import {nextTick, onBeforeUnmount, onMounted, ref, watch} from 'vue'
// import MarkdownIt from 'markdown-it';
import {marked} from 'marked';
import {useAgentChatStore} from "@/stores/agentChat.js";
import {useDeepSearchChatStore} from '@/stores/deepResearchChat.js'
import {getAgentFile} from "@/api/runService.js";

// const markdown = new MarkdownIt();

const props = defineProps({
  taskId: {type: String, required: true},
  isShow: {type: Boolean, required: true},
  messages: {type: Array, required: true},
})
let chatStore = props.title==='DeepResearch'?useDeepSearchChatStore():useAgentChatStore()

const isCopyingArray = ref([])
const thinkLabelOpen = ref('<think>')
const thinkLabelClose = ref('</think>')
// 默认展开
const activeNames = Array.from({length: 1000}, () => 'tab1')
const handleChange = (val) => {
  console.log('handleChange', val)
};

// 定义一个 delete-thread 事件
const emit = defineEmits(['delete-thread'])

const scrollContainer = ref(null)
// 自动滚动状态
const isAutoScrolling = ref(false)

const itemRefs = ref([])

let scrollAnimationFrame = null

// 设置元素引用
const setItemRef = (el) => {
  if (el) {
    itemRefs.value.push(el)
    isCopyingArray.value.push(false)
  }
}

// 处理用户滚动事件
const handleScroll = () => {
  if (isAutoScrolling.value) {
    isAutoScrolling.value = false
  }
}


// 滚动到指定元素
const scrollToElement = (element) => {
  if (!element || !scrollContainer.value) return

  const container = scrollContainer.value;
  // 计算最后一个元素的底部位置
  const targetPosition = element.offsetTop + element.offsetHeight - container.offsetHeight;

  // 取消之前的动画
  cancelAnimationFrame(scrollAnimationFrame);

  const startPosition = container.scrollTop;
  const distance = targetPosition - startPosition;
  const duration = 500; // 动画时间(ms)
  let startTime = null;

  const animateScroll = (timestamp) => {
    if (!startTime) startTime = timestamp;
    const elapsed = timestamp - startTime;
    const progress = Math.min(elapsed / duration, 1);

    container.scrollTop = startPosition + distance * progress;

    if (progress < 1) {
      scrollAnimationFrame = requestAnimationFrame(animateScroll);
    }
  };

  scrollAnimationFrame = requestAnimationFrame(animateScroll);
}

// 滚动到底部
const scrollToLastItem = () => {
  nextTick(() => {
    if (itemRefs.value.length > 0) {
      scrollToElement(itemRefs.value[itemRefs.value.length - 1])
      isAutoScrolling.value = false
    }
  })
}

onMounted(async () => {
  // 设置自动滚动
  nextTick(scrollToLastItem)
})

watch(props.messages, (newVal) => {
  // if (!newVal) {
  //   return
  // }
  // 清空元素引用数组，在nextTick后重新收集
  itemRefs.value = []
  if (!isAutoScrolling.value) {
    nextTick(() => {
      isAutoScrolling.value = true
      // 等待DOM更新和引用收集完成
      nextTick(scrollToLastItem)
    })
  }
}, { deep: true })

// 清理
onBeforeUnmount(() => {
  console.log('onBeforeUnmount')
  cancelAnimationFrame(scrollAnimationFrame)
})

function findThinking(content) {
  // 特殊适配
  if (content.startsWith(thinkLabelOpen.value)) {
    content = thinkLabelOpen.value + content
  }
  if (!content.startsWith(thinkLabelOpen.value)) {
    return ''
  }
  let str = content.slice(thinkLabelOpen.value.length);
  const index = str.indexOf(thinkLabelClose.value)
  if (index > 0) {
    str = str.slice(0, index)
  }
  return str
}

function findResult(content, modelId) {
  // 特殊适配
  if (NO_PRE_THINK_MODEL_NAME_ARR.includes(modelStore.getModelName(modelId))) {
    const indexOf = content.indexOf(thinkLabelClose.value)
    return indexOf > 0 ? content.slice(indexOf + thinkLabelClose.value.length) : ''
  }
  if (!content.startsWith(thinkLabelOpen.value)) {
    return content
  }
  const index = content.indexOf(thinkLabelClose.value)
  if (index > 0) {
    return content.slice(index + thinkLabelClose.value.length)
  }
  return ''
}

// 复制最佳方案，适用于Https访问
const copyToClipboard = async (id, textResult) => {
  if (isCopyingArray.value[id]) return
  try {
    // 使用现代 Clipboard API
    await navigator.clipboard.writeText(textResult);
    isCopyingArray.value[id] = true
    setTimeout(() => {
      isCopyingArray.value[id] = false
    }, 1000);
  } catch (err) {
    console.error('复制失败:', err);
    isCopyingArray.value[id] = false
    legacyCopy(id, textResult)
  }
}

// 复制的替代方案
function legacyCopy(id, text) {
  if (isCopyingArray.value[id]) return
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = 0;
  document.body.appendChild(textarea);
  textarea.select();

  try {
    const success = document.execCommand('copy');
    document.body.removeChild(textarea);
    isCopyingArray.value[id] = true
    setTimeout(() => {
      isCopyingArray.value[id] = false
    }, 1000);
    return success;
  } catch (err) {
    document.body.removeChild(textarea);
    console.error('legacyCopy 复制失败: ', err);
    isCopyingArray.value[id] = false
    return false;
  }
}

const refreshChat = async () => {

}

const doLike = (msgId, like) => {
  chatStore.updateAssistantMessageLike(like, msgId, props.threadId)
}

function blankTarget(html) {
  return html.replace(/<a/g, '<a target="_blank"');
}

</script>

<template>
  <div class="chatPanelAgent">
    <div class="header">
      <div class="modelInfo">
        <h4>PPT生成助手的电脑</h4>
      </div>
      <!-- 2. 新增 “×” 删除按钮 -->
      <button class="closeButton" @click="emit('delete-thread', props.taskId)">✖</button>
    </div>
    <div class="messages" ref="scrollContainer" @scroll="handleScroll">
      <div
          v-for="(msg, idx) in props.messages"
          :key="idx"
          :ref="setItemRef"
      >
        <div class="message-row message-row.assistant">
	        <div style="display: flex; flex-direction: column">
            <el-collapse v-if="findThinking(msg.content, modelId)" v-model="activeNames[(idx - 1) / 2]"
                         @change="handleChange" style="margin-bottom: 10px">
              <el-collapse-item title="思考过程" name="tab1">
                <div id="bubbleThink" class="bubble" v-text="findThinking(msg.content, modelId)"/>
              </el-collapse-item>
            </el-collapse>
            <div class="bubble"
                 v-if="props.msg"
                 v-html="$sanitizeHtml(blankTarget(marked(props.msg)))"/>
          </div>
	      </div>
	    </div>
        </div>
    <!--    <div class="shader"></div>-->
  </div>
</template>


<style>
* {
  box-sizing: border-box;
}

.chatPanelAgent {
  display: flex;
  flex-direction: column;
  flex: 1;
  background-color: #fff;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  height: 100%; /* 或给一个固定高度 */
  min-height: 0;
  position: relative;
}

.header {
  height: 72px;
  padding: 0 16px;
  background: linear-gradient(to bottom, #f2f5fe, #f6f8fe, #fff);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  max-width: 100%;
  min-width: 0%;
}

.modelInfo {
  flex: 1 1 0;
  font-size: 16px;
  font-weight: bold;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  align-items: center;
  gap: 12px;
}

.modelInfo span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.modelIcon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
}

.paramSettingButton {
  height: 32px;
  padding: 4px 16px;
  border: 1px solid #c9c9c9;
  border-radius: 8px;
  background: #fff;
  color: #323232;
  cursor: pointer;
  margin-left: auto;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.paramSettingButton:hover {
  background: #f0f0f0;
}

.paramSettingButton:active {
  background: #dedede;
}

.messages {
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow-y: auto;
  /* 关键：抢占 .chatPanel header 之外的所有剩余空间 */
  flex: 1 1 0;
  /* 确保自己也可以收缩，否则 overflow 依然无效 */
  min-height: 0;
  max-width: 100%;
}

.message-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 12px;
  max-width: 100%;
}

/* AI 消息靠左 */
.message-row.assistant {
  justify-content: flex-start;
  /* avatar | bubble */
  flex-direction: row;
  padding-right: 42px;
}

/* 用户消息靠右 */
.message-row.user {
  /* bubble | avatar */
  flex-direction: row-reverse;
  padding-left: 58px;
}

.avatar {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  border-radius: 50%;
  object-fit: cover;
  object-position: top center;
}

.message-row.assistant .avatar {
  border-radius: 8px;
}

.el-collapse-item__content {
  padding-bottom: 0 !important;
}

.bubble {
  max-width: 100%;
  padding: 8px 12px;
  word-wrap: break-word;
  line-height: 1.4;
  overflow-wrap: break-word;
  word-break: break-word; /* 或者 break-all，根据需求 */
  white-space: normal; /* 保证空格可折行 */
}

.bubble > * {
  max-width: 100% !important;
  white-space: pre-wrap;
}

.bubble > pre,
.bubble > code {
  font-family: "Consolas", "Courier New", monospace;
}

.bubble > *:first-child {
  margin-top: 0;
}

.bubble p {
  white-space: pre-wrap;
}

.bubble > *:last-child {
  margin-bottom: 0;
}

/* 下载图标样式 */
.download-icon {
  width: 24px;
  height: 24px;
  margin-top: 8px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.download-icon:hover {
  opacity: 0.8;
}

/* 确保图标在 bubble 下方显示 */
.bubble + .download-icon {
  display: inline-block;
  vertical-align: top;
  margin-left: 8px;
}

/* AI 气泡样式 */
.message-row.assistant .bubble {
  background: #f9f9f9;
  color: #333;
  border-radius: 4px 16px 16px 16px;
  /* 增加右边 margin，避免太贴边 */
  margin-right: auto;
}

#bubbleThink {
  background: #fff;
  color: #555;
  border-left: 2px solid #f0f0f0;
  border-radius: 0;
}


/* 用户气泡样式 */
.message-row.user .bubble {
  background: #007aff;
  color: #fff;
  border-radius: 16px 16px 4px 16px;
  /* 增加左边 margin，避免太贴边 */
  margin-left: auto;
}

.shader {
  width: 100%;
  height: 32px;
  position: absolute;
  left: 0;
  bottom: 0;
  background: linear-gradient(to top, white, white 16px, transparent 32px);
}

.icon-bubble-container {
  margin-top: 5px;
  display: flex;
  align-items: center;
}

.icon-bubble, .ppt-icon-bubble {
  border-radius: 5px;
  margin: 2px;
  padding: 3px;
  width: 24px;
  height: 24px;
}

.icon-bubble:hover {
  background: #f5f5f5;
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
  transition: all 0.1s ease-in-out;;
}

.closeButton:hover {
  background-color: red;
  color: white;
}

details.think-details {
  padding: 4px 2px;
  margin-bottom: 4px;
  border-radius: 8px;
  width: 100%;
  color: grey;
}

details.think-details > summary {
  cursor: pointer;
  outline: none;
}

details.think-details[open] {
  /* 展开时的一些样式 */
}

details.think-details .think-content {
  margin-top: 4px;
  color: #666;
  white-space: pre-wrap; /* 如果有换行，可以保留 */
}

</style>
