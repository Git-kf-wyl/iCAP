<template>
  <div class="container">
    <div class="cardContainer" style="margin-top:20px">
      <div class="buttonRow">
        <!-- <el-button class="createTaskbtn" @click="addDialog()">新增数据</el-button> -->
        <div class="news">
          <div
            class="model-news"
            :style="{ backgroundImage: `url(${modelNewsBg})` }"
            @click="addDialog"
          >
            <h4 class="title">新模型启动测评</h4>
          </div>

          <div
            class="model-selection"
            :style="{ backgroundImage: `url(${modelSelectionBg})` }"
            @click="handleRuleClick"
          >
            <h4 class="title">点击查看测评规则</h4>

            <!-- 添加阻止冒泡的包裹层 -->
            <div v-if="showRulePreview" @click.stop class="custom-image-viewer">
              <el-image-viewer :url-list="ruleImg" show-progress @close="showRulePreview = false">
                <template #progress="{ activeIndex }">
                  <span v-if="activeIndex===0">模型测评规则</span>
                </template>
              </el-image-viewer>
            </div>
          </div>

          <div
            class="model-selection"
            :style="{ backgroundImage: `url(${modelSelectionBg})` }"
            @click="handleProcessClick"
          >
            <h4 class="title">点击查看测评流程</h4>
            <div v-if="showProcessPreview" @click.stop class="custom-image-viewer">
              <el-image-viewer
                :url-list="processImg"
                show-progress
                @close="showProcessPreview = false"
              >
                <template #progress="{ activeIndex }">
                  <span>{{img_index_to_tile[activeIndex]}}</span>
                </template>
              </el-image-viewer>
            </div>
          </div>
        </div>
      </div>
      <el-table
        :data="tableData"
        :header-cell-style="tableHeaderStyle"
        :cell-style="tableCellStyle"
        height="100%"
        :default-sort="{ prop: 'ID', order: 'descending' }"
        @sort-change="handleSortChange"
        @filter-change="handleFilterChange"
      >
        <el-table-column
          prop="modelName"
          label="模型名称"
          sortable
          :filters="modelNameFilters"
          :filter-method="filterHandler"
          width="300px"
        ></el-table-column>
        <el-table-column prop="modelSeries" label="模型系列"></el-table-column>
        <el-table-column
          prop="status"
          label="当前状态"
          sortable
          :filters="statusFilters"
          :filter-method="filterHandler"
        >
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="stage" label="阶段" width="600px">
          <template #default="{ row }">
            <el-steps style="max-width: 600px" :active="row.stage" align-center>
              <el-step title="启动测评" />

              <el-tooltip
                class="box-item"
                effect="dark"
                content="完成模型下载"
                placement="top"
                v-if="row.stage===1"
              >
                <el-step title="模型下载" @click="nextStageDialog(row)" style="cursor: pointer;" />
              </el-tooltip>
              <el-step title="模型下载" v-else />

              <el-tooltip
                class="box-item"
                effect="dark"
                content="完成模型部署"
                placement="top"
                v-if="row.stage===2"
              >
                <el-step title="模型部署" @click="nextStageDialog(row)" style="cursor: pointer;" />
              </el-tooltip>
              <el-step title="模型部署" v-else />

              <el-tooltip
                class="box-item"
                effect="dark"
                content="完成模型注册"
                placement="top"
                v-if="row.stage===3"
              >
                <el-step title="模型注册" @click="nextStageDialog(row)" style="cursor: pointer;" />
              </el-tooltip>
              <el-step title="模型注册" v-else />

              <el-tooltip
                class="box-item"
                effect="dark"
                content="完成模型评估"
                placement="top"
                v-if="row.stage===4"
              >
                <el-step title="模型评估" @click="nextStageDialog(row)" style="cursor: pointer;" />
              </el-tooltip>
              <el-step title="模型评估" v-else />

              <el-step title="输出报告" v-if="row.status!=='完成'&& row.stage<=4" />
              <el-step title="输出报告" @click="toModelDetail(row)" style="cursor: pointer;" v-else />
            </el-steps>
          </template>
        </el-table-column>
        <el-table-column prop="responsible" label="责任人"></el-table-column>
        <el-table-column prop="date1" label="预计完成时间" sortable width="200px"></el-table-column>
        <el-table-column fixed="right" label="操作">
          <template #default="{ row }">
            <!-- <el-tooltip content="生成报告" placement="top">
              <el-button link type="primary" size="large" @click="generateReport(row)">
                <el-icon>
                  <Postcard />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="下载报告" placement="top">
              <el-button link type="primary" size="large" @click="downloadReport(row)">
                <el-icon>
                  <Download />
                </el-icon>
              </el-button>
            </el-tooltip>-->
            <el-tooltip content="编辑信息" placement="top" v-if="row.stage<=4">
              <el-button link type="primary" size="large" @click="editDialog(row)">
                <el-icon>
                  <Edit />
                </el-icon>
              </el-button>
            </el-tooltip>
            <!-- <el-tooltip content="阶段完成" placement="top" v-if="row.stage<=4">
              <el-button link type="primary" size="large" @click="nextStageDialog(row)">
                <el-icon>
                  <Check />
                </el-icon>
              </el-button>
            </el-tooltip>-->
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination">
        <span class="total-text">总计: {{ totalItems }}</span>
        <el-pagination
          background
          layout="sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20]"
          :page-size="pageSize"
          :total="totalItems"
          :current-page="currentPage"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        ></el-pagination>
      </div>
    </div>
    <el-dialog v-model="addDialogOpen" width="600px" title="新增进展" :before-close="closeDialog">
      <el-form
        :model="progressForm"
        label-width="auto"
        style="max-width: 600px"
        :rules="progressFormRules"
      >
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="progressForm.modelName" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="模型系列" prop="modelSeries">
          <el-input v-model="progressForm.modelSeries" placeholder="请输入模型系列" />
        </el-form-item>
        <el-form-item label="下阶段:">
          <div>模型下载</div>
        </el-form-item>
        <el-form-item label="下阶段负责人">
          <el-input v-model="progressForm.responsible" placeholder="请输入下一阶段负责人" />
        </el-form-item>
        <el-form-item label="预期完成时间">
          <el-col :span="11">
            <el-date-picker
              v-model="progressForm.date1"
              type="date"
              placeholder="选择预期完成时间"
              style="width: 100%"
              format="YYYY/MM/DD"
              value-format="YYYY-MM-DD"
            />
          </el-col>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeDialog">取 消</el-button>
          <el-button type="primary" @click="handleAdd">确 定</el-button>
        </div>
      </template>
    </el-dialog>
    <el-dialog
      v-model="editDialogOpen"
      width="600px"
      :title="'编辑'+(curRow?curRow.modelName:'')+'进展'"
      :before-close="closeEditDialog"
    >
      <el-form
        :model="curRow"
        label-width="auto"
        style="max-width: 600px"
        :rules="progressFormRules"
      >
        <el-form-item label="模型名称" prop="modelName">
          <el-input v-model="curRow.modelName" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="当前阶段:" v-if="curRow.status!=='完成'&& curRow.stage<=4">
          <div>{{stages[curRow.stage]}}</div>
        </el-form-item>
        <el-form-item label="本阶段负责人" v-if="curRow.status!=='完成'&& curRow.stage<=4">
          <el-input v-model="curRow.responsible" placeholder="请输入下一阶段负责人" />
        </el-form-item>
        <el-form-item label="当前状态" v-if="curRow.status!=='完成'&& curRow.stage<=4">
          <el-select v-model="curRow.status" placeholder="please select your zone">
            <el-option label="进行" value="进行" />
            <el-option label="延期" value="延期" />
          </el-select>
        </el-form-item>
        <el-form-item label="预期完成时间" v-if="curRow.status!=='完成'&& curRow.stage<=4">
          <el-col :span="11">
            <el-date-picker
              v-model="curRow.date1"
              type="date"
              placeholder="选择预期完成时间"
              style="width: 100%"
              format="YYYY/MM/DD"
              value-format="YYYY-MM-DD"
            />
          </el-col>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeEditDialog">取 消</el-button>
          <el-button type="primary" @click="handleEdit">确 定</el-button>
        </div>
      </template>
    </el-dialog>
    <el-dialog
      v-model="nextStageOpen"
      :width="curRow.stage===4?'80%':'600px'"
      :title="(curRow.modelName?curRow.modelName:'')+'下一阶段'"
      :before-close="closeNextDialog"
      :close-on-click-modal="false"
    >
      <el-form :model="nextStageForm" label-width="auto" style="max-width: 100%">
        <h3 v-if="curRow.stage===4">模型当前测评情况</h3>
        <el-table
          v-if="curRow.stage===4"
          v-loading="scoreDataLoading"
          :data="modelScoreData"
          style="margin-bottom: 20px;"
          class="modelScoreTable"
        >
          <!-- 固定模型名列 -->
          <el-table-column prop="modelName" label="模型名称" fixed />

          <el-table-column
            label="大语言Ruler1"
            v-if="modelScoreData.length > 0 && Object.keys(modelScoreData[0].ruler1).length>0"
            align="center"
          >
            <template v-if="modelScoreData.length > 0">
              <el-table-column
                v-for="(score, key, index) in modelScoreData[0].ruler1"
                :key="`ruler1-${index}`"
                :label="key"
                align="center"
              >
                <template
                  #default="{ row }"
                >{{ (Number.isInteger(row.ruler1[key]*10000))?(row.ruler1[key]*100).toFixed(2):row.ruler1[key] }}</template>
              </el-table-column>
            </template>
          </el-table-column>

          <el-table-column
            label="大语言Ruler2"
            v-if="modelScoreData.length > 0 && Object.keys(modelScoreData[0].ruler2).length>0"
            align="center"
          >
            <template v-if="modelScoreData.length > 0">
              <el-table-column
                v-for="(value, key, index) in modelScoreData[0].ruler2"
                :key="`ruler2-${index}`"
                :label="key"
                align="center"
              >
                <template
                  #default="{ row }"
                >{{ (Number.isInteger(row.ruler2[key]*10000))?(row.ruler2[key]*100).toFixed(2):row.ruler2[key] }}</template>
              </el-table-column>
            </template>
          </el-table-column>

          <el-table-column
            label="多模态Ruler1"
            v-if="modelScoreData.length > 0 && Object.keys(modelScoreData[0].multiRuler1).length>0"
            align="center"
          >
            <template v-if="modelScoreData.length > 0">
              <el-table-column
                v-for="(score, key, index) in modelScoreData[0].multiRuler1"
                :key="`ruler1-${index}`"
                :label="key"
                align="center"
              >
                <template
                  #default="{ row }"
                >{{ (Number.isInteger(row.multiRuler1[key]*10000))?(row.multiRuler1[key]*100).toFixed(2):row.multiRuler1[key] }}</template>
              </el-table-column>
            </template>
          </el-table-column>

          <el-table-column
            label="多模态Ruler2"
            v-if="modelScoreData.length > 0 && Object.keys(modelScoreData[0].multiRuler2).length>0"
            align="center"
          >
            <template v-if="modelScoreData.length > 0">
              <el-table-column
                v-for="(score, key, index) in modelScoreData[0].multiRuler2"
                :key="`ruler1-${index}`"
                :label="key"
                align="center"
              >
                <template
                  #default="{ row }"
                >{{ (Number.isInteger(row.multiRuler2[key]*10000))?(row.multiRuler2[key]*100).toFixed(2):row.multiRuler2[key] }}</template>
              </el-table-column>
            </template>
          </el-table-column>
        </el-table>
        <el-form-item label="模型名称">
          <el-input v-model="curRow.modelName" placeholder="请输入模型名称" disabled />
        </el-form-item>
        <el-form-item label="测评类型" v-if="curRow.stage===3">
          <el-select v-model="evaluationType" placeholder="请选择测评类型" style="width: 200px">
            <el-option label="大语言" value="language" />
            <el-option label="多模态" value="multiple" />
          </el-select>
        </el-form-item>
        <el-form-item label="通用测试集" v-if="curRow.stage===3 && evaluationType==='language'">
          <el-select
            v-model="nextStageForm.dataset1"
            multiple
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="3"
            placeholder="请选择待测评的通用测试集"
          >
            <el-option
              v-for="item in dataset1Options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="领域测试集" v-if="curRow.stage===3 && evaluationType==='language'">
          <el-select
            v-model="nextStageForm.dataset2"
            multiple
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="2"
            placeholder="请选择待测评的领域测试集"
          >
            <el-option
              v-for="item in dataset2Options"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="通用测试集" v-if="curRow.stage===3 && evaluationType==='multiple'">
          <el-select
            v-model="nextStageForm.datasets1multi"
            multiple
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="2"
            placeholder="请选择待测评的通用测试集"
          >
            <el-option
              v-for="item in dataset1MultiOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="领域测试集" v-if="curRow.stage===3 && evaluationType==='multiple'">
          <el-select
            v-model="nextStageForm.datasets2multi"
            multiple
            collapse-tags
            collapse-tags-tooltip
            :max-collapse-tags="2"
            placeholder="请选择待测评的领域测试集"
          >
            <el-option
              v-for="item in dataset2MultiOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="下阶段:">
          <div>{{stages[curRow.stage+1]}}</div>
        </el-form-item>
        <el-form-item label="下阶段负责人" v-if="curRow.status!=='完成'&& curRow.stage<=3">
          <el-input v-model="nextStageForm.responsible" placeholder="请输入下一阶段负责人" />
        </el-form-item>
        <el-form-item label="预期完成时间" v-if="curRow.status!=='完成'&& curRow.stage<=3">
          <el-col :span="11">
            <el-date-picker
              v-model="nextStageForm.date1"
              type="date"
              placeholder="选择预期完成时间"
              style="width: 100%"
              format="YYYY/MM/DD"
              value-format="YYYY-MM-DD"
            />
          </el-col>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeNextDialog">取 消</el-button>
          <el-button type="primary" @click="handleNext">确 定</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, reactive, watch } from "vue";
