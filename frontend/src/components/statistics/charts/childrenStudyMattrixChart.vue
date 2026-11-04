<template>
  <div class="sparkline-matrix-container" ref="chartContainer">
    <div ref="chartRef" class="sparkline-chart" :style="{ height: containerHeight + 'px' }"></div>
  </div>
</template>
  
  <script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from "vue";
import * as echarts from "echarts";

// ==================== Props 定义 ====================
const props = defineProps({
  // 数据源：每个对象代表一个任务
  data: {
    type: Array,
    required: true,
    default: () => [],
  },
  // 每行显示的维度数量（默认5列）
  columns: {
    type: Number,
    default: 5,
  },
  // 每个微型图表的高度（像素）
  chartHeight: {
    type: Number,
    default: 100,
  },
  // 维度标签行的高度
  labelHeight: {
    type: Number,
    default: 30,
  },
  // 图表间距
  gap: {
    type: Number,
    default: 5,
  },
  // 颜色配置
  colors: {
    type: Array,
    default: () => ["#5470c6", "#91cc75", "#fac858", "#ee6666", "#73c0de"],
  },
  // 是否显示图例
  showLegend: {
    type: Boolean,
    default: true,
  },
  title: {
    type: String,
  },
  rateName: {
    type: String,
    default: "",
  },
});

// ==================== 响应式引用 ====================
const chartRef = ref(null);
const chartContainer = ref(null);
let chartInstance = null;

// ==================== 数据处理 ====================
// 提取所有维度名称
const dimensions = computed(() => {
  if (!props.data || props.data.length === 0) return [];

  const excludeKeys = ["task_name", "taskName", "task-name"];
  const allKeys = Object.keys(props.data[0]);
  return allKeys.filter((key) => !excludeKeys.includes(key));
});

// 提取任务名称列表
const taskNames = computed(() => {
  if (!props.data || props.data.length === 0) return [];
  return props.data.map(
    (item) => item.task_name || item.taskName || item["task-name"] || "未知任务"
  );
});

// 计算矩阵行数（维度标签行 + 图表行）
const matrixRows = computed(() => {
  const dimensionCount = dimensions.value.length;
  const chartRows = Math.ceil(dimensionCount / props.columns);
  return chartRows * 2; // 每行图表对应一行标签
});

// 计算容器总高度
const containerHeight = computed(() => {
  const chartRows = Math.ceil(dimensions.value.length / props.columns);
  const labelRows = chartRows; // 标签行数与图表行数相同
  const totalChartHeight = chartRows * props.chartHeight * 2;
  const totalLabelHeight = labelRows * props.labelHeight;
  const totalGap = (chartRows + labelRows - 1) * props.gap;
  const legendHeight = props.showLegend ? 40 : 0;

  return totalChartHeight + totalLabelHeight + totalGap + legendHeight + 20;
});

// ==================== 数据转换 ====================
// 将原始数据转换为ECharts需要的系列数据
const transformDataForSeries = () => {
  const series = [];
  const dimensionCount = dimensions.value.length;
  const chartRows = Math.ceil(dimensionCount / props.columns);

  // 为每个维度创建一个系列
  dimensions.value.forEach((dim, dimIndex) => {
    const rowIndex = Math.floor(dimIndex / props.columns); // 第几行图表
    const colIndex = dimIndex % props.columns; // 第几列

    // 计算该图表在matrix中的位置
    const matrixRowIndex = rowIndex * 2 + 1; // 图表行在奇数行（标签在偶数行）

    // 提取该维度下所有任务的数据
    const dataValues = props.data.map((task) => {
      const value = task[dim];
      // 处理百分比字符串，转换为数值
      if (typeof value === "string") {
        return parseFloat(value.replace("%", ""));
      }
      return typeof value === "number" ? value : 0;
    });

    series.push({
      type: "line",
      data: dataValues,
      // 指定该系列使用哪个grid（通过matrix坐标系定位）
      xAxisIndex: dimIndex,
      yAxisIndex: dimIndex,
      // 微型折线图样式
      symbol: "circle",
      symbolSize: 4,
      lineStyle: {
        width: 2,
        cap: "round",
      },
      areaStyle: {
        opacity: 0.1,
      },
      // 不显示默认标签
      label: {
        show: true,
        formatter: (params) => {
          return params.data + "%";
        },
      },
    });
  });

  return series;
};

