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
              v-for="option in options"
              :key="option.value"
              :label="option.label"
              :value="option.label"
              :disabled="option.value === 2"
              :class="option.value === 2 ? 'radioDisabled' : 'radioButton'"
            >
              {{
              option.label }}
            </el-radio-button>
          </el-radio-group>

          <!-- <el-button style="position: absolute; left:calc(50% - 57.5px);width:115px" type=primary @click="toResult">总体评测结果</el-button> -->
          <el-button style="margin-left: 20px;" type="primary" @click="toResult" plain>总体评测结果</el-button>
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
              <div v-if="index === 0" class="step1DescBox">
                <div class="flex center gap10">
                  <div>选择场景</div>
                  <el-select
                    v-model="scene"
                    placeholder="请选择场景"
                    style="width: 240px"
                    @change="clearSelections"
                    :disabled="taskId !== ''||is_run"
                  >
                    <el-option
                      v-for="item in sceneOptions"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    />
                  </el-select>
                </div>
                <el-form
                  class="languageForm flex center gap10"
                  v-show="scene === 'MT' || scene === 'ASR+MT' || scene === 'ASR+MT+TTS'"
                  :model="languageData"
                  :rules="languageRules"
                >
                  <el-form-item label=" " prop="languageFrom" required style="margin: 0;">
                    <el-select
                      v-model="languageData.languageFrom"
                      placeholder="请选择源语言"
                      style="width: 240px"
                      :disabled="taskId !== '' || is_run"
                    >
                      <el-option
                        v-for="item in languageOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                  <!-- <img src="/images/exchange.svg" /> -->
                  <el-image style="width: 30px; height: 30px" src="/images/rightArrow.png" />
                  <el-form-item label=" " prop="languageTo" required style="margin: 0;">
                    <el-select
                      v-model="languageData.languageTo"
                      placeholder="请选择目标语言"
                      style="width: 240px"
                      :disabled="taskId !== ''||is_run"
                    >
                      <el-option
                        v-for="item in languageOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </el-form-item>
                </el-form>
              </div>
              <div
                v-if="index === 1"
                class="flex center step2DescBox"
              >Task name:{{ steps[1].formData.task_name }}</div>
              <div v-if="index === 2">
                <div v-for="(value, key) in steps[2].formData" :key="key">
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
                </div>
              </div>
              <div v-if="index === 3">
                <div v-for="(value, key) in steps[3].formData" :key="key">
                  <span v-for="(item2, idx) in value" :key="idx" class="json-container">
                    <span class="circle"></span>
                    <span>{{ (item2 as { 'dataset_name': string }).dataset_name }}:</span>
                    <strong style="margin-left: 5px">{{ (item2.score * 100).toFixed(2) }}</strong>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="content-zone">
            <div class="left-divider"></div>
            <el-scrollbar style="width: 100%;">
              <div class="content-wrapper">
                <div class="content">
                  <keep-alive>
                    <component
                      :is="currentStepComponent"
                      v-model="steps[currentStepIndex].formData"
                    />
                  </keep-alive>
                  <el-button
                    type="primary"
                    class="startButton margin_top_20"
                    @click="changeStep(currentStepIndex + 1)"
                    v-if="currentStepIndex === 0"
                  >下一步</el-button>
                  <el-button
                    type="primary"
                    class="startButton"
                    @click="startEvaluation"
                    v-if="currentStepIndex === 1 && !is_run && taskId === ''"
                  >开始测评</el-button>
                </div>
              </div>
            </el-scrollbar>
          </div>
        </div>
      </div>
    </el-container>
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, computed, provide, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import modelDatasetSelect from "./modelDatasetSelect.vue";
import evaluationStart from "./evaluationStart.vue";
import evaluationProgress from "./evaluationProgress.vue";
import evaluationResult from "../interpretationResult.vue";
import { ElMessage } from "element-plus";
import { useStore } from "vuex";
import { runInterpretation } from "@/api/dataSetApi";
import { useTaskStore } from "@/stores/taskStore";

const token = ref("");
const route = useRoute();
const router = useRouter();
const store = useStore();

const goBack = () => {
  router.back();
};

const taskId = ref("");
const assessmentType = ref("同声传译评估");

const options = computed(() => {
  if (taskId && taskId.value !== "") {
    return [{ value: 5, label: "同声传译评估" }];
  } else {
    return [
      { value: 0, label: "通用评估(Ruler1)" },
      { value: 1, label: "领域评估(Ruler2)" },
      // { value: 2, label: "定制评估" },
      { value: 3, label: "AISF开发评估" },
      { value: 5, label: "同声传译评估" },
    ];
  }
});

