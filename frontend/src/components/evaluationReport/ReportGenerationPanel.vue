<template>
  <div class="container">
    <div class="titleContainer">
      <span style="padding: 0 5px"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:10px;" />
      <span style="padding: 0 20px;"></span>
      <span style="font-size:18px;font-weight:600;">生成报告</span>
    </div>

    <div class="report-header-buttons" style="justify-content: space-between;">
      <div class="report-type-section">
        <el-button v-if="canEvaluate" type="primary" class="customButton" @click="dialogVisible = true">生成报告</el-button>
        <el-button type="primary" class="customButton" @click="router.push('/PublishedReport');">
          已发布报告
          <el-icon>
            <Right />
          </el-icon>
        </el-button>
      </div>

      <el-table
        :data="tempTasksData"
        stripe
        height="750px"
        v-loading="tasksLoading"
        element-loading-text="加载中..."
        :header-cell-style="tableHeaderStyle"
        :row-key="(row) => row.task_id"
        :expand-row-keys="expandedRowKeys"
        @expand-change="onExpandChange"
      >
        <el-table-column type="expand">
          <template #default="props">
            <div
              v-for="(reportTypes, baseModel) in props.row.types"
              :key="baseModel"
              style="margin-bottom:12px;"
            >
              <div
                style="font-weight:600;font-size:14px;margin-bottom:6px;color:#303133;"
              >{{ baseModel }}</div>
              <el-descriptions border direction="vertical">
                <el-descriptions-item
                  v-for="(info, reportType) in reportTypes"
                  :key="reportType"
                  :label="reportType"
                >
                  {{info?.filter((item) => {
                  return item !== baseModel
                  }).join(', ') || '无'}}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务ID" align="center" show-overflow-tooltip />
        <el-table-column prop="report_name" label="报告名称" align="center" show-overflow-tooltip />
        <el-table-column prop="model_names" label="基准模型" align="center" show-overflow-tooltip />
        <!-- <el-table-column label="报告类型" align="center" show-overflow-tooltip>
          <template #default="{ row }">{{ Object.keys(row.types).join('、') }}</template>
        </el-table-column>-->
        <el-table-column prop="status" label="状态" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="large" v-if="row.status !== 'failed'">
              {{ row.status
              }}
            </el-tag>
            <el-tooltip :content="row.error" placement="top" v-else>
              <el-tag :type="statusTagType(row.status)" size="large">{{ row.status }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" align="center" />
        <el-table-column prop="complete_time" label="结束时间" align="center">
          <template #default="{ row }">{{ row.complete_time || '-' }}</template>
        </el-table-column>
        <el-table-column prop="userName" label="创建人" align="center" />
        <el-table-column label="操作" align="center" width="200">
          <template #default="{ row }">
            <el-tooltip content="预览" placement="top">
              <el-button
                link
                type="primary"
                size="large"
                :disabled="row.status !== 'completed'"
                @click="previewReport(row)"
              >
                <el-icon>
                  <View />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="下载" placement="top">
              <el-button
                link
                type="primary"
                size="large"
                :disabled="row.status !== 'completed'"
                @click="downloadTaskReport(row)"
              >
                <el-icon>
                  <Download />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip v-if="canEvaluate" content="发布" placement="top">
              <el-button
                link
                type="primary"
                size="large"
                :disabled="row.status !== 'completed'"
                @click="uploadReport(row)"
              >
                <el-icon>
                  <Upload />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip v-if="canEvaluate" content="删除" placement="top">
              <el-button
                link
                type="danger"
                size="large"
                :disabled="row.status === 'running'"
                @click="handleDeleteTask(row)"
              >
                <el-icon>
                  <Delete />
                </el-icon>
              </el-button>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="生成报告" width="760px" :close-on-click-modal="false">
      <div style="display:flex;flex-direction:column;gap:16px;">
        <!-- 报告名称 -->
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="white-space:nowrap;font-size:13px;color:#606266;min-width:56px;">报告名称</span>
          <div style="display:flex;flex-direction:column;gap:4px;">
            <el-input
              v-model="reportName"
              placeholder="留空则自动生成报告名称"
              style="width: 540px"
              clearable
            />
            <div
              v-if="!reportName && autoReportName"
              style="font-size:12px;color:#909399;padding-left:4px;line-height:1.3;"
            >
              <span style="color:#606266;">自动命名：</span>
              {{ autoReportName }}
            </div>
          </div>
          <el-tooltip content="未输入时将根据基准模型和报告类型自动命名，随选择实时变更" placement="top">
            <el-icon style="color:#909399;cursor:pointer;">
              <InfoFilled />
            </el-icon>
          </el-tooltip>
        </div>
        <!-- 选择基准模型 -->
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="white-space:nowrap;font-size:13px;color:#606266;min-width:56px;">基准模型</span>
          <el-select
            v-model="selectedBaseModels"
            multiple
            :multiple-limit="3"
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择基准模型，可输入模型名进行筛选(不分大小写)"
            style="width: 540px"
            clearable
            filterable
          >
            <el-option
              v-for="item in allModelOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <!-- 每个基准模型分别选报告类型和对比模型 -->
        <template v-for="bm in selectedBaseModels" :key="bm">
          <div style="border:1px solid #e8e8e8;border-radius:6px;padding:12px;">
            <div style="font-size:14px;font-weight:600;margin-bottom:10px;color:#303133;">{{ bm }}</div>
            <div style="display:flex;flex-direction:column;gap:10px;">
              <div style="display:flex;align-items:center;gap:8px;">
                <span style="white-space:nowrap;font-size:13px;color:#606266;min-width:56px;">报告类型</span>
                <el-select
                  :model-value="getBaseModelReportTypes(bm)"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择报告类型，模型暂无分数的类型为灰"
                  style="width: 540px"
                  @update:model-value="(v) => setBaseModelReportTypes(bm, v)"
                >
                  <el-option-group
                    v-for="group in getGroupedReportTypeOptions(bm)"
                    :key="group.label"
                    :label="group.label"
                  >
                    <el-option
                      v-for="item in group.options"
                      :key="item.value"
                      :label="item.label"
                      :value="item.value"
                    >
                      <span
                        :class="{ 'report-type-option-dimmed': !item.baseModelExists }"
                      >{{ item.label }}</span>
                    </el-option>
                  </el-option-group>
                </el-select>
              </div>
              <div
                v-for="rt in getBaseModelReportTypes(bm)"
                :key="rt"
                style="display:flex;align-items:center;gap:8px;padding-left:64px;"
              >
                <span class="report-type-label-dialog">{{ getReportTypeLabel(rt) }}对比模型</span>
                <el-select
                  :model-value="getBaseModelCompareModels(bm, rt)"
                  multiple
                  :multiple-limit="5"
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择对比模型，可输入模型名进行筛选(不分大小写)"
                  style="width: 420px"
                  @update:model-value="(v) => setBaseModelCompareModels(bm, rt, v)"
                  filterable
                >
                  <el-option
                    v-for="item in getCompareModelOptions(bm, rt)"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value"
                  />
                </el-select>
              </div>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleGenerateInDialog">生成报告</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {useEvaluationAccess} from '@/evaluationAccess';
const {canEvaluate}=useEvaluationAccess();
import { ref, computed, watch, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox, UploadInstance } from "element-plus";
import { InfoFilled, View } from "@element-plus/icons-vue";
import {
  downloadEvalReport,
  genReport,
  queryReportStatus,
  getAllReportTasks,
  deleteReportTask,
  publishReportFromTask,
} from "@/api/runService.js";
import { getCurrentFullRes, getMultiModelData } from "@/api/dataService.js";

const router = useRouter();
const goBack = () => {
  router.back();
};

const props = defineProps({});

const tempTasksData = ref([]);
const expandedRowKeys = ref([]);
const tasksLoading = ref(false);

const onExpandChange = (row, expandedRows) => {
  expandedRowKeys.value = expandedRows.map((r) => r.task_id);
};

const statusTagType = (status) => {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "primary";
    case "failed":
      return "danger";
    default:
      return "warning";
  }
};

