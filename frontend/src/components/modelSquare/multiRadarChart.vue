<template>
  <VChart :option="chartOptions" autoresize :style="{
    width: width,
    height: height
  }" />
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
  // title: {
  //   type: String,
  //   default: "得分",
  // },
  width: {
    type: [String, Number],
    default: "100%",
  },
  height: {
    type: [String, Number],
    default: "400px",
  },
  showLabel: {
    type: Boolean,
    default: true,
  },
  titles: {
    type: Array,
    default: () => [{ title: "得分", color: "#333" }],
  },
  radius: {
    type: String,
  },
  CNDimention: {
    type: Array,
  },
});

// 用于渲染的 option
const chartOptions = ref({});

// 构建 option 的函数
function buildOptions() {
  // console.log("dimensions:");
  // console.log(props.dimensions);
  // console.log(props.data);
  // console.log(props.CNDimention);
  return {
    tooltip: {
      show: true,
      trigger: "item",
    },
    legend: {
      show: true,
      data: props.data.map((item) => item.title),
      icon: "circle",
      bottom: 0,
      left: "center",
      textStyle: {
        color: "#333",
      },
    },
    radar: {
      radius: props.radius,
      indicator:
        props.CNDimention && props.CNDimention.length > 0
          ? props.CNDimention.map((name) => ({
              name,
              max: 100, // 当CNDimention不为空时，最大值设置为100
            }))
          : props.dimensions.map((name) => ({
              name,
              max: props.maxValue, // 当CNDimention为空时，使用原有的逻辑
            })),
      shape: "circle",
      startAngle: 30,
      splitNumber: 5,
      axisName: {
        color: "#333",
      },
      axisLabel: {
        distance: 10,
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
        type: "radar",
        data: props.data.map((item) => ({
          value: props.dimensions.map((dimension) => {
            let foundData = 0;
            item.data.forEach((oneData) => {
              // console.log("oneData");
              // console.log(oneData);
              if (oneData.dimension === dimension) {
                // console.log(oneData.data);
                foundData = parseFloat(oneData.data) || 0;
              }
            });
            // console.log(
            //   "Final foundData for dimension:",
            //   dimension,
            //   "value:",
            //   foundData
            // );
            return foundData;
            // const foundData = item.data.find((d) => d.dimension === dimension);
          }),
          name: item.title,
          areaStyle: {
            color: item.color ? item.color : "rgba(84,112,198,0.125)",
          },
          lineStyle: {
            color: item.color ? item.color : "#5470C6",
            width: 2,
          },
          itemStyle: {
            color: item.color ? item.color : "#5470C6",
          },
          symbol: "circle",
          symbolSize: 6,
          label: {
            show: props.showLabel,
            formatter: function (params) {
              return params.value;
            },
            position: "center",
            offset: [-8, 0],
          },
        })),
      },
    ],
  };
}

// 初始赋值
chartOptions.value = buildOptions();

// 监控 props 变化，自动更新
watch(
  () => [
    props.dimensions,
    props.data,
    props.maxValue,
    props.titles,
    props.showLabel,
  ],
  () => {
    chartOptions.value = buildOptions();
  },
  { deep: true }
);
</script>
