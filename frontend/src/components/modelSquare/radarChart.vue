<template>
  <VChart
    :option="chartOptions"
    autoresize
    :style="{
      width: width,
      height: height
    }"
  />
</template>

<script setup>
import { ref, watch } from "vue";
import { use } from "echarts/core";
import VChart from "vue-echarts";
import { RadarChart } from "echarts/charts";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

// 按需引入 ECharts 模块
use([RadarChart, TooltipComponent, LegendComponent, CanvasRenderer]);

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
  maxValue: {
    type: Number,
    default: 100,
  },
  title: {
    type: String,
    default: "得分",
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
    tooltip: {
      show: true,
      trigger: "item",
    },
    legend: {
      show: true,
      data: [props.title],
      icon: "circle",
      bottom: 0, // 距离容器底部 10px
      left: "center", // 水平居中
      textStyle: {
        color: "#333",
      },
    },
    radar: {
      indicator: props.dimensions.map((name) => ({
        name,
        max: props.maxValue,
      })),
      shape: "polygon",
      splitNumber: 5,
      axisName: {
        color: "#333",
      },
      splitLine: {
        lineStyle: {
          color: "#ccc",
        },
      },
      splitArea: {
        areaStyle: {
          color: ["rgb(255, 255, 255)", "rgba(239,239,239,0.52)"],
        },
      },
    },
    series: [
      {
        name: props.title,
        type: "radar",
        data: [
          {
            value: props.data,
            name: props.title,
            areaStyle: {
              color: "rgba(84,112,198,0.125)",
            },
            lineStyle: {
              color: "#5470C6",
              width: 2,
            },
            itemStyle: {
              color: "#5470C6",
            },
            symbol: "circle",
            symbolSize: 6,
            label: {
              show: true,
              formatter: function (params) {
                return params.value;
              },
            },
          },
        ],
      },
    ],
  };
}

// 初始赋值
chartOptions.value = buildOptions();

// 监控 props 变化，自动更新
watch(
  () => [props.dimensions, props.data, props.maxValue, props.title],
  () => {
    chartOptions.value = buildOptions();
  },
  { deep: true }
);
</script>
