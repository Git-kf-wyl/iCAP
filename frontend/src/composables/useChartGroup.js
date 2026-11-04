/**
 * useChartGroup — 管理单个 chart group 的状态逻辑
 *
 * 每个 chart group 独立管理：
 *  - 对比模型列表 & 选中值
 *  - 测试集选中值
 *  - 图表数据构建（雷达图 + 柱状图）
 *  - 全选/反选逻辑
 *  - 颜色映射
 */
import { ref, computed } from "vue";
import { ElMessage } from "element-plus";
import { DATASET_MAPPING } from "@/stores/rankingStore";

const CHART_COLORS = [
  "#00ffff",
  "#008000",
  "#ffa500",
  "#800080",
  "#ff00ff",
  "#008080",
  "#808000",
  "#ff9999",
  "#ffff00",
];

/**
 * 创建单个 chart group 的状态
 * @param {object} groupConfig - CHART_GROUPS 中的一项配置
 * @param {object} options
 * @param {string} options.currentModelName - 当前模型的名称
 * @param {import("vue").Ref<object>} options.allDataRef - 全局加载的原始数据 { llm: {ruler1, ruler2}, multimodal: {ruler1, ruler2} }
 * @param {import("vue").Ref<object>} options.globalColorMap - 全局颜色映射 { [modelName]: color }
 * @param {import("vue").Ref<number>} options.globalColorIndex - 全局颜色索引
 */
