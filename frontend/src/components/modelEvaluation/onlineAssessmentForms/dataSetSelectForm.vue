<template>
  <div style="margin: 40px auto; width: 100%">
    <el-form
      :model="localFormData"
      ref="form1Ref"
      label-width="auto"
      style="max-width: 95%"
      label-position="top"
      hide-required-asterisk
      class="custom-form"
      size="large"
      :disabled="is_run"
    >
      <el-form-item label="基准" prop="datasets">
        <!-- <el-cascader
            v-model="localFormData.datasets"
            :options="baselineOptions"
            :props="{ multiple: true, emitPath: false }"
            placeholder="请选择基准"
            style="width: 100%;"
        />-->
        <el-select
          v-model="localFormData.datasets"
          multiple
          clearable
          placeholder="请选择"
          class="el_input"
        >
          <el-option
            v-for="(value, key) in baselineOptions2"
            :key="key"
            :label="(value as { 'dataset_name': string }).dataset_name"
            :value="key"
            :disabled="isRestrictedModeActive && !isSelectedDataset(key)"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <!-- 记忆测试集子业务表格 -->
    <template v-for="(rowData, rowIndex) in tableData" :key="rowIndex">
      <div v-if="rowData.isMemory" class="memory-dataset-block">
        <div class="memory-dataset-header">
          <span class="memory-dataset-title">{{ rowData.dataset_name }}（记忆）</span>
        </div>
        <el-table :data="rowData.memoryBusinessParams" border style="width:100%;" class="memory-sub-table">
          <el-table-column label="选择" width="60">
            <template #default="scope">
              <el-checkbox v-model="scope.row.selected" :disabled="is_run" />
            </template>
          </el-table-column>
          <el-table-column prop="name" label="子业务" min-width="120" />
          <el-table-column prop="prompt_version" label="prompt_version" min-width="140">
            <template #default="scope">
              <el-input v-model="scope.row.prompt_version" placeholder="请输入" size="small" :disabled="is_run" />
            </template>
          </el-table-column>
          <el-table-column prop="eval_type" label="eval_type" min-width="140">
            <template #default="scope">
              <el-input v-model="scope.row.eval_type" placeholder="请输入" size="small" :disabled="is_run" />
            </template>
          </el-table-column>
          <el-table-column prop="use_fewshot" label="use_fewshot" min-width="120">
            <template #default="scope">
              <el-select v-model="scope.row.use_fewshot" placeholder="请选择" size="small" :disabled="is_run">
                <el-option label="true" :value="true" />
                <el-option label="false" :value="false" />
              </el-select>
            </template>
          </el-table-column>
         <el-table-column prop="judge_prompt" label="裁判prompt" min-width="140">
            <template #default="scope">
              <el-input type="textarea" v-model="scope.row.judge_prompt" placeholder="judge_prompt" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="Prompt文件" min-width="220">
            <template #default="scope">
              <div v-if="scope.row.promptFileList && scope.row.promptFileList.length > 0" style="display:flex;flex-direction:column;gap:4px;">
                <el-radio-group v-model="scope.row.selectedPromptFile" size="small" :disabled="is_run">
                  <el-radio v-for="(pf, idx) in scope.row.promptFileList" :key="idx" :value="pf.url" style="margin-right:0;margin-bottom:2px;">
                    {{ pf.name }}
                  </el-radio>
                </el-radio-group>
              </div>
              <span v-else style="color:#999;font-size:12px;">无</span>
            </template>
          </el-table-column>
          <el-table-column label="测试集文件" min-width="220">
            <template #default="scope">
              <div v-if="scope.row.testFileList && scope.row.testFileList.length > 0" style="display:flex;flex-direction:column;gap:4px;">
                <el-radio-group v-model="scope.row.selectedTestFile" size="small" :disabled="is_run">
                  <el-radio v-for="(tf, idx) in scope.row.testFileList" :key="idx" :value="tf.url" style="margin-right:0;margin-bottom:2px;">
                    {{ tf.name }}
                  </el-radio>
                </el-radio-group>
              </div>
              <span v-else style="color:#999;font-size:12px;">无</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- 非记忆测试集表格 -->
    <el-table
      ref="multipleTable"
      :data="nonMemoryTableData"
      tooltip-effect="dark"
      :cell-style="{ textAlign: 'center' }"
      :header-cell-style="{ 'text-align': 'center' }"
      class="dataSelectTable"
      v-if="nonMemoryTableData.length > 0"
    >
      <el-table-column prop="dataset_name" label="测试集" min-width="135" show-overflow-tooltip></el-table-column>
      <el-table-column label="编辑" width="80" v-if="!is_run">
        <template #default="scope">
          <el-button link type="primary" @click="editCell(scope.$index,scope.row)">
            <el-icon>
              <Edit />
            </el-icon>
          </el-button>
        </template>
      </el-table-column>
      <el-table-column type="expand" label="超参  " width="70" v-if="evaluationType!=='multiple'">
        <template #default="props">
          <el-input
            v-model="props.row.generate_config"
            placeholder="请输入generation_config"
            type="textarea"
            :rows="2"
            :disabled="true"
          />
        </template>
      </el-table-column>
      <el-table-column
        prop="metric_list"
        label="metric_list"
        width="180"
        v-if="evaluationType!=='multiple'"
      >
        <template #default="scope">
          <el-select
            v-model="scope.row.metric_list"
            multiple
            clearable
            collapse-tags
            placeholder="请选择"
            class="el_input"
            :disabled="true"
          >
            <el-option
              v-for="value in scope.row.allMetrics"
              :key="value"
              :label="value"
              :value="value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column prop="subset_list" label="subset_list" min-width="160">
        <template #default="scope">
          <el-select
            v-model="scope.row.subset_list"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="默认"
            class="el_input"
            :disabled="true"
          >
            <el-option
              v-for="value in scope.row.AllSubsetList"
              :key="value"
              :label="value"
              :value="value"
            />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column
        prop="system_prompt"
        label="Sys Prompt"
        width="160"
        show-overflow-tooltip
        v-if="assessmentType==='AISF开发评估' || isStudy || isYitu"
      >
        <template #default="scope">
          {{ scope.row.system_prompt }}
        </template>
      </el-table-column>
      <el-table-column
        prop="user_prompt"
        label="User Prompt"
        width="160"
        show-overflow-tooltip
        v-if="assessmentType==='AISF开发评估' || isStudy"
      >
        <template #default="scope">
          {{ scope.row.user_prompt }}
        </template>
      </el-table-column>
      <el-table-column
        prop="eval_batch_size"
        label="并发数"
        width="90"
        v-if="evaluationType!=='multiple'"
      >
        <template #default="scope">
          {{ scope.row.eval_batch_size }}
        </template>
      </el-table-column>
    </el-table>
    <!-- <div style="margin: 20px 10px">generation_config</div> -->
    <!-- <div v-for="item in localFormData.datasets" :key="item">
      <div style="display: flex; margin-top: 10px">
        <div style="width: 200px; text-align: center">
          {{ item }}
        </div>
        <div>
          <el-input
            style="width: 400px"
            v-model="generationConfigString"
            placeholder="请输入generation_config"
            type="textarea"
            :rows="7"
          />
        </div>
      </div>
    </div>-->
    <!-- 普通测试集编辑弹窗 -->
    <el-dialog
      :title="editTitle"
      v-model="showEditDialog"
      width="30%"
      draggable
      :modal="false"
      top="10vh"
    >
      <el-form
        :model="formData"
        label-width="auto"
        :rules="rules"
        ref="addFormRef"
        style="max-width: 600px"
      >
        <el-form-item label="metric_list" prop="metric_list" v-if="evaluationType!=='multiple'">
          <el-select
            multiple
            clearable
            collapse-tags
            placeholder="请选择metric_list"
            class="el_input"
            v-model="formData.metric_list"
          >
            <el-option v-for="value in allMetrics" :key="value" :label="value" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="subset_list" prop="subset_list">
          <el-select
            v-model="formData.subset_list"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            max-collapse-tags="4"
            placeholder="默认"
            class="el_input"
          >
            <el-option v-for="value in allSubsetList" :key="value" :label="value" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="System Prompt" prop="System Prompt" v-if="assessmentType==='AISF开发评估' || isStudy || isYitu">
          <el-input type="textarea" v-model="formData.system_prompt" :rows="5"></el-input>
        </el-form-item>
        <el-form-item label="User Prompt" prop="User Prompt" v-if="assessmentType==='AISF开发评估' || isStudy">
          <el-input type="textarea" v-model="formData.user_prompt" :rows="5"></el-input>
        </el-form-item>
        <el-form-item label="并发数" prop="并发数" v-if="evaluationType!=='multiple'">
          <el-input v-model.number="formData.eval_batch_size" type="number"></el-input>
        </el-form-item>
        <el-divider style="margin-top: 30px;" v-if="evaluationType!=='multiple'">
          <h3>
            <b>模型超参列表</b>
          </h3>
        </el-divider>
        <el-form-item label="超参" prop="generate_config" v-if="evaluationType!=='multiple'">
          <div
            v-for="(item, index) in generate_configs"
            :key="index"
            style="display:flex; align-items:center; margin-bottom:8px;"
          >
            <el-input
              v-model="item.key"
              placeholder="Key"
              style="margin-right:8px;"
              :disabled="item.key==='chat_template_kwargs'"
            />
            <el-input
              v-model.number="item.value"
              placeholder="Value"
              style="margin-right:8px;"
              type="number"
              :disabled="item.key==='chat_template_kwargs'"
            />
            <el-button size="small" type="danger" :icon="Minus" @click="removeParam(index)" circle />
          </div>
          <el-button
            type="primary"
            style="min-width: 150px; margin-left: auto"
            @click="addParam()"
          >添加参数</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeDialog">取 消</el-button>
          <el-button type="primary" @click="commitSubmit">确 定</el-button>
        </div>
      </template>
    </el-dialog>
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
  nextTick,
} from "vue";
import { get_datasets } from "@/api/dataSetApi";
import { useAIModelStore } from "@/stores/aiModel";
import { useDatasetStore } from "@/stores/datasetStore";
import {
  ArrowDown,
  ArrowUp,
  Download,
  Upload,
  Minus,
} from "@element-plus/icons-vue";
// import Sortable from "sortablejs";
import { ModelService } from "@/services/modelService.js";
import { ElMessage, FormInstance, FormRules, tabBarProps } from "element-plus";