const emit = defineEmits(["report-generated"]);

const dialogVisible = ref(false);
const selectedBaseModels = ref([]);
const reportName = ref("");

// 报告类型 value → 业务名称映射（用于展示）
const REPORT_TYPE_BIZ_NAME = {
  "0": "大语言通用",
  "1": "视觉通用",
  "2": "音频通用",
  "3": "AISF改写",
  "6": "AISF伴学",
  "7": "AISF操控规划",
  "8": "AISF操控执行",
  "9": "AISF意图",
  "10": "AISF记忆",
};

// 报告类型 value → 所属尺子
const getRuler = (rt) => {
  const cfg = REPORT_TYPE_SCENE_MAP[rt];
  if (!cfg) return null;
  return cfg.type === "ruler1" ? "ruler1" : "ruler2";
};

// 是否为「通用测试集」类型（尺子一）
const isRuler1Type = (rt) => getRuler(rt) === "ruler1";

/**
 * 为单个基准模型生成报告名称片段
 * 返回 { name: string, hasUserInput: boolean }
 */
const generateSingleModelReportName = (modelName, reportTypes) => {
  if (!reportTypes || reportTypes.length === 0)
    return { name: modelName, hasUserInput: false };

  const types = [...reportTypes];
  const bizNames = types.map((rt) => REPORT_TYPE_BIZ_NAME[rt] || `类型${rt}`);

  // 判断是否跨尺子
  const hasRuler1 = types.some((rt) => isRuler1Type(rt));
  const hasRuler2 = types.some((rt) => !isRuler1Type(rt));
  const crossRuler = hasRuler1 && hasRuler2;

  // 判断是否「全量」—— 所选类型是否覆盖了该尺子的全部报告类型
  // 注：不考虑模型在对应业务上是否有分数，所有模型的判断逻辑一致
  const ALL_R1_TYPES = REPORT_TYPE_DEFS.filter((d) =>
    isRuler1Type(d.value)
  ).map((d) => d.value);
  const ALL_R2_TYPES = REPORT_TYPE_DEFS.filter(
    (d) => !isRuler1Type(d.value)
  ).map((d) => d.value);

  const selectedR1 = types.filter((rt) => isRuler1Type(rt));
  const selectedR2 = types.filter((rt) => !isRuler1Type(rt));

  const r1Full =
    ALL_R1_TYPES.length > 0 && selectedR1.length === ALL_R1_TYPES.length;
  const r2Full =
    ALL_R2_TYPES.length > 0 && selectedR2.length === ALL_R2_TYPES.length;

  // ========== 不跨尺子 ==========
  if (!crossRuler) {
    const isR1 = hasRuler1; // 在 ruler1 内
    const rulerLabel = isR1 ? "通用" : "";

    // 全量
    if ((isR1 && r1Full) || (!isR1 && r2Full)) {
      const rulerName = isR1 ? "通用尺子一" : "通用尺子二";
      return { name: `${modelName}${rulerName}评估报告`, hasUserInput: false };
    }

    // 不全量，判断业务数
    const bizCount = isR1 ? selectedR1.length : selectedR2.length;

    if (bizCount <= 2) {
      // xxx模型zzz与yyy评估报告
      const names = isR1
        ? selectedR1.map((rt) => REPORT_TYPE_BIZ_NAME[rt])
        : selectedR2.map((rt) => REPORT_TYPE_BIZ_NAME[rt]);
      return {
        name: `${modelName}${names.join("与")}评估报告`,
        hasUserInput: false,
      };
    }

    // > 2：xxx模型(所有业务名称)评估报告
    const names = isR1
      ? selectedR1.map((rt) => REPORT_TYPE_BIZ_NAME[rt])
      : selectedR2.map((rt) => REPORT_TYPE_BIZ_NAME[rt]);
    return {
      name: `${modelName}（${names.join("+")}）评估报告`,
      hasUserInput: false,
    };
  }

  // ========== 跨尺子 ==========
  // 两个尺子均全量
  if (r1Full && r2Full) {
    return { name: `${modelName}全量评估报告`, hasUserInput: false };
  }

  // 收集所有选中的业务名
  const allBizNames = types.map((rt) => REPORT_TYPE_BIZ_NAME[rt]);

  if (types.length <= 2) {
    return {
      name: `${modelName}${allBizNames.join("与")}评估报告`,
      hasUserInput: false,
    };
  }

  return {
    name: `${modelName}（${allBizNames.join("+")}）评估报告`,
    hasUserInput: false,
  };
};

