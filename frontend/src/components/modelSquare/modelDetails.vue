<template>
  <div class="model-details">
    <!-- <div class="pageTitle">
      <span style="color: grey" @click="onBack">模型广场 /</span>模型详情
    </div>-->
    <div class="detailTitleContainer">
      <span style="padding: 0 14px"></span>
      <!-- <el-icon @click="onBack" style="cursor: pointer;">
        <Back />
      </el-icon>
      <span @click="onBack" style="color:rgba(18, 19, 22, 0.8);cursor: pointer;">返回</span>-->
      <img src="/images/return.png" class="returnicon" @click="onBack" style="left:28px;" />
      <span style="padding: 0 20px;"></span>
      <span @click="onBack" style="color: #969696;cursor: pointer;">模型广场</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>
      <span style="font-size:18px;font-weight:600;">模型详情</span>
    </div>

    <!-- header 区 -->
    <header class="md-header">
      <img class="header-icon" :src="ModelService.getModelIcon(modelData.model_id)" />
      <div class="header-info">
        <h1 class="header-title">{{ modelData.model_id }}</h1>
        <div class="tag-group">
          <span
            class="tag type-tag"
            v-for="(cat, idx) in modelData.info.category"
            :key="`cat-${idx}`"
          >{{ getModelType(cat) }}</span>
          <span
            class="tag info-tag"
            v-for="(tag, idx) in modelData.info.tags"
            :key="`tag-${idx}`"
          >{{ tag }}</span>
        </div>
      </div>
    </header>

    <div class="ms-content">
      <div class="tabs-buttons">
        <button
          @click="switchToTab(0)"
          :class="[currentTab === 0 ? 'active': '']"
          style="cursor: pointer;"
        >模型介绍</button>
        <button
          v-if="hasResult"
          @click="switchToTab(1)"
          :class="[currentTab === 1 ? 'active': '']"
          style="cursor: pointer;"
        >模型对比</button>
        <!-- <button
          v-if="hasResult"
          @click="switchToTab(2)"
          :class="[currentTab === 2 ? 'active': '']"
          style="cursor: pointer;"
        >评估报告</button> -->
      </div>
      <div class="tab-content-wrapper">
        <div v-if="currentTab === 0" class="tab-content">
          <div v-if="!isEditingModelDoc" class="edit-buttons">
            <button @click="startEdit">编辑</button>
          </div>
          <div v-show="!isEditingModelDoc && reportReadyType >= 5" class="report-buttons">
            <el-button
              type="primary"
              style="margin-right: 100px"
              class="customButtonMinTest"
              @click="downloadReport"
              :disabled="isReportGenerating || downloadReportPath === ''"
            >下载报告</el-button>
            <el-button
              type="primary"
              style="margin-right: 10px"
              class="customButtonMinTest"
              @click="generateReport(reportReadyType)"
              :disabled="isReportGenerating"
            >{{ getReportButtonName() }}</el-button>
          </div>
          <div
            v-if="isEditingModelDoc"
            style="border: 1px solid #ccc; width: 100%; margin-top: 10px"
          >
            <Toolbar
              style="border-bottom: 1px solid #ccc"
              :editor="editorRef"
              :defaultConfig="toolbarConfig"
              :mode="mode"
            />
            <Editor
              style="height: 400px; overflow-y: hidden"
              v-model="editDoc"
              :defaultConfig="editorConfig"
              :mode="mode"
              @onCreated="handleCreated"
            />
          </div>
          <div v-else v-html="$sanitizeHtml(modelData.info.model_doc)"></div>

          <!-- <div v-if="!isEditingModelDoc" v-html="$sanitizeHtml(markdown.render(modelData.info.model_doc || ''))"></div>

          <textarea v-if="isEditingModelDoc" v-model="editDoc" class="doc-editor" rows="15"></textarea>-->

          <div v-if="isEditingModelDoc" class="action-buttons">
            <button @click="cancelEdit" class="cancel">取消</button>
            <button @click="submitEdit">提交</button>
          </div>
        </div>
        <div v-if="currentTab === 1">
          <ModelCompareTab
            :modelName="modelData.info.model_name"
            :modelId="modelData.model_id"
          />
        </div>
        <!-- <div v-if="currentTab === 2">
          <ReportGenerationPanel
            :modelName="modelData.info.model_name"
            :modelId="modelData.model_id"
          />
        </div> -->
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  onMounted,
  reactive,
  ref,
  computed,
  onBeforeUnmount,
  shallowRef,
  watch,
} from "vue";
import { useAIModelStore } from "@/stores/aiModel";
import { ModelService } from "@/services/modelService.js";

import { ElMessage, ElSlider } from "element-plus";
import { useRoute } from "vue-router";
import router from "@/router/index.js";
import RadarChart from "@/components/modelSquare/multiRadarChart.vue";
import BarChart from "@/components/modelSquare/multiBarChart.vue";
import { getCurrentFullRes, getMultiModelData } from "@/api/dataService.js";
import { DATASET_MAPPING } from "@/stores/rankingStore";
import MarkdownIt from "markdown-it";
import "@wangeditor/editor/dist/css/style.css";
import { Editor, Toolbar } from "@wangeditor/editor-for-vue";
import { getLocalISOString } from "@/utils/TimeUtils.js";
import { useStore } from "vuex";
import { upload_file } from "@/api/dataSetApi.js";
import { API_BASE_URL } from "@/utils/Constants.js";
import {
  downloadEvalReport,
  genReport,
  getMinTestChart,
} from "@/api/runService.js";
import {
  AUDIO_REPORT_DATASETS,
  AV_REPORT_DATASETS,
  LLM_DATASET_TO_REPORT_TYPE,
  LLM_REPORT_DATASETS,
  VISION_REPORT_DATASETS,
} from "@/components/modelSquare/modelConstants.js";
import ModelCompareTab from "@/components/modelSquare/modelCompareTab.vue";

const markdown = new MarkdownIt();
const modelStore = useAIModelStore();
const store = useStore();
const route = useRoute();
const currentTab = ref(0);

const modelData = reactive({
  model_id: "",
  status: true,
  info: {
    model_name: "",
    model_desc: "",
    model_doc: "",
    series: "",
    vendor: "",
    tags: [],
    category: [],
    size: 0,
    context_length: 128000,
    isInternalDeployed: true,
    creation_date: getLocalISOString().split("T")[0],
  },
  config: {
    endpoint: [""], // 至少一个
    api_key: "",
    is_openai_format: true,
    request_method: "POST",
    body: "",
    resp_prefix: "",
    resp_tail: "",
    extra_headers: [{ key: "", value: "" }],
    params: [
      { key: "max_tokens", value: 4000 },
      { key: "top_p", value: 1.0 },
      { key: "top_k", value: 40 },
      { key: "temperature", value: 0.7 },
    ],
    filter: {
      head: "",
      tail: "",
    },
    api_params: [
      {
        endpoint: "",
        api_key: "",
        request_method: "POST",
        body: "",
        extra_headers: [{ key: "", value: "" }],
      },
    ],
    api_params_available: [],
  },
});

// 编辑器实例，必须用 shallowRef
const editorRef = shallowRef();

const toolbarConfig = {};
const editorConfig = {
  defaultValue:
    "<p><strong>模型介绍</strong></p><p></p><p><strong>技术亮点</strong></p><p></p><p><strong>官方评测</strong><p></p><p><strong>三方评测</strong></p><p></p>",
  placeholder: "请输入模型介绍、技术亮点、官方评测、三方评测内容及图片...",
  MENU_CONF: {
    uploadImage: {
      customUpload: async (file, insertFn) => {
        let formData = new FormData();
        formData.append("file", file);
        await upload_file(formData).then((res) => {
          insertFn(API_BASE_URL + "image/view/" + res.data.filename);
        });
      },
    },
  },
};

// 组件销毁时，也及时销毁编辑器
onBeforeUnmount(() => {
  const editor = editorRef.value;
  if (editor == null) return;
  editor.destroy();
});

const handleCreated = (editor) => {
  editorRef.value = editor; // 记录 editor 实例，重要！
  // editor.setHtml(item.content);
};

// 新增：编辑状态相关
const isEditingModelDoc = ref(false);
const editDoc = ref(
  "<p><strong>模型介绍</strong></p><p></p><p><strong>技术亮点</strong></p><p></p><p><strong>官方评测</strong><p></p><p><strong>三方评测</strong></p><p></p>"
);