const handleRadioChange = (value) => {
  if (value !== "同声传译评估") {
    router.push({ name: "multipleEvaluation", query: { type: value } });
  }
};

const stepAFormData = reactive({
  model_id: "",
  directoryA: "",
  directoryB: "",
  directoryC: "",
  directoryD: "",
  MtDirectoryC: "",
  MtDirectoryD: [],
});

const is_run = ref(false);

const steps = reactive([
  {
    index: 0,
    title: "步骤一",
    description: "模型&测试集选择",
    info: "",
    component: modelDatasetSelect,
    formData: stepAFormData,
  },
  {
    index: 1,
    title: "步骤二",
    description: "测试启动",
    info: "",
    component: evaluationStart,
    formData: reactive({
      task_name: "",
    }),
  },
  {
    index: 2,
    title: "步骤三",
    description: "测评进行中",
    info: "",
    component: evaluationProgress,
    formData: reactive({}),
  },
  {
    index: 3,
    title: "步骤四",
    description: "测评结束",
    info: "",
    component: evaluationResult,
    formData: reactive({}),
  },
]);

const currentStepIndex = ref(0);
// 动态获取当前组件
const currentStepComponent = computed(() => {
  return steps[currentStepIndex.value].component;
});

const selectedDatasets = computed(
  () => store.getters["interpretation/getDataSets"]
);

// 点击切换步骤
function changeStep(index) {
  if (index === currentStepIndex.value) {
    return;
  }
  console.log(scene.value);
  console.log(steps[0].formData);
  if (scene.value) {
    if (
      scene.value.includes("ASR") &&
      (store.getters["interpretation/getDataSets"].length === 0 ||
        store.getters["interpretation/getLabel"] === "") &&
      index === 1
    ) {
      ElMessage({
        type: "error",
        message: "请先进行步骤一中的模型选择、语料选择与标注选择",
      });
    } else if (
      ((scene.value !== "ASR+MT" &&
        scene.value !== "ASR+MT+TTS" &&
        (steps[0].formData as { model_id: string }).model_id === "") ||
        (scene.value === "ASR+MT" &&
          ((steps[0].formData as { model_id_MT: string }).model_id_MT === "" ||
            (steps[0].formData as { model_id_ASR: string }).model_id_ASR ===
              "")) ||
        (scene.value === "ASR+MT+TTS" &&
          ((steps[0].formData as { model_id_MT: string }).model_id_MT === "" ||
            (steps[0].formData as { model_id_ASR: string }).model_id_ASR ===
              "" ||
            (steps[0].formData as { model_id_TTS: string }).model_id_TTS ===
              "")) ||
        (scene.value !== "MT" &&
          store.getters["interpretation/getDataSets"].length === 0) ||
        (scene.value === "MT" &&
          store.getters["interpretation/getMTDataset"] === "")) &&
      index === 1
    ) {
      ElMessage({
        type: "error",
        message: "请先进行步骤一中的模型选择与测试集选择",
      });
    } else if (
      (scene.value === "MT" || scene.value === "ASR+MT") &&
      (languageData.value.languageFrom === "" ||
        languageData.value.languageTo === "" ||
        languageData.value.languageFrom === languageData.value.languageTo) &&
      index === 1
    ) {
      ElMessage({
        type: "error",
        message: "请先进行语言选择",
      });
    } else if ((index === 2 || index === 3) && !is_run.value) {
      ElMessage({
        type: "error",
        message: "请先开始评估才能查看进度",
      });
    } else {
      console.log("steps[0].formData");
      console.log(steps[0].formData);
      currentStepIndex.value = index;
    }
  } else {
    ElMessage({
      type: "error",
      message: "请选择场景",
    });
  }
}

const scene = ref();
provide("scene", scene);

// watch(scene, () => {
//   languageData.value = {
//     languageFrom: "",
//     languageTo: "",
//   };
// });

const sceneOptions = [
  {
    value: "ASR",
    label: "ASR",
  },
  {
    value: "MT",
    label: "MT",
  },
  {
    value: "TTS",
    label: "TTS",
  },
  {
    value: "ASR+MT",
    label: "ASR+MT",
  },
  {
    value: "ASR+MT+TTS",
    label: "ASR+MT+TTS",
  },
];

const languageData = ref({
  languageFrom: "",
  languageTo: "",
});
provide("languageData", languageData);

const languageRules = ref({
  languageFrom: [
    { required: true, message: "请选择源语言", trigger: "change" },
  ],
  languageTo: [
    { required: true, message: "请选择目标语言", trigger: "change" },
  ],
});

