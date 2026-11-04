<script setup>
import {
  ref,
  computed,
  watch,
  onMounted,
  reactive,
  onBeforeUnmount,
  toRaw,
} from "vue";
import { useAIModelStore } from "@/stores/aiModel";
import specIcon from "@/assets/icons/specIcon.svg";
import tagIcon from "@/assets/icons/tagIcon.svg";
import typeIcon from "@/assets/icons/typeIcon.svg";
import { ModelService } from "@/services/modelService.js";
import router from "@/router/index.js";
import { ElMessage } from "element-plus";
import modelNewsBg from "@/assets/modelNewsBg.png";
import modelSelectionBg from "@/assets/modelSelectionBg.png";
import speakerIcon from "@/assets/speaker.svg";
import strategy from "@/assets/strategy.png";
import { Delete, Minus, Search } from "@element-plus/icons-vue";
import { useStore } from "vuex";
import { isModelAvailable, isLocalChatModel } from "@/utils/ModelUtils.js";
import dayjs from "dayjs";
import _ from "lodash"; // 引入lodash
import * as XLSX from "xlsx";
import { manager_list } from "@/consts/copyrightConsts";

const token = ref("");
const store = useAIModelStore();
const detailStore = useStore();

// header 筛选
const deployType = ref("all"); // 'all' | 'local' | 'external'
const searchTerm = ref("");

// 左侧面板筛选
const selectedCategories = ref([]);
const selectedTags = ref([]);
const selectedSizeRange = ref({ label: "全部", min: 0, max: Infinity });

watch(selectedSizeRange, () => {
  // console.log("selectedSizeRange");
  // console.log(selectedSizeRange.value);
});

// 静态规格：LLM、MLLM
const allCategories = [
  { label: "自然语言", value: "LLM" },
  { label: "多模态", value: "MLLM" },
];

// 静态规格：reason chat tools math coder others
const allTags = [
  { label: "reason", value: "reason" },
  { label: "chat", value: "chat" },
  { label: "tools", value: "tools" },
  { label: "math", value: "math" },
  { label: "coder", value: "coder" },
  { label: "others", value: "others" },
  { label: "ASR", value: "ASR" },
  { label: "MT", value: "MT" },
  { label: "TTS", value: "TTS" },
];

// 静态规格：全部、10B以下、10-50B、50-100B、100B以上
const sizeRanges = [
  { label: "全部", min: 0, max: Infinity },
  { label: "10B以下", min: 0, max: 10 },
  { label: "10-50B", min: 10, max: 50 },
  { label: "50-100B", min: 50, max: 100 },
  { label: "100B以上", min: 100, max: Infinity },
];

const modelWhiteName = [
  "DeepSeek-V4.1-Flash-w8a8",
  "DeepSeek-V4-Flash-0731-w8a8",
  "DeepSeek-V4-Flash_w8a8_mtp",
  "Qwen3.6-27B",
  "Qwen3.8-27B",
  "Qwen3.6-35B-A3B",
  // "MiniMax-M2.5",
  "Qwen3.5-27B",
  // "Qwen3.5-122B-A10B",
  // "Qwen3-VL-32B-Instruct",
  "Qwen3-32B",
  // "gemini-3-pro-preview(外网api,请注意信息安全)",
  // "gemini-3-pro-preview-thinking(外网api,请注意信息安全)",
  "DeepSeek-V3.2(chat模型,外网api,请注意信息安全)",
  "DeepSeek-V3.2(reasoner模型,外网api,请注意信息安全)",
  "GLM-5(外网api,请注意信息安全)",
  // "Qwen2.5-Omni-7B",
  "Qwen3-Omni-30B-A3B-Instruct",
  "gpt-5-thinking-all",
  "gemma-4-12B-it",
  "gemma-4-31B-it",
  "openpangu-2.0-flash",
  "openpangu-2.0-pro",
  "LongCat-2.0",
];

/* 处理分页相关 */
const pageSize = ref(12);
const currentPage = ref(1);

// 识别 admin 用户：admin 不受白名单限制，直接展示全量模型
const isAdmin = computed(() => username.value === "admin");

// 白名单过滤：admin 跳过白名单，其余用户仅显示白名单内模型
const whiteListFilter = () => true;

const totalItems = computed(() => {
  return filteredModels.value.filter(whiteListFilter).length;
});
const curDataList = computed(() => {
  // console.log("csh, curDatalist");
  // 先过滤白名单模型，再进行分页切片，确保每页展示满 pageSize 个模型
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  // console.log("csh, curDatalist 更新", start, end);
  console.log("filteredModels");
  console.log(filteredModels.value);
  console.log(
    filteredModels.value
      // .filter((item) => modelWhiteName.includes(item.model_id))
      // .slice(start, end)
  );
  return filteredModels.value.filter(whiteListFilter).slice(start, end)
});
const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1; // 切换每页数量时回到第一页
};
const handleCurrentChange = (val) => {
  currentPage.value = val;
};

// 过滤逻辑
const filteredModels = computed(() => {
  const lowerSearchTerm = searchTerm.value?.toLowerCase();
  const isLocalDeploy = deployType.value === "local";
  const isNativeDeploy = deployType.value === "native";
  const isExternalDeploy = deployType.value === "external";

  return store.models.filter((m) => {
    const { info, is_available, status } = m;

    // 部署类型过滤
    if (
      isLocalDeploy &&
      (!info.isInternalDeployed || info.tags.includes("native"))
    )
      return false;
    if (isNativeDeploy && !info.tags.includes("native")) return false;
    if (isExternalDeploy && info.isInternalDeployed) return false;

    // 名称搜索
    if (
      lowerSearchTerm &&
      !info.model_name.toLowerCase().includes(lowerSearchTerm)
    )
      return false;

    // 分类筛选
    if (
      selectedCategories.value.length > 0 &&
      !selectedCategories.value.some(
        (item) => item.value && info.category.includes(item.value)
      )
    ) {
      return false;
    }

    // 标签筛选
    if (
      selectedTags.value.length > 0 &&
      !selectedTags.value.some(
        (item) => item.value && info.tags.includes(item.value)
      )
    ) {
      return false;
    }

    // 规格（size）筛选
    if (
      selectedSizeRange.value &&
      (info.size < selectedSizeRange.value.min ||
        info.size > selectedSizeRange.value.max)
    ) {
      return false;
    }

    // 是否显示全部模型
    if (isShowAvailableModel.value && (!is_available || !status)) return false;

    return true;
  });
});