function startEdit() {
  // 进入编辑模式前，将当前 doc 内容拷贝到 editDoc
  if (modelData.info.model_doc.trim()) {
    editDoc.value = modelData.info.model_doc;
  }
  isEditingModelDoc.value = true;
}

function cancelEdit() {
  // 退出编辑模式，不保存
  isEditingModelDoc.value = false;
}

function submitEdit() {
  // 将 editDoc 的内容提交出去，业务逻辑可以写在下面这个函数里
  submit(editDoc.value);
  // 如果希望在本地也更新显示，可以：
  modelData.info.model_doc = editDoc.value;
  isEditingModelDoc.value = false;
}

// 这个方法由你来完善具体的提交逻辑
async function submit(newDoc) {
  try {
    const newModelData = JSON.parse(JSON.stringify(modelData));
    newModelData.info.model_doc = newDoc;
    const data = await ModelService.modifyModel(newModelData);
    ElMessage.success("提交成功");
    modelStore.setModels(data);
  } catch (err) {
    console.error(err);
    ElMessage.error("提交失败");
  }

  console.log("提交新的 model_doc：", newDoc);
  // 例如调用接口 ModelService.updateModelDoc(...)
}

const getModelType = (value) => {
  return value.toUpperCase() === "LLM" ? "自然语言" : "多模态";
};

// 原始数据建模：按“类型”分组，每组内部是测评集名称 + 分数
// const tableData = ref([
//   {
//     type: "Knowledge",
//     entries: [
//       { id: "mmlu", name: "MMLU", score: "-" },
//       { id: "aime24", name: "MATH AIME2024", score: "-" },
//       { id: "aime25", name: "MATH AIME2025", score: "-" },
//       { id: "math_500", name: "MATH MATH500", score: "-" },
//     ],
//   },
//   {
//     type: "CODE",
//     entries: [
//       { id: "live_code_bench", name: "LiveCodeBench", score: "-" },
//       { id: "humaneval", name: "HumanEval", score: "-" },
//     ],
//   },
//   {
//     type: "Reasoning",
//     entries: [{ id: "gpqa", name: "GPQA_Diamond", score: "-" }],
//   },
//   {
//     type: "Tool",
//     entries: [{ id: "bfcl", name: "BFCL_v3", score: "-" }],
//   },
//   {
//     type: "Instruct",
//     entries: [{ id: "ifeval", name: "IF-Eval", score: "-" }],
//   },
// ]);

const chartDimention = ref([
  "mmlu",
  "aime24",
  "aime25",
  "live_code_bench",
  "gpqa",
  "bfcl_v3",
  "ifeval",
  "mmlu_redux",
  "aime26",
]);

const columns = ref([
  "算力型号",
  "卡数",
  "并发数",
  "框架",
  "输入长度(tokens)",
  "输出长度(tokens)",
  "首token时延(ms)",
  "增量token时延(ms)",
  "模型总推理速度(tokens/s)",
  "模型单并发推理速度(tokens/s)",
  "请求数",
  "95首token(ms)",
  "测试时长",
]);

const allRuler2Dataset = ref([
  "om_alarm_diag",
  "om_mml_generate",
  "明确代词指向",
  "省略主语",
  "省略宾语",
  "省略主体",
  "省略服务名",
  "主题明确",
  "询问历史细节信息",
  // "外挂fewshot库",
  // "不外挂fewshot库",
  "上下文信息无法支持内容补全",
  "上下文信息无法支持指代消解",
  "需内容补全",
  "需指代消解",
  "意图模糊",
  "意图完备",

  "单意图-易",
  "多意图-易",
  "上下文理解",
  "单意图-难",
  "多意图-难",
]);

const multiChartDimension = ref([
  "HallusionBench",
  "MMMU",
  "MMStar",
  "OCRBench",
  "DailyOmni",
  "librispeech_asr",
  "Fleurs",
  "MELD",
  "MMAU",
  "MMAR",
  "Video-MME",
  "WorldSense",
  "ScreenSpot_Pro",
  "MVBench",
]);

const multiAllRuler2Dataset = ref([
  "注意力检测",
  "坐姿检测",
  "影音娱乐-长视频(腾讯视频)",
  "影音娱乐--音乐(QQ音乐)",
  "影音娱乐-长视频(爱奇艺)",
  "影音娱乐-长视频(优酷视频)",
  "影音娱乐-长视频(芒果TV)",
  "影音娱乐--音乐(网易云音乐)",
  "影音娱乐--音乐(酷狗音乐)",
  "影音娱乐-短剧(红果)",
  "系统工具-应用安装(应用市场)",
  "游戏(咸鱼之王)",
  "游戏(蛋仔派对)",
  "游戏(开心消消乐)",
  "游戏(剑网3)",
  "通讯-运营商APP(中国联通)",
]);

const Ruler2CN = ref([]);

const chartValue = ref(chartDimention.value.map(() => 0));

// 计算合计分数（所有条目分数之和）
const totalScore = ref(0);

const rankingData = ref({});

const ruler1Data = ref();
const ruler2Data = ref();

const checkAll = ref(false);
const indeterminate = ref(false);
const selectValue = ref([]);
const selectDatasetValue = ref([]);
const models = ref([]);
const radarChartData = ref([]);
const checkAllDataset = ref(false);
const datasetIndeterminate = ref(false);

const Ruler2ChartData = ref([]);
const Ruler2RankingData = ref({});
const Ruler2ChartValue = ref(allRuler2Dataset.value.map(() => 0));

const datasetChartDimention = ref([]);

const datasetDisabled = ref(false);

const downloadReportPath = ref("");
const isReportGenerating = ref(false);

const handleCheckAll = (val) => {
  indeterminate.value = false;
  if (val) {
    selectValue.value = models.value.map((_) => _.value);
  } else {
    selectValue.value = [modelName.value];
  }
};

const handleCheckAllDataset = (val) => {
  checkAllDataset.value = val;
  if (val) {
    datasetIndeterminate.value = false;
    selectDatasetValue.value = chartDimention.value;
  } else {
    if (datasetIndeterminate.value === true) {
      selectDatasetValue.value = chartDimention.value;
    } else {
      checkAllDataset.value = true;
      datasetIndeterminate.value = false;
      ElMessage({
        message: "请至少选择一个测试集",
        type: "warning",
      });
    }
    // selectDatasetValue.value = [];
  }
};

const hasColor = ref({});
const showLabel = ref();
const showLabelBar = ref();
const titles = ref([]);
const titlesRuler2 = ref([]);
const colors = ref([
  "#00ffff", // cyan
  // "#000080",  // navy
  "#008000", // green
  "#ffa500", // orange
  // "#00ffff",  // aqua
  "#800080", // purple
  "#ff00ff", // magenta
  "#008080", // teal
  "#808000", // olive
  "#ff9999", // pink
  "#008000", // green
  "#ffff00", // yellow
  "#a52a2a", // brown
  "#00ff00", // lime
]);
const bottomMargin = ref("10%");
const Ruler1RadarWidth = ref("600px");
const Ruler1RadarHeight = ref("500px");
const Ruler1BarWidth = ref("600px");
const Ruler2BarWidth = ref("600px");
const radius = ref("70%");