import { TableColumnCtx } from "element-plus";
import { Download, Postcard } from "@element-plus/icons-vue";
import {
  addModelProgress,
  getModelProgress,
  modifyModelProgress,
  getMultiModelData,
} from "@/api/dataService.js";
import router from "@/router/index.js";
import { useAIModelStore } from "@/stores/aiModel.js";
import { ModelService } from "@/services/modelService.js";
import { ElMessage, ElMessageBox, FormRules } from "element-plus";
import { useRankingStore } from "@/stores/rankingStore";
import { useDatasetStore } from "@/stores/datasetStore";
import { get_datasets } from "@/api/dataSetApi";
import modelNewsBg from "@/assets/modelNewsBg.png";
import modelSelectionBg from "@/assets/modelSelectionBg.png";

const modelStore = useAIModelStore();
const datasetStore = useDatasetStore();
const tableData = ref([]);

const modelNameFilterName = ref([]);
const modelNameFilters = ref([]);

const statusFilterName = ref([]);
const statusFilters = ref([]);

const ruleImg = ref(["/images/new_model_eval_standard.png"]);
const showRulePreview = ref(false);
const handleRuleClick = () => {
  !showRulePreview.value && (showRulePreview.value = true);
};

const processImg = ref([
  "/images/model_eval_overall.png",
  "/images/model_eval_task_progress.png",
  "/images/model_register.png",
  "/images/model_eval.png",
  "/images/model_insight.png",
  "/images/report_generate.png",
  "/images/report_download.png",
]);

