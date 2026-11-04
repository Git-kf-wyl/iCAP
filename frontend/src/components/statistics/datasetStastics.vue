<template>
  <div class="cardContainer">
    <div class="semiCardDontainer">
      <el-card shadow="never" class="basicCard" v-loading="loading">
        <div class="chart-wrapper">
          <div class="chart-title">通用测试集</div>
          <DatasetPieChart
            v-if="classifiedData1.length > 0"
            width="100%"
            height="100%"
            :data="classifiedData1"
            :title="'通用测试集'"
          ></DatasetPieChart>
        </div>
      </el-card>
      <el-card shadow="never" class="basicCard" v-loading="loading">
        <div class="chart-wrapper">
          <div class="chart-title">领域测试集</div>
          <DatasetPieChart
            v-if="classifiedData2.length > 0"
            width="100%"
            height="100%"
            :data="classifiedData2"
            :title="'领域测试集'"
          ></DatasetPieChart>
        </div>
      </el-card>
    </div>
    <div class="semiCardDontainer">
      <el-card shadow="never" class="basicCard" v-loading="loading">
        <div class="chart-wrapper">
          <div class="chart-title">开发态测试集</div>
          <DatasetPieChart
            v-if="classifiedData3.length > 0"
            width="100%"
            height="100%"
            :data="classifiedData3"
            :title="'开发态测试集'"
          ></DatasetPieChart>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, nextTick } from "vue";
import DatasetPieChart from "./charts/datasetPieChart.vue";
import { get_datasets } from "@/api/dataSetApi";

const loading = ref(true);

const rawData1 = ref();
const classifiedData1 = ref([]);
const rawData2 = ref();
const classifiedData2 = ref([]);
const rawData3 = ref();
const classifiedData3 = ref([]);

//处理数据分类
const classifyByTags = (data, targetData) => {
  // 遍历原始数据
  for (const dataset in data) {
    const tags = data[dataset].testcase_tags;
    const cases = data[dataset].dataSet_cases;

    // 遍历标签
    for (const tag of tags) {
      // 查找是否已存在该标签的分类
      let existingTag = targetData.find((item) => item.title === tag);

      if (existingTag) {
        // 如果存在，添加到已有的分类中
        existingTag.data.push({ dataset: dataset, cases: cases });
      } else {
        // 如果不存在，创建新的分类
        targetData.push({
          title: tag,
          data: [{ dataset: dataset, cases: cases }],
        });
      }
    }
  }
};

const loadDatasetData = async () => {
  const res1 = await get_datasets(1);
  rawData1.value = res1.data;
  classifiedData1.value = [];
  classifyByTags(rawData1.value, classifiedData1.value);

  const res2 = await get_datasets(2);
  rawData2.value = res2.data;
  classifiedData2.value = [];
  classifyByTags(rawData2.value, classifiedData2.value);

  const res3 = await get_datasets(3);
  rawData3.value = res3.data;
  classifiedData3.value = [];
  classifyByTags(rawData3.value, classifiedData3.value);

  loading.value = false;
};

onMounted(async () => {
  loadDatasetData();
});
</script>

<style scoped>
.cardContainer {
  display: flex;
  flex-direction: column;
  gap: 2%;
  height: calc(100vh - 110px);
  margin: 0;
}

.semiCardDontainer {
  display: flex;
  flex-direction: row;
  height: 49%;
  gap: 1%;
}

.basicCard {
  width: 49.5%;
}

.basicCard :deep(.el-card__body) {
  height: 100%;
  width: 100%;
  /* padding-top: 10px;
  padding-left: 10px; */
  padding: 0;
  position: relative;
}

.chart-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.chart-title {
  margin-left: 8px;
  padding: 8px;
  padding-bottom: 0;
  font-size: 16px;
  line-height: 16px;
  font-weight: 600;
  color: #333;
  z-index: -1;
}
</style>