watch(selectValue, (val) => {
  console.log("selectValue");
  console.log(val);
  console.log(curModelData.value);
  if (val.length === 0) {
    checkAll.value = false;
    indeterminate.value = false;
  } else if (val.length === models.value.length) {
    checkAll.value = true;
    indeterminate.value = false;
  } else {
    indeterminate.value = true;
  }

  radarChartData.value = [];
  Ruler2ChartData.value = [];
  multiRadarChartData.value = [];
  multiRuler2RadarChartData.value = [];
  if (selectValue.value.length > 1) {
    showLabel.value = false;
  } else {
    showLabel.value = true;
  }
  showLabelBar.value = val.length > 2 ? false : true;

  radius.value = val.length > 8 ? "50%" : "70%";
  selectValue.value.forEach((item) => {
    const normalize = (s) => normalizeModelKey(s);

    if (
      curModelData.value.info?.category?.includes("LLM") ||
      currentType.value === "LLM"
    ) {
      const matchKey = Object.keys(ruler1Data.value).find(
        (key) => normalize(key) === normalize(item)
        // normalize(item).endsWith(normalize(key))
      );
      const matchKeyRuler2 = Object.keys(ruler2Data.value).find(
        (key) => normalize(key) === normalize(item)
        // normalize(item).endsWith(normalize(key))
      );
      if (matchKey) {
        const keyAllData = ruler1Data.value[matchKey];
        // console.log(matchKey + "_keyAllData");
        // console.log(keyAllData);
        const tempChartDimention = chartDimention.value;
        const tempChartData = [];
        tempChartDimention.forEach((c, idx) => {
          const ds = keyAllData.result.find((d) => d.dataset_name === c);
          tempChartData[idx] = {
            data: ds ? (ds.score * 100).toFixed(2) : 0,
            dimension: c,
          };
        });

        radarChartData.value.push({
          // dimensions:tempChartDimention,
          data: tempChartData,
          title: matchKey,
          color: getColorFromPalette(matchKey),
        });
        titles.value.push({
          title: matchKey,
          color: hasColor.value[matchKey],
        });
        // console.log("radarChartData");
        // console.log(radarChartData.value);
      } else {
        genarateAble.value = false;
        console.log("未在Ruler1中");
      }
      if (matchKeyRuler2) {
        const keyAllDataRuler2 = ruler2Data.value[matchKeyRuler2];
        // console.log(matchKeyRuler2 + ":keyAllDataRuler2");
        // console.log(keyAllDataRuler2);
        const tempChartDimentionRuler2 = allRuler2Dataset.value;
        const tempChartDataRuler2 = [];
        tempChartDimentionRuler2.forEach((c, idx) => {
          keyAllDataRuler2.result.forEach((firstD) => {
            firstD.metrics?.[0]?.categories?.[0]?.subsets?.forEach((subset) => {
              if (subset.name === c) {
                const ds = subset;
                Ruler2ChartValue.value[idx] = ds
                  ? (ds.score * 100).toFixed(2)
                  : 0;
                tempChartDataRuler2[idx] = {
                  data: ds ? (ds.score * 100).toFixed(2) : 0,
                  dimension: c,
                };
              }
            });
          });
        });
        // console.log("getColorFromPalette");
        // console.log(getColorFromPalette(matchKeyRuler2));

        Ruler2ChartData.value.push({
          // dimensions:tempChartDimentionRuler2,
          data: tempChartDataRuler2,
          title: matchKeyRuler2,
          color: getColorFromPalette(matchKeyRuler2),
        });
        titlesRuler2.value.push({
          title: matchKeyRuler2,
          color: hasColor.value[matchKeyRuler2],
        });
      } else {
        genarateAble.value = false;
        console.log("未在Ruler2中");
      }
    }
    if (
      curModelData.value.info?.category?.includes("MLLM") ||
      currentType.value === "MLLM"
    ) {
      const multiMatchKey = Object.keys(multiRuler1Data.value).find(
        (key) => normalize(key) === normalize(item)
        // normalize(item).endsWith(normalize(key))
      );
      const multiMatchKeyRuler2 = Object.keys(multiRuler2Data.value).find(
        (key) => normalize(key) === normalize(item)
        // normalize(item).endsWith(normalize(key))
      );
      if (multiMatchKey) {
        const keyAllData = multiRuler1Data.value[multiMatchKey];
        // console.log(multiMatchKey + "_keyAllData");
        // console.log(keyAllData);
        const tempChartDimention = multiChartDimension.value;
        const tempChartData = [];
        tempChartDimention.forEach((c, idx) => {
          const ds = keyAllData.result.find((d) => d.dataset_name === c);
          tempChartData[idx] = {
            data: ds ? (ds.score * 100).toFixed(2) : 0,
            dimension: c,
          };
        });

        multiRadarChartData.value.push({
          // dimensions:tempChartDimention,
          data: tempChartData,
          title: multiMatchKey,
          color: getColorFromPalette(multiMatchKey),
        });
        titles.value.push({
          title: multiMatchKey,
          color: hasColor.value[multiMatchKey],
        });
        // console.log("multiRadarChartData");
        // console.log(multiRadarChartData.value);
      } else {
        multiGenarateAble.value = false;
        console.log("未在多模态Ruler1中");
      }

      if (multiMatchKeyRuler2) {
        const keyAllDataRuler2 = multiRuler2Data.value[multiMatchKeyRuler2];
        // console.log(multiMatchKeyRuler2 + ":keyAllDataRuler2");
        // console.log(keyAllDataRuler2);
        const tempChartDimentionRuler2 = multiAllRuler2Dataset.value;
        const tempChartDataRuler2 = [];
        tempChartDimentionRuler2.forEach((c, idx) => {
          keyAllDataRuler2.result.forEach((firstD) => {
            firstD.metrics?.[0]?.categories?.[0]?.subsets?.forEach((subset) => {
              if (subset.name === c) {
                const ds = subset;
                Ruler2ChartValue.value[idx] = ds
                  ? (ds.score * 100).toFixed(2)
                  : 0;
                tempChartDataRuler2[idx] = {
                  data: ds ? (ds.score * 100).toFixed(2) : 0,
                  dimension: c,
                };
              }
            });
          });
        });
        // console.log("getColorFromPalette");
        // console.log(getColorFromPalette(multiMatchKeyRuler2));

        multiRuler2RadarChartData.value.push({
          // dimensions:tempChartDimentionRuler2,
          data: tempChartDataRuler2,
          title: multiMatchKeyRuler2,
          color: getColorFromPalette(multiMatchKeyRuler2),
        });
        titlesRuler2.value.push({
          title: multiMatchKeyRuler2,
          color: hasColor.value[multiMatchKeyRuler2],
        });
      } else {
        multiGenarateAble.value = false;
        console.log("未在多模态Ruler2中");
      }
    }
    // console.log("Ruler2ChartData:");
    // console.log(Ruler2ChartData.value);
  });
  bottomMargin.value = selectValue.value.length > 8 ? "15%" : "10%";
  bottomMargin.value =
    selectValue.value.length > 16 ? "30%" : bottomMargin.value;
});

watch(selectDatasetValue, (val) => {
  // console.log(selectDatasetValue.value);
  if (val.length === 1) {
    datasetChartDimention.value.forEach((item) => {
      item.disabled = val.includes(item.value);
    });
  } else if (val.length === 0) {
    checkAllDataset.value = false;
    datasetIndeterminate.value = false;
  } else if (val.length === chartDimention.value.length) {
    checkAllDataset.value = true;
    datasetIndeterminate.value = false;
    datasetChartDimention.value.forEach((item) => {
      item.disabled = false;
    });
  } else {
    datasetChartDimention.value.forEach((item) => {
      item.disabled = false;
    });
    datasetIndeterminate.value = true;
  }
});

const colorIndex = ref(0);

const getColorFromPalette = (matchKey) => {
  if (hasColor.value[matchKey] !== null) {
    return hasColor.value[matchKey];
  } else {
    const color = colors.value[colorIndex.value % colors.value.length];
    const colorWithOpacity = `${color}40`;
    colorIndex.value++;
    // console.log("colorWithOpacity");
    // console.log(colorWithOpacity);
    hasColor.value[matchKey] = colorWithOpacity;
    return colorWithOpacity;
  }
};

const modelName = ref();
const ruler2SelectDatasetValue = ref([
  "om_alarm_diag",
  "om_mml_generate",
  "明确代词指向",
  "省略主语",
  "省略宾语",
  "省略主体",
  "省略服务名",
  "主题明确",
  "询问历史细节信息",

  "单意图-易",
  "多意图-易",
  "上下文理解",
  "单意图-难",
  "多意图-难",
]);
const ruler2CheckAllDataset = ref(true);
const ruler2DatasetIndeterminate = ref(false);

const ruler2HandleCheckAllDataset = (val) => {
  ruler2CheckAllDataset.value = val;
  if (val) {
    ruler2DatasetIndeterminate.value = false;
    ruler2SelectDatasetValue.value = allRuler2Dataset.value;
  } else {
    if (ruler2DatasetIndeterminate.value === true) {
      ruler2SelectDatasetValue.value = allRuler2Dataset.value;
    } else {
      ruler2CheckAllDataset.value = true;
      ruler2DatasetIndeterminate.value = false;
      ElMessage({
        message: "请至少选择一个测试集",
        type: "warning",
      });
    }
  }
};

