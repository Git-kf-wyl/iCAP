<template>
  <div class="onlineContainer">
    <el-container class="createContainer">
      <div class="insideContainer">
        <el-container class="radio-row">
          <div class="onlineTitleContainer" v-if="is_run">
            <span style="padding: 0 5px"></span>
            <img src="/images/return.png" class="returnicon" @click="goBack" />
            <span style="padding: 0 20px;"></span>
            <span style="font-size:18px;font-weight:600;">任务详情</span>
          </div>
          <el-radio-group
            v-model="assessmentType"
            class="screeningButtonGroup"
            @change="handleRadioChange"
          >
            <el-radio-button
              v-for="option in filteredOptions"
              :key="option.value"
              :label="option.label"
              :value="option.label"
              class="radioButton"
            >{{ option.label }}</el-radio-button>
          </el-radio-group>
        </el-container>

        <div class="stepContainer">
          <div class="steps">
            <el-steps direction="vertical" :active="currentStepIndex" finish-status="success">
              <el-step v-for="(step, index) in steps" :key="index" @click="changeStep(index)">
                <template #title>
                  <span>{{ step.title }}</span>
                  <div class="step-description">
                    <p class="desc-text">{{ step.description || "" }}</p>
                  </div>
                </template>
              </el-step>
            </el-steps>
          </div>

          <div class="description-zone">
            <div v-for="(step, index) in steps" :key="index" class="description-card" ref="cards">
              <div class="json-display">
                <template v-if="index === 0">
                  <div class="json-display" style="display: block; width: 100%">
                    <div
                      v-for="(value, key) in step.formData"
                      :key="key"
                      class="json-container"
                      style="margin-top: 10px; width: 100%"
                    >
                      <div v-if="value !== ''">
                        <span class="circle"></span>
                        <span class="key-value">{{ value }}</span>
                      </div>
                    </div>
                  </div>
                </template>
                <template v-else-if="index === 1">
                  <div
                    v-for="(item, idx) in Object.values(
                      step.formData.datasets
                    ).flat()"
                    :key="idx"
                    class="json-container"
                  >
                    <span class="circle" v-if="item !== ''"></span>
                    <span>{{ item }}</span>
                  </div>
                </template>
                <template v-else-if="index === 3" v-for="(value, key) in step.formData" :key="key">
                  <span v-for="(item2, idx) in value" :key="idx" class="json-container">
                    <span class="circle"></span>
                    <span>{{ (item2 as { 'dataset_name': string }).dataset_name }}:</span>
                    <strong style="margin-left: 5px">
                      {{ (item2.progress * 100).toFixed(0) + "%" }}
                    </strong>
                    <span class="dots" v-if="item2.progress !== 1">{{ dots }}</span>
                  </span>
                </template>
                <template
                  v-else-if="index === 4"
                  v-for="(value, key) in step.formData"
                  :key="value"
                >
                  <span v-for="(item2, idx) in value" :key="idx" class="json-container">
                    <span class="circle"></span>
                    <span>{{ (item2 as { 'dataset_name': string }).dataset_name }}:</span>
                    <strong style="margin-left: 5px">
                      {{ (item2.score * rate(item2.dataset_name)).toFixed(1) }}
                    </strong>
                  </span>
                </template>
                <template v-else>
                  <div v-for="(value, key) in step.formData" :key="key" class="json-container">
                    <span class="circle"></span>
                    {{ key }}: {{ value }}
                  </div>
                </template>
              </div>
            </div>
          </div>

          <div class="content-zone">
            <div class="left-divider"></div>
            <div class="content-wrapper">
              <div class="content">
                <component :is="currentStepComponent" v-model="steps[currentStepIndex].formData" />
                <el-button
                  type="primary"
                  class="startButton margin_top_20"
                  @click="changeStep(currentStepIndex + 1)"
                  v-if="(currentStepIndex === 0 || currentStepIndex === 1) && !is_run"
                >下一步</el-button>
                <el-button
                  type="primary"
                  @click="startEvaluation"
                  v-if="currentStepIndex === 2 && !is_run"
                >开始测评</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