/**
 * 自动报告名称（computed，随选择实时变化）
 * 当用户手动输入时，使用用户输入；否则自动生成
 */
const autoReportName = computed(() => {
  if (reportName.value && reportName.value.trim()) {
    return reportName.value.trim(); // 用户手动输入，不覆盖
  }

  const bms = selectedBaseModels.value;
  if (bms.length === 0) return "";

  const parts = [];
  for (const bm of bms) {
    const types = baseModelReportTypes.value[bm] || [];
    if (types.length === 0) {
      parts.push(bm);
    } else {
      const { name } = generateSingleModelReportName(bm, types);
      parts.push(name);
    }
  }

  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0];
  // 多模型时，去除每个片段末尾的"评估报告"，只在最后统一加一次
  const stripped = parts.map((p) => p.replace(/评估报告$/, ""));
  return stripped.join(" & ") + "评估报告";
});

/** 每个基准模型选择的报告类型：{ "modelA": ["0", "1"], "modelB": ["6"] } */
const baseModelReportTypes = ref({});

/** 每个基准模型+报告类型选择的对比模型：{ "modelA_0": [...], "modelA_1": [...] } */
const baseModelCompareModels = ref({});

const getBaseModelReportTypes = (bm) => baseModelReportTypes.value[bm] ?? [];
const setBaseModelReportTypes = (bm, val) => {
  baseModelReportTypes.value[bm] = val;
};
const getBaseModelCompareModels = (bm, rt) =>
  baseModelCompareModels.value[`${bm}_${rt}`] ?? [];
