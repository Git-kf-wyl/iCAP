<template>
  <div ref="chartRef" :style="{ width: width, height: height }"></div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { TooltipComponent, VisualMapComponent } from "echarts/components";
import { HeatmapChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([TooltipComponent, VisualMapComponent, HeatmapChart, CanvasRenderer]);

const chartRef = ref(null);
let chartInstance = null;

const props = defineProps({
  xAxis: { type: Array, required: true },
  yAxis: { type: Array, required: true },
  data: { type: Array, required: true },
  width: { type: String, default: "100%" },
  height: { type: String, default: "400px" },
});

function buildOptions() {
  if (!chartRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);

  const maxVal = Math.max(...props.data.map((d) => d[2]), 1);

  chartInstance.setOption({
    title: { text: "用户活跃度热力图", left: "center" },
    tooltip: {
      formatter: (p) =>
        `用户: ${props.yAxis[p.value[1]]}<br/>日期: ${props.xAxis[p.value[0]]}<br/>操作次数: ${p.value[2]}`,
    },
    grid: { left: "10%", right: "4%", bottom: "12%" },
    xAxis: {
      type: "category",
      data: props.xAxis,
      splitArea: { show: true },
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: "category",
      data: props.yAxis,
      splitArea: { show: true },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#f0f9ff", "#bae6fd", "#38bdf8", "#0284c7", "#0c4a6e"] },
    },
    series: [
      {
        type: "heatmap",
        data: props.data,
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.5)" },
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
  () => [props.xAxis, props.yAxis, props.data],
  () => buildOptions(),
  { deep: true }
);
</script>