<template>
  <div>
    <el-tabs v-model="activeName" type="card" @tab-change="handleClick" class="typeTabs">
      <el-tab-pane label="全部" name="all" />
      <!-- <el-tab-pane label="Ruler1" name="ruler1" />
      <el-tab-pane label="Ruler2" name="ruler2" />
      <el-tab-pane label="AISF" name="aisf" /> -->
      <!-- <el-tab-pane label="同声传译" name="interpretation" /> -->
      <el-tab-pane label="儿童伴读" name="childrenStudy" />
    </el-tabs>
    <div class="cardContainer" v-if="activeName!=='childrenStudy'">
      <div v-show="!loading" class="colFlex">
        <el-row>
          <el-col :span="12">
            <span>日期筛选器：</span>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              unlink-panels
              range-separator="至"
              start-placeholder="起始日期"
              end-placeholder="结束日期"
              :shortcuts="shortcuts"
              :disabled-date="disabledDate"
              :default-time="defaultTime"
              @change="dateChange"
              value-format="YYYY-MM-DD HH:mm:ss"
            />
          </el-col>
          <el-col :span="6">
            <span style="margin:0 20px">模型筛选</span>
            <el-select
              v-model="selectedModels"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="请选择模型"
              popper-class="custom-header"
              :max-collapse-tags="1"
              :style="{ width: isSmallScreen ? '150px' : '250px' }"
              @change="modelsChange"
            >
              <template #header>
                <el-checkbox
                  v-model="checkAll"
                  :indeterminate="indeterminate"
                  @change="handleCheckAll"
                >All</el-checkbox>
              </template>
              <el-option
                v-for="item in models"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-col>
          <el-col :span="6" v-show="activeName!=='interpretation'">
            <span style="margin-right: 20px;">测试集筛选</span>
            <el-cascader
              v-model="selectedDatasets"
              collapse-tags
              collapse-tags-tooltip
              :props="cascaderProps"
              placeholder="请选择测试集"
              popper-class="custom-header"
              :max-collapse-tags="1"
              :style="{ width: isSmallScreen ? '150px' : '250px' }"
              :show-all-levels="false"
              :options="datasetOptions"
              @change="datasetsChange"
            >
              <template #header>
                <el-checkbox
                  v-model="checkAllDataset"
                  :indeterminate="datasetIndeterminate"
                  @change="handleCheckAllDataset"
                >All</el-checkbox>
              </template>
            </el-cascader>
          </el-col>
        </el-row>
        <el-row class="taskStatistics" :gutter="20">
          <el-col :span="6">
            <div class="statistic-card">
              <el-statistic :value="evaluationTimes" :value-style="taskCountValueStyle">
                <template #title>
                  <span class="taskCountTitle">评估总次数</span>
                </template>
              </el-statistic>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="statistic-card">
              <el-statistic
                :value="remainingHoursSource + minutesSource + secondsSource"
                :value-style="taskCountValueStyle"
              >
                <template #title>
                  <span class="taskCountTitle">评估总用时</span>
                </template>
              </el-statistic>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="statistic-card">
              <EvaluationBarChart
                v-if="taskCreators.length > 0"
                :data="taskCreators"
                :title="'测评人次数统计'"
                width="100%"
                height="100%"
              />
              <div v-else>暂无数据</div>
            </div>
          </el-col>
        </el-row>
        <el-row class="taskStatistics" :gutter="20">
          <el-col :span="6" v-if="activeName!=='interpretation'">
            <div class="statistic-card">
              <!--千万别动v-if，惨痛教训-->
              <EvaluationPieChart
                v-if="languageChartData.length > 0"
                :data="languageChartData"
                :title="'大语言评估统计'"
                width="100%"
                height="100%"
              />
              <div v-else>暂无数据</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="statistic-card">
              <EvaluationPieChart
                v-if="multiChartData.length > 0"
                :data="multiChartData"
                :title="'多模态评估统计'"
                width="100%"
                height="100%"
              />
              <div v-else>暂无数据</div>
            </div>
          </el-col>
          <el-col :span="activeName==='interpretation'?18:12" :key="heatMapKey">
            <div class="statistic-card">
              <EvaluationHeatmapChart
                v-if="modelDataSetData.length > 0"
                :data="modelDataSetData"
                :xData="dataSetList"
                :yData="modelList"
                :title="'模型在测试集评测次数热力图'"
                width="100%"
                height="100%"
              />
              <div v-else>暂无数据</div>
            </div>
          </el-col>
        </el-row>
      </div>
      <div v-loading="loading" style="height: 100%;" v-show="loading"></div>
    </div>
    <div v-else>
      <childrenStudyStastics />
    </div>
  </div>
