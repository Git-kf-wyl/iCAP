<template>
  <div class="dataset-progress-card">
    <div class="model-header">进度</div>
    <div
      v-for="(value, key) in localFormData"
      :key="key"
      class="dataset-container"
      style="display: block"
    >
      <div v-for="(item, key) in value" :key="key" class="dataset-container">
        <div class="dataset-name" :title="item.dataset_name">{{ item.dataset_name }}</div>
        <el-progress :percentage="item.progress * 100" class="progress-bar" />
      </div>
    </div>
  </div>
</template>
  
  <script lang="ts" setup>
import { ref, watch } from "vue";

const props = defineProps(["modelValue"]);
const emit = defineEmits(["update:modelValue"]);

const localFormData = ref(props.modelValue);

// const formData = ;
const hidePercentage = (percentage) => {
  return percentage.toFixed(0); // 返回空字符串以隐藏百分比
};

watch(
  localFormData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);
</script>
  
  <style scoped>
.dataset-progress-card {
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

.dataset-container :deep(.el-progress--line) {
  width: 600px;
}

.dataset-container {
  display: flex;
  align-items: center; /* 垂直居中对齐 */
  margin-bottom: 10px; /* 每个进度条之间的间距 */
}

.dataset-name {
  visibility: hidden;
  margin-right: 10px; /* 与进度条之间的间距 */
  width: 400px;
  white-space: nowrap; /* 防止文本换行 */
  overflow: hidden; /* 隐藏溢出的文本 */
  text-overflow: ellipsis; /* 显示省略号 */
}

.dataset-container .dataset-name {
  visibility: visible;
}

.progress-bar {
  flex: 1; /* 使进度条占据剩余空间 */
}
</style>
  