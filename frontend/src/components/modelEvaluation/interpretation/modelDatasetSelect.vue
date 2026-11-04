<template>
  <div
    style="margin: 0 auto; width: 90%"
    v-loading.fullscreen.lock="loading"
    element-loading-text="加载测试集中..."
  >
    <div v-if="scene">
      <div style="margin-bottom: 20px;">{{ scene }}</div>
      <el-form
        :model="localFormData"
        label-width="auto"
        class="modelForm"
        :rules="rules"
        style="max-width: 100%"
        :disabled="taskId!==''"
      >
        <el-form-item label="模型" prop="model_id" v-if="scene.length < 6">
          <el-cascader
            v-model="localFormData.model_id"
            :options="modelOptions"
            :props="{ emitPath: false, expandTrigger: 'click' }"
            placeholder="请选择模型"
          />
        </el-form-item>
        <div v-else>
          <el-form-item label="ASR模型" prop="model_id_ASR">
            <el-cascader
              v-model="localFormData.model_id_ASR"
              :options="ASRModelOptions"
              :props="{ emitPath: false, expandTrigger: 'click' }"
              placeholder="请选择模型"
            />
          </el-form-item>
          <el-form-item label="MT模型" prop="model_id_MT">
            <el-cascader
              v-model="localFormData.model_id_MT"
              :options="MTModelOptions"
              :props="{ emitPath: false, expandTrigger: 'click' }"
              placeholder="请选择模型"
            />
          </el-form-item>
          <el-form-item label="TTS模型" prop="model_id_TTS" v-if="scene.length === 10">
            <el-cascader
              v-model="localFormData.model_id_TTS"
              :options="TTSModelOptions"
              :props="{ emitPath: false, expandTrigger: 'click' }"
              placeholder="请选择模型"
            />
          </el-form-item>
        </div>
        <div class="flex gap20">
          <el-form-item
            label="一级目录"
            label-position="top"
            prop="directoryA"
            style="flex:1;min-width: 100px"
            v-if="scene!=='MT'"
          >
            <el-select
              v-model="localFormData.directoryA"
              placeholder="请选择一级目录"
              style="width: 180px"
              @change="directoryAChange"
              clearable
            >
              <el-option
                v-for="item in optionsA"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item
            label="二级目录"
            label-position="top"
            prop="directoryB"
            style="flex:1;min-width: 100px"
          >
            <el-select
              v-model="localFormData.directoryB"
              placeholder="请选择二级目录"
              style="width: 180px"
              :disabled="!ADone"
              @change="directoryBChange"
              clearable
            >
              <el-option
                v-for="item in optionsB"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item
            :label="scene==='ASR+MT'?'ASR三级目录':'三级目录'"
            label-position="top"
            prop="directoryC"
            style="flex:1;min-width: 100px"
          >
            <el-select
              v-model="localFormData.directoryC"
              placeholder="请选择三级目录"
              style="width: 180px"
              :disabled="!ABDone"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              @change="directoryCChange"
              v-if="scene !== 'MT'"
            >
              <el-option
                v-for="item in optionsC"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-select
              v-model="localFormData.directoryC"
              placeholder="请选择三级目录"
              style="width: 180px"
              :disabled="!ABDone"
              collapse-tags
              collapse-tags-tooltip
              clearable
              @change="directoryCChange"
              v-else
            >
              <el-option
                v-for="item in optionsC"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item
            :label="scene==='ASR+MT'?'ASR四级目录':'四级目录'"
            label-position="top"
            prop="directoryD"
            style="flex:1;min-width: 100px"
            v-if="haveASR||scene==='MT'"
          >
            <el-select
              v-model="localFormData.directoryD"
              placeholder="请选择四级目录"
              style="width: 180px"
              :disabled="!ABDone"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              @change="directoryDChange"
            >
              <el-option
                v-for="item in optionsD"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <div>
          <el-button type="primary" v-if="!openDatasetInfo" @click="changeStoreOpenDatasetInfo">
            <span v-if="!haveASR">测试集详情展开</span>
            <span v-else>语料详情展开</span>
          </el-button>
          <el-button type="primary" v-if="openDatasetInfo" @click="changeStoreOpenDatasetInfo">
            <span v-if="!haveASR">测试集详情收起</span>
            <span v-else>语料详情收起</span>
          </el-button>
          <el-table
            ref="tableRef"
            :data="datasetTableData"
            v-show="openDatasetInfo"
            reserve-selection
            @selection-change="handleSelectionChange"
            border
            row-key="id"
            v-if="scene !== 'MT'"
            max-height="500"
            scrollbar-always-on
          >
            <el-table-column type="selection" width="55" />
            <el-table-column property="id" label="id" width="50" />
            <el-table-column property="directoryA" label="一级目录" />
            <el-table-column property="directoryB" label="二级目录" />
            <el-table-column property="directoryC" label="三级目录" />
            <el-table-column property="directoryD" label="四级目录" v-if="haveASR" />
          </el-table>
          <el-table
            ref="tableRef"
            :data="datasetTableData"
            v-show="openDatasetInfo"
            reserve-selection
            @selection-change="handleMTChange"
            border
            row-key="id"
            v-if="scene === 'MT'"
            max-height="500"
            scrollbar-always-on
          >
            <el-table-column type="selection" width="55" />
            <el-table-column property="id" label="id" width="50" />
            <el-table-column property="directoryA" label="一级目录" />
            <el-table-column property="directoryB" label="二级目录" />
            <el-table-column property="directoryC" label="三级目录" />
            <el-table-column property="directoryD" label="四级目录" />
          </el-table>
        </div>
        <div style="margin-top: 20px;" v-if="haveASR">
          <span style="font-size: 14px;color:rgb(96, 98, 102);">ASR标注三级目录</span>
          <div style="margin-bottom:8px;"></div>
          <el-select
            v-model="lableDirectoryC"
            placeholder="请选择三级目录"
            style="width: 180px;display: block;margin-bottom: 20px;"
            :disabled="!ABDone"
            collapse-tags
            collapse-tags-tooltip
            clearable
            max-height="500"
            @change="LabelDirectoryCChange"
          >
            <el-option
              v-for="item in labelOptionsC"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-button type="primary" v-if="!openLabelInfo" @click="changeStoreOpenLabelInfo">标注详情展开</el-button>
          <el-button type="primary" v-if="openLabelInfo" @click="changeStoreOpenLabelInfo">标注详情收起</el-button>
          <el-table
            ref="tableLabelRef"
            :data="labelTableData"
            v-show="openLabelInfo"
            reserve-selection
            highlight-current-row
            @current-change="handleLabelChange"
            style="cursor: pointer;"
            max-height="500"
            border
            row-key="id"
            scrollbar-always-on
          >
            <el-table-column property="id" label="id" width="50" />
            <el-table-column property="directoryA" label="一级目录" />
            <el-table-column property="directoryB" label="二级目录" />
            <el-table-column property="directoryC" label="三级目录" />
            <!-- <el-table-column property="directoryD" label="四级目录" /> -->
          </el-table>
        </div>
        <div v-if="scene==='ASR+MT'||scene==='ASR+MT+TTS'" style="margin-top: 20px;">
          <div style="display: flex; gap: 20px;margin-bottom: 20px;">
            <div style="display: flex; flex-direction: column; align-items: flex-start;">
              <span style="font-size: 14px; color: rgb(96, 98, 102); margin-bottom: 8px;">MT语料三级目录</span>
              <el-select
                v-model="localFormData.MtDirectoryC"
                placeholder="请选择三级目录"
                style="width: 180px; display: inline-block;"
                :disabled="!ABDone"
                collapse-tags
                collapse-tags-tooltip
                clearable
                @change="MTDirectoryCChange"
              >
                <el-option
                  v-for="item in MTOptionsC"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </div>
            <div style="display: flex; flex-direction: column; align-items: flex-start;">
              <span style="font-size: 14px; color: rgb(96, 98, 102); margin-bottom: 8px;">MT语料四级目录</span>
              <el-select
                v-model="localFormData.MtDirectoryD"
                placeholder="请选择四级目录"
                style="width: 180px; display: inline-block;"
                :disabled="!ABDone || !localFormData.MtDirectoryC"
                multiple
                collapse-tags
                collapse-tags-tooltip
                clearable
                @change="MTDirectoryDChange"
              >
                <el-option
                  v-for="item in MTOptionsD"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </div>
          </div>
          <el-button type="primary" v-if="!openMTDatasetInfo" @click="changeOpenMTDataset">
            <span v-if="!haveASR">测试集详情展开</span>
            <span v-else>MT语料详情展开</span>
          </el-button>
          <el-button type="primary" v-if="openMTDatasetInfo" @click="changeOpenMTDataset">
            <span v-if="!haveASR">测试集详情收起</span>
            <span v-else>MT语料详情收起</span>
          </el-button>
          <el-table
            ref="MTTableRef"
            :data="MTDatasetTableData"
            v-show="openMTDatasetInfo"
            reserve-selection
            @selection-change="handleMTChange"
            border
            row-key="id"
            max-height="500"
            scrollbar-always-on
          >
            <el-table-column type="selection" width="55" />
            <el-table-column property="id" label="id" width="50" />
            <el-table-column property="directoryA" label="一级目录" />
            <el-table-column property="directoryB" label="二级目录" />
            <el-table-column property="directoryC" label="三级目录" />
            <el-table-column property="directoryD" label="四级目录" />
          </el-table>
        </div>
      </el-form>
    </div>
    <div v-else>请选择场景</div>
  </div>
