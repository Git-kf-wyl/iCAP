<template>
  <div class="compare-chart-card">
    <div v-if="title" class="chart-title">{{ title }}</div>
    <div ref="chartEl" class="compare-chart-body"></div>
    <div v-if="rows.length === 0" class="null-data">暂无数据</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import * as echarts from "echarts";

const props = defineProps({
  title: { type: String, default: "" },
  data: { type: Array, default: () => [] },
  height: { type: Number, default: null },
});

const chartEl = ref(null);
let chartInstance = null;
let resizeObserver = null;

const rows = computed(() =>
  [...props.data]
    .filter((d) => d && d.name != null && d.value != null)
    .sort((a, b) => b.value - a.value)
);

function buildOption() {
  const names = rows.value.map((r) => r.name);
  const values = rows.value.map((r) => r.value);
  const rotateLabels = names.length > 8;
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const p = params[0];
        return p.name + "<br/>得分: " + Number(p.value).toFixed(2);
      },
    },
    grid: {
      left: "8%",
      right: "8%",
      top: "8%",
      bottom: rotateLabels ? "22%" : "12%",
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: names,
      axisLabel: {
        color: "#333",
        fontSize: 11,
        interval: 0,
        rotate: rotateLabels ? 35 : 0,
        width: 120,
        overflow: "truncate",
      },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      max: 1.0,
      axisLabel: { color: "#666", fontSize: 11 },
      splitLine: { lineStyle: { color: "#eee" } },
    },
    series: [
      {
        name: "得分",
        type: "bar",
        data: values,
        barMaxWidth: 32,
        itemStyle: { color: "#5470C6", borderRadius: [3, 3, 0, 0] },
        label: {
          show: true,
          position: "top",
          formatter: (p) => Number(p.value).toFixed(2),
          color: "#333",
          fontSize: 10,
        },
      },
    ],
  };
}

function render() {
  if (chartInstance) chartInstance.setOption(buildOption(), true);
}

const handleResize = () => {
  if (chartInstance) chartInstance.resize();
};

onMounted(async () => {
  if (!chartEl.value) return;
  chartInstance = echarts.init(chartEl.value);
  await nextTick();
  render();
  // 容器尺寸变化（如 tab 由隐藏转为可见）时自动调整图表尺寸
  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => handleResize());
    resizeObserver.observe(chartEl.value);
  } else {
    window.addEventListener("resize", handleResize);
  }
});

watch(
  () => [props.data, props.title],
  () => nextTick(() => render()),
  { deep: true }
);

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  } else {
    window.removeEventListener("resize", handleResize);
  }
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.compare-chart-card {
  position: relative;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #eaeaea;
  border-radius: 8px;
  padding: 12px 16px;
  box-sizing: border-box;
  height: 100%;
  width: 100%;
}
.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #1b3882;
  margin-bottom: 8px;
  padding-left: 8px;
  border-left: 3px solid #1b3882;
  flex-shrink: 0;
}
.compare-chart-body {
  flex: 1 1 0;
  width: 100%;
  min-height: 320px;
}
.null-data {
  position: absolute;
  left: 0;
  right: 0;
  top: 45%;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>
