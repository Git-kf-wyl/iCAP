<template>
  <VChart
    :option="chartOptions"
    :style="{
      width: width,
      height: height,
    }"
  />
</template>

<script setup>
import { ref, watch } from "vue";
import { use } from "echarts/core";
import VChart from "vue-echarts";
import { BarChart } from "echarts/charts";
// import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { GridComponent } from "echarts/components";

// 按需引入 ECharts 模块
use([BarChart, CanvasRenderer, GridComponent]);

// 定义 props
const props = defineProps({
  dimensions: {
    type: Array,
    required: true,
  },
  data: {
    type: Array,
    required: true,
  },
  width: {
    type: [String, Number],
    default: "100%",
  },
  height: {
    type: [String, Number],
    default: "400px",
  },
});

// 用于渲染的 option
const chartOptions = ref({});

// 构建 option 的函数
function buildOptions() {
  return {
    xAxis: {
      type: "category",
      axisLabel: { interval: 0, rotate: 30 },
      data: props.dimensions,
    },
    yAxis: {
      type: "value",
    },
    series: [
      {
        type: "bar",
        data: props.data,
        realtimeSort: true,
      },
    ],
  };
}

// 初始赋值
chartOptions.value = buildOptions();

// 监控 props 变化，自动更新
watch(
  () => [props.dimensions, props.data],
  () => {
    chartOptions.value = buildOptions();
  },
  { deep: true }
);
</script>
