<template>
  <div class="dataContainer">
    <div class="taskDetailTitleContainer">
      <span style="padding: 0 10px"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" />
      <span style="padding: 0 20px;"></span>
      <span @click="goBack" style="color: #969696;cursor: pointer;" v-if="!singleDataset">我的评测任务</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;" v-if="!singleDataset">/</span>
      <span style="font-size:18px;font-weight:600;">评测详情</span>
    </div>
    <div class="task-info"></div>
    <el-tabs v-model="activeTab" class="tabsContainer">
      <el-tab-pane label="评测统计" name="first" v-if="isChildStudy">
        <ChildrenStudyStastics :task_id="task_id" />
      </el-tab-pane>
      <el-tab-pane label="各题详情" name="second">
        <el-card
          class="head_card"
          :body-style="{
            padding:'5px 20px',
        display: 'flex',
        'background-color': '#ffffff',
        width: '100%',
        'justify-content': 'space-between',
      }"
        >
          <div style="display: flex; align-items: center; gap: 12px;width:100%">
            <!-- <el-image
            style="width: 30px; height: 30px"
            src="/src/assets/deepseek.png"
            fit="cover"
            ></el-image>-->
            <span style="min-width:15%">
              <span style="margin-right:8px">模型名:</span>
              <strong>{{task.model_id}}</strong>
            </span>
            <span v-if="singleDataset">
              <span style="margin-right:8px">测试集:</span>
              <el-tag>{{ singleDataset }}</el-tag>
              <span style="margin-left:16px">严格准确率:</span>
              <el-tag type="success">{{ (singleScore * 100).toFixed(2) }}</el-tag>
              <template v-if="singleLooseScore > 0">
                <span style="margin-left:12px">宽松准确率:</span>
                <el-tag type="warning">{{ (singleLooseScore * 100).toFixed(2) }}</el-tag>
              </template>
            </span>
            <span v-else>
              <span style="width:4%">测试集:</span>
              <el-tooltip
                class="box-item"
                effect="dark"
                :content="options.join(',')"
                placement="top"
              >
                <span
                  style="
                max-width: 80%;
                white-space: nowrap;
                text-overflow: ellipsis;
                overflow: hidden;
              "
                >
                  <span v-for="(item, index) in options" :key="index">
                    {{ item }}
                    <span v-if="index < options.length - 1">,</span>
                  </span>
                </span>
              </el-tooltip>
            </span>
          </div>
        </el-card>
        <el-card
          class="head_card"
          :body-style="{
            padding:'5px 20px',
        display: 'flex',
        'background-color': '#ffffff',
        width: '100%',
        'justify-content': 'space-between',
        'align-items': 'center',
      }"
        >
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
            <template v-if="!singleDataset">
              <span>选择测试集：</span>
              <el-select
                v-model="selectValue"
                placeholder="Select"
                class="selectOrder"
                size="large"
                style="width: 320px; align-items: center"
                @change="dataChange"
              >
                <el-option v-for="item in options" :key="item" :label="item" :value="item" />
              </el-select>
            </template>
            <span v-if="!isinterpretation && !isChildStudy">选择子测试集：</span>
            <el-select
              v-model="selectSubValue"
              placeholder="Select"
              class="selectOrder"
              size="large"
              style="width: 300px; align-items: center"
              @change="subChange"
              v-if="!isinterpretation"
            >
              <el-option v-for="item in subsetOptions" :key="item" :label="item" :value="item" />
            </el-select>
            <el-button type="primary" style="margin-left: 16px" @click="drawer = true">查看评测结果</el-button>
            <el-button
              type="primary"
              style="margin-left: 16px"
              @click="asyncScoreClick"
              v-if="!isinterpretation && !isChildStudy && !singleDataset && !isRuler2"
            >分数同步</el-button>
            <el-button
              type="primary"
              style="margin-left: 16px"
              @click="asyncScoreClick"
              v-if="isinterpretation"
            >提交修改</el-button>
          </div>
          <!-- <div>
          <el-button @click="clickDownload" type="primary">下载当前测试集</el-button>
          <el-button @click="clickDownloadAll" type="primary">下载全部测试集</el-button>
          </div>-->
        </el-card>
        <AssessmentDetailPanel
          :task="task"
          :datasets="datasets"
          :assessment-type="assessmentType"
          :select-value="selectValue"
          :select-sub-value="selectSubValue"
          :scene="scene"
          :page-size="page"
          :is-llm-judge="is_llmjudge"
          :task-id="task_id"
          :model-id="currentModelID"
          v-model:result="Result"
        />
      </el-tab-pane>
    </el-tabs>
    <el-drawer v-model="drawer" :title="selectValue" size="50%">
      <el-table :data="localTableData" style="width: 100%" border stripe :show-summary="isRewriteBusiness" :summary-method="tableSummary">
        <el-table-column prop="datasetName" label="测试集名" min-width="150"></el-table-column>
        <el-table-column prop="subsetName" label="子测试集名" min-width="150" />
        <el-table-column prop="num" label="测试集子集数量" width="124" />
        <el-table-column prop="score" :label="hasLooseScoreData ? '严格准确率（%)' : '准确率（%)'">
          <template #default="scope">{{ ((scope.row.score || 0) * 100).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column v-if="hasLooseScoreData" prop="looseScore" label="宽松准确率（%)">
          <template #default="scope">{{ ((scope.row.looseScore || 0) * 100).toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="time" label="耗时" />
      </el-table>
    </el-drawer>
    <el-drawer v-model="drawer" size="80%" v-if="isinterpretation">
      <MtResult v-if="assessmentType==='MT'" :task_id="task.ID" />
      <ASRResult v-if="assessmentType==='ASR'" :task_id="task.ID" />
      <TTSResult v-if="assessmentType==='TTS'" :task_id="task.ID" />
      <ASRMTResult v-if="assessmentType==='ASR+MT'" :task_id="task.ID" />
    </el-drawer>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { get_datasets } from "@/api/dataSetApi";