</template>

<script lang="ts" setup>
import {
  ref,
  onMounted,
  nextTick,
  watch,
  computed,
  onBeforeUnmount,
} from "vue";
import { getList } from "@/api/runService.js";
import dayjs from "dayjs";
import EvaluationBarChart from "./charts/evaluationBarChart.vue";
import EvaluationPieChart from "./charts/evaluationPieChart.vue";
import EvaluationHeatmapChart from "./charts/evaluationHeatmapChart.vue";
import { useTransition } from "@vueuse/core";
import { get_datasets } from "@/api/dataSetApi";
import { useDatasetStore } from "@/stores/datasetStore";
import type { CascaderOption, TabsPaneContext } from "element-plus";
import childrenStudyStastics from "./childrenStudyStastics.vue";

const loading = ref(true);
const activeName = ref("all");
const heatMapKey = ref(1);

const handleClick = (tab) => {
  console.log(tab);
  if (tab === "interpretation") {
    // console.log("同声传译！！！");
    allTaskInfo.value = rawTaskInfo.value.filter((task) => {
      const validTypes = ["ASR", "MT", "TTS", "ASR+MT", "ASR+MT+TTS"];
      return validTypes.includes(task.assessmentType);
    });
    // console.log("filteredallTaskInfo");
    // console.log(allTaskInfo.value);
    filterTasks();
    handelFilting();
    heatMapKey.value++;
  } else {
    switch (tab) {
      case "all":
        allTaskInfo.value = rawTaskInfo.value;
        break;
      case "ruler1":
        allTaskInfo.value = rawTaskInfo.value.filter((task) => {
          const validTypes = ["通用评估(Ruler1)"];
          return validTypes.includes(task.assessmentType);
        });
        break;
      case "ruler2":
        allTaskInfo.value = rawTaskInfo.value.filter((task) => {
          const validTypes = ["领域评估(Ruler2)"];
          return validTypes.includes(task.assessmentType);
        });
        break;
      case "aisf":
        allTaskInfo.value = rawTaskInfo.value.filter((task) => {
          const validTypes = ["AISF"];
          return task.assessmentType.includes(validTypes);
        });
        break;
    }
    filterTasks();
    handelFilting();
    heatMapKey.value++;
  }
};

const models = ref([]);
const selectedModels = ref([]);
const checkAll = ref(false);
const indeterminate = ref(false);

const isSmallScreen = ref(false);

const handleCheckAll = (val) => {
  indeterminate.value = false;
  if (val) {
    selectedModels.value = models.value.map((_) => _.value);
    modelsChange(val);
  } else {
    selectedModels.value = [];
    modelsChange([]);
  }
};

const cascaderProps = ref({
  emitPath: false,
  multiple: true,
});
const selectedDatasets = ref([]);
const checkAllDataset = ref(false);
const datasetIndeterminate = ref(false);
const datasetOptions = ref([]);

const getAllValuePaths = computed(() => {
  const result: string[][] = [];
  const queue: { node: CascaderOption; path: string[] }[] =
    datasetOptions.value.map((node) => ({ node, path: [node.value] }));

  while (queue.length > 0) {
    const { node, path } = queue.shift()!;
    if (node.children?.length) {
      node.children.forEach((child) => {
        queue.push({ node: child, path: [...path, child.value as string] });
      });
    } else {
      result.push(path);
    }
  }
  return result;
});

const handleCheckAllDataset = (val) => {
  datasetIndeterminate.value = false;
  selectedDatasets.value = val ? getAllValuePaths.value : [];
};

const rawTaskInfo = ref([]);
const allTaskInfo = ref([]);
const filteredTasks = ref([]);
const modelList = ref([]);
const dataSetList = ref([]);
const modelDataSetData = ref([]);

const taskCountValueStyle = {
  fontSize: "46px",
  fontWeight: "700",
};

