<template>
  <div>
    <div ref="BarChart" class="BarChart"></div>
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
  const categories = props.data.map((item) => `${item.name} |   ${item.index}`);
  const values = props.data.map((item) => item.value);
  const dsIndex = categories.findIndex((category) =>
      category.startsWith("DeepSeek-R1 |")
  );
  const option = {
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "shadow",
      },
    },
    grid: {
      left: "0%",
      right: "4%",
      bottom: "3%",
      containLabel: true,
    },
    xAxis: {
      type: "value",
      axisLabel: {
        fontSize: 20,
        fontFamily: "Arial",
        fontWeight: "bold",
      },
    },
    yAxis: {
      type: "category",
      data: categories,
      inverse: true,
      axisLabel: {
        fontSize: 20,
        fontFamily: "Arial",
        fontWeight: "bold",
        align: "right",
      },
    },
    series: [
      {
        name: "平均分",
        type: "bar",
        data: values,
        label: {
          show: true,
          position: "right",
        },
      },
    ],
  };
  chartInstance.setOption(option);
};

onMounted(() => {
  initChart();
  // window.hwa('trackPageView', 'P135A5DAB7B7244');
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
.BarChart {
  width: 100%;
  height: 100%;
}
</style>