const props = defineProps(["modelValue"]);
const emit = defineEmits(["update:modelValue"]);
const m_formData = inject("m_formData");
const first_time = inject("first_time");
const datasetStore = useDatasetStore();
const store = useAIModelStore();
const edit = ref(false);
const line = ref(0);
const localFormData = ref(props.modelValue);
const baselineOptions2 = reactive({});
const models = reactive([]);
const gen_config = reactive({});
// const select_item = ref([]);

const config = ref({
  max_tokens: 4096,
  temperature: 0.6,
  top_p: 0.95,
  top_k: 40,
});

const generate_configs = ref([
  {
    key: "max_tokens",
    value: 4096,
  },
  { key: "temperature", value: 0.6 },
  { key: "top_p", value: 0.95 },
  { key: "top_k", value: 40 },
]);

const generationConfig = computed(() => {
  return {
    default: {
      ...config.value,
      request_nums: 4,
    },
    ifeval: {
      ...config.value,
      request_nums: 1,
    },
    bfcl_v3: {
      ...config.value,
      request_nums: 1,
    },
    mmlu: {
      ...config.value,
      request_nums: 1,
    },
    mmlu_redux: {
      ...config.value,
      request_nums: 1,
    },
  };
});

const eval_batch_size = ref({
  default: 1,
  ifeval: 4,
  bfcl_v3: 4,
  mmlu: 4,
  mmlu_redux: 4
});

