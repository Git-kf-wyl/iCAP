<template>
  <div class="onlineContainer">
    <el-container class="createContainer">
      <div class="insideContainer">
        <el-container class="radio-row">
          <div class="onlineTitleContainer" v-if="is_run">
            <span style="padding: 0 5px"></span>
            <img src="/images/return.png" class="returnicon" @click="goBack" />
            <span style="padding: 0 20px;"></span>
            <!-- <span @click="goBack" style="color: #969696;cursor: pointer;">我的评测任务</span>
            <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>-->
            <span v-if="is_run" style="font-size:18px;font-weight:600;">任务详情</span>
            <span v-else style="font-size:18px;font-weight:600;">创建任务</span>
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
            >
              <!-- :disabled="option.value === 2"
              :class="option.value === 2 ? 'radioDisabled' : 'radioButton'"-->
              {{ option.label }}
            </el-radio-button>
            <!-- <el-radio-button label="领域评估(Ruler2)" disabled v-show="showOther===assessmentType||showOther===''">领域评估(Ruler2)</el-radio-button>
                  <el-radio-button label="定制评估" disabled v-show="showOther===assessmentType||showOther===''">定制评估</el-radio-button>
            <el-radio-button label="AISF开发评估" v-show="showOther===assessmentType||showOther===''">AISF开发评估</el-radio-button>-->
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
              <!-- <el-button type="primary" @click="startEvaluation"
              v-if="currentStepIndex === 2 && !is_run">开始测评</el-button>-->
              <!-- <el-button type="primary" @click="reStartEvaluation" v-if="currentStepIndex===4">重新测评</el-button> -->
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
                      {{
                      (item2.progress * 100).toFixed(0) + "%"
                      }}
                    </strong>
                    <span class="dots" v-if="item2.progress !== 1">{{ dots }}</span>
                  </span>
                  <!-- </div> -->
                </template>
                <template
                  v-else-if="index === 4"
                  v-for="(value, key) in step.formData"
                  :key="value"
                >
                  <!-- <div class="json-container" style="display: block"> -->
                  <span v-for="(item2, idx) in value" :key="idx" class="json-container">
                    <span class="circle"></span>
                    <span>{{ (item2 as { 'dataset_name': string }).dataset_name }}:</span>
                    <strong style="margin-left: 5px">
                      {{
                      (item2.score * rate(item2.dataset_name)).toFixed(1)
                      }}
                    </strong>
                  </span>
                  <!-- </div> -->
                  <!-- <div v-for="(value, key) in step.formData" :key="key" class="json-container">
                          <span v-for="(item, idx) in value" :key="idx" class="json-container">
                            <span class="circle"></span>
                            <span>{{ item.dataset_name }}: {{ (item.score * 100).toFixed(0) }}</span>
                          </span>
                  </div>-->
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
                <!-- <keep-alive> -->
                <component :is="currentStepComponent" v-model="steps[currentStepIndex].formData" />
                <!-- </keep-alive> -->
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
  getProgress,
  startRunAisfRelease
} from "@/api/runService.js";
import { useDatasetStore } from "@/stores/datasetStore";
import { get_datasets } from "@/api/dataSetApi";
import { useTaskStore } from "@/stores/taskStore";
const dots = ref("");
const taskStore = useTaskStore();
const route = useRoute();
const router = useRouter();

const activeTab = ref("nlp");
const assessmentType = ref("通用评估(Ruler1)");
const datasetStore = useDatasetStore();

const options = ref([
  { value: 0, label: "通用评估(Ruler1)" },
  { value: 1, label: "领域评估(Ruler2)" },
  // { value: 2, label: "定制评估" },
  { value: 2, label: "AISF发布评估" },
  { value: 3, label: "AISF开发评估" },
]);

const rate = (name) => {
  if (name === "service_emotion" || name === "service_style") {
    return 20;
  } else {
    return 100;
  }
};

const filteredOptions = computed(() => {
  if (is_run.value) {
    return options.value.filter(
      (option) => option.label === assessmentType.value
    );
  } else {
    return options.value;
  }
});

const goBack = () => {
  router.back();
};

