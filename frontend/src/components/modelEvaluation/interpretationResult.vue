<template>
  <div class="onlineContainer">
    <div class="detailTitleContainer">
      <span style="padding: 0 14px"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:28px;" />
      <span style="padding: 0 20px;"></span>
      <span @click="goBack" style="color: #969696;cursor: pointer;">同声传译</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>
      <span style="font-size:18px;font-weight:600;">总体评测结果</span>
    </div>
    <!-- <el-tabs v-model="activeTypeTab" class="tabsContainer"> -->
    <!-- <el-tab-pane label="同声传译" name="interpretation"> -->
    <el-tabs v-model="activeSceneTab" class="tabsContainer" type="card">
      <el-tab-pane label="ASR" name="asr" style="height: 100%">
        <ASRResult v-if="activeSceneTab === 'asr'" />
      </el-tab-pane>
      <el-tab-pane label="MT" name="mt" style="height: 100%">
        <MTResult v-if="activeSceneTab === 'mt'" />
      </el-tab-pane>
      <el-tab-pane label="TTS" name="tts">
        <TTSResult v-if="activeSceneTab === 'tts'" />
      </el-tab-pane>
      <el-tab-pane label="ASR+MT" name="asrmt">
        <ASRMTResult v-if="activeSceneTab === 'asrmt'" />
      </el-tab-pane>
      <el-tab-pane label="ASR+MT+TTS" name="asrmttts">
        <ASRMTTTSResult v-if="activeSceneTab === 'asrmttts'" />
      </el-tab-pane>
    </el-tabs>
    <!-- </el-tab-pane> -->
    <!-- </el-tabs> -->
  </div>
</template>


<script lang="ts" setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import type { TableColumnCtx } from "element-plus";
import ASRResult from "./interpretationResult/asrResult.vue"
import MTResult from "./interpretationResult/mtResult.vue"
import TTSResult from "./interpretationResult/ttsResult.vue"
import ASRMTResult from "./interpretationResult/asrmtResult.vue"
import ASRMTTTSResult from "./interpretationResult/asrmtttsResult.vue"

const route = useRoute();
const router = useRouter();

const activeTypeTab = ref("interpretation");
const activeSceneTab = ref("asr");

const model_name = ref("");

const goBack = () => {
  router.back();
};

const tableHeaderStyle = {
  textAlign: "center",
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
};

interface User {
  scene: string;
  model_name: string;
  time: string;
  directoryD: string;
}

interface SpanMethodProps {
  row: User;
  column: TableColumnCtx<User>;
  rowIndex: number;
  columnIndex: number;
}

onMounted(async () => {});
</script>


<style scoped>
.onlineContainer {
  /* background-color: #f5f5f5; */
  width: 100%;
  height: 90%;
  min-height: calc(100vh - 60px);
  /* height: auto; */
  display: flex;
  /* max-width: 95%; */
  min-width: 100%;
  /* gap: 12px; */
  position: relative;
  flex-direction: column;
  /* padding: 10px; */
}

.detailTitleContainer {
  display: flex;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  /* margin-left: 15px; */
  margin-bottom: 10px;
}

.dataContainer {
  background-color: #d1bdbd;
  width: 100%;
  height: calc(100vh - 60px);
  /* display: flex; */
  /* padding: 20px; */
  max-width: 100%;
  /* padding: 0 20px; */
  gap: 12px;
  position: relative;
  flex-direction: row;
}

.taskDetailTitleContainer {
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  /* margin-bottom: 18px; */
}

.tabsContainer {
  height: 93%;
}

.tabsContainer :deep(.el-tabs__header) {
  margin-left: 20px;
}

.tabsContainer :deep(.el-tabs__content) {
  height: 50% !important;
}

.head_card {
  display: flex;
  align-items: center;
  width: 98%;
  height: 60px;
  border-radius: 8px;
  background: rgb(255, 255, 255);
  padding: 5px 0px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  /* border-radius: 4px; */
  margin-top: 10px;
  margin-left: 20px;
}

.dataCardContainer {
  display: flex;
  flex-direction: column;
  background-color: #ffffff;
  margin: 0 20px;
  border-radius: 8px;
  height: 100%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.interpretationDetailTable {
  width: 100%;
  /* margin: 20px 1% 0 1%; */
}
</style>