</template>

<script lang="ts" setup>
import {
  ref,
  inject,
  watch,
  onMounted,
  reactive,
  computed,
  nextTick,
} from "vue";
import { ModelService } from "@/services/modelService.js";
import { useAIModelStore } from "@/stores/aiModel";
import { useStore } from "vuex";
import { getIntepretationDatasets } from "@/api/dataSetApi";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

const route = useRoute();
const store = useStore();
const AIStore = useAIModelStore();
const scene = inject("scene") as Object;
const languageData = inject("languageData");

const language2Directory = [
  {
    from: "Arabic",
    to: "English",
    directoryA: "英阿互译",
    // directoryB: "阿语语料",
  },
  {
    from: "English",
    to: "Arabic",
    directoryA: "英阿互译",
    // directoryB: "阿语语料",
  },
];

const languageDone = ref(false);

watch(
  () => [languageData.value.languageFrom, languageData.value.languageTo],
  ([newFrom, newTo]) => {
    if (newFrom && newTo) {
      languageDone.value = true;
      const foundItem = language2Directory.find((item) => {
        return (
          (item.from === newFrom && item.to === newTo) ||
          (item.from === newTo && item.to === newFrom)
        );
      });

      if (foundItem) {
        store.dispatch("interpretation/updateDirectoryA", foundItem.directoryA);
        directoryAChange(foundItem.directoryA);
        // directoryBChange(foundItem.directoryB);
        // setDirectoryCOptions(foundItem.directoryB);
      } else {
        console.log("No matching item found, not updating directoryA.");
        ElMessage({
          type: "error",
          message: "没有匹配语言的MT语料",
        });
      }
    }
  },
  { immediate: true }
);