import { ElMessage, ElLoading, ElMessageBox } from "element-plus";
import { useDatasetStore } from "@/stores/datasetStore";
import { getResult, asyncScore, getList } from "@/api/runService.js";
import MtResult from "../interpretationResult/mtResult.vue";
import ASRResult from "../interpretationResult/asrResult.vue";
import TTSResult from "../interpretationResult/ttsResult.vue";
import ASRMTResult from "../interpretationResult/asrmtResult.vue";
import ChildrenStudyStastics from "@/components/statistics/childrenStudyStastics.vue";
import { getEvaluationResult } from "@/api/dataService";
import AssessmentDetailPanel from "./assessmentDetailPanel.vue";
import { checkAllDatasetsTag, computeIsInterpretation } from "./assessmentSharedUtils";

const task = ref({});
const singleDataset = ref("");
const singleScore = ref(0);
const singleLooseScore = ref(0);
const activeTab = ref("first");
const route = useRoute();
const router = useRouter();
const task_id = ref("");
const selectValue = ref("");
const selectSubValue = ref("");
const Result = ref([]);
const datasets = ref({});
const model_name = ref("");
const is_llmjudge = ref(false);
const datasetStore = useDatasetStore();
const options = ref([]);
const subsetOptions = ref([]);
const page = ref(50);


const isinterpretation = computed(() =>
  computeIsInterpretation(assessmentType.value)
);

const isChildStudy = computed(() => {
  // console.log("tas123k");
  // console.log(task.value);
  if (!task.value?.datasets || task.value.datasets.length === 0) {
    // if (
    //   task.value?.task_dataset &&
    //   task.value?.task_dataset.includes("儿童伴学")
    // ) {
    //   return true;
    // }
    return false;
  }

  for (const datasetId of task.value.datasets) {
    const dataset = datasets.value[datasetId];
    if (!dataset || !dataset.testcase_tags.includes("儿童伴读")) {
      return false;
    }
  }
  return true;
});