const filteredByDate = computed(() => {
  const end = dayjs().endOf("day");
  const start = dayjs().subtract(30, "day").startOf("day");

  return [...store.models].filter((model) => {
    const taskDate = dayjs(model.info.creation_date);
    return taskDate.isAfter(start) && taskDate.isBefore(end);
  });
});

const currentIndex = ref(0);
const intervalTimer = ref(null);

const currentID = computed(() => {
  if (filteredByDate.value.length === 0) return "暂无数据";
  const item = filteredByDate.value[currentIndex.value];
  return `${item.model_id}`;
});

const currentDesc = computed(() => {
  if (filteredByDate.value.length === 0) return "暂无数据";
  const item = filteredByDate.value[currentIndex.value];
  return `${item.info.model_desc}`;
});

const showModelIntroduce = ref(false);

const isShowAvailableModel = ref(true);
const lsShowModelValue = localStorage.getItem("showAvailableModel");
if (lsShowModelValue != null) {
  isShowAvailableModel.value =
    localStorage.getItem("showAvailableModel") === "1";
}

const onShowAvailableModelChange = (newValue) => {
  isShowAvailableModel.value = newValue;
  localStorage.setItem("showAvailableModel", newValue ? "1" : "0");
};

// 注册模型按钮
function onRegister(model) {
  if (model instanceof Event) model = null;
  if (model) {
    router.push({
      path: "/models/manage",
      query: {
        modelId: model.model_id,
      },
    });
  } else {
    router.push({
      path: "/models/manage", query: {register: "1"}
    });
  }
}

const username = ref("");
const addFormRef = ref(null);
const isShowToApplyTable = ref(false);
const toApplyList = ref([]);
const isDoneInput = ref([]);

const form = reactive({
  model_name: "",
  model_desc: "",
  isInternalDeployed: true,
  create_time: "",
  creator: "",
  isDone: false,
});

const initialFormData = {
  model_name: "",
  model_desc: "",
  isInternalDeployed: true,
  create_time: "",
  creator: "",
  isDone: false,
};

const categoryOptions = [
  { label: "自然语言大模型", value: "LLM" },
  { label: "多模态大模型", value: "MLLM" },
];
const yesNoOptions = [
  { label: "是", value: true },
  { label: "否", value: false },
];

const isShowApplyDialog = ref(false);
function applyToDeploy() {
  isShowApplyDialog.value = true;
}

function closeApplyDialog() {
  isShowApplyDialog.value = false;
  resetFormData();
}

function getToApplyList() {
  isDoneInput.value = [];
  isShowToApplyTable.value = true;
  ModelService.getApplyDeployList()
    .then((res) => {
      toApplyList.value = res;
      console.log("getToApplyList ok");
    })
    .catch((error) => {
      console.error("getToApplyList", error);
      ElMessage.error(`失败: ${error.message}`);
    });
}

const isShowSupportedModel = ref(false);
const supportedModelData = ref([]);

const excellMapping = {
  模型: "modelName",
  "NPU-910B4(32GB)": "NPU",
  "V100 32GB": "V100",
  是否量化: "isQuantification",
  部署顺序: "sequence",
  资源: "resource",
};

const columnOrder = [
  "发布时间",
  "发布机构",
  "模型名称",
  "模型架构",
  "支持的框架",
  "已使用部署框架",
  "卡信息说明",
  "vllm环境要求(优先)",
  "Mindie环境要求",
  // "POST请求内容",
  // "能力",
];

const excelMapping = {
  发布时间: "releaseTime",
  发布机构: "publisher",
  模型名称: "modelName",
  模型架构: "modelArch",
  支持的框架: "supportedFrameworks",
  已使用部署框架: "deployedFramework",
  卡信息说明: "gpuSpec",
  所需910B3卡数量: "gpuSpec910B3",
  所需910B4卡数量: "gpuSpec910B4",
  所需GPUV100卡数量: "gpuSpecGPUV100",
  "vllm环境要求(优先)": "vllmEnvReq",
  vllm部署命令: "vllmDeployCommand",
  性能速率: "performanceRate",
  并发数量: "concurrency",
  最大上下文长度: "maxContextLength",
  Mindie环境要求: "mindieEnvReq",
  payload样例: "payloadExample",
  POST请求内容: "payloadExample",
  能力: "capabilities",
};

const formatExcelDate = (serial) => {
  // 处理非数字类型直接返回
  if (typeof serial !== "number") return serial;

  // Excel日期计算（1900年1月1日为起点）
  const utcDays = Math.floor(serial) - 25569; // 25569是1970-01-01的序列号
  const date = new Date(utcDays * 86400000);

  // 格式化为YYYY/MM/DD
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");

  return `${year}/${month}/${day}`;
};

