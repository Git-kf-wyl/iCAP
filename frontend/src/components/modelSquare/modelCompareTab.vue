<template>
  <div class="model-compare-tab" v-loading="!dataLoaded" element-loading-text="数据加载中...">
    <!-- =============== 尺子一：通用榜单 =============== -->
    <section v-if="showRuler1" class="ruler-section">
      <h3 class="ruler-title">尺子一：通用</h3>
      <div class="modality-tabs">
        <span
          v-for="group in visibleRuler1Groups"
          :key="group.groupKey"
          class="modality-tab"
          :class="{ active: activeRuler1GroupKey === group.groupKey }"
          @click="activeRuler1GroupKey = group.groupKey"
        >{{ group.label }}</span>
      </div>
      <div class="chartContainer" v-if="activeRuler1Group">
        <ChartGroupPanel
          :key="'r1-' + activeRuler1Group.groupKey"
          :group="activeRuler1Group"
          v-bind="ruler1Bindings"
          @model-change="handleR1ModelChange"
          @dataset-change="handleR1DatasetChange"
          @check-all="handleR1CheckAll"
        />
      </div>
    </section>

    <el-divider v-if="showRuler1 && showRuler2" />

    <!-- =============== 尺子二：领域榜单 =============== -->
    <section v-if="showRuler2" class="ruler-section">
      <h3 class="ruler-title">尺子二：领域</h3>
      <div class="modality-tabs">
        <span
          v-for="group in visibleRuler2Groups"
          :key="group.groupKey"
          class="modality-tab"
          :class="{ active: activeRuler2GroupKey === group.groupKey }"
          @click="activeRuler2GroupKey = group.groupKey"
        >{{ group.label }}</span>
      </div>
      <div class="chartContainer" v-if="activeRuler2Group">
        <ChartGroupPanel
          :key="'r2-' + activeRuler2Group.groupKey"
          :group="activeRuler2Group"
          v-bind="ruler2Bindings"
          @model-change="handleR2ModelChange"
          @dataset-change="handleR2DatasetChange"
          @check-all="handleR2CheckAll"
        />
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref, computed, watch } from "vue";
import ChartGroupPanel from "./ChartGroupPanel.vue";
import {
  CHART_GROUPS,
  GROUPS_BY_TAB,
} from "./evaluationReportChartGroupConfig.js";
import { useChartGroup } from "@/composables/useChartGroup.js";
import { getCurrentFullRes, getMultiModelData } from "@/api/dataService.js";
import { useAIModelStore } from "@/stores/aiModel";
import { ModelService } from "@/services/modelService.js";

const props = defineProps({
  modelName: { type: String, required: true },
  modelId: { type: String, default: "" },
  defaultSubKey: { type: String, default: "" },
});
const activeRuler1GroupKey = ref("llmGeneral");
const activeRuler2GroupKey = ref("aisf_llm_gaixie");
// 如果有 defaultSubKey，初始化对应的尺子二子组
if (props.defaultSubKey) {
  const subKeyMap = {
    aisf_banxue: "aisf_banxue",
    aisf_llm_gaixie: "aisf_llm_gaixie",
    aisf_llm_yitu: "aisf_llm_yitu",
    aisf_memory_cuiqu: "aisf_memory_cuiqu",
    aisf_memory_zhaohui: "aisf_memory_zhaohui",
    aisf_gui_plan: "aisf_gui_plan",
    aisf_gui_vla: "aisf_gui_vla",
    aisf_llm_skilltican: "aisf_llm_skilltican",
    aisf_llm_guican: "aisf_llm_guican",
    aisf_llm_banxue: "aisf_llm_banxue",
    aisf_llm_coordinator: "aisf_llm_coordinator",
  };
  if (subKeyMap[props.defaultSubKey]) {
    activeRuler2GroupKey.value = subKeyMap[props.defaultSubKey];
  }
}