const isRuler2 = computed(() => {
  return (
    checkAllDatasetsTag(task.value, datasets.value, "意图") ||
    checkAllDatasetsTag(task.value, datasets.value, "记忆") ||
    checkAllDatasetsTag(task.value, datasets.value, "改写") ||
    checkAllDatasetsTag(task.value, datasets.value, "skill提参") ||
    checkAllDatasetsTag(task.value, datasets.value, "GUI提参") ||
    checkAllDatasetsTag(task.value, datasets.value, "伴学提参") ||
    checkAllDatasetsTag(task.value, datasets.value, "Coordinator")
  );
});


watch(selectValue, (newVal) => {
  if (newVal === "live_code_bench") {
    page.value = 10;
  } else {
    page.value = 52;
  }
});

const asyncScoreClick = async () => {
  ElMessageBox.confirm(
    "同步分数用于在手动修改结果后重新计算分数，可以在修改完多个结果后再同步分数。同步分数较慢请耐心等待。(只有在同步分数后修改的结果才会生效)",
    "提示",
    {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning",
    }
  ).then(async () => {
    const loading = ElLoading.service({
      lock: true,
      text: "卖力加载中...",
    });
    await asyncScore({
      task_id: task_id.value,
      dataset: selectValue.value,
      sub_dataset: selectSubValue.value,
    })
      .then((res) => {
        ElMessage({
          type: "success",
          message: "同步成功！",
        });
      })
      .catch((err) => {
        ElMessage({
          type: "error",
          message: "同步失败！暂时没有需要同步的数据",
        });
      });
    loading.close();
  });
};


const filepath = ref([]);

const clickDownload = () => {};

const clickDownloadAll = () => {
  // downloadFile;
  ElMessage({
    type: "info",
    message: "暂未实现: ",
  });
};

const scene = ref("");

const dataChange = async () => {
  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });
  setScene();
  let isMos = false;
  if (selectValue.value === "MOS") {
    isMos = true;
    selectValue.value = task_id.value.replace("_", "");
  }
  await getResult({
    task_id: task_id.value,
    model_id: currentModelID.value,
    page: `${1},${page.value}`,
    dataset: isMos ? selectValue.value.replace("_", "") : selectValue.value,
    assessmentType: scene.value,
  }).then((res) => {
    loading.close();
    try {
      if (res.data.result.length < 1) {
        ElMessage({
          type: "error",
          message: "暂无数据",
        });
        return;
      }
    } catch {
      ElMessage({
        type: "error",
        message: "暂无数据",
      });
      return;
    }
    // ElMessage({
    //   type: "success",
    //   message: "更新成功",
    // });
    Result.value = res.data.result;
    subsetOptions.value = res.data.subset;
    selectSubValue.value = res.data.subset[0];
    filepath.value = res.data.files;
  });
  if (isMos) {
    selectValue.value = "MOS";
  }

  loading.close();
};

const currentModelID = ref("");

const setScene = () => {
  const datasetLists = selectValue.value.split("/");
  if (datasetLists[2] && datasetLists[2].includes("xlsx")) {
    scene.value = "MT";
    if (assessmentType.value.includes("ASR+MT")) {
      currentModelID.value = task.value.model_id.split(";")[1];
    } else if (assessmentType.value === "MT") {
      currentModelID.value = task.value.model_id;
    }
  } else if (datasetLists[3]) {
    scene.value = "ASR";
    currentModelID.value = task.value.model_id.split(";")[0];
  } else if (datasetLists[2] || datasetLists[0] === "MOS") {
    scene.value = "TTS";
    currentModelID.value = task.value.model_id.split(";")[2];
  } else {
    // console.log("不是同声传译");
    currentModelID.value = task.value.model_id;
    loadSubsetsData();
  }
};

const subChange = async () => {
  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });
  await getResult({
    task_id: task_id.value,
    page: `${1},${page.value}`,
    dataset: selectValue.value,
    model_id: currentModelID.value,
    subset: selectSubValue.value,
    assessmentType: scene.value,
  }).then((res) => {
    loading.close();
    try {
      if (res.data.result.length < 1) {
        ElMessage({
          type: "error",
          message: "暂无数据",
        });
        return;
      }
    } catch {
      ElMessage({
        type: "error",
        message: "暂无数据",
      });
      return;
    }
    // ElMessage({
    //   type: "success",
    //   message: "更新成功",
    // });
    Result.value = res.data.result;
    subsetOptions.value = res.data.subset;
    filepath.value = res.data.files;
  });
  loading.close();
};