const taskId = ref("");

const haveASR = ref(true);

function processModels(tag, target) {
  const filteredModels = models_option.filter((item) =>
    item.info.tags.includes(tag)
  );
  target.value = filteredModels.map((model) => ({
    value: model.model_id,
    label: model.model_id,
  }));
}

watch(
  scene,
  (val: String) => {
    // console.log("scene");
    // console.log(val);
    if (val.includes("ASR")) {
      haveASR.value = true;
    } else {
      haveASR.value = false;
    }

    if (val === "ASR" || val === "MT" || val === "TTS") {
      processModels(val, modelOptions);
    } else {
      processModels("ASR", ASRModelOptions);
      processModels("MT", MTModelOptions);
      processModels("TTS", TTSModelOptions);
    }

    optionsA.value = [];
    if (Object.keys(rawData.value).length !== 0) {
      switch (val) {
        case "ASR":
          Object.keys(rawData.value.ASRAllData).forEach((key) => {
            optionsA.value.push({
              value: key,
              label: key,
            });
          });
          break;
        case "MT":
          Object.keys(rawData.value.MTAllData).forEach((key) => {
            optionsA.value.push({
              value: key,
              label: key,
            });
          });
          rules.value.directoryC[0].required = true;
          break;
        case "TTS":
          Object.keys(rawData.value.TTSAllData).forEach((key) => {
            optionsA.value.push({
              value: key,
              label: key,
            });
          });
          break;
        default:
          Object.keys(rawData.value.ASRAllData).forEach((key) => {
            optionsA.value.push({
              value: key,
              label: key,
            });
          });
          break;
      }
    }

    transformedData.value = transformData(rawData.value, val);
    updateData(transformedData.value, 0);
  },
  { deep: true }
);

const ASRModelOptions = ref([]);
const MTModelOptions = ref([]);
const TTSModelOptions = ref([]);

const props = defineProps(["modelValue"]);
const emit = defineEmits(["update:modelValue"]);
const localFormData = ref(props.modelValue);
watch(
  localFormData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);

const rules = ref({
  model_id: [
    {
      required: true,
      message: "请选择模型",
      trigger: "change",
    },
  ],
  directoryA: [
    {
      required: true,
      message: "请选择一级目录",
      trigger: "change",
    },
  ],
  directoryB: [
    {
      required: true,
      message: "请选择二级目录",
      trigger: "change",
    },
  ],
  directoryC: [
    {
      required: scene.value === "MT",
      message: "请选择三级目录",
      trigger: "change",
    },
  ],
  // directoryD: [
  //   {
  //     required: true,
  //     message: "请选择四级目录",
  //     trigger: "change",
  //   },
  // ],
});

const model = ref();

const transformData = (data, sceneVal) => {
  const result = [];
  let index = 0;
  function recurse(currentData, path) {
    for (let key in currentData) {
      if (currentData.hasOwnProperty(key)) {
        const newPath = path.concat(key);
        if (
          typeof currentData[key] === "object" &&
          currentData[key] !== null &&
          !Array.isArray(currentData[key])
        ) {
          recurse(currentData[key], newPath);
        } else {
          result.push({
            id: index++,
            directoryA: newPath.length > 0 ? newPath[0] : null,
            directoryB: newPath.length > 1 ? newPath[1] : null,
            directoryC: newPath.length > 2 ? newPath[2] : null,
            directoryD: newPath.length > 3 ? newPath[3] : null,
            files: currentData[key],
          });
        }
      }
    }
  }
  if (sceneVal.includes("ASR")) {
    if (scene.value.includes("ASR+MT")) {
      result.length = 0;
      recurse(data.MTAllData, []);
      const tempMT = [];
      index = 0;
      result.forEach((item) => {
        item.files.forEach((file) => {
          tempMT.push({
            id: index++,
            directoryA: item.directoryA,
            directoryB: item.directoryB,
            directoryC: item.directoryC,
            directoryD: file,
          });
        });
      });
      updateMTDatasetData(tempMT, 1);
    }

    result.length = 0;
    recurse(data.ASRAllData, []);
    const resultLabel = [];
    let indexLabel = 0;
    function recurseLabel(currentData, path) {
      for (let key in currentData) {
        if (currentData.hasOwnProperty(key)) {
          const newPath = path.concat(key);
          const child = currentData[key];
          if (
            typeof child === "object" &&
            child !== null &&
            !Array.isArray(child) &&
            Object.keys(child).length > 0
          ) {
            recurseLabel(child, newPath);
          } else {
            resultLabel.push({
              id: indexLabel++,
              directoryA: newPath.length > 0 ? newPath[0] : null,
              directoryB: newPath.length > 1 ? newPath[1] : null,
              directoryC: newPath.length > 2 ? newPath[2] : null,
              directoryD: newPath.length > 3 ? newPath[3] : null,
              files: child,
            });
          }
        }
      }
    }
    recurseLabel(data.ASRTagging, []);
    // console.log("resultLabel");
    // console.log(resultLabel);
    labelTransformedData.value = resultLabel;
    updateLabelData(labelTransformedData.value);
  } else if (sceneVal === "MT") {
    recurse(data.MTAllData, []);
    const tempMT = [];
    index = 0;
    // const seenDirectoryC = [];
    result.forEach((item) => {
      item.files.forEach((file) => {
        // if (seenDirectoryC.some((str) => str === item.directoryC)) {
        // } else {
        tempMT.push({
          id: index++,
          directoryA: item.directoryA,
          directoryB: item.directoryB,
          directoryC: item.directoryC,
          directoryD: file,
        });
        //   seenDirectoryC.push(item.directoryC);
        // }
      });
    });
    return tempMT;
  } else if (sceneVal === "TTS") {
    recurse(data.TTSAllData, []);
  }
  return result;
};
const transformedData = ref();
const tableRef = ref(null);
const tableLabelRef = ref(null);
const datasetTableData = ref([]);