const setBaseModelCompareModels = (bm, rt, val) => {
  baseModelCompareModels.value[`${bm}_${rt}`] = val;
};

/** 全部模型选项（去重），作为基准模型选择下拉的选项 */
const allModelOptions = computed(() => {
  const set = new Set();
  Object.values(reportTypeModelOptions.value).forEach((arr) => {
    arr.forEach((item) => set.add(item.value));
  });
  return Array.from(set).map((v) => ({ value: v, label: v }));
});

/** 基准模型在各报告类型下是否有数据 */
const baseModelExistsMap = ref({});

/** 尺子分组标签 */
const RULER_LABELS = {
  ruler1: "尺子一",
  ruler2: "尺子二",
};

/**
 * 获取某个基准模型的分组报告类型选项（按尺子分组）
 */
const getGroupedReportTypeOptions = (bm) => {
  const groups = { ruler1: [], ruler2: [] };
  const opts = getReportTypeOptionsForBaseModel(bm);
  for (const opt of opts) {
    const ruler = getRuler(opt.value) || "ruler1";
    groups[ruler].push(opt);
  }
  return [
    { label: RULER_LABELS.ruler1, options: groups.ruler1 },
    { label: RULER_LABELS.ruler2, options: groups.ruler2 },
  ];
};

/** 报告类型选项列表（合并基准模型存在状态）—— 全部报告类型都会显示，无数据的选项文字灰色 */
const reportTypeOptions = computed(() => {
  return REPORT_TYPE_DEFS.map((def) => ({
    ...def,
    baseModelExists: true, // 模板中用具体基准模型的值动态替换，这里占位
  }));
});