const assessmentType = ref(route.query.assessmentType);


const drawer = ref(false);
const localTableData = ref([]);
const tableInfo = ref([]);

// 改写业务：report 子集带 loose_score（宽松准确率）时，抽屉表格同时展示严格/宽松两套准确率
const hasLooseScoreData = computed(() => {
  return localTableData.value.some(
    (item) =>
      item.looseScore !== undefined &&
      item.looseScore !== null &&
      item.looseScore !== ""
  );
});

// 改写业务：表格底部展示"总计"行，测试集子集数量求和，严格/宽松准确率按子集数量加权平均
const isRewriteBusiness = computed(() =>
  checkAllDatasetsTag(task.value, datasets.value, "改写")
);

const tableSummary = ({ columns, data }) => {
  const totalNum = data.reduce(
    (sum, item) => sum + (Number(item.num) || 0),
    0
  );
  const weightedScore = totalNum
    ? data.reduce(
        (sum, item) =>
          sum + (Number(item.score) || 0) * (Number(item.num) || 0),
        0
      ) / totalNum
    : 0;
  const weightedLooseScore = totalNum
    ? data.reduce(
        (sum, item) =>
          sum + (Number(item.looseScore) || 0) * (Number(item.num) || 0),
        0
      ) / totalNum
    : 0;
  return columns.map((col, index) => {
    if (index === 1) {
      return "总计";
    }
    switch (col.property) {
      case "num":
        return totalNum;
      case "score":
        return (weightedScore * 100).toFixed(2);
      case "looseScore":
        return (weightedLooseScore * 100).toFixed(2);
      default:
        return "";
    }
  });
};

const loadSubsetsData = async () => {
  const data = task.value.result;
  console.log("data");
  console.log(data);
  localTableData.value = [];
  if (!model_name.value.includes(";") && data[model_name.value]) {
    data[model_name.value].forEach((model) => {
      if (Array.isArray(model.metrics)) {
        model.metrics.forEach((metric) => {
          metric.categories.forEach((category) => {
            if (category.subsets) {
              category.subsets.forEach((subset) => {
                localTableData.value.push({
                  datasetName: model.dataset_name,
                  subsetName: subset.name,
                  score: subset.score,
                  looseScore: subset.loose_score,
                  time: subset.time,
                  num: subset.num,
                });
              });
            }
          });
        });
      } else {
        // console.log("mertrics压根不是数组！！！");
      }
    });
  }
  localTableData.value = localTableData.value.filter(
    (item) => item.datasetName === selectValue.value
  );
  console.log("localTableData");
  console.log(localTableData.value);

  if (isinterpretation.value) {
    loadInterpretationData(task.value);
  }
};

