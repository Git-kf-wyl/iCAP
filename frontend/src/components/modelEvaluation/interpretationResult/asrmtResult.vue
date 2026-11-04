<template>
  <div>
    <el-table :header-cell-style="tableHeaderStyle" align="center" class="hide-empty-table">
      <el-table-column prop="scene" label="服务" width="180" />
      <el-table-column prop="language" label="语言" width="100" />
      <el-table-column prop="model_name" label="模型" />
      <el-table-column prop="time" label="时间" />
      <el-table-column prop="directoryD" label="语料" />
      <el-table-column prop="average" label="平均值" />
      <el-table-column label="场景(BLEU/COMET)">
        <el-table-column prop="Restaurant" label="Restaurant" />
        <el-table-column prop="Hotel" label="Hotel" />
        <el-table-column prop="Taxi" label="Taxi" />
        <el-table-column prop="Airport" label="Airport" />
        <el-table-column prop="Clinic" label="Clinic" />
        <el-table-column prop="TourismInformation" label="Tourism information" />
        <el-table-column prop="Emergencies" label="Emergencies" />
        <el-table-column prop="SpokenLanguages" label="Spoken languages" />
        <el-table-column prop="BusinessNegotiation" label="Business negotiation" />
        <el-table-column prop="Shopping" label="Shopping" />
      </el-table-column>
    </el-table>
    <el-container class="dataCardContainer" v-loading="loading">
      <el-scrollbar>
        <div v-for="(tableInfo) in mtRawData" :key="tableInfo.id">
          <el-table
            :data="tableInfo"
            :span-method="asrmtObjectSpanMethod"
            border
            class="interpretationDetailTable"
            stripe
            :header-cell-style="tableHeaderStyle"
            :cell-style="asrmtCellStyle"
            align="center"
            :show-header="false"
          >
            <el-table-column prop="scene" label="服务" width="180" />
            <el-table-column prop="language" label="语言" width="100" />
            <el-table-column prop="model_name" label="模型" />
            <el-table-column prop="time" label="时间" />
            <el-table-column prop="directoryD" label="语料" />
            <el-table-column prop="average" label="平均值" />
            <el-table-column label="场景(BLEU/COMET)">
              <el-table-column prop="Restaurant" label="Restaurant" />
              <el-table-column prop="Hotel" label="Hotel" />
              <el-table-column prop="Taxi" label="Taxi" />
              <el-table-column prop="Airport" label="Airport" />
              <el-table-column prop="Clinic" label="Clinic" />
              <el-table-column prop="TourismInformation" label="Tourism information" />
              <el-table-column prop="Emergencies" label="Emergencies" />
              <el-table-column prop="SpokenLanguages" label="Spoken languages" />
              <el-table-column prop="BusinessNegotiation" label="Business negotiation" />
              <el-table-column prop="Shopping" label="Shopping" />
            </el-table-column>
          </el-table>
        </div>
      </el-scrollbar>
    </el-container>
  </div>
</template>
  
  <script lang="ts" setup>
import { ref, onMounted } from "vue";
import { getList } from "@/api/runService.js";
import { useTaskStore } from "@/stores/taskStore.js";

const props = defineProps({
  task_id: {
    type: String,
  },
});

const taskStore = useTaskStore();

const tableHeaderStyle = {
  textAlign: "center",
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
};

const asrmtCellStyle = ({ row, column, rowIndex, columnIndex }) => {
  // 根据行索引和列索引设置样式
  if (rowIndex === 1 && columnIndex > 4) {
    return {
      ...tableHeaderStyle,
      fontWeight: "600",
    };
  }
  return {
    textAlign: "center",
  };
};

const asrmtObjectSpanMethod = ({
  row,
  column,
  rowIndex,
  columnIndex,
}: SpanMethodProps) => {
  if (columnIndex <= 3) {
    if (rowIndex === 0) {
      return {
        rowspan: 8,
        colspan: 1,
      };
    } else {
      return {
        rowspan: 0,
        colspan: 0,
      };
    }
  } else if (columnIndex === 4) {
    if (rowIndex === 6) {
      return {
        rowspan: 2,
        colspan: 1,
      };
    } else if (rowIndex === 7) {
      return {
        rowspan: 0,
        colspan: 0,
      };
    } else {
      return {
        rowspan: 1,
        colspan: 1,
      };
    }
  }
};

const rowHeaders = [
  "8k+10db",
  "16k+10db",
  "8k_0db",
  "16k_0db",
  "方言",
  "关键词",
  "关键词",
];
const asrRawTableData = ref([]);
const loading = ref(true);
const mtRawData = ref([]);