import { useRoute, useRouter } from "vue-router";
import {
  computed,
  ref,
  reactive,
  provide,
  onMounted,
  onUnmounted,
  watch,
  nextTick,
} from "vue";
import modelSelect from "./onlineAssessmentForms/modelSelectForm.vue";
import dataSetSelect from "./onlineAssessmentForms/dataSetSelectForm.vue";
import evaluationStart from "./onlineAssessmentForms/startEvaluationForm.vue";
import evaluationProgress from "./onlineAssessmentForms/evaluationProgress.vue";
import evaluationResult from "./onlineAssessmentForms/evaluationResult.vue";

import { ElMessage, ElLoading } from "element-plus";
import {
  startRun,
  startRun2,
  startRun3,
  startRunMul,
  getProgress,
  startRunAisfRelease,
  startMCPAtlas
} from "@/api/runService.js";
import { useDatasetStore } from "@/stores/datasetStore";
import { get_datasets } from "@/api/dataSetApi";
import { useTaskStore } from "@/stores/taskStore";
import { useStore } from "vuex";
import { getErrorMessage } from "@/utils/errorHandler";

const dots = ref("");
const taskStore = useTaskStore();
const route = useRoute();
const router = useRouter();
const store = useStore();

const username = ref("");
const assessmentType = ref("通用评估(Ruler1)");
const datasetStore = useDatasetStore();

const options = ref([
  { value: 0, label: "通用评估(Ruler1)" },
  { value: 1, label: "领域评估(Ruler2)" },
  // { value: 2, label: "AISF发布评估" },
  // { value: 3, label: "AISF开发评估" },
  // { value: 4, label: "同声传译评估" },
]);

const rate = (name: string) => {
  if (name === "service_emotion" || name === "service_style") {
    return 20;
  }
  return 100;
};

const filteredOptions = computed(() => {
  if (is_run.value) {
    return options.value.filter(
      (option) => option.label === assessmentType.value
    );
  }
  return options.value;
});

const goBack = () => {
  router.back();
};

const currentStepIndex = ref(0);
const is_run = ref(false);
let interval1: any;
let interval2: any;
let interval3: any;
let intervalDot: any;

// ============================================================
// 模型白名单 — 从 textConversation.vue 同步
// ============================================================
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
  "gemini-3-pro-preview(外网api,请注意信息安全)",
  "gemini-3-pro-preview-thinking(外网api,请注意信息安全)",
  "DeepSeek-V3.2(chat模型,外网api,请注意信息安全)",
  "DeepSeek-V3.2(reasoner模型,外网api,请注意信息安全)",
  "GLM-5(外网api,请注意信息安全)",
  'Qwen2.5-Omni-7B',
  'Qwen3.6-27B',
  'Qwen3.6-35B-A3B',
];

const imageModelWhiteName = [
  "Qwen3.5-27B",
  "Qwen3.5-122B-A10B",
  "Qwen3-VL-32B-Instruct",
  "Qwen3-Omni-30B-A3B-Instruct",
  "Qwen2.5-Omni-7B",
  'Qwen3.6-27B',
  'Qwen3.6-35B-A3B',
];

// ============================================================
// 测试集分类 — 哪些测试集属于大语言 / 多模态
// ============================================================
const llmDatasets = ref([
  "aime26",
  "bfcl_v3",
  "gpqa",
  "ifeval",
  "live_code_bench",
  "mmlu_redux",
]);

const multipleDatasets = ref([
  "MMMU",
  "MMStar"
]);

const isRuler2Datasets = ref([
  // "om_alarm_diag",
  // "om_mml_generate",
  // "LLM最小集",
]);

const isRuler2MultipleDatasets = ref([
  "aisf_vla",
  "视觉感知",
  "儿童伴读",
]);

const isAISFReleased = ref([
  'aisf_clarify_32b',
  'aisf_functioncall_32b',
  'aisf_intentcategory_32b',
  'aisf_perceptionplan_32b',
  'aisf_memory_forever_32b',
  'aisf_box_param_extract_32b',
]);