const img_index_to_tile = reactive({
  0: "模型测评总体流程",
  1: "1. 模型测评任务跟踪",
  2: "2. 模型注册",
  3: "3. 模型评测",
  4: "4. 模型洞察",
  5: "5. 一键生成报告",
  6: "6. 报告展示",
});
const showProcessPreview = ref(false);
const handleProcessClick = () => {
  !showProcessPreview.value && (showProcessPreview.value = true);
};

interface AddForm {
  modelName: string;
  status: string;
  stage: string;
  responsible: string;
}

function getUniqueFilters(field, data) {
  // console.log("getUniqueFilters");
  return [
    ...new Set(
      data
        .map((item) => item[field])
        .filter(
          (value) => value !== null && value !== "" && value !== undefined
        )
    ),
  ].map((value) => ({ text: value, value }));
}

const filterHandler = (
  value: string,
  row: AddForm,
  column: TableColumnCtx<AddForm>
) => {
  const property = column.property;
  if (!property) {
    console.error("Column property is undefined");
    return false;
  }
  return row[property] === value;
};

const loadFilter = () => {
  modelNameFilters.value = getUniqueFilters("modelName", tableData.value);
  statusFilters.value = getUniqueFilters("status", tableData.value);
  // console.log("modelNameFilters");
  // console.log(modelNameFilters.value);
};

