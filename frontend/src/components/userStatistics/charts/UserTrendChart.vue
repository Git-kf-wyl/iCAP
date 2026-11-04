<template>
  <div ref="chartRef" :style="{ width: width, height: height }"></div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from "echarts/components";
import { LineChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  TooltipComponent,
  LegendComponent,
  GridComponent,
  LineChart,
  CanvasRenderer,
]);

const chartRef = ref(null);
let chartInstance = null;

const props = defineProps({
  xAxis: { type: Array, required: true },
  series: { type: Array, required: true },
  width: { type: String, default: "100%" },
  height: { type: String, default: "400px" },
});

function buildOptions() {
  if (!chartRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);

  chartInstance.setOption({
    title: { text: "用户操作趋势", left: "center" },
    tooltip: { trigger: "axis" },
    legend: { 
      bottom: 0, // 设置图例距离底部 30px
      height: 30, // 设置图例高度
      type: "scroll"
    },
    grid: { 
      left: "3%", 
      right: "4%", 
      bottom: "60px", // 为 dataZoom 和 legend 留出空间
      containLabel: true 
    },
    xAxis: {
      type: "category",
      data: props.xAxis,
      boundaryGap: false,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: { type: "value", name: "操作次数" },
    dataZoom: [
      {
        type: "inside",
        start: 90,
        end: 100,
      },
      {
        start: 90,
        end: 100,
        bottom: 30, // 设置 dataZoom 距离底部 60px，避免与 legend 重叠
      },
    ],
    series: props.series.map((s) => ({
      name: s.name,
      type: "line",
      data: s.data,
      smooth: true,
      symbol: "circle",
      emphasis: {
        focus: "series",
      },
      symbolSize: 6,
    })),
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
  () => [props.xAxis, props.series],
  () => buildOptions(),
  { deep: true }
);
</script>