const loadInterpretationData = (task) => {
  const data = task.result;
  const oneTask = [];
  oneTask.push({
    id: 0,
    scene: assessmentType.value,
    language:
      assessmentType.value === "MT" || assessmentType.value === "ASR+MT"
        ? task.taskConfig.language
        : "",
    model_name: model_name.value,
    time: task.createTime,
    directoryD: "全集",
    average:
      assessmentType.value === "MT"
        ? (data[model_name.value][0].score * 100).toFixed(2)
        : "",
  });
  const rowHeaders = [
    "8k+10db",
    "16k+10db",
    "8k_0db",
    "16k_0db",
    "方言",
    "关键词",
    "关键词",
  ];

  if (assessmentType.value === "ASR") {
    rowHeaders.forEach((head, index) => {
      const match = {};
      let sum = 0;
      let num = 0;
      data[model_name.value].forEach((item) => {
        // console.log('match');
        // console.log(item.dataset_name.match(/(.*?\/.*?\/.*?\/)(.*)/));
        const directories = item.dataset_name.split("/");
        if (directories.length > 3 && directories[3].includes(head)) {
          //TODO后续改为全等于head
          match[directories[2]] = item.score * 100;
          if (item.score || item.score === 0) {
            num++;
            sum += item.score;
          }
        }
      });
      if (index !== 5) {
        oneTask.push({
          id: index,
          scene: assessmentType.value,
          // language: info.taskConfig.language,
          model_name: model_name.value,
          time: task.createTime,
          directoryD: head,
          average: num !== 0 ? (sum / num) * 100 : "-",
          ...match,
        });
      } else {
        oneTask.push({
          id: index,
          scene: assessmentType.value,
          model_name: model_name.value,
          time: task.createTime,
          directoryD: head,
          average: "平均值",
          Restaurant: "Airport",
          Hotel: "Area name",
          Taxi: "Attractions",
          Airport: "Metro Station name",
          Clinic: "Main festivals and events",
          TourismInformation: "Food and dish",
          Emergencies: "Bus Station name",
          SpokenLanguages: "Country and Capital",
        });
      }
    });
  } else if (assessmentType.value === "MT") {
    oneTask.push({
      id: 1,
      scene: assessmentType.value,
      language:
        assessmentType.value === "MT" || assessmentType.value === "ASR+MT"
          ? task.taskConfig.language
          : "",
      model_name: model_name.value,
      time: task.createTime,
      directoryD: "关键词",
      average: "平均值",
      Restaurant: "Airport",
      Hotel: "Area name",
      Taxi: "Attractions",
      Airport: "Metro Station name",
      Clinic: "Main festivals and events",
      TourismInformation: "Food and dish",
      Emergencies: "Bus Station name",
      SpokenLanguages: "Country and Capital",
    });
    oneTask.push({
      id: 2,
      scene: assessmentType.value,
      language:
        assessmentType.value === "MT" || assessmentType.value === "ASR+MT"
          ? task.taskConfig.language
          : "",
      model_name: model_name.value,
      time: task.createTime,
      directoryD: "关键词",
    });
  } else if (assessmentType.value === "TTS") {
    //TODO测评结果TTS
  }
  tableInfo.value = oneTask;

  // console.log("Result");
  // console.log(Result.value);
};






const goBack = () => {
  // router.push("/modelEvaluation/onlineAssessment");
  router.back();
};





