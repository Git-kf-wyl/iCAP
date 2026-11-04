<template>
  <div>
    <div style="margin: 0 auto; width: 90%">
      <div style="margin-bottom: 20px;">任务参数</div>
      <el-form
        :model="localFormData"
        label-width="auto"
        style="max-width: 95%"
        label-position="left"
        :disabled="taskId!==''"
      >
        <el-form-item prop="task_name" label="任务名称">
          <el-input v-model="localFormData.task_name" placeholder="请输入任务名称" />
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();

const taskId = ref("");

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

const getTaskInfo = () => {
  if (route.query.task_id) {
    taskId.value = route.query.task_id;
  }
};

onMounted(() => {
  getTaskInfo();
});
</script>