const notLlmDevDatasets = ref(['aisf_vla_dev', 'simultaneous_interpretation']);

const defaultDevDatasets = ref(["aisf_vla_dev"]);
const defaultInterpre = ref(["simultaneous_interpretation"]);

// ============================================================
// 判断模型模态能力
// ============================================================
function isLLMModel(modelId: string): boolean {
  return modelWhiteName.includes(modelId);
}

function isMultiModalModel(modelId: string): boolean {
  return imageModelWhiteName.includes(modelId);
}

onMounted(async () => {
  username.value = localStorage.getItem("username");
  if (is_run.value) {
    intervalDot = setInterval(() => {
      if (dots.value.length < 5) {
        dots.value += ".";
      } else {
        dots.value = "";
      }
    }, 500);
  }
  if (route.query.task_id) {
    const config = taskStore.getTaskById(route.query.task_id)[0];
    is_run.value = true;
    if (config.ID !== "" && config.status === "running") {
      get_progress(config.ID);
      intervalDot = setInterval(() => {
        if (dots.value.length < 5) {
          dots.value += ".";
        } else {
          dots.value = "";
        }
      }, 500);
      interval2 = setInterval(() => {
        get_progress(config.ID);
      }, 5000);
    } else if (config.status === "failed") {
      console.error("此任务执行失败: ", config.error);
    }
    assessmentType.value = config.assessmentType;
    steps[0].formData.model_id = config.taskConfig.model_id;
    Object.assign(steps[1].formData, config.taskConfig);
    steps[2].formData.name = config.taskConfig.name;
    steps[2].formData.limit = config.taskConfig.limit;
    steps[2].formData.stream = config.taskConfig.stream;
    steps[2].formData.temperature = config.taskConfig.temperature;
    steps[2].formData.eval_batch_size = config.taskConfig.eval_batch_size;
    if (assessmentType.value === "AISF开发评估") {
      steps[2].formData.system_prompt = config.taskConfig.system_prompt;
    }
    steps[3].formData = config.result;
    steps[4].formData = config.result;
    currentStepIndex.value = 3;
  } else {
    steps[1].formData.datasets = [...llmDatasets.value];
    await get_datasets("1").then((res) => {
      datasetStore.setDatasets("ruler1", res.data);
    });
  }
});

onUnmounted(() => {
  clearInterval(interval1);
  clearInterval(interval2);
  clearInterval(interval3);
  clearInterval(intervalDot);
  interval1 = null;
  interval2 = null;
  interval3 = null;
  intervalDot = null;
});

const config = ref({
  eval_type: "service",
  request_retry: false,
  retry_content_none: false,
  judge_worker_num: 1,
  assessmentType: assessmentType,
});

// 步骤列表
const steps = reactive([
  {
    index: 0,
    title: "步骤一",
    description: "模型选择",
    info: "",
    component: modelSelect,
    formData: reactive({
      model_id: "",
    }),
  },
  {
    index: 1,
    title: "步骤二",
    description: "测试集选择",
    info: "",
    component: dataSetSelect,
    formData: reactive({
      datasets: [],
      dataset_args: {},
    }),
  },
  {
    index: 2,
    title: "步骤三",
    description: "测评启动",
    info: "",
    component: evaluationStart,
    formData: reactive({
      name: "",
      limit: 0,
      stream: false,
      temperature: 0,
      eval_batch_size: 1,
    }),
  },
  {
    index: 3,
    title: "步骤四",
    description: "测评进行中",
    info: "",
    component: evaluationProgress,
    formData: reactive({}),
  },
  {
    index: 4,
    title: "步骤五",
    description: "测评结束",
    info: "",
    component: evaluationResult,
    formData: reactive({}),
  },
]);

const first_time = ref(0);
provide("m_formData", steps[0].formData);
provide("d_formData", steps[1].formData);
provide("is_run", is_run);
provide("assessmentType", assessmentType);
provide("first_time", first_time);
provide("evaluationType", "online");