const handleFilterChange = (filters) => {
  // console.log("filters");
  // console.log(filters);
  modelNameFilterName.value = filters.modelName || [];
  statusFilterName.value = filters.status || [];
  loadFilter();
};

const filteredTaskData = computed(() => {
  const filters = {
    modelName: modelNameFilterName.value,
    status: statusFilterName.value,
  };

  return tableData.value.filter((row) => {
    return Object.keys(filters).every((key) => {
      const filterValues = filters[key];
      const rowValue = row[key];
      return filterValues.length === 0 || filterValues.includes(rowValue);
    });
  });
});

// 处理排序
const sortConfig = ref({ prop: "", order: "" });

const handleSortChange = ({ column, prop, order }) => {
  sortConfig.value = { prop, order };
};

const sortedTaskData = computed(() => {
  if (!Array.isArray(tableData.value) || tableData.value.length === 0) {
    return [];
  }

  let { prop, order } = sortConfig.value;
  if (!prop || !order) {
    prop = "ID";
    order = "descending";
  }

  const isAsc = order === "ascending";
  return [...filteredTaskData.value].sort((a, b) => {
    const strA = String(a[prop] || "");
    const strB = String(b[prop] || "");

    return isAsc ? strA.localeCompare(strB) : strB.localeCompare(strA);
  });
});

// 定义分页相关变量
const pageSize = ref(10);
const currentPage = ref(1);
const totalItems = computed(() => sortedTaskData.value.length);

// 分页数据计算属性
const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return sortedTaskData.value.slice(start, end);
});

// 处理每页数量变化
const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1; // 切换每页数量时回到第一页
};

// 处理页码改变
const handleCurrentChange = (val) => {
  currentPage.value = val;
};

const tableHeaderStyle = {
  textAlign: "center",
  backgroundColor: "#f5f6fd",
  color: "#000000",
};