const ruler2_eval_batch_size = ref({
  default: 4,
});

const domainConfig = ref({
  max_tokens: 65536,
  temperature: 0.01,
  top_p: 0.8,
  top_k: 20,
  request_nums: 1,
  chat_template_kwargs: { enable_thinking: false },
});

const domainGenerationConfig = computed(() => {
  return {
    default: {
      ...domainConfig.value,
    },
    aisf_intent: {
      max_tokens: 65536,
      temperature: 0,
      request_nums: 1,
      chat_template_kwargs: { enable_thinking: false },
    },
    box_tool_use: {
      max_tokens: 65536,
      temperature: 0,
      top_p: 1,
      top_k: 1,
      request_nums: 1,
      chat_template_kwargs: { enable_thinking: false },
    },
    service_emotion: {
      max_tokens: 65536,
      presence_penalty: 0.5,
      request_nums: 1,
      chat_template_kwargs: { enable_thinking: false },
    },
    service_style: {
      max_tokens: 65536,
      temperature: 0.8,
      request_nums: 1,
      chat_template_kwargs: { enable_thinking: false },
    },
    service_parameter_extract: {
      ...domainConfig.value,
    },
    service_tool_select: {
      ...domainConfig.value,
    },
    service_intent: {
      ...domainConfig.value,
    },
    om_task: {
      max_tokens: 65536,
      temperature: 0.01,
      top_p: 0.95,
      top_k: 40,
      request_nums: 1,
      chat_template_kwargs: { enable_thinking: false },
    },
  };
});

