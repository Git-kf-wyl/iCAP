/**
 * Chart Group 配置 — 定义 modelCompareTab.vue 中 7 组 chart 的结构
 *
 * 尺子一：大语言 / 视觉 / 音频
 * 尺子二：AISF-伴学 / AISF-改写 / AISF-GUI规划 / AISF-GUI操控
 */
import {
  LLM_RULER1_DIMENSIONS,
  LLM_RULER1_DEFAULT_DIMENSIONS,
  LLM_RULER2_DATASETS,
  MLLM_RULER2_DATASETS,
  LLM_RULER2_OPTIONS,
  MLLM_RULER2_OPTIONS,
  VISUAL_DIMENSIONS,
  AUDIO_DIMENSIONS,
} from "./evaluationReportConstants.js";

/** 从 MLLM_RULER2_OPTIONS 中提取指定场景的子集列表 */
function getSubsetsByScene(options, sceneValue) {
  const group = options.find((g) => g.value === sceneValue);
  return group ? group.children.map((c) => c.value) : [];
}

/**
 * 7 组 chart 的统一配置
 *
 * 字段说明：
 *  - tab:             归属 tab（"ruler1" | "ruler2"）
 *  - groupKey:        唯一标识
 *  - label:           显示名称
 *  - dataSource:      数据来源（"llm" = getCurrentFullRes, "multimodal" = getMultiModelData）
 *  - rulerType:       尺子类型（"ruler1" | "ruler2"）
 *  - dimensions:      该组所有可选测试集维度
 *  - defaultDimensions: 默认选中的维度
 *  - scene:           仅 ruler2 有效，对应的 scene key
 */
export const CHART_GROUPS = [
  // ====== 尺子一 ======
  {
    tab: "ruler1",
    groupKey: "llmGeneral",
    label: "大语言",
    dataSource: "llm",
    rulerType: "ruler1",
    dimensions: [...LLM_RULER1_DIMENSIONS],
    defaultDimensions: [...LLM_RULER1_DEFAULT_DIMENSIONS],
    scene: null,
  },
  {
    tab: "ruler1",
    groupKey: "visualGeneral",
    label: "视觉",
    dataSource: "multimodal",
    rulerType: "ruler1",
    dimensions: [...VISUAL_DIMENSIONS],
    defaultDimensions: [...VISUAL_DIMENSIONS],
    scene: null,
  },
  {
    tab: "ruler1",
    groupKey: "audioGeneral",
    label: "音频",
    dataSource: "multimodal",
    rulerType: "ruler1",
    dimensions: [...AUDIO_DIMENSIONS],
    defaultDimensions: [...AUDIO_DIMENSIONS],
    scene: null,
  },

  // ====== 尺子二 ======
  {
    tab: "ruler2",
    groupKey: "aisf_banxue",
    label: "AISF-伴学",
    dataSource: "multimodal",
    rulerType: "ruler2",
    scene: "aisf_banxue",
    dimensions: getSubsetsByScene(MLLM_RULER2_OPTIONS, "aisf_banxue"),
    defaultDimensions: getSubsetsByScene(MLLM_RULER2_OPTIONS, "aisf_banxue"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_llm_gaixie",
    label: "AISF-改写",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_llm_gaixie",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_gaixie"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_gaixie"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_gui_plan",
    label: "AISF-GUI规划",
    dataSource: "multimodal",
    rulerType: "ruler2",
    scene: "aisf_gui_plan",
    dimensions: getSubsetsByScene(MLLM_RULER2_OPTIONS, "aisf_gui_plan"),
    defaultDimensions: getSubsetsByScene(MLLM_RULER2_OPTIONS, "aisf_gui_plan"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_gui_vla",
    label: "AISF-GUI操控",
    dataSource: "multimodal",
    rulerType: "ruler2",
    scene: "aisf_gui_vla",
    dimensions: getSubsetsByScene(MLLM_RULER2_OPTIONS, "aisf_gui_vla"),
    defaultDimensions: getSubsetsByScene(MLLM_RULER2_OPTIONS, "aisf_gui_vla"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_llm_yitu",
    label: "AISF-意图",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_llm_yitu",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_yitu"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_yitu"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_memory_cuiqu",
    label: "记忆萃取",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_memory_cuiqu",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_memory_cuiqu"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_memory_cuiqu"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_memory_zhaohui",
    label: "记忆召回",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_memory_zhaohui",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_memory_zhaohui"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_memory_zhaohui"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_llm_skilltican",
    label: "skill提参",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_llm_skilltican",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_skilltican"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_skilltican"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_llm_guican",
    label: "GUI提参",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_llm_guican",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_guican"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_guican"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_llm_banxue",
    label: "伴学提参",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_llm_banxue",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_banxue"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_banxue"),
  },
  {
    tab: "ruler2",
    groupKey: "aisf_llm_coordinator",
    label: "Coordinator",
    dataSource: "llm",
    rulerType: "ruler2",
    scene: "aisf_llm_coordinator",
    dimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_coordinator"),
    defaultDimensions: getSubsetsByScene(LLM_RULER2_OPTIONS, "aisf_llm_coordinator"),
  },
];

/** 按 tab 分组 */
export const GROUPS_BY_TAB = {
  ruler1: CHART_GROUPS.filter((g) => g.tab === "ruler1"),
  ruler2: CHART_GROUPS.filter((g) => g.tab === "ruler2"),
};
