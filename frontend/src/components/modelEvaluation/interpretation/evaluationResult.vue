<template>
    <div class="model-score-card">
      <div class="model-header">测试结果</div>
      <div
        v-for="(value, key) in localFormData"
        :key="key"
        class="dataset-container"
        style="display: block"
      >
        <!-- <h1 style="margin: 20px 0">{{ model }}</h1> -->
        <div v-for="(item, key) in value" :key="key" class="dataset-container">
          <div class="datsSetContainer">
            <el-icon v-if="expandedDatasets[item.dataset_name]" size="25">
              <ArrowDownBold />
            </el-icon>
            <div class="dataset-name" :title="item.dataset_name">{{ item.dataset_name }}</div>
            <el-progress
              :percentage="item.score*100"
              :text-inside="false"
              :format="hidePercentage"
              class="progress-bar"
            />
          </div>
        </div>
      </div>
    </div>
  </template>
  
  <script lang="ts" setup>
  import { ref, watch, reactive, onMounted } from "vue";
  
  const props = defineProps(["modelValue"]);
  const emit = defineEmits(["update:modelValue"]);
  
  const localFormData = ref(props.modelValue);
  
  watch(
    localFormData,
    (newVal) => {
      emit("update:modelValue", newVal);
    },
    { deep: true }
  );
  
  const rate = (name) => {
    if (name === "service_emotion" || name === "service_style") {
      return 20;
    } else {
      return 100;
    }
  };
  
  // 原始数据
  const rawData = {};
  
  const hidePercentage = (percentage) => {
    return percentage.toFixed(2); // 返回空字符串以隐藏百分比
  };
  
  const modelName = ref("");
  const datasets = ref({});
  
  const expandedDatasets = ref({});
  
  // 初始化数据
  onMounted(() => {
    console.log("localFormData");
    console.log(localFormData.value);
    if (localFormData.value === undefined) {
      return;
    }
    // 获取模型名称
    modelName.value = Object.keys(localFormData.value)[0] || "";
  
    // 安全处理数据转换
    if (
      localFormData.value[modelName.value] &&
      Array.isArray(localFormData.value[modelName.value])
    ) {
      const scores = {};
      localFormData.value[modelName.value].forEach((item) => {
        scores[item.dataset_name] = item.score;
      });
      datasets.value = scores;
    } else {
      console.error("Invalid data structure:", localFormData.value);
      datasets.value = {};
    }
  
    Object.keys(datasets.value).forEach((key) => {
      expandedDatasets.value[key] = false;
    });
  });
  
  // 根据分数返回进度条样式类
  const getProgressClass = (score) => {
    if (score >= 0.7) return "high";
    if (score >= 0.5) return "medium";
    return "low";
  };
  
  const toggleDataset = (name) => {
    expandedDatasets.value[name] = !expandedDatasets.value[name];
  };
  </script>
  
  <style scoped>
  .hide-percentage .el-progress-text {
    display: none;
  }
  
  .model-score-card {
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    /* max-width: 600px; */
    width: 95%;
    margin: 20px auto;
    padding: 25px;
    border-radius: 12px;
    background: #ffffff;
  }
  
  .model-header {
    text-align: left;
    margin: 25px 0;
    padding-bottom: 15px;
    border-bottom: 1px solid #eee;
  }
  
  .model-header h2 {
    color: #2c3e50;
    margin: 0;
    font-size: 1.8rem;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  
  .dataset-container :deep(.el-progress--line) {
    width: 500px;
  }
  
  .dataset-container {
    display: flex;
    flex-direction: column;
    /* align-items: center;  */
    /* 垂直居中对齐 */
    margin-bottom: 10px;
    /* 每个进度条之间的间距 */
  }
  
  .dataset-name {
    visibility: hidden;
    margin-right: 10px;
    /* 与进度条之间的间距 */
    width: 400px;
    white-space: nowrap;
    /* 防止文本换行 */
    overflow: hidden;
    /* 隐藏溢出的文本 */
    text-overflow: ellipsis;
    /* 显示省略号 */
  }
  
  .dataset-container .dataset-name {
    visibility: visible;
  }
  
  .progress-bar {
    flex: 1;
    /* 使进度条占据剩余空间 */
  }
  
  .datsSetContainer {
    display: flex;
    margin: 20px 0;
    line-height: 25px;
  }
  </style>
  