const tableCellStyle = {
  textAlign: "center",
  color: "#000000",
};

const statusTagType = (status) => {
  switch (status) {
    case "完成":
      return "success";
    case "进行":
      return "primary";
    case "延期":
      return "danger";
    default:
      return "info";
  }
};

const getStatusColor = (status) => {
  switch (status) {
    case "completed":
      return "#67C23A"; // 绿色
    case "Doing":
      return "#409EFF"; // 蓝色
    case "failed":
      return "#F56C6C"; // 红色
    case "paused":
      return "#E6A23C"; // 黄色
    default:
      return "#909399"; // 灰色
  }
};

const stages = [
  "启动测评",
  "模型下载",
  "模型部署",
  "模型注册",
  "模型评估",
  "输出报告",
];

const generateReport = (row) => {};

const downloadReport = (row) => {};

const restartProgress = (row) => {};

const progressFormRules = reactive<FormRules<AddForm>>({
  modelName: [{ required: true, message: "请输入模型名称", trigger: "blur" }],
});
const addDialogOpen = ref(false);
const addDialog = () => {
  addDialogOpen.value = true;
};

interface AddForm {
  modelName: string;
  modelSeries: string;
  responsible: string;
  date1: string;
}

const initialFormData = {
  modelName: "",
  modelSeries: "",
  responsible: "",
  date1: "",
};
const progressForm = reactive<AddForm>({ ...initialFormData });

const closeDialog = () => {
  // console.log("close dialog!");
  Object.assign(progressForm, initialFormData);
  addDialogOpen.value = false;
};

const handleAdd = () => {
  console.log(progressForm);
  addModelProgress({ ...progressForm, status: "进行", stage: 1 })
    .then((response) => {
      console.log("接口返回数据:", response);
      loadData();
    })
    .catch((error) => {
      console.error("接口调用失败:", error);
    });

  closeDialog();
};

const curRow = ref({});

const editDialogOpen = ref(false);
const editDialog = (row) => {
  Object.assign(curRow.value, row);
  editDialogOpen.value = true;
};

const closeEditDialog = () => {
  editDialogOpen.value = false;
};

const handleEdit = () => {
  console.log(curRow.value);
  modifyModelProgress({ ...curRow.value })
    .then((response) => {
      console.log("接口返回数据:", response);
      loadData();
    })
    .catch((error) => {
      console.error("接口调用失败:", error);
    });

  closeEditDialog();
};

const nextStageForm = ref({});
const modelScoreData = ref([]);

const modelRuler1Dataset = computed(() => {
  [modelScoreData.value[0].ruler1];
});
const modelRuler2Dataset = computed(() => {
  [modelScoreData.value[0].ruler2];
});
const modelRuler1MultiDataset = computed(() => {});
const modelRuler2MultiDataset = computed(() => {});

const nextStageOpen = ref(false);
const scoreDataLoading = ref(true);

const nextStageDialog = (row) => {
  curRow.value = Object.assign(row);
  evaluationType.value = "";

  if (curRow.value.stage === 3) {
    console.log("检查模型注册");
    const matchModel = models.value.find((model) => {
      return model.model_id === curRow.value.modelName;
    });

    if (!matchModel) {
      console.log(curRow.value.modelName);
      ElMessageBox.confirm(
        "模型广场没有注册该模型，是否跳转模型注册？",
        "提示",
        {
          confirmButtonText: "确认",
          cancelButtonText: "取消",
          type: "warning",
        }
      )
        .then(() => {
          router.push({
            path: "/modelSquare/edit",
            query: {
              modelId: curRow.value.modelName,
              type: "add",
            },
          });
        })
        .catch(() => {});
      ElMessage({
        type: "warning",
        message: "模型广场中没有注册该模型",
      });
      return;
    }
  } else if (curRow.value.stage === 4) {
    loadScoreData();
  }
  nextStageOpen.value = true;
};