const cascaderProps = ref({
  emitPath: false,
  multiple: true,
  // showAllLevels: false,
});

const Ruler2Options = ref([
  {
    value: "operations",
    label: "运维智能",
    children: [
      {
        value: "om_alarm_diag",
        label: "告警E2E",
        disabled: false,
      },
      {
        value: "om_mml_generate",
        label: "MML生成",
        disabled: false,
      },
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_gaixie",
    label: "AISF LLM 改写",
    children: [
      //   {
      //   value:  "外挂fewshot库",
      //   label:  "外挂fewshot库",
      //   disabled: false,
      // },
      //   {
      //   value:  "不外挂fewshot库",
      //   label:  "不外挂fewshot库",
      //   disabled: false,
      // },
      {label:"上下文信息无法支持内容补全",value:"上下文信息无法支持内容补全"},
      {label:"上下文信息无法支持指代消解",value:"上下文信息无法支持指代消解"},
      {label:"需内容补全",value:"需内容补全"},
      {label:"需指代消解",value:"需指代消解"},
      {label:"意图模糊",value:"意图模糊"},
      {label:"意图完备",value:"意图完备"}
      // {
      //   value: "明确代词指向",
      //   label: "明确代词指向",
      //   disabled: false,
      // },
      // {
      //   value: "省略主语",
      //   label: "省略主语",
      //   disabled: false,
      // },
      // {
      //   value: "省略宾语",
      //   label: "省略宾语",
      //   disabled: false,
      // },
      // {
      //   value: "省略主体",
      //   label: "省略主体",
      //   disabled: false,
      // },
      // {
      //   value: "省略服务名",
      //   label: "省略服务名",
      //   disabled: false,
      // },
      // {
      //   value: "主题明确",
      //   label: "主题明确",
      //   disabled: false,
      // },
      // {
      //   value: "询问历史细节信息",
      //   label: "询问历史细节信息",
      //   disabled: false,
      // },
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_yitu",
    label: "AISF LLM 意图",
    children: [
      {
        value: "单意图-易",
        label: "单意图-易",
        disabled: false,
      },
      {
        value: "多意图-易",
        label: "多意图-易",
        disabled: false,
      },
      {
        value: "上下文理解",
        label: "上下文理解",
        disabled: false,
      },
      {
        value: "单意图-难",
        label: "单意图-难",
        disabled: false,
      },
      {
        value: "多意图-难",
        label: "多意图-难",
        disabled: false,
      },
    ],
    disabled: false,
  },
]);
const multiRuler2Options = ref([
  {
    value: "aisf_banxue",
    label: "儿童伴读",
    children: [
      {
        value: "注意力检测",
        label: "注意力检测",
        disabled: false,
      },
      {
        value: "坐姿检测",
        label: "坐姿检测",
        disabled: false,
      },
    ],
    disabled: false,
  },
  {
    value: "aisf_gui_plan",
    label: "AISF-GUI规划",
    children: [
      {
        value: "影音娱乐-长视频(腾讯视频)",
        label: "长视频(腾讯视频)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(QQ音乐)",
        label: "音乐(QQ音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(爱奇艺)",
        label: "长视频(爱奇艺)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(优酷视频)",
        label: "长视频(优酷视频)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(芒果TV)",
        label: "长视频(芒果TV)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(网易云音乐)",
        label: "音乐(网易云音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(酷狗音乐)",
        label: "音乐(酷狗音乐)",
        disabled: false,
      },
      { value: "影音娱乐-短剧(红果)", label: "短剧(红果)", disabled: false },
      {
        value: "系统工具-应用安装(应用市场)",
        label: "应用安装(应用市场)",
        disabled: false,
      },
      { value: "游戏(咸鱼之王)", label: "咸鱼之王", disabled: false },
      { value: "游戏(蛋仔派对)", label: "蛋仔派对", disabled: false },
      { value: "游戏(开心消消乐)", label: "开心消消乐", disabled: false },
      { value: "游戏(剑网3)", label: "剑网3", disabled: false },
      {
        value: "通讯-运营商APP(中国联通)",
        label: "运营商APP(中国联通)",
        disabled: false,
      },
    ],
    disabled: false,
  },
  {
    value: "aisf_gui_vla",
    label: "AISF-GUI操控",
    children: [
      {
        value: "影音娱乐-长视频(腾讯视频)",
        label: "长视频(腾讯视频)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(QQ音乐)",
        label: "音乐(QQ音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(爱奇艺)",
        label: "长视频(爱奇艺)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(优酷视频)",
        label: "长视频(优酷视频)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(芒果TV)",
        label: "长视频(芒果TV)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(网易云音乐)",
        label: "音乐(网易云音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(酷狗音乐)",
        label: "音乐(酷狗音乐)",
        disabled: false,
      },
      { value: "影音娱乐-短剧(红果)", label: "短剧(红果)", disabled: false },
      {
        value: "系统工具-应用安装(应用市场)",
        label: "应用安装(应用市场)",
        disabled: false,
      },
      { value: "游戏(咸鱼之王)", label: "咸鱼之王", disabled: false },
      { value: "游戏(蛋仔派对)", label: "蛋仔派对", disabled: false },
      { value: "游戏(开心消消乐)", label: "开心消消乐", disabled: false },
      { value: "游戏(剑网3)", label: "剑网3", disabled: false },
      {
        value: "通讯-运营商APP(中国联通)",
        label: "运营商APP(中国联通)",
        disabled: false,
      },
    ],
    disabled: false,
  },
]);

watch(ruler2SelectDatasetValue, (val) => {
  // console.log("ruler2SelectDatasetValue");
  // console.log(val);
  Ruler2CN.value = [];
  ruler2SelectDatasetValue.value.forEach((item) => {
    if (DATASET_MAPPING.operations?.subsets?.includes?.(item)) {
      Ruler2CN.value.push(DATASET_MAPPING.operations.labels?.[item] ?? item);
    } else if (DATASET_MAPPING.aisf_llm_gaixie.subsets.includes(item)) {
      Ruler2CN.value.push(DATASET_MAPPING.aisf_llm_gaixie.labels[item]);
    } else if (DATASET_MAPPING.aisf_llm_yitu.subsets.includes(item)) {
      Ruler2CN.value.push(DATASET_MAPPING.aisf_llm_yitu.labels[item]);
    }
  });

  if (val.length === 1) {
    Ruler2Options.value.forEach((option) => {
      if (option.children) {
        option.children.forEach((child) => {
          child.disabled = val.includes(child.value);
        });
      }
    });
    // console.log(Ruler2Options.value);
  } else if (val.length === 0) {
    ruler2CheckAllDataset.value = false;
    ruler2DatasetIndeterminate.value = false;
  } else if (val.length === allRuler2Dataset.value.length) {
    Ruler2Options.value.forEach((option) => {
      if (option.children) {
        option.children.forEach((child) => {
          child.disabled = false;
        });
      }
    });
    ruler2CheckAllDataset.value = true;
    ruler2DatasetIndeterminate.value = false;
  } else {
    Ruler2Options.value.forEach((option) => {
      if (option.children) {
        option.children.forEach((child) => {
          child.disabled = false;
        });
      }
    });
    ruler2DatasetIndeterminate.value = true;
  }
});

const canSelectParentAll = ref(true);
const preRuler2Dataset = ref();
const cascadertKey = ref(0);

const handelCascaderChange = (value) => {
  if (value.length === 0) {
    ruler2SelectDatasetValue.value = preRuler2Dataset.value;
    ElMessage({
      message: "请至少选择一个测试集",
      type: "warning",
    });
    cascadertKey.value++;
  } else {
    preRuler2Dataset.value = ruler2SelectDatasetValue.value;
  }
  // 获取report type
  if (value.length > 0) {
    const matchedDataset = LLM_REPORT_DATASETS.find((dataset) =>
      value[0].includes(dataset)
    );
    llmReportType.value = LLM_DATASET_TO_REPORT_TYPE[matchedDataset] ?? 1;
  }
};

const isInRuler1 = ref(false);
const isInRuler2 = ref(false);
const llmReportType = ref(1);
// MinTest:5;MllmAv:6;MllmVision:7;MllmAudio:8
const reportReadyType = ref(0);

const getReportButtonName = () => {
  if (reportReadyType.value === 5) {
    return "生成最小集报告";
  } else if (reportReadyType.value === 6) {
    return "生成全模态测评报告";
  } else if (reportReadyType.value === 7) {
    return "生成视觉测评报告";
  } else if (reportReadyType.value === 8) {
    return "生成音频测评报告";
  }
  return null;
};

const multiRuler2Data = ref();

// 模型名归一化：忽略末尾量化后缀 -w8a8（如 DeepSeek-V4-Flash-0731 与 DeepSeek-V4-Flash-0731-w8a8 视为同名）
const stripQuantSuffix = (s) => String(s || "").replace(/-w8a8$/i, "");
const normalizeModelKey = (s) =>
  stripQuantSuffix(s).toLowerCase().replace(/_/g, "-");
// 在榜单 keys 中解析模型对应的真实 key：优先精确匹配，其次忽略 -w8a8 归一匹配；未命中返回 null
const resolveRankModel = (keys, name) =>
  keys.includes(name)
    ? name
    : keys.find((k) => normalizeModelKey(k) === normalizeModelKey(name)) ||
      null;
// 当前模型的候选名列表：info.model_name（如 dsv4）与 model_id（如 DeepSeek-V4-Flash-0731-w8a8）
let modelNameCandidates = [];
const resolveRankByCandidates = (keys) => {
  for (const name of modelNameCandidates) {
    const hit = resolveRankModel(keys, name);
    if (hit) return hit;
  }
  return null;
};
const multiRuler2SelectDatasetValue = ref();
const multiRuler2RadarChartData = ref();
const multiTitlesRuler2 = ref([]);
const multiRuler2RankingData = ref();
const multiRuler2CN = ref([]);
const loadRuler2Data = (chartData, type) => {
  if (type === "LLM") {
    ruler2Data.value = chartData.ruler2;
    const rankModel =
      resolveRankByCandidates(Object.keys(ruler2Data.value)) ||
      modelName.value;

    let tempModels = Object.keys(ruler2Data.value);
    const newModels = tempModels
      .map((item) => {
        // 检查models.value中是否已存在该value
        const exists = models.value.some((model) => model.value === item);
        if (!exists) {
          return {
            value: item,
            label: item,
            disabled: item === rankModel,
          };
        }
        return null;
      })
      .filter(Boolean);

    const existingModelIndex = tempModels.findIndex(
      (item) => item === rankModel
    );
    if (existingModelIndex === -1) {
      ruler2SelectDatasetValue.value = [];
      llmReportType.value = 0;
      return;
    }
    models.value.push(...newModels);
    models.value.forEach((item) => {
      hasColor.value[item.label] = null;
    });

    const normalize = (s) => normalizeModelKey(s);
    const matchKey = Object.keys(ruler2Data.value).find(
      (key) => normalize(key) === normalize(rankModel)
      // normalize(rankModel).endsWith(normalize(key))
    );

    let tempChartData = [];
    if (matchKey) {
      Ruler2RankingData.value = ruler2Data.value[matchKey];
      // console.log("Ruler2RankingData:");
      // console.log(Ruler2RankingData.value);

      allRuler2Dataset.value = allRuler2Dataset.value.filter(
        (c) => c !== "average"
      );

      // 定义优先级数组
      const sceneList = ["operations", "aisf_llm_gaixie", "aisf_llm_yitu"]; // 优先级随下标递减

      // 步骤1：找出优先级最高的res
      let highestPriorityRes = null;
      let highestPriorityIndex = Infinity;

      Ruler2RankingData.value.result.forEach((res) => {
        if (res.metrics.length > 0) {
          const priorityIndex = sceneList.indexOf(res.dataset_name);

          // 如果在优先级数组中且优先级更高（下标更小）
          if (priorityIndex !== -1 && priorityIndex < highestPriorityIndex) {
            highestPriorityIndex = priorityIndex;
            highestPriorityRes = res;
          }
        }
      });

      // console.log("highestPriorityRes");
      // console.log(highestPriorityRes);

      // 步骤2：确定最终要使用的res
      const targetRes =
        highestPriorityRes ||
        (Ruler2RankingData.value.result[0]?.metrics?.length > 0
          ? Ruler2RankingData.value.result[0]
          : null);

      // 步骤3：清空并重新填充ruler2SelectDatasetValue
      ruler2SelectDatasetValue.value = [];
      if (targetRes) {
        targetRes.metrics?.[0]?.categories?.[0]?.subsets?.forEach((subset) => {
          ruler2SelectDatasetValue.value.push(subset.name);
        });
        // 收集Ruler2Options中所有叶子节点值
        const ruler2LeafValues = [];
        Ruler2Options.value.forEach((group) => {
          if (group.children) {
            group.children.forEach((child) => {
              ruler2LeafValues.push(child.value);
            });
          }
        });
        // 检查该模型是否至少有一个subset匹配Ruler2Options的叶子节点
        const hasAnyDatasetScore = ruler2SelectDatasetValue.value.some((name) =>
          ruler2LeafValues.includes(name)
        );
        if (hasAnyDatasetScore) {
          isInRuler2.value = true;
        } else {
          ruler2SelectDatasetValue.value = [];
          llmReportType.value = 0;
        }
      }

      // 步骤4：处理图表数据
      allRuler2Dataset.value.forEach((datasetName, idx) => {
        let found = false;

        Ruler2RankingData.value.result.forEach((res) => {
          if (!res.metrics.length) return;

          res.metrics?.[0]?.categories?.[0]?.subsets?.forEach((subset) => {
            if (subset.name === datasetName) {
              found = true;
              const scoreValue = subset ? (subset.score * 100).toFixed(2) : 0;

              Ruler2ChartValue.value[idx] = scoreValue;
              tempChartData[idx] = {
                data: scoreValue,
                dimension: datasetName,
              };
            }
          });
        });

        // 如果没找到，设置默认值
        if (!found) {
          Ruler2ChartValue.value[idx] = 0;
          tempChartData[idx] = {
            data: 0,
            dimension: datasetName,
          };
        }
      });

      Ruler2ChartData.value = [];
      Ruler2ChartData.value.push({
        // dimensions:tempChartDimention,
        data: tempChartData,
        title: matchKey,
        color: "#0000ff40",
      });
      hasColor.value[matchKey] = "#0000ff40";
      titlesRuler2.value.push({
        title: matchKey,
        color: hasColor.value[matchKey],
      });
      allRuler2Dataset.value.forEach((item) => {
        if (DATASET_MAPPING.operations?.subsets?.includes?.(item)) {
          Ruler2CN.value.push(DATASET_MAPPING.operations.labels?.[item] ?? item);
        } else if (DATASET_MAPPING.aisf_llm_gaixie.subsets.includes(item)) {
          Ruler2CN.value.push(DATASET_MAPPING.aisf_llm_gaixie.labels[item]);
        } else if (DATASET_MAPPING.aisf_llm_yitu.subsets.includes(item)) {
          Ruler2CN.value.push(DATASET_MAPPING.aisf_llm_yitu.labels[item]);
        }
      });
    } else {
      ruler2SelectDatasetValue.value = [];
      llmReportType.value = 0;
    }
  } else {
    multiRuler2Data.value = chartData.ruler2;
    const rankModel =
      resolveRankByCandidates(Object.keys(multiRuler2Data.value)) ||
      modelName.value;

    let tempModels = Object.keys(multiRuler2Data.value);
    const newModels = tempModels
      .map((item) => {
        // 检查models.value中是否已存在该value
        const exists = models.value.some((model) => model.value === item);
        if (!exists) {
          return {
            value: item,
            label: item,
            disabled: item === rankModel,
          };
        }
        return null;
      })
      .filter(Boolean);

    const existingModelIndex = tempModels.findIndex(
      (item) => item === rankModel
    );
    if (existingModelIndex === -1) {
      multiRuler2SelectDatasetValue.value = [];
      mllmReportType.value = 6;
      console.log("mllmReportType");
      console.log(mllmReportType.value);
      return;
    }
    models.value.push(...newModels);
    models.value.forEach((item) => {
      hasColor.value[item.label] = null;
    });

    const normalize = (s) => normalizeModelKey(s);
    const matchKey = Object.keys(multiRuler2Data.value).find(
      (key) => normalize(key) === normalize(rankModel)
      // normalize(rankModel).endsWith(normalize(key))
    );

    let tempChartData = [];
    if (matchKey) {
      multiRuler2RankingData.value = multiRuler2Data.value[matchKey];
      // console.log("multiRuler2RankingData:");
      // console.log(multiRuler2RankingData.value);

      multiAllRuler2Dataset.value = multiAllRuler2Dataset.value.filter(
        (c) => c !== "average"
      );

      // 定义优先级数组
      const sceneList = ["aisf_banxue", "aisf_gui_plan", "aisf_gui_vla"]; // 优先级随下标递减

      // 步骤1：找出优先级最高的res
      let highestPriorityRes = null;
      let highestPriorityIndex = Infinity;

      multiRuler2RankingData.value.result.forEach((res) => {
        if (res.metrics.length > 0) {
          const priorityIndex = sceneList.indexOf(res.dataset_name);

          // 如果在优先级数组中且优先级更高（下标更小）
          if (priorityIndex !== -1 && priorityIndex < highestPriorityIndex) {
            highestPriorityIndex = priorityIndex;
            highestPriorityRes = res;
          }
        }
      });

      // console.log("highestPriorityRes");
      // console.log(highestPriorityRes);

      // 步骤2：确定最终要使用的res
      const targetRes =
        highestPriorityRes ||
        (multiRuler2RankingData.value.result[0]?.metrics?.length > 0
          ? multiRuler2RankingData.value.result[0]
          : null);

      // 步骤3：清空并重新填充ruler2SelectDatasetValue
      multiRuler2SelectDatasetValue.value = [];
      if (targetRes) {
        targetRes.metrics?.[0]?.categories?.[0]?.subsets?.forEach((subset) => {
          multiRuler2SelectDatasetValue.value.push(subset.name);
        });
        // 收集Ruler2Options中所有叶子节点值
        const ruler2LeafValues = [];
        multiRuler2Options.value.forEach((group) => {
          if (group.children) {
            group.children.forEach((child) => {
              ruler2LeafValues.push(child.value);
            });
          }
        });
        // 检查该模型是否至少有一个subset匹配Ruler2Options的叶子节点
        const hasAnyDatasetScore = multiRuler2SelectDatasetValue.value.some(
          (name) => ruler2LeafValues.includes(name)
        );
        if (hasAnyDatasetScore) {
          isInMultiRuler2.value = true;
          console.log("isInMultiRuler2");
          console.log(isInMultiRuler2.value);
        } else {
          multiRuler2SelectDatasetValue.value = [];
          mllmReportType.value = 6;
          console.log("mllmReportType");
          console.log(mllmReportType.value);
        }
      }

      // 步骤4：处理图表数据
      multiAllRuler2Dataset.value.forEach((datasetName, idx) => {
        let found = false;

        multiRuler2RankingData.value.result.forEach((res) => {
          if (!res.metrics.length) return;

          res.metrics?.[0]?.categories?.[0]?.subsets?.forEach((subset) => {
            if (subset.name === datasetName) {
              found = true;
              const scoreValue = subset ? (subset.score * 100).toFixed(2) : 0;

              Ruler2ChartValue.value[idx] = scoreValue;
              tempChartData[idx] = {
                data: scoreValue,
                dimension: datasetName,
              };
            }
          });
        });

        // 如果没找到，设置默认值
        if (!found) {
          Ruler2ChartValue.value[idx] = 0;
          tempChartData[idx] = {
            data: 0,
            dimension: datasetName,
          };
        }
      });

      multiRuler2RadarChartData.value = [];
      multiRuler2RadarChartData.value.push({
        // dimensions:tempChartDimention,
        data: tempChartData,
        title: matchKey,
        color: "#0000ff40",
      });
      hasColor.value[matchKey] = "#0000ff40";
      multiTitlesRuler2.value.push({
        title: matchKey,
        color: hasColor.value[matchKey],
      });
      multiAllRuler2Dataset.value.forEach((item) => {
        if (DATASET_MAPPING.operations?.subsets?.includes?.(item)) {
          multiRuler2CN.value.push(DATASET_MAPPING.operations.labels?.[item] ?? item);
        } else if (DATASET_MAPPING.aisf_llm_gaixie.subsets.includes(item)) {
          multiRuler2CN.value.push(
            DATASET_MAPPING.aisf_llm_gaixie.labels[item]
          );
        } else if (DATASET_MAPPING.aisf_llm_yitu.subsets.includes(item)) {
          multiRuler2CN.value.push(DATASET_MAPPING.aisf_llm_yitu.labels[item]);
        }
      });
    } else {
      multiRuler2SelectDatasetValue.value = [];
      mllmReportType.value = 6;
      console.log("mllmReportType");
      console.log(mllmReportType.value);
    }
  }
};

const multiRadarChartData = ref([]);
const multiTitles = ref([]);
const multiSelectDatasetValue = ref([]);
const multiDatasetChartDimention = ref();
const multiPreRuler2Dataset = ref();
const isInMultiRuler1 = ref(false);
const isInMultiRuler2 = ref(false);
const multiRuler1Data = ref();
const loadRuler1Data = (curModelName, chartData, type) => {
  if (type === "LLM") {
    let curDimention =
      type === "LLM" ? chartDimention.value : multiChartDimension.value;
    modelName.value = curModelName;
    console.log("chartData");
    console.log(chartData.ruler1);
    ruler1Data.value = chartData.ruler1;
    models.value = Object.keys(ruler1Data.value);
    const rankModel =
      resolveRankByCandidates(Object.keys(ruler1Data.value)) ||
      modelName.value;
    models.value = models.value.map((item) => {
      if (item === rankModel) {
        return {
          value: item,
          label: item,
          disabled: true,
        };
      } else {
        return {
          value: item,
          label: item,
          disabled: false,
        };
      }
    });
    // console.log('models')
    // console.log(models.value)
    if (!selectValue.value.includes(rankModel)) {
      selectValue.value.push(rankModel);
    }

    const existingModelIndex = models.value.findIndex(
      (item) => item.value === rankModel
    );
    if (existingModelIndex === -1) {
      return;
    }
    const existingModel = models.value.splice(existingModelIndex, 1)[0];
    models.value.unshift(existingModel);
    models.value.forEach((item) => {
      hasColor.value[item.label] = null;
    });
    selectDatasetValue.value.push();
    const normalize = (s) => normalizeModelKey(s);
    const matchKey = Object.keys(ruler1Data.value).find(
      (key) => normalize(key) === normalize(rankModel)
    );
    let tempChartData = [];
    if (matchKey) {
      rankingData.value = ruler1Data.value[matchKey];
      // 检查该模型是否至少有一个chartDimention中的测试集有非零分数
      const hasAnyDatasetScore = curDimention.some((c) => {
        const ds = rankingData.value.result.find((d) => d.dataset_name === c);
        return ds && ds.score > 0;
      });
      if (hasAnyDatasetScore) {
        isInRuler1.value = true;
      } else {
        selectDatasetValue.value = [];
      }

      curDimention = curDimention.filter((c) => c !== "average");

      curDimention.forEach((c, idx) => {
        const ds = rankingData.value.result.find((d) => d.dataset_name === c);
        chartValue.value[idx] = ds ? (ds.score * 100).toFixed(2) : 0;
        tempChartData[idx] = {
          data: ds ? (ds.score * 100).toFixed(2) : 0,
          dimension: c,
        };
      });
      radarChartData.value.push({
        // dimensions:tempChartDimention,
        data: tempChartData,
        title: matchKey,
        color: "#0000ff40",
      });
      // console.log("radarChartData.value");
      // console.log(radarChartData.value);
      hasColor.value[matchKey] = "#0000ff40";
      titles.value.push({
        title: matchKey,
        color: hasColor.value[matchKey],
      });
      // console.log("chartDimention");
      // console.log(curDimention);
      selectDatasetValue.value = curDimention;
    } else {
      selectDatasetValue.value = [];
    }

    datasetChartDimention.value = curDimention.map((item) => ({
      value: item,
    }));
    preRuler2Dataset.value = ruler2SelectDatasetValue.value;
  } else {
    let curDimention =
      type === "LLM" ? chartDimention.value : multiChartDimension.value;
    modelName.value = curModelName;
    multiRuler1Data.value = chartData.ruler1;
    const rankModel =
      resolveRankByCandidates(Object.keys(multiRuler1Data.value)) ||
      modelName.value;
    if (models.value.length === 0) {
      models.value = Object.keys(multiRuler1Data.value);
      models.value = models.value.map((item) => {
        if (item === rankModel) {
          return {
            value: item,
            label: item,
            disabled: true,
          };
        } else {
          return {
            value: item,
            label: item,
            disabled: false,
          };
        }
      });
    } else {
      const newKeys = Object.keys(multiRuler1Data.value);
      const existingValues = new Set(models.value.map((m) => m.value));

      newKeys.forEach((key) => {
        // 仅添加不存在的模型
        if (!existingValues.has(key)) {
          models.value.push({
            value: key,
            label: key,
            disabled: key === rankModel,
          });
        }
      });
    }
    // console.log('models')
    // console.log(models.value)
    if (!selectValue.value.includes(rankModel)) {
      selectValue.value.push(rankModel);
    }

    const existingModelIndex = models.value.findIndex(
      (item) => item.value === rankModel
    );
    if (existingModelIndex === -1) {
      multiSelectDatasetValue.value = [];
      mllmReportType.value = mllmReportType.value === 6 ? 67 : 7;
      return;
    }
    const existingModel = models.value.splice(existingModelIndex, 1)[0];
    models.value.unshift(existingModel);
    models.value.forEach((item) => {
      hasColor.value[item.label] = null;
    });
    multiSelectDatasetValue.value.push();
    const normalize = (s) => normalizeModelKey(s);
    const matchKey = Object.keys(multiRuler1Data.value).find(
      (key) => normalize(key) === normalize(rankModel)
    );
    let tempChartData = [];
    if (matchKey) {
      rankingData.value = multiRuler1Data.value[matchKey];
      // 检查该模型是否至少有一个chartDimention中的测试集有非零分数
      const hasAnyDatasetScore = curDimention.some((c) => {
        const ds = rankingData.value.result.find((d) => d.dataset_name === c);
        return ds && ds.score > 0;
      });
      if (hasAnyDatasetScore) {
        isInMultiRuler1.value = true;
        console.log("isInMultiRuler1");
        console.log(isInMultiRuler1.value);
      } else {
        multiSelectDatasetValue.value = [];
        mllmReportType.value = mllmReportType.value === 6 ? 67 : 7;
      }

      curDimention = curDimention.filter((c) => c !== "average");

      curDimention.forEach((c, idx) => {
        const ds = rankingData.value.result.find((d) => d.dataset_name === c);
        chartValue.value[idx] = ds ? (ds.score * 100).toFixed(2) : 0;
        tempChartData[idx] = {
          data: ds ? (ds.score * 100).toFixed(2) : 0,
          dimension: c,
        };
      });

      multiRadarChartData.value.push({
        // dimensions:tempChartDimention,
        data: tempChartData,
        title: matchKey,
        color: "#0000ff40",
      });
      hasColor.value[matchKey] = "#0000ff40";
      multiTitles.value.push({
        title: matchKey,
        color: hasColor.value[matchKey],
      });
      // console.log("chartDimention");
      // console.log(curDimention);
      multiSelectDatasetValue.value = curDimention;
    } else {
      multiSelectDatasetValue.value = [];
      mllmReportType.value = mllmReportType.value === 6 ? 67 : 7;
    }

    multiDatasetChartDimention.value = curDimention.map((item) => ({
      value: item,
    }));
    multiPreRuler2Dataset.value = ruler2SelectDatasetValue.value;
  }
};

const isSmallScreen = ref(false);

const checkScreenWidth = () => {
  isSmallScreen.value = window.innerWidth < 1300;
};

const curModelData = ref();
const loadChartData = async () => {
  const modelId = route.query.modelId;
  if (!modelId) {
    console.error("Err: model id is null.");
    return;
  }
  try {
    let data = modelStore.getModelById(modelId);
    if (!data) {
      data = await ModelService.getOneModelInfo(modelId);
      curModelData.value = data;
    }
    curModelData.value = data;
    Object.assign(modelData, data);
    if (!modelData.info.model_doc.trim()) {
      modelData.info.model_doc = editDoc.value;
    }
    const modelName = data.info.model_name;
    modelNameCandidates = [modelName, modelId].filter(Boolean);
    if (data.info.category.includes("LLM")) {
      const chartData = (await getCurrentFullRes()).data;
      loadRuler1Data(modelName, chartData, "LLM");
      loadRuler2Data(chartData, "LLM");
      // 检查是否具备生成最小集报告能力
      const res = await getMinTestChart({ model_name: modelName });
      console.log("getMinTestChart response:", res);
      reportReadyType.value =
        res.status === 200 && res.data["model"] === modelName ? 5 : 0;
    }
    if (data.info.category.includes("MLLM")) {
      const multiData = (await getMultiModelData()).data;
      loadRuler1Data(modelName, multiData, "MLLM");
      loadRuler2Data(multiData, "MLLM");
      if (
        !(modelName in multiData.ruler1) &&
        !(modelName in multiData.ruler2)
      ) {
        console.log(modelName, "不具备多模态生成报告条件");
        return;
      }
      if (modelName in multiData.ruler1) {
        const datasets_scores = multiData.ruler1[modelName].result;
        // 检查是否具备生成全模态能力的报告
        if (
          AV_REPORT_DATASETS.every((el) =>
            datasets_scores.some((ds) => ds.dataset_name === el)
          )
        ) {
          reportReadyType.value = 6;
        }
        // 检查是否具备生成视觉能力的报告
        else if (
          VISION_REPORT_DATASETS.every((el) =>
            datasets_scores.some((ds) => ds.dataset_name === el)
          )
        ) {
          reportReadyType.value = 7;
        }
        // 检查是否具备生成音频能力的报告
        else if (
          AUDIO_REPORT_DATASETS.every((el) =>
            datasets_scores.some((ds) => ds.dataset_name === el)
          )
        ) {
          reportReadyType.value = 8;
        } else {
          console.log(modelName, "评测数量不够生成报告");
        }
      }
    } else if (
      !data.info.category.includes("LLM") &&
      !data.info.category.includes("MLLM")
    ) {
      console.log("Model info category is invalid.");
    }
  } catch (error) {
    ElMessage.error("获取模型信息失败");
    console.log(error);
  }
};

function onBack() {
  router.push({
    path: "/modelSquare",
  });
}

function switchToTab(index) {
  currentTab.value = index;
}

const genarateAble = ref(true);
const multiGenarateAble = ref();

function checkToGenReport() {
  const compareModels = selectValue.value.filter(
    (item) => item !== modelData.info.model_name
  );
  // if (compareModels.length < 1) {
  //   ElMessage({
  //     type: "error",
  //     message: "请至少选择1个对比模型",
  //   });
  //   isReportGenerating.value = false;
  //   return null;
  // }
  if (compareModels.length > 4) {
    ElMessage({
      type: "error",
      message: "请至多选择4个对比模型",
    });
    isReportGenerating.value = false;
    return null;
  }
  return compareModels;
}

const generateReport = (type) => {
  // 多选报告类型至少选择一个
  if (selectedReportTypes.value.length === 0) {
    ElMessage({
      type: "warning",
      message: "请至少选择一个报告类型",
    });
    return;
  }
  if (
    currentType.value === "MLLM" &&
    multiRuler2SelectDatasetValue.value.length != 0
  ) {
    console.log("multiRuler2SelectDatasetValue");
    console.log(multiRuler2SelectDatasetValue.value);

    // 提取 aisf_gui_plan、aisf_gui_vla 和 aisf_banxue 下的所有叶子节点 value
    const aisfGuiLeafValues = new Set();
    const aisfBanxueLeafValues = new Set();

    multiRuler2Options.value.forEach((option) => {
      if ((option.value === "aisf_gui_plan" || option.value === "aisf_gui_vla") && Array.isArray(option.children)) {
        option.children.forEach((child) => {
          aisfGuiLeafValues.add(child.value);
        });
      }
      if (option.value === "aisf_banxue" && Array.isArray(option.children)) {
        option.children.forEach((child) => {
          aisfBanxueLeafValues.add(child.value);
        });
      }
    });

    const selectedValues = multiRuler2SelectDatasetValue.value || [];

    if (selectedValues.length === 0) {
      // 空数组，type 不变
      return type;
    }
  }
  isReportGenerating.value = true;
  genarateAble.value = true;
  let compareModels = [];
  if (type != 5) {
    //最小集不需要查阅尺子1尺子2数据库
    compareModels = checkToGenReport();
    if (compareModels == null || !compareModels) {
      return;
    }
  }
  console.log("type");
  console.log(type);
  ElMessage({
    type: "success",
    message: "正在生成报告，请稍候...",
  });
  genReport({
    model_id: modelData.model_id,
    model_name: modelData.info.model_name,
    compare_models: compareModels,
    compare_type: type,
  })
    .then(
      (response) => {
        downloadReportPath.value = response.data.filepath;
        ElMessage({
          type: "success",
          message: "生成报告成功",
        });
        isReportGenerating.value = false;
      },
      (err) => {
        ElMessage({
          type: "error",
          message: "生成报告失败: " + err.response.data.error,
        });
        isReportGenerating.value = false;
      }
    )
    .catch((error) => {
      ElMessage({
        type: "error",
        message: "生成报告异常: " + error,
      });
      isReportGenerating.value = false;
    });
};

const downloadReport = () => {
  downloadEvalReport({
    filepath: downloadReportPath.value,
  })
    .then(
      (response) => {
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const a = document.createElement("a");
        a.href = url;
        a.download = downloadReportPath.value
          .split("/")
          .pop()
          .split("\\")
          .pop(); // 设置下载的文件名
        a.click();
        window.URL.revokeObjectURL(url);
        ElMessage({
          type: "success",
          message: "下载成功",
        });
      },
      (err) => {
        ElMessage({
          type: "error",
          message: "下载失败: " + err.response.data.error,
        });
      }
    )
    .catch((error) => {
      ElMessage({
        type: "error",
        message: "下载异常: " + error,
      });
    });
};

const currentType = ref("LLM");
const mllmReportType = ref(67);

// 多选报告类型
const selectedReportTypes = ref([]);

const reportTypeOptions = computed(() => {
  if (currentType.value === "LLM") {
    return [
      { label: "通用测试集", value: "0" },
      { label: "运维智能", value: "1" },
      { label: "AISF-改写", value: "2" },
      { label: "AISF-意图", value: "3" },
    ];
  } else {
    return [
      { label: "通用测试集", value: "6" },
      { label: "AISF-伴学", value: "7" },
      { label: "AISF-GUI规划", value: "8" },
      { label: "AISF-GUI操控", value: "9" },
    ];
  }
});

const computedReportType = computed(() => {
  return selectedReportTypes.value.sort().join("");
});

watch(currentType, () => {
  selectedReportTypes.value = [];
});

const toMLLM = () => {
  currentType.value = "MLLM";
};

const toLLM = () => {
  currentType.value = "LLM";
};

const hasResult = computed(() => {
  return (
    isInRuler1.value ||
    isInRuler2.value ||
    isInMultiRuler1.value ||
    isInMultiRuler2.value
  );
});

onMounted(async () => {
  await loadChartData();
  checkScreenWidth();
  window.addEventListener("resize", checkScreenWidth);
});
</script>

<style scoped>
.model-details {
  box-sizing: border-box;
  overflow: auto;
  background-color: rgb(245, 245, 245);
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  gap: 12px;
}

.pageTitle {
  flex: 0;
  color: #191919;
  font-size: 16px;
  font-weight: bold;
  font-family: "鸿蒙黑体", sans-serif;
}

.md-header {
  flex: 0 0 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  justify-content: flex-start;
  gap: 16px;
  align-items: center;
  margin: 0 10px;
  padding: 16px 24px;
  border-radius: 8px;
  background-color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-bottom: 1px solid #eee;
  transition: 0.3s ease-in-out;
}

.header-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
}

.header-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 8px;
}