const labelTransformedData = ref([]);
const labelTableData = ref([]);

const models_option = reactive([]);
const modelOptions = ref([]);

const optionsA = ref([]);
const optionsB = ref([]);
const optionsC = ref([]);
const optionsD = ref([]);

const directoryA = computed(
  () => store.getters["interpretation/getDirectoryA"]
);
const directoryB = computed(
  () => store.getters["interpretation/getDirectoryB"]
);
const directoryC = computed(
  () => store.getters["interpretation/getDirectoryC"]
);
const directoryD = computed(
  () => store.getters["interpretation/getDirectoryD"]
);

watch(directoryA, (val) => {
  // console.log("directoryA Changed!!!");
  // console.log(val);
  localFormData.value.directoryA = val;
});

watch(directoryB, (val) => {
  // console.log("directoryB Changed!!!");
  // console.log(val);
  localFormData.value.directoryB = val;
});

watch(directoryC, (val) => {
  // console.log("directoryC Changed!!!");
  // console.log(val);
  localFormData.value.directoryC = val;
});

watch(directoryD, (val) => {
  // console.log("directoryD Changed!!!");
  // console.log(val);
  localFormData.value.directoryD = val;
});

const ADone = computed(() => {
  return localFormData.value.directoryA;
});
const ABDone = computed(() => {
  return localFormData.value.directoryA && localFormData.value.directoryB;
});

const openDatasetInfo = computed(
  () => store.getters["interpretation/getOpenDatasetInfo"]
);
const openLabelInfo = computed(
  () => store.getters["interpretation/getOpenLabelInfo"]
);
const changeStoreOpenDatasetInfo = () => {
  store.dispatch(
    "interpretation/updateOpenDatasetInfo",
    !store.getters["interpretation/getOpenDatasetInfo"]
  );
  //   console.log("执行了！");
  //   console.log(store.getters["interpretation/getOpenDatasetInfo"]);
  //   console.log(openDatasetInfo.value);
};

const changeStoreOpenLabelInfo = () => {
  store.dispatch(
    "interpretation/updateOpenLabelInfo",
    !store.getters["interpretation/getOpenLabelInfo"]
  );
};

const selectedInfos = computed(() => {
  if (scene.value !== "MT") {
    return store.getters["interpretation/getDataSets"];
  } else if (scene.value === "MT") {
    return store.getters["interpretation/getMTDataset"];
  }
});

watch(selectedInfos, () => {
  //   console.log("selectedInfosCHANGED");
  //   console.log(selectedInfos.value);
});

const selectedLabel = computed(() => {
  return store.getters["interpretation/getLabel"];
});

const handleSelectionChange = (vals: []) => {
  // console.log("handleSelectionChange");
  // console.log("vals");
  // console.log(vals);
  store.dispatch("interpretation/updateDataSets", vals);
};

const handleMTChange = (val) => {
  // console.log("val");
  // console.log(val);
  store.dispatch("interpretation/updateMTDataset", val);
};

const handleLabelChange = (val) => {
  store.dispatch("interpretation/updateLabel", val);
};

const setDirectoryBOptions = (value) => {
  optionsB.value = [];
  if (haveASR.value) {
    Object.keys(rawData.value.ASRAllData[value]).forEach((item: any) => {
      optionsB.value.push({
        value: item,
        label: item,
      });
    });
  } else if (scene.value === "MT") {
    Object.keys(rawData.value.MTAllData[value]).forEach((item: any) => {
      optionsB.value.push({
        value: item,
        label: item,
      });
    });
  } else if (scene.value === "TTS") {
    Object.keys(rawData.value.TTSAllData[value]).forEach((item: any) => {
      optionsB.value.push({
        value: item,
        label: item,
      });
    });
  }
};

const matchingKeys = ref([]);

