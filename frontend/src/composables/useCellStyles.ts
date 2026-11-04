import { ref, computed } from "vue";
import { excludedDimensions } from "@/components/statistics/childrenStudyConstants";

export function useCellStyles() {
  const handleCellStyle = ({ row, column, rowIndex, columnIndex }) => {
    if (column.property === "goldValue") return;

    const goldValue = row.goldValue;
    const predLabel = column.label;
    const cellValue = row[column.property];

    const isNotSubstring = !goldValue
      .split(/[，,]/)
      .some((tag: string) => tag.trim() === predLabel);

    const isValidNumber =
      !isNaN(parseFloat(cellValue)) && isFinite(cellValue) && cellValue > 0;

    if (isNotSubstring && isValidNumber) {
      return { backgroundColor: "rgb(250, 182, 182)" };
    }
    return {};
  };

  const handleCellStyleGreen = computed(() => {
    return ({ row, column, rowIndex, columnIndex }) => {
      if (column.property === "goldValue") return {};

      const goldValue = row.goldValue;
      const predLabel = column.label;
      const cellValue = row[column.property];

      const isNotSubstring = goldValue
        .split(/[，,]/)
        .some((tag: string) => tag.trim() === predLabel);

      const isValidNumber =
        !isNaN(parseFloat(cellValue)) && isFinite(cellValue) && cellValue > 0;

      if (isNotSubstring && isValidNumber) {
        return { backgroundColor: "#C6EFCE" };
      }
      return {};
    };
  });

  const tableVisible = ref<boolean[]>([]);

  const toggleTable = (index: number) => {
    tableVisible.value[index] = !tableVisible.value[index];
  };

  const createIndicatorCellStyle = (normalCategory: string) => {
    return ({ row, column }) => {
      const category = row["小类名"];
      const columnLabel = column.label;

      const isNormalRecall =
        category === normalCategory && columnLabel === "召回率";
      const isAbnormalPrecision =
        category !== normalCategory && columnLabel === "精确率";

      if (isNormalRecall || isAbnormalPrecision) {
        return {
          backgroundColor: "rgb(250, 182, 182)",
          fontWeight: "bold",
        };
      }
      return {};
    };
  };

  const attentionIndicatorCellStyle = createIndicatorCellStyle("集中");
  const sittingIndicatorCellStyle = createIndicatorCellStyle("正常");
  const distanceIndicatorCellStyle = createIndicatorCellStyle("视距正常");
  const seatIndicatorCellStyle = createIndicatorCellStyle("在座状态");

  const filteredTableData = (rawTableData) => {
    if (!rawTableData) return [];
    return rawTableData.filter(
      (item) => !excludedDimensions.includes(item.dimension)
    );
  };

  return {
    handleCellStyle,
    handleCellStyleGreen,
    tableVisible,
    toggleTable,
    createIndicatorCellStyle,
    attentionIndicatorCellStyle,
    sittingIndicatorCellStyle,
    distanceIndicatorCellStyle,
    seatIndicatorCellStyle,
    filteredTableData,
  };
}