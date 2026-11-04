<template>
  <div ref="chartRef" class="chartBox" :key="chartKey"></div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed } from "vue";
import * as echarts from "echarts/core";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { PieChart } from "echarts/charts";
import { LabelLayout } from "echarts/features";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  TooltipComponent,
  LegendComponent,
  PieChart,
  CanvasRenderer,
  LabelLayout,
]);

const chartRef = ref(null);
let chartInstance = null;

const chartKey = ref(0);
const isSmallScreen = ref(false);

// 定义 props
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
    default: "400px",
  },
});

// 用于渲染的 option
const chartOptions = ref({});

const casesArr = ref([]);
const sum = ref(0);

// 构建 option 的函数
function buildOptions() {
  sum.value = 0;
  casesArr.value = props.data.map((item) => {
    // 1. 在数据处理阶段（reduce）集中处理和过滤
    const itemSum = item.data
      .map((obj) => obj.cases)
      .reduce((acc, num) => {
        // 核心逻辑：确保我们累加的是一个有效的数字
        if (num !== undefined && num !== "") {
          const convertedNum = Number(num);
          // 只有当转换结果为有效数字时才累加
          if (!isNaN(convertedNum)) {
            return acc + convertedNum;
          }
        }
        // 如果是无效值，则加上0，相当于忽略
        return acc + 0;
      }, 0); // 初始值0，保证即使item.data为空，itemSum也是0

    // 2. 构建 casesArr，此时的 itemSum 必然是有效数字或0
    return {
      title: item.title,
      sum: itemSum,
    };
  });

  // 3. 计算 sum.value
  // 此时 casesArr 中的所有 item.sum 都是可信的有效数字
  // 不需要再次检查，直接累加即可
  sum.value = casesArr.value.reduce((acc, item) => acc + item.sum, 0);

  if (!chartRef.value) return;

  chartInstance = echarts.init(chartRef.value);

  const total = props.data.reduce((sum, item) => sum + item.data.length, 0);

  const legendConfig = isSmallScreen.value
    ? {
        itemWidth: 10,
        itemHeight: 6,
        itemGap: 5,
        textStyle: { fontSize: 10 },
      }
    : {
        textStyle: { fontSize: 14 },
      };

  const fontSize = isSmallScreen.value ? 10 : 14;

  const data = props.data.map((item) => ({
    name: item.title,
    value: item.data.length,
  }));

  // 计算字符串的实际显示长度（汉字算2，其他算1）
  const getDisplayNameLength = (str) => {
    let length = 0;
    for (let i = 0; i < str.length; i++) {
      const charCode = str.charCodeAt(i);
      if (charCode >= 0x4e00 && charCode <= 0x9fa5) {
        // 汉字范围
        length += 2;
      } else {
        length += 1;
      }
    }
    return length;
  };

  // 计算最大长度
  let maxLength = 0;
  data.forEach((item) => {
    const displayNameLength = getDisplayNameLength(item.name);
    if (displayNameLength > maxLength) {
      maxLength = displayNameLength;
    }
  });

  // 格式化图例项
  const legendData = data.map((item) => {
    const name = item.name;
    const value = item.value;
    const percentage = ((value / total) * 100).toFixed(2);
    const padding = " ".repeat(maxLength - name.length);
    return `${name}${padding} - ${value} (${percentage}%)`;
  });

  const isOnlyOne = props.data.length === 1;

  const options = {
    tooltip: {
      trigger: "item",
      backgroundColor: "#909399",
      // formatter: "{b} : {c} ({d}%)",
      formatter: (params) => {
        const items = props.data.find((d) => d.title === params.name);
        // console.log("items");
        // console.log(items);
        const name = params.name;
        const value = params.value;
        const percent = params.percent;
        // HTML转义函数
        function escapeHtml(unsafe) {
          return unsafe
            .replace(/&/g, "&")
            .replace(/</g, "<")
            .replace(/>/g, ">")
            .replace(/"/g, '"')
            .replace(/'/g, "'");
        }

        const dataStrings =
          items.data.map((item) => {
            let str = escapeHtml(item.dataset); // 转义dataset
            if (item.cases !== undefined && item.cases !== "") {
              str += `<span>/</span><span style="color: rgb(217, 236, 255);">cases:${escapeHtml(
                item.cases
              )}</span>`; // 转义cases
            }
            return str;
          }) || [];
        const dataStringsStr = dataStrings.join("<br />");
        const fontSizeTitle = isSmallScreen.value ? "8px" : "16px";
        return `
        <div style="font-size: ${fontSizeTitle}; font-weight: bold; color: #fff;">
          ${name}
          ${value} (${percent}%)
        </div>
        </div>
        <div style="font-size: ${fontSizeTitle}; color: #fff;">
          ${dataStringsStr}
        </div>`;
      },
    },
    legend: {
      ...legendConfig,
      orient: "vertical",
      right: "75%",
      top: "center",
      // textStyle: { fontFamily: "Microsoft YaHei",fontWeight:600 },
      // formatter: function (name) {
      //   const item = data.find((d) => d.name === name);
      //   const value = item.value;
      //   const percentage = ((value / total) * 100).toFixed(2);
      //   const displayNameLength = getDisplayNameLength(name);
      //   const diff = maxLength - displayNameLength;
      //   // console.log(name);
      //   // console.log(displayNameLength);
      //   let paddingCount;
      //   if (diff > 0) {
      //     paddingCount = 2 * diff - 1;
      //   }
      //   const padding = " ".repeat(paddingCount);
      //   return `${name}${padding} - ${value} (${percentage}%)`;
      // },
    },

    series: [
      {
        name: props.title,
        type: "pie",
        radius: ["30%", "50%"],
        center: ["60%", "50%"],
        avoidLabelOverlap: false,
        padAngle: isOnlyOne ? 0 : 1,
        labelLine: {
          show: false,
        },
        label: {
          show: true,
          position: "center",
          formatter: `总计：${total}\n用例总数：${sum.value}`,
          fontSize: fontSize,
          fontWeight: "bold",
        },
        emphasis: {
          focus: "self",
          label: {
            show: true,
            fontSize: fontSize,
            fontWeight: "bold",
            formatter: function (params) {
              let caseNum = casesArr.value.find((item) => {
                return params.name === item.title;
              });
              caseNum.sum = !caseNum.sum ? 0 : caseNum.sum;
              // 只在鼠标移上时显示具体数值
              return `${params.name}：${params.value}\n用例数：${caseNum.sum}`;
            },
          },
        },
        data: props.data.map((item) => ({
          name: item.title,
          value: item.data.length,
        })),
      },
      {
        name: "Label Series",
        type: "pie",
        radius: ["30%", "50%"],
        center: ["60%", "50%"],
        labelLine: {
          length: 30,
          lineStyle: {
            color: "#000",
          },
          minTurnAngle: 90,
          // maxSurfaceAngle:45,
          length: isSmallScreen.value ? 20 : 35,
          length2: isSmallScreen.value ? 30 : 40,
        },
        label: {
          formatter: function (params) {
            // 获取当前项的数据
            const items = props.data.find((d) => d.title === params.name);
            const percent = params.percent;
            const count = items.data.length;
            if (items) {
              // 生成字符串数组
              items.data.forEach((item) => {
                // console.log(item);
              });
              let dataStrings = "";
              if (items.data.length > 3) {
                dataStrings =
                  items.data[0].dataset +
                  // (items.data[0].dataset.cases !== undefined &&
                  // items.data[0].dataset.cases !== ""
                  //   ? ":" + items.data[0].dataset.cases
                  //   : "") +
                  "\n" +
                  items.data[1].dataset +
                  // (items.data[0].dataset.cases !== undefined &&
                  // items.data[0].dataset.cases !== ""
                  //   ? ":" + items.data[1].dataset.cases
                  //   : "") +
                  "\n" +
                  "...";
                // console.log(dataStrings);
              } else {
                dataStrings = items.data
                  .map(
                    (d) => d.dataset.toString()
                    //+ (d.cases !== undefined && d.cases !== ""
                    //   ? ":" + d.cases
                    //   : "")
                  )
                  .join("\n");
              }
              return `{b|${params.name} ${count}(${percent}%)}{abg|}\n{hr|}\n{d|${dataStrings}}`;
            }
            return "";
          },
          // rotate:30,
          // alignTo: "labelLine",
          backgroundColor: "#F6F8FC",
          borderColor: "#8C8D8E",
          borderWidth: 1,
          borderRadius: 4,
          rich: {
            hr: {
              borderColor: "#8C8D8E",
              width: "100%",
              borderWidth: 1,
              height: 0,
            },
            b: {
              fontSize: isSmallScreen.value ? 8 : 12,
              color: "#000",
              fontWeight: 600,
              lineHeight: 22,
              align: "center",
            },
            d: {
              fontSize: isSmallScreen.value ? 8 : 12,
              color: "rgb(115, 118, 122)",
              lineHeight: isSmallScreen.value ? 15 : 22,
              align: "center",
              fontWeight: 600,
              padding: [10, 10, 10, 10],
            },
          },
        },
        itemStyle: {
          color: "rgba(0, 0, 0, 0)",
        },
        data: props.data.map((item) => ({
          name: item.title,
          value: item.data.length,
        })),
      },
    ],
  };
  chartInstance.setOption(options);

  chartInstance.on("mouseover", { seriesName: "Label Series" }, (params) => {
    var name = params.data.name; //获取顶层高亮的item名称
    chartInstance.dispatchAction({
      type: "highlight", //高亮
      seriesName: props.title, //底层系列名称
      name: name, //底层要高亮的item的名称
    });
  });
  chartInstance.on("mouseout", { seriesName: "Label Series" }, (params) => {
    var name = params.data.name;
    chartInstance.dispatchAction({
      type: "downplay",
      seriesName: props.title,
      name: name,
    });
  });

  // chartInstance.on("mouseover", { seriesName: props.title }, (params) => {
  //   var name = params.data.name; //获取顶层高亮的item名称
  //   chartInstance.dispatchAction({
  //     type: "highlight", //高亮
  //     seriesName: "Label Series", //底层系列名称
  //     name: name, //底层要高亮的item的名称
  //   });
  // });
  // chartInstance.on("mouseout", { seriesName: props.title }, (params) => {
  //   var name = params.data.name;
  //   chartInstance.dispatchAction({
  //     type: "downplay",
  //     seriesName: "Label Series",
  //     name: name,
  //   });
  // });

  return options;
}

// 初始赋值
chartOptions.value = buildOptions();

// 监控 props 变化，自动更新
watch(
  //   () => [props.dimensions, props.data, props.maxValue, props.title],
  () => {
    chartOptions.value = buildOptions();
  },
  { deep: true }
);

const checkScreenWidth = () => {
  isSmallScreen.value = window.innerWidth < 1500;
  chartKey.value++;
};

onMounted(async () => {
  checkScreenWidth();
  window.addEventListener("resize", checkScreenWidth);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", checkScreenWidth);
});
</script>

<style scoped>
.chartBox {
  /* margin-top: 20px; */
  height: calc(100% - 24px) !important;
  width: 100%;
  z-index: 10;
}

.chartBox :deep(div:first-child) {
  z-index: 10;
}

.chartBox :deep(canvas) {
  z-index: 10;
}
</style>