const handleRadioChange = async (value: string) => {
  // 重置步骤三的额外字段
  if (value !== "同声传译评估") {
    steps[2].formData = {
      name: "",
      limit: 0,
      stream: false,
      temperature: 0,
      eval_batch_size: 1,
    };
  }

  if (value === "AISF开发评估") {
    (steps[2].formData as any).system_prompt = "";
    (steps[1].formData as any).datasets = [...defaultDevDatasets.value];
  } else if (value === "通用评估(Ruler1)") {
    delete (steps[2].formData as any).system_prompt;
    // 根据所选模型过滤可用测试集
    const modelId = (steps[0].formData as any).model_id;
    (steps[1].formData as any).datasets = getAvailableDatasetsForModel(modelId, "通用评估(Ruler1)");
  } else if (value === "领域评估(Ruler2)") {
    delete (steps[2].formData as any).system_prompt;
    if (JSON.stringify(datasetStore.getDatasets("ruler2")) !== "{}") {
      (steps[1].formData as any).datasets = Object.keys(
        datasetStore.getDatasets("ruler2")
      );
    } else {
      await get_datasets("2").then((res) => {
        datasetStore.setDatasets("ruler2", res.data);
      });
      (steps[1].formData as any).datasets = Object.keys(
        datasetStore.getDatasets("ruler2")
      );
    }
    // 领域评估只保留领域测试集
    (steps[1].formData as any).datasets = (
      steps[1].formData as any
    ).datasets.filter((item: string) => isRuler2Datasets.value.includes(item));
  } else if (value === "AISF发布评估") {
    delete (steps[2].formData as any).system_prompt;
    if (JSON.stringify(datasetStore.getDatasets("ruler2")) !== "{}") {
      (steps[1].formData as any).datasets = Object.keys(
        datasetStore.getDatasets("ruler2")
      );
    } else {
      await get_datasets("2").then((res) => {
        datasetStore.setDatasets("ruler2", res.data);
      });
    }
    (steps[1].formData as any).datasets = (
      steps[1].formData as any
    ).datasets.filter((item: string) => isAISFReleased.value.includes(item));
  } else if (value === "同声传译评估") {
    store.dispatch("interpretation/updateDirectoryA", "");
    store.dispatch("interpretation/updateDirectoryB", "");
    store.dispatch("interpretation/updateDirectoryC", []);
    store.dispatch("interpretation/updateDirectoryD", []);
    await router.push("/modelEvaluation/multipleEvaluation/interpretation");
    return;
  }

  first_time.value = 0;
  currentStepIndex.value = 0;
};

/** 根据选中的模型和评估类型，返回该模型支持的测试集列表 */
function getAvailableDatasetsForModel(modelId: string, evalType: string): string[] {
  const isLLM = isLLMModel(modelId);
  const isMulti = isMultiModalModel(modelId);

  if (evalType === "通用评估(Ruler1)") {
    const available: string[] = [];
    if (isLLM) available.push(...llmDatasets.value);
    if (isMulti) available.push(...multipleDatasets.value);
    // 去重
    return [...new Set(available)];
  }
  return [];
}

const currentStepComponent = computed(() => {
  return steps[currentStepIndex.value].component;
});

function changeStep(index: number) {
  if (index === currentStepIndex.value) return;

  if (
    (steps[0].formData as any).model_id === "" &&
    currentStepIndex.value === 0
  ) {
    ElMessage({ type: "error", message: "请先填写步骤一中的模型选择" });
    return;
  }
  if (
    JSON.stringify((steps[1].formData as any).datasets) === "[]" &&
    currentStepIndex.value === 1
  ) {
    ElMessage({ type: "error", message: "请先填写步骤二中的测试集选择" });
    return;
  }
  if ((index === 3 || index === 4) && !is_run.value) {
    ElMessage({ type: "error", message: "请先开始评估才能查看进度" });
    return;
  }
  first_time.value += 1;
  currentStepIndex.value = index;

  if (is_run.value) {
    first_time.value = 10;
  }
}

