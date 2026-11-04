<template>
  <div ref="chartRef" :key="chartKey" class="chart"></div>
</template>

<script setup>
import {ref, onMounted, watch, onBeforeUnmount, nextTick, onUpdated, onActivated} from "vue";
import * as echarts from 'echarts/core';
import {
  DatasetComponent,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  VisualMapComponent,
  LegendComponent,
  TransformComponent
} from 'echarts/components';
import {ScatterChart, LineChart} from 'echarts/charts';
import {UniversalTransition, LabelLayout} from 'echarts/features';
import {CanvasRenderer} from 'echarts/renderers';

echarts.use([
  DatasetComponent,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  VisualMapComponent,
  LegendComponent,
  TransformComponent,
  ScatterChart,
  LineChart,
  CanvasRenderer,
  UniversalTransition,
  LabelLayout
]);
echarts.registerTransform(ecStat.transform.regression);

import ecStat from 'echarts-stat';

const chartRef = ref(null);
let chartInstance = null;

const chartKey = ref(0);
const isSmallScreen = ref(false);

const props = defineProps({
  data: {
    type: Array,
    required: true,
  },
  title: {
    type: String,
    default: "",
  },
  width: {
    type: [String, Number],
    default: "100%",
  },
  height: {
    type: [String, Number],
    default: "400px"
  },
  xData: {
    type: Array,
    required: true,
  },
  yData: {
    type: Array,
    required: true,
  },
});

function formatExcelDate(excelSerial) {
  // Excel日期起点是1900-01-01，而JS是1970-01-01
  const offset = 25569; // 1900-01-01到1970-01-01的天数
  const utcDate = new Date((excelSerial - offset) * 86400 * 1000);
  return utcDate.toISOString().split('T')[0]; // 返回YYYY-MM-DD格式
}

function isPredict(modelDay) {
  // 创建一个 Date 对象，获取当前时间
  const now = new Date();
  // 创建一个 Date 对象，表示 1900-01-01
  const epoch = new Date(1900, 0, 1); // 月份从 0 开始，0 表示 1 月
  // 获取当前时间和 1900-01-01 的时间戳（毫秒数）
  const nowTimestamp = now.getTime();
  const epochTimestamp = epoch.getTime();
  // 计算时间戳差值（毫秒数）
  const diffMilliseconds = nowTimestamp - epochTimestamp;
  // 将毫秒数转换为天数，手动调整2天，避免当天判断失效
  const diffDays = Math.floor(diffMilliseconds / (1000 * 60 * 60 * 24)) + 2;
  return diffDays < modelDay;
}

/**
 * 计算两个字符串的共同前缀长度
 */
function commonPrefixLength(str1, str2) {
  const s1 = str1.toLowerCase();
  const s2 = str2.toLowerCase();
  let i = 0;
  const len = Math.min(s1.length, s2.length);
  while (i < len && s1[i] === s2[i]) {
    i++;
  }
  return i;
}

/**
 * 判断模型名是否包含受保护的关键词（deepseek、qwen、glm）
 */
function isProtectedKeyword(modelName) {
  if (!modelName) return false;
  const lower = modelName.toLowerCase();
  return lower.includes('deepseek') || lower.includes('qwen') || lower.includes('glm');
}

/**
 * 数据筛选函数：剔除导致散点过于密集的冗余数据点
 * 
 * 筛选规则：
 * 1. 时间窗口（一个月/30天）内，存在多个分数接近（分差<=20）的模型，保留最高分
 *    → 对 deepseek/qwen/glm 模型不生效（这些模型不受规则1剔除）
 * 2. 同一类型模型（共同前缀长度>5）且分数接近（分差<=20），只保留最高分
 *    → 对 deepseek/qwen/glm 模型也生效（这些模型之间也会被规则2筛选）
 * 3. 闭源模型最高分和开源模型最高分必须保留（不受剔除规则影响）
 * 
 * @param {Array} sourceData - 原始数据 [[time, score, model, type], ...]
 * @returns {Array} 筛选后的数据
 */
