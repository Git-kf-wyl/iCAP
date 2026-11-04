<template>
  <div>
    <div>测评参数</div>
    <div style="margin: 40px auto; width: 100%">
      <el-form
        :model="localFormData"
        label-width="auto"
        style="max-width: 95%"
        label-position="left"
        class="custom-form"
        size="large"
        :disabled="is_run"
        :rules="rules"
      >
        <el-form-item prop="name" label="name">
          <el-input v-model="localFormData.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item prop="language" label="language" v-if="isTranslate">
          <el-select v-model="localFormData.language" placeholder="请选择语言" class="el_input">
            <el-option
              v-for="item in languageOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item prop="limit" label="limit" v-if="!isTranslate">
          <el-input v-model.number="localFormData.limit" placeholder="请输入limit" />
        </el-form-item>
        <el-form-item prop="temperature" label="temperature" v-if="!isTranslate">
          <el-input
            v-model.number="localFormData.temperature"
            placeholder="请输入temperature"
            type="number"
          />
        </el-form-item>
        <el-form-item
          prop="eval_batch_size"
          label="eval_batch_size"
          v-if="!isTranslate && !isMemory"
        >
          <el-input
            v-model.number="localFormData.eval_batch_size"
            placeholder="请输入eval_batch_size"
          />
        </el-form-item>
        <el-form-item
          prop="stream"
          label="stream"
          v-if="!isTranslate && !isRewriteTask && !isYitu &&!isMemory &&!isSkill"
        >
          <el-radio v-model="localFormData.stream" :label="true">是</el-radio>
          <el-radio v-model="localFormData.stream" :label="false">否</el-radio>
        </el-form-item>

        <el-form-item prop="description" label="描述">
          <el-input
            v-model="localFormData.description"
            style="max-width: 100%"
            :rows="3"
            type="textarea"
            placeholder="请输入评测任务描述"
          />
        </el-form-item>

        <!-- 改写业务任务参数 -->
        <!-- <template v-if="isRewriteTask">
          <el-divider>
            <h3>
              <b>改写业务参数</b>
            </h3>
          </el-divider>
          <el-form-item prop="enable_fewshot" label="enable_fewshot">
            <el-radio v-model="localFormData.enable_fewshot" :label="true">是</el-radio>
            <el-radio v-model="localFormData.enable_fewshot" :label="false">否</el-radio>
          </el-form-item>
          <el-form-item prop="enable_fixed_fewshot" label="enable_fixed_fewshot">
            <el-radio v-model="localFormData.enable_fixed_fewshot" :label="true">是</el-radio>
            <el-radio v-model="localFormData.enable_fixed_fewshot" :label="false">否</el-radio>
          </el-form-item>
          <el-form-item prop="fewshot_retrieval_mode" label="fewshot_retrieval_mode">
            <el-select
              v-model="localFormData.fewshot_retrieval_mode"
              placeholder="请选择"
              class="el_input"
            >
              <el-option label="query" value="query" />
              <el-option label="prev_crurent" value="prev_crurent" />
            </el-select>
          </el-form-item>
          <el-form-item prop="fewshot_example_field" label="fewshot_example_field">
            <el-select
              v-model="localFormData.fewshot_example_field"
              placeholder="请选择"
              class="el_input"
            >
              <el-option label="no_thought_example" value="no_thought_example" />
              <el-option label="prompt_example" value="prompt_example" />
            </el-select>
          </el-form-item>
          <el-form-item prop="fewshot_top_k" label="fewshot_top_k">
            <el-input
              v-model.number="localFormData.fewshot_top_k"
              placeholder="请输入fewshot_top_k"
              type="number"
            />
          </el-form-item>
          <el-form-item prop="fewshot_score_threshold" label="fewshot_score_threshold">
            <el-input
              v-model.number="localFormData.fewshot_score_threshold"
              placeholder="请输入fewshot_score_threshold"
              type="number"
            />
          </el-form-item>
          <el-form-item prop="max_fewshot_examples" label="max_fewshot_examples">
            <el-input
              v-model.number="localFormData.max_fewshot_examples"
              placeholder="请输入max_fewshot_examples"
              type="number"
            />
          </el-form-item>
          <el-form-item prop="max_context_turns" label="max_context_turns">
            <el-input
              v-model.number="localFormData.max_context_turns"
              placeholder="请输入max_context_turns"
              type="number"
            />
          </el-form-item>
        </template> -->
      </el-form>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, watch, computed, inject, onMounted } from "vue";
import type { FormRules } from "element-plus";

const rules = ref({
  name: [{ required: true, message: "请输入任务名称", trigger: "blur" }],
  temperature: [
    { type: "number", message: "温度必须是数字", trigger: "blur" },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === undefined || value === "") {
          return callback();
        }
        const num = Number(value);
        if (isNaN(num)) {
          return callback(new Error("温度必须是数字"));
        }
        if (num >= 0 && num < 1) {
          return callback();
        }
        return callback(new Error("温度必须在 0~1 之间（不含 1）"));
      },
      trigger: "blur",
    },
  ],
});
const evaluationType = inject("evaluationType");

const m_formData = inject("m_formData");
const d_formData = inject("d_formData");
const is_run = inject("is_run");
const assessmentType = inject("assessmentType");
const isTranslate = ref(false);

