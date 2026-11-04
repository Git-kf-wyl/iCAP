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

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  title: {
    type: String,
    default: "",
  },
  dataType: {
    type: Object,
  },
  width: {
    type: [String, Number],
    default: "100%",
  },
  height: {
    type: [String, Number],
    default: "450px",
  },
});

function buildOptions() {
  if (!chartRef.value) return;

  // console.log(props.data);
  const options = generateChartOptions(props.data, props.dataType);

  // 销毁旧实例并创建新实例
  if (chartInstance) {
    chartInstance.dispose();
  }
  chartInstance = echarts.init(chartRef.value);
  chartInstance.setOption(options);
}

const generateChartOptions = (data, dataType) => {
  // 提取x轴数据（任务名称）
  const xAxisData = data.map((item) => item.task_name);

  // 分离系列类型（折线图/柱状图）
  const lineSeries = [];
  const barSeries = [];
  const legendData = [];

  // 获取所有需要展示的键（排除task_name）
  const keys = Object.keys(dataType);

  keys.forEach((key) => {
    if (!dataType.hasOwnProperty(key)) return;

    // 检查当前数据项是否包含该key（双重保障）
    const isValidKey = data.every((item) => key in item);
    if (!isValidKey) {
      console.warn(`警告: 数据缺少必要字段 '${key}'`);
      return; // 跳过无效key
    }

    if (dataType[key]) {
      // 折线图数据处理：安全替换字符
      lineSeries.push({
        name: key,
        type: "line",
        data: data.map((item) => {
          const rawValue = item[key];

          // 类型安全处理
          if (rawValue === null || rawValue === undefined) {
            return 0; // 空值默认返回0
          }

          // 确保转换为字符串后再处理
          const strValue = String(rawValue);
          return strValue.replace("s", ""); // 移除's'字符
        }),
        yAxisIndex: 0,
        symbol: "circle",
        symbolSize: 8,
        lineStyle: { width: 3 },
        label: { show: true },
      });
    } else {
      // 柱状图数据处理：安全数值转换
      barSeries.push({
        name: key,
        type: "bar",
        data: data.map((item) => {
          const rawValue = item[key];

          // 空值处理
          if (rawValue === null || rawValue === undefined) {
            return 0; // 空值默认返回0
          }

          // 数值转换（兼容字符串数字）
          const num = Number(rawValue);
          return isNaN(num) ? 0 : num; // 转换失败返回0
        }),
        yAxisIndex: 1,
        barGap: "0%",
        emphasis: { focus: "series" },
        label: { show: true, position: "top" },
      });
    }

    legendData.push(key);
  });

  // console.log("lineSeries");
  // console.log(lineSeries);

  return {
    title: {
      text: props.title,
      left: "center",
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    legend: { data: legendData, bottom: 0, left: "center" },
    grid: {
      left: 50,
      right: 50,
      bottom: 50,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: xAxisData,
      axisLabel: { interval: 0, rotate: 30 },
    },
    yAxis: [
      {
        show: Object.values(props.dataType).includes(true),
        // 左侧百分比轴（折线图）
        type: "value",
        name: "耗时(s)",
        position: "left",
        axisLabel: { show: true },
        axisLine: { show: true },
        splitLine: { show: true },
      },
      {
        show: Object.values(props.dataType).includes(false),
        // 右侧数值轴（柱状图）
        type: "value",
        name: "数量",
        position: Object.values(props.dataType).includes(true)
          ? "right"
          : "left",
        alignTicks: true,
        axisLine: { show: true },
        axisLabel: { formatter: "{value}" },
        splitLine: { show: false },
      },
    ],
    series: [...lineSeries, ...barSeries],
  };
};

onMounted(async () => {
  buildOptions();
});

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});

watch(
  () => props.data,
  () => {
    buildOptions();
  },
  { deep: true }
);
</script>