// 从卡信息说明文本中解析出 910B3 / 910B4 卡数量（兼容旧版"卡信息说明"列）
// 支持格式：910B3(8卡)、910B4(8卡)，910B3(8卡)、16 * 910B3、4*910B4
const parseGpuSpecFromText = (gpuSpec) => {
  const parsed = { gpuSpec910B3: undefined, gpuSpec910B4: undefined };
  if (!gpuSpec || typeof gpuSpec !== "string") return parsed;
  const pattern = /(\d+)\s*\*\s*910B([34])|910B([34])\s*[（(]\s*(\d+)\s*[）)]?\s*卡?/g;
  let match;
  while ((match = pattern.exec(gpuSpec)) !== null) {
    let type, count;
    if (match[2]) {
      type = match[2];
      count = match[1];
    } else {
      type = match[3];
      count = match[4];
    }
    if (type === "3") {
      parsed.gpuSpec910B3 = Number(count);
    } else if (type === "4") {
      parsed.gpuSpec910B4 = Number(count);
    }
  }
  return parsed;
};

// 模型货柜能力
const handelExcellData = async (index) => {
  // 获取Excel文件的二进制数据
  const response = await fetch("/v1/model_shelf.xlsx");
  const data = await response.arrayBuffer();
  const workbook = XLSX.read(data, { type: "buffer" });
  const sheetName = workbook.SheetNames[index];
  const sheet = workbook.Sheets[sheetName];
  // 获取列标题并生成映射数组
  const headersRow = XLSX.utils.sheet_to_json(sheet, { header: 1 })[0];
  const mappedHeaders = headersRow.map((header) => excelMapping[header]);

  // 解析数据并转换列名
  const jsonData = XLSX.utils.sheet_to_json(sheet, { header: 1 }).slice(1);
  let transformedData = jsonData.map((row) => {
    const obj = {};
    row.forEach((value, index) => {
      if (mappedHeaders[index]) {
        // 特殊处理发布时间列
        if (
          mappedHeaders[index] === "releaseTime" &&
          typeof value === "number"
        ) {
          obj[mappedHeaders[index]] = formatExcelDate(value);
        } else {
          obj[mappedHeaders[index]] = value;
        }
      }
    });
    return obj;
  });

  transformedData.sort((a, b) => {
    return a.ranking_Rating - b.ranking_Rating;
  });
  transformedData = transformedData.map((item) => {
    const parsed = parseGpuSpecFromText(item.gpuSpec);
    return {
      ...item,
      gpuSpec910B3: item.gpuSpec910B3 ?? parsed.gpuSpec910B3,
      gpuSpec910B4: item.gpuSpec910B4 ?? parsed.gpuSpec910B4,
    };
  });
  console.log(transformedData);
  supportedModelData.value = transformedData;
};

const getToSupportedModel = () => {
  isShowSupportedModel.value = true;
  handelExcellData(0);
};

// 生成模型名称的过滤选项
const modelNameFilterOptions = computed(() => {
  const uniqueNames = new Set();
  supportedModelData.value.forEach((item) => {
    uniqueNames.add(item.modelName);
  });
  return Array.from(uniqueNames).map((name) => ({
    text: name,
    value: name,
  }));
});

// 生成能力的过滤选项
const capabilityFilterOptions = computed(() => {
  const uniqueCapabilities = new Set();
  supportedModelData.value.forEach((item) => {
    // 处理能力数据：字符串转数组（如 "对话,问答" -> ["对话","问答"]）
    const capabilities =
      typeof item.capabilities === "string"
        ? item.capabilities.split(",").map((cap) => cap.trim())
        : item.capabilities || [];

    capabilities.forEach((cap) => uniqueCapabilities.add(cap));
  });
  return Array.from(uniqueCapabilities).map((cap) => ({
    text: cap,
    value: cap,
  }));
});

// 模型名称过滤方法
const handleModelNameFilter = (value, row) => {
  return row.modelName === value;
};

// 能力过滤方法
const handleCapabilityFilter = (value, row) => {
  // 统一处理能力数据格式
  const rowCapabilities =
    typeof row.capabilities === "string"
      ? row.capabilities.split(",").map((cap) => cap.trim())
      : row.capabilities || [];

  return rowCapabilities.includes(value);
};

const tableHeaderStyle = {
  textAlign: "center",
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
};

const rules = {
  model_name: [
    { required: true, message: "请填写正确的模型名称", trigger: "blur" },
  ],
  model_desc: [
    { required: true, message: "请填写部署模型的价值或作用", trigger: "blur" },
  ],
  isInternalDeployed: [
    { required: true, message: "请选择是否内部部署", trigger: "change" },
  ],
};

function commitApplyDeploy() {
  addFormRef.value.validate(async (valid) => {
    if (!valid) {
      return ElMessage.error("请完善申请信息");
    }

    isShowApplyDialog.value = false;
    form.creator = username.value;
    ModelService.applyDeployModel(form)
      .then((res) => {
        console.log("applyDeployModel is ok");
        ElMessage.success("提交成功");
      })
      .catch((err) => {
        console.error("applyDeployModel", err);
        ElMessage.error(`失败: ${err.message}`);
      });
  });
}

function commitIsDone(row, index) {
  const curData = toApplyList.value.find(
    (applyData) => applyData.model_name === row.model_name
  );
  curData.isDone = isDoneInput.value[index];
  ModelService.applyDeployModel(curData)
    .then((res) => {
      console.log("commitIsDone is ok");
      ElMessage.success("提交成功");
    })
    .catch((err) => {
      console.error("commitIsDone", err);
      ElMessage.error(`失败: ${err.message}`);
    });
  isDoneInput.value = [];
}

function resetFormData() {
  Object.keys(initialFormData).forEach((key) => {
    form[key] = initialFormData[key];
  });
}

