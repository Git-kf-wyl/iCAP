<script setup>
import {nextTick, onBeforeUnmount, onMounted, ref, watch} from 'vue'
import {ModelService} from "@/services/modelService.js";
import {useAIModelStore} from "@/stores/aiModel.js";
import MarkdownIt from 'markdown-it';
import copySvg from '@/assets/copy.svg'
import copySvgOk from '@/assets/copy_ok.svg'
import refreshSvg from '@/assets/refresh.svg'
import likeSvg from '@/assets/like.svg'
import likeFillSvg from '@/assets/like_fill.svg'
import unlikeSvg from '@/assets/unlike.svg'
import unlikeFillSvg from '@/assets/unlike_fill.svg'
import {useChatStore} from "@/stores/chat.js";
import {useImageChatStore} from "@/stores/imageChat.js";
import {useAudioChatStore} from "@/stores/audioChat.js";
import {useVideoChatStore} from "@/stores/videoChat.js";
import { marked } from "marked";
import {Bottom} from "@element-plus/icons-vue";
import { isLocalChatModelById } from "@/utils/ModelUtils.js"

const markdown = new MarkdownIt();

const props = defineProps({
  threadId: {type: String, required: true},    // 新增：传入 threadId
  modelId: {type: String, required: true},
  messages: {type: Array, required: true},
  params: {
    type: Object,
    default: () => ({
      max_tokens: 1000,
      temperature: 0.7,
      top_p: 0.9,
      top_k: 40
    })
  },
  sessionType: "text"
})
let chatStore = useChatStore()
const modelStore = useAIModelStore()

const isCopyingArray = ref([])
const thinkLabelOpen = ref('<think>')
const thinkLabelClose = ref('</think>')

// 默认展开
const activeNames = Array.from({ length: 1000 }, () => 'tab1')
const deepResearchActiveNames = Array.from({ length: 1000 }, () => 'tab2')
const deepResearchThinkActiveNames = Array.from({ length: 1000 }, () => 'tab3')
const handleChange = (val) => {
  // console.log('handleChange', val)
};

const NO_PRE_THINK_MODEL_NAME_ARR = ['Qwen3-30B-A3-Thinking-2507', 'Qwen3-Next-80B-A3B-Thinking'];

// 定义一个 delete-thread 事件
const emit = defineEmits(['delete-thread'])

const scrollContainer = ref(null)
// 自动滚动状态
const isAutoScrolling = ref(true)

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
// const handleScroll = () => {
//   if (isAutoScrolling.value) {
//     isAutoScrolling.value = false;
//   }
// };
const handleScroll = () =>{
  const container = scrollContainer.value;
  // 判断是否滚动到底部（保留5px容差）
  const atBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 5;

  if (!atBottom) {
    // 未到底部时进入手动模式
    isAutoScrolling.value = false;
  } else if (!isAutoScrolling.value) {
    // 已到底部且当前是手动模式时，切回自动模式
    isAutoScrolling.value = true;
  }
}

const scrollToBottom = () => {
  const container = scrollContainer.value;
  container.scrollTop = container.scrollHeight;
  isAutoScrolling.value = true; // 切回自动模式
}

// 滚动到指定元素
const scrollToElement = (element) => {
  if (!element || !scrollContainer.value || !isAutoScrolling.value) return

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
    if (itemRefs.value.length > 0 && isAutoScrolling.value) {
      scrollToElement(itemRefs.value[itemRefs.value.length - 1])
      isAutoScrolling.value = false
    }
  })
}

onMounted(async () => {
  switch (props.sessionType) {
    case "image":
      chatStore = useImageChatStore()
      break;
    case "audio":
      chatStore = useAudioChatStore()
      break;
    case "video":
      chatStore = useVideoChatStore()
      break;
    default:
      chatStore = useChatStore()
      break;
  }
  // 设置自动滚动
  // nextTick(scrollToLastItem)
  nextTick(scrollToBottom)
})

// 监听items变化
watch(props.messages, () => {
  if (props.messages.at(-1).isFinished) {
    return
  }
  // 清空元素引用数组，在nextTick后重新收集
  // itemRefs.value = []
  // if (!isAutoScrolling.value) {
  //   // nextTick(() => {
  //   //   isAutoScrolling.value = true
  //   //   // 等待DOM更新和引用收集完成
  //   //   nextTick(scrollToLastItem)
  //   // })
  // }
  if (isAutoScrolling.value) {
    nextTick(() => {
      const container = scrollContainer.value;
      container.scrollTop = container.scrollHeight;
    });
  }
}, { deep: true })