/**
 * 获取某个基准模型对应的 reportTypeOptions（每个选项标记 baseModelExists）
 */
const getReportTypeOptionsForBaseModel = (bm) => {
  return REPORT_TYPE_DEFS.map((def) => ({
    ...def,
    baseModelExists: baseModelExistsMap.value[bm]?.[def.value] ?? false,
  }));
};

/**
 * 获取对比模型选项，排除当前基准模型自身
 */
const getCompareModelOptions = (bm, rt) => {
  const all = getModelsForReportType(rt);
  return all.filter((item) => item.value !== bm);
};

// 报告类型定义 —— value 字段与业务场景的映射关系
const REPORT_TYPE_DEFS = [
  { label: "大语言", value: "0" },
  { label: "视觉", value: "1" },
  { label: "音频", value: "2" },
  { label: "AISF-改写", value: "3" },
  { label: "AISF-伴学", value: "6" },
  { label: "AISF-操控规划", value: "7" },
  { label: "AISF-操控执行", value: "8" },
  { label: "AISF-意图", value: "9" },
  { label: "AISF-记忆", value: "10" },
];

// 报告类型 → 业务场景映射
// ruler1 类型：
//   - scene === null：key 存在于 ruler1Data / mmlRuler1Data 即为可用
//   - scenes 数组：模型的 result 中包含 scenes 中至少一个 dataset_name 且有分数
// ruler2 类型：key 存在于 ruler2Data / mmlRuler2Data，且 result 中包含对应 dataset_name（scene）
const REPORT_TYPE_SCENE_MAP = {
  0: { source: "llm", type: "ruler1", scene: null },
  1: { source: "mml", type: "ruler1", scenes: ["MMMU", "MMStar", "Video-MME"] },
  2: {
    source: "mml",
    type: "ruler1",
    scenes: ["librispeech_asr", "MMAU", "MMAR", "WorldSense"],
  },
  3: { source: "llm", type: "ruler2", scene: "aisf_llm_gaixie" },
  6: { source: "mml", type: "ruler2", scene: "aisf_banxue" },
  7: { source: "mml", type: "ruler2", scene: "aisf_gui_plan" },
  8: { source: "mml", type: "ruler2", scene: "aisf_gui_vla" },
  9: { source: "llm", type: "ruler2", scene: "aisf_llm_yitu" },
  10: { source: "llm", type: "ruler2", scenes: ["aisf_memory_cuiqu", "aisf_memory_zhaohui"] },
};

// ========== 数据加载 ==========

/** ruler1Data: { [modelKey]: {...} } — key 存在即表示该模型有 ruler1 数据 */
let ruler1Data = null;
/** ruler2Data: { [modelKey]: { result: [{ dataset_name, metrics, ...}] } } */
let ruler2Data = null;
let mmlRuler1Data = null;
let mmlRuler2Data = null;

/**
 * 报告类型 → 可用对比模型列表（不含基准模型）
 * key: 报告类型 value，如 "0", "1", ...
 * value: [{ value: modelKey, label: modelKey }, ...]
 */
const reportTypeModelOptions = ref({});

const getModelsForReportType = (reportType) => {
  return reportTypeModelOptions.value[reportType] ?? [];
};

const getReportTypeLabel = (value) => {
  const opt = REPORT_TYPE_DEFS.find((o) => o.value === value);
  return opt ? opt.label : value;
};

