<template>
  <div ref="chartRef" :style="{ width: width, height: height }"></div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { TooltipComponent, LegendComponent, GridComponent } from "echarts/components";
import { BarChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([TooltipComponent, LegendComponent, GridComponent, BarChart, CanvasRenderer]);

const chartRef = ref(null);
let chartInstance = null;

const props = defineProps({
  users: { type: Array, required: true },
  counts: { type: Array, required: true },
  width: { type: String, default: "100%" },
  height: { type: String, default: "400px" },
});

function buildOptions() {
  if (!chartRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);

  chartInstance.setOption({
    title: { text: "活跃用户排行", left: "center" },
    tooltip: { trigger: "axis" },
    grid: { left: "3%", right: "4%", bottom: "10%", containLabel: true },
    xAxis: {
      type: "category",
      data: props.users,
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: { type: "value", name: "操作次数" },
    series: [
      {
        type: "bar",
        data: props.counts,
        label: { show: true, position: "top", fontSize: 11 },
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "#38bdf8" },
            { offset: 1, color: "#0284c7" },
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
  () => [props.users, props.counts],
  () => buildOptions(),
  { deep: true }
);
</script>