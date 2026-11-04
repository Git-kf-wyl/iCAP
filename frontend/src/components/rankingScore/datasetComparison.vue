<template>
  <div class="ds-comparison-container">
    <div class="TitleContainer">
      <span style="padding: 0 8px;"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" />
      <span style="padding: 0 20px;"></span>
      <span @click="goBack" style="color: #969696; cursor: pointer;">模型榜单</span>
      <span style="padding: 0 8px; font-weight: 600; font-size: 18px;">/</span>
      <span style="font-weight: 600; font-size: 18px;">{{ pageTitle }}</span>
    </div>
    <div class="ds-content" v-loading="loading">
      <div v-if="sections.length === 0 && !loading" class="null-data">暂无数据</div>
      <div v-for="sec in sections" :key="sec.title" class="chart-wrapper">
        <CompareBarChart :title="sec.title" :data="sec.chartData" />
      </div>
      <div v-if="!loading" class="hint-text">
        本页展示各模型在此测试集上的得分对比，数据来源于平台评测榜单。
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getCurrentFullRes, getMultiModelData } from "@/api/dataService.js";
import { get_datasets } from "@/api/dataSetApi.js";
import { useDatasetStore } from "@/stores/datasetStore";
import CompareBarChart from "./compareBarChart.vue";
import {
  SCENE_TAG_MAP,
  SCENE_LABELS,
  matchTag,
} from "./datasetComparisonConfig";

const props = defineProps({
  fromTab: { type: String, default: "" },
  datasetKey: { type: String, default: "" },
  scenes: { type: Array, default: null },
  displayName: { type: String, default: "" },
});

const route = useRoute();
const router = useRouter();
const datasetStore = useDatasetStore();

const loading = ref(true);
const sections = ref([]);
const pageTitle = ref("");

let fullRuler1 = {};
let fullRuler2 = {};
let multiRuler1 = {};
let multiRuler2 = {};

const fromTab = computed(() => props.fromTab || route.query.fromTab || "ruler1");
const datasetKey = computed(() => props.datasetKey || route.query.datasetKey || "");
const displayName = computed(() => props.displayName || route.query.displayName || "");
const scenes = computed(() => {
  if (props.scenes && props.scenes.length > 0) return props.scenes;
  const q = route.query.scenes;
  if (q) return String(q).split(",").filter(Boolean);
  return [];
});

function normalizeMatch(str) {
  return String(str || "").replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}

function getItems(group) {
  if (Array.isArray(group)) return group;
  return group?.result || [];
}

function hasSceneData(src, scene) {
  return Object.values(src || {}).some((g) =>
    getItems(g).some((item) => item.dataset_name === scene)
  );
}

function collectSceneChart(scene, rawData) {
  const map = new Map();
  Object.entries(rawData).forEach(([model, group]) => {
    const hit = (getItems(group)).find((item) => item.dataset_name === scene);
    if (hit && hit.score != null && !map.has(model)) map.set(model, hit.score);
  });
  return [...map.entries()].map(([name, value]) => ({ name, value }));
}

function collectBanxueSubChart(rawData, subName) {
  const map = new Map();
  Object.entries(rawData).forEach(([model, group]) => {
    const hit = (getItems(group)).find((item) => item.dataset_name === "aisf_banxue");
    if (!hit) return;
    const sub = (hit.metrics || [])
      .flatMap((m) => m.categories || [])
      .flatMap((c) => c.subsets || [])
      .find((s) => s.name === subName);
    if (sub && sub.score != null && !map.has(model)) map.set(model, sub.score);
  });
  return [...map.entries()].map(([name, value]) => ({ name, value }));
}

function collectRuler1Chart(dsKey) {
  const map = new Map();
  const keyNorm = normalizeMatch(dsKey);
  [fullRuler1, multiRuler1].forEach((src) => {
    Object.entries(src).forEach(([model, group]) => {
      const hit = (getItems(group)).find(
        (item) => normalizeMatch(item.dataset_name) === keyNorm
      );
      if (hit && hit.score != null && !map.has(model)) map.set(model, hit.score);
    });
  });
  return [...map.entries()].map(([name, value]) => ({ name, value }));
}

function findInUseDatasetName(tag) {
  const all = datasetStore.ruler2Datasets || {};
  const candidates = Object.values(all).filter((d) =>
    (d.testcase_tags || []).some((t) => matchTag(t, tag))
  );
  const inUse = candidates.filter(
    (d) => d.in_use === true || d.in_use === 1 || d.in_use === "1" || d.in_use === "true"
  );
  const pool = inUse.length > 0 ? inUse : candidates;
  pool.sort(
    (a, b) => new Date(b.establish_time || 0) - new Date(a.establish_time || 0)
  );
  return pool[0]?.dataset_name || "";
}

function buildSections() {
  const list = [];
  if (fromTab.value === "ruler1") {
    pageTitle.value = displayName.value || datasetKey.value || "测试集对比";
    list.push({ title: displayName.value || datasetKey.value, chartData: collectRuler1Chart(datasetKey.value) });
  } else {
    const sceneList = scenes.value.length > 0 ? scenes.value : [];
    const firstScene = sceneList[0];
    const tag = firstScene ? SCENE_TAG_MAP[firstScene] : "";
    const inUseName = tag ? findInUseDatasetName(tag) : "";
    pageTitle.value =
      inUseName || (firstScene ? SCENE_LABELS[firstScene] : "测试集对比");
    sceneList.forEach((scene) => {
      if (scene === "aisf_banxue") {
        const raw = Object.keys(multiRuler2).length > 0 ? multiRuler2 : fullRuler2;
        list.push({ title: "注意力检测", chartData: collectBanxueSubChart(raw, "注意力检测") });
        list.push({ title: "坐姿检测", chartData: collectBanxueSubChart(raw, "坐姿检测") });
      } else {
        // 优先取 full 源；改写在 full 中有数据但不在多模态 multi 中，
        // 因此按场景动态判断，避免硬编码名单遗漏导致“暂无数据”
        const raw = hasSceneData(fullRuler2, scene)
          ? fullRuler2
          : multiRuler2;
        list.push({
          title: SCENE_LABELS[scene] || scene,
          chartData: collectSceneChart(scene, raw),
        });
      }
    });
  }
  sections.value = list;
}

const goBack = () => {
  router.back();
};

onMounted(async () => {
  loading.value = true;
  try {
    const [fullRes, multiRes] = await Promise.all([
      getCurrentFullRes(),
      getMultiModelData(),
    ]);
    fullRuler1 = fullRes.data?.ruler1 || {};
    fullRuler2 = fullRes.data?.ruler2 || {};
    multiRuler1 = multiRes.data?.ruler1 || {};
    multiRuler2 = multiRes.data?.ruler2 || {};
    if (fromTab.value === "ruler2") {
      const dsRes = await get_datasets(2);
      datasetStore.setDatasets("ruler2", dsRes.data);
    }
    buildSections();
  } catch (err) {
    console.error("加载测试集对比数据失败", err);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.ds-comparison-container {
  box-sizing: border-box;
  overflow: auto;
  background-color: rgb(245, 245, 245);
  width: 100%;
  min-height: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
}
.TitleContainer {
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  margin-bottom: 10px;
  flex-shrink: 0;
}
.ds-content {
  flex: 1 1 0;
  min-height: 0;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin: 0 10px 10px;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: auto;
}
.chart-wrapper {
  width: 100%;
  flex: 1 1 0;
  min-height: 320px;
}
.null-data {
  text-align: center;
  padding: 60px 0;
  color: #909399;
}
.hint-text {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  flex-shrink: 0;
}
</style>
