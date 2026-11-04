<template>
  <div class="evaluation-tab">
    <!-- 标题 + 测试集选择 + 模型选择 -->
    <div class="section-header">
      <div class="section-controls">
        <!-- 测试集选择器 -->
        <span class="control-label">选择测试集</span>
        <!-- 记忆场景使用级联选择器（二级子集），其他场景使用普通多选 -->
        <el-cascader
          v-if="isMemoryScene"
          :model-value="selectDatasetValue"
          @update:model-value="onFlatDatasetChange($event)"
          :options="memoryCascaderOptions"
          :props="{ multiple: true, emitPath: false }"
          collapse-tags
          collapse-tags-tooltip
          placeholder="Select"
          :max-collapse-tags="1"
          style="width:300px"
          clearable
        />
        <el-select
          v-else
          :model-value="selectDatasetValue"
          @update:model-value="onFlatDatasetChange($event)"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="Select"
          popper-class="custom-header"
          :max-collapse-tags="1"
          style="width:300px"
        >
          <template #header>
            <el-checkbox
              :model-value="checkAll"
              :indeterminate="indeterminate"
              @update:model-value="onCheckAllChange($event)"
            >All</el-checkbox>
          </template>
          <el-option
            v-for="item in allDatasetOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <!-- 模型选择器 -->
        <span class="control-label" style="margin-left:12px;">对比模型</span>
        <el-select
          :model-value="selectValue"
          @update:model-value="onModelValueChange($event)"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="Select"
          popper-class="custom-header"
          :max-collapse-tags="1"
          style="width: 240px;"
        >
          <template #header>
            <el-checkbox
              :model-value="modelCheckAll"
              :indeterminate="modelIndeterminate"
              @update:model-value="onModelCheckAll($event)"
            >All</el-checkbox>
          </template>
          <el-option
            v-for="item in models"
            :key="item.value"
            :label="item.label"
            :value="item.value"
            :disabled="item.disabled"
          />
        </el-select>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-row" v-if="chartData?.length > 0">
      <div class="chart-item">
        <RadarChart
          :dimensions="activeDimensions"
          :data="chartData"
          :maxValue="100"
          :titles="titles"
          :width="Ruler1RadarWidth"
          :height="chartHeight"
          :showLabel="showLabel"
          :radius="radius"
          :CNDimention="CNdimensions"
        />
      </div>
      <div class="chart-item">
        <BarChart
          :dimensions="activeDimensions"
          :data="chartData"
          :maxValue="100"
          :titles="titles"
          :width="barWidth"
          :height="chartHeight"
          :showLabel="showLabelBar"
          :bottomMargin="bottomMargin"
          :CNDimention="CNdimensions"
        />
      </div>
    </div>
    <div v-else class="nullData">暂无数据</div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import RadarChart from "./multiRadarChart.vue";
import BarChart from "./multiBarChart.vue";

const props = defineProps({
  group: { type: Object, required: true },
  selectValue: { type: Array, required: true },
  models: { type: Array, required: true },
  selectDatasetValue: { type: Array, required: true },
  chartData: { type: Array, required: true },
  titles: { type: Array, required: true },
  checkAll: { type: Boolean, default: false },
  indeterminate: { type: Boolean, default: false },
  CNdimensions: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "update:selectValue",
  "update:selectDatasetValue",
  "model-change",
  "dataset-change",
  "check-all",
]);

// ===== 布局常量 =====
const Ruler1RadarWidth = "100%";
const barWidth = "100%";
const chartHeight = "500px";
const DEFAULT_RADIUS = "70%";
const OVERFLOW_RADIUS = "50%";
const NORMAL_BOTTOM_MARGIN = "10%";
const OVERFLOW_BOTTOM_MARGIN = "15%";
const EXTREME_BOTTOM_MARGIN = "30%";

// ===== 计算属性 =====
const showLabel = computed(() => props.selectValue.length <= 1);
const showLabelBar = computed(() => props.selectValue.length <= 2);

const radius = computed(() =>
  props.selectValue.length > 8 ? OVERFLOW_RADIUS : DEFAULT_RADIUS
);

const bottomMargin = computed(() => {
  if (props.selectValue.length > 16) return EXTREME_BOTTOM_MARGIN;
  if (props.selectValue.length > 8) return OVERFLOW_BOTTOM_MARGIN;
  return NORMAL_BOTTOM_MARGIN;
});

const activeDimensions = computed(() => {
  if (props.selectDatasetValue.length > 0) return props.selectDatasetValue;
  return props.group.dimensions;
});

const allDatasetOptions = computed(() =>
  props.group.dimensions.map((d) => ({ value: d, label: d }))
);

// 记忆场景判断
const isMemoryScene = computed(() => props.group?.groupKey === "aisf_memory");

// 记忆场景级联选择器选项：按一级子集分组
const memoryCascaderOptions = computed(() => {
  if (!isMemoryScene.value) return [];
  // 从 LLM_RULER2_OPTIONS 中找到 aisf_memory 的 children 并分组
  // 这里从 props.group.dimensions 反推分组：以"-"分隔前缀作为组名
  const groups = {};
  props.group.dimensions.forEach((d) => {
    // 取第一个"-"前的内容作为分组 key（如 "记忆萃取"）
    const prefix = d.includes("-") ? d.substring(0, d.indexOf("-")) : d;
    if (!groups[prefix]) groups[prefix] = [];
    groups[prefix].push({ value: d, label: d });
  });
  return Object.entries(groups).map(([prefix, children]) => ({
    value: prefix,
    label: prefix,
    children,
  }));
});

const modelCheckAll = computed(
  () =>
    props.models?.length > 0 && props.selectValue.length === props.models.length
);

const modelIndeterminate = computed(
  () =>
    props.selectValue?.length > 0 &&
    props.selectValue.length < props.models.length
);

// ===== 事件处理器 =====
function onModelValueChange(val) {
  emit("update:selectValue", val);
  emit("model-change", val);
}

function onFlatDatasetChange(val) {
  emit("update:selectDatasetValue", val);
  emit("dataset-change", val);
}

function onCheckAllChange(val) {
  emit("check-all", val);
}

function onModelCheckAll(val) {
  if (!val) return; // 不允许全部取消
  const allModelValues = props.models.map((m) => m.value);
  emit("update:selectValue", allModelValues);
  emit("model-change", allModelValues);
}
</script>

<style scoped>
.evaluation-tab {
  display: flex;
  flex-direction: column;
  padding: 16px 0;
  border-radius: 30px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
}
.section-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.control-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}
.charts-row {
  display: flex;
  flex-direction: row;
  gap: 16px;
  justify-content: center;
}
.chart-item {
  flex: 1;
  display: flex;
  justify-content: center;
  min-width: 0;
}
.nullData {
  width: 100%;
  text-align: center;
  padding: 40px 0;
  color: #909399;
}
</style>