watch(() => props.modelId, () => {
  const model = modelStore.getModelById(props.modelId)
  if (!model) return
  thinkLabelOpen.value = model.config.filter.head ?? '<think>'
  thinkLabelClose.value = model.config.filter.tail ?? '</think>'
})

// 清理
onBeforeUnmount(() => {
  console.log('onBeforeUnmount')
  cancelAnimationFrame(scrollAnimationFrame)
})

// 核心：用正则，把 <think> 标签包裹的内容替换成 <details><summary>思考过程</summary>xxx</details>
function transformThinkTags(content) {
  // 注意：[\s\S]*? 为非贪婪匹配，才能捕获多行
  const thinkRegex = /<think>([\s\S]*?)<\/think>/g
  // 将捕获到的内容替换成 <details> ... <details>
  return content.replace(thinkRegex, (_, thinkText) => {
    return `<details class="think-details">
              <summary>思考过程</summary>
              <div class="think-content">${thinkText}</div>
            </details>`
  })
}

const processDeepResult = (rawResult) => {
  const deepResearchRegex = /<deepResearch>([\s\S]*?)(?:<\/deepResearch>|$)/;
  let deepResearch = rawResult.match(deepResearchRegex);
  if (!deepResearch || deepResearch.length < 1) {
    // console.log('rawResult')
    // console.log(rawResult)
    return [];
  }
  // console.log('deepResearch')
  // console.log(deepResearch)

  deepResearch = marked(deepResearch[1]);
  // 初始化结果对象
  const result = {
    think: '',
    tool_search_result: '',
    actions: [],
    outline: '',
    research_report: ''
  };

  // 匹配思考内容
  const thinkMatch = deepResearch.match(/<think>([\s\S]*?)(<\/think>|$)/);
  if (thinkMatch) result.think = thinkMatch[1].trim();

  // const outputMatch = rawResult.match(/<\/think>([\s\S]*?)(<tool_search_result>|$)/);
  // if (outputMatch) result.output = outputMatch[1].trim();

  // 匹配所有搜索结果
  const toolMatches = [];
  const regex = /<tool_search_result>([\s\S]*?)<\/tool_search_result>|<tool_search_result>([\s\S]*)$/g;
  let match;
  while ((match = regex.exec(deepResearch)) !== null) {
    // 检查第一个捕获组（有闭合标签）或第二个捕获组（无闭合标签）
    const content = match[1] !== undefined ? match[1] : match[2];
    toolMatches.push(content.trim());
  }
  if (toolMatches.length > 0) {
    // 用空格拼接所有结果（如需换行可用 \n）
    result.tool_search_result = toolMatches.join('\n\n');
  }

  // 匹配访问和总结信息（位于</tool_search_result>和<outline>之间）
  const actionSectionMatch = deepResearch.match(/<\/tool_search_result>([\s\S]*?)(<outline>|$)/);
  if (actionSectionMatch) {
    const actionText = actionSectionMatch[1].trim();
    // 使用正则提取所有动作信息
    const actionRegex = /(正在访问网页\s*：?\s*\S+|正在总结网页\s*：?\s*\S+)/g;
    let match;
    while ((match = actionRegex.exec(actionText)) !== null) {
      // 规范化动作描述（统一冒号格式）
      const normalized = match[0]
      // .replace(/\s*:\s*/, ': ')
      // .replace(/\s+/g, ' ');
      result.actions.push(normalized);
    }
  }

  // 匹配大纲
  const outlineMatch = deepResearch.match(/<outline>([\s\S]*?)(<\/outline>|$)/);
  if (outlineMatch) result.outline = outlineMatch[1].trim().replaceAll('[cite]', '\<i\>').replaceAll('[\/cite]', '\<\/i\>');

  // 匹配最终报告
  const reportMatch = deepResearch.match(/<research_report>([\s\S]*?)(<\/research_report>|$)/);
  if (reportMatch) result.research_report = reportMatch[1].trim();

  // console.log('DRResult')
  // console.log(result)
  return result;
};


