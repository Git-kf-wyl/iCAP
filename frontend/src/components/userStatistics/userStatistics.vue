<template>
  <div>
    <el-tabs v-model="activeName" class="tabs" @tab-click="handleClick">
      <el-tab-pane label="用户运营" name="user">
        <component v-if="activeName === 'user'" :is="UserOperational" />
      </el-tab-pane>
      <el-tab-pane label="评测运营" name="eval">
        <component v-if="activeName === 'eval'" :is="EvaluationOperational" />
      </el-tab-pane>
      <el-tab-pane label="API Key" name="apikey">
        <component v-if="activeName === 'apikey'" :is="ApiKeyPage" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import UserOperational from "./index.vue";
import EvaluationOperational from "@/components/statistics/statistics.vue";
import ApiKeyPage from "./apiKeyPage.vue";

const route = useRoute();
const router = useRouter();

// 根据当前路由路径决定激活的 tab
const tabMap: Record<string, string> = {
  "/userStatistics": "user",
  "/userStatistics/eval": "eval",
  "/userStatistics/apikey": "apikey",
};

const routeMap: Record<string, string> = {
  user: "/userStatistics",
  eval: "/userStatistics/eval",
  apikey: "/userStatistics/apikey",
};

const activeName = ref(tabMap[route.path] || "user");

// 监听路由变化，同步 tab
watch(
  () => route.path,
  (path) => {
    const tab = tabMap[path];
    if (tab) {
      activeName.value = tab;
    }
  }
);

const handleClick = (tab: any) => {
  const path = routeMap[tab.props.name];
  if (path) {
    router.push(path);
  }
};
</script>

<style scoped>
.tabs {
  margin: 0 20px;
}

.tabs :deep(.el-tabs__header) {
  margin: 0 0 5px !important;
}
</style>