import { ref, computed } from "vue";
import { getEldStatistics } from "@/api/runService.js";

// 模板中实际使用的维度前缀
const CATEGORIES = ["attention", "sitting"] as const;
type Category = (typeof CATEGORIES)[number];

/** 为多个维度统一创建 ref 集合 */
function initRefs<T>(initial: T) {
  return Object.fromEntries(
    CATEGORIES.map((c) => [c, ref<T>(initial)])
  ) as Record<Category, ReturnType<typeof ref<T>>>;
}

// ============================================================
// title 前缀到 ref 的映射表（评测结果统计 / normal 场景）
// ============================================================
interface TableItem {
  title: string;
  columns: string[];
  rows: Record<string, any>[];
}

/**
 * 从 tables 数组中查找 title 包含关键字的 TableItem
 */
function findTable(tables: TableItem[], keyword: string): TableItem | undefined {
  return tables.find((t) => t.title.includes(keyword));
}

function findNthTable(tables: TableItem[], keyword: string, index: number = 0): TableItem | undefined {
  const matches = tables.filter((t) => t.title.includes(keyword));
  return matches[index];
}

/**
 * 将后端返回的评测结果统计 sheet 数据映射到前端 ref
 */
function mapNormalSheet(sheetData: TableItem[]) {
  return {
    totalAccuracyTableData: findNthTable(sheetData, "各个业务整体准确率交付指标", 0)?.rows ?? [],
    totalAccuracyTableData_1: findNthTable(sheetData, "各个业务整体准确率交付指标", 1)?.rows ?? [],
    attentionIndicatorTablData: findTable(sheetData, "##注意力交付指标")?.rows ?? [],
    sittingIndicatorTablData: findTable(sheetData, "##坐姿交付指标")?.rows ?? [],

    accuracyTableData: findTable(sheetData, "##总的正确率")?.rows ?? [],
    statusTableData: findTable(sheetData, "##各个大小类的正确率")?.rows ?? [],
    costTimeTableData: findTable(sheetData, "##时延分布统计")?.rows ?? [],
    sourceTableData: findTable(sheetData, "##不同图片来源统计")?.rows ?? [],
    resolutionTableData: findTable(sheetData, "##不同分辨率统计")?.rows ?? [],
    // attentionDifficultyTablData: findTable(sheetData, "##注意力难易度准确率")?.rows ?? [],
    attentionPrecisionTablData: findTable(sheetData, "##注意力统计_模型")?.rows ?? [],
    attentionConfusionMatrixData: toConfusionMatrix(findTable(sheetData, "##注意力混淆矩阵_模型")),
    // sittingDifficultyTablData: findTable(sheetData, "##坐姿难易度准确率")?.rows ?? [],
    sittingPrecisionTablData: findTable(sheetData, "##坐姿统计_模型")?.rows ?? [],
    sittingConfusionMatrixData: toConfusionMatrix(findTable(sheetData, "##坐姿混淆矩阵_模型")),
  };
}

/**
 * 将后端返回的产品验收维度保持一致 sheet 数据映射到前端 ref
 */
function mapPartSheet(sheetData: TableItem[]) {
  return {
    statusPartTableData: findTable(sheetData, "##各个业务的正确率")?.rows ?? [],
    attentionIndicatorPartTablData: findTable(sheetData, "##注意力交付指标")?.rows ?? [],
    sittingIndicatorPartTablData: findTable(sheetData, "##坐姿交付指标")?.rows ?? [],
    attentionConfusionMatrixData: toConfusionMatrix(findTable(sheetData, "##注意力混淆矩阵")),
    sittingConfusionMatrixData: toConfusionMatrix(findTable(sheetData, "##坐姿混淆矩阵")),
    accuracyTableData: findTable(sheetData, "##总的正确率")?.rows ?? [],
    statusTableData: findTable(sheetData, "##各个大小类的正确率")?.rows ?? [],
  };
}

/**
 * 将混淆矩阵的 backend 格式转为前端需要的 { tableData, predValues, goldValues, dimensionName } 格式
 * 后端格式：columns = ['标签', '集中', '疑似睡觉', ...] 即 [goldColumn, pred1, pred2, ...]
 *           rows = [{ '标签': '集中', '集中': 8, '疑似睡觉': 0, ... }, ...]
 * 前端需要：tableData, predValues, goldValues, dimensionName
 */
