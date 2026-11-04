<template>
  <div ref="chartRef" :style="{ width: width, height: height }"></div>
</template>

<script setup>
import { ref, onMounted, watch, onBeforeUnmount, computed } from "vue";
import * as echarts from "echarts/core";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { PieChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([TooltipComponent, LegendComponent, PieChart, CanvasRenderer]);

const chartRef = ref(null);
let chartInstance = null;

const props = defineProps({
  data: { type: Array, required: true },
  width: { type: String, default: "100%" },
  height: { type: String, default: "400px" },
});

const total = computed(() => props.data.reduce((acc, cur) => acc + cur.value, 0));

function buildOptions() {
  if (!chartRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(chartRef.value);

  chartInstance.setOption({
    title: {
      text: "操作类型分布",
      subtext: "总计: " + total.value,
      left: "center",
    },
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [
      {
        type: "pie",
        radius: ["35%", "55%"],
        center: ["50%", "55%"],
        data: props.data,
        label: {
          formatter: "{b}\n{d}%",
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.5)" },
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
  () => props.data,
  () => buildOptions(),
  { deep: true }
);
</script>