const setDirectoryCOptions = (value) => {
  // console.log("rawData");
  // console.log(rawData.value);
  optionsC.value = [];
  labelOptionsC.value = [];
  if (haveASR.value) {
    Object.keys(rawData.value.ASRAllData[directoryA.value][value]).forEach(
      (item: any) => {
        optionsC.value.push({
          value: item,
          label: item,
        });
      }
    );
    const labelB = Object.keys(rawData.value.ASRTagging[directoryA.value]).find(
      (item) => item.includes(value.slice(0, 1))
    );
    Object.keys(rawData.value.ASRTagging[directoryA.value][labelB]).forEach(
      (item: any) => {
        labelOptionsC.value.push({
          value: item,
          label: item,
        });
      }
    );
    if (scene.value.includes("ASR+MT")) {
      if (
        rawData.value &&
        rawData.value.MTAllData &&
        rawData.value.MTAllData[directoryA.value]
      ) {
        MTOptionsC.value = [];
        const prefix = value.slice(0, 2); // 获取value的前两个字符
        matchingKeys.value = Object.keys(
          rawData.value.MTAllData[directoryA.value]
        ).filter((key) => key.startsWith(prefix)); // 过滤出前两个字符相同的键
        // console.log("matchingKeys");
        // console.log(matchingKeys.value);

        const existingValues = new Set();

        // matchingKeys.value.forEach((key) => {
        Object.keys(rawData.value.MTAllData[directoryA.value]).forEach(
          (key) => {
            Object.keys(rawData.value.MTAllData[directoryA.value][key]).forEach(
              (item) => {
                MTOptionsC.value.push({
                  value: item,
                  label: item,
                });
                rawData.value.MTAllData[directoryA.value][key][item].forEach(
                  (DD: any) => {
                    if (!existingValues.has(DD)) {
                      // 检查值是否已存在
                      MTOptionsD.value.push({
                        value: DD,
                        label: DD,
                      });
                      existingValues.add(DD); // 将值添加到Set中
                    }
                  }
                );
              }
            );
          }
        );

        if (MTOptionsC.value.length === 0) {
          console.log("Data is not available or is empty.");
          ElMessage({
            type: "error",
            message: "没有匹配的MT语料1",
          });
        }
      } else {
        console.log("Data is not available or is empty.");
        ElMessage({
          type: "error",
          message: "没有匹配的MT语料2",
        });
      }
    }
  } else if (scene.value === "MT") {
    Object.keys(rawData.value.MTAllData[directoryA.value][value]).forEach(
      (item: any) => {
        optionsC.value.push({
          value: item,
          label: item,
        });
      }
    );
  } else if (scene.value === "TTS") {
    Object.keys(rawData.value.TTSAllData[directoryA.value][value]).forEach(
      (item: any) => {
        optionsC.value.push({
          value: item,
          label: item,
        });
      }
    );
  }
  // console.log("optionsC");
  // console.log(optionsC.value);
};

const setDirectoryDOptionsFromB = (value) => {
  optionsD.value = [];
  const existingValues = new Set(); // 用于存储已存在的值
  if (haveASR.value && haveASR) {
    Object.keys(rawData.value.ASRAllData[directoryA.value][value]).forEach(
      (third) => {
        Object.keys(
          rawData.value.ASRAllData[directoryA.value][value][third]
        ).forEach((item: any) => {
          if (!existingValues.has(item)) {
            // 检查值是否已存在
            optionsD.value.push({
              value: item,
              label: item,
            });
            existingValues.add(item); // 将值添加到Set中
          }
        });
      }
    );
  } else if (scene.value === "MT") {
    // console.log(rawData.value.MTAllData[directoryA.value][value]);
    Object.keys(rawData.value.MTAllData[directoryA.value][value]).forEach(
      (third) => {
        rawData.value.MTAllData[directoryA.value][value][third].forEach(
          (item: any) => {
            if (!existingValues.has(item)) {
              // 检查值是否已存在
              optionsD.value.push({
                value: item,
                label: item,
              });
              // console.log(optionsD.value);
              existingValues.add(item); // 将值添加到Set中
            }
          }
        );
      }
    );
  }
};

const setDirectoryDOptions = (value) => {
  optionsD.value = [];
  if (haveASR.value && haveASR) {
    if (Array.isArray(value)) {
      const existingValues = new Set(); // 用于存储已存在的值
      value.forEach((third) => {
        Object.keys(
          rawData.value.ASRAllData[directoryA.value][directoryB.value][third]
        ).forEach((item: any) => {
          if (!existingValues.has(item)) {
            // 检查值是否已存在
            optionsD.value.push({
              value: item,
              label: item,
            });
            existingValues.add(item); // 将值添加到Set中
          }
        });
      });
    }
  } else if (scene.value === "MT") {
    // if (Array.isArray(value)) {
    const existingValues = new Set(); // 用于存储已存在的值
    // value.forEach((third) => {
    rawData.value.MTAllData[directoryA.value][directoryB.value][value].forEach(
      (item: any) => {
        if (!existingValues.has(item)) {
          // 检查值是否已存在
          optionsD.value.push({
            value: item,
            label: item,
          });
          existingValues.add(item); // 将值添加到Set中
        }
      }
    );
    // });
    // }
  }

  console.log("optionsD");
  console.log(optionsD.value);
};

const directoryAChange = (value) => {
  //   console.log(value);
  if (value) {
    if (haveASR.value) {
      const newValue = labelTransformedData.value.filter(
        (item) => item.directoryA === value
      );
      updateLabelData(newValue);
    }
    if (scene.value.includes("ASR+MT")) {
      beforeDirectoryCMTData.value = MTDatasetTableData.value;
      const newValue = beforeDirectoryCMTData.value.filter(
        (item) => item.directoryA === value
      );
      updateMTDatasetData(newValue, 1);
    }
    const newValue = transformedData.value.filter(
      (item) => item.directoryA === value
    );
    updateData(newValue, 1);
    setDirectoryBOptions(value);
    store.dispatch("interpretation/updateDirectoryA", value);
  } else {
    localFormData.value.directoryB = "";
    localFormData.value.directoryC = "";
    localFormData.value.directoryD = "";
    // datasetTableData.value = transformedData.value;
    updateData(transformedData.value, 0);
    store.dispatch("interpretation/updateDirectoryA", "");
    store.dispatch("interpretation/updateLabelDirectoryC", "");
  }
  filtered1TableData.value = datasetTableData.value;
  filteredLabelData.value = labelTableData.value;
  filtered2TableData.value = datasetTableData.value;
  beforeDirectoryCMTData.value = MTDatasetTableData.value;
};