const metric_list = ref({
  default: ["AveragePass@1"],
});

const evaluationType = inject("evaluationType");

// 在线评估（onlineEvaluation.vue）同时展示大语言与多模态测试集
const showAllDatasets = evaluationType === "online";
const assessmentType = inject("assessmentType");
const is_run = inject("is_run");

const devDatasets = reactive({
  AISF: { dataset_name: "AISF" },
});
const domainDatasets = reactive({
  AISF: { dataset_name: "AISF" },
  意图识别: { dataset_name: "算力主机/意图识别" },
  告警E2E: { dataset_name: "运维只能/告警E2E" },
});

const LLM_RULER1_LABELS = ['知识百科', '逻辑推理', '数学', '代码', '工具', '指令遵从', '长文本','Agent']
const LLM_RULER2_LABELS = [
  // '运维智能', '业务智能', '算力主机', 'AISF',
   '儿童伴读','改写','意图','记忆','skill提参','GUI提参','伴学提参','Coordinator']
const LLM_RULER3_LABELS = ['运维智能', '业务智能', '算力主机', 'AISF']

const allMetrics = ref([]);
const allSubsetList = ref([]);

const editCell = (index, row) => {
  console.log("row");
  console.log(row);
  console.log("localFormData");
  console.log(localFormData.value.dataset_args);
  edit.value = true;
  line.value = index;
  // Object.assign(formData, row);
  Object.keys(row).forEach((key) => {
    formData[key] = row[key];
  });
  // console.log("formData");
  // console.log(formData);
  allMetrics.value = row.allMetrics;
  allSubsetList.value = row.AllSubsetList;
  editTitle.value = row.dataset_name + "编辑参数";
  const jsonString = localFormData.value.dataset_args[index].generate_config;

  let jsonObject
  // 解析JSON字符串为对象
  try{
    jsonObject = JSON.parse(jsonString);
  }
  catch{
  // console.log("jsonString");
  // console.log(jsonString);
  }
  console.log("jsonObject");
  console.log(jsonObject);

  // 将对象转换为数组
  if(jsonObject){
    generate_configs.value = Object.keys(jsonObject).map((key) => ({
    key: key,
    value: jsonObject[key],
  }));
  }

  console.log("generate_configs");
  console.log(generate_configs.value);

  showEditDialog.value = true;
};

// const saveCell = (index) => {
//   edit.value = false;
//   console.log("tableData");
//   console.log(tableData.value);
//   // 这里可以添加保存逻辑，例如发送请求更新数据
// };

// const rowDrop = function () {
//   // 要拖拽元素的父容器
//   const tbody = document.querySelector(".el-table__body-wrapper tbody");
//   Sortable.create(tbody, {
//     //  可被拖拽的子元素
//     draggable: ".el-table__row",
//     onEnd({ newIndex, oldIndex }) {
//       const currRow = tableData.value.splice(oldIndex, 1)[0];
//       tableData.value.splice(newIndex, 0, currRow);
//       localFormData.value.datasets = tableData.value.map((item) => item.name);
//       tableData.value.forEach((row, index) => {
//         row.index = index + 1; // 假设行号从 1 开始
//       });
//     },
//   });
// };