// 基准模型选择变化时，清理已移除模型的数据，并清空报告名称输入
watch(selectedBaseModels, (newVal, oldVal) => {
  const removed = oldVal.filter((v) => !newVal.includes(v));
  removed.forEach((bm) => {
    delete baseModelReportTypes.value[bm];
    // 清理该基准模型关联的对比模型选择
    Object.keys(baseModelCompareModels.value).forEach((key) => {
      if (key.startsWith(bm + "_")) {
        delete baseModelCompareModels.value[key];
      }
    });
  });
  reportName.value = ""; // 清空用户输入，触发自动命名
});

// ========== 判断模型是否在 ruler2 的指定 scene 下有数据 ==========

/**
 * 判断 ruler2Data 中某个模型是否包含指定 scene 的数据
 * @param {object} data — ruler2Data 或 mmlRuler2Data
 * @param {string} modelKey — 模型标识
 * @param {string} scene — dataset_name，如 "operations", "aisf_llm_gaixie"
 */
const modelHasRuler2Scene = (data, modelKey, scene) => {
  const entry = data[modelKey];
  if (!entry || !Array.isArray(entry.result)) return false;
  return entry.result.some(
    (r) => r.dataset_name === scene && r.metrics?.length > 0
  );
};
/**
 * 判断 ruler1Data 中某个模型是否包含指定 scenes 中的至少一个测试集数据
 */
const modelHasRuler1Scenes = (data, modelKey, scenes) => {
  const entry = data[modelKey];
  if (!entry) return false;
  if (entry.result && Array.isArray(entry.result)) {
    return entry.result.some(
      (r) => scenes.includes(r.dataset_name)
      //  && r.metrics?.length > 0
    );
  }
  return true;
};

/**
 * 判断 ruler2Data 中某个模型是否包含指定 scenes 中的至少一个测试集数据（且有分数）
 */
const modelHasRuler2Scenes = (data, modelKey, scenes) => {
  const entry = data[modelKey];
  if (!entry || !Array.isArray(entry.result)) return false;
  return entry.result.some(
    (r) => scenes.includes(r.dataset_name) && r.metrics?.length > 0
  );
};

// ========== 加载数据并构建 reportTypeModelOptions / baseModelExistsMap ==========

const loadResultData = async () => {
  const llmData = (await getCurrentFullRes()).data;
  ruler1Data = llmData.ruler1;
  ruler2Data = llmData.ruler2;
  const multiData = (await getMultiModelData()).data;
  mmlRuler1Data = multiData.ruler1;
  mmlRuler2Data = multiData.ruler2;

  // 计算各报告类型的可用模型选项（全部模型，不做过滤）
  const options = {};

  for (const rt of Object.keys(REPORT_TYPE_SCENE_MAP)) {
    const cfg = REPORT_TYPE_SCENE_MAP[rt];
    let sourceData = null;

    if (cfg.source === "llm") {
      sourceData = cfg.type === "ruler1" ? ruler1Data : ruler2Data;
    } else {
      sourceData = cfg.type === "ruler1" ? mmlRuler1Data : mmlRuler2Data;
    }

    if (!sourceData) {
      options[rt] = [];
      continue;
    }

    const modelKeys = Object.keys(sourceData);
    const filtered = modelKeys
      .filter((key) => {
        if (cfg.scene === null) {
          return true;
        }
        if (cfg.scenes) {
          // ruler2 类型用 modelHasRuler2Scenes（检查 metrics 是否有值）
          if (cfg.type === "ruler2") {
            return modelHasRuler2Scenes(sourceData, key, cfg.scenes);
          }
          return modelHasRuler1Scenes(sourceData, key, cfg.scenes);
        }
        return modelHasRuler2Scene(sourceData, key, cfg.scene);
      })
      .map((key) => ({ value: key, label: key }));

    options[rt] = filtered;
  }

  reportTypeModelOptions.value = options;

  // 构建每个模型在每个报告类型下是否有数据的映射
  const existsMap = {};
  const allModelKeys = new Set();
  Object.values(options).forEach((arr) =>
    arr.forEach((item) => allModelKeys.add(item.value))
  );
  allModelKeys.forEach((modelKey) => {
    existsMap[modelKey] = {};
    for (const rt of Object.keys(REPORT_TYPE_SCENE_MAP)) {
      const cfg = REPORT_TYPE_SCENE_MAP[rt];
      let sourceData = null;
      if (cfg.source === "llm") {
        sourceData = cfg.type === "ruler1" ? ruler1Data : ruler2Data;
      } else {
        sourceData = cfg.type === "ruler1" ? mmlRuler1Data : mmlRuler2Data;
      }
      if (!sourceData) {
        existsMap[modelKey][rt] = false;
        continue;
      }
      if (!(modelKey in sourceData)) {
        existsMap[modelKey][rt] = false;
        continue;
      }
      if (cfg.scene === null) {
        existsMap[modelKey][rt] = true;
        continue;
      }
      if (cfg.scenes) {
        // ruler2 类型用 modelHasRuler2Scenes
        if (cfg.type === "ruler2") {
          existsMap[modelKey][rt] = modelHasRuler2Scenes(
            sourceData,
            modelKey,
            cfg.scenes
          );
        } else {
          existsMap[modelKey][rt] = modelHasRuler1Scenes(
            sourceData,
            modelKey,
            cfg.scenes
          );
        }
        continue;
      }
      existsMap[modelKey][rt] = modelHasRuler2Scene(
        sourceData,
        modelKey,
        cfg.scene
      );
    }
  });
  baseModelExistsMap.value = existsMap;
};