const languageOptions = [
  {
    value: "Chinese",
    label: "中文",
  },
  {
    value: "English",
    label: "英语",
  },
  {
    value: "Arabic",
    label: "阿拉伯语",
  },
  {
    value: "Thai",
    label: "泰语",
  },
];

const transformLanguage = [
  {
    target: "enar",
    from: "English",
    to: "Arabic",
  },
  {
    target: "aren",
    from: "Arabic",
    to: "English",
  },
  {
    target: "then",
    from: "Thai",
    to: "English",
  },
  {
    target: "enth",
    from: "English",
    to: "Thai",
  },
  {
    target: "chth",
    from: "Chinese",
    to: "Thai",
  },
  {
    target: "thch",
    from: "Thai",
    to: "Chinese",
  },
  {
    target: "ench",
    from: "English",
    to: "Chinese",
  },
  {
    target: "chen",
    from: "Chinese",
    to: "English",
  },
];

const directoryToLanguage = [
  {
    directoryA: "英阿互译",
    directoryB: "阿语",
    MTLanguage: "aren",
    ASRLanguage: "arabic",
    TTSLanguage: "en",
  },
  {
    directoryA: "英阿互译",
    directoryB: "英语",
    MTLanguage: "enar",
    ASRLanguage: "english",
    TTSLanguage: "ar",
  },
];

const haldelCombinedFormData = (formData) => {
  let transformedFormData = {
    exec_list: formData.exec_list.map((item) => {
      if (item === "MT") {
        return "mt";
      }
      if (item === "ASR") {
        return "asr";
      }
      if (item === "TTS") {
        return "tts";
      }
    }),
    task_name: formData.task_name,
  };

  // console.log(transformedFormData.exec_list);
  if (transformedFormData.exec_list.some((item) => item === "mt")) {
    let language = "";
    // console.log("languageFrom");
    // console.log(formData.languageFrom);
    // console.log("languageTo");
    // console.log(formData.languageTo);
    transformLanguage.forEach((lang) => {
      if (
        lang.from === formData.languageFrom &&
        lang.to === formData.languageTo
      ) {
        language = lang.target;
      }
    });
    console.log("language");
    console.log(language);
    // console.log("formData.MTDataSets");
    // console.log(formData.MTDataSets);
    transformedFormData.mt = {
      model_id:
        transformedFormData.exec_list[0] === "mt"
          ? formData.model_id
          : formData.model_id_MT,
      type: "xf",
      model_type: "word",
      username: token.value,
    };

    if (transformedFormData.exec_list[0] === "mt") {
      transformedFormData.mt.dataset = formData.dataSets.map((dataset) => {
        return (
          dataset.directoryA +
          "/" +
          dataset.directoryB +
          "/" +
          dataset.directoryC +
          "/" +
          dataset.directoryD
        );
      });
    } else if (transformedFormData.exec_list[1] === "mt") {
      transformedFormData.mt.dataset = formData.MTDataSets.map((dataset) => {
        return (
          dataset.directoryA +
          "/" +
          dataset.directoryB +
          "/" +
          dataset.directoryC +
          "/" +
          dataset.directoryD
        );
      });
    }
    if (language !== "") {
      transformedFormData.mt.language = language;
    } else {
      directoryToLanguage.forEach((item) => {
        if (
          formData.directoryA === item.directoryA &&
          formData.directoryB.slice(0, 2) === item.directoryB
        ) {
          transformedFormData.mt.language = item.MTLanguage;
        }
      });
    }
  }
  if (transformedFormData.exec_list.some((item) => item === "asr")) {
    transformedFormData.asr = {
      model_id:
        transformedFormData.exec_list[0] === "asr" &&
        transformedFormData.exec_list.length === 1
          ? formData.model_id
          : formData.model_id_ASR,
      datasets: formData.dataSets.map((dataset) => {
        return (
          dataset.directoryA +
          "/" +
          dataset.directoryB +
          "/" +
          dataset.directoryC +
          "/" +
          dataset.directoryD
        );
      }),
      username: token.value,
      label:
        //  store.getters["interpretation/getLabel"],
        store.getters["interpretation/getLabel"].directoryA +
        "/" +
        store.getters["interpretation/getLabel"].directoryB +
        "/" +
        store.getters["interpretation/getLabel"].directoryC +
        (store.getters["interpretation/getLabel"].directoryD ? "/" : "") +
        (store.getters["interpretation/getLabel"].directoryD
          ? store.getters["interpretation/getLabel"].directoryD
          : ""),
    };
    directoryToLanguage.forEach((item) => {
      if (
        formData.directoryA === item.directoryA &&
        formData.directoryB.slice(0, 2) === item.directoryB
      ) {
        transformedFormData.asr.language = item.ASRLanguage;
      }
    });
  }
  if (transformedFormData.exec_list.some((item) => item === "tts")) {
    transformedFormData.tts = {
      model_id:
        transformedFormData.exec_list[0] === "tts"
          ? formData.model_id
          : formData.model_id_TTS,
      datasets:
        transformedFormData.exec_list[0] === "tts"
          ? formData.dataSets.map((dataset) => {
              return (
                dataset.directoryA +
                "/" +
                dataset.directoryB +
                "/" +
                dataset.directoryC
              );
            })
          : [],
      username: token.value,
    };
    directoryToLanguage.forEach((item) => {
      if (
        formData.directoryA === item.directoryA &&
        formData.directoryB.slice(0, 2) === item.directoryB
      ) {
        transformedFormData.tts.language = item.TTSLanguage;
      }
    });
  }
  return transformedFormData;
};

