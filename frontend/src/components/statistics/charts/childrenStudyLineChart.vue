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

    if (dataType[key]) {
      // 折线图系列配置（百分比数据）
      lineSeries.push({
        name: key,
        type: "line",
        data: data.map((item) => item[key].replace("%", "")),
        yAxisIndex: 0, // 绑定左侧y轴

        symbol: "circle",
        symbolSize: 8,
        lineStyle: { width: 3 },
        label: {
          show: true,
          formatter: (params) => {
            const dataIndex = params.dataIndex;
            const dataItem = data[dataIndex];
            return `正确率：${dataItem[key]}\n总数量：${dataItem["总数量"]}\n全部正确数量：${dataItem["全部正确数量"]}`;
          },
        },
      });
    } else {
      // 柱状图系列配置（普通数值）
      barSeries.push({
        name: key,
        type: "bar",
        data: data.map((item) => item[key]),
        yAxisIndex: 1, // 绑定右侧y轴
        barGap: "0%",
        emphasis: { focus: "series" },
        label: {
          show: true,
          position: "top",
        },
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

      formatter: function (params) {
        // 1. 从 params 中获取当前分类的名称 (即 {b})
        const taskName = params[0].name;

        // 2. 在 props.data 中查找 task_name 与之匹配的对象
        let foundItem = null;
        for (const item of props.data) {
          if (item.task_name === taskName) {
            foundItem = item;
            break; // 找到后即可跳出循环
          }
        }

        // 3. 准备 tooltip 的显示内容
        let tooltipContent = `<div>任务名：${taskName}</div><br/>`;

        // 4. 遍历所有系列，显示它们的数据（这是 {c} 的默认行为）
        params.forEach((param) => {
          // seriesName 是图例的名称，value 是该数据点的值
          tooltipContent +=
            param.seriesName === "总正确率"
              ? `<div>${param.seriesName}: <strong>${param.value}%</strong></div>`
              : `<div>${param.seriesName}: <strong>${param.value}</strong></div>`;
        });

        // 5. 如果在 props.data 中找到了匹配项，则添加“总正确率”信息
        if (foundItem) {
          const totalNum = foundItem["总数量"]; // 使用您的实际属性名
          const accuracyItem = foundItem["全部正确数量"];
          if (foundItem["总数量"]) {
            tooltipContent += `<br/><div>总数量: ${totalNum}</div>`;
          }
          if (foundItem["全部正确数量"]) {
            tooltipContent += `<br/><div>全部正确数量: ${accuracyItem}</div>`;
          }
        }

        return tooltipContent;
      },
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
        name: "百分比",
        min: 0,
        max: 100,
        position: "left",
        axisLabel: { formatter: "{value}%" },
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