// ========== 报告生成（异步 + 轮询） ==========

const handleGenerateInDialog = () => {
  if (selectedBaseModels.value.length === 0) {
    ElMessage({ type: "warning", message: "请至少选择一个基准模型" });
    return;
  }

  // 校验每个基准模型是否选择了报告类型和对比模型
  for (const bm of selectedBaseModels.value) {
    const types = baseModelReportTypes.value[bm];
    if (!types || types.length === 0) {
      ElMessage({
        type: "warning",
        message: `请为基准模型"${bm}"选择报告类型`,
      });
      return;
    }
    for (const rt of types) {
      const cm = baseModelCompareModels.value[`${bm}_${rt}`];
      if (!cm || cm.length === 0) {
        ElMessage({
          type: "warning",
          message: `请为基准模型"${bm}"的报告类型"${getReportTypeLabel(
            rt
          )}"选择对比模型`,
        });
        return;
      }
    }
  }

  // 使用最终的报告名称（用户输入的或自动生成的）
  const finalReportName = autoReportName.value || `评估报告_${Date.now()}`;

  ElMessage({ type: "success", message: "正在生成报告，请稍候..." });

  // 构造接口参数：单次调用，传入所有基准模型
  const modelNames = [...selectedBaseModels.value];
  const modelIds = [...selectedBaseModels.value];
  const compareModels = {};
  const compareType = {};

  for (const bm of modelNames) {
    const types = baseModelReportTypes.value[bm];
    const bmCompareModels = {};
    for (const rt of types) {
      bmCompareModels[rt] = baseModelCompareModels.value[`${bm}_${rt}`];
    }
    compareModels[bm] = bmCompareModels;
    compareType[bm] = [...types].sort().join(",");
  }

  genReport({
    model_name: modelNames,
    model_id: modelIds,
    compare_models: compareModels,
    compare_type: compareType,
    report_name: finalReportName,
    userName: localStorage.getItem("username"),
  })
    .then((response) => {
      const taskId = response.data.task_id;
      loadTasksData();
      dialogVisible.value = false;
    })
    .catch((err) => {
      ElMessage({
        type: "error",
        message:
          "发起生成报告失败: " + (err.response?.data?.error || err.message),
      });
      loadTasksData();
    });
};

// ========== 页面加载时恢复报告状态 ==========

/**
 * 从后端获取本模型的全部报告生成任务，填充表格
 */