const minParams = ref([]);

const getParam = (model) => {
  // console.log(model);
  let minTokens = Infinity;
  minParams.value = null;

  model[0].config.api_params_available.forEach((element) => {
    if (
      element.params.some(
        (param) => param.key === "max_tokens" && param.value < minTokens
      )
    ) {
      minTokens = element.params.find(
        (param) => param.key === "max_tokens"
      ).value;
      minParams.value = element.params;
    }
  });

  // console.log("minParams");
  // console.log(minParams.value);
  generate_configs.value = [...minParams.value];

  config.value = generate_configs.value.reduce(
    (acc, { key, value }) => ({ ...acc, [key]: value }),
    {}
  );
  domainConfig.value = generate_configs.value.reduce(
    (acc, { key, value }) => ({
      ...acc,
      [key]: value,
      chat_template_kwargs: { enable_thinking: false },
    }),
    {}
  );
  // console.log("config");
  // console.log(config.value);
  console.log("domainConfig");
  console.log(domainConfig.value);
};

const tableData = computed(() => {
  if (Object.keys(gen_config).length !== 0 || first_time.value === 1) {
    return localFormData.value.datasets.map((item, index) => ({
      index: index + 1,
      dataset_name: item,
      ...gen_config[item],
    }));
  } else {
    return localFormData.value.dataset_args;
  }
});

// 非记忆测试集表格数据
const nonMemoryTableData = computed(() => {
  return tableData.value.filter((row) => !row.isMemory);
});

// 记忆模式相关状态
const showMemoryEditDialog = ref(false);
const memoryEditTitle = ref("");
const memoryEditForm = ref([]);
const memoryEditRowIndex = ref(-1);

watch(
  localFormData,
  (newVal) => {
    emit("update:modelValue", newVal);
  },
  { deep: true }
);

interface AddForm {
  index: number;
  metric_list: Array<string>;
  subset_list: Array<string>;
  eval_batch_size: number;
  system_prompt: string;
  user_prompt: string;
}

const initialFormData = {
  index: 114514,
  metric_list: [],
  subset_list: [],
  eval_batch_size: 1,
  system_prompt: "",
  user_prompt: "",
};

const editTitle = ref("编辑测试集参数");
const showEditDialog = ref(false);
const formData = reactive<AddForm>({ ...initialFormData });

const rules = reactive<FormRules<AddForm>>({});

function addParam() {
  generate_configs.value.push({
    key: "",
    value: null,
  });
}

const removeParam = (index) => {
  generate_configs.value.splice(index, 1);
};

function resetFormData() {
  // console.log("执行了！！！");
  Object.keys(initialFormData).forEach((key) => {
    formData[key] = initialFormData[key];
  });
}

const closeDialog = () => {
  console.log("close dialog!");
  resetFormData();
  generate_configs.value = [...minParams.value];
  showEditDialog.value = false;
};

const commitSubmit = () => {
  // localFormData.value.dataset_args[formData.index] = formData;
  Object.keys(formData).forEach((key) => {
    localFormData.value.dataset_args[formData.index - 1][key] = formData[key];
    const obj = generate_configs.value.reduce((acc, item) => {
      acc[item.key] = item.value;
      return acc;
    }, {});
    localFormData.value.dataset_args[formData.index - 1].generate_config =
      JSON.stringify(obj);
  });

  resetFormData();
  generate_configs.value = [...minParams.value];
  showEditDialog.value = false;
};

const isStudy = computed(() => {
  return localFormData.value.datasets?.some(dataset => 
    baselineOptions2[dataset]?.testcase_tags?.includes('儿童伴读')
  ) || false
})

const isYitu = computed(()=>{
  return localFormData.value.datasets?.some(dataset =>
    baselineOptions2[dataset]?.testcase_tags?.includes('意图')
  ) || false
})

// 限制单选的tags：儿童伴读、意图、记忆、改写
const SINGLE_SELECT_TAGS = LLM_RULER2_LABELS

