<template>
  <div>
    <el-radio-group
      v-model="activeLevel"
      size="small"
      style="margin-bottom: 8px; text-align: center; display: flex; justify-content: center;"
    >
      <el-radio-button value="dept4">四级部门</el-radio-button>
      <el-radio-button value="dept5">五级部门</el-radio-button>
      <el-radio-button value="dept6">六级部门</el-radio-button>
    </el-radio-group>
    <div ref="chartRef" :style="{ width: width, height: height }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, computed } from "vue";
import * as echarts from "echarts/core";
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from "echarts/components";
import { BarChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  TooltipComponent,
  LegendComponent,
  GridComponent,
  BarChart,
  CanvasRenderer,
]);

const chartRef = ref(null);
let chartInstance = null;

const activeLevel = ref("dept4");

const props = defineProps({
  data: { type: Object, required: true },
  width: { type: String, default: "100%" },
  height: { type: String, default: "380px" },
});

const currentNames = computed(() => {
  const level = props.data[activeLevel.value];
  return level ? level.names : [];
});

const currentCounts = computed(() => {
  const level = props.data[activeLevel.value];
  return level ? level.counts : [];
});

function buildOptions() {
  // console.log('data')
  // console.log(props.data)
  if (!chartRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);

  chartInstance.setOption({
    title: { text: "部门使用统计", left: "center" },
    tooltip: { trigger: "axis" },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "10%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: currentNames.value,
      axisLabel: {
        rotate: 35,
        fontSize: 11,
        interval: 0,
        margin: 10,
        overflow: "break",
        width: 100,
      },
    },
    yAxis: { type: "value", name: "操作次数" },
    series: [
      {
        type: "bar",
        data: currentCounts.value,
        label: { show: true, position: "top", fontSize: 10 },
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#f97316" },
            { offset: 1, color: "#ea580c" },
          ]),
        },
      },
    ],
  });
}

onMounted(() => {
  chartInstance = echarts.init(chartRef.value);
  buildOptions();
  window.addEventListener("resize", () => chartInstance?.resize());
});

onBeforeUnmount(() => {
  chartInstance?.dispose();
});

watch(
  () => [props.data, activeLevel.value],
  () => buildOptions(),
  { deep: true }
);
</script>