onMounted(async () => {
  task_id.value = route.query.taskId;
  const response = await getList();
  task.value = response.data.find((item) => item.ID === task_id.value);
  if (task.value) {
    if (route.query.model_name) {
      model_name.value = route.query.model_name;
    } else {
      model_name.value = task.value.model_name;
    }
  } else {
    const res = await getEvaluationResult();
    // 如果 res.data 是对象，则提取值为数组；如果是数组，保持不变
    const resultData = Array.isArray(res.data)
      ? res.data
      : Object.values(res.data);
    // console.log("resultData");
    // console.log(resultData);
    task.value = resultData.filter((item) => item.task_id === task_id.value)[0];
  }
  console.log("task");
  console.log(task.value);

  // 从evaluationResult跳转时，携带单个dataset和score
  if (route.query.dataset) {
    singleDataset.value = route.query.dataset;
    singleScore.value = parseFloat(route.query.score) || 0;
    // 改写业务：从 report 数据中同步读取该测试集的宽松准确率
    const modelRes = task.value?.result?.[model_name.value];
    const matchItem = (Array.isArray(modelRes) ? modelRes : []).find(
      (i) => i.dataset_name === singleDataset.value
    );
    const looseVal = matchItem?.loose_score ?? matchItem?.looseScore;
    singleLooseScore.value =
      looseVal === undefined || looseVal === null || looseVal === ""
        ? 0
        : parseFloat(looseVal) || 0;
    options.value = [singleDataset.value];
    selectValue.value = singleDataset.value;
  } else {
    const query_dataset = JSON.parse(route.query.datasets);
    if (query_dataset.length !== 0) {
      if (assessmentType.value === "ASR+MT+TTS") {
        options.value = [...query_dataset, "MOS"];
      } else {
        options.value = [...query_dataset];
      }
      selectValue.value = query_dataset[0];
    }
  }
  // Result.value = resp.value;
  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });
  setScene();
  currentModelID.value =
    !currentModelID.value || currentModelID.value === ""
      ? task.value.model_id
      : currentModelID.value;
  console.log("currentModelID");
  console.log(currentModelID.value);
  // 先加载 datasets，确保 isYitu/isChildStudy computed 能正确计算
  if (assessmentType.value === "通用评估(Ruler1)") {
    if (
      JSON.stringify(datasetStore.getDatasets("ruler1")) !== "{}" &&
      JSON.stringify(datasetStore.getDatasets("ruler1")) !== undefined
    ) {
      datasets.value = datasetStore.getDatasets("ruler1");
    } else {
      await get_datasets("1").then((res) => {
        datasets.value = res.data;
        datasetStore.setDatasets("ruler1", res.data);
      });
    }
  } else if (assessmentType.value === "领域评估(Ruler2)") {
    if (
      JSON.stringify(datasetStore.getDatasets("ruler2")) !== "{}" &&
      JSON.stringify(datasetStore.getDatasets("ruler2")) !== undefined
    ) {
      datasets.value = datasetStore.getDatasets("ruler2");
    } else {
      await get_datasets("2").then((res) => {
        datasets.value = res.data;
        datasetStore.setDatasets("ruler2", res.data);
      });
    }
  }

  await getResult({
    task_id: task_id.value,
    model_id: currentModelID.value,
    page: `${1},${page.value}`,
    dataset: selectValue.value,
    assessmentType: scene.value,
  }).then((res) => {
    console.log("原始响应:", res.data);
    console.log("result 类型:", typeof res.data);
    console.log("result 值:", res.data.result);
    let resultData = res.data;
    if (typeof resultData === "string") {
      try {
        resultData = JSON.parse(resultData);
      } catch (e) {
        console.error("JSON 解析失败:", e);
        throw new Error("数据格式错误");
      }
    }
    console.log("解析后:", resultData);
    if (res.data.result.length < 1) {
      ElMessage({
        type: "error",
        message: "暂无数据",
      });
      loading.close();
      return;
    }
    // ElMessage({
    //   type: "success",
    //   message: "更新成功",
    // });
    Result.value = res.data.result;
    subsetOptions.value = res.data.subset;
    selectSubValue.value = res.data.subset[0];
    filepath.value = res.data.files;
    // if (isChildStudy.value) {
    //   getStatisticsData();
    // }
  });
  loading.close();
  loadSubsetsData();

  if (
    selectValue.value &&
    datasets.value[selectValue.value] &&
    datasets.value[selectValue.value].need_llmjudge
  ) {
    is_llmjudge.value = datasets.value[selectValue.value].need_llmjudge;
  }
  // loadInterpretationResult();

  activeTab.value = isChildStudy.value ? "first" : "second";
});
</script>

<style scoped>
.main {
  display: flex;
  /* justify-content: center; */
  height: 100%;
  background-color: #ffffff;
  margin-left: 20px;
  padding-right: 0;
  padding-bottom: 0;
  border-radius: 8px;
  overflow: auto;
  gap: 0;
}

.title {
  /* height: 50px; */
  /* margin-top: 50px; */
  /* margin-right: 50px; */
}

.qestion_card {
  /* height: 100px; */
  width: 100%;
  resize: vertical;
  background-color: #f4f3f9;
  overflow: auto;
}

.screening {
  /* margin-left: 10px; */
  /* height: 100vh; */
  /* padding-top: 20px; */
  background-color: #fff;
  border-radius: 5px;
  box-shadow: 0px 0px 8px rgba(158, 158, 158, 0.3);
}

.selectOrder {
  width: 50%;
  /* margin-left: 2%; */
  box-sizing: border-box;
}

.el-main {
  margin-left: auto;
  align-self: flex-start;
  /* margin-right: 20px; */
  padding-top: 0px;
  gap: 1rem;
  flex-wrap: wrap;
}