const get_progress = (task_id: string) => {
  getProgress(task_id).then((res) => {
    steps[3].formData = res.data.result;
    steps[4].formData = res.data.result;
    return res.data.status;
  });
};

const cards = ref([]);
const zoneHeight = ref(0);
const calculateTotalHeight = () => {
  let totalHeight = 0;
  cards.value.forEach((card: any) => {
    totalHeight += card.offsetHeight;
  });
  zoneHeight.value = totalHeight;
};

onMounted(() => {
  nextTick(() => {
    calculateTotalHeight();
  });
});

watch(steps, () => {
  nextTick(() => {
    calculateTotalHeight();
  });
});

watch(
  () => (steps[0].formData as any).model_id,
  (newModelId) => {
    first_time.value = 0;
    // 当模型改变时，自动更新可用的测试集列表
    if (assessmentType.value === "通用评估(Ruler1)" && newModelId) {
      (steps[1].formData as any).datasets = getAvailableDatasetsForModel(
        newModelId,
        assessmentType.value
      );
    }
  }
);

// 同步任务到 localStorage（复用 onlineAssessment.vue 的任务列表机制）
function syncTaskToLocalStorage(taskRecord: any) {
  try {
    const key = `evalTaskList_${username.value}`;
    const raw = localStorage.getItem(key);
    const list = raw ? JSON.parse(raw) : [];
    // 避免重复
    const exists = list.some((t: any) => t.ID === taskRecord.ID);
    if (!exists) {
      list.push(taskRecord);
      localStorage.setItem(key, JSON.stringify(list));
    }
  } catch (e) {
    console.warn("同步任务到本地存储失败", e);
  }
}

/** 将选择的测试集按模态拆分为 LLM 和多模态两组 */
function splitDatasetsByModality(selectedDatasets: string[]): {
  llmDatasets: string[];
  multiDatasets: string[];
} {
  const llm: string[] = [];
  const multi: string[] = [];
  for (const ds of selectedDatasets) {
    if (llmDatasets.value.includes(ds)) {
      llm.push(ds);
    }
    if (multipleDatasets.value.includes(ds)) {
      multi.push(ds);
    }
  }
  return { llmDatasets: llm, multiDatasets: multi };
}

/** 从 combinedFormData 中提取改写业务参数，合并到 generate_config 中 */
function extractRewriteParams(data: any): any {
  const rewriteKeys = [
    "enable_fewshot",
    "enable_fixed_fewshot",
    "fewshot_retrieval_mode",
    "fewshot_example_field",
    "fewshot_top_k",
    "fewshot_score_threshold",
    "max_fewshot_examples",
    "max_context_turns",
  ];
  const result: any = {};
  for (const key of rewriteKeys) {
    if (key in data) {
      result[key] = data[key];
      delete data[key];
    }
  }
  return result;
}

/** 根据数据集类型选择调用哪个接口 */
function callEvalApi(
  datasets: string[],
  combinedFormData: any,
  evalType: "llm" | "multi"
): Promise<any> {
  const rewriteParams = extractRewriteParams(combinedFormData);
  if (Object.keys(rewriteParams).length > 0) {
    combinedFormData.generate_config = {
      ...(combinedFormData.generate_config || {}),
      ...rewriteParams,
    };
  }
  const payload = {
    ...combinedFormData,
    ...config.value,
    username: username.value,
    evaluationType: evalType,
    datasets,
    dataset_args: Array.isArray(combinedFormData.dataset_args)
      ? combinedFormData.dataset_args.filter(
          (arg: any) => arg?.dataset_name && datasets.includes(arg.dataset_name)
        )
      : [],
  };

  if (assessmentType.value === "通用评估(Ruler1)") {
    if (payload.datasets[0] === 'mcp_atlas'){
      return startMCPAtlas(payload);
    }
    return evalType === "llm" ? startRun(payload) : startRunMul(payload);
  }
  if (assessmentType.value === "领域评估(Ruler2)") {
    return startRun2(payload);
  }
  if (assessmentType.value === "AISF发布评估") {
    return startRunAisfRelease(payload);
  }
  return startRun3(payload);
}