const filtered1TableData = ref([]);
const filteredLabelData = ref([]);
const directoryBFilterdLabel = ref([]);

const directoryBChange = (value) => {
  // console.log(value);
  if (value) {
    if (haveASR.value) {
      const newValue = filteredLabelData.value.filter((item) =>
        value.includes(item.directoryB.slice(0, 1))
      );
      updateLabelData(newValue);
      directoryBFilterdLabel.value = newValue;
    }
    // if (scene.value.includes("ASR+MT")) {
    // const newValue = beforeDirectoryCMTData.value.filter((item) =>
    //   item.directoryB.startsWith(value.slice(0, 2))
    // );
    // updateMTDatasetData(newValue, 1);
    // selectMTDataset();
    // setDirectoryCOptions(newValue);
    // }
    const newValue = filtered1TableData.value.filter(
      (item) => item.directoryB === value
    );
    updateData(newValue, 2);
    setDirectoryCOptions(value);
    setDirectoryDOptionsFromB(value);
    // selectEveryRow();
    store.dispatch("interpretation/updateDirectoryB", value);
  } else if (localFormData.value.directoryA) {
    localFormData.value.directoryC = "";
    localFormData.value.directoryD = "";
    directoryAChange(localFormData.value.directoryA);
    store.dispatch("interpretation/updateDirectoryB", "");
    store.dispatch("interpretation/updateLabelDirectoryC", "");
    store.dispatch("interpretation/updateMTDirectionC", "");
    store.dispatch("interpretation/updateMTDirectionD", "");
    localFormData.MtDirectoryC = "";
    localFormData.MtDirectoryD = "";
  } else {
    localFormData.value.directoryC = "";
    localFormData.value.directoryD = "";
    // datasetTableData.value = filtered1TableData.value;
    updateData(transformedData.value, 1);
    store.dispatch("interpretation/updateDirectoryB", "");
    store.dispatch("interpretation/updateLabelDirectoryC", "");
    store.dispatch("interpretation/updateMTDirectionC", "");
    store.dispatch("interpretation/updateMTDirectionD", "");
    localFormData.MtDirectoryC = "";
    localFormData.MtDirectoryD = "";
  }
  filtered2TableData.value = datasetTableData.value;
  filteredLabelData2.value = labelTableData.value;
  filtered3TableData.value = datasetTableData.value;
  if (MTDatasetTableData.value.length !== 0) {
    beforeDirectoryCMTData.value = MTDatasetTableData.value;
    afterDirectoryCMTData.value = MTDatasetTableData.value;
  }
};

const filtered2TableData = ref([]);
const filteredLabelData2 = ref([]);

const directoryCChange = (value) => {
  console.log(value);
  if (value && value.length > 0 && scene.value !== "MT") {
    const newValue = filtered2TableData.value.filter((item) =>
      value.find((directory) => item.directoryC === directory)
    );
    updateData(newValue, 3);
    setDirectoryDOptions(value);
    store.dispatch("interpretation/updateDirectoryC", value);
  } else if (value && value !== "" && scene.value === "MT") {
    const newValue = filtered2TableData.value.filter(
      (item) => item.directoryC === value
    );
    updateData(newValue, 3);
    setDirectoryDOptions(value);
    store.dispatch("interpretation/updateDirectoryC", value);
  } else if (scene.value === "MT") {
    updateData(filtered2TableData.value, 2);
    store.dispatch("interpretation/updateDirectoryC", "");
    store.dispatch("interpretation/updateDirectoryD", []);
  } else {
    updateData(filtered2TableData.value, 2);
    store.dispatch("interpretation/updateDirectoryC", []);
  }
  filtered3TableData.value = datasetTableData.value;
  if (haveASR.value) {
    directoryDChange(localFormData.value.directoryD);
  }
};

const filtered3TableData = ref([]);

const directoryDChange = (value) => {
  //   console.log(value);
  if (value.length > 0) {
    const newValue = filtered3TableData.value.filter((item) => {
      return value.some((tag) => item.directoryD.includes(tag));
    });
    updateData(newValue, 4);
    selectEveryRow();
    store.dispatch("interpretation/updateDirectoryD", value);
  } else {
    updateData(filtered3TableData.value, 3);
    store.dispatch("interpretation/updateDirectoryD", []);
  }
};

const previousSelected = ref();
const isDataUpdating = ref(false);

const labelOptionsC = ref([]);
const lableDirectoryC = computed(
  () => store.getters["interpretation/getLabelDirectoryC"]
);

const LabelDirectoryCChange = (value) => {
  // console.log("value");
  // console.log(value);
  console.log("directoryBFilterdLabel");
  console.log(directoryBFilterdLabel.value);
  if (value) {
    const newValue = directoryBFilterdLabel.value.filter(
      (item) => item.directoryC === value
    );
    updateLabelData(newValue);
    selectCurrentLabel();
    store.dispatch("interpretation/updateLabelDirectoryC", value);
  } else {
    labelTableData.value = directoryBFilterdLabel.value;
    store.dispatch("interpretation/updateLabelDirectoryC", "");
  }
};