// 当前步骤索引（从0开始）
const currentStepIndex = ref(0);
const is_run = ref(false);
const username = ref("");
let interval1;
let interval2;
let interval3;
let intervalDot;

const defaultDatasets = ref([
  "aime26",
  "bfcl_v3",
  "gpqa",
  "ifeval",
  "live_code_bench",
  "mmlu_redux",
]);

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
    // (steps[0].formData as { eval_type: string }).eval_type = config.taskConfig.eval_type;
    Object.assign(steps[1].formData, config.taskConfig);
    steps[2].formData.name = config.taskConfig.name;
    steps[2].formData.limit = config.taskConfig.limit;
    steps[2].formData.stream = config.taskConfig.stream;
    if (assessmentType.value === "AISF开发评估") {
      steps[2].formData.system_prompt = config.taskConfig.system_prompt;
    }
    steps[3].formData = config.result;
    steps[4].formData = config.result;
    currentStepIndex.value = 3;
  } else {
    (steps[1].formData as { datasets: string[] }).datasets =
      defaultDatasets.value;
    await get_datasets("1").then((res) => {
      datasetStore.setDatasets("ruler1", res.data);
    });
  }
});

onUnmounted(() => {
  // 清除间隔
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
provide("evaluationType", 'llm');
provide("first_time", first_time);

const isRuler2Datasets = ref([
  "om_alarm_diag",
  "om_mml_generate",
  "LLM最小集"
]);

const isAISFReleased = ref([
  'aisf_clarify_32b',
  'aisf_functioncall_32b',
  'aisf_intentcategory_32b',
  'aisf_perceptionplan_32b',
  'aisf_memory_forever_32b',
  'aisf_box_param_extract_32b',
])

const notLlmDevDatasets = ref(['aisf_vla_dev', 'simultaneous_interpretation'])

const handleRadioChange = async (value) => {
  if (value === "AISF开发评估") {
    // (steps[1].formData as { datasets: string[] }).datasets = ["AISF"];
    (steps[2].formData as { system_prompt: string }).system_prompt = "";
    if (JSON.stringify(datasetStore.getDatasets("ruler3")) !== "{}") {
      (steps[1].formData as { datasets: string[] }).datasets = Object.keys(
        datasetStore.getDatasets("ruler3")
      );
    } else {
      await get_datasets("3").then((res) => {
        (steps[1].formData as { datasets: string[] }).datasets = Object.keys(
          res.data
        );
        datasetStore.setDatasets("ruler3", res.data);
      });
    }
    (steps[1].formData as { datasets: string[] }).datasets = (
        steps[1].formData as {
          datasets: string[];
        }
    ).datasets.filter(item => !notLlmDevDatasets.value.includes(item));
  } else if (value === "通用评估(Ruler1)") {
    delete (steps[2].formData as { system_prompt: string }).system_prompt;
    (steps[1].formData as { datasets: string[] }).datasets =
      defaultDatasets.value;
  } else if (value === "领域评估(Ruler2)") {
    delete (steps[2].formData as { system_prompt: string }).system_prompt;
    if (JSON.stringify(datasetStore.getDatasets("ruler2")) !== "{}") {
      (steps[1].formData as { datasets: string[] }).datasets = Object.keys(
        datasetStore.getDatasets("ruler2")
      );
    } else {
      await get_datasets("2").then((res) => {
        (steps[1].formData as { datasets: string[] }).datasets = Object.keys(
          res.data
        );
        datasetStore.setDatasets("ruler2", res.data);
      });
    }
    (steps[1].formData as { datasets: string[] }).datasets = (
      steps[1].formData as {
        datasets: string[];
      }
    ).datasets.filter((item) => isRuler2Datasets.value.includes(item));
  } else if (value === "AISF发布评估") {
    delete (steps[2].formData as { system_prompt: string }).system_prompt;
    if (JSON.stringify(datasetStore.getDatasets("ruler2")) !== "{}") {
      (steps[1].formData as { datasets: string[] }).datasets = Object.keys(
        datasetStore.getDatasets("ruler2")
      );
    } else {
      await get_datasets("2").then((res) => {
        (steps[1].formData as { datasets: string[] }).datasets = Object.keys(
          res.data
        );
        datasetStore.setDatasets("ruler2", res.data);
      });
    }
    (steps[1].formData as { datasets: string[] }).datasets = (
      steps[1].formData as {
        datasets: string[];
      }
    ).datasets.filter((item) => isAISFReleased.value.includes(item));
  }
  first_time.value = 0;
  currentStepIndex.value = 0;
};

// 动态获取当前组件
const currentStepComponent = computed(() => {
  return steps[currentStepIndex.value].component;
});

// 点击切换步骤
function changeStep(index) {
  if (index === currentStepIndex.value) {
    return;
  }
  if (
    (steps[0].formData as { model_id: string }).model_id === "" &&
    currentStepIndex.value === 0
  )
    ElMessage({
      type: "error",
      message: "请先填写步骤一中的模型选择",
    });
  else if (
    JSON.stringify((steps[1].formData as { datasets: [] }).datasets) === "[]" &&
    currentStepIndex.value === 1
  ) {
    ElMessage({
      type: "error",
      message: "请先填写步骤二中的测试集选择",
    });
  } else if ((index === 3 || index === 4) && !is_run.value) {
    ElMessage({
      type: "error",
      message: "请先开始评估才能查看进度",
    });
  } else {
    first_time.value += 1;
    currentStepIndex.value = index;
  }
  if (is_run.value) {
    first_time.value = 10;
  }
}

const get_progress = (task_id) => {
  getProgress(task_id).then((res) => {
    steps[3].formData = res.data.result;
    steps[4].formData = res.data.result;
    return res.data.status;
  });
};

// 用于存储description-zone的高度
const zoneHeight = ref(0);
// 用于获取所有description-card的DOM元素
const cards = ref([]);

// 计算所有description-card的高度总和
const calculateTotalHeight = () => {
  let totalHeight = 0;
  cards.value.forEach((card) => {
    totalHeight += card.offsetHeight;
  });
  zoneHeight.value = totalHeight;
};

// 当组件挂载时计算高度
onMounted(() => {
  nextTick(() => {
    calculateTotalHeight();
  });
});

// 监听steps的变化，当steps变化时重新计算高度
watch(steps, () => {
  nextTick(() => {
    calculateTotalHeight();
  });
});

watch(steps[0].formData, (newVal) => {
  first_time.value = 0;
});

const startEvaluation = () => {
  const combinedFormData = steps
    .filter((fil) => {
      if (fil.index < 3) return fil;
    })
    .reduce((acc, step) => {
      return { ...acc, ...step.formData };
    }, {});
  if (combinedFormData.name === "") {
    ElMessage({
      type: "error",
      message: "请输入任务名称",
    });
    return;
  }
  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });
  combinedFormData.evaluationType = "language";
  if (assessmentType.value === "通用评估(Ruler1)") {
    startRun({...combinedFormData, ...config.value, username: username.value})
      .then((response) => {
        getProgress(response.data.task_id).then(
          (res) => {
            steps[3].formData = res.data.result;
            steps[4].formData = res.data.result;
            is_run.value = true;
            currentStepIndex.value = 3;
            if (res.data.status === "failed") {
              ElMessage({
                type: "error",
                message: "运行失败：" + res.data.res,
              });
              loading.close();
              return;
            } else {
              ElMessage({
                type: "success",
                message: "运行成功",
              });
              loading.close();
            }
          },
          (err) => {
            ElMessage({
              type: "error",
              message: "运行失败：" + err,
            });
            loading.close();
            return;
          }
        );
        interval3 = setInterval(() => {
          get_progress(response.data.task_id);
        }, 5000);
      })
      .catch((error) => {
        ElMessage({
          type: "error",
          message: "运行失败：" + error,
        });
        loading.close();
      });
  } else if (assessmentType.value === "AISF开发评估") {
    startRun3({
      ...combinedFormData,
      ...config.value,
      username: username.value,
    })
      .then((response) => {
        getProgress(response.data.task_id).then(
          (res) => {
            steps[3].formData = res.data.result;
            steps[4].formData = res.data.result;
            is_run.value = true;
            currentStepIndex.value = 3;
            if (res.data.status === "failed") {
              ElMessage({
                type: "error",
                message: "运行失败：" + res.data.res,
              });
              loading.close();
              return;
            } else {
              ElMessage({
                type: "success",
                message: "运行成功",
              });
              loading.close();
            }
          },
          (err) => {
            ElMessage({
              type: "error",
              message: "运行失败：" + err.data.res,
            });
            loading.close();
            return;
          }
        );
        interval3 = setInterval(() => {
          get_progress(response.data.task_id);
        }, 5000);
      })
      .catch((error) => {
        ElMessage({
          type: "error",
          message: "运行失败：" + error,
        });
        loading.close();
      });
    loading.close();
  } else if (assessmentType.value === "领域评估(Ruler2)") {
    startRun2({...combinedFormData, ...config.value, username: username.value})
      .then((response) => {
        getProgress(response.data.task_id).then(
          (res) => {
            steps[3].formData = res.data.result;
            steps[4].formData = res.data.result;
            is_run.value = true;
            currentStepIndex.value = 3;
            if (res.data.status === "failed") {
              ElMessage({
                type: "error",
                message: "运行失败：" + res.data.res,
              });
              loading.close();
              return;
            } else {
              ElMessage({
                type: "success",
                message: "运行成功",
              });
              loading.close();
            }
          },
          (err) => {
            ElMessage({
              type: "error",
              message: "运行失败：" + err.data.res,
            });
            loading.close();
            return;
          }
        );
        interval3 = setInterval(() => {
          get_progress(response.data.task_id);
        }, 5000);
      })
      .catch((error) => {
        ElMessage({
          type: "error",
          message: "运行失败：" + error,
        });
        loading.close();
      });

    loading.close();
  } else if (assessmentType.value === "AISF发布评估") {
    startRunAisfRelease({...combinedFormData, ...config.value, username: username.value})
        .then((response) => {
          getProgress(response.data.task_id).then(
              (res) => {
                steps[3].formData = res.data.result;
                steps[4].formData = res.data.result;
                is_run.value = true;
                currentStepIndex.value = 3;
                if (res.data.status === "failed") {
                  ElMessage({
                    type: "error",
                    message: "运行失败：" + res.data.res,
                  });
                  loading.close();
                  return;
                } else {
                  ElMessage({
                    type: "success",
                    message: "运行成功",
                  });
                  loading.close();
                }
              },
              (err) => {
                ElMessage({
                  type: "error",
                  message: "运行失败：" + err.data.res,
                });
                loading.close();
                return;
              }
          );
          interval3 = setInterval(() => {
            get_progress(response.data.task_id);
          }, 5000);
        })
        .catch((error) => {
          ElMessage({
            type: "error",
            message: "运行失败：" + error,
          });
          loading.close();
        });
  }
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
  /* margin-left: 10px; */
  margin-right: 10px;
  max-width: 98%;
}

.onlineContainer {
  /* background-color: #f5f5f5; */
  width: 100%;
  min-height: calc(100vh - 60px);
  max-height: 100%;
  height: auto;
  display: flex;
  /* max-width: 95%; */
  min-width: 100%;
  /* gap: 12px; */
  position: relative;
  flex-direction: column;
  /* padding: 10px; */
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
  justify-content: space-between;
  /* 垂直均匀分布 */
  height: 100%;
  flex-direction: column;
  gap: 10px;
  padding: 0 16px;
  box-sizing: border-box;
  background-color: transparent;
  top: 20px;
  /* overflow: auto; */

  > .description-card {
    flex: 0 0 auto;
  }
}

.description-card {
  background-color: #f4f3f9;
  border-radius: 6px;
  min-height: 150px;
  padding: 10px;
  transition: background-color 0.3s;
  /* margin-bottom: 20px; */
}

.content-zone {
  flex: 1;
  display: flex;
  position: relative;
  width: 40%;
  /*height: 600px;*/
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
  gap: 10px;
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
  min-height: 100%;
}

.returnicon {
  position: absolute;
  top: 5px;
  left: 10px;
  /* bottom: 10px; */
}
</style>