const processResult = (rawResult) => {
  const deepResearchRegex = /<deepResearch>([\s\S]*?)(?:<\/deepResearch>|$)/;
  rawResult = rawResult.match(deepResearchRegex);
  if (!rawResult || rawResult.length < 1) {
    // console.log('rawResult')
    // console.log(rawResult)
    return {
      steps: [],
      tool_search_result: "",
      originOutline: "",
      outline: "",
      research_report: "",
    };
  }
  // console.log('deepResearch')
  // console.log(deepResearch)

  rawResult = marked(rawResult[1]);
  // rawResult = localRawResult.value
  const result = {
    steps: [],
    tool_search_result: "",
    originOutline: "",
    outline: "",
    research_report: "",
  };

  // 提取大纲和报告部分（保持不变）
  const outlineMatch = rawResult.match(/<outline>([\s\S]*?)(<\/outline>|$)/);
  if (outlineMatch) {
    result.originOutline = outlineMatch[1]
      .trim()
      .replaceAll("[cite]", "<i>")
      .replaceAll("[/cite]", "</i>");
  }

  const outlineAfterMatch = rawResult.match(/<\/outline>([\s\S]*?)(<research_report>|$)/);
  if (outlineAfterMatch) {
    result.outline = outlineAfterMatch[1]
      .trim()
      .replaceAll("[cite]", "<i>")
      .replaceAll("[/cite]", "</i>");
  }

  const reportMatch = rawResult.match(/<research_report>([\s\S]*?)(<\/research_report>|$)/);
  if (reportMatch) result.research_report = reportMatch[1].trim();

  // 获取步骤部分（到<outline>之前）
  const outlineIndex = rawResult.indexOf("<outline>");
  const stepsPart = outlineIndex !== -1
    ? rawResult.substring(0, outlineIndex)
    : rawResult;

  // 匹配所有步骤块（从到下一个或<outline>或结尾）
  const stepBlockRegex = /<think>([\s\S]*?)(?=<outline>|<think>|$)/g;
  const toolContents = []; // 保存所有工具调用内容

  let stepBlockMatch;
  while ((stepBlockMatch = stepBlockRegex.exec(stepsPart)) !== null) {
    // console.log('stepBlockMatch')
    // console.log(stepBlockMatch)
    const stepBlock = stepBlockMatch[0].trim(); // 当前步骤块内容
    const toolMatches = [];

    // 提取所有<tool_search_result>标签内容
    const toolRegex = /<tool_search_result>([\s\S]*?)(<\/tool_search_result>|$)/g;
    let toolMatch;
    while ((toolMatch = toolRegex.exec(stepBlock)) !== null) {
      // console.log('toolMatch')
      // console.log(toolMatch)
      toolMatches.push({
        content: toolMatch[1].trim(),
        endIndex: toolMatch.index + toolMatch[1].length // 记录结束位置
      });
    }

    const thinkRegex = /<think>([\s\S]*?)(<\/think>|$)/g;
    let thinkMatch;
    thinkMatch = thinkRegex.exec(stepBlock)
    // console.log('thinkMatch')
    // console.log(thinkMatch)

    const actions = [];
    const actionsRegex = /(?:[\s\S]*<\/tool_search_result>)?([\s\S]*)$/;
    let actionsMatch;
    actionsMatch = actionsRegex.exec(stepBlock)
    // console.log('actionsMatch')
    // console.log(actionsMatch)
    if (actionsMatch) {
      // 按行分割并过滤空行
      actionsMatch[1].split('\n').forEach(line => {
        const trimmed = line.trim();
        if (trimmed && (trimmed.startsWith('正在总结网页：') || trimmed.startsWith('正在访问网页：'))) actions.push(trimmed);
      });
    }

    const toolSearchResults = toolMatches.map(m => {
      toolContents.push(m.content); // 添加到总工具内容
      return m.content;
    });

    result.steps.push({
      think: thinkMatch[1],
      tool_search_results: toolSearchResults,
      actions:actions
    });
  }

  // console.log("DRResultNew!!!");
  // console.log(result);
  return result;
};

const processOrighinOutline = (msg)=>{
  return  blankTarget(marked(processResult(msg.content).originOutline))
  // return '<div class="originOutline>"</br>' + blankTarget(marked(processResult(msg.content).originOutline)) + '</div>'
}