const isClosed = ref(false);
const screenWidth = ref("250px");
const hideScreening = () => {
  isClosed.value = !isClosed.value;
  const newValue = screenWidth.value === "250px" ? "0px" : "250px";
  setTimeout(() => {
    screenWidth.value = newValue;
    const screeningElement = document.querySelector(".screening");
    if (screeningElement) {
      screeningElement.style.marginLeft = newValue === "250px" ? "20px" : "0px";
    }
  }, 0);
};

// 这个方法用来页面跳转，并把 model_id 传过去
function onExplore(model) {
  if (model.model_id === "pangu718B") {
    window.open("https://pangu-chat.tools.huawei.com/", "_blank");
  } else {
    router.push({
      path: "/chat",
      query: {
        modelId: model.model_id,
      },
    });
  }
}

watch(
  () => detailStore.getters.getSelectedCategories,
  (newSelectedCategories) => {
    selectedCategories.value = newSelectedCategories;
  }
);

watch(
  () => detailStore.getters.getSelectedTags,
  (newSelectedTags) => {
    selectedTags.value = newSelectedTags;
    console.log(selectedTags.value);
  }
);

watch(
  () => detailStore.getters.getSelectedSizeRange,
  (newSelectedSizeRange) => {
    selectedSizeRange.value = newSelectedSizeRange;
  }
);

watch(
  () => detailStore.getters.getDeployType,
  (newDeployType) => {
    deployType.value = newDeployType;
  }
);

watch(deployType, () => {
  detailStore.dispatch("updateDeployType", deployType.value);
});

function onOpenModelDetail(modelId) {
  detailStore.dispatch("updateSelectedCategories", selectedCategories.value);
  detailStore.dispatch("updateSelectedTags", selectedTags.value);
  detailStore.dispatch("updateSelectedSizeRange", selectedSizeRange.value);
  detailStore.dispatch("updateDeployType", deployType.value);
  router.push({
    path: "/modelSquare/details",
    query: {
      modelId: modelId,
    },
  });
}

async function deleteModel(modelId) {
  // 弹原生确认框
  const ok = window.confirm("确定要删除该模型吗？");
  if (!ok) return;

  try {
    await ModelService.deleteModelInfo(modelId);
    store.removeModel(modelId);
    ElMessage.success("删除成功");
  } catch (e) {
    ElMessage.error("删除失败");
  }
}

// 是否显示对话框
const showDialog = ref(false);

// 打开对话框
function openDialog() {
  showDialog.value = true;
}

// 关闭对话框
function closeDialog() {
  showDialog.value = false;
}

const getModelType = (value) => {
  return allCategories.find((cat) => cat.value === value).label ?? "大语言";
};

function getSizeLabel(size) {
  if (size == null || size === "" || !Number.isFinite(Number(size))) return "";
  const arr = sizeRanges
    .slice(1)
    .filter((item) => size >= item.min && size < item.max);
  if (arr.length > 0) {
    return arr[0].label;
  }
  return "";
}

const loadTaskData = async () => {
  if (store.models && store.models.length > 0) {
    console.log("taskStore.getTasks");
    console.log(store.models);
  } else {
    const data = await ModelService.getAllModelInfo();
    store.setModels(data);
  }
};

onMounted(async () => {
  detailStore.dispatch("updateDeployType", 'all');
  token.value = localStorage.getItem("username");
  await loadTaskData();
  username.value = localStorage.getItem("username");
  selectedCategories.value = detailStore.getters.getSelectedCategories;
  selectedTags.value = detailStore.getters.getSelectedTags;
  selectedSizeRange.value = detailStore.getters.getSelectedSizeRange;
  deployType.value = detailStore.getters.getDeployType;

  intervalTimer.value = setInterval(() => {
    currentIndex.value = (currentIndex.value + 1) % filteredByDate.value.length;
  }, 10000);

  // if (detailStore.getters.getShownIntroduction) {
  //   showModelIntroduce.value = true;
  //   detailStore.dispatch("updateShownIntroduction", false);
  // }

  // 从 localStorage 中获取 newModels 并解析为数组
  /* const newModelsStr = localStorage.getItem("newModels");
  const newModels = newModelsStr ? JSON.parse(newModelsStr) : [];

  // 获取filteredByDate的原始对象，避免代理对象的影响
  const rawFiltered = toRaw(filteredByDate.value);

  // 使用lodash的深度比较
  const newModelsNotChange = _.isEqual(newModels, rawFiltered);

  console.log("newModelsNotChange:", newModelsNotChange);

  if (
    (Array.isArray(newModels) && newModels.length === 0) ||
    !newModels ||
    !newModelsNotChange
  ) {
    console.log("更新 newModels!!!");
    showModelIntroduce.value = true;
    // 将 filteredByDate.value 存储到 localStorage
    localStorage.setItem("newModels", JSON.stringify(rawFiltered));
  }*/
});

onBeforeUnmount(() => {
  clearInterval(intervalTimer.value);
});
</script>