// 判断单个dataset是否含有限制tag
const datasetHasRestrictedTag = (dataset) => {
  if (!dataset) return false
  return SINGLE_SELECT_TAGS.some(tag =>
    baselineOptions2[dataset]?.testcase_tags?.includes(tag)
  )
}

// 当前是否处于限制模式（已选中含限制tag的dataset）
const isRestrictedModeActive = computed(() => {
  return localFormData.value.datasets?.length === 1 && datasetHasRestrictedTag(localFormData.value.datasets[0])
})

// 模板中判断某个key是否为当前已选中的dataset
const isSelectedDataset = (key) => {
  return localFormData.value.datasets?.includes(key)
}

// 选中限制tag测试集时清除其他，选中普通测试集时若有限制tag测试集已选中则阻止
watch(() => localFormData.value.datasets, (newVal, oldVal) => {
  if (!newVal || newVal.length === 0) return

  // 找出本次新增的项
  const addedItems = oldVal ? newVal.filter(item => !oldVal.includes(item)) : newVal
  if (addedItems.length === 0) return

  // 如果新加了含限制tag的dataset，只保留这一个
  const hasRestrictedAdded = addedItems.some(item => datasetHasRestrictedTag(item))
  if (hasRestrictedAdded) {
    const restrictedItem = addedItems.find(item => datasetHasRestrictedTag(item))
    localFormData.value.datasets = [restrictedItem]
    return
  }

  // 如果已有含限制tag的dataset被选中，阻止新增其他项
  if (oldVal?.length === 1 && datasetHasRestrictedTag(oldVal[0])) {
    ElMessage.warning('该业务仅支持单测试集评估，请取消选择后再切换其他测试集')
    localFormData.value.datasets = [...oldVal]
    return
  }
}, { deep: true })