const updateData = async (newData, index) => {
  // console.log("updateData" + index);
  isDataUpdating.value = true;
  // if (scene.value !== "MT") {
  previousSelected.value = selectedInfos.value.slice();
  // console.log("PV");
  // console.log(previousSelected.value);
  // }
  // else if (scene.value === "MT") {
  //   previousSelected.value = selectedInfos.value;
  // console.log("MTPV");
  // console.log(previousSelected.value);
  // }
  // console.log("newData");
  // console.log(newData);
  datasetTableData.value = newData;
  await nextTick(() => {
    restoreSelection();
    if (scene.value !== "MT" && (index === 2 || index === 4)) {
      selectEveryRow();
    } else if (
      (scene.value === "MT" && (index === 3 || index === 4)) ||
      (scene.value === "TTS" && index === 3)
    ) {
      selectEveryRow();
    }
  });
};

const restoreSelection = () => {
  if (scene.value !== "MT") {
    const selectedIds = previousSelected.value.map((row) => row.id);
    if (tableRef.value) {
      tableRef.value.clearSelection();
      // console.log("清空啦！");
    }
    // console.log("selectedIds");
    // console.log(selectedIds);
    // console.log("datasetTableData");
    // console.log(datasetTableData.value);
    datasetTableData.value.forEach((row) => {
      if (selectedIds.includes(row.id) && tableRef.value) {
        // console.log("选中了" + row.id);
        tableRef.value.toggleRowSelection(row, true);
      }
    });
  } else if (scene.value === "MT") {
    datasetTableData.value.forEach((row) => {
      if (previousSelected.value.id === row.id && tableRef.value) {
        tableRef.value.toggleRowSelection(row, true);
      }
    });
  }
  isDataUpdating.value = false;
};

const selectEveryRow = () => {
  // console.log("selectEveryRow");
  datasetTableData.value.forEach((row) => {
    if (tableRef.value) {
      tableRef.value.toggleRowSelection(row, true);
    }
  });
};

const selectCurrentRow = () => {
  console.log("selectCurrentRow");
  // console.log("datasetTableData.value");
  // console.log(datasetTableData.value);
  const row = datasetTableData.value[0];
  // console.log("row");
  // console.log(row);
  if (tableRef.value) {
    tableRef.value.setCurrentRow(row);
  }
};

const selectCurrentLabel = () => {
  console.log("selectCurrentLabel");
  const row = labelTableData.value[0];
  if (tableLabelRef.value) {
    tableLabelRef.value.setCurrentRow(row);
  }
};

const updateLabelData = (newData) => {
  // console.log("updateLabelData");
  labelTableData.value = newData;
};

watch(tableRef, () => {
  handelMarkChecked();
});

const handelMarkChecked = () => {
  //   console.log("selectedInfosONMMark");
  //   console.log(selectedInfos.value);
  if (tableRef.value) {
    // console.log("有table!!");
    if (scene.value !== "MT") {
      selectedInfos.value.forEach((selected) => {
        const row = datasetTableData.value.find((r) => r.id === selected.id);
        if (row) {
          // console.log("row");
          // console.log(row);
          tableRef.value.toggleRowSelection(row, true);
        }
      });
    }
  } else {
    // console.log("没table!!");
  }
};

const MTTableRef = ref(null);
const MTOptionsC = ref([]);

const MTDatasetTableData = ref([]);
const beforeDirectoryCMTData = ref([]);
const isUpdatingMT = ref(false);

const updateMTDatasetData = async (value, index) => {
  // 改为async函数
  console.log("updateMTDatasetData");

  isUpdatingMT.value = true;
  MTDatasetTableData.value = value;

  // 关键修改：等待DOM更新完成
  await nextTick();

  // 确保表格引用存在且有数据
  if (MTTableRef.value && MTDatasetTableData.value.length > 0) {
    // 先清除所有选择
    MTTableRef.value.clearSelection();

    // 全选所有行
    if (index === 2 || index === 3) {
      selectMTDataset();
    }
  }
  isUpdatingMT.value = false;
};

const selectMTDataset = () => {
  console.log("selectMTDataset");
  // console.log(MTDatasetTableData.value);
  // const row = MTDatasetTableData.value[0];
  // if (MTTableRef.value) {
  //   MTTableRef.value.setCurrentRow(row);
  // }
  if (MTTableRef.value && MTDatasetTableData.value.length > 0) {
    MTDatasetTableData.value.forEach((row) => {
      MTTableRef.value.toggleRowSelection(row, true);
    });
  }
};

watch(MTDatasetTableData, (val) => {
  // console.log("MTDatasetTableData的值更新了：");
  // console.log(val);
});

const openMTDatasetInfo = computed(
  () => store.getters["interpretation/getOpenMTDatasetInfo"]
);

const afterDirectoryCMTData = ref([]);
const MTOptionsD = ref([]);

const MTDirectoryCChange = (val) => {
  console.log("MTDirectoryCChange");
  console.log(val);

  if (val) {
    const newValue = beforeDirectoryCMTData.value.filter(
      (item) => item.directoryC === val
    );
    updateMTDatasetData(newValue, 2);
    setMTDirectoryDOptions(val);
    selectMTDataset();
    afterDirectoryCMTData.value = newValue;
    store.dispatch("interpretation/updateMTDirectionC", val);
  } else {
    updateMTDatasetData(beforeDirectoryCMTData.value, 1);
    store.dispatch("interpretation/updateMTDirectionC", "");
  }
};

