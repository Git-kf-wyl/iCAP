// ============= 测试集对比页共享配置 =============
// 尺子二 scene key → 测试集标签（数据集库 testcase_tags 中的取值，用于定位"使用中"测试集）
export const SCENE_TAG_MAP = {
  aisf_memory_cuiqu: "记忆",
  aisf_memory_zhaohui: "记忆",
  aisf_gui_plan: "GUI",
  aisf_gui_vla: "GUI",
  aisf_banxue: "儿童伴读",
  aisf_llm_gaixie: "改写",
  aisf_llm_yitu: "意图",
  aisf_llm_skilltican: "skill提参",
  aisf_llm_guican: "GUI提参",
  aisf_llm_banxue: "伴学提参",
  aisf_llm_coordinator: "Coordinator",
};

// 尺子二 scene key → 展示名（当找不到"使用中"测试集名称时兜底显示）
export const SCENE_LABELS = {
  aisf_memory_cuiqu: "记忆萃取",
  aisf_memory_zhaohui: "记忆召回",
  aisf_gui_plan: "VLM(GUI操控规划)",
  aisf_gui_vla: "VLA(GUI操控执行)",
  aisf_banxue: "伴学",
  aisf_llm_gaixie: "改写",
  aisf_llm_yitu: "意图",
  aisf_llm_skilltican: "skill提参",
  aisf_llm_guican: "GUI提参",
  aisf_llm_banxue: "伴学提参",
  aisf_llm_coordinator: "Coordinator",
};

// 尺子二场景合并组：同一个测试集在榜单上表现为多个独立子类榜单，对比页需合并为一页上下展示
export const SCENE_GROUPS = {
  aisf_memory_cuiqu: ["aisf_memory_cuiqu", "aisf_memory_zhaohui"],
  aisf_memory_zhaohui: ["aisf_memory_cuiqu", "aisf_memory_zhaohui"],
  aisf_gui_plan: ["aisf_gui_plan", "aisf_gui_vla"],
  aisf_gui_vla: ["aisf_gui_plan", "aisf_gui_vla"],
};

// 标签容错匹配：支持全等 / 互相包含
export function matchTag(tag, key) {
  return tag === key || (tag && key && (tag.includes(key) || key.includes(tag)));
}

// 从某测试集的 testcase_tags 中解析出场景配置 key（记忆/GUI/儿童伴读/改写/...）
export function resolveTagKey(testcaseTags = []) {
  const known = Object.values(SCENE_TAG_MAP);
  for (const tag of testcaseTags) {
    const hit = known.find((k) => matchTag(tag, k));
    if (hit) return hit;
  }
  return testcaseTags[0] || "";
}

// 由测试集 testcase_tags 反推尺子二 scene 列表（供 datasetDetail 的对比 tab 使用）
export function resolveScenesByTags(testcaseTags = []) {
  const tagKey = resolveTagKey(testcaseTags);
  if (!tagKey) return [];
  const scenes = Object.keys(SCENE_TAG_MAP).filter(
    (k) => SCENE_TAG_MAP[k] === tagKey
  );
  if (scenes.length === 0) return [];
  return SCENE_GROUPS[scenes[0]] || scenes;
}