const dateRange = ref([]);
const defaultTime = ref<[Date, Date]>([
  new Date(2000, 1, 1, 0, 0, 0),
  new Date(2000, 2, 1, 23, 59, 59),
]);
const shortcuts = [
  {
    text: "过去一周",
    value: () => {
      const end = dayjs().endOf("day");
      const start = dayjs().subtract(7, "day").startOf("day");
      return [
        start.format("YYYY-MM-DD HH:mm:ss"),
        end.format("YYYY-MM-DD HH:mm:ss"),
      ];
    },
  },
  {
    text: "过去一月",
    value: () => {
      const end = dayjs().endOf("day");
      const start = dayjs().subtract(30, "day").startOf("day");
      return [
        start.format("YYYY-MM-DD HH:mm:ss"),
        end.format("YYYY-MM-DD HH:mm:ss"),
      ];
    },
  },
  {
    text: "过去季度",
    value: () => {
      const end = dayjs().endOf("day");
      const start = dayjs().subtract(91, "day").startOf("day");
      return [
        start.format("YYYY-MM-DD HH:mm:ss"),
        end.format("YYYY-MM-DD HH:mm:ss"),
      ];
    },
  },
];

const disabledDate = (time: Date) => {
  return time.getTime() > Date.now();
};

const dateChange = (val) => {
  if (val) {
    // console.log("DateChange:");
    // console.log(val[0]);
    // console.log(val[1]);

    if ((!val[0] || val[0] === "") && (!val[1] || val[1] === "")) {
      runTimesSource.value = allTaskInfo.value.length;
    } else {
      runTimesSource.value = 0;
    }
  }
  handelFilting();
};

const modelsChange = (val) => {
  if (val) {
    if (val.length === 0) {
      checkAll.value = false;
      indeterminate.value = false;
    } else if (val.length === modelList.value.length) {
      checkAll.value = true;
      indeterminate.value = false;
    } else {
      indeterminate.value = true;
    }
  }
  handelFilting();
};

const datasetsChange = (val) => {
  console.log("datasets:");
  console.log(val);
  if (val.length === 0) {
    checkAllDataset.value = false;
    datasetIndeterminate.value = false;
  } else if (val.length === getAllValuePaths.value.length) {
    checkAllDataset.value = true;
    datasetIndeterminate.value = false;
  } else {
    datasetIndeterminate.value = true;
  }
  handelFilting();
};

const handelFilting = () => {
  filterTasks();
  hoursSource.value = 0;
  filteredTasks.value.forEach((task) => {
    hoursSource.value += task.runningTime;
  });
  runTimesSource.value = filteredTasks.value.length;
  getCreators();
  getLanguageChartData();
  getMultiChartData();
  getModelDataSetData();
};

const filterTasks = () => {
  filteredTasks.value = [];
  // if (props.evalType === "interpretation") {
  //   console.log("同声传译！！！");
  //   allTaskInfo.value = allTaskInfo.value.filter((task) => {
  //     const validTypes = ["ASR", "MT", "TTS", "ASR+MT", "ASR+MT+TTS"];
  //     return validTypes.includes(task.assessmentType);
  //   });
  //   console.log("filteredallTaskInfo");
  //   console.log(allTaskInfo.value);
  // }
  filteredTasks.value = allTaskInfo.value.filter((task) => {
    // 日期筛选
    if (dateRange.value && dateRange.value[0] && dateRange.value[1]) {
      const taskDate = new Date(task.createTime);
      if (
        (dateRange.value[0] && taskDate < new Date(dateRange.value[0])) ||
        (dateRange.value[1] && taskDate > new Date(dateRange.value[1]))
      ) {
        return false;
      }
    }

    // 其他筛选条件
    if (selectedModels.value && selectedModels.value.length > 0) {
      return selectedModels.value.some((model) => task.model_name === model);
    } else {
      selectedModels.value = [];
    }

    if (selectedDatasets.value && selectedDatasets.value.length > 0) {
      return selectedDatasets.value.some((dataset) =>
        task.datasets.some((item) => item === dataset)
      );
    } else {
      selectedDatasets.value = [];
    }

    return true;
  });
  console.log("filteredTasks");
  console.log(filteredTasks.value);
};

const runTimesSource = ref(0);
const evaluationTimes = useTransition(runTimesSource, {
  duration: 500,
});

