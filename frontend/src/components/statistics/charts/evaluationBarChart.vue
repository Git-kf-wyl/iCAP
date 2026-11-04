<template>
  <div ref="chartRef" :key="chartKey" :style="{
      width: width,
      height: height,
    }"></div>
</template>

<script setup>
import { ref, onMounted, watch, computed, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { LineChart } from "echarts/charts";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  TooltipComponent,
  LegendComponent,
  LineChart,
  CanvasRenderer,
  LabelLayout,
]);

const chartRef = ref(null);
let chartInstance = null;

const chartKey = ref(0);
const isSmallScreen = ref(false);

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  title: {
    type: String,
    default: "",
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

const creatorNames = computed(() => props.data.map((item) => item.creator));
const times = computed(() => props.data.map((item) => item.times));

function buildOptions() {
  // if (!chartInstance || !chartRef.value) return;
  if (!chartRef.value) return;

  chartInstance = echarts.init(chartRef.value);

  const options = {
    title: { text: props.title, left: "center" },
    tooltip: { trigger: "axis" },
    xAxis: {
      type: "category",
      data: creatorNames.value,
      axisLabel: {
        color: "#333",
        interval: 0,
        rotate: 30,
      },
    },
    yAxis: { type: "value" },
    series: [
      {
        name: "评测次数",
        type: "bar",
        data: times.value,
        label: {
          show: true,
          position: "top",
        },
      },
    ],
  };

  chartInstance.setOption(options);
}

const checkScreenWidth = () => {
  isSmallScreen.value = window.innerWidth < 1500;
};

onMounted(async () => {
  // chartInstance = echarts.init(chartRef.value);
  buildOptions();
  checkScreenWidth();
  window.addEventListener("resize", checkScreenWidth);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", checkScreenWidth);
});

watch(
  () => props.data,
  () => {
    buildOptions();
  },
  { deep: true }
);
</script>