<template>
  <div class="model-square">
    <div class="news">
      <div
        class="model-news"
        :style="{ backgroundImage: `url(${modelNewsBg})` }"
        @click="showModelIntroduce=true"
      >
        <h4 class="title">{{ currentID }}</h4>
        <div class="desc">
          <img :src="speakerIcon" />
          <el-tooltip effect="dark" placement="bottom">
            <template #content>
              <div style="max-width:50rem">{{ currentDesc || "暂无描述" }}</div>
            </template>
            <p>{{ currentDesc|| '暂无描述' }}</p>
          </el-tooltip>
        </div>
      </div>

      <el-dialog
        v-model="showModelIntroduce"
        title="公告栏"
        width="800"
        center
        align-center
        style="background-color: rgb(198, 226, 255);max-height:800px;overflow: auto;"
      >
        <div v-for="(model) in filteredByDate" :key="model.model_id" class="oneModel">
          <div class="bulletin-title">
            <div class="blueCircle"></div>
            <div>{{ model.model_id }}</div>
          </div>
          <el-tooltip effect="dark" placement="bottom">
            <template #content>
              <div style="max-width:50rem">{{ model.info.model_desc || "暂无描述" }}</div>
            </template>
            <el-text line-clamp="2">{{ model.info.model_desc || "暂无描述" }}</el-text>
          </el-tooltip>
        </div>
        <template #footer>
          <div class="dialog-footer">
            <el-button type="primary" @click="showModelIntroduce = false">关闭</el-button>
          </div>
        </template>
      </el-dialog>

      <div
        class="model-selection"
        :style="{ backgroundImage: `url(${modelSelectionBg})` }"
        @click="openDialog"
      >
        <h4 class="title">点击查看模型选型策略</h4>
        <p class="desc">挑选、体验、评测、使用。4步选出合适模型</p>
      </div>

      <!-- 遮罩 + 对话框 -->
      <div v-if="showDialog" class="overlay" @click.self="closeDialog">
        <div class="dialog">
          <!-- 对话框头部 -->
          <div class="dialog-header">
            <h3 class="dialog-title">模型选型策略</h3>
            <button class="close-btn" @click="closeDialog">×</button>
          </div>
          <!-- 对话框内容：几张占位图 -->
          <div class="dialog-body">
            <img :src="strategy" :alt="`占位图`" />
          </div>
        </div>
      </div>

      <div
        class="model-selection"
        :style="{ backgroundImage: `url(${modelSelectionBg})` }"
        @click="applyToDeploy"
      >
        <h4 class="title">模型引入</h4>
        <p class="desc">如果没找到您想要的模型，可把需求提给我们，我们来帮忙引入</p>
      </div>

      <div
        class="model-selection"
        :style="{ backgroundImage: `url(${modelSelectionBg})` }"
        @click="getToSupportedModel"
      >
        <h4 class="title">模型货架</h4>
        <p class="desc">查看支持部署的模型信息</p>
      </div>
    </div>

    <!-- header 区 -->
    <header class="ms-header">
      <div class="ms-btns">
        <!-- <button :class="{ active: deployType === 'all' }" @click="deployType = 'all'">全部</button>
        <button :class="{ active: deployType === 'local' }" @click="deployType = 'local'">本地部署</button>
        <button :class="{ active: deployType === 'native' }" @click="deployType = 'native'">内网API</button>
        <button
          :class="{ active: deployType === 'external' }"
          @click="deployType = 'external'"
        >外网 API</button>-->
        <el-button class="closebtn" @click="hideScreening">
          <el-icon>
            <Operation />
          </el-icon>
          <span v-if="!isClosed">展开筛选器</span>
          <span v-else>隐藏筛选器</span>
        </el-button>
      </div>
      <div class="ms-search">
        <el-input v-model="searchTerm" type="text" placeholder="请输入模型名称" :suffix-icon="Search"></el-input>
        <el-tooltip content="已部署模型，点击这里注册">
          <button class="register-btn" @click="onRegister">模型注册</button>
        </el-tooltip>

        <!--el-tooltip :content="isShowAvailableModel ? '显示所有模型' : '显示可用模型'">
              <el-switch @change="onShowAvailableModelChange" v-model="isShowAvailableModel"
                         style="--el-switch-on-color: #0067D1"/>
        </el-tooltip-->
      </div>
    </header>

    <!-- 申请部署表单   -->
    <el-dialog title="申请部署" v-model="isShowApplyDialog" width="30%" draggable>
      <el-form
        :rules="rules"
        :model="form"
        label-width="auto"
        ref="addFormRef"
        style="max-width: 600px"
      >
        <el-form-item label="模型名称" prop="model_name" required>
          <el-input v-model="form.model_name" placeholder="请填写正确的模型名称" />
        </el-form-item>
        <el-form-item label="部署原因" prop="model_desc" required>
          <el-input type="textarea" v-model="form.model_desc" placeholder="请填写部署模型的价值或作用，方便部署人员通过" />
        </el-form-item>
        <el-form-item label="内部部署" prop="isInternalDeployed" required>
          <el-select v-model="form.isInternalDeployed" placeholder="请选择">
            <el-option
              v-for="opt in yesNoOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="getToApplyList">查看待部署模型</el-button>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="getToSupportedModel">查看已支持部署的模型</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeApplyDialog">取 消</el-button>
          <el-button type="primary" @click="commitApplyDeploy">确 定</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 待部署模型列表  -->
    <el-drawer v-model="isShowToApplyTable" title="申请模型部署列表" size="50%">
      <el-table
        :header-cell-style="tableHeaderStyle"
        :data="toApplyList"
        style="width: 100%"
        border
        stripe
      >
        <el-table-column prop="model_name" label="模型" width="150"></el-table-column>
        <el-table-column prop="model_desc" label="申请描述" min-width="200" />
        <el-table-column prop="isInternalDeployed" label="是否内部部署" width="80">
          <template #default="{ row }">{{ row.isInternalDeployed ? "是" : "否" }}</template>
        </el-table-column>
        <el-table-column prop="create_time" label="申请时间" width="100" />
        <el-table-column prop="creator" label="申请人" width="100" />
        <el-table-column prop="isDone" label="是否完成" width="60">
          <template #default="{ row }">{{ row.isDone ? "是" : "否" }}</template>
        </el-table-column>
        <el-table-column label="确认是否完成" width="200">
          <template #default="{ row, $index }">
            <div class="action-cell">
              <el-radio-group v-model="isDoneInput[$index]">
                <el-radio :value="true">Yes</el-radio>
                <el-radio :value="false">No</el-radio>
              </el-radio-group>
              <el-button size="small" type="primary" @click="commitIsDone(row, $index)">提交</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 已支持部署的模型列表  -->
    <el-drawer v-model="isShowSupportedModel" title="已支持部署的模型列表" size="90%">
      <el-table
        :header-cell-style="tableHeaderStyle"
        :data="supportedModelData"
        border
        stripe
        max-height="calc(100vh - 82px)"
      >
        <el-table-column prop="releaseTime" label="发布时间" :show-overflow-tooltip="true" width="120" />
        <el-table-column prop="publisher" label="发布机构" :show-overflow-tooltip="true" width="100" />
        <el-table-column
          prop="modelName"
          label="模型名称"
          :show-overflow-tooltip="true"
          width="300"
          :filters="modelNameFilterOptions"
          :filter-method="handleModelNameFilter"
        />3
        <el-table-column prop="modelArch" label="模型架构" :show-overflow-tooltip="true" width="130" />
        <el-table-column
          prop="supportedFrameworks"
          label="支持的框架"
          :show-overflow-tooltip="true"
          width="130"
        />
        <el-table-column
          prop="deployedFramework"
          label="已使用部署框架"
          :show-overflow-tooltip="true"
          width="130"
        />
        <el-table-column label="所需910B3卡数量" width="130" :show-overflow-tooltip="true">
          <template #default="{ row }">{{ row.gpuSpec910B3 ?? "-" }}</template>
        </el-table-column>
        <el-table-column label="所需910B4卡数量" width="130" :show-overflow-tooltip="true">
          <template #default="{ row }">{{ row.gpuSpec910B4 ?? "-" }}</template>
        </el-table-column>
        <el-table-column label="所需GPUV100卡数量" :show-overflow-tooltip="true" min-width="180">
          <template #default="{ row }">{{ row.gpuSpecGPUV100 ?? "-" }}</template>
        </el-table-column>
        <el-table-column prop="vllmEnvReq" label="vllm环境要求(优先)" :show-overflow-tooltip="true" min-width="150" />
        <el-table-column
          prop="vllmDeployCommand"
          label="vllm部署命令"
          :show-overflow-tooltip="true"
          min-width="220"
        />
        <el-table-column prop="performanceRate" label="性能速率" :show-overflow-tooltip="true" width="110" />
        <el-table-column prop="concurrency" label="并发数量" :show-overflow-tooltip="true" width="100" />
        <el-table-column prop="maxContextLength" label="最大上下文长度" :show-overflow-tooltip="true" width="120" />
        <el-table-column
          prop="mindieEnvReq"
          label="Mindie环境要求"
          :show-overflow-tooltip="true"
          width="160"
        />
        <el-table-column prop="payloadExample" label="payload样例" :show-overflow-tooltip="true" min-width="200">
          <template #default="{ row }">
            <el-input type="textarea" v-model="row.payloadExample" />
          </template>
        </el-table-column>
        <el-table-column
          prop="capabilities"
          label="能力"
          :show-overflow-tooltip="true"
          :filters="capabilityFilterOptions"
          :filter-method="handleCapabilityFilter"
        />
      </el-table>
    </el-drawer>

    <div class="ms-content">
      <!-- 左侧 filter panel -->
      <aside class="ms-filters" v-show="isClosed">
        <div style="font-size: 18px;font-weight: 700;">筛选</div>
        <div class="filter-group">
          <h4>
            <img :src="typeIcon" />类型
          </h4>
          <div class="tag-group">
            <div v-for="cat in allCategories" :key="cat.label" class="filter-item">
              <input
                type="checkbox"
                class="filter-radio"
                :id="`filter-cat-${cat.label}`"
                :value="cat"
                v-model="selectedCategories"
              />
              <label class="filter-label" :for="`filter-cat-${cat.label}`">{{ cat.label }}</label>
            </div>
          </div>
        </div>

        <div class="filter-group">
          <h4>
            <img :src="tagIcon" />标签
          </h4>
          <div class="tag-group">
            <div v-for="tag in allTags" :key="tag.label" class="filter-item">
              <input
                type="checkbox"
                class="filter-radio"
                :id="`filter-tag-${tag.label}`"
                :value="tag"
                v-model="selectedTags"
              />
              <label class="filter-label" :for="`filter-tag-${tag.label}`">{{ tag.label }}</label>
            </div>
          </div>
        </div>

        <div class="filter-group">
          <h4>
            <img :src="specIcon" />规格
          </h4>
          <div class="tag-group">
            <div v-for="r in sizeRanges" :key="r.label" class="filter-item">
              <input
                type="radio"
                name="sizeRange"
                class="filter-radio"
                :id="`filter-size-${r.label}`"
                :value="r"
                v-model="selectedSizeRange"
              />
              <label class="filter-label" :for="`filter-size-${r.label}`">{{ r.label }}</label>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧模型列表 / 卡片 -->
      <div style="display: flex; flex-direction: column; flex: 1">
        <div class="ms-list">
          <div v-if="curDataList.length === 0" class="empty-tip">暂无模型</div>
          <div v-else class="list-grid">
            <div
              v-for="m in curDataList"
              :key="m.model_id"
              :class="isModelAvailable(m) ? 'model-card-base model-card' : 'model-card-base model-card-disable'"
              @click="onOpenModelDetail(m.model_id)"
            >
              <!-- 第一行：图标 + 名称 -->
              <div class="card-header">
                <img
                  :class="isModelAvailable(m) ? 'model-icon-base' : 'model-icon-base model-icon-disable'"
                  :src="m.info.logo_url || ModelService.getModelIcon(m.model_id)"
                  alt="icon"
                />
                <div style="display: flex;flex-direction: column;width:80%">
                  <span
                    :class="isModelAvailable(m) ? 'model-name-base model-name' : 'model-name-base model-name-disable'"
                  >
                    {{
                    m.info.model_name }}
                  </span>
                  <el-tag
                    v-if="!m.info.isInternalDeployed"
                    effect="light"
                    hit
                    round
                    type="warning"
                    style="width:20%;font-weight: 700;margin-top: 5px;"
                  >外部模型</el-tag>
                </div>
                <div class="button-container" v-if="m.can_edit">
                  <el-link underline="never" @click.stop="onRegister(m)">
                    <el-icon class="editClass">
                      <Edit />
                    </el-icon>
                  </el-link>
                  <el-link underline="never" @click.stop="deleteModel(m.model_id)">
                    <el-icon class="editClass">
                      <Delete />
                    </el-icon>
                  </el-link>
                </div>
              </div>
              <!-- 第二行：描述 -->
              <el-tooltip>
                <template #content>
                  <div style="max-width:30rem">{{ m.info.model_desc || "暂无描述" }}</div>
                </template>
                <span class="card-desc">{{ m.info.model_desc || "暂无描述" }}</span>
              </el-tooltip>
              <!-- 第三行：标签 -->
              <div class="card-tags">
                <span
                  class="tag type-tag"
                  v-for="(cat, idx) in m.info.category"
                  :key="`cat-${idx}`"
                >
                  {{
                  getModelType(cat)
                  }}
                </span>
                <span
                  class="tag info-tag"
                  v-for="(tag, idx) in m.info.tags"
                  :key="`tag-${idx}`"
                >{{ tag }}</span>
                <span class="tag size-tag" v-if="getSizeLabel(m.info.size) !== ''">
                  {{ getSizeLabel(m.info.size)
                  }}
                </span>
              </div>
              <!-- 第四行：操作按钮 -->
              <div class="card-actions">
                <button
                  class="btn-explore"
                  @click.stop="onExplore(m)"
                  :disabled="!isModelAvailable(m)"
                >立即体验</button>
              </div>
            </div>
          </div>
        </div>
        <div class="pagination">
          <el-pagination
            background
            layout="sizes, prev, pager, next, jumper"
            :page-sizes="[12]"
            :page-size="pageSize"
            :total="totalItems"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          ></el-pagination>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.model-square {
  box-sizing: border-box;
  padding: 16px 28px 28px;
  /* background-color: rgb(245, 245, 245); */
  width: 100%;
  /*  height: 100%;*/
  /* min-height: 100vh; */
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  gap: 16px;
  overflow: hidden;
  min-height: 100%;
}