// ==================== Grid配置（matrix布局核心） ====================
const getGridConfig = () => {
  const grids = [];
  const dimensionCount = dimensions.value.length;
  const chartRows = Math.ceil(dimensionCount / props.columns);

  dimensions.value.forEach((dim, dimIndex) => {
    const rowIndex = Math.floor(dimIndex / props.columns);
    const colIndex = dimIndex % props.columns;

    // 计算标签高度占容器总高度的百分比
    const labelPercent = (props.labelHeight / containerHeight.value) * 100;
    // 计算图表高度占容器总高度的百分比
    const chartPercent = (props.chartHeight / containerHeight.value) * 100;

    // 计算在容器中的位置（百分比）
    const topPercent =
      11 + // 顶部留白
      rowIndex * 2 * (labelPercent + chartPercent) + // 每行占的空间（标签+图表）
      labelPercent; // 当前标签的高度

    grids.push({
      // 使用matrix坐标系定位
      top: `${topPercent}%`,
      left: `${colIndex * (100 / props.columns) + 1}%`,
      width: `${(100 - (props.columns - 1) * 2) / props.columns - 2}%`,
      height: `${chartPercent}%`,
      borderColor: "transparent",
      backgroundColor: "transparent",
      containLabel: false,
    });
  });

  return grids;
};

// ==================== X轴配置 ====================
const getXAxisConfig = () => {
  const xAxisList = [];
  const dimensionCount = dimensions.value.length;

  dimensions.value.forEach((dim, dimIndex) => {
    xAxisList.push({
      type: "category",
      data: taskNames.value,
      axisLabel: { interval: 0, rotate: 30 },
      // 微型图表不显示坐标轴
      //   show: false,
      gridIndex: dimIndex,
      // 不显示刻度
      axisTick: { show: false },
      axisLine: { show: false },
      //   axisLabel: { show: false },
    });
  });

  return xAxisList;
};

// ==================== Y轴配置 ====================
const getYAxisConfig = () => {
  const yAxisList = [];
  const dimensionCount = dimensions.value.length;

  dimensions.value.forEach((dim, dimIndex) => {
    yAxisList.push({
      type: "value",
      scale: true,
      gridIndex: dimIndex,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        showMaxLabel: true,
        fontSize: 9,
      },
      //   splitLine: { show: false },
      // 固定范围0-100（正确率百分比）
      min: 0,
      max: 100,
    });
  });

  return yAxisList;
};

