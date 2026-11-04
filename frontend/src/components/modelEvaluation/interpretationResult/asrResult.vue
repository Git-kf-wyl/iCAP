<template>
  <div>
    <el-table :header-cell-style="tableHeaderStyle" align="center" class="hide-empty-table">
      <el-table-column prop="scene" label="服务" width="180" />
      <el-table-column prop="model_name" label="模型" />
      <el-table-column prop="time" label="时间" />
      <el-table-column prop="directoryD" label="语料" />
      <el-table-column prop="average" label="平均值" />
      <el-table-column label="场景(准确率/精确率，关键错误)">
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
        <div v-for="(tableInfo) in asrRawTableData" :key="tableInfo.id">
          <el-table
            :data="tableInfo"
            :span-method="asrObjectSpanMethod"
            border
            class="interpretationDetailTable"
            stripe
            :header-cell-style="tableHeaderStyle"
            :cell-style="asrCellStyle"
            align="center"
            :show-header="false"
          >
            <el-table-column prop="scene" label="服务" width="180" />
            <el-table-column prop="model_name" label="模型" />
            <el-table-column prop="time" label="时间" />
            <el-table-column prop="directoryD" label="语料" />
            <el-table-column prop="average" label="平均值" />
            <el-table-column label="场景(准确率/精确率，关键错误)">
              <el-table-column prop="Restaurant" label="Restaurant" />
              <el-table-column prop="Hotel" label="Hotel" />
              <el-table-column prop="Taxi" label="Taxi" />
              <el-table-column prop="Airport" label="Airport" />
              <el-table-column prop="Clinic" label="Clinic" />
              <el-table-column prop="Tourism_information" label="Tourism information" />
              <el-table-column prop="Emergencies" label="Emergencies" />
              <el-table-column prop="Spoken_languages" label="Spoken languages" />
              <el-table-column prop="Business_negotiation" label="Business negotiation" />
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

const asrCellStyle = ({ row, column, rowIndex, columnIndex }) => {
  // 根据行索引和列索引设置样式
  // if (rowIndex === 6 && columnIndex > 3) {
  //   return {
  //     ...tableHeaderStyle,
  //     fontWeight: "600",
  //   };
  // }
  // return {
  //   textAlign: "center",
  // };
  if (row.id === 5 && columnIndex > 3) {
    return {
      ...tableHeaderStyle,
      fontWeight: "600",
    };
  }
  return {
    textAlign: "center",
  };
};

