<template>
  <VChart :option="chartOptions" autoresize :style="{
    width: width,
    height: height
  }" />
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import VChart from "vue-echarts";
import * as echarts from "echarts";

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
  bottomMargin: {
    type: String,
    default: "10%",
  },
  CNDimention: {
    type: Array,
  },
});

const chartOptions = ref({});

function buildOptions() {
  const dataMap = new Map();
  props.data.forEach((item) => {
    item.data.forEach((d) => {
      // console.log(d);
      dataMap.set(d.dimention, d.data);
    });
  });

  //   console.log(dataMap);
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
    },
    legend: {
      data: props.titles.map((item) => item.title),
      icon: "circle",
      bottom: 0, // 距离容器底部 10px
      left: "center", // 水平居中
      textStyle: {
        color: "#333",
      },
    },
    grid: {
      left: "10%",
      right: "3%",
      top: "10%",
      bottom:
        props.CNDimention &&
          props.CNDimention.length > 0 &&
          props.data.length <= 8
          ? "14%"
          : props.bottomMargin, // 动态调整底部边距
      containLabel: true,
    },
    xAxis: [
      {
        type: "category",
        data:
          props.CNDimention && props.CNDimention.length > 0
            ? props.CNDimention
            : props.dimensions,
        axisTick: {
          // alignWithLabel: true,
        },
        axisLabel: {
          color: "#333",
          interval: 0,
          rotate: 30,
        },
      },
    ],
    yAxis: [
      {
        type: "value",
        max: props.maxValue,
        axisLabel: {
          color: "#333",
        },
        splitLine: {
          lineStyle: {
            color: "#ccc",
          },
        },
      },
    ],
    series: props.data.map((item) => ({
      name: item.title,
      type: "bar",
      data: props.dimensions.map((dimension) => {
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
      itemStyle: {
        color: item.color ? item.color : "#5470C6",
      },
      label: {
        show: props.showLabel,
        position: "top",
        formatter: (params) => {
          return params.value;
        },
      },
      // emphasis: {
      //   focus: 'series'
      // },
      // animationDelay: function (idx) {
      //   return idx * 10;
      // }
    })),
  };
}

chartOptions.value = buildOptions();

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