.header-title {
  margin: 0;
  padding: 0;
  font-size: 24px;
}

.tag-group {
  display: flex;
  flex-wrap: nowrap;
  overflow: hidden;
  margin-top: auto;
}

.tag {
  flex: 0 0 auto;
  margin-right: 6px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.type-tag {
  background-color: rgb(231, 235, 254);
  color: rgb(31, 85, 180);
}

.info-tag {
  background-color: rgb(244, 242, 253);
  color: rgb(145, 133, 240);
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
}

.edit-buttons {
  position: absolute;
  right: 0;
}

.action-buttons {
  flex: 0 0 1;
  margin-top: 16px;
  display: flex;
  gap: 8px;
  flex-direction: row;
  justify-content: flex-end;
}

.edit-buttons button,
.action-buttons button {
  border-radius: 8px;
  padding: 6px 24px;
  border: none;
  outline: none;
  color: white;
  background-color: rgba(0, 103, 209, 0.8);
  transition: background-color 0.15s ease-in-out;
}

.edit-buttons button:hover,
.action-buttons button:hover {
  background-color: rgba(0, 103, 209, 1);
}

.action-buttons button.cancel {
  color: rgba(0, 103, 209, 1);
  background-color: rgba(230, 230, 230, 0.5);
}

.action-buttons button.cancel:hover {
  color: rgba(0, 103, 209, 1);
  background-color: rgba(230, 230, 230, 0.8);
}

.tabs-buttons {
  flex: 0 0 1;
  display: flex;
  position: relative;
  flex-direction: row;
  justify-content: flex-start;
  align-items: flex-end;
  gap: 16px;
  border-bottom: 1px solid grey;
}

.tab-content-wrapper {
  flex: 1 1 0;
  display: flex;
  overflow: auto; /* 父元素的滚动 */
  max-height: 2000px;
  flex-direction: column;
  justify-content: stretch;
}

.tab-content {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  position: relative;
}

.tabs-buttons button {
  display: flex;
  padding: 4px 16px;
  position: relative;
  bottom: -1px;
  border-style: none none solid none;
  border-width: 1px;
  border-color: grey;
  background-color: transparent;
  font-size: 16px;
  color: grey;
  transition: border-color, color 0.3s ease-in-out;
}

.tabs-buttons button.active {
  border-width: 2px;
  padding: 8px 16px;
  border-color: #2274c9;
  color: #2274c9;
  font-weight: bold;
}

.evaluation-tab {
  display: flex;
  flex-direction: column;
  position: relative;
  height: 100%;
  justify-content: flex-start;
  /* gap: 48px; */
  padding-top: 36px;
  /* padding: 36px 200px 0; */
  width: 50%;
  /* border: blue 2px solid; */
  border-radius: 30px;
}

table.evaluation-table {
  width: 400px;
  border-collapse: collapse; /* 把所有格线合并成一条白线 */
}

/* 所有单元格和表格本身都用白色实线作边框 */
table.evaluation-table,
table.evaluation-table th,
table.evaluation-table td {
  border: 2px solid rgb(243, 243, 243);
}

table.evaluation-table th,
table.evaluation-table td {
  padding: 8px 16px;
}

/* 表头所有 <th>（“类型”、“测评集”、“分数” 标题） */
table.evaluation-table th {
  background-color: rgb(228, 228, 228);
}

.perf-table {
  width: 100%;
  border-collapse: collapse; /* 合并相邻单元格边框 */
  border: 1px solid rgb(243, 243, 243); /* 表格外框 */
  font-size: 14px;
}

.perf-table th,
.perf-table td {
  border: 1px solid rgb(243, 243, 243); /* 单元格内边框 */
  padding: 8px;
  text-align: center;
}

.perf-table thead th {
  background-color: rgb(228, 228, 228);
}

.doc-editor {
  flex: 1 1 0;
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 16px;
  background-color: rgba(0, 0, 0, 0.015);
  border: 1px solid grey;
  font-size: 16px;
}

.doc-editor:focus {
  outline: none;
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
}

.chartContainer {
  display: flex;
  flex-direction: row;
  min-height: 1200px;
  gap: 20px;
}

.charts {
  position: absolute;
}

.selectContainer {
  position: absolute;
}

.nullData {
  /* position: absolute; */
  width: 600px;
}

.customButton {
  font-size: 14px;
  float: right;
  margin-right: 10px;
}

.customButtonMinTest {
  font-size: 14px;
  float: right;
}

.report-buttons {
}

.customButton :deep(.circular) {
  margin-top: 10px;
  width: 25px;
  height: 25px;
}

.ms-content :deep(.el-tabs__header){
  margin: 0;
}
</style>