// ==================== 完整Option配置 ====================
const getChartOption = () => {
  // 计算高度百分比
  const labelPercent = containerHeight.value
    ? (props.labelHeight / containerHeight.value) * 100
    : 0;
  const chartPercent = containerHeight.value
    ? (props.chartHeight / containerHeight.value) * 100
    : 0;

  // 获取grid配置（传入新参数）
  const grids = getGridConfig(labelPercent, chartPercent);
  return {
    // 标题
    // title: {
    //   text: props.title,
    //   left: "center",
    //   top: 0,
    //   textStyle: {
    //     fontSize: 14,
    //     color: "#333",
    //   },
    // },

    // 图例
    legend: {
      show: props.showLegend,
      data: taskNames.value,
      top: 25,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        fontSize: 11,
      },
    },

    graphic: dimensions.value.map((dim, dimIndex) => {
      const rowIndex = Math.floor(dimIndex / props.columns);
      const colIndex = dimIndex % props.columns;

      // 计算标签位置
      const labelPercent = (props.labelHeight / containerHeight.value) * 100;
      const chartPercent = (props.chartHeight / containerHeight.value) * 100;
      const topPercent = 10 + rowIndex * 2 * (labelPercent + chartPercent);

      return {
        type: "text",
        left: `${
          colIndex * (100 / props.columns) + 100 / props.columns / 2 - 3
        }%`,
        top: `${topPercent}%`,
        style: {
          text: dim,
          fontSize: 16,
          fontWeight: 700,
          fill: "#666",
          textAlign: "center",
        },
      };
    }),

    // graphic: dimensions.value.map((dim, dimIndex) => {
    //   const grid = grids[dimIndex];
    //   if (!grid) return null;

    //   // 解析grid定位数据（去除%符号）
    //   const gridLeft = parseFloat(grid.left);
    //   const gridWidth = parseFloat(grid.width);
    //   const gridTop = parseFloat(grid.top);

    //   // 计算水平中心：grid左边缘 + grid宽度的一半
    //   const centerX = gridLeft + gridWidth / 2;

    //   // 计算垂直位置：grid顶部 - 标签行高度的一半
    //   const labelY = gridTop - labelPercent;

    //   return {
    //     type: "text",
    //     left: `${centerX}%`, // 水平中心点
    //     top: `${labelY}%`, // 垂直中心点
    //     style: {
    //       text: dim,
    //       fontSize: 16, // 适当减小字号避免溢出
    //       fontWeight: 700,
    //       fill: "#666",
    //       textAlign: "center", // 文本水平居中
    //       textBaseline: "middle", // 文本垂直居中
    //     },
    //     z: 100, // 确保文本在最上层
    //   };
    // }),

    // Grid配置
    grid: getGridConfig(),

    // X轴配置
    xAxis: getXAxisConfig(),

    // Y轴配置
    yAxis: getYAxisConfig(),

    // 系列配置
    series: transformDataForSeries().map((series, index) => ({
      ...series,
      itemStyle: {
        color: props.colors[index % props.colors.length],
      },
    })),

    // 提示框
    tooltip: {
      show: true,
      trigger: "axis",
      formatter: (params) => {
        if (!params || params.length === 0) return "";
        const dimensionIndex = params[0].seriesIndex;
        const dimensionName = dimensions.value[dimensionIndex];
        let html = `<div style="font-weight:bold;margin-bottom:5px;">${dimensionName}${props.rateName}</div>`;
        params.forEach((param) => {
          html += `<div style="display:flex;justify-content:space-between;margin:2px 0;">
              <span>${param.name}:</span>
              <span style="font-weight:bold;">${param.value}%</span>
            </div>`;
        });
        return html;
      },
    },

    animation: true,
    animationDuration: 800,
    responsive: true,
  };
};

// ==================== 图表初始化 ====================
const initChart = async () => {
  if (!chartRef.value) return;

  // 销毁旧实例
  if (chartInstance) {
    chartInstance.dispose();
  }

  // 创建新实例
  chartInstance = echarts.init(chartRef.value);

  // 设置option
  const option = getChartOption();
  chartInstance.setOption(option, true);

  // 监听窗口大小变化
  window.addEventListener("resize", handleResize);
};

// ==================== 窗口大小变化处理 ====================
const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

// ==================== 生命周期 ====================
onMounted(() => {
  // console.log(props.data);
  nextTick(() => {
    initChart();
  });
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  window.removeEventListener("resize", handleResize);
});

// ==================== 监听数据变化 ====================
watch(
  () => [props.data, props.columns, props.chartHeight],
  () => {
    nextTick(() => {
      initChart();
    });
  },
  { deep: true }
);

// ==================== 暴露方法 ====================
defineExpose({
  resize: handleResize,
  getChartInstance: () => chartInstance,
});
</script>
  
  <style scoped>
.sparkline-matrix-container {
  width: 100%;
  padding: 10px;
  box-sizing: border-box;
  background: #fff;
  border-radius: 8px;
  /* box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1); */
}

.sparkline-chart {
  width: 100%;
  /* height: 500px; */
}
</style>