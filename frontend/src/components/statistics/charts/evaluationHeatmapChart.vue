<template>
  <div
    ref="chartRef"
    :key="chartKey"
    :style="{
        width: width,
        height: height,
    }"
  ></div>
</template>

<script setup>
import { ref, onMounted, watch, computed, onBeforeUnmount } from "vue";
import * as echarts from "echarts/core";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { HeatmapChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([TooltipComponent, LegendComponent, HeatmapChart, CanvasRenderer]);

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
  xData: {
    type: Array,
    required: true,
  },
  yData: {
    type: Array,
    required: true,
  },
});

const creatorNames = computed(() => props.data.map((item) => item.creator));
const times = computed(() => props.data.map((item) => item.times));

function buildOptions() {
  if (!chartInstance || !chartRef.value) return;

  const heatmapData = props.data.map((item) => {
    const y = props.yData.indexOf(item[0]);
    const x = props.xData.indexOf(item[1]);
    return [x, y, item[2]];
  });
  // console.log('heatmapData');
  // console.log(heatmapData);

  const options = {
    tooltip: {
      position: "top",
      formatter: function (p) {
        return (
          "模型：" +
          props.yData[p.data[1]] +
          "<br/>测试集：" +
          props.xData[p.data[0]] +
          "<br/>次数：" +
          p.data[2]
        );
      },
    },
    grid: {
      height: "70%",
      top: "0",
      left: "22%",
    },
    xAxis: {
      type: "category",
      data: props.xData,
      splitArea: { show: true },
      axisLabel: {
        // interval: 0,
        rotate: 40,
        fontSize: 10,
        margin: 2,
      },
    },
    yAxis: {
      type: "category",
      data: props.yData,
      splitArea: { show: true },
      nameTextStyle: { color: "rgba(161, 78, 78, 1)" },
    },
    visualMap: {
      min: 0,
      max: 10,
      calculable: true,
      orient: "vertical",
      right: "0",
      top: "center",
    },
    series: [
      {
        name: "Punch Card",
        type: "heatmap",
        data: heatmapData,
        label: {
          show: false,
          fontSize: isSmallScreen.value ? 8 : 12,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: "rgba(0, 0, 0, 0.5)",
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