const startEvaluation = () => {
  let combinedFormData = steps
    .filter((fil) => {
      if (fil.index < 3) return fil;
    })
    .reduce((acc, step) => {
      if (typeof step.formData === "object" && step.formData !== null) {
        return { ...acc, ...step.formData };
      }
      return acc;
    }, {});

  combinedFormData = {
    ...combinedFormData,
    dataSets:
      scene.value === "MT"
        ? store.getters["interpretation/getMTDataset"]
        : store.getters["interpretation/getDataSets"],
    MTDataSets: scene.value.includes("ASR+MT")
      ? store.getters["interpretation/getMTDataset"]
      : [],
    exec_list: scene.value.split("+"),
    languageFrom: languageData.value.languageFrom,
    languageTo: languageData.value.languageTo,
  };
  console.log("combinedFormData");
  console.log(combinedFormData);

  const transformedFormData = haldelCombinedFormData(combinedFormData);
  console.log("transformedFormData");
  console.log(transformedFormData);

  // return;
  try {
    runInterpretation({ ...transformedFormData, username: token.value }).then(
      (res) => {
        if (res.data.status === "failed") {
          ElMessage({
            type: "error",
            message: "运行失败：" + res.data.res,
          });
          return;
        } else {
          ElMessage({
            type: "success",
            message: "运行成功",
          });
          is_run.value = true;
        }
      }
    );
  } catch (error) {
    console.log(error);
  }
};

const clearSelections = () => {
  store.dispatch("interpretation/updateDataSets", []);
  store.dispatch("interpretation/updateMTDataset", "");
  store.dispatch("interpretation/updateDirectoryA", "");
  store.dispatch("interpretation/updateDirectoryB", "");
  store.dispatch("interpretation/updateDirectoryC", []);
  store.dispatch("interpretation/updateDirectoryD", []);
  store.dispatch("interpretation/updateLabelDirectoryC", "");
};

const taskStore = useTaskStore();

