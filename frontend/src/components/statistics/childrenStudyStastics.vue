<template>
  <ChildrenStudyTemplate />
</template>

<script lang="ts" setup>
import { onMounted, provide, computed,ref } from "vue";
import { ElLoading } from "element-plus";
import { useTaskSelection } from "@/composables/useTaskSelection";
import { useChildrenStudyData } from "@/composables/useChildrenStudyData";
import { useChildrenStudyCharts } from "@/composables/useChildrenStudyCharts";
import { useCellStyles } from "@/composables/useCellStyles";
import ChildrenStudyTemplate from "./childrenStudyTemplate.vue";

const props = defineProps({
  task_id: {
    type: String,
  },
  result: {
    type: Object,
  },
});
const emit = defineEmits(["update:modelValue"]);

// ====================================================================
// 1. 任务选择 + API 请求
// ====================================================================
const taskSelection = useTaskSelection(props, emit);

// ====================================================================
// 2. 数据处理（依赖 Result ref）
// ====================================================================
const studyData = useChildrenStudyData(
  taskSelection.Result,
  taskSelection.taskSubSet
);

// ====================================================================
// 3. 图表数据
// ====================================================================
const charts = useChildrenStudyCharts(
  studyData.accuracyTableData,
  studyData.statusTableData,
  studyData.costTimeTableData,
  studyData.sourceTableData,
  studyData.resolutionTableData,
  studyData.attentionTableData,
  studyData.distanceTableData,
  studyData.sittingTableData,
  null,
  null,
  null,
  null,
  taskSelection.preSelectedTasks
);

// ====================================================================
// 4. 单元格样式
// ====================================================================
const cellStyles = useCellStyles();

// 动态 sheet 名称列表（供模板遍历）
const dynamicSheetNames = computed(() => {
  const names = new Set<string>();
  studyData.dynamicSheetData.value.forEach((taskData) => {
    if (taskData) Object.keys(taskData).forEach((name) => names.add(name));
  });
  return Array.from(names);
});

// ====================================================================
// 5. 包装 handleConfirm — 串联提取枚举 + 统计
// ====================================================================
const selected = ref<any[]>([])
const handleConfirm = () => {
  // console.log('handleConfirm')
  taskSelection.handleConfirm((validResults) => {
    if (validResults.length > 0) {
      studyData.extractEnums();
      // 为每个任务调用后端API获取统计数据，等待全部完成后再赋值 selected
      const promises = taskSelection.selectedTasks.value.map((task, index) => {
        const datasetName = task.datasets?.[0] || '';
        return studyData.loadTaskStatistics(index, task.ID, task.model_id, datasetName);
      });
      Promise.all(promises).then(() => {
        selected.value = taskSelection.selectedTasks.value;
      });
    }
  });
};

// ====================================================================
// 6. onMounted
// ====================================================================
onMounted(async () => {
  await taskSelection.fetchTasks();
  if (props.task_id) {
    handleConfirm();
  }
});

// ====================================================================
// 7. provide 所有模板需要的变量给 ChildrenStudyTemplate
// ====================================================================
provide("childrenStudyData", {
  // --- 任务选择 ---
  ...taskSelection,
  // --- 数据处理 ---
  ...studyData,
  // --- 图表 ---
  ...charts,
  // --- 单元格样式 ---
  ...cellStyles,
  // --- 包装后的 handleConfirm ---
  handleConfirm,
  // --- 动态 sheet ---
  dynamicSheetData: studyData.dynamicSheetData,
  dynamicSheetNames,
  // --- props ---
  props,
  selected
});
</script>