const rankingStore = useRankingStore();
const loadScoreData = async () => {
  try {
    modelScoreData.value = [];
    //大语言分数获取
    await rankingStore.getRankingData();
    const ruler1Data = rankingStore.ruler1Values.find((info) => {
      return info.name === curRow.value.modelName;
    });
    let ruler2Data = null;
    Object.keys(rankingStore.ruler2Values).forEach((key) => {
      const sceneData = rankingStore.ruler2Values[key].find((info) => {
        return info.name === curRow.value.modelName;
      });
      if (sceneData) {
        ruler2Data = Object.assign(sceneData);
      }
    });
    // console.log("ruler1Data");
    // console.log(ruler1Data);
    // console.log("ruler2Data");
    // console.log(ruler2Data);

    const tempObj = {
      modelName: curRow.value.modelName,
      ruler1: {},
      ruler2: {},
      multiRuler1: {},
      multiRuler2: {},
    };

    // ====== Ruler1 数据处理 ======
    // 创建所有需要处理的key集合（dataset1 + ruler1Data中所有的key）
    const allRuler1Keys = new Set([
      ...(curRow.value.dataset1 || []),
      ...(ruler1Data?.subsets?.map((d) => d.key) || []),
    ]);

    // 创建分数映射
    const ruler1ScoreMap = {};
    ruler1Data?.subsets?.forEach((dataset) => {
      ruler1ScoreMap[dataset.key] = dataset.score;
    });

    // 遍历所有key，赋值或标记未测评
    allRuler1Keys.forEach((key) => {
      if (key in ruler1ScoreMap) {
        tempObj.ruler1[key] = ruler1ScoreMap[key];
      } else {
        tempObj.ruler1[key] = "测评中";
      }
    });

    // ====== Ruler2 数据处理 ======
    // 创建所有需要处理的key集合（dataset2 + ruler2Data中所有的key）
    const allRuler2Keys = new Set([
      ...(curRow.value.dataset2 || []),
      ...(ruler2Data?.subsets?.map((d) => d.key) || []),
    ]);

    // 创建分数映射
    const ruler2ScoreMap = {};
    ruler2Data?.subsets?.forEach((dataset) => {
      ruler2ScoreMap[dataset.key] = dataset.score;
    });

    // 遍历所有key，赋值或标记未测评
    allRuler2Keys.forEach((key) => {
      if (key in ruler2ScoreMap) {
        tempObj.ruler2[key] = ruler2ScoreMap[key];
      } else {
        tempObj.ruler2[key] = "测评中";
      }
    });

    //多模态分数获取
    const res = await getMultiModelData();
    // console.log("res.data.ruler1");
    // console.log(res.data.ruler1);
    // console.log("res.data.ruler2");
    // console.log(res.data.ruler2);
    let multiRuler1Data = {};
    let multiRuler2Data = {};

    Object.keys(res.data.ruler1).forEach((key) => {
      if (key === curRow.value.modelName) {
        multiRuler1Data = Object.assign(res.data.ruler1[key]);
      }
    });
    Object.keys(res.data.ruler2).forEach((key) => {
      if (key === curRow.value.modelName) {
        multiRuler2Data = Object.assign(res.data.ruler2[key]);
      }
    });
    // console.log("multiRuler1Data");
    // console.log(multiRuler1Data);
    // console.log("multiRuler2Data");
    // console.log(multiRuler2Data);

    // ====== 修改 multiRuler1 数据处理 ======
    const ruler1Results = multiRuler1Data?.result;
    // 合并配置数据集和实际数据集
    const allMultiRuler1Keys = new Set([
      ...(curRow.value.datasets1multi || []), // 配置的数据集
      ...(ruler1Results?.map((item) => item?.dataset_name) || []), // 实际返回的数据集
    ]);

    // 创建分数映射表
    const multiRuler1ScoreMap = {};
    ruler1Results?.forEach((item) => {
      if (item?.dataset_name != null) {
        multiRuler1ScoreMap[item.dataset_name] = item.score;
      }
    });

    // 遍历所有数据集key
    allMultiRuler1Keys.forEach((key) => {
      if (key && key in multiRuler1ScoreMap) {
        tempObj.multiRuler1[key] = multiRuler1ScoreMap[key];
      } else if (key) {
        // 确保key有效
        tempObj.multiRuler1[key] = "测评中";
      }
    });

    // ====== 修改 multiRuler2 数据处理 ======
    const ruler2FirstResult = multiRuler2Data?.result?.[0];
    const ruler2Metrics = ruler2FirstResult?.metrics?.[0];
    const ruler2Categories = ruler2Metrics?.categories?.[0];
    const ruler2Subsets = ruler2Categories?.subsets;

    // 合并配置数据集和实际数据集
    const allMultiRuler2Keys = new Set([
      ...(curRow.value.datasets2multi || []), // 配置的数据集
      ...(ruler2Subsets?.map((item) => item?.name) || []), // 实际返回的数据集
    ]);

    // 创建分数映射表
    const multiRuler2ScoreMap = {};
    ruler2Subsets?.forEach((item) => {
      if (item?.name != null) {
        multiRuler2ScoreMap[item.name] = item.score;
      }
    });

    // 遍历所有数据集key
    allMultiRuler2Keys.forEach((key) => {
      if (key && key in multiRuler2ScoreMap) {
        tempObj.multiRuler2[key] = multiRuler2ScoreMap[key];
      } else if (key) {
        // 确保key有效
        tempObj.multiRuler2[key] = "测评中";
      }
    });

    modelScoreData.value.push(tempObj);
    console.log("modelScoreData");
    console.log(modelScoreData.value);
  } catch (error) {
    console.error("Error fetching data:", error);
  } finally {
    scoreDataLoading.value = false;
  }
};