const hoursSource = ref(0);
const remainingHoursSource = computed(() => {
  return Math.floor(hoursSource.value / 3600) > 0
    ? Math.floor(hoursSource.value / 3600) + "时"
    : "";
});
const minutesSource = computed(() => {
  return Math.floor((hoursSource.value % 3600) / 60) > 0
    ? Math.floor((hoursSource.value % 3600) / 60) + "分"
    : "";
});
const secondsSource = computed(() => {
  return Math.floor(hoursSource.value % 60) > 0
    ? Math.floor(hoursSource.value % 60) + "秒"
    : "";
});
// const hours = useTransition(remainingHoursSource, {
//   duration: 500,
// });
// const minutes = useTransition(minutesSource, {
//   duration: 500,
// });
// const seconds = useTransition(secondsSource, {
//   duration: 500,
// });

const taskCreators = ref([]);

const getCreators = () => {
  // console.log("filteredTasks");
  // console.log(filteredTasks.value);
  taskCreators.value = [];
  filteredTasks.value.forEach((task) => {
    if (task.creator && task.creator !== "") {
      const existingCreator = taskCreators.value.find(
        (creator) => creator.creator === task.creator
      );

      if (existingCreator) {
        existingCreator.times += 1;
      } else {
        taskCreators.value.push({
          creator: task.creator,
          times: 1,
        });
      }
    }
  });

  // console.log("taskCreators");
  // console.log(taskCreators.value);
};

const languageChartData = ref([]);

const getLanguageChartData = () => {
  // console.log("filteredTasks");
  // console.log(filteredTasks.value);

  languageChartData.value = [];
  filteredTasks.value.forEach((task) => {
    if (task.modelType[0] === "LLM" || task.modelType === "LLM") {
      const existingType = languageChartData.value.find(
        (item) => item.name === task.assessmentType
      );

      if (existingType) {
        existingType.value += 1;
      } else {
        languageChartData.value.push({
          name: task.assessmentType,
          value: 1,
        });
      }
    }
  });
  // console.log("languageChartData");
  // console.log(languageChartData.value);
};

const multiChartData = ref([]);

const getMultiChartData = () => {
  // console.log("filteredTasks");
  // console.log(filteredTasks.value);

  multiChartData.value = [];
  filteredTasks.value.forEach((task) => {
    if (task.modelType[0] === "MLLM" || task.modelType === "MLLM") {
      const existingType = multiChartData.value.find(
        (item) => item.name === task.assessmentType
      );

      if (existingType) {
        existingType.value += 1;
      } else {
        multiChartData.value.push({
          name: task.assessmentType,
          value: 1,
        });
      }
    }
  });
  // console.log("multiChartData");
  // console.log(multiChartData.value);
};

const getModelDataSetData = () => {
  // console.log("filteredTasks");
  // console.log(filteredTasks.value);

  modelDataSetData.value = [];
  modelList.value = [];
  dataSetList.value = [];

  // 提取 getValidTime 函数到 sort 作用域外
  const getValidTime = (timeString) => {
    const timestamp = new Date(timeString).getTime();
    return isNaN(timestamp) ? -Infinity : timestamp;
  };

  const sortedTasks = [...filteredTasks.value].sort((a, b) => {
    const timeB = getValidTime(b.createTime);
    const timeA = getValidTime(a.createTime);
    return timeB - timeA; // 保持原降序排序逻辑
  });

  sortedTasks.forEach((task) => {
    if (modelList.value.length > 20 || dataSetList.value.length > 30) {
      return;
    }
    if (task.result) {
      Object.keys(task.result).forEach((model) => {
        if (model === task.model_name) {
          //装填modelList
          const existingModel = modelList.value.find((name) => name === model);
          if (!existingModel) {
            modelList.value.push(model);
          }

          task.result[model]
            .map((item: { dataset_name: string }) => {
              return item.dataset_name;
            })
            .forEach((dataSet: string) => {
              //装填dataSetList
              const existingDataset = dataSetList.value.find(
                (name) => name === dataSet
              );
              if (!existingDataset) {
                dataSetList.value.push(dataSet);
              }

              //装填模型测试集次数数组
              const existingData = modelDataSetData.value.find((array) => {
                return array[0] === task.model_name && array[1] === dataSet;
              });

              if (existingData) {
                existingData[2]++;
              } else {
                modelDataSetData.value.push([task.model_name, dataSet, 1]);
              }
            });
        }
      });
    }
  });
};