const loadData = () => {
  if (taskStore.getTasks && taskStore.getTasks.length > 0) {
    // console.log("taskStore.getTasks");
    // console.log(taskStore.getTasks);
    getTaskInfo(taskStore.getTasks);
  } else {
    getList().then((res) => {
      getTaskInfo(res.data);
      taskStore.setTasks(res.data);
    });
  }
};

const getTaskInfo = (resData) => {
  let data = resData.filter((item) => item.assessmentType === "ASR+MT");
  if (props.task_id) {
    // console.log("接收到task_id");
    // console.log(props.task_id);
    // console.log("data111:");
    // console.log(data.find((item) => item.ID === props.task_id));
    data = [data.find((item) => item.ID === props.task_id)];
  }
  // console.log("data:");
  // console.log(data);

  data.forEach((info) => {
    if (info.status === "completed") {
      const oneTask = [];

      let sum = 0;
      let num = 0;
      const dataSetScore = {};

      const getSceneScore = (sceneName) => {
        const keys = Object.keys(dataSetScore);
        const matchedKey = keys.find((key) => key.includes(sceneName));
        return matchedKey ? dataSetScore[matchedKey] : "";
      };

      let datasetName = "";
      info.result[info.model_name.split(";")[1]].forEach((item) => {
        sum += item.score;
        num++;

        let scene = item.dataset_name.split("/")[3]
          ? item.dataset_name.split("/")[3]
          : "";
        datasetName = item.dataset_name.split("/")[2];
        scene = scene.includes(" ")
          ? scene
              .split(" ")
              .map((word, index) => {
                if (index === 0) {
                  return word;
                }
                return (
                  word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
                );
              })
              .join("")
          : scene;
        // console.log(scene);
        dataSetScore[scene] = (item.score * 100).toFixed(2);
      });
      const avg = sum / num;

      if (datasetName.includes("关键词")) {
        oneTask.push({
          id: 0,
          scene: "ASR+MT",
          language: info.taskConfig.language,
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "全集",
          average: "-",
        });
      } else {
        const sceneScore = {
          Restaurant: getSceneScore("Restaurant"),
          Hotel: getSceneScore("Hotel"),
          Taxi: getSceneScore("Taxi"),
          Airport: getSceneScore("Airport"),
          Clinic: getSceneScore("Clinic"),
          TourismInformation: getSceneScore("TourismInformation"),
          Emergencies: getSceneScore("Emergencies"),
          SpokenLanguages: getSceneScore("SpokenLanguages"),
          BusinessNegotiation: getSceneScore("BusinessNegotiation"),
          Shopping: getSceneScore("Shopping"),
        };

        oneTask.push({
          id: 0,
          scene: "ASR+MT",
          language: info.taskConfig.language,
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "全集",
          average: (avg * 100).toFixed(2),
          ...sceneScore,
        });
      }

      oneTask.push({
        id: 1,
        scene: "ASR+MT",
        language: info.taskConfig.language,
        model_name: info.model_name,
        time: info.createTime,
        average: "平均值",
        directoryD: "关键词",
        Restaurant: "Airport",
        Hotel: "Area name",
        Taxi: "Attractions",
        Airport: "Metro Station name",
        Clinic: "Main festivals and events",
        TourismInformation: "Food and dish",
        Emergencies: "Bus Station name",
        SpokenLanguages: "Country and Capital",
      });

      if (datasetName.includes("关键词")) {
        oneTask.push({
          id: 2,
          scene: "ASR+MT",
          language: info.taskConfig.language,
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "关键词",
          average: (avg * 100).toFixed(2),
          Restaurant: getSceneScore("Airport"),
          Hotel: getSceneScore("AreaName"),
          Taxi: getSceneScore("Attractions"),
          Airport: getSceneScore("MetroStationName"),
          Clinic: getSceneScore("MainFestivalAndEvents"),
          TourismInformation: getSceneScore("FoodAndDish"),
          Emergencies: getSceneScore("BusStationName"),
          SpokenLanguages: getSceneScore("CountryAndCapital"),
        });
      } else {
        oneTask.push({
          id: 2,
          scene: "ASR+MT",
          language: info.taskConfig.language,
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "关键词",
          average: "-",
        });
      }
      mtRawData.value.push(oneTask);
    }
  });
  loading.value = false;
};

onMounted(async () => {
  loadData();
});
</script>
  
  <style scoped>
.dataCardContainer {
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
  margin: 0 20px;
  /* border-radius: 8px; */
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  height: calc(100vh - 300px);
  overflow: auto;
}

.hide-empty-table {
  left: 20px;
  width: calc(100% - 40px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

/* 隐藏空状态行 */
.hide-empty-table :deep(.el-table__body-wrapper) {
  display: none;
}
</style>