const processOutline = (msg)=>{
  return  blankTarget(marked(processResult(msg.content).outline))
  // return '<div class="droutline>"</br>' + blankTarget(marked(processResult(msg.content).outline)) + '</div>'
}

const processReport = (msg)=>{
  return  blankTarget(marked(processResult(msg.content).research_report))
  // return '<div class="research_report>"</br>' + blankTarget(marked(processResult(msg.content).research_report)) + '</div>'
}

const processAgentResult = (rawResult) => {
  const deepResearchRegex = /<deepResearch>([\s\S]*?)(?:<\/deepResearch>|$)/;
  let deepResearch = rawResult.match(deepResearchRegex);
  if (!deepResearch || deepResearch.length < 1) {
    // console.log('rawResult')
    // console.log(rawResult)
    return [];
  }
  // console.log('deepResearch')
  // console.log(deepResearch)

  deepResearch = marked(deepResearch[1]);
  const loadingPattern = /<p>\S\sLoading\.*<\/p>/gs;

  if (loadingPattern.test(deepResearch)) {
    return [
      {
        id: 1,
        think: "",
        content: deepResearch,
      },
    ];
  }

  deepResearch = deepResearch
    .replace(/<a/g, '<a target="_blank"')
    .replace(/<hr>/g, "")
    .replace(/<tool_search_result>/g, "<div>")
    .replace(/<\/tool_search_result>/g, "</div>");

  // 修改后的正则表达式：<think>标签变为可选匹配
  const regex = /<ROUND(\d+)>(?:(.*?)<\/think>)?(.*?)(?=<ROUND\d+>|$)/gs;

  let matches;
  const result = [];

  while ((matches = regex.exec(deepResearch)) !== null) {
    const id = parseInt(matches[1], 10);
    // 有标签时：matches[2]=think内容, matches[3]=content
    // 无<think>标签时：matches[2]=undefined, matches[3]=全部内容
    const think = matches[2]?.trim() || ""; // 处理无think标签情况
    const content = matches[3]?.trim() || "";

    result.push({ id, think, content });
  }

  return result;
}

function findThinking(content, modelId) {
  const deepResearchRegex = /(?:<deepResearch>(.*?)<\/deepResearch>)?(.*)/;
  if(content.startsWith('<deepResearch>') && content.lastIndexOf('<\/deepResearch>')===-1){
    return ''
  }else if(content.startsWith('<deepResearch>') && content.lastIndexOf('<\/deepResearch>')!==-1){
    content = content.match(deepResearchRegex)[2]
  }
  // console.log('tempcontent')
  // console.log(content.match(deepResearchRegex))
  // 特殊适配
  if (NO_PRE_THINK_MODEL_NAME_ARR.includes(modelStore.getModelName(modelId))) {
    const indexOf = content.indexOf(thinkLabelClose.value)
    return indexOf > 0 ? content.slice(0, indexOf) : content
  }
  if (!content.startsWith(thinkLabelOpen.value)) {
    return ''
  }
  // 移除开头的thinkLabelOpen
  let str = content.slice(thinkLabelOpen.value.length);

  // 查找最后一个thinkLabelClose的位置
  const lastIndex = str.lastIndexOf(thinkLabelClose.value);

  // 如果找到结束标签，截取开头到最后一个结束标签之前的内容
  if (lastIndex !== -1) {
    str = str.slice(0, lastIndex).replace(/<think>/g, '\n').replace(/<\/think>/g, '');
  }
  // console.log('str');
  // console.log(str)
  // 未找到结束标签时返回整个str（原逻辑）
  return str;
}