const changeOpenMTDataset = () => {
  store.dispatch(
    "interpretation/updateOpenMTDatasetInfo",
    !store.getters["interpretation/getOpenMTDatasetInfo"]
  );
};

const setMTDirectoryDOptions = (val) => {
  MTOptionsD.value = [];
  const existingValues = new Set(); // 用于存储已存在的值
  // matchingKeys.value.forEach((key) => {
  Object.keys(rawData.value.MTAllData[directoryA.value]).forEach((key) => {
    rawData.value.MTAllData[directoryA.value][key][val].forEach((item: any) => {
      if (!existingValues.has(item)) {
        // 检查值是否已存在
        MTOptionsD.value.push({
          value: item,
          label: item,
        });
        existingValues.add(item); // 将值添加到Set中
      }
    });
  });
};

const MTDirectoryDChange = (value) => {
  console.log("afterDirectoryCMTData");
  console.log(afterDirectoryCMTData.value);
  // console.log("MtDirectoryD");
  // console.log(value);
  if (value && value.length > 0) {
    const newValue = afterDirectoryCMTData.value.filter((item) => {
      return value.some((tag) => item.directoryD.includes(tag));
    });
    updateMTDatasetData(newValue, 3);
    selectMTDataset();
    store.dispatch("interpretation/updateMTDirectionD", value);
  } else {
    updateMTDatasetData(afterDirectoryCMTData.value, 2);
    store.dispatch("interpretation/updateMTDirectionD", []);
  }
};

const handleMTSelectionChange = (val) => {
  console.log("handleMTSelectionChange");
  console.log(val);
};

const HandelInitSelection = async () => {
  // console.log("HandelInitSelection");
  localFormData.value.directoryA = directoryA.value;
  localFormData.value.directoryB = directoryB.value;
  localFormData.value.directoryC = directoryC.value;
  localFormData.value.directoryD = directoryD.value;

  directoryAChange(localFormData.value.directoryA);
  directoryBChange(localFormData.value.directoryB);
  directoryCChange(localFormData.value.directoryC);
  directoryDChange(localFormData.value.directoryD);
  LabelDirectoryCChange(lableDirectoryC.value);
  //   console.log("selectedInfosONMOUNTED");
  //   console.log(selectedInfos.value);
};

const loadModels = async () => {
  if (Array.isArray(AIStore.models) && AIStore.models.length !== 0) {
    Object.assign(models_option, AIStore.models);
  } else {
    try {
      const data = await ModelService.getAllModelInfo();
      // console.log("data");
      // console.log(data);
      Object.assign(models_option, data);
    } catch (error) {
      console.error(error);
    }
  }

  // console.log('scene')
  // console.log(scene.value)
  // const models = models_option.filter((item) => {
  //   console.log(item)
  //   console.log(item.info.tags.some((x) => x === scene.value))
  //   return item.info.tags.some((x) => x === scene.value);
  // });

  // // console.log("models");
  // // console.log(models);
  // models.forEach((model) => {
  //   modelOptions.push({
  //     value: model.model_id,
  //     label: model.model_id,
  //   });
  // });
  // // console.log("modelOptions");
  // // console.log(modelOptions);
  // console.log(localFormData.value.model_id);
};

const rawData = ref({
  ASRAllData: {},
  ASRTagging: {},
  MTAllData: {},
  TTSAllData: {},
});

const loading = ref(true);

const loadDatasets = async () => {
  // 尝试从localStorage中读取数据
  const storedData = localStorage.getItem("interpretationData");
  if (storedData) {
    // 如果存在数据，解析JSON字符串并赋值给rawData
    rawData.value = JSON.parse(storedData);
  } else {
    // 如果不存在数据，从API获取数据
    const res = await getIntepretationDatasets();
    // 将数据存储到localStorage中
    localStorage.setItem("interpretationData", JSON.stringify(res.data));
    // 将数据赋值给rawData
    rawData.value = res.data;
  }
  // console.log("rawData");
  // console.log(rawData.value);
  // rawData.value.directoryA.forEach((item: any) => {
  //   optionsA.value.push({
  //     value: item,
  //     label: item,
  //   });
  // });
  // rawData.value.directoryB.forEach((item: any) => {
  //   optionsB.value.push({
  //     value: item,
  //     label: item,
  //   });
  // });
  // rawData.value.directoryC.forEach((item: any) => {
  //   optionsC.value.push({
  //     value: item,
  //     label: item,
  //   });
  // });
  rawData.value.directoryD.forEach((item: any) => {
    optionsD.value.push({
      value: item,
      label: item,
    });
  });

  transformedData.value = transformData(
    rawData.value,
    scene.value && scene.value !== "" ? scene.value : ""
  );
  updateData(transformedData.value, 0);
  loading.value = false;
};

const getTaskInfo = () => {
  if (route.query.task_id) {
    taskId.value = route.query.task_id;
  }
};

onMounted(async () => {
  loadModels();
  await loadDatasets();
  HandelInitSelection();
  getTaskInfo();
});
</script>

<style scoped>
.modelForm :deep(.el-cascader) {
  width: 50%;
}

.flex {
  display: flex;
}

.gap20 {
  gap: 20px;
}
</style>