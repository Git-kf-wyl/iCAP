import { computed } from "vue";

export function useChildrenStudyCharts(
  accuracyTableData,
  statusTableData,
  costTimeTableData,
  sourceTableData,
  resolutionTableData,
  attentionTableData,
  distanceTableData,
  sittingTableData,
  correctTableDataConfig,
  falseAlarmTableDataConfig,
  missedRateTableDataConfig,
  difficultyTableDataConfig,
  preSelectedTasks
) {
  const accuracyChartData = computed(() => {
    const result = [];
    const tableData = accuracyTableData.value;
    const tasks = preSelectedTasks.value;
    const minLength = Math.min(tableData.length, tasks.length);

    for (let i = 0; i < minLength; i++) {
      const metricArray = tableData[i];
      const taskItem = tasks[i];

      const totalObj = metricArray.find((item) => item['指标'] === "总数量");
      const correctObj = metricArray.find(
        (item) => item['指标'] === "全部正确数量"
      );
      const rateObj = metricArray.find((item) => item['指标'] === "总正确率");

      result.push({
        task_name: taskItem.name,
        总数量: totalObj ? totalObj['数值'] : 0,
        全部正确数量: correctObj ? correctObj['数值'] : 0,
        总正确率: rateObj ? rateObj['数值'] : 0,
      });
    }
    return result;
  });

  const tokensChartData = computed(() => {
    const result = [];
    const tableData = accuracyTableData.value;
    const tasks = preSelectedTasks.value;
    const minLength = Math.min(tableData.length, tasks.length);

    for (let i = 0; i < minLength; i++) {
      const metricArray = tableData[i];
      const taskItem = tasks[i];

      const avgCompletion = metricArray.find(
        (item) => item['指标'] === "平均completion_tokens"
      );
      const avgPrompt = metricArray.find(
        (item) => item['指标'] === "平均prompt_tokens"
      );
      const avgTotal = metricArray.find(
        (item) => item['指标'] === "平均total_tokens"
      );
      const avgCostTime = metricArray.find(
        (item) => item['指标'] === "平均cost_time"
      );

      result.push({
        task_name: taskItem.name,
        平均completion_tokens: avgCompletion ? avgCompletion['数值'] : 0,
        平均prompt_tokens: avgPrompt ? avgPrompt['数值'] : 0,
        平均total_tokens: avgTotal ? avgTotal['数值'] : 0,
        平均cost_time: avgCostTime ? avgCostTime['数值'] : 0,
      });
    }
    return result;
  });

  const generateChartData = (tableData, tasks, dimensionKey, valueKey) => {
    const result = [];
    const allDimensions = new Set();
    tableData.forEach((metricArray) => {
      metricArray.forEach((item) => {
        allDimensions.add(item[dimensionKey]);
      });
    });

    const minLength = Math.min(tableData.length, tasks.length);

    for (let i = 0; i < minLength; i++) {
      const metricArray = tableData[i];
      const taskItem = tasks[i];

      const oneTaskData = {};
      allDimensions.forEach((dim) => {
        oneTaskData[dim] = null;
      });

      metricArray.forEach((item) => {
        oneTaskData[item[dimensionKey]] = item[valueKey];
      });

      result.push({
        task_name: taskItem.name,
        ...oneTaskData,
      });
    }
    return result;
  };

  const generateStatusChartData = (tableData, tasks) => {
    return generateChartData(tableData, tasks, "维度", "正确率");
  };

  const generateCostTimeChartData = (tableData, tasks) => {
    return generateChartData(tableData, tasks, "耗时", "占比");
  };

  const generateSourceChartData = (tableData, tasks) => {
    return generateChartData(tableData, tasks, "图片来源", "总正确率_正确率");
  };

  const generateResolutionChartData = (tableData, tasks) => {
    return generateChartData(tableData, tasks, "分辨率", "正确率");
  };

  const generateDifficultyChartData = (tableData, tasks) => {
    return generateChartData(tableData, tasks, "level", "accuracy");
  };

  const generateStabilityChartData = (tableData, tasks) => {
    return generateChartData(tableData, tasks, "category", "stabilityRate");
  }

  const generateMattrixChartData = (tableData, tasks, extractor) => {
    const result = [];
    const minLength = Math.min(tableData.length, tasks.length);

    for (let i = 0; i < minLength; i++) {
      const metricArray = tableData[i];
      const taskItem = tasks[i];
      const metricObject = {};

      metricArray.forEach((item) => {
        const [key, value] = extractor(item);
        metricObject[key] = value;
      });

      result.push({
        task_name: taskItem.name,
        ...metricObject,
      });
    }
    return result;
  };

  const generateNormalChartData = (tableData, tasks) =>
    generateMattrixChartData(tableData, tasks, (item) => [item.type, item.ratio]);

  const generateFalseAlarmChartData = (tableData, tasks) =>
    generateMattrixChartData(tableData, tasks, (item) => [
      item.category,
      item.errorRate,
    ]);

  const generateCorrectChartData = (tableData, tasks) =>
    generateMattrixChartData(tableData, tasks, (item) => [
      item.category,
      item.correctRate,
    ]);

  const generateMissedRateTChartData = (tableData, tasks) => {
    return generateMattrixChartData(tableData, tasks, (item) => [
      item.dimension,
      item.missRate,
    ]);
  };

  return {
    accuracyChartData,
    tokensChartData,
    generateStatusChartData,
    generateCostTimeChartData,
    generateSourceChartData,
    generateResolutionChartData,
    generateDifficultyChartData,
    generateMattrixChartData,
    generateNormalChartData,
    generateFalseAlarmChartData,
    generateCorrectChartData,
    generateMissedRateTChartData,
    generateStabilityChartData
  };
}