function findResult(content, modelId) {
  // 检查内容是否以<deepResearch>开头且没有闭合标签
if (content.startsWith('<deepResearch>') && content.indexOf('</deepResearch>') === -1) {
    return '深度搜索中...';
}

// 正则表达式：匹配<deepResearch>标签（可选）及后续内容
// 使用s标志使.能匹配换行符，捕获标签外的内容
const deepResearchRegex = /(?:<deepResearch>.*?<\/deepResearch>)?(.*)/s;

// 提取标签外内容（始终能匹配到结果）
content = content.match(deepResearchRegex)[1];
  // console.log('tempcontent')
  // console.log(content.match(deepResearchRegex))
  // 特殊适配
  if (NO_PRE_THINK_MODEL_NAME_ARR.includes(modelStore.getModelName(modelId))) {
    const indexOf = content.indexOf(thinkLabelClose.value)
    return indexOf > 0 ? content.slice(indexOf + thinkLabelClose.value.length) : ''
  }
  if (!content.startsWith(thinkLabelOpen.value)) {
    return content
  }
  // const index = content.indexOf(thinkLabelClose.value)
  const lastIndex = content.lastIndexOf(thinkLabelClose.value);
  if (lastIndex > 0) {
    return content.slice(lastIndex + thinkLabelClose.value.length).replace(/<answer>\*/g, '\n\*').replace(/<answer>/g, '').replace(/<\/answer>/g, '');
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

const formattedContent =(str)=>{
  // return str.replace(/\n/g, '<br>');
  return str
}

function blankTarget(html) {
  return html.replace(/<a/g, '<a target="_blank"');
}
</script>

<template>
  <div class="chatPanel">
    <div class="header">
      <div class="modelInfo">
        <img class="modelIcon" :src=ModelService.getModelIcon(props.modelId) alt="avatar" />
        <span>{{ modelStore.getModelName(props.modelId) }}</span>
        <el-tag v-if="!isLocalChatModelById(props.modelId)" effect="light" hit round type="warning" size="small">外部模型</el-tag>
      </div>
      <!--      <button class="paramSettingButton">参数设置</button>-->
      <!-- 2. 新增 “×” 删除按钮 -->
      <button class="closeButton" @click="emit('delete-thread', props.threadId)">✖</button>
    </div>
    <div class="log-bottom">
      <el-button v-show="!isAutoScrolling" type="primary" :icon="Bottom" circle @click="scrollToBottom" />
    </div>
    <div class="messages" ref="scrollContainer" @scroll="handleScroll">
      <div v-for="(msg, idx) in props.messages" :key="idx" :ref="setItemRef">
        <div class="message-row" :class="msg.role" v-if="msg.role !== 'assistant'">
          <div style="display: flex; flex-direction: column">
            <!-- 显示上传的图片 -->
            <el-image v-if="msg.content.previewUrl && msg.content.previewUrl.startsWith('data:image/')" :src="msg.content.previewUrl"
              alt="预览图" :max-scale="7" :min-scale="0.2" :preview-src-list="[msg.content.previewUrl]"
              style="max-width: 300px;margin-bottom: 10px" />
            <!-- 显示上传的音频 -->
            <audio v-if="msg.content.previewUrl && msg.content.previewUrl.startsWith('data:audio/')" :src="msg.content.previewUrl"
                   controls controlsList="nodownload noplaybackrate" style="margin:0 0 10px auto"></audio>
            <!-- 显示上传的视频 -->
            <video v-if="msg.content.previewUrl && msg.content.previewUrl.startsWith('data:video/')" :src="msg.content.previewUrl"
                   controls controlsList="nodownload noplaybackrate" oncontextmenu="return false;" style="max-width: 300px; margin-bottom: 10px"></video>
            <!-- <div class="bubble" v-html="$sanitizeHtml(markdown.render(msg.content.text ? msg.content.text: msg.content))"/> -->
            <!-- <div class="bubble" v-text="formattedContent(msg.content.text ? msg.content.text: msg.content)"/> -->
            <div class="bubble">
              <pre style="font-family:'Microsoft YaHei';">{{ msg.content.text ? msg.content.text : msg.content }}</pre>
            </div>
            <el-tooltip content="复制" :hide-after="20">
              <img :src="!isCopyingArray[idx] ? copySvg : copySvgOk" alt="copy" class="icon-bubble"
                style="margin-left: auto;"
                @click="legacyCopy(idx, findResult(msg.content.text ? msg.content.text : msg.content, modelId))" />
            </el-tooltip>
          </div>
        </div>
        <div class="message-row" :class="msg.role" v-else>
          <div style="display: flex; flex-direction: column">
            <el-collapse
              v-if="processResult(msg.content).steps.length>0 && processResult(msg.content).steps[0].think.trim()"
              v-model="deepResearchActiveNames[(idx - 1) / 2]" @change="handleChange" style="margin-bottom: 10px">
              <el-collapse-item title="深度搜索结果：" name="tab2">
                <div id="bubbleThink" style="padding-left: 20px;">
                  <!-- <div v-for="(round, index) in processAgentResult(msg.content)" :key="index">
                  <el-collapse v-if="round.think" v-model="deepResearchThinkActiveNames[(idx - 1) / 2]" @change="handleChange"
                    style="margin-bottom: 10px">
                    <el-collapse-item title="已深度思考" name="tab3">
                      <div id="bubbleThink" class="bubble" v-text="round.think" />
                    </el-collapse-item>
                  </el-collapse>
                  <div class="deepResearchBubble" v-if="round.content" v-html="$sanitizeHtml(round.content)" />
                </div> -->

                  <!-- <el-collapse v-if="processDeepResult(msg.content).think" v-model="activeNames[(idx - 1) / 2]"
                  @change="handleChange" style="margin-bottom: 10px">
                  <el-collapse-item title="已深度思考" name="tab3">
                    <div id="bubbleThink" class="bubble" v-text="marked(processDeepResult(msg.content).think)" />
                  </el-collapse-item>
                </el-collapse>
                <h2 v-if="processDeepResult(msg.content).tool_search_result">搜索结果：</h2>
                <div class="bubble" v-if="processDeepResult(msg.content).tool_search_result"
                  v-html="$sanitizeHtml(blankTarget(marked(processDeepResult(msg.content).tool_search_result)))" />
                  <h2 v-if="processDeepResult(msg.content).actions?.length>0">网页访问与总结：</h2>
                <div class="bubble" v-for="(result, index) in processDeepResult(msg.content).actions" :key="index"
                  v-html="$sanitizeHtml(blankTarget(marked(result)))"></div>
                  <h2 v-if="processDeepResult(msg.content).outline">大纲：</h2>
                <div class="bubble" v-if="processDeepResult(msg.content).outline"
                  v-html="$sanitizeHtml(blankTarget(marked(processDeepResult(msg.content).outline)))" />
                  <h2 v-if="processDeepResult(msg.content).research_report">总结报告：</h2>
                <div class="bubble" v-if="processDeepResult(msg.content).research_report"
                  v-html="$sanitizeHtml(blankTarget(marked(processDeepResult(msg.content).research_report)))" /> -->

                  <div v-for="(step, index) in processResult(msg.content).steps" :key="index">
                    <el-collapse v-if="step.think" v-model="deepResearchThinkActiveNames[(idx - 1) / 2]"
                      @change="handleChange" style="margin-bottom: 10px">
                      <el-collapse-item title="思考过程" name="tab3">
                        <div id="bubbleThink" class="bubble" v-html="$sanitizeHtml(step.think)" />
                      </el-collapse-item>
                    </el-collapse>

                    <h2 v-if="step.tool_search_results.length>0">搜索结果：</h2>
                    <div class="bubble" v-for="(result, index) in step.tool_search_results" :key="index"
                      v-html="$sanitizeHtml(blankTarget(marked(result)))" />
                    <h2 v-if="step.actions.length > 0">网站总结：</h2>
                    <div class="bubble" v-for="(action, index) in step.actions" :key="index"
                      v-html="$sanitizeHtml(blankTarget(marked(action)))"></div>
                  </div>

                  <h2 v-if="processResult(msg.content).originOutline">初始大纲：</h2>
                  <div class="bubble" v-if="processResult(msg.content).originOutline"
                    v-html="$sanitizeHtml(processOrighinOutline(msg))" />

                  <h2 v-if="processResult(msg.content).outline">大纲：</h2>
                  <div class="bubble" v-if="processResult(msg.content).outline" v-html="$sanitizeHtml(processOutline(msg))" />

                  <h2 v-if="processResult(msg.content).research_report">总结报告：</h2>
                  <div class="bubble" v-if="processResult(msg.content).research_report" v-html="$sanitizeHtml(processReport(msg))" />
                  <div v-show="!msg.isFinished" v-loading="!msg.isFinished" element-loading-text="生成报告中......"
                    style="height:40px;width:100px"></div>
                </div>
              </el-collapse-item>
            </el-collapse>
            <el-collapse v-if="findThinking(msg.content, modelId).trim()" v-model="activeNames[(idx - 1) / 2]"
              @change="handleChange" style="margin-bottom: 10px">
              <el-collapse-item title="已深度思考" name="tab1">
                <div id="bubbleThink" class="bubble" v-html="$sanitizeHtml(markdown.render(findThinking(msg.content, modelId)))" />
              </el-collapse-item>
            </el-collapse>
            <div class="bubble" v-if="findResult(msg.content, modelId)"
              v-html="$sanitizeHtml(markdown.render(findResult(msg.content, modelId)))" />
            <!-- <div class='bubble' v-text="msg.content"></div> -->

            <div class="icon-bubble-container" v-if="msg.isFinished">
              <el-tooltip content="复制" :hide-after="20">
                <img :src="!isCopyingArray[idx] ? copySvg : copySvgOk" alt="copy" class="icon-bubble"
                  @click="legacyCopy(idx, findResult(msg.content, modelId))" />
              </el-tooltip>
              <el-tooltip v-if="false" content="重新生成" :hide-after="20">
                <img :src="refreshSvg" alt="refresh" class="icon-bubble" @click="refreshChat()" />
              </el-tooltip>
              <el-tooltip content="喜欢" :hide-after="20">
                <img :src="msg.like !== 1 ? likeSvg : likeFillSvg" alt="like" class="icon-bubble"
                  @click="msg.like !== 1 ? doLike(idx, 1) : doLike(idx, 0)" />
              </el-tooltip>
              <el-tooltip content="不喜欢" :hide-after="20">
                <img :src="msg.like !== -1 ? unlikeSvg : unlikeFillSvg" alt="unlike" class="icon-bubble"
                  @click="msg.like !== -1 ? doLike(idx, -1) : doLike(idx, 0)" />
              </el-tooltip>
            </div>
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

.chatPanel {
  display: flex;
  flex-direction: column;
  flex: 1;
  position: relative;
  background-color: transparent;
  overflow: hidden;
  height: 100%;
  min-height: 0;
  position: relative;
}

.header {
  height: 48px;
  padding: 0 16px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  max-width: 100%;
  min-width: 0%;
}

.modelInfo {
  flex: 1 1 0;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  align-items: center;
  gap: 8px;
  color: rgb(60, 60, 60);
}

.modelInfo span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.modelIcon {
  width: 28px;
  height: 28px;
  border-radius: 6px;
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
  padding: 8px 32px;
  overflow-y: auto;
  flex: 1 1 0;
  min-height: 0;
  max-width: 100%;
}

.message-row {
  display: flex;
  align-items: flex-start;
  margin-bottom: 10px;
  gap: 0;
  max-width: 100%;
}

/* AI 消息靠左 */
.message-row.assistant {
  justify-content: flex-start;
  flex-direction: row;
  padding-right: 42px;
}

/* 用户消息靠右 */
.message-row.user {
  flex-direction: row-reverse;
  padding-left: 58px;
}

.el-collapse-item__content {
  padding-bottom: 0 !important;
}

.bubble {
  max-width: 100%;
  padding: 6px 10px;
  word-wrap: break-word;
  line-height: 1.5;
  overflow-wrap: break-word;
  word-break: break-word;
  white-space: normal;
  font-size: 13px;
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

.bubble h2{
  font-size: 16px;
}

.bubble h5{
  font-size: 14px;
  margin: 10px 0;
}

.bubble strong{
  font-size: 16px;
}

.bubble blockquote{
  margin: 0;
}

.bubble p{
  margin: 0;
}

.bubble table {
  table-layout: fixed;
  min-width: 100%;
  width: fit-content;
  margin: 20px 0;
  text-align: start;
  border-radius: 2px 2px 0 0;
  border-collapse: separate;
  border-spacing: 0;
}

.bubble table tr th {
  left: 0px;
  text-align: center;
  /* border-start-start-radius: 2px; */
  background-color: #f5f6fd;
  border: 1px rgba(39, 39, 42, 0.5) solid;
  padding: 10px;
}

.bubble table tr td {
  left: 0px;
  text-align: center;
  /* text-align: right; */
  /* border-start-start-radius: 2px; */
  background-color: #f5f6fd;
  border: 1px rgba(39, 39, 42, 0.1) solid;
  padding: 10px;
}

.bubble table tr td code {
  font-family: monospace;
  font-size: 14px;
}

.bubble ul,ol{
  margin: 0;
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

.icon-bubble {
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
  transition: all 0.1s ease-in-out;
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

.log-bottom{
  position: absolute;
  bottom: 0; /* 贴紧父盒子底部 */
  left: 50%; /* 左侧定位到父盒子50%位置 */
  transform: translateX(-50%);
}
</style>