function toConfusionMatrix(table: TableItem | undefined) {
  if (!table) return { tableData: [], predValues: [], goldValues: [], dimensionName: "" };
  const goldColumn = table.columns[0]; // 第一列是金标列名 如 '标签'
  const predValues = table.columns.slice(1).filter((c) => c.trim() !== "");
  const goldValues = table.rows.map((r) => r[goldColumn]);
  // 重建 tableData：每行包含 goldValue + 各 pred column 的值
  const tableData = table.rows.map((r) => {
    const row: Record<string, any> = { goldValue: r[goldColumn] };
    predValues.forEach((pred) => {
      row[pred.replace(/\s+/g, "_")] = r[pred];
    });
    return row;
  });
  return {
    tableData,
    predValues,
    goldValues,
    dimensionName: goldColumn,
  };
}

export function useChildrenStudyData(Result, taskSubSet) {
  // ====================================================================
  // 独立 ref
  // ====================================================================
  const statisticsData = ref([]);
  const totalAccuracyTableData = ref<any[][]>([]);
  const totalAccuracyTableData_1 = ref<any[][]>([]);
  const accuracyTableData = ref<any[][]>([]);
  const statusTableData = ref<any[][]>([]);
  const costTimeTableData = ref<any[][]>([]);
  const sourceTableData = ref<any[][]>([]);
  const resolutionTableData = ref<any[][]>([]);

  // Part 数据
  const statusPartTableData = ref<any[][]>([]);
  const attentionIndicatorPartTablData = ref<any[][]>([]);
  const sittingIndicatorPartTablData = ref<any[][]>([]);

  // Dynamic enums（后端已算好，不再需要前端提取）
  const attentionResultEnum = ref([]);
  const postureResultEnum = ref([]);

  // ====================================================================
  // 按维度分组的 ref（attention / sitting）
  // ====================================================================
  const categoryData = initRefs<any[]>([]);
  const correctRateData = initRefs<any[]>([]);
  const falseAlarmData = initRefs<any[]>([]);
  const missedRateData = initRefs<any[]>([]);
  const confusionMatrixData = initRefs<any[]>([]);
  const difficultyData = initRefs<any[]>([]);
  const precisionData = initRefs<any[]>([]);
  const recallData = initRefs<any[]>([]);
  const fnrData = initRefs<any[]>([]);
  const confusionMatrixData2 = initRefs<any[]>([]);
  const indicatorData = initRefs<any[]>([]);

  const attentionStabilityData = ref([]);
  const sittingStabilityData = ref([]);
  const totalStabilityData = ref([]);

  // 动态 sheet 数据（除"评测结果统计"和"与产品验收维度保持一致"之外的剩余 sheet）
  const dynamicSheetData = ref<Record<string, { title: string; columns: string[]; rows: Record<string, any>[] }[]>[]>([]);

  // 解构到原有变量名（兼容模板注入）
  const attentionTableData = categoryData.attention;
  const sittingTableData = categoryData.sitting;
  const attentionCorrectTableData = correctRateData.attention;
  const sittingCorrectTableData = correctRateData.sitting;
  const attentionFalseAlarmTableData = falseAlarmData.attention;
  const sittingFalseAlarmTableData = falseAlarmData.sitting;
  const attentionMissedRateTableData = missedRateData.attention;
  const sittingMissedRateTableData = missedRateData.sitting;
  const attentionConfusionMatrixData = confusionMatrixData.attention;
  const sittingConfusionMatrixData = confusionMatrixData.sitting;
  const attentionDifficultyTablData = difficultyData.attention;
  const sittingDifficultyTablData = difficultyData.sitting;
  const attentionPrecisionTablData = precisionData.attention;
  const sittingPrecisionTablData = precisionData.sitting;
  const attentionRecallTablData = recallData.attention;
  const sittingRecallTablData = recallData.sitting;
  const attentionFNRTablData = fnrData.attention;
  const sittingFNRTablData = fnrData.sitting;
  const attentionConfusionMatrixData2 = confusionMatrixData2.attention;
  const sittingConfusionMatrixData2 = confusionMatrixData2.sitting;
  const attentionIndicatorTablData = indicatorData.attention;
  const sittingIndicatorTablData = indicatorData.sitting;

  // ====================================================================
  // Computed
  // ====================================================================
  const dynamicSourceColumns = computed(() => {
    if (sourceTableData.value[0]?.length === 0) return [];
    const keys = new Set<string>();
    sourceTableData.value[0].forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (key !== "indicator") keys.add(key);
      });
    });
    return Array.from(keys);
  });

  // ====================================================================
  // 核心：getStatisticsData — 从后端API获取统计结果
  // ====================================================================
  const getStatisticsData = async () => {
    statisticsData.value = [];
    // 收集所有 tasks 的原始 Result 到 statisticsData（保留原始数据查看功能）
    Result.value.forEach((task) => {
      if (!Array.isArray(task)) return;
      const taskData = task
        .filter((item) => item)
        .map((item) => ({
          index: item.index,
          ...(item.choices?.[0]?.review || {}),
          response_time: item.response_time,
          ...(item.usage || {}),
          ...(item.image_info || {}),
          ...(item.difficulty_level || {}),
        }));
      statisticsData.value.push(...taskData);
    });

    // 调用后端API获取统计数据
    const promises = Result.value.map((_, taskIndex) => {
      // 从 preSelectedTasks 获取 task 信息
      // 这里 Result.value 中每个 task 对应 selectedTasks 中的一个
      // 我们需要从外部传入 selectedTasks 或通过 taskSelection 获取
      // 由于没有直接传入，暂时用 getStatisticsData 的参数形式
      return Promise.resolve(null);
    });

    // 这里通过异步调用来获取数据
    // 注意：实际调用时，Result.value 中的任务ID等信息需要通过外部传入
    // 下面是一个 placeholder 实现，实际数据加载在 childrenStudyStastics.vue 的 handleConfirm 中触发
    console.log("[useChildrenStudyData] getStatisticsData called via API");
  };

  /**
   * 从后端API加载单个task的统计数据，并合并到对应索引的ref中
   * @param taskIndex 任务在 selectedTasks 中的索引
   * @param taskId 任务ID
   * @param modelId 模型ID
   * @param datasetName 数据集名称
   */
  const loadTaskStatistics = async (taskIndex: number, taskId: string, modelId: string, datasetName: string) => {
    try {
      // 先清空该索引的旧数据
      clearRefValue(totalAccuracyTableData, taskIndex);
      clearRefValue(totalAccuracyTableData_1, taskIndex);
      clearRefValue(accuracyTableData, taskIndex);
      clearRefValue(statusTableData, taskIndex);
      clearRefValue(costTimeTableData, taskIndex);
      clearRefValue(sourceTableData, taskIndex);
      clearRefValue(resolutionTableData, taskIndex);
      clearRefValue(statusPartTableData, taskIndex);
      clearRefValue(attentionIndicatorPartTablData, taskIndex);
      clearRefValue(sittingIndicatorPartTablData, taskIndex);
      clearRefValue(precisionData.attention, taskIndex);
      clearRefValue(precisionData.sitting, taskIndex);
      clearRefValue(indicatorData.attention, taskIndex);
      clearRefValue(indicatorData.sitting, taskIndex);
      clearRefValue(confusionMatrixData.attention, taskIndex);
      clearRefValue(confusionMatrixData.sitting, taskIndex);
      clearRefValue(confusionMatrixData2.attention, taskIndex);
      clearRefValue(confusionMatrixData2.sitting, taskIndex);
      clearRefValue(dynamicSheetData, taskIndex);

      const res = await getEldStatistics({
        task_id: taskId,
        model_id: modelId,
        dataset_name: datasetName,
      });

      const allData = res.data?.data;
      if (!allData) {
        console.warn(`[useChildrenStudyData] no data for task ${taskId}`);
        return;
      }

      // 填充 statisticsData（触发模板 v-if 条件），使 radio-group 可见
      statisticsData.value.push(...([1] as any));

      // 解析各 sheet 的数据
      const normalSheet = allData["评测结果统计"] ?? [];
      const partSheet = allData["与产品验收维度保持一致"] ?? [];

      const normal = mapNormalSheet(normalSheet);
      const part = mapPartSheet(partSheet);

      // console.log('normal')
      // console.log(normal)

      // ---- 赋值到 ref（兼容模板 data[index] 的访问方式）----

      // normal 场景
      setRefValue(totalAccuracyTableData, taskIndex, normal.totalAccuracyTableData);
      setRefValue(totalAccuracyTableData_1, taskIndex, normal.totalAccuracyTableData_1);
      setRefValue(accuracyTableData, taskIndex, normal.accuracyTableData);
      setRefValue(statusTableData, taskIndex, normal.statusTableData ?? part.statusTableData);
      setRefValue(costTimeTableData, taskIndex, normal.costTimeTableData);
      setRefValue(sourceTableData, taskIndex, normal.sourceTableData);
      setRefValue(resolutionTableData, taskIndex, normal.resolutionTableData);

      // 注意力/坐姿难度、精确率、混淆矩阵 (normal scene)
      // setRefValue(difficultyData.attention, taskIndex, normal.attentionDifficultyTablData);
      // setRefValue(difficultyData.sitting, taskIndex, normal.sittingDifficultyTablData);
      setRefValue(precisionData.attention, taskIndex, normal.attentionPrecisionTablData);
      setRefValue(precisionData.sitting, taskIndex, normal.sittingPrecisionTablData);
      setRefValue(indicatorData.attention, taskIndex, normal.attentionIndicatorTablData);
      setRefValue(indicatorData.sitting, taskIndex, normal.sittingIndicatorTablData);
      setRefValue(confusionMatrixData.attention, taskIndex, normal.attentionConfusionMatrixData);
      setRefValue(confusionMatrixData.sitting, taskIndex, normal.sittingConfusionMatrixData);
      setRefValue(confusionMatrixData2.attention, taskIndex, normal.attentionConfusionMatrixData);
      setRefValue(confusionMatrixData2.sitting, taskIndex, normal.sittingConfusionMatrixData);

      // part 场景
      setRefValue(statusPartTableData, taskIndex, part.statusPartTableData);
      setRefValue(attentionIndicatorPartTablData, taskIndex, part.attentionIndicatorPartTablData);
      setRefValue(sittingIndicatorPartTablData, taskIndex, part.sittingIndicatorPartTablData);

      // 动态 sheet：除"评测结果统计"和"与产品验收维度保持一致"外的剩余 sheet
      const knownSheets = ["评测结果统计", "与产品验收维度保持一致", "全量"];
      const dynamicSheets: Record<string, any[]> = {};
      for (const [sheetName, tables] of Object.entries(allData)) {
        if (!knownSheets.includes(sheetName)) {
          dynamicSheets[sheetName] = tables;
        }
      }
      setRefValue(dynamicSheetData, taskIndex, dynamicSheets);

    } catch (err) {
      console.error(`[useChildrenStudyData] loadTaskStatistics error for task ${taskId}:`, err);
      // 置空占位，防止模板访问 undefined
      setRefValue(accuracyTableData, taskIndex, []);
      setRefValue(statusTableData, taskIndex, []);
      setRefValue(costTimeTableData, taskIndex, []);
      setRefValue(sourceTableData, taskIndex, []);
      setRefValue(resolutionTableData, taskIndex, []);
      setRefValue(statusPartTableData, taskIndex, []);
      setRefValue(attentionIndicatorPartTablData, taskIndex, []);
      setRefValue(sittingIndicatorPartTablData, taskIndex, []);
    }
  };

  // ====================================================================
  // 枚举提取（不再需要，保留空函数兼容）
  // ====================================================================
  const extractEnums = () => {
    return { attentionResult: [], postureResult: [] };
  };

  // ====================================================================
  // Public API
  // ====================================================================
  return {
    statisticsData,
    totalAccuracyTableData,
    totalAccuracyTableData_1,
    accuracyTableData,
    statusTableData,
    costTimeTableData,
    sourceTableData,
    resolutionTableData,

    attentionTableData,
    sittingTableData,
    attentionCorrectTableData,
    sittingCorrectTableData,
    attentionFalseAlarmTableData,
    sittingFalseAlarmTableData,
    attentionMissedRateTableData,
    sittingMissedRateTableData,
    attentionConfusionMatrixData,
    sittingConfusionMatrixData,
    attentionDifficultyTablData,
    sittingDifficultyTablData,
    attentionPrecisionTablData,
    sittingPrecisionTablData,
    attentionRecallTablData,
    sittingRecallTablData,
    attentionFNRTablData,
    sittingFNRTablData,
    attentionConfusionMatrixData2,
    sittingConfusionMatrixData2,
    attentionIndicatorTablData,
    sittingIndicatorTablData,

    attentionIndicatorPartTablData,
    sittingIndicatorPartTablData,
    statusPartTableData,

    attentionResultEnum,
    postureResultEnum,
    dynamicSourceColumns,

    getStatisticsData,
    loadTaskStatistics,
    extractEnums,

    attentionStabilityData,
    sittingStabilityData,
    totalStabilityData,

    dynamicSheetData,
  };
}

/**
 * 辅助函数：确保 ref 数组在指定索引有值
 */
function setRefValue<T>(refArray: { value: T[] }, index: number, value: T) {
  while (refArray.value.length <= index) {
    refArray.value.push(null as any);
  }
  refArray.value[index] = value;
}

/**
 * 辅助函数：清空 ref 数组在指定索引的值
 */
function clearRefValue<T>(refArray: { value: T[] }, index: number) {
  if (refArray.value[index] !== null && refArray.value[index] !== undefined) {
    refArray.value[index] = null as any;
  }
}