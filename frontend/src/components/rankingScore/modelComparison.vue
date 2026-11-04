<template>
  <div class="comparisonContainer">
    <div class="TitleContainer">
      <span style="padding: 0 8px;"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" />
      <span style="padding: 0 20px;"></span>
      <span @click="goBack" style="color: #969696;cursor: pointer;">模型榜单</span>
      <span style="padding: 0 8px;font-weight:600;font-size:18px;">/</span>
      <span style="font-weight:600;font-size:18px;">{{ route.query.modelName }}</span>
    </div>
    <div class="ms-content">
      <!-- <el-tabs v-model="activeTab">
      <el-tab-pane label="模型对比" name="0">-->
      <ModelCompareTab
        :modelName="modelName"
        :modelId="(route.query.modelName as string) || ''"
        :defaultTab="defaultTab"
        :defaultSubKey="(route.query.fromSubKey as string) || ''"
      />
      <!-- </el-tab-pane> -->
      <!-- <el-tab-pane label="评估报告" name="1">
          <ReportGenerationPanel
            :modelName="modelName"
            :modelId="(route.query.modelName as string) || ''"
          />
      </el-tab-pane>-->
      <!-- </el-tabs> -->
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import ModelCompareTab from "@/components/modelSquare/modelCompareTab.vue";

const route = useRoute();
const router = useRouter();

const modelName = route.query.modelName as string;

// 从 rankingScore 页面进入时携带的上下文，决定默认展示哪个 tab
// 只有当来自尺子一+大语言模型 或 尺子二+改写时，默认"大语言"，其余默认"多模态"
const defaultTab = computed(() => {
  const fromTab = route.query.fromTab as string;
  const fromModality = route.query.fromModality as string;
  const fromSubKey = route.query.fromSubKey as string;

  // if (fromTab === "ruler1" && fromModality === "llm") return "LLM";
  // if (fromTab === "ruler2" && fromSubKey === "aisf_llm_gaixie") return "LLM";
  // return "MLLM";
  return fromTab
});

const goBack = () => {
  router.back();
};

const activeTab = ref("0");
</script>

<style scoped>
.comparisonContainer {
  box-sizing: border-box;
  overflow: auto;
  background-color: rgb(245, 245, 245);
  width: 100%;
  min-height: 100%;
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
}

.ms-content {
  flex: 1 1 0;
  overflow: hidden;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  margin: 5px 10px 0 10px;
  height: 100%;
  padding: 0 24px 0 24px;
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  /* gap: 16px; */
  overflow: auto;
}

.ms-content :deep(.el-tabs__header) {
  margin: 0;
}
</style>