const loadTasksData = async () => {
  try {
    const resp = await getAllReportTasks();
    tempTasksData.value = resp.data; // 后端返回已按 create_time 倒序排列的列表
  } catch (err) {
    console.warn("获取报告任务列表失败:", err);
  } finally {
    tasksLoading.value = false;
  }
};

/**
 * 下载表格中某行对应的报告
 */
const downloadTaskReport = (row) => {
  if (!row.filepath) {
    ElMessage({ type: "warning", message: "该任务无报告文件可下载" });
    return;
  }
  downloadEvalReport({ filepath: row.filepath })
    .then((response) => {
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = row.filepath.split("/").pop().split("\\").pop();
      a.click();
      window.URL.revokeObjectURL(url);
      ElMessage({ type: "success", message: "下载成功" });
    })
    .catch((err) => {
      ElMessage({
        type: "error",
        message: "下载失败: " + (err.response?.data?.error || err.message),
      });
    });
};

const uploadReport = async (row) => {
  if (!row.filepath) {
    ElMessage({ type: "warning", message: "该任务无报告文件可发布" });
    return;
  }
  try {
    await publishReportFromTask({
      task_id: row.task_id,
      // userName: localStorage.getItem("username"),
    });
    ElMessage({ type: "success", message: "发布成功" });
  } catch (err) {
    ElMessage({
      type: "error",
      message: "发布失败: " + (err.response?.data?.error || err.message),
    });
  }
};

/**
 * 删除表格中某行对应的报告任务（弹出确认框）
 */
const handleDeleteTask = (row) => {
  ElMessageBox.confirm(
    `确定删除任务 "${row.task_id}" 吗？此操作不可恢复。`,
    "删除确认",
    { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" }
  )
    .then(async () => {
      try {
        await deleteReportTask(row.task_id);
        ElMessage({ type: "success", message: "删除成功" });
        await loadTasksData();
      } catch (err) {
        ElMessage({
          type: "error",
          message: "删除失败: " + (err.response?.data?.error || err.message),
        });
      }
    })
    .catch(() => {
      // 用户取消，不做处理
    });
};

const previewReport = (row) => {
  if (!row.filepath) {
    ElMessage({ type: "warning", message: "该报告无文件可预览" });
    return;
  }
  const url = router.resolve({
    name: "ReportPreview",
    query: { filepath: row.filepath, taskId: row.task_id },
  });
  router.push(url.href);
};

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
};

let tasksPollTimer = null;

onMounted(async () => {
  tasksLoading.value = true;
  await loadResultData();
  await loadTasksData();
  tasksPollTimer = setInterval(loadTasksData, 15000);
});

onBeforeUnmount(() => {
  if (tasksPollTimer) {
    clearInterval(tasksPollTimer);
  }
});
</script>

<style scoped>
.report-type-section {
  display: flex;
  justify-content: space-between; /* 关键属性：左右贴边对齐 */
  align-items: center; /* 垂直居中 */
  width: 100%; /* 确保容器有宽度 */
}

.customButton {
  font-size: 14px;
  /* 移除浮动和边距 */
}

/* 图标样式保持不变 */
.customButton :deep(.circular) {
  margin-top: 10px;
  width: 25px;
  height: 25px;
}

.report-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.report-header-buttons {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0 10px;
  padding: 10px;
  background-color: #fff;
  /* border-bottom: 1px solid rgb(230, 230, 230); */
}

.el-table__expand-icon > .el-icon {
  font-size: 20px;
}

/* 基准模型没有数据的报告类型：下拉选项文字灰色 */
:deep(.report-type-option-dimmed) {
  color: #c0c4cc !important;
}

.report-type-label-dialog {
  font-size: 13px;
  white-space: nowrap;
  color: #606266;
  min-width: 56px;
}

.titleContainer {
  background-color: #fff;
  line-height: 50px;
  height: 50px;
}

.container {
  /* gap: 0; */
  /* margin: 0; */
  max-width: 100%;
}
</style>