const loadTaskData = async () => {
  const res = await getList();
  rawTaskInfo.value = res.data;
  allTaskInfo.value = rawTaskInfo.value;
  console.log("allTaskInfo");
  console.log(allTaskInfo.value);

  // dateRange.value = shortcuts[0].value();
  hoursSource.value = 0;

  // allTaskInfo.value.forEach((task) => {
  //   if (
  //     dateRange.value[0] &&
  //     dateRange.value[0] !== "" &&
  //     dateRange.value[1] &&
  //     dateRange.value[1] !== "" &&
  //     new Date(task.createTime) > new Date(dateRange.value[0]) &&
  //     new Date(task.createTime) < new Date(dateRange.value[1])
  //   ) {
  //     filteredTasks.value.push(task);
  //   }
  // });
  filterTasks();
  filteredTasks.value.forEach((task) => {
    hoursSource.value += task.runningTime;
  });
  runTimesSource.value = filteredTasks.value.length;

  //   console.log("dateRange");
  //   console.log(dateRange.value);
  loading.value = false;
};

const loadModelData = async () => {
  // selectedModels.value = modelList.value

  models.value = modelList.value.map((item) => {
    return {
      value: item,
      label: item,
    };
  });
};

const datasetStore = useDatasetStore();

const loadDataSetData = async () => {
  const languageDatasets = await getDatasetFromStore(1);
  const multipleDatasets = await getDatasetFromStore(2);
  const aisfDatasets = await getDatasetFromStore(3);

  // console.log(Object.keys(languageDatasets));
  // console.log(Object.keys(multipleDatasets));
  // console.log(Object.keys(aisfDatasets));

  datasetOptions.value.push(
    {
      value: "language",
      label: "通用测试集",
      children: [],
    },
    {
      value: "multiple",
      label: "领域测试集",
      children: [],
    },
    // {
    //   value: "aisf",
    //   label: "开发态测试集",
    //   children: [],
    // }
  );

  Object.keys(languageDatasets).forEach((dataset) => {
    datasetOptions.value
      .find((item) => item.value === "language")
      .children.push({
        value: dataset,
        label: dataset,
      });
  });

  Object.keys(multipleDatasets).forEach((dataset) => {
    datasetOptions.value
      .find((item) => item.value === "multiple")
      .children.push({
        value: dataset,
        label: dataset,
      });
  });

  Object.keys(aisfDatasets).forEach((dataset) => {
    datasetOptions.value
      .find((item) => item.value === "aisf")
      .children.push({
        value: dataset,
        label: dataset,
      });
  });
};

const getDatasetFromStore = async (isField) => {
  const key = "ruler" + isField;
  const datasets = datasetStore.getDatasets(key);

  if (!datasets || Object.keys(datasets).length === 0) {
    const res = await get_datasets(isField);
    datasetStore.setDatasets(key, res.data);
    return res.data;
  } else {
    return datasets;
  }
};

const checkScreenWidth = () => {
  console.log("checkScreenWidth");
  isSmallScreen.value = window.innerWidth < 1500;
  console.log(isSmallScreen.value);
};

const handleResize = () => {
  location.reload();
};

onMounted(async () => {
  await loadTaskData();
  getCreators();
  getLanguageChartData();
  getMultiChartData();
  getModelDataSetData();
  loadModelData();
  loadDataSetData();
  checkScreenWidth();
  window.addEventListener("resize", checkScreenWidth);
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", checkScreenWidth);
  window.removeEventListener("resize", handleResize);
});
</script>

<style scoped>
.cardContainer {
  display: flex;
  flex-direction: column;
  gap: 2%;
  height: calc(100vh - 140px);
  margin: 0;
}

.taskStatistics {
  height: 47%;
  /* gap:1% */
}

.taskStatistics :deep(.el-col) {
  /* border: solid 1px black; */
  border-radius: 8px;
}

.text_center {
  display: inline-flex;
  text-align: center;
  align-items: center;
  justify-content: center;
}

.taskCountTitle {
  font-size: 18px;
  font-weight: 600;
}

.statistic-card {
  /* height: 100%;
  padding: 20px;
  border-radius: 4px;
  background-color: var(--el-bg-color-overlay); */
  display: flex;
  text-align: center;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
  border-radius: 12px;
  border: 1px solid #f0f2f6;
  box-shadow: 0 3px 8px #1f63b514;
}

.colFlex {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 2%;
}

.typeTabs {
  height: 30px;
}

.typeTabs :deep(.el-tabs__header) {
  height: 30px;
}

.typeTabs :deep(.el-tabs__item) {
  font-size: 14px;
  height: 30px;
  line-height: 30px;
}
</style>
