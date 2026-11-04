<template>
  <div>
    <div ref="BarChart" :style="{
          width: width,
          height: height,
        }"></div>
  </div>
</template>
  
  <script setup>
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import * as echarts from "echarts";

const props = defineProps({
  data: {
    type: Array,
    required: true,
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

const BarChart = ref(null);
let chartInstance = null;

const initChart = () => {
  if (!chartInstance) {
    chartInstance = echarts.init(BarChart.value);
  }
  updateChart();
};

const updateChart = () => {
  const categories = props.data.map((item) => `${item.interval}`);
  const values = props.data.map((item) => item.count);
  const option = {
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
      formatter: (params) => {
        const p = params[0];
        const count = p.value;
        const total = values.reduce((s, v) => s + v, 0);
        const pct = total > 0 ? ((count / total) * 100).toFixed(2) + "%" : "0.00%";
        return `${p.axisValue}<br/>数量：${count}<br/>占比：${pct}`;
      },
    },
    grid: {
      left: "0%",
      right: "4%",
      bottom: "3%",
      containLabel: true,
    },
    yAxis: {
      type: "value",
    },
    xAxis: {
      type: "category",
      data: categories,
    },
    series: [
      {
        name: "数量",
        type: "bar",
        data: values,
        label: {
          show: true,
          position: "top",
        },
      },
    ],
  };
  chartInstance.setOption(option);
};

onMounted(() => {
  initChart();
  window.addEventListener("resize", handleResize);
});

watch(
  () => props.data,
  () => {
    if (chartInstance) {
      updateChart();
    }
  },
  { deep: true }
);

const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>
  
  <style scoped>
</style>