const evaluationType = ref("");
const LLM_RULER1_LABELS = [
  "知识百科",
  "逻辑推理",
  "数学",
  "代码",
  "工具",
  "指令遵从",
  "长文本",
];
const LLM_RULER2_LABELS = ["运维智能", "业务智能", "算力主机", "AISF"];

watch(evaluationType, (val) => {
  if (val === "language") {
    let filteredEntries = Object.entries(dataset1Data.value).filter(
      ([key, value]) =>
        value.testcase_tags.length > 0 &&
        value.testcase_tags.every((v) => LLM_RULER1_LABELS.indexOf(v) !== -1)
    );
    let filteredObj = Object.fromEntries(filteredEntries);
    dataset1Options.value = [];
    Object.keys(filteredObj).forEach((dataset) => {
      dataset1Options.value.push({
        label: dataset,
        value: dataset,
      });
    });

    filteredEntries = Object.entries(dataset2Data.value).filter(
      ([key, value]) =>
        value.testcase_tags.length > 0 &&
        value.testcase_tags.every((v) => LLM_RULER2_LABELS.indexOf(v) !== -1)
    );
    filteredObj = Object.fromEntries(filteredEntries);
    dataset2Options.value = [];
    Object.keys(filteredObj).forEach((dataset) => {
      dataset2Options.value.push({
        label: dataset,
        value: dataset,
      });
    });

    nextStageForm.value.dataset1 = [
      "aime24",
      "aime25",
      "bfcl_v3",
      "gpqa",
      "ifeval",
      "live_code_bench",
      "mmlu",
    ];
    nextStageForm.value.dataset2 = ["om_alarm_diag", "om_mml_generate"];
    nextStageForm.value.datasets1multi = [];
    nextStageForm.value.datasets2multi = [];
  } else {
    let filteredEntries = Object.entries(dataset1Data.value).filter(
      ([key, value]) =>
        value.testcase_tags.length > 0 &&
        value.testcase_tags.some((v) => LLM_RULER1_LABELS.indexOf(v) === -1)
    );
    let filteredObj = Object.fromEntries(filteredEntries);
    dataset1Options.value = [];
    Object.keys(filteredObj).forEach((dataset) => {
      dataset1MultiOptions.value.push({
        label: dataset,
        value: dataset,
      });
    });

    filteredEntries = Object.entries(dataset2Data.value).filter(
      ([key, value]) =>
        value.testcase_tags.length > 0 &&
        value.testcase_tags.some((v) => LLM_RULER2_LABELS.indexOf(v) === -1)
    );
    filteredObj = Object.fromEntries(filteredEntries);
    dataset2Options.value = [];
    Object.keys(filteredObj).forEach((dataset) => {
      dataset2MultiOptions.value.push({
        label: dataset,
        value: dataset,
      });
    });

    nextStageForm.value.dataset1 = [];
    nextStageForm.value.dataset2 = [];
    nextStageForm.value.datasets1multi = [
      "MMMU",
      "HallusionBench",
      "OCRBench",
      "MMStar",
      "ScreenSpot_Pro",
    ];
    nextStageForm.value.datasets2multi = ["aisf_vla", "视觉感知",'儿童伴读'];
  }
});

const closeNextDialog = () => {
  nextStageOpen.value = false;
  scoreDataLoading.value = true;
};

const handleNext = () => {
  // console.log({
  //   ...nextStageForm.value,
  //   ID: curRow.value.ID,
  //   modelName: curRow.value.modelName,
  //   status: "进行",
  //   stage: curRow.value.stage + 1,
  // });
  // return;
  // if (curRow.value.stage === 3) {
  //   console.log("检查模型注册");
  //   const matchModel = models.value.find((model) => {
  //     return model.model_id === curRow.value.modelName;
  //   });

  //   if (!matchModel) {
  //     console.log(curRow.value.modelName);
  //     ElMessage({
  //       type: "error",
  //       message: "模型广场中没有注册该模型",
  //     });
  //     return;
  //   }
  // }
  modifyModelProgress({
    ...nextStageForm.value,
    ID: curRow.value.ID,
    modelName: curRow.value.modelName,
    status: curRow.value.stage === 4 ? "完成" : "进行",
    stage:
      curRow.value.stage === 4
        ? curRow.value.stage + 2
        : curRow.value.stage + 1,
    dataset1: curRow.value.datasets1,
    dataset2: curRow.value.datasets2,
    aisf: curRow.value.aisf,
  })
    .then((response) => {
      console.log("接口返回数据:", response);
      ElMessage({
        type: "success",
        message: "成功进入下一阶段",
      });
      loadData();
    })
    .catch((error) => {
      console.error("接口调用失败:", error);
      ElMessage({
        type: "error",
        message: "进入下一阶段失败",
      });
    });

  closeNextDialog();
};