.dataContainer {
  background-color: #f5f5f5;
  width: 100%;
  height: calc(100vh - 80px);
  /* display: flex; */
  /* padding: 20px; */
  max-width: 100%;
  /* padding: 0 20px; */
  gap: 12px;
  position: relative;
  flex-direction: row;
}

.head_card {
  display: flex;
  align-items: center;
  width: 98%;
  min-height: 60px;
  border-radius: 8px;
  background: rgb(255, 255, 255);
  padding: 5px 0px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  /* border-radius: 4px; */
  margin-top: 10px;
  margin-left: 1%;
}

.dataCardContainer {
  /* background-color: #ffffff; */
  /* padding: 5px 0px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06); */
  /* border-radius: 4px; */
  /* margin-top: 10px; */
  height: calc(100vh - 310px);
  margin: 10px 20px 0;
  display: flex;
}

.el-card {
  border-radius: 8px;
}

.el-link :deep(.el-link__inner) {
  display: block;
}

.questionCardButtom {
  width: 80px;
  height: 30px;
}

.button_success_color {
  background-color: rgb(160, 207, 255);
}

.buttom_error_color {
  background-color: rgb(250, 182, 182);
}

.buttom_undefine_color {
  background-color: #909399;
  color: #ffffff;
}

.questionCard {
  margin: 10px 0;
  /* width: 200px */
}

.ButtomCard {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.questionButtomTag {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.highlight {
  /* border: 0.5px solid #2125fdff; #78a0ffff */
  box-shadow: 0 0 5px 5px #78a0ffff;
  transition: all 0.3s ease;
}

.tabsContainer {
  height: calc(100% - 40px);
}

.tabsContainer :deep(.el-tabs__header) {
  margin: 0;
}

.taskDetailTitleContainer {
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 40px;
  height: 40px;
  /* margin-bottom: 18px; */
}

.turnTitle {
  margin-top: 20px;
  font-weight: 700;
  color: rgb(115, 118, 122);
}

.lowAccuracyColor {
  background-color: rgb(250, 182, 182);
}

.middleAccuracyColor {
  background-color: rgb(160, 207, 255);
}

.highAccuracyColor {
  background-color: rgb(179, 225, 157);
}

.asideContainer :deep(.el-scrollbar__view) {
  height: 100%;
}

/* 例如：让图片容器不填满父容器 */
/* 使用深度选择器 */
.preview-image :deep(.el-image__inner) {
  /* 你的自定义样式 */
  max-height: 300px !important;
  width: auto;
  height: auto;
}

.main :deep(.el-textarea) {
  display: block;
  margin-right: 20px;
  width: calc(100% - 20px);
}

.tabsContainer :deep(.el-tabs__header) {
  margin-left: 20px;
}

.tablesContainer {
  width: 98%;
  height: calc(100vh - 170px);
  border-radius: 8px;
  background: rgb(255, 255, 255);
  padding: 5px 0 0 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  margin-top: 10px;
  /* margin-left: 1%; */
  overflow: auto;
}

.stasticsTableTitle {
  margin: 10px;
  font-size: 18px;
  font-weight: 600;
}

.statisticsChildeTitle {
  margin: 10px;
  font-size: 16px;
}

.statisticTable {
  max-height: calc(100% - 20px);
  width: 50%;
  overflow: auto;
}

.stasticsAnchorList {
  width: 12%;
  margin-top: 10px;
  margin-left: 1%;
  border-radius: 8px;
  background-color: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.anchor-nav {
  margin-left: 10px;
  padding-left: 20px;
}

.returnicon {
  top: 5px;
}

.gaixie-flex {
  display: flex;
  gap: 16px;
}

.gaixie-anchor {
  width: 11%;
  min-width: 120px;
  /* margin-top: 28px; */
  border-right: 1px solid #dcdfe6;
}

.gaixie-rounds {
  flex: 1;
  min-width: 0;
}

.gaixie-anchor :deep(.el-anchor__item) {
  margin-bottom: 4px;
}

.gaixie-anchor :deep(.el-anchor__link) {
  font-size: 13px;
  padding: 4px 8px;
  white-space: nowrap;
}
</style>