function filterDenseScatterData(sourceData) {
  if (!sourceData || sourceData.length === 0) return sourceData;

  // 按类型分组
  const grouped = {};
  for (const point of sourceData) {
    const type = point[3]; // '闭源' or '开源'
    if (!grouped[type]) grouped[type] = [];
    grouped[type].push(point);
  }

  const keptPoints = [];

  for (const type of Object.keys(grouped)) {
    const points = grouped[type];
    if (points.length <= 1) {
      keptPoints.push(...points);
      continue;
    }

    // 找出该类型中的最高分
    const sortedByScore = [...points].sort((a, b) => b[1] - a[1]);
    const maxScore = sortedByScore[0][1];

    // 标记绝对保护模型：只有最高分模型绝对保护
    // deepseek/qwen/glm 模型不再绝对保护，它们会受到规则2（同前缀）的筛选
    // 但它们不受规则1（时间窗口）的剔除
    const absolutelyProtectedSet = new Set();
    for (const point of points) {
      // 最高分模型绝对保护
      if (point[1] === maxScore) {
        absolutelyProtectedSet.add(point[2]);
      }
    }

    // 按分数从高到低排序，依次判断是否保留
    // 高分模型优先保留，低分模型检查是否被"覆盖"
    const candidates = [...points].sort((a, b) => b[1] - a[1]);
    const retained = []; // 已决定保留的模型

    for (const point of candidates) {
      const modelName = point[2];
      const score = point[1];
      const time = point[0];
      const isKeywordModel = isProtectedKeyword(modelName);

      // 绝对保护模型（最高分）直接保留
      if (absolutelyProtectedSet.has(modelName)) {
        retained.push(point);
        continue;
      }

      // 检查是否应该被剔除
      let shouldRemove = false;

      for (const retainedPoint of retained) {
        const retainedName = retainedPoint[2];
        const retainedScore = retainedPoint[1];
        const retainedTime = retainedPoint[0];
        const scoreDiff = retainedScore - score;

        // 只有当保留的模型分数 >= 当前模型时，才可能剔除当前模型
        if (scoreDiff < 0) continue;

        // 规则1：时间窗口（30天）内，分数差<=20
        // → 对 deepseek/qwen/glm 模型不生效
        if (!isKeywordModel) {
          const timeDiff = Math.abs(retainedTime - time);
          if (timeDiff <= 30 && scoreDiff <= 20) {
            shouldRemove = true;
            break;
          }
        }

        // 规则2：共同前缀长度>5，分数差<=20
        // → 对 deepseek/qwen/glm 模型也生效
        if (scoreDiff <= 24) {
          const prefixLen = commonPrefixLength(modelName, retainedName);
          if (prefixLen > 6) {
            shouldRemove = true;
            break;
          }
        }
      }

      if (!shouldRemove) {
        retained.push(point);
      }
    }

    keptPoints.push(...retained);
  }

  return keptPoints;
}

/**
 * Pre-compute which model labels should be hidden due to overlap.
 *
 * Groups points by (x-time, y-score) proximity. Within each group,
 * only the highest-scoring model(s) get to show their label — the
 * rest are hidden (except deepseek/qwen/glm models, which always show).
 *
 * Returns a Set of model-name strings to hide.
 */
function computeHiddenLabels(sourceData, scoreThreshold = 50) {
  const hidden = new Set();

  // Cluster: points whose x AND y are both close
  const clusters = [];
  const sorted = [...sourceData].filter(d => d[2]).sort((a, b) => b[1] - a[1]);

  for (const point of sorted) {
    let added = false;
    for (const c of clusters) {
      // Same time-series typically means same or adjacent Excel-serial date
      // x dimension is time (excel serial), y is score
      if (Math.abs(c.repX - point[0]) <= 5 && Math.abs(c.repScore - point[1]) <= scoreThreshold) {
        c.points.push(point);
        added = true;
        break;
      }
    }
    if (!added) {
      clusters.push({ repX: point[0], repScore: point[1], points: [point] });
    }
  }

  for (const cluster of clusters) {
    if (cluster.points.length < 2) continue;
    // Keep the highest-scored one visible, hide the rest
    // But never hide deepseek/qwen/glm models
    for (let i = 1; i < cluster.points.length; i++) {
      const p = cluster.points[i];
      const name = p[2];
      if (isProtectedKeyword(name)) continue;
      hidden.add(name);
    }
  }

  return hidden;
}

