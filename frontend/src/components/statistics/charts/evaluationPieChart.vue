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
import { PieChart } from "echarts/charts";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  TooltipComponent,
  LegendComponent,
  PieChart,
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
  if (!chartInstance || !chartRef.value) return;

  const options = {
    title: {
      top: 10,
      text: props.title,
      subtext: "总计:" + props.data.reduce((acc, curr) => acc + curr.value, 0),
      left: "center",
    },
    tooltip: {
      trigger: "item",
    },
    series: [
      {
        name: props.title,
        type: "pie",
        radius: "45%",
        center: ["50%", "60%"],
        data: props.data.length > 0 ? props.data : {},
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: "rgba(0, 0, 0, 0.5)",
          },
        },
        labelLine: {
          length: 30,
          minTurnAngle: 90,
          // maxSurfaceAngle:45,
          length: 15,
          length2: 15,
        },
        label: {
          formatter: function (params) {
            const items = props.data.find((d) => d.name === params.name);
            const percent = params.percent;
            if (items) {
              return `{b|${params.name}\n${params.value}(${percent}%)}`;
            } else {
              return "";
            }
          },
          backgroundColor: "#F6F8FC",
          borderColor: "#8C8D8E",
          borderWidth: 1,
          borderRadius: 4,
          rich: {
            b: {
              fontSize: 12,
              color: "#000",
              fontWeight: 600,
              lineHeight: 22,
              align: "center",
            },
          },
        },
      },
    ],
  };

  chartInstance.setOption(options);
}

const checkScreenWidth = () => {
  const newIsSmallScreen = window.innerWidth < 1500;
  // 如果屏幕状态发生变化，则更新并重建图表选项
  if (newIsSmallScreen !== isSmallScreen.value) {
    isSmallScreen.value = newIsSmallScreen;
    if (chartInstance) {
      buildOptions();
      chartInstance.resize();
    }
  } else {
    // 即使状态没变，也可能只是调整大小，需要重绘
    if (chartInstance) {
      chartInstance.resize();
    }
  }
};

onMounted(() => {
  chartInstance = echarts.init(chartRef.value);
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