// 辅助函数：检测 dataset_args 中是否有任意项的 testcase_tags 包含指定标签
const hasTag = (tag: string): boolean => {
  const datasetArgs: any[] = (d_formData as any)?.dataset_args || [];
  if (!datasetArgs.length) return false;
  return datasetArgs.some((item: any) => item.testcase_tags?.includes(tag));
};

/** 检测当前选中的测试集中是否有 testcase_tags 包含 "改写" */
const isRewriteTask = computed(() => hasTag("改写"));

/** 检测当前选中的测试集中是否有 testcase_tags 包含 "意图" */
const isYitu = computed(() => hasTag("意图"));

/** 检测当前选中的测试集中是否有 testcase_tags 包含 "记忆" */
const isMemory = computed(() => hasTag("记忆"));

/** 检测当前选中的测试集中是否有 testcase_tags 包含 "skill提参" */
const isSkill = computed(() => hasTag("skill提参"));

/** 检测当前选中的测试集中是否有 testcase_tags 包含 "GUI提参" */
const isGUI = computed(() => hasTag("GUI提参"));

// 定义类型
interface DynamicField {
  label: string;
  value: string;
}

interface FormData {
  // model_id: string;
  // eval_type: string;
  limit: number;
  // filters: string;
  stream: boolean;
  // generation_config: object;
  // dynamicFields: DynamicField[];
  // datasets: [];
  // metric_list: string;
  // use_cache: string;
  assessmentType: string;
  // system_prompt: string;
  name: string;
  temperature: number;
  eval_batch_size: number;
  request_retry: boolean;
  retry_content_none: boolean;
  description: string;
  // 改写业务参数
  enable_fewshot?: boolean;
  enable_fixed_fewshot?: boolean;
  fewshot_retrieval_mode?: string;
  fewshot_example_field?: string;
  fewshot_top_k?: number;
  fewshot_score_threshold?: number;
  max_fewshot_examples?: number;
  max_context_turns?: number;
}

// 定义 Props 和 Emits
const props = defineProps<{
  modelValue: FormData;
}>();
const emit = defineEmits<{
  (e: "update:modelValue", value: FormData): void;
}>();

// 使用类型化的 ref
const localFormData = ref<FormData>({
  ...props.modelValue,
  // request_retry: false,
  // retry_content_none: false,
  // assessmentType: assessmentType,
});

const languageOptions = [
  {
    value: "enar",
    label: "enar",
  },
  {
    value: "aren",
    label: "aren",
  },
];

watch(
  localFormData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);

onMounted(() => {
  isTranslate.value = assessmentType.value === "同声传译评估";
  console.log(isTranslate.value);
  if (!isTranslate.value) {
    const baseFormData = {
      ...props.modelValue,
      request_retry: false,
      retry_content_none: false,
      assessmentType: assessmentType,
    };
    // 只在改写任务时才赋值改写相关参数
    if (isRewriteTask.value) {
      localFormData.value = {
        ...baseFormData,
        enable_fewshot: true,
        enable_fixed_fewshot: true,
        fewshot_retrieval_mode: "query",
        fewshot_example_field: "no_thought_example",
        fewshot_top_k: 5,
        fewshot_score_threshold: 0.61,
        max_fewshot_examples: 5,
        max_context_turns: 5,
      };
    } else {
      localFormData.value = baseFormData;
    }
  }
  // console.log('modelValue');
  // console.log(props.modelValue);
  // if (m_formData) {
  //   localFormData.value.model_id = (m_formData as { model_id: string }).model_id;
  //   localFormData.value.eval_type = (m_formData as { eval_type: string }).eval_type;
  //   localFormData.value.datasets = (d_formData as { datasets: [] }).datasets;
  //   localFormData.value.assessmentType = assessmentType as string;
  // }
});

// 添加字段
const addField = () => {
  localFormData.value.dynamicFields.push({
    label: "",
    value: "",
  });
};

// 删除字段
const removeField = (index: number) => {
  localFormData.value.dynamicFields.splice(index, 1);
};

// const generationConfigString = computed({
//   get: () => {
//     return JSON.stringify(localFormData.value.generation_config, null, 2);
//   },
//   set: (value) => {
//     try {
//       localFormData.value.generation_config = JSON.parse(value);
//     } catch (error) {
//       console.error("Invalid JSON:", error);
//     }
//   },
// });

// 监听 generation_config 的变化，确保数据始终是有效的 JSON
watch(
  () => localFormData.value.generation_config,
  (newValue) => {
    if (typeof newValue !== "object" || newValue === null) {
      console.error("generation_config should be an object");
      localFormData.value.generation_config = {};
    }
  }
);
</script>

<style scoped>
.dynamic-field {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  border-radius: 8px;
}

.value-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.delete-btn {
  flex-shrink: 0;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .dynamic-field {
    flex-direction: column;
    align-items: stretch;
  }

  .value-container {
    width: 100%;
  }
}

:deep(.el-input input::-webkit-outer-spin-button),
:deep(.el-input input::-webkit-inner-spin-button) {
  -webkit-appearance: none !important;
}
:deep(.el-input input[type="number"]) {
  -moz-appearance: textfield;
}
:deep(.el-input .el-input__inner) {
  line-height: 1px !important;
}
</style>