.pageTitle {
  flex: 0;
  color: #191919;
  font-size: 16px;
  font-weight: bold;
  font-family: "鸿蒙黑体", sans-serif;
}

.news {
  flex: 0 0 1;
  height: 80px;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 16px;
}

.model-news,
.model-selection {
  height: 100%;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  overflow: hidden;
  border-radius: 16px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  padding: 16px;
  cursor: pointer;
}

.model-news {
  flex: 3;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  justify-content: center;
  /* padding: 0; */
}

.model-news .title {
  margin: 0;
  font-size: 16px;
  font-weight: bold;
  color: black;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.model-news .desc {
  font-size: 14px;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 4px;
  max-width: 100%;
}

.model-news .desc > p {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  color: grey;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-news .desc > img {
  min-width: 0;
  flex: 0 0 1;
  height: 20px;
  width: auto;
}

.model-selection {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  justify-content: center;
}

.model-selection .title {
  margin: 0;
  font-size: 16px;
  font-weight: bold;
  color: rgb(0, 103, 209);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.model-selection .desc {
  display: block;
  margin: 0;
  font-size: 14px;
  color: grey;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.ms-header {
  flex: 0 0 1;
  /* min-height: 57px; */
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-radius: 6px;
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-bottom: 1px solid #eee;
  transition: 0.3s ease-in-out;
}

.ms-btns {
  border-radius: 4px;
  overflow: hidden;
}

.ms-btns button:not(:last-child) {
  flex: 1 1 0;
  min-height: 0;
  border: none;
  outline: none;
  background-color: rgb(242, 242, 242);
  color: rgb(51, 51, 51);
  font-size: 14px;
  padding: 8px 16px;
  transition: 0.3s ease-in-out;
  line-height: 1;
}

.ms-btns button.active {
  background-color: rgb(0, 103, 209);
  color: white;
}

.ms-search {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ms-search input {
  margin-right: 16px;
  height: 30px;
  width: 280px;
  border-radius: 4px;
  border: 1px solid rgb(201, 201, 201);
  padding: 0 8px;
  font-size: 12px;
}

.register-btn {
  background-color: rgb(0, 103, 209);
  color: white;
  height: 30px;
  width: 120px;
  border: none;
  outline: none;
  border-radius: 4px;
}

.register-btn:hover {
  background-color: rgb(0, 90, 178);
}

.register-btn:active {
  background-color: rgb(0, 80, 160);
}

.ms-search input:focus {
  border-color: rgb(0, 103, 209);
  outline: 1px solid rgb(0, 103, 209);
}

.ms-content {
  display: flex;
  flex: 1;
  flex-direction: row;
  gap: 16px;
}

.ms-filters {
  width: 250px;
  padding: 20px;
  border-right: 1px solid #f0f0f0;
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  gap: 24px;
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.filter-group h4 {
  margin: 0;
  display: flex;
  flex-direction: row;
  gap: 8px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}

/* 隐藏原生 input */
.filter-radio {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
  pointer-events: none;
}

.filter-item {
  width: 48%;
  margin-bottom: 10px;
}

.tag-group .filter-item:nth-child(2n-1) {
  margin-right: 4%;
}

/* 默认状态下的 label */
.filter-label {
  background-color: #e7ebfe;
  color: #265ab7;
  border: 1px solid transparent;
  border-radius: 6px;
  width: 100%;
  font-size: 14px;
  -webkit-appearance: none;
  border-left-color: transparent;
  border-radius: 0;
  box-sizing: border-box;
  cursor: pointer;
  display: inline-block;
  line-height: 1;
  margin: 0;
  outline: none;
  padding: 8px 15px;
  position: relative;
  text-align: center;
  -webkit-user-select: none;
  -moz-user-select: none;
  user-select: none;
  vertical-align: middle;
  white-space: nowrap;
  box-shadow: none !important;
  border-radius: 6px;
  transition: 0.3s;
}

/* hover 效果 */
.filter-label:hover {
  background-color: rgb(224, 235, 250);
}

/* 禁用状态 */
.filter-radio[disabled] + .filter-label {
  opacity: 0.5;
  cursor: not-allowed;
  background-color: #efefef;
}

.filter-radio[disabled] + .filter-label:hover {
  background-color: #efefef;
}

/* 选中高亮 */
.filter-radio:checked + .filter-label {
  background-color: rgb(89, 144, 253);
  /* 可按需调整 */
  color: rgb(255, 255, 255);
}

/* —— grid 布局 —— */
.ms-list {
  flex: 1;
  overflow: auto;
}

.list-grid {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(375px, 1fr));
  gap: 1rem;
}

.empty-tip {
  color: #666;
  padding: 20px;
  text-align: center;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

/* —— 卡片基础 —— */
.model-card-base {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  padding: 16px;
  padding-bottom: 0;
  border: 2px solid #ddd;
  border-radius: 8px;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
  animation: fade-in 0.3s ease-in-out;
}

.model-card {
  background-color: #fff;
}

.model-card:hover {
  border-color: #0590f3;
  border-width: 2px;
}

.model-card-disable {
  background-color: #f4f4f5;
}

/* 第一行：图标 + 名称 */
.card-header {
  display: flex;
  align-items: center;
}

.model-name {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  padding-right: 16px;
}

.card-header:hover .model-name {
  color: #3d93e4;
  transition: color 0.15s ease-in-out;
}

.model-icon-base {
  width: 25px;
  height: 25px;
  margin-right: 12px;
  border-radius: 8px;
}

.model-icon-disable {
  filter: grayscale(100%);
  -webkit-filter: grayscale(100%);
  -moz-filter: grayscale(100%);
  -ms-filter: grayscale(100%);
  -o-filter: grayscale(100%);
}

.model-name-base {
  font-size: 16px;
  font-weight: 600;
}

.model-name {
  color: #191919;
}

.model-name-disable {
  color: #999999;
}

.button-container {
  /* position: absolute;  */
  margin-left: auto;
  margin-right: 10px;
  display: flex;
  top: 10px;
  right: 10px;
}

.editClass {
  margin-left: 10px;
}

/* 第二行：描述 */
.card-desc {
  font-size: 12px;
  color: rgb(119, 119, 119);
  line-height: 1.4;
  height: calc(12px * 1.4 * 2);
  flex-shrink: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  /* 指定最多显示几行 */
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 第三行：标签，超出隐藏 */
.card-tags {
  display: flex;
  flex-wrap: nowrap;
  overflow: hidden;
  margin-top: auto;
}

.tag {
  flex: 0 0 auto;
  margin-right: 6px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 14px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.type-tag {
  background-color: rgb(231, 235, 254);
  color: rgb(31, 85, 180);
}

.info-tag {
  background-color: rgb(230, 240, 250);
  color: rgb(113, 135, 245);
}

.size-tag {
  background-color: rgb(244, 242, 253);
  color: rgb(145, 133, 240);
}

.type-tag-disable {
  background-color: #e0e0e0;
  color: #999999;
}

.info-tag-disable {
  background-color: #e0e0e0;
  color: #999999;
}

.size-tag-disable {
  background-color: #e0e0e0;
  color: #999999;
}

/* 第四行：按钮 */
.card-actions {
  margin-top: 5px;
  margin-bottom: 5px;
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.card-actions button {
  border: none;
  background-color: white;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-explore {
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  padding: 5px 10px;
  color: #0067d1;
}

.btn-explore:hover {
  color: #0067d1;
  background-color: #0067d10c;
}

.btn-explore[disabled] {
  cursor: not-allowed;
  color: #9a9a9a !important;
  background-color: #f3f3f300 !important;
}

.overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

/* 对话框 */
.dialog {
  background-color: #fff;
  min-width: 600px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
}

/* 对话框头部 */
.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.dialog-title {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #bababa;
  transition: color 0.2s ease-in-out;
}

.close-btn:hover {
  color: black;
}

/* 对话框内容 */
.dialog-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  flex-wrap: nowrap;
  justify-content: flex-start;
  max-height: 600px;
  overflow: auto;
}

.dialog-body img {
  width: auto;
  height: 400px;
  object-fit: cover;
  border-radius: 4px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
}

.closebtn {
  border-color: #d9d9d9;
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.02);
  font-size: 16px;
  line-height: 1.5;
  height: 30px;
  margin-left: 20px;
  padding: 7px 15px;
  border-radius: 8px;
}

.action-cell {
  display: flex;
  align-items: center;
  /* 垂直居中 */
  gap: 8px;
}

.oneModel {
  padding: 16px 32px;
  border-radius: 8px;
  background: #ffffffcc;
  margin: 10px 0;
}

.blueCircle {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  background-color: #1890ff;
  margin-right: 5px;
  border-radius: 50%;
}

.bulletin-title {
  display: flex;
  align-items: center;
}

.bulletin-text {
  padding: 5px 5px 5px 12px;
  font-size: 13px;
  color: #4c596b;
}
</style>