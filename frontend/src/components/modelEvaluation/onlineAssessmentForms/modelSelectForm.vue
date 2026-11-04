<template>
  <div style="margin: 40px auto; width: 800px">
    <el-form
      :model="localFormData"
      ref="form1Ref"
      label-width="auto"
      style="max-width: 600px"
      label-position="left"
      hide-required-asterisk
      class="custom-form"
      size="large"
      :rules="rules"
      :disabled="is_run"
    >
      <el-form-item label="模型名称" prop="model">
        <el-cascader
          v-model="localFormData.model_id"
          :options="options"
          :props="{ emitPath: false, expandTrigger: 'click' }"
          placeholder="请选择模型"
        />
      </el-form-item>
    </el-form>
  </div>
</template>

<script lang="ts" setup>
import {
  ref,
  watch,
  reactive,
  onMounted,
  computed,
  inject,
  provide,
} from "vue";
import { useAIModelStore } from "@/stores/aiModel";
import { ModelService } from "@/services/modelService.js";

const store = useAIModelStore();
const props = defineProps(["modelValue"]);
const emit = defineEmits(["update:modelValue"]);
const models_option = reactive([]);

const assessmentType = inject("assessmentType");

const localFormData = ref(props.modelValue);
const rules = reactive({
  model_id: [{ required: true, message: "请选择模型名称", trigger: "change" }],
});

const is_run = inject("is_run");

watch(
  localFormData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);

const options = ref([]);
const normalOptions = ref([]);
const translateOption = ref([]);

watch(assessmentType, (newVal, oldVal) => {
  console.log("assessmentType");
  console.log(assessmentType.value);
  if (newVal === "同声传译评估") {
    localFormData.value.model_id = "";
    options.value = translateOption.value;
  } else if (newVal !== "同声传译评估") {
    localFormData.value.model_id =
      oldVal === "同声传译评估" ? "" : localFormData.value.model_id;
    options.value = normalOptions.value;
  }
});

onMounted(async () => {
  if (Array.isArray(store.models) && store.models.length !== 0) {
    Object.assign(models_option, store.models);
  } else {
    try {
      const data = await ModelService.getAllModelInfo();
      store.setModels(data);
      Object.assign(models_option, store.models);
    } catch (error) {
      console.error(error);
    }
  }
  normalOptions.value = models_option.reduce((acc, item) => {
    const series = item.info.series;
    const model = item.model_id;
    const enabled = item.is_available && item.status;
    if (!enabled) return acc;
    // 查找是否已经存在该 series
    let seriesItem = acc.find((obj) => obj.value === series);

    // 如果不存在，则创建新的 series 项
    if (!seriesItem) {
      seriesItem = {
        value: series,
        label: series,
        children: [],
      };
      acc.push(seriesItem);
    }

    // 将 model 添加到 children 数组中
    seriesItem.children.push({
      value: model,
      label: model,
      disabled: !enabled,
    });

    return acc;
  }, []);
  translateOption.value = [
    {
      value: "同声传译模型",
      label: "同声传译模型",
      children: [
        {
          value: "同声传译模型01",
          label: "同声传译模型01",
          disabled: false,
        },
        // {
        //   value: "同声传译模型02",
        //   label: "同声传译模型02",
        //   disabled: false,
        // },
      ],
    },
  ];
  if (assessmentType.value !== "同声传译评估") {
    options.value = normalOptions.value;
  } else {
    options.value = translateOption.value;
  }
});
</script>