const ruler1Groups = GROUPS_BY_TAB.ruler1;
const ruler2Groups = GROUPS_BY_TAB.ruler2;

const activeRuler1Group = computed(() =>
  ruler1Groups.find((g) => g.groupKey === activeRuler1GroupKey.value)
);
const activeRuler2Group = computed(() =>
  ruler2Groups.find((g) => g.groupKey === activeRuler2GroupKey.value)
);

// ===== 全局数据 =====
const chartDataStore = ref({ llm: null, multimodal: null });
const dataLoaded = ref(false);

// ===== 全局颜色管理 =====
const globalColorMap = ref({ [props.modelName]: "#0000ff40" });
const globalColorIndex = ref(0);

// ===== 所有 chart group 实例 =====
const groupInstances = {};

CHART_GROUPS.forEach((groupConfig) => {
  groupInstances[groupConfig.groupKey] = useChartGroup(groupConfig, {
    currentModelName: props.modelName,
    allDataRef: chartDataStore,
    globalColorMap,
    globalColorIndex,
  });
});

// ===== 过滤有分数的 group =====
const visibleRuler1Groups = computed(() =>
  dataLoaded.value
    ? ruler1Groups.filter((g) =>
        groupInstances[g.groupKey].hasModelScore(props.modelName)
      )
    : ruler1Groups
);

const visibleRuler2Groups = computed(() =>
  dataLoaded.value
    ? ruler2Groups.filter((g) =>
        groupInstances[g.groupKey].hasModelScore(props.modelName)
      )
    : ruler2Groups
);

// ===== 判断尺子是否展示 =====
const showRuler1 = computed(() => visibleRuler1Groups.value.length > 0);
const showRuler2 = computed(() => visibleRuler2Groups.value.length > 0);

// ===== 确保默认 active groupKey 在可见范围内 =====
function ensureDefaultGroupKey(groups, currentKey, ref) {
  if (!dataLoaded.value) return;
  const visible = groups.filter((g) =>
    groupInstances[g.groupKey].hasModelScore(props.modelName)
  );
  if (visible.length === 0) return;
  if (!visible.find((g) => g.groupKey === currentKey)) {
    ref.value = visible[0].groupKey;
  }
}

// 数据加载后校正默认选中值
watch(dataLoaded, (loaded) => {
  if (!loaded) return;
  ensureDefaultGroupKey(
    ruler1Groups,
    activeRuler1GroupKey.value,
    activeRuler1GroupKey
  );
  ensureDefaultGroupKey(
    ruler2Groups,
    activeRuler2GroupKey.value,
    activeRuler2GroupKey
  );
});

// ===== 构建 binding 对象 =====
function buildBindings(inst) {
  return {
    selectValue: inst.selectValue.value,
    models: inst.models.value,
    selectDatasetValue: inst.selectDatasetValue.value,
    chartData: inst.chartData.value,
    titles: inst.titles.value,
    checkAll: inst.checkAll.value,
    indeterminate: inst.indeterminate.value,
    CNdimensions: inst.CNdimensions.value,
  };
}

// ===== Ruler1 Bindings =====
const ruler1Bindings = ref({});

function refreshR1() {
  const inst = groupInstances[activeRuler1GroupKey.value];
  if (inst) ruler1Bindings.value = buildBindings(inst);
}

// ===== Ruler2 Bindings =====
const ruler2Bindings = ref({});

function refreshR2() {
  const inst = groupInstances[activeRuler2GroupKey.value];
  if (inst) ruler2Bindings.value = buildBindings(inst);
}

// ===== 事件处理器：Ruler1 =====
function handleR1ModelChange(val) {
  const inst = groupInstances[activeRuler1GroupKey.value];
  if (!inst) return;
  // inst.onModelChange 会更新 selectValue 和图表数据
  inst.onModelChange(val);
  refreshR1();
}

function handleR1DatasetChange(val) {
  const inst = groupInstances[activeRuler1GroupKey.value];
  if (!inst) return;
  inst.selectDatasetValue.value = val;
  inst.onDatasetChange(val);
  refreshR1();
}