const getTaskInfo = () => {
  if (route.query.task_id) {
    taskId.value = route.query.task_id;
    is_run.value = true;
    const config = taskStore.getTaskById(taskId.value)[0];
    console.log("config");
    console.log(config);
    store.dispatch("interpretation/updateOpenDatasetInfo", true);
    store.dispatch("interpretation/updateOpenLabelInfo", true);
    store.dispatch("interpretation/updateOpenMTDatasetInfo", true);

    stepAFormData.model_id = config.model_id;
    const modelIDs = config.model_id.split(";");
    if (modelIDs[1]) {
      stepAFormData.model_id_ASR = modelIDs[0];
      stepAFormData.model_id_MT = modelIDs[1];
      if (modelIDs[2]) {
        stepAFormData.model_id_TTS = modelIDs[2];
      }
    }
    steps[1].formData.task_name = config.name;
    steps[2].formData = config.result;
    steps[3].formData = config.result;
    scene.value = config.assessmentType;
    if (scene.value.includes("MT")) {
      const language = config.taskConfig.language;
      transformLanguage.forEach((lang) => {
        if (lang.target === language) {
          languageData.value.languageFrom = lang.from;
          languageData.value.languageTo = lang.to;
        }
      });
      if (scene.value === "MT") {
        const allDirectoryD = [];
        config.taskConfig.datasets.forEach((dataset) => {
          const directories = dataset.split("/");
          store.dispatch("interpretation/updateDirectoryA", directories[0]);
          store.dispatch("interpretation/updateDirectoryB", directories[1]);
          store.dispatch("interpretation/updateDirectoryC", directories[2]);
          if (allDirectoryD.every((item) => item !== directories[3])) {
            allDirectoryD.push(directories[3]);
          }
        });
        store.dispatch("interpretation/updateDirectoryD", allDirectoryD);
      }
    } else if (scene.value.includes("ASR")) {
      if (scene.value === "ASR") {
        const allDirectoryC = [];
        const allDirectoryD = [];
        config.taskConfig.datasets.forEach((dataset) => {
          const directories = dataset.split("/");
          // console.log("directories");
          // console.log(directories);
          store.dispatch("interpretation/updateDirectoryA", directories[0]);
          store.dispatch("interpretation/updateDirectoryB", directories[1]);
          if (allDirectoryC.every((item) => item !== directories[2])) {
            allDirectoryC.push(directories[2]);
          }
          if (allDirectoryD.every((item) => item !== directories[3])) {
            allDirectoryD.push(directories[3]);
          }
        });
        store.dispatch("interpretation/updateDirectoryC", allDirectoryC);
        store.dispatch("interpretation/updateDirectoryD", allDirectoryD);

        const labelDirections = config.taskConfig.label.split("/");
        // console.log("labelDirections");
        // console.log(labelDirections);
        store.dispatch(
          "interpretation/updateLabelDirectoryC",
          labelDirections[2]
        );
      }
    } else if (scene.value === "TTS") {
      const allDirectoryC = [];
      config.taskConfig.datasets.forEach((dataset) => {
        const directories = dataset.split("/");
        console.log("directories");
        console.log(directories);
        store.dispatch("interpretation/updateDirectoryA", directories[0]);
        store.dispatch("interpretation/updateDirectoryB", directories[1]);
        if (allDirectoryC.every((item) => item !== directories[2])) {
          allDirectoryC.push(directories[2]);
        }
      });
      store.dispatch("interpretation/updateDirectoryC", allDirectoryC);
    }
  }
};

const toResult = () => {
  router.push("/modelEvaluation/multipleEvaluation/evaluationResult");
};

onMounted(async () => {
  clearSelections();
  store.dispatch("interpretation/updateOpenDatasetInfo", false);
  store.dispatch("interpretation/updateOpenLabelInfo", false);
  getTaskInfo();
  token.value = localStorage.getItem("username");
});
</script>

<style scoped>
.onlineContainer {
  /* background-color: #f5f5f5; */
  width: 100%;
  height: 90%;
  min-height: calc(100vh - 80px);
  /* height: auto; */
  display: flex;
  /* max-width: 95%; */
  min-width: 100%;
  /* gap: 12px; */
  position: relative;
  flex-direction: column;
  /* padding: 10px; */
}

.createContainer {
  background-color: #ffffff;
  padding: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  height: 95%;
  margin-top: 10px;
  /* margin-left: 10px; */
  margin-right: 10px;
  max-width: 98%;
}

.insideContainer {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.radio-row {
  max-height: 40px;
  align-items: center;
  position: relative;
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

.radioDisabled :deep(.el-radio-button__inner) {
  color: #a8abb2 !important;
}

.stepContainer {
  margin-top: 10px;
  display: flex;
  height: 90%;
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
  /* 垂直均匀分布 */
  height: 100%;
  gap: 10px;
  padding: 0 16px;
  box-sizing: border-box;
  background-color: transparent;
  top: 20px;
  overflow: auto;

  > .description-card {
    flex: 0 0 auto;
  }
}

.description-card {
  background-color: #f4f3f9;
  border-radius: 6px;
  min-height: 180px;
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
  width: calc(100% - 20px);
}

.content {
  position: relative;
  width: 100%;
  max-width: 900px;
}

.step1DescBox {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
  padding: 30px 0;
}

:deep(.el-table__body tr.current-row > td.el-table__cell) {
  background-color: rgb(121, 187, 255);
  color: #fff;
}

.circle {
  display: inline-block;
  min-width: 10px;
  height: 10px;
  background-color: rgb(132, 132, 224);
  border-radius: 50%;
  margin-right: 5px;
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

.step2DescBox {
  height: 100%;
}

.startButton {
  margin-left: 5%;
}

.flex {
  display: flex;
}

.center {
  justify-content: center;
  align-items: center;
}

.gap10 {
  gap: 10px;
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

.returnicon {
  position: absolute;
  top: 5px;
  left: 10px;
  /* bottom: 10px; */
}

.languageForm {
  height: 32px;
}

.margin_top_20 {
  margin-top: 20px;
}
</style>