const startEvaluation = () => {
  const combinedFormData = steps
    .filter((fil) => fil.index < 3)
    .reduce((acc, step) => ({ ...acc, ...step.formData }), {});

  if (combinedFormData.name === "") {
    ElMessage({ type: "error", message: "请输入任务名称" });
    return;
  }

  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });

  combinedFormData.assessmentType = assessmentType.value;

  // ---- 同声传译评估 ----
  if (assessmentType.value === "同声传译评估") {
    // 保持原有逻辑 — 跳转到 interpretation 页面处理
    ElMessage({ type: "warning", message: "同声传译评估请通过对应入口进入" });
    loading.close();
    return;
  }

  // ---- 拆分测试集 ----
  const selectedDatasets: string[] = combinedFormData.datasets || [];
  const { llmDatasets: llmDS, multiDatasets: multiDS } =
    splitDatasetsByModality(selectedDatasets);

  const apiCalls: Promise<any>[] = [];
  const callInfos: { evalType: "llm" | "multi"; datasets: string[] }[] = [];

  if (llmDS.length > 0) {
    callInfos.push({ evalType: "llm", datasets: llmDS });
    apiCalls.push(
      callEvalApi(llmDS, combinedFormData, "llm")
    );
  }
  if (multiDS.length > 0) {
    callInfos.push({ evalType: "multi", datasets: multiDS });
    apiCalls.push(
      callEvalApi(multiDS, combinedFormData, "multi")
    );
  }

  // 如果没有任何匹配的测试集，使用原始全部数据集走默认接口
  if (apiCalls.length === 0) {
    callInfos.push({ evalType: "llm", datasets: selectedDatasets });
    apiCalls.push(
      callEvalApi(selectedDatasets, combinedFormData, "llm")
    );
  }

  // ---- 并发发起调用 ----
  Promise.allSettled(
    apiCalls.map((call, idx) =>
      call.then((response) => ({
        response,
        info: callInfos[idx],
      }))
    )
  )
    .then((results) => {
      let hasSuccess = false;
      let hasError = false;

      for (const result of results) {
        if (result.status === "fulfilled") {
          hasSuccess = true;
          const { response, info } = result.value;

          // 为这个调用单独创建一条任务记录同步到 localStorage
          if (response.data && response.data.task_id) {
            const taskRecord = {
              ID: response.data.task_id,
              name: combinedFormData.name + (apiCalls.length > 1 ? ` (${info.evalType === "llm" ? "大语言" : "多模态"})` : ""),
              model_id: combinedFormData.model_id,
              modelType: info.evalType === "llm" ? "大语言" : "多模态",
              datasets: info.datasets.join(", "),
              assessmentType: assessmentType.value,
              status: "running",
              taskConfig: { ...combinedFormData, datasets: info.datasets },
              result: {},
              createTime: new Date().toISOString(),
            };
            syncTaskToLocalStorage(taskRecord);
          }
        } else {
          hasError = true;
          console.error("测评调用失败:", result.reason);
        }
      }

      // 取第一个成功的调用的 task_id 用于轮询进度
      const firstFulfilled = results.find(
        (r) => r.status === "fulfilled"
      ) as PromiseFulfilledResult<any> | undefined;

      if (firstFulfilled) {
        const taskId = firstFulfilled.value.response.data.task_id;
        getProgress(taskId).then(
          (res: any) => {
            steps[3].formData = res.data.result;
            steps[4].formData = res.data.result;
            is_run.value = true;
            currentStepIndex.value = 3;
            if (res.data.status === "failed") {
              ElMessage({ type: "error", message: "运行失败：" + res.data.res });
            } else {
              ElMessage({ type: "success", message: "运行成功" });
            }
            loading.close();
          },
          (err: any) => {
            ElMessage({ type: "error", message: "运行失败：" + err });
            loading.close();
          }
        );
        interval3 = setInterval(() => {
          get_progress(taskId);
        }, 5000);
      }

      if (hasError && hasSuccess) {
        ElMessage({
          type: "warning",
          message: "部分测评任务启动成功，部分失败，请查看任务列表",
        });
      } else if (hasError) {
        ElMessage({ type: "error", message: "所有测评任务启动失败" });
        loading.close();
      }
    })
    .catch((error) => {
      ElMessage({ type: "error", message: "运行失败：" + error });
      loading.close();
    });
};
</script>