function handleR1CheckAll(val) {
  const inst = groupInstances[activeRuler1GroupKey.value];
  if (!inst) return;
  inst.handleCheckAll(val);
  refreshR1();
}

// ===== 事件处理器：Ruler2 =====
function handleR2ModelChange(val) {
  const inst = groupInstances[activeRuler2GroupKey.value];
  if (!inst) return;
  inst.onModelChange(val);
  refreshR2();
}

function handleR2DatasetChange(val) {
  const inst = groupInstances[activeRuler2GroupKey.value];
  if (!inst) return;
  inst.selectDatasetValue.value = val;
  inst.onDatasetChange(val);
  refreshR2();
}

function handleR2CheckAll(val) {
  const inst = groupInstances[activeRuler2GroupKey.value];
  if (!inst) return;
  inst.handleCheckAll(val);
  refreshR2();
}

// ===== 初始化所有 group =====
function initAllGroups() {
  if (!dataLoaded.value) return;
  // 初始化尺子一的所有 group
  for (const g of ruler1Groups) {
    const inst = groupInstances[g.groupKey];
    if (inst && !inst.isInited.value) {
      inst.init();
    }
  }
  // 初始化尺子二的所有 group
  for (const g of ruler2Groups) {
    const inst = groupInstances[g.groupKey];
    if (inst && !inst.isInited.value) {
      inst.init();
    }
  }
  refreshR1();
  refreshR2();
}

// ===== Group 切换 =====
watch(activeRuler1GroupKey, () => {
  const inst = groupInstances[activeRuler1GroupKey.value];
  if (inst && !inst.isInited.value) {
    inst.init();
  }
  refreshR1();
});

watch(activeRuler2GroupKey, () => {
  const inst = groupInstances[activeRuler2GroupKey.value];
  if (inst && !inst.isInited.value) {
    inst.init();
  }
  refreshR2();
});

// ===== 数据加载 =====
const loadChartData = async () => {
  const modelId = props.modelId;
  if (!modelId) {
    console.error("Err: model id is null.");
    return;
  }

  try {
    const modelStore = useAIModelStore();
    let data = modelStore.getModelById(modelId);
    if (!data) {
      try {
        data = await ModelService.getOneModelInfo(modelId);
      } catch {
        console.warn("getOneModelInfo failed, treat as both LLM and MLLM");
        data = null;
      }
    }

    const categories = data?.info?.category ?? ["LLM", "MLLM"];

    const [llmRes, multiRes] = await Promise.all([
      categories.includes("LLM") ? getCurrentFullRes() : Promise.resolve(null),
      categories.includes("MLLM") ? getMultiModelData() : Promise.resolve(null),
    ]);

    chartDataStore.value = {
      llm: llmRes?.data || null,
      multimodal: multiRes?.data || null,
    };

    dataLoaded.value = true;
    initAllGroups();
  } catch (error) {
    console.error("加载数据失败:", error);
  }
};

onMounted(async () => {
  await loadChartData();
});
</script>

<style scoped>
.model-compare-tab {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-top: 20px;
}

.ruler-section {
  display: flex;
  flex-direction: column;
  min-height: 700px;
}

.ruler-title {
  margin: 0 0 8px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1b3882;
}

.chartContainer {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.modality-tabs {
  display: flex;
  gap: 0;
  padding: 8px 16px;
  border-bottom: 1px solid rgb(230, 230, 230);
  flex-wrap: wrap;
}

.modality-tab {
  padding: 4px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  cursor: pointer;
  border-radius: 4px 4px 0 0;
  transition: all 0.2s;
  user-select: none;
}

.modality-tab:hover {
  color: #1b3882;
  background: rgba(27, 56, 130, 0.06);
}

.modality-tab.active {
  color: #1b3882;
  font-weight: 600;
  border-bottom: 2px solid #1b3882;
}
</style>