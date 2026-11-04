<template>
  <div ref="chartRef" class="chart"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import * as echarts from "echarts";

import { ModelService } from "@/services/modelService.js";

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  title: {
    type: String,
    default: "",
  },
});

const chartRef = ref(null);
let chartInstance = null;

// 排名对应的渐变色对
const RANK_GRADIENTS = [
  [
    ["#FFE680", "#FFB300"],
    ["#FFF0B3", "#FFC107"],
  ],
  [
    ["#E0E0E0", "#9E9E9E"],
    ["#F5F5F5", "#BDBDBD"],
  ],
  [
    ["#E8A87C", "#BF6B3A"],
    ["#F0C9A8", "#CD7F32"],
  ],
  [
    ["#7EA8F0", "#3B6FC6"],
    ["#A8C4F5", "#5470C6"],
  ],
  [
    ["#A8E6A0", "#5CB85C"],
    ["#C5F0BF", "#7BC77B"],
  ],
  [
    ["#FFE082", "#FFB74D"],
    ["#FFECB3", "#FFC107"],
  ],
  [
    ["#FF9E9E", "#E53935"],
    ["#FFCDD2", "#EF5350"],
  ],
  [
    ["#81D4FA", "#29B6F6"],
    ["#B3E5FC", "#4FC3F7"],
  ],
  [
    ["#A5D6A7", "#43A047"],
    ["#C8E6C9", "#66BB6A"],
  ],
  [
    ["#FFB74D", "#F57C00"],
    ["#FFCC80", "#FB8C00"],
  ],
];

const barColors = [
  "rgb(31, 31, 31)",
  "rgb(28, 127, 248)",
  "rgb(52, 168, 83)",
  "rgb(235, 53, 104)",
  "rgb(34, 67, 230)",
  "rgb(0, 137, 244)",
  "rgb(255, 112, 24)",
  "rgb(134, 183, 55)",
  "rgb(255, 153, 0)",
  "rgb(4, 122, 254)",
];

const getLogoUrl = (name) => {
  return ModelService.getModelIcon(name);
};

const getBarColor = (index, item) => {
  // 如果数据项自带 color 字段则优先使用
  if (item && item.color) return item.color;
  // fallback 到按索引分配
  if (index < barColors.length) {
    return barColors[index];
  } else {
    return barColors[0];
  }
};

// ── 图表渲染 ────────────────────────────────────────────────

const updateChart = () => {
  const names = props.data.map((item) => item.name);
  const values = props.data.map((item) => item.value * 100);

  // 为第二个 series（图标层）生成纯图标 rich 样式
  const iconRichStyles = {};
  names.forEach((name, i) => {
    const styleName = `icon_${i}`;
    const logoUrl = getLogoUrl(name);
    iconRichStyles[styleName] = {
      width: 22,
      height: 22,
      align: "center",
      verticalAlign: "middle",
      backgroundColor: {
        image: typeof logoUrl === "string" ? logoUrl : logoUrl,
      },
    };
  });
  // 计算 barWidth：以 10 条数据时的宽度为基准，动态适配
  // 10 条时 barWidth = containerWidth / 10 * 0.6，此处用百分比近似
  const barWidth = Math.max(
    8,
    Math.min(10, (100 / props.data.length) * 0.6 + "%")
  );

  const option = {
    title: {
      text: props.title,
      textStyle: { fontSize: 16, fontWeight: 600, color: "#1d2129" },
      left: "center",
      top: 0,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const p = params[0];
        return `${p.name}<br/>均分: ${p.value.toFixed(2)}`;
      },
    },
    grid: {
      left: "10%",
      right: "5%",
      bottom: "32%",
      top: 30,
      containLabel: false,
    },
    xAxis: {
      type: "category",
      data: names,
      boundaryGap: true,
      axisLabel: {
        fontSize: 12,
        rotate: 60,
        margin: 55,
        formatter: (name) => {
          // 从第11个字符开始检查，遇到'-'且之后超过14个字符则在'-'后换行
          // 保证以'-'之后进行换行，同时保证一行字符不超过14个
          if (name.length <= 14) return name;

          let result = "";
          let lineStart = 0;

          while (lineStart < name.length) {
            // 剩余长度不超过14，直接追加
            if (name.length - lineStart <= 14) {
              result += name.slice(lineStart);
              break;
            }

            // 从第11个字符位置开始查找'-'
            let searchStart = lineStart + 7; // 第11个字符的索引（0-based）
            let breakPoint = -1;

            while (searchStart < name.length && searchStart - lineStart < 14) {
              if (name[searchStart] === "-") {
                // 检查从下一位置到行尾或下一个换行点是否超过14个字符
                // 即：当前行已用 searchStart - lineStart + 1 个字符（包含'-'）
                // 如果保留'-'在本行，本行字符数为 searchStart - lineStart + 1
                // 这个数量一定<=14（因为循环条件）
                // 关键判断：'-'之后的内容如果放到本行是否会超限
                // 实际上，我们在'-'处换行，'-'保留在本行
                // 本行长度 = searchStart - lineStart + 1，一定<=14
                breakPoint = searchStart;
                break;
              }
              searchStart++;
            }

            // 如果找到了合适的'-'换行点
            if (breakPoint !== -1) {
              result += name.slice(lineStart, breakPoint + 1) + "\n";
              lineStart = breakPoint + 1;
            } else {
              // 没找到合适的'-'，直接在14个字符处截断
              result += name.slice(lineStart, lineStart + 14) + "\n";
              lineStart += 14;
            }
          }

          return result.trim();
        },
      },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      max: 100,
      axisLabel: {
        show: false, // 不显示左侧的数值标签
      },
      splitLine: {
        show: true, // 显示横向的网格线（默认就是 true）
      },
    },
    series: [
      {
        // series 1：柱状图 + 顶部数值 label
        type: "bar",
        barWidth: props.data.length * + 7 + "%",
        data: values.map((v, i) => ({
          value: v,
          itemStyle: { color: getBarColor(i, props.data[i]) },
        })),
        label: {
          show: true,
          position: "top",
          fontSize: 11,
          formatter: (p) => p.value.toFixed(2),
        },
        borderRadius: [4, 4, 0, 0],
        itemStyle: {
          barBorderRadius: [5, 5, 0, 0], // [上左, 上右, 下右, 下左]
        },
      },
      {
        // series 2：与 series 1 完全重叠，仅用于展示底部 logo label
        type: "bar",
        barGap: "-100%",
        barWidth: props.data.length * +8 + "%",
        data: values.map((v, i) => ({
          value: v,
          itemStyle: { color: "transparent" },
        })),
        label: {
          show: true,
          position: "bottom",
          offset: [0, 10],
          formatter: (params) => {
            const i = names.indexOf(params.name);
            return `{icon_${i}|}`;
          },
          rich: iconRichStyles,
        },
        itemStyle: {
          barBorderRadius: [5, 5, 0, 0], // [上左, 上右, 下右, 下左]
        },
      },
    ],
  };

  chartInstance.setOption(option);
};

// ── 生命周期 ────────────────────────────────────────────────

const initChart = () => {
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value);
  }
  updateChart();
};

onMounted(() => {
  initChart();
  window.addEventListener("resize", handleResize);
});

watch(
  () => props.data,
  () => {
    if (chartInstance) updateChart();
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
.chart {
  width: 100%;
  height: 100%;
}
</style>
