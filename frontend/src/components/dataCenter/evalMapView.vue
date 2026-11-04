<template>
  <div class="eval-map-container">
    <iframe
      :src="iframeSrc"
      class="eval-map-frame"
      title="评测地图"
      frameborder="0"
      allowfullscreen
    ></iframe>
  </div>
</template>

<script lang="ts" setup>
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

/**
 * 将前端 history 路由映射为 llm_bench 的 hash 子页面。
 * /evalMap             -> #/overview       研究总览
 * /evalMap/benchmarks  -> #/benchmarks     Benchmark 浏览器
 * /evalMap/capabilities-> #/capabilities   能力图谱
 * /evalMap/vendors     -> #/vendors        厂商关注
 * /evalMap/compare     -> #/compare        对比工作台
 * /evalMap/methodology -> #/methodology    方法论与 SMART
 */
const pageMap: Record<string, string> = {
  benchmarks: "benchmarks",
  capabilities: "capabilities",
  vendors: "vendors",
  compare: "compare",
  methodology: "methodology",
};

const hashFragment = computed(() => {
  const path = route.path;
  const segment = path.replace(/^\/evalMap\/?/, "");
  return pageMap[segment] || "overview";
});

const iframeSrc = computed(() => `/llm_bench/index.html#/${hashFragment.value}`);
</script>

<style scoped>
.eval-map-container {
  width: 100%;
  height: 100%;
  background: #fff;
}
.eval-map-frame {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}
</style>