export function useChartGroup(groupConfig, { currentModelName, allDataRef, globalColorMap, globalColorIndex }) {
  // ===== 状态 =====
  const selectValue = ref([]);           // 选中的对比模型列表
  const models = ref([]);                // 可选模型列表 [{ value, label, disabled }]
  const selectDatasetValue = ref([]);    // 选中的测试集列表
  const chartData = ref([]);             // 图表数据 [{ data: [{data, dimension}], title, color }]
  const titles = ref([]);                // 图例标题 [{ title, color }]
  const checkAll = ref(false);
  const indeterminate = ref(false);
  const isInited = ref(false);           // 是否已初始化

  // CN 维度映射（仅 ruler2 gaixie 场景使用）
  const CNdimensions = ref([]);

  // ===== 计算属性 =====
  const dimensions = computed(() => groupConfig.dimensions);
  const isRuler1 = groupConfig.rulerType === "ruler1";
  const isRuler2 = groupConfig.rulerType === "ruler2";
  const dataSource = groupConfig.dataSource; // "llm" | "multimodal"

  // ===== 获取该组数据 =====
  function getGroupRawData() {
    const source = allDataRef.value[dataSource];
    if (!source) return null;
    return isRuler1 ? (source.ruler1 || null) : (source.ruler2 || null);
  }

  // ===== 标准化 key 匹配 =====
  function normalize(s) {
    return (s || "").toLowerCase().replace(/_/g, "-");
  }

  // ===== 颜色分配 =====
  function getColorForModel(modelName) {
    if (globalColorMap.value[modelName]) {
      return globalColorMap.value[modelName];
    }
    const color = CHART_COLORS[globalColorIndex.value % CHART_COLORS.length];
    const colorWithOpacity = `${color}40`;
    globalColorIndex.value++;
    globalColorMap.value[modelName] = colorWithOpacity;
    return colorWithOpacity;
  }

  // ===== 初始化模型列表 =====
  function initModels() {
    const rawData = getGroupRawData();
    if (!rawData) return false;

    const allKeys = Object.keys(rawData);
    // 过滤：只在当前 group 有实际分数的模型才加入
    const validKeys = allKeys.filter((key) => {
      if (isRuler1) {
        return rawData[key].result.some(
          (d) => d.score > 0 && dimensions.value.includes(d.dataset_name)
        );
      } else {
        // Ruler2: 检查指定场景下是否有分数
        const scene = groupConfig.scene;
        const result = rawData[key].result || [];
        return result.some(
          (r) =>
            r.dataset_name === scene &&
            r.metrics?.length > 0 &&
            r.metrics[0].categories?.[0]?.subsets?.some((sub) => sub.score > 0)
        );
      }
    });

    models.value = validKeys.map((key) => ({
      value: key,
      label: key,
      disabled: key === currentModelName,
    }));

    // 当前模型排在第一位
    const idx = models.value.findIndex((m) => m.value === currentModelName);
    if (idx !== -1) {
      const m = models.value.splice(idx, 1)[0];
      models.value.unshift(m);
    }

    // 默认选中的测试集
    selectDatasetValue.value = [...groupConfig.defaultDimensions];

    // 初始颜色：当前模型固定为 #0000ff40
    globalColorMap.value[currentModelName] = "#0000ff40";

    // 当前模型默认选中
    selectValue.value = [currentModelName];

    return validKeys.length > 0;
  }

  // ===== 构建 Ruler1 图表数据 =====
  function buildRuler1ChartData() {
    const rawData = getGroupRawData();
    console.log('buildRuler1ChartData')
    console.log(rawData)
    if (!rawData) return;

    const newChartData = [];
    const newTitles = [];

    selectValue.value.forEach((item) => {
      const matchKey = Object.keys(rawData).find(
        (key) => normalize(key) === normalize(item)
      );
      const label = matchKey || item;
      const tempData = [];

      const activeDimensions =
        selectDatasetValue.value.length > 0
          ? selectDatasetValue.value
          : dimensions.value;

      activeDimensions.forEach((dim) => {
        let found = false;
        if (matchKey) {
          const ds = rawData[matchKey].result.find(
            (d) => d.dataset_name === dim
          );
          if (ds && ds.score > 0) {
            found = true;
            tempData.push({
              data: (ds.score * 100).toFixed(2),
              dimension: dim,
            });
          }
        }
        if (!found) {
          tempData.push({ data: 0, dimension: dim });
        }
      });

      newChartData.push({
        data: tempData,
        title: label,
        color: getColorForModel(label),
      });
      newTitles.push({
        title: label,
        color: globalColorMap.value[label],
      });
    });

    chartData.value = newChartData;
    titles.value = newTitles;
    console.log(chartData.value)
  }

  // ===== 构建 Ruler2 图表数据 =====
  function buildRuler2ChartData() {
    const rawData = getGroupRawData();
    if (!rawData) return;

    const scene = groupConfig.scene;
    if (!scene) return;

    const newChartData = [];
    const newTitles = [];

    selectValue.value.forEach((item) => {
      const matchKey = Object.keys(rawData).find(
        (key) => normalize(key) === normalize(item)
      );
      const label = matchKey || item;
      const tempData = [];
      const activeDimensions =
        selectDatasetValue.value.length > 0
          ? selectDatasetValue.value
          : dimensions.value;

      if (dataSource === "llm") {
        // LLM Ruler2（改写场景/意图场景/记忆场景）
        // 改写/意图/记忆场景：维度直接匹配一级子集
        activeDimensions.forEach((dn) => {
          let found = false;
          if (matchKey) {
            const keyAllData = rawData[matchKey];
            (keyAllData.result || []).forEach((res) => {
              if (res.dataset_name === scene && res.metrics?.length > 0) {
                const subsets = res.metrics[0].categories?.[0]?.subsets || [];
                subsets.forEach((subset) => {
                  if (subset.name === dn) {
                    found = true;
                    tempData.push({
                      data: (subset.score * 100).toFixed(2),
                      dimension: dn,
                    });
                  }
                });
              }
            });
          }
          if (!found) {
            tempData.push({ data: 0, dimension: dn });
          }
        });
      } else {
        // Multimodal Ruler2（伴学/GUI规划/GUI操控）
        if (matchKey) {
          const keyAllData = rawData[matchKey];
          const targetResList = (keyAllData.result || []).filter(
            (res) => res.dataset_name === scene && res.metrics?.length > 0
          );

          // 收集所有选中场景的 subsets
          const allSubsets = [];
          targetResList.forEach((targetRes) => {
            const subsets = targetRes.metrics[0].categories?.[0]?.subsets || [];
            subsets.forEach((sub) => {
              if (!allSubsets.find((s) => s.name === sub.name)) {
                allSubsets.push(sub);
              }
            });
          });

          activeDimensions.forEach((dn) => {
            let found = false;
            allSubsets.forEach((subset) => {
              if (subset.name === dn) {
                found = true;
                tempData.push({
                  data: (subset.score * 100).toFixed(2),
                  dimension: dn,
                });
              }
            });
            if (!found) {
              tempData.push({ data: 0, dimension: dn });
            }
          });
        } else {
          activeDimensions.forEach((dn) => {
            tempData.push({ data: 0, dimension: dn });
          });
        }
      }

      newChartData.push({
        data: tempData,
        title: label,
        color: getColorForModel(label),
      });
      newTitles.push({
        title: label,
        color: globalColorMap.value[label],
      });
    });

    chartData.value = newChartData;
    titles.value = newTitles;

    // CN 维度映射
    if (scene === "aisf_llm_gaixie") {
      CNdimensions.value = [];
      dimensions.value.forEach((item) => {
        if (DATASET_MAPPING.aisf_llm_gaixie.subsets.includes(item)) {
          CNdimensions.value.push(DATASET_MAPPING.aisf_llm_gaixie.labels[item]);
        }
      });
    } else if (scene === "aisf_llm_yitu") {
      CNdimensions.value = [];
      dimensions.value.forEach((item) => {
        if (DATASET_MAPPING.aisf_llm_yitu?.subsets?.includes(item)) {
          CNdimensions.value.push(DATASET_MAPPING.aisf_llm_yitu.labels[item]);
        }
      });
    }
  }

  // ===== 重建图表数据 =====
  function rebuildChartData() {
    if (selectValue.value.length === 0) return;
    if (isRuler1) {
      buildRuler1ChartData();
    } else {
      buildRuler2ChartData();
    }
  }

  // ===== 监听模型选择变化 =====
  function onModelChange(val) {
    if (val.length === 0) {
      // 不允许取消所有选择
      selectValue.value = [currentModelName];
      ElMessage({ message: "请至少选择一个模型", type: "warning" });
      return;
    }
    // 同步外部传入的 val 到内部 state
    selectValue.value = val;
    rebuildChartData();
  }

  // ===== 监听测试集选择变化 =====
  function onDatasetChange(val) {
    if (val.length === 0) {
      selectDatasetValue.value = dimensions.value;
    }
    rebuildChartData();
  }

  // ===== 测试集全选/反选（平铺 select） =====
  function handleCheckAll(val) {
    checkAll.value = val;
    indeterminate.value = false;
    if (val) {
      selectDatasetValue.value = [...dimensions.value];
    }
  }

  // ===== 判断某个模型在当前 group 是否有分数 =====
  function hasModelScore(modelName) {
    const rawData = getGroupRawData();
    if (!rawData) return false;

    const matchKey = Object.keys(rawData).find(
      (key) => normalize(key) === normalize(modelName)
    );
    if (!matchKey) return false;

    if (isRuler1) {
      return rawData[matchKey].result.some(
        (d) => d.score > 0 && dimensions.value.includes(d.dataset_name)
      );
    } else {
      const scene = groupConfig.scene;
      const result = rawData[matchKey].result || [];
      return result.some(
        (r) =>
          r.dataset_name === scene &&
          r.metrics?.length > 0 &&
          r.metrics[0].categories?.[0]?.subsets?.some((sub) => sub.score > 0)
      );
    }
  }

  // ===== 初始化 =====
  function init() {
    const hasValid = initModels();
    if (hasValid) {
      rebuildChartData();
      isInited.value = true;
    }
    return hasValid;
  }

  // ===== 重置（tab 切换时） =====
  function reset() {
    selectValue.value = [];
    models.value = [];
    chartData.value = [];
    titles.value = [];
    checkAll.value = false;
    indeterminate.value = false;
    selectDatasetValue.value = [];
    CNdimensions.value = [];
    isInited.value = false;
  }

  return {
    // 状态
    selectValue,
    models,
    selectDatasetValue,
    chartData,
    titles,
    checkAll,
    indeterminate,
    isInited,
    CNdimensions,

    // 方法
    init,
    reset,
    rebuildChartData,
    onModelChange,
    onDatasetChange,
    hasModelScore,
    handleCheckAll,
    getColorForModel,
  };
}