onMounted(async () => {
  if (store.models.length === 0) {
    await store.fetchModels();
  }
  Object.assign(models, store.models);
  const model = models.filter((item) => item.model_id === m_formData.model_id);

  getParam(model);
  // rowDrop();
  let filteredObj = {}
  if (assessmentType.value === "通用评估(Ruler1)") {
    if (
      JSON.stringify(datasetStore.getDatasets("ruler1")) === "{}" ||
      JSON.stringify(datasetStore.getDatasets("ruler1")) === undefined
    ) {
      await get_datasets("1").then((res) => {
        datasetStore.setDatasets("ruler1", res.data);
        console.log('res.data', res.data)
        filteredObj = res.data
        // Object.assign(baselineOptions2, res.data);
      });
    } else {
      filteredObj = datasetStore.getDatasets("ruler1")
      // Object.assign(baselineOptions2, datasetStore.getDatasets("ruler1"));
    }
    if (showAllDatasets) {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0);
      filteredObj = Object.fromEntries(filteredEntries);
    } else if (evaluationType !== 'multiple') {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0 && value.testcase_tags.every(v => LLM_RULER1_LABELS.indexOf(v) !== -1));
      filteredObj = Object.fromEntries(filteredEntries);
    } else {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0 && value.testcase_tags.some(v => LLM_RULER1_LABELS.indexOf(v) === -1));
      filteredObj = Object.fromEntries(filteredEntries);
    }
    Object.assign(baselineOptions2, filteredObj)
    // select_item.value = Object.keys(baselineOptions2);
    // const model = models.filter(
    //   (item) => item.model_id === m_formData.model_id
    // );

    // getParam(model);

    // console.log("generate_configs");
    // console.log(generate_configs.value);

    // config.value = model[0].config.params.reduce((acc, item) => {
    //   acc[item.key] = item.value;
    //   return acc;
    // }, {});

    if (first_time.value === 1) {
      console.log("generationConfig");
      console.log(generationConfig.value);
      Object.keys(baselineOptions2).forEach((element) => {
        const generateConfigValue =
          generationConfig.value[element] || generationConfig.value.default;
        const metricListValue =
          baselineOptions2[element].metric_list || metric_list.value.default;
        const subsetList = baselineOptions2[element].subset_list;
        const default_subsets = baselineOptions2[element].default_subsets;
        const evalBatchSizeValue =
          eval_batch_size.value[element] || eval_batch_size.value.default;
        gen_config[element] = {
          generate_config: JSON.stringify(generateConfigValue),
          eval_batch_size: evalBatchSizeValue,
          AllSubsetList: subsetList,
          subset_list: default_subsets,
          allMetrics: metricListValue,
          metric_list: [metricListValue[0]],
        };
      });
      localFormData.value.dataset_args = tableData;
    }
  } else if (assessmentType.value === "AISF开发评估") {
    filteredObj = datasetStore.getDatasets("ruler3")
    if (showAllDatasets) {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0);
      filteredObj = Object.fromEntries(filteredEntries);
    } else if (evaluationType !== 'multiple') {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0 && value.testcase_tags.every(v => LLM_RULER3_LABELS.indexOf(v) !== -1));
      filteredObj = Object.fromEntries(filteredEntries);
    } else {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0 && value.testcase_tags.some(v => LLM_RULER3_LABELS.indexOf(v) === -1));
      filteredObj = Object.fromEntries(filteredEntries);
    }
    Object.assign(baselineOptions2, filteredObj);

    if (first_time.value === 1) {
      Object.keys(baselineOptions2).forEach((element) => {
        const generateConfigValue =
          domainGenerationConfig.value[element] ||
          domainGenerationConfig.value.default;
        const metricListValue =
          baselineOptions2[element].metric_list || metric_list.value.default;
        const subsetList = baselineOptions2[element].subset_list;
        const default_subsets = baselineOptions2[element].default_subsets;
        const evalBatchSizeValue =
          ruler2_eval_batch_size.value[element] ||
          ruler2_eval_batch_size.value.default;
        const system_prompt = baselineOptions2[element].system_prompt;
        gen_config[element] = {
          generate_config: JSON.stringify(generateConfigValue),
          AllSubsetList: subsetList,
          subset_list: default_subsets,
          eval_batch_size: evalBatchSizeValue,
          allMetrics: metricListValue,
          metric_list: [metricListValue[0]],
          system_prompt: system_prompt,
        };
      });
      localFormData.value.dataset_args = tableData;
    }
  } else if (assessmentType.value === "领域评估(Ruler2)") {
    filteredObj = datasetStore.getDatasets("ruler2")
    console.log('filteredObj')
    console.log(filteredObj)
    if (showAllDatasets) {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0);
      filteredObj = Object.fromEntries(filteredEntries);
    } else if (evaluationType !== 'multiple') {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0 && value.testcase_tags.every(v => LLM_RULER2_LABELS.indexOf(v) !== -1));
      filteredObj = Object.fromEntries(filteredEntries);
    } else {
      const filteredEntries = Object.entries(filteredObj).filter(([key, value]) => value.testcase_tags.length > 0 && value.testcase_tags.some(v => LLM_RULER2_LABELS.indexOf(v) === -1) && !value.testcase_tags.includes("AISF_NEW"));
      filteredObj = Object.fromEntries(filteredEntries);
    }
    Object.assign(baselineOptions2, filteredObj);

    if (first_time.value === 1) {
      Object.keys(baselineOptions2).forEach((element) => {
        const generateConfigValue =
          domainGenerationConfig.value[element] ||
          domainGenerationConfig.value.default;
        const metricListValue =
          baselineOptions2[element].metric_list || metric_list.value.default;
        const subsetList = baselineOptions2[element].subset_list;
        const default_subsets = baselineOptions2[element].default_subsets;
        const testcase_tags = baselineOptions2[element].testcase_tags;
        const system_prompt = baselineOptions2[element].system_prompt;
        const user_prompt = baselineOptions2[element].user_prompt;
        const evalBatchSizeValue =
          ruler2_eval_batch_size.value[element] ||
          ruler2_eval_batch_size.value.default;
        const memoryBizList = baselineOptions2[element].memory_business_list;
        const isMemory = testcase_tags && testcase_tags.includes("记忆") && memoryBizList && memoryBizList.length > 0;
        gen_config[element] = {
          generate_config: JSON.stringify(generateConfigValue),
          AllSubsetList: subsetList,
          subset_list: default_subsets,
          eval_batch_size: evalBatchSizeValue,
          allMetrics: metricListValue,
          metric_list: [metricListValue[0]],
          testcase_tags:testcase_tags,
          system_prompt:system_prompt,
          user_prompt:user_prompt,
          isMemory: isMemory,
          memoryBusinessParams: isMemory ? memoryBizList.map((biz) => {
            const promptFiles = biz.prompt_file
              ? (Array.isArray(biz.prompt_file) ? biz.prompt_file : [biz.prompt_file])
              : [];
            const testFiles = biz.test_file
              ? (Array.isArray(biz.test_file) ? biz.test_file : [biz.test_file])
              : [];
            return {
              name: biz.name,
              prompt_version: biz.prompt_version || "",
              eval_type: biz.eval_type || "",
              use_fewshot: biz.use_fewshot ?? false,
              judge_prompt:biz.judge_prompt || "",
              selected: true,
              promptFileList: promptFiles.map(f => ({ name: f.split('/').pop().split('\\').pop(), url: f })),
              testFileList: testFiles.map(f => ({ name: f.split('/').pop().split('\\').pop(), url: f })),
              selectedPromptFile: promptFiles.length > 0 ? promptFiles[0] : '',
              selectedTestFile: testFiles.length > 0 ? testFiles[0] : '',
            };
          }) : [],
        };
      });
      localFormData.value.dataset_args = tableData;
    }
  } else if (assessmentType.value === "同声传译评估") {
    Object.assign(baselineOptions2, {
      simultaneous_interpretation: {
        dataset_name: "simultaneous_interpretation",
      },
    });
  } else if (assessmentType.value === "AISF发布评估") {
    Object.assign(baselineOptions2, {
      aisf_clarify_32b: {
        dataset_name: "aisf_clarify_32b"
      },
      aisf_functioncall_32b: {
        dataset_name: "aisf_functioncall_32b"
      },
      aisf_intentcategory_32b: {
        dataset_name: "aisf_intentcategory_32b"
      },
      aisf_perceptionplan_32b: {
        dataset_name: "aisf_perceptionplan_32b"
      },
      aisf_box_param_extract_32b: {
        dataset_name: "aisf_box_param_extract_32b"
      },
      aisf_memory_forever_32b: {
        dataset_name: "aisf_memory_forever_32b"
      },
      aisf_box_scene_classify_4b: {
        dataset_name: "aisf_box_scene_classify_4b"
      },
      aisf_box_param_extract_4b: {
        dataset_name: "aisf_box_param_extract_4b"
      },
      aisf_memory_travel_agent_8b: {
        dataset_name: "aisf_memory_travel_agent_8b"
      },
      aisf_memory_attribute_extract_8b: {
        dataset_name: "aisf_memory_attribute_extract_8b"
      },
      aisf_memory_topic_8b: {
        dataset_name: "aisf_memory_topic_8b"
      },
      aisf_memory_fact_8b: {
        dataset_name: "aisf_memory_fact_8b"
      },
      aisf_memory_intent_classify_8b: {
        dataset_name: "aisf_memory_intent_classify_8b"
      },
      aisf_box_bert: {
        dataset_name: "aisf_box_bert"
      },
      aisf_memory_8b_open: {
        dataset_name: "aisf_memory_8b_open"
      },
      aisf_memory_32b_open: {
        dataset_name: "aisf_memory_32b_open"
      },
    });
  }
  // console.log("baselineOptions2");
  // console.log(baselineOptions2);
  console.log("localFormData");
  console.log(localFormData.value.dataset_args);
  console.log("tableData");
  console.log(tableData.value);
});
</script>

<style scoped>
.el-table {
  width: 95%; /* 设置表格的宽度 */
}

.dataSelectTable {
  border: 1px solid rgb(221, 221, 221);
  border-radius: 5px;
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

.memory-dataset-block {
  margin-bottom: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.memory-dataset-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

/* 限制模式下禁用选项的样式 */
:deep(.el-select-dropdown__item.is-disabled) {
  color: #c0c4cc !important;
  cursor: not-allowed !important;
}

.memory-dataset-title {
  font-weight: bold;
  font-size: 14px;
}

.memory-sub-table {
  width: 100%;
}
</style>
