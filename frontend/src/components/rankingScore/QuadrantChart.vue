<template>
  <div style="height: 600px">
    <div ref="chartDom" class="chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import * as echarts from "echarts";

// 接收数据
const props = defineProps({
  data: {
    type: Array,
    required: true,
    default: () => [],
  },
  ruler1Median: {
    type: Number,
    default: 50,
  },
  ruler2Median: {
    type: Number,
    default: 50,
  },
  title: {
    type: String,
    default: "象限图",
  },
  width: {
    type: [String, Number],
    default: "400px",
  },
  height: {
    type: [String, Number],
    default: "400px",
  },
  quadrantLabels: {
    topLeft: "",
    bottomLeft: "",
    topRight: "",
    bottomRight: "",
  },
});

// 图表 DOM 引用
const chartDom = ref(null);
let chartInstance = null;

// 四个象限颜色
const quadrantColors = {
  实用主义者: "#409EFF",
  卓越领导者: "#F56C6C",
  技术领跑者: "#67C23A",
  潜力探索者: "#E6A23C",
};

const quadrantCenterData = [
  {
    name: props.quadrantLabels.topLeft,
    value: [
      props.ruler1Median / 2,
      props.ruler2Median + props.ruler2Median / 2,
    ],
  },
  {
    name: props.quadrantLabels.bottomLeft,
    value: [props.ruler1Median / 2, props.ruler2Median / 2],
  },
  {
    name: props.quadrantLabels.topRight,
    value: [
      props.ruler1Median + props.ruler1Median / 2,
      props.ruler2Median + props.ruler2Median / 2,
    ],
  },
  {
    name: props.quadrantLabels.bottomRight,
    value: [
      props.ruler1Median + props.ruler1Median / 2,
      props.ruler2Median / 2,
    ],
  },
];

// 获取象限名称
function getQuadrant(item) {
  const x = item.ruler1;
  const y = item.ruler2;

  if (x < props.ruler1Median && y < props.ruler2Median) return "实用主义者";
  if (x < props.ruler1Median && y >= props.ruler2Median) return "卓越领导者";
  if (x >= props.ruler1Median && y >= props.ruler2Median) return "技术领跑者";
  if (x >= props.ruler1Median && y < props.ruler2Median) return "潜力探索者";
}

// 初始化图表
function initChart() {
  if (!chartDom.value) return;
  // console.log("chartDom");
  // console.log(chartDom.value);

  chartInstance = echarts.init(chartDom.value);

  // console.log("chartInstance");
  // console.log(chartInstance);

  const seriesData = props.data.map((item) => ({
    name: item.name,
    value: [item.ruler1, item.ruler2],
    category: getQuadrant(item),
  }));

  const option = {
    title: {
      text: props.title,
      left: "center",
    },
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        return `${params.name}<br/>基本能力: ${params.value[0]}<br/>领域能力: ${params.value[1]}`;
      },
    },
    xAxis: {
      name: "基本能力 (ruler1)",
      min: 0,
      max: 100,
      splitLine: { show: false },
    },
    yAxis: {
      name: "领域能力 (ruler2)",
      min: 0,
      max: 100,
      splitLine: { show: false },
    },
    grid: {
      left: "15%",
      right: "15%",
      bottom: "10%",
      top: "10%",
      containLabel: true,
    },
    series: [
      {
        type: "scatter",
        symbolSize: () => 10,
        data: seriesData,
        label: {
          show: true,
          position: "right",
          formatter: (params) => params.data.name,
        },
        itemStyle: {
          color: (params) => {
            return quadrantColors[params.data.category] || "#999";
          },
        },
      },
      {
        name: "中位线",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        markLine: {
          symbol: "none", // 不显示箭头等符号
          lineStyle: {
            color: "#999",
            width: 1,
          },
          data: [
            {
              yAxis: props.ruler2Median,
              name: "水平中位线",
            },
            {
              xAxis: props.ruler1Median,
              name: "垂直中位线",
            },
          ],
          label: { show: false },
        },
      },
      {
        type: "bar",
        data: quadrantCenterData,
        label: {
          show: true,
          position: "insideTop", // 居中显示
          formatter: (params) => params.data.name,
          color: "#333",
          fontSize: 14,
          fontWeight: "bold",
          backgroundColor: "transparent", // 可选背景色
          padding: [2, 5],
          borderRadius: 2,
          borderWidth: 1,
        },
        itemStyle: {
          color: "transparent", // 隐藏柱子
        },
        emphasisItemStyle: {
          color: "transparent",
        },
        z: -1,
      },
    ],
    legend: {
      data: Object.keys(quadrantColors),
      top: "bottom",
    },
  };

  chartInstance.setOption(option);
}

// 监听数据变化
watch(
  () => props.data,
  () => {
    if (chartInstance) {
      chartInstance.dispose(); // 销毁旧图表
    }
    initChart();
  },
  { deep: true }
);

// 挂载时初始化
onMounted(() => {
  initChart();
});
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%;
}
</style>