function buildOptions() {
  if (!chartInstance || !chartRef.value) return;
  const dimensions = ['time', 'score', 'model', 'type']

  // 应用数据筛选，剔除密集散点
  const filteredData = filterDenseScatterData(props.data || []);

  // Pre-compute hidden labels (基于筛选后的数据)
  const src = filteredData;
  const hiddenClosed = computeHiddenLabels(src.filter(d => d[3] === '闭源'));
  const hiddenOpen   = computeHiddenLabels(src.filter(d => d[3] === '开源'));

  const options = {
    dataset: [
      // 原始数据集 (索引0) - 使用筛选后的数据
      {dimensions: dimensions, source: filteredData},

      // 闭源数据过滤 (索引1)
      {transform: {type: 'filter', config: {dimension: 3, eq: '闭源'}}},

      // 开源数据过滤 (索引2)
      {transform: {type: 'filter', config: {dimension: 3, eq: '开源'}}},

      // 闭源回归变换 (新增索引3) - 使用对数(log)回归
      {
        fromDatasetIndex: 1,  // 指向闭源数据集
        transform: {
          type: 'ecStat:regression',
          config: {method: 'logarithmic'}
        }
      },

      // 开源回归变换 (新增索引4) - 使用对数(log)回归
      {
        fromDatasetIndex: 2,  // 指向开源数据集
        transform: {
          type: 'ecStat:regression',
          config: {method: 'logarithmic'}
        }
      }
    ],
    title: {
      text: props.title,
      top: '3%',
      left: 'center'
    },
    legend: {
      show: true,
      orient: 'vertical',
      data: [
        {
          name: '闭源',
          icon: 'circle',
          itemStyle: {color: 'rgb(255,115,0)'},
          textStyle: {color: 'rgb(255,115,0)'}
        },
        {
          name: '开源',
          icon: 'rect',
          itemStyle: {color: 'rgb(51, 126, 204)'},
          textStyle: {color: 'rgb(51, 126, 204)'}
        },
        // { name: '闭源拟合线', itemStyle: { color: 'rgb(196, 86, 86)' }, textStyle: { color: 'rgb(196, 86, 86)' } },
        // { name: '开源拟合线', itemStyle: { color: 'rgb(51, 126, 204)' }, textStyle: { color: 'rgb(51, 126, 204)' } },
      ],
      itemWidth: 14, // 设置图例图标的宽度
      itemHeight: 14, // 设置图例图标的高度
      itemGap: 16,
      top: '15%',
      left: '8%',
      formatter: (params) => {
        return params === '闭源' ? '闭源模型' : '开源模型'
      },
      borderWidth: 1,
      borderRadius: 10,
      padding: 16,
      textStyle: {
        fontSize: 16,
        padding: [0, 20]
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {type: 'line'},
      formatter: function (params) {
        let tip = "";
        if (isPredict(params[0].value[0])) {
          tip += "预测值<br/>"
        }
        tip += formatExcelDate(params[0].value[0]) + '<br/>';
        params.forEach(item => {
          if (!item.seriesName.startsWith('闭源拟合') && !item.seriesName.startsWith('开源拟合')) {
            tip += `${item.value[2]}: ${item.value[1]}<br/>`;
          }
        });
        return '<strong>' + tip + '</strong>';
      }
    },
    grid: {
      top: '10%',
      bottom: '10%',
      left: '5%',
      right: '5%'
    },
    xAxis: {
      type: 'value',
      splitLine: { /* 原有配置 */},
      min: 'dataMin',
      max: 'dataMax',
      // 新增日期格式化
      axisLabel: {
        formatter: function (value) {
          return formatExcelDate(value);
        }
      },
      splitNumber: 10, // 刻度之间的分割段数
      axisPointer: {
        label: {
          formatter: function (params) {
            return formatExcelDate(params.value);
          }
        }
      }
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      },
      min: 1200,
      max: 'dataMax'
    },
    visualMap: {
      show: false,
      dimension: 2,
      min: 20000,
      max: 1500000000,
      seriesIndex: [0, 1],
      inRange: {
        // symbolSize: [10, 70]
      }
    },
    series: [
      {
        name: '闭源',
        type: 'scatter',
        datasetIndex: 1,
        symbolSize: 6,
        label: {
          show: true, // 显示标签
          position: 'top', // 奇数索引显示在底部,
          fontSize: 10,
          distance: 8,
          formatter: (params) => {
            const name_value = params.value[2];
            const score_value = params.value[1];
            if (hiddenClosed.has(name_value)) return '';
            const all_value = `${name_value}`
            if (name_value === 'gemini-2.0' || name_value === 'claude-4.5' || name_value === 'grok-4.20') {
              return `{item_color_padding_left|${all_value}}`
            } else if (name_value === 'claude-opus-4-6-think') {
              return `{item_color_padding_left_more|${all_value}}`
            } else if(name_value.includes('GPT-5.2')){
              return `{item_color_padding_left_top|${all_value}}`
            } else if (name_value === 'gemini-3.1-pro' || name_value === 'gpt-5.5-high' || name_value.includes('Qwen3.7-Max-Preview')) {
              return `{item_color_padding_right|${all_value}}`
            } else if (name_value === 'gpt-5.1-high') {
              return `{item_color_padding_right_bottom|${all_value}}`
            } else if (name_value.toLowerCase() === 'claude fable 5') {
              return `{red|${all_value}}`;
            } else if (name_value === 'gpt-6') {
              return `{grey|${all_value}}`;
            }
            return `{item_color|${all_value}}`
          },
          rich: {
            // 定义富文本样式
            red: {
              color: 'red',
              fontWeight: 'bold',
              align: 'center',
              height: 15,
            },
            grey: {
              color: 'grey',
              align: 'center',
              height: 15,
            },
            black: {
              color: 'black',
              align: 'center'
            },
            item_color: {
              color: 'rgb(255,115,0)',
              align: 'center',
              height: 15,
            },
            item_color_padding_top: {
              padding: [-30, 0],
              color: 'rgb(255,115,0)',
              height: 15,
              align: 'center'
            },
            item_color_padding_right_bottom: {
              padding: [0, 0, -75, 80],
              color: 'rgb(255,115,0)',
              height: 90,
              align: 'center',
            },
            item_color_padding_right: {
              padding: [0, 0, 0, 80],
              color: 'rgb(255,115,0)',
              height: 15,
              align: 'center',
            },
            item_color_padding_left: {
              padding: [0, 100, -45, 0],
              height: 60,
              color: 'rgb(255,115,0)',
              align: 'center'
            },
            item_color_padding_left_more: {
              padding: [0, 160, -45, 0],
              height: 60,
              color: 'rgb(255,115,0)',
              align: 'center'
            },
            item_color_padding_left_top: {
              padding: [0, 80, -30, 0],
              height: 60,
              color: 'rgb(255,115,0)',
              align: 'center'
            }
          }
        },
        itemStyle: {
          color: (params) => {
            const name = params.value[2];
            // 灰色（预测模型）
            if (name === 'gpt-6') return 'grey';
            // 红色（闭源最高分）
            if (name.toLowerCase() === 'claude fable 5') return 'red';
            return 'rgb(255,115,0)';
          }
        }
      },
      {
        name: '开源',
        type: 'scatter',
        datasetIndex: 2,
        symbol: 'rect',
        symbolSize: 6,
        label: {
          show: true,
          fontSize: 10,
          distance: 10,
          position: 'bottom',
          formatter: (params) => {
            const name_value = params.value[2];
            const score_value = params.value[1];
            if (hiddenOpen.has(name_value)) return '';
            const all_value = `${name_value}`
            if (name_value === 'deepseek-coder-v2' || name_value === 'kimi-k2.5-think'|| name_value === 'qwen2.5-max' || name_value === 'qwen3-235b-a22b' || name_value === 'glm-5' || name_value === 'mimo-v2.5-pro') {
              return `{item_color_padding_top|${all_value}}`
            } else if (name_value === 'mimo-v2-pro') {
              return `{item_color_padding_left|${all_value}}`
            } else if (name_value === 'qwen3.6-plus') {
              return `{item_color_padding_right_bottom|${all_value}}`
            } else if (name_value === 'qwen3.5-max' || name_value === 'qwen3-max' ) {
              return `{item_color_padding_bottom_offset|${all_value}}`
            } else if (name_value.includes("deepseek-v4")) {
              return `{item_color_padding_right_bottom|${all_value}}`
            } else if (name_value.toLowerCase() === 'glm-5.1') {
              return `{red|${all_value}}`;
            } else if (name_value === 'qwen4' || name_value === 'deepseek-r2') {
              return `{grey|${all_value}}`;
            }
            return `{item_color|${all_value}}`
          },
          rich: {
            // 定义富文本样式
            red: {
              color: 'red',
              fontWeight: 'bold',
              align: 'center',
              height: 15,
            },
            grey: {
              color: 'grey',
              align: 'center',
              height: 15,
            },
            black: {
              color: 'black',
              align: 'center'
            },
            item_color: {
              color: 'rgb(51, 126, 204)',
              align: 'center',
              height: 15,
            },
            item_color_padding_top: {
              color: 'rgb(51, 126, 204)',
              align: 'center',
              height: 145,
              padding: [-105, 0, 0, 0]
            },
            item_color_padding_bottom_offset: {
              color: 'rgb(51, 126, 204)',
              align: 'center',
              height: 40,
              padding: [-20, 0, 0, 0]
            },
            item_color_padding_right_bottom: {
              padding: [-15, 0, 0, 60],
              color: 'rgb(51, 126, 204)',
              height: 30,
              align: 'center',
            },
            item_color_padding_right_middle: {
              padding: [-30, 0, 0, 130],
              color: 'rgb(51, 126, 204)',
              height: 30,
              align: 'center',
            },
            item_color_padding_left: {
              padding: [0, 0, 0, 0],
              height: 40,
              color: 'rgb(51, 126, 204)',
              align: 'center'
            }
          }
        },
        itemStyle: {
          color: (params) => {
            const name = params.value[2];
            // 灰色（预测模型）
            if (name === 'deepseek-v4' || name === 'qwen4' || name === 'deepseek-r2') return 'grey';
            // 红色（开源最高分，大小写不敏感）
            if (name.toLowerCase() === 'glm-5.1') return 'red';
            return 'rgb(51, 126, 204)';
          }
        }
      },
      {
        name: '闭源拟合线',
        type: 'line',
        smooth: true,
        datasetIndex: 3,  // 使用闭源回归数据集
        symbolSize: 0.1,
        symbol: 'circle',
        lineStyle: {
          color: 'rgb(255,115,0)'
        },
        itemStyle: {
          color: 'rgb(255,115,0)' // 设置 symbol 颜色
        }
      },
      {
        name: '开源拟合线',
        type: 'line',
        smooth: true,
        datasetIndex: 4,  // 使用开源回归数据集
        symbolSize: 0.1,
        symbol: 'rect',
        lineStyle: {
          color: 'rgb(51, 126, 204)'
        },
        itemStyle: {
          color: 'rgb(51, 126, 204)' // 设置 symbol 颜色
        }
      }
    ]
  };
  chartInstance.setOption(options);
}