const toModelDetail = (row) => {
  console.log("click报告");
  console.log(row);

  router.push({
    path: "/modelSquare/details",
    query: {
      modelId: row.modelName,
    },
  });
};

const loadData = async () => {
  const response = await getModelProgress();
  const data = response.data;
  tableData.value = data;
  // console.log("tableData");
  // console.log(tableData.value);
};

const models = ref([]);

const loadModelData = async () => {
  if (modelStore.models && modelStore.models.length > 0) {
    // console.log(modelStore.models);
    models.value = modelStore.models;
  } else {
    const data = await ModelService.getAllModelInfo();
    modelStore.setModels(data);
    // console.log(modelStore.models);
    models.value = modelStore.models;
  }
};

const dataset1Data = ref();
const dataset2Data = ref();
const aisfData = ref();
const dataset1Options = ref([]);
const dataset2Options = ref([]);
const aisfOptions = ref([]);

const dataset1MultiOptions = ref([]);
const dataset2MultiOptions = ref([]);

const fleshDatasets = async (isField) => {
  const storeKey = `ruler${isField}Datasets`; // 构建 store 中的 key

  // 检查 store 中是否存在对应数据且不为空
  if (datasetStore[storeKey] && datasetStore[storeKey].length > 0) {
    return datasetStore[storeKey];
  }

  // 当 store 中没有数据时调用接口
  const res = await get_datasets(isField);
  datasetStore.setDatasets(`ruler${isField}`, res.data); // 存储到 store
  return res.data;
};

const loadDatasetData = async () => {
  dataset1Data.value = await fleshDatasets("1");
  dataset2Data.value = await fleshDatasets("2");
  aisfData.value = await fleshDatasets("3");

  Object.keys(dataset1Data.value).forEach((key) => {
    dataset1Options.value.push({
      label: key,
      value: key,
    });
  });
  Object.keys(dataset2Data.value).forEach((key) => {
    dataset2Options.value.push({
      label: key,
      value: key,
    });
  });
  Object.keys(aisfData.value).forEach((key) => {
    aisfOptions.value.push({
      label: key,
      value: key,
    });
  });
};

onMounted(async () => {
  await loadModelData();
  await loadData();
  await loadDatasetData();
  loadFilter();
});
</script>

<style scoped>
.buttonRow {
  height: 60px; /* 保持与标题一致或略高 */
  align-items: center;
  margin-bottom: 10px;
}

.createTaskbtn {
  margin: 0;
}

.news {
  flex: 0 0 1;
  height: px;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 16px;
}

.model-news,
.model-selection {
  height: 100%;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  overflow: hidden;
  border-radius: 16px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  padding: 16px;
  cursor: pointer;
}

.model-news {
  flex: 2 2 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
  justify-content: center;
  /* padding: 0; */
}

.model-news .title {
  margin: 0;
  font-size: 16px;
  font-weight: bold;
  color: black;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.model-news .desc {
  font-size: 14px;
  display: flex;
  flex-direction: row;
  justify-content: stretch;
  gap: 4px;
  max-width: 100%;
}

.model-news .desc > p {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  font-size: 14px;
  color: grey;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-news .desc > img {
  min-width: 0;
  flex: 0 0 1;
  height: 20px;
  width: auto;
}

.model-selection {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  /* gap: 8px; */
  align-items: flex-start;
  justify-content: center;
}

.model-selection .title {
  margin: 0;
  font-size: 16px;
  font-weight: bold;
  color: rgb(0, 103, 209);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.model-selection .desc {
  display: block;
  margin: 0;
  font-size: 14px;
  color: grey;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.custom-image-viewer :deep(.el-image-viewer__mask) {
  background-color: rgba(0, 0, 0, 0.7);
}

.custom-image-viewer :deep(.el-image-viewer__canvas) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.custom-image-viewer :deep(.el-image-viewer__canvas img) {
  max-width: 80vw !important; /* 限制最大宽度为视口80% */
  max-height: 78vh !important; /* 限制最大高度为视口80% */
  object-fit: contain; /* 保持比例 */
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.modelScoreTable {
  border: 1px solid rgba(0, 0, 0, 0.3);
}

.modelScoreTable :deep(th) {
  border: 1px solid rgba(0, 0, 0, 0.3);
}

.modelScoreTable :deep(td) {
  border: 1px solid rgba(0, 0, 0, 0.3);
}

.modelScoreTable :deep(.cell) {
  color: black !important;
}
</style>