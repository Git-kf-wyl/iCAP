<template>
  <div>
    <el-tabs v-model="activeName" class="tabs" @tab-click="handleClick">
      <el-tab-pane label="模型评估统计" name="first">
        <component v-if="activeName === 'first'" :is="EvaluationStastics" />
      </el-tab-pane>
      <!-- <el-tab-pane label="同声传译评估统计" name="second">
        <component v-if="activeName === 'second'" :is="EvaluationStastics" :evalType="evalType" />
      </el-tab-pane>-->
      <el-tab-pane label="测试集统计" name="third">
        <component v-if="activeName === 'third'" :is="DatasetStastics" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, nextTick } from "vue";
import { get_datasets } from "@/api/dataSetApi";
import EvaluationStastics from "./evaluationStastics.vue";
import DatasetStastics from "./datasetStastics.vue";
import type { TabsPaneContext } from "element-plus";

const activeName = ref("first");
const evalType = ref("all");

const handleClick = (tab: TabsPaneContext, event: Event) => {
  const name = tab.props.name;
  console.log("TabChange!");
  console.log(name);

  if (name === "second") {
    evalType.value = "interpretation";
  } else {
    evalType.value = "all";
  }
};
</script>

<style scoped>
.tabs {
  margin: 0 20px;
}

.tabs :deep(.el-tabs__header) {
  margin: 0 0 5px !important;
}
</style>