const checkScreenWidth = () => {
  const newIsSmallScreen = window.innerWidth < 1500;
  // 如果屏幕状态发生变化，则更新并重建图表选项
  if (newIsSmallScreen !== isSmallScreen.value) {
    isSmallScreen.value = newIsSmallScreen;
    if (chartInstance) {
      buildOptions();
      chartInstance.resize();
    }
  } else {
    // 即使状态没变，也可能只是调整大小，需要重绘
    if (chartInstance) {
      chartInstance.resize();
    }
  }
};

onMounted(() => {
  chartInstance = echarts.init(chartRef.value);

  // 使用双重保障：
  // 立即尝试一次 + 延迟确保
  buildOptions();
  ensureChartSize();  // 新增的尺寸检查

  window.addEventListener("resize", checkScreenWidth);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", checkScreenWidth);
});

onUpdated(() => {
  if (chartInstance) {
    chartInstance.resize(); // 组件更新时重新调整尺寸
  }
});

watch(
  () => props.data,
  () => {
    buildOptions();
    ensureChartSize(); // 数据变化后也检查尺寸
  },
  {deep: true}
);

const ensureChartSize = () => {
  nextTick(() => {
    if (!chartRef.value || !chartInstance) return;

    // 检查容器是否可见且有有效尺寸
    const {offsetWidth, offsetHeight} = chartRef.value;
    if (offsetWidth > 10 && offsetHeight > 10) {
      chartInstance.resize();
    } else {
      // 延迟重试直到获得有效尺寸
      requestAnimationFrame(ensureChartSize);
    }
  });
};
onActivated(() => {
  ensureChartSize();
});
</script>

<style scoped>
.chart {
  width: 100%;
  height: 100%
}
</style>