const asrObjectSpanMethod = ({
  row,
  column,
  rowIndex,
  columnIndex,
}: SpanMethodProps) => {
  if (columnIndex === 0 || columnIndex === 1 || columnIndex === 2) {
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
  } else if (columnIndex === 3) {
    if (row.id === 5) {
      return {
        rowspan: 2,
        colspan: 1,
      };
    } else if (row.id === 6) {
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

const rowHeaders = ["8k_10dB", "16k_10dB", "8k_0dB", "16k_0dB", "方言"];
const asrRawTableData = ref([]);
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
  let data = resData.filter((item) => item.assessmentType === "ASR");
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

      let fullSum = 0;
      let fullNum = 0;
      let datasetName = "";
      let allScore = 0;
      info.result[info.model_name].forEach((item) => {
        if ((item.score || item.score === 0) && item.dataset_name !== "all") {
          fullNum++;
          fullSum += item.score;
          // console.log("item.dataset_name.split()");
          // console.log(item.dataset_name.split("/"));

          let scene = item.dataset_name.split("/")[2]
            ? item.dataset_name.split("/")[3]
            : "";
          datasetName = item.dataset_name.split("/")[1];
          // console.log("datasetName");
          // console.log(datasetName);
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
        } else if (item.dataset_name === "all") {
          // console.log("item");
          // console.log(item);
          allScore = (item.score * 100).toFixed(2);
        }
      });
      let fullAverage = (fullSum / fullNum) * 100;
      // console.log("dataSetScore");
      // console.log(dataSetScore);
      // console.log("datasetName");
      // console.log(datasetName);

      if (!datasetName.includes("关键词")) {
        oneTask.push({
          id: 0,
          scene: "ASR",
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "全集",
          // average: fullAverage ? fullAverage.toFixed(2) : "-",
          average: allScore,
        });
        rowHeaders.forEach((head, index) => {
          const match = {};
          let sum = 0;
          let num = 0;
          info.result[info.model_name].forEach((item) => {
            if (item.dataset_name !== "all") {
              // console.log('match');
              // console.log(item.dataset_name.match(/(.*?\/.*?\/.*?\/)(.*)/));
              const directories = item.dataset_name.split("/");
              if (directories[3].includes(head)) {
                //TODO后续改为全等于head
              // console.log('match');
              // console.log(directories[2]);
                match[directories[2]] = (item.score * 100).toFixed(2);
                if (item.score || item.score === 0) {
                  num++;
                  sum += item.score;
                }
              }
            }
          });
          // console.log('match');
          // console.log(match);
          const avg = (sum / num) * 100;
          fullAverage += avg;
          if (index !== 5) {
            oneTask.push({
              id: index,
              scene: "ASR",
              model_name: info.model_name,
              time: info.createTime,
              directoryD: head,
              average: avg ? avg.toFixed(2) : "-",
              ...match,
            });
          } else {
            oneTask.push({
              id: index,
              scene: "ASR",
              model_name: info.model_name,
              time: info.createTime,
              directoryD: head,
              average: "平均值",
              Restaurant: "Airport",
              Hotel: "Area name",
              Taxi: "Attractions",
              Airport: "Metro Station name",
              Clinic: "Main festivals and events",
              Tourism_information: "Food and dish",
              Emergencies: "Bus Station name",
              Spoken_languages: "Country and Capital",
            });
          }
        });
      } else {
        // console.log("info");
        // console.log(info);
        oneTask.push({
          id: 5,
          scene: "ASR",
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "关键词",
          average: "平均值",
          Restaurant: "Airport",
          Hotel: "Area name",
          Taxi: "Attractions",
          Airport: "Metro Station name",
          Clinic: "Main festivals and events",
          Tourism_information: "Food and dish",
          Emergencies: "Bus Station name",
          Spoken_languages: "Country and Capital",
        });
        const tempObj = {
          id: 6,
          scene: "ASR",
          model_name: info.model_name,
          time: info.createTime,
          directoryD: "关键词",
          average: "-",
          Restaurant: "-",
          Hotel: "-",
          Taxi: "-",
          Airport: "-",
          Clinic: "-",
          Tourism_information: "-",
          Emergencies: "-",
          Spoken_languages: "-",
        };
        info.result[info.model_name].forEach((item) => {
          const tempScore = (item.score * 100).toFixed(2);
          if (item.dataset_name !== "all") {
            let scene = item.dataset_name.split("/")[2];
            switch (scene) {
              case "Airport":
                tempObj.Restaurant = tempScore;
                break;
              case "Area_name":
                tempObj.Hotel = tempScore;
                break;
              case "Attractions":
                tempObj.Taxi = tempScore;
                break;
              case "Bus_Station_name":
                tempObj.Emergencies = tempScore;
                break;
              case "Country_and_Capital":
                tempObj.Spoken_languages = tempScore;
                break;
              case "Food_and_dish":
                tempObj.Tourism_information = tempScore;
                break;
              case "Main_festivals_and_events":
                tempObj.Clinic = tempScore;
                break;
              case "Metro_Station_name":
                tempObj.Airport = tempScore;
                break;
            }
          }else{
            tempObj.average = tempScore;
          }
        });
        oneTask.push(tempObj);
      }
      // console.log('oneTask')
      // console.log(oneTask)
      asrRawTableData.value.push(oneTask);
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