<template>
  <div>
    <el-table :header-cell-style="tableHeaderStyle" align="center" class="hide-empty-table">
      <el-table-column prop="scene" label="服务" width="180" />
      <el-table-column prop="language" label="语言" />
      <el-table-column prop="model_name" label="模型" />
      <el-table-column prop="time" label="时间" />
      <el-table-column prop="directoryD" label="语料" />
      <el-table-column prop="value" label="值" />
    </el-table>
    <el-container class="dataCardContainer" v-loading="loading">
      <el-scrollbar>
        <div v-for="(tableInfo) in ttsRawTableData" :key="tableInfo.id">
          <el-table
            :data="tableInfo"
            :span-method="ttsObjectSpanMethod"
            border
            class="interpretationDetailTable"
            stripe
            :header-cell-style="tableHeaderStyle"
            :cell-style="ttsCellStyle"
            align="center"
            :show-header="false"
          >
            <el-table-column prop="scene" label="服务" width="180" />
            <el-table-column prop="language" label="语言" />
            <el-table-column prop="model_name" label="模型" />
            <el-table-column prop="time" label="时间" />
            <el-table-column prop="directoryD" label="语料" />
            <el-table-column prop="value" label="值" />
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

const ttsCellStyle = () => {
  return {
    textAlign: "center",
  };
};

// const ttsTableData = [
//   {
//     id: 0,
//     scene: "TTS",
//     language: "enar",
//     model_name: "同声传译模型01",
//     time: "2025-09-17 19:27:03",
//     directoryD: "字词准",
//     value: 100,
//   },
//   {
//     id: 1,
//     scene: "TTS",
//     language: "enar",
//     model_name: "同声传译模型01",
//     time: "2025-09-17 19:27:03",
//     directoryD: "归一化",
//     value: 100,
//   },
// ];

const ttsObjectSpanMethod = ({
  row,
  column,
  rowIndex,
  columnIndex,
}: SpanMethodProps) => {
  if (columnIndex <= 3) {
    if (rowIndex === 0) {
      return {
        rowspan: 3,
        colspan: 1,
      };
    } else {
      return {
        rowspan: 0,
        colspan: 0,
      };
    }
  }
};

const rowHeaders = [
  "8k+10dB",
  "16k+10dB",
  "8k_0dB",
  "16k_0dB",
  "方言",
  "关键词",
  "关键词",
];
const ttsRawTableData = ref([]);
const loading = ref(true);

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
  let data = resData.filter((item) => item.assessmentType === "TTS");
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
      // console.log("info");
      // console.log(info);
      const oneTask = [];

      const dataSetScore = {};

      const getSceneScore = (sceneName) => {
        const keys = Object.keys(dataSetScore);
        const matchedKey = keys.find((key) => key.includes(sceneName));
        return matchedKey ? dataSetScore[matchedKey] : "";
      };

      let language = [];
      let datasetName = "";
      info.result[info.model_name].forEach((item) => {
        datasetName = item.dataset_name.split("/")[2];
        let scene = datasetName ? datasetName : "";
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

        language.push(item.dataset_name.split("/")[1]);
      });

      // console.log("dataSetScore");
      // console.log(dataSetScore);

      oneTask.push({
        id: 0,
        scene: "TTS",
        language: language,
        model_name: info.model_name,
        time: info.createTime,
        directoryD: "字词准",
        value: getSceneScore("词准"),
      });
      oneTask.push({
        id: 1,
        scene: "TTS",
        language: language,
        model_name: info.model_name,
        time: info.createTime,
        directoryD: "归一化",
        value: getSceneScore("归一化"),
      });
      oneTask.push({
        id: 2,
        scene: "TTS",
        language: language,
        model_name: info.model_name,
        time: info.createTime,
        directoryD: "MOS",
        value: info.result[info.model_name][0].mos,
      });

      ttsRawTableData.value.push(oneTask);
    }
  });

  // console.log("ttsRawTableData");
  // console.log(ttsRawTableData.value);
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