<style scoped>
.tabsContainer {
  margin-left: 10px;
}
.tabsContainer :deep(.el-tabs__item) {
  font-size: 16px;
}
.createContainer {
  background-color: #ffffff;
  padding: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  height: 95%;
  border-radius: 4px;
  margin-top: 10px;
  margin-right: 10px;
  max-width: 98%;
}
.onlineContainer {
  width: 100%;
  min-height: calc(100vh - 80px);
  max-height: 100%;
  display: flex;
  min-width: 100%;
  position: relative;
  flex-direction: column;
}
.onlineTitleContainer {
  display: flex;
  flex-wrap: wrap;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 36px;
  height: 40px;
  margin-right: 15px;
}
.screeningButtonGroup {
  height: 40px;
}
.screeningButtonGroup :deep(.el-radio-button__inner) {
  background-color: #f3f3f3;
  color: #333;
  border: none;
}
.screeningButtonGroup
  :deep(.el-radio-button.is-active .el-radio-button__inner) {
  background-color: #0067d1;
  color: #fff;
  border: none;
}
.stepContainer {
  margin-top: 10px;
  display: flex;
  height: 100%;
  width: 100%;
  flex-direction: row;
}
.steps {
  cursor: pointer;
  padding: 0 20px;
  box-sizing: border-box;
  flex-shrink: 0;
  width: 10%;
}
.step-header {
  display: flex;
  gap: 20px;
  flex-direction: row;
}
.step-card {
  width: 200px;
  height: 60px;
  background: #f0f0f0;
  border-radius: 4px;
  padding: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}
.step-description {
  margin-top: 8px;
  font-size: 12px;
  color: #777777;
}
.desc-text {
  margin: 0 0 8px 0;
  color: #999;
}
.description-zone {
  width: 40%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  gap: 10px;
  padding: 0 16px;
  box-sizing: border-box;
  background-color: transparent;
  top: 20px;
  overflow: auto;
}
.description-zone > .description-card {
  flex: 0 0 auto;
}
.description-card {
  background-color: #f4f3f9;
  border-radius: 6px;
  min-height: 150px;
  padding: 10px;
  transition: background-color 0.3s;
}
.content-zone {
  flex: 1;
  display: flex;
  position: relative;
  width: 40%;
}
.left-divider {
  width: 2px;
  background-color: #d7d7d7;
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
}
.content-wrapper {
  flex: 1;
  margin-left: 18px;
  display: flex;
  justify-content: center;
  max-width: 100%;
}
.content {
  width: 100%;
  max-width: 900px;
}
.json-display {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.json-container {
  display: flex;
  align-items: center;
  margin-right: 10px;
  width: calc(50% - 15px);
  box-sizing: border-box;
}
.json-container:last-child {
  margin-right: 0;
}
.circle {
  display: inline-block;
  min-width: 10px;
  height: 10px;
  background-color: rgb(132, 132, 224);
  border-radius: 50%;
  margin-right: 5px;
}
.key-value {
  display: inline-block;
}
.radioDisabled :deep(.el-radio-button__inner) {
  color: #a8abb2 !important;
}
.radio-row {
  max-height: 40px;
  align-items: center;
}
.insideContainer {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}
.returnicon {
  position: absolute;
  top: 5px;
  left: 10px;
}
.startButton {
  margin-left: 5%;
}
.margin_top_20 {
  margin-top: 20px;
}
</style>