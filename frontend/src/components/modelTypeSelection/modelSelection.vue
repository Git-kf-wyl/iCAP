<template>
  <div class="container">
    <el-tabs
        v-model="activeTab"
        class="tabsContainer"
        @tab-click="tabClick"
        :class="{ 'no-slide': disableSlide }"
    >
      <el-tab-pane label="业务选型" name="business">
        <div class="tableBox">
          <div class="buttonRow">
            <div class="update-info">
              <span class="update-label">更新频率：1个月</span>
              <span class="update-divider"></span>
              <span class="update-label">更新时间：{{ updateTime }}</span>
            </div>
            <el-button class="createTaskbtn" @click="showaddDialog = true">新增数据</el-button>
            <el-button class="createTaskbtn" @click="exportToExcel()">导出数据</el-button>
          </div>
          <el-table
              :data="paginatedInfo"
              fit
              show-header
              class="selectInfoTable"
              :header-cell-style="tableHeaderStyle"
              :default-sort="{ prop: 'ID', order: 'ascending' }"
              @filter-change="handleFilterChange"
              border
              stripe
          >
            <el-table-column label="序号" width="55px" align="center">
              <template #default="scope">
                <span>{{ (currentPage - 1) * pageSize + scope.$index + 1 }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="zone"
                label="领域"
                width="90px"
                :filters="zoneFilters"
                :filter-method="filterHandler"
                align="center"
                column-key="zone"
            >
              <template #default="scope">
                <span>{{ scope.row.zone }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="version"
                label="版本"
                width="100px"
                align="center"
                :filters="versionFilters"
                :filter-method="filterHandler"
                column-key="version"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.version"
                    @change="handleChange(scope.row, 'version')"
                ></el-input>
                <span v-else>{{ scope.row.version }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="direction"
                label="智能方向"
                width="100px"
                :filters="directionFilters"
                :filter-method="filterHandler"
                show-overflow-tooltip
                column-key="direction"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    type="textarea"
                    :rows="1"
                    v-model="scope.row.direction"
                    @change="handleChange(scope.row, 'direction')"
                ></el-input>
                <span v-else>{{ scope.row.direction }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="categorize"
                label="模型分类"
                width="100px"
                align="center"
                :filters="categorizeFilters"
                :filter-method="filterHandler"
                column-key="categorize"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.categorize"
                    @change="handleChange(scope.row, 'categorize')"
                ></el-input>
                <span v-else>{{ scope.row.categorize }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="name"
                label="模型名称"
                min-width="210px"
                align="center"
                :filters="nameFilters"
                :filter-method="filterHandler"
                column-key="name"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.name"
                    @change="handleChange(scope.row, 'name')"
                ></el-input>
                <span v-else>{{ scope.row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="releaseTime"
                label="官方发布时间"
                width="125px"
                align="center"
                :filters="releaseTimeFilters"
                :filter-method="filterHandler"
                column-key="releaseTime"
            >
              <template #default="scope">
                <el-date-picker
                    v-model="scope.row.releaseTime"
                    type="date"
                    aria-label="Pick a date"
                    placeholder="请选择官方发布时间"
                    style="width: 100%"
                    v-if="scope.row.editing"
                    @change="handleChange(scope.row, 'releaseTime')"
                    format="YYYY/MM/DD"
                    value-format="YYYY/MM/DD"
                />
                <span v-else>{{ scope.row.releaseTime }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="modelSize"
                label="模型大小"
                width="100px"
                align="center"
                :filters="modelSizeFilters"
                :filter-method="filterHandler"
                column-key="modelSize"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.modelSize"
                    @change="handleChange(scope.row, 'modelSize')"
                ></el-input>
                <span v-else>{{ scope.row.modelSize }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="framework"
                label="部署框架"
                width="120px"
                align="center"
                :filters="frameworkFilters"
                :filter-method="filterHandler"
                column-key="framework"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.framework"
                    @change="handleChange(scope.row, 'framework')"
                ></el-input>
                <span v-else>{{ scope.row.framework }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="license"
                label="开源协议"
                width="200px"
                align="center"
                :filters="licenseFilters"
                :filter-method="filterHandler"
                column-key="license"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    type="textarea"
                    :rows="1"
                    v-model="scope.row.license"
                    @change="handleChange(scope.row, 'license')"
                ></el-input>
                <span v-else>{{ scope.row.license }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="company"
                label="发布公司"
                width="100px"
                align="center"
                :filters="companyFilters"
                :filter-method="filterHandler"
                column-key="company"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.company"
                    @change="handleChange(scope.row, 'company')"
                ></el-input>
                <span v-else>{{ scope.row.company }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="TMG"
                label="TMG裁决"
                width="105px"
                align="center"
                :filters="TMGFilters"
                :filter-method="filterHandler"
                column-key="TMG"
            >
              <template #default="scope">
                <span>{{ scope.row.TMG }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="DRB"
                label="DRB裁决"
                width="105px"
                align="center"
                :filters="DRBFilters"
                :filter-method="filterHandler"
                column-key="DRB"
            >
              <template #default="scope">
                <span>{{ scope.row.DRB }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="minutes"
                label="裁决纪要"
                width="100px"
                align="center"
                :filters="minutesFilters"
                :filter-method="filterHandler"
                column-key="minutes"
            >
              <template #default="scope">
                <span>{{ scope.row.minutes }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="responsiblePerson"
                label="选型责任人"
                width="110px"
                align="center"
                :filters="responsiblePersonFilters"
                :filter-method="filterHandler"
                column-key="responsiblePerson"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    v-model="scope.row.responsiblePerson"
                    @change="handleChange(scope.row, 'responsiblePerson')"
                ></el-input>
                <span v-else>{{ scope.row.responsiblePerson }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="remark"
                label="备注"
                min-width="100px"
                :filters="remarkFilters"
                :filter-method="filterHandler"
                show-overflow-tooltip
                column-key="remark"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    type="textarea"
                    :rows="1"
                    v-model="scope.row.remark"
                    @change="handleChange(scope.row, 'remark')"
                ></el-input>
                <span v-else>{{ scope.row.remark }}</span>
              </template>
            </el-table-column>
            <el-table-column
                prop="edit_time"
                label="最后编辑时间"
                min-width="100px"
                :filters="editTimeFilters"
                :filter-method="filterHandler"
                show-overflow-tooltip
                column-key="edit_time"
            >
              <template #default="scope">
                <el-input
                    v-if="scope.row.editing"
                    type="textarea"
                    :rows="1"
                    v-model="scope.row.edit_time"
                    @change="handleChange(scope.row, 'edit_time')"
                ></el-input>
                <span v-else>{{ scope.row.edit_time }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="90px" align="center">
              <template #default="{ row }">
                <el-tooltip content="编辑" placement="top" v-if="!row.editing">
                  <el-button
                      link
                      type="primary"
                      size="large"
                      @click="startEdit(row)"
                      v-if="!row.editing"
                  >
                    <el-icon>
                      <Edit/>
                    </el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip content="取消" placement="top" v-if="row.editing">
                  <el-button
                      link
                      type="primary"
                      size="large"
                      v-if="row.editing"
                      @click="closeEdit(row)"
                  >
                    <el-icon>
                      <Close/>
                    </el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip content="确认" placement="top" v-if="row.editing">
                  <el-button link type="primary" size="large" v-if="row.editing" @click="saveEdit(row)">
                    <el-icon>
                      <Check/>
                    </el-icon>
                  </el-button>
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <el-button link type="primary" size="large" @click="handleDelete(row)">
                    <el-icon>
                      <Delete/>
                    </el-icon>
                  </el-button>
                </el-tooltip>
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
      </el-tab-pane>
      <el-tab-pane label="大语言模型" name="language">
        <component v-if="activeTab === 'language'" :is="Language" />
      </el-tab-pane>
    </el-tabs>
    <el-dialog
        :title="dialogTitle"
        v-model="showaddDialog"
        width="30%"
        draggable
        :modal="false"
        :before-close="closeDialog"
        top="10vh"
    >
      <el-form
          :model="formData"
          label-width="auto"
          :rules="rules"
          ref="addFormRef"
          style="max-width: 600px"
      >
        <el-form-item label="领域" prop="zone">
          <el-input v-model="formData.zone" placeholder="请输入领域"></el-input>
        </el-form-item>
        <el-form-item label="版本" prop="version">
          <el-input v-model="formData.version" placeholder="请输入版本"></el-input>
        </el-form-item>
        <el-form-item label="智能方向" prop="direction">
          <el-input v-model="formData.direction" placeholder="请输入智能方向"></el-input>
        </el-form-item>
        <el-form-item label="模型分类" prop="categorize">
          <el-input v-model="formData.categorize" placeholder="请输入模型分类"></el-input>
        </el-form-item>
        <el-form-item label="模型名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入模型名称"></el-input>
        </el-form-item>
        <el-form-item label="官方发布时间" prop="releaseTime">
          <el-date-picker
              v-model="formData.releaseTime"
              type="date"
              aria-label="Pick a date"
              placeholder="请选择官方发布时间"
              style="width: 100%"
              format="YYYY/MM/DD"
              value-format="YYYY/MM/DD"
          />
        </el-form-item>
        <el-form-item label="模型大小" prop="modelSize">
          <el-input v-model="formData.modelSize" placeholder="请输入模型大小"></el-input>
        </el-form-item>
        <el-form-item label="部署框架" prop="framework">
          <el-input v-model="formData.framework" placeholder="请输入部署框架"></el-input>
        </el-form-item>
        <el-form-item label="开源协议" prop="license">
          <el-input v-model="formData.license" placeholder="请输入开源协议"></el-input>
        </el-form-item>
        <el-form-item label="发布公司" prop="company">
          <el-input v-model="formData.company" placeholder="请输入发布公司"></el-input>
        </el-form-item>
        <!-- <el-form-item label="模式" prop="mode">
          <el-radio-group v-model="formData.mode">
            <el-radio value="open">开源</el-radio>
            <el-radio value="self">自研</el-radio>
          </el-radio-group>
        </el-form-item>-->
        <el-form-item label="TMG裁决" prop="TMG">
          <el-radio-group v-model="formData.TMG">
            <el-radio value="Y">Yes</el-radio>
            <el-radio value="N">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="DRB裁决" prop="DRB">
          <el-radio-group v-model="formData.DRB">
            <el-radio value="Y">Yes</el-radio>
            <el-radio value="N">No</el-radio>
          </el-radio-group>
        </el-form-item>
        <!-- <el-form-item label="类型" prop="type">
          <el-radio-group v-model="formData.type">
            <el-radio value="Reasoning">Reasoning</el-radio>
            <el-radio value="Chat">Chat</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="领域微调" prop="tune">
          <el-radio-group v-model="formData.tune">
            <el-radio value="sft">sft</el-radio>
            <el-radio value="lora">lora</el-radio>
          </el-radio-group>
        </el-form-item>-->
        <!-- <el-form-item label="模型压缩" prop="compression">
          <el-radio-group v-model="formData.compression">
            <el-radio value="W4a16">W4a16量化</el-radio>
            <el-radio value="W8a8">W8a8量化</el-radio>
          </el-radio-group>
        </el-form-item>-->
        <!-- <el-form-item label="模型类别" prop="modelType">
          <el-radio-group v-model="formData.modelType">
            <el-radio value="largeLanguage">大语言模型</el-radio>
            <el-radio value="multimodal">多模态模型</el-radio>
          </el-radio-group>
        </el-form-item>-->
        <el-form-item label="裁决纪要" prop="minutes">
          <el-input v-model="formData.minutes" placeholder="请输入裁决纪要"></el-input>
        </el-form-item>
        <el-form-item label="选型责任人" prop="responsiblePerson">
          <el-input v-model="formData.responsiblePerson" placeholder="请输入选型责任人"></el-input>
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="formData.remark" placeholder="请输入备注"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeDialog">取 消</el-button>
          <el-button type="primary" @click="addModelSelect">确 定</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import {ref, computed, reactive, onMounted} from "vue";
import {
  getAllmodelSelect,
  deletemodelSelectionByID,
  addmodelSelect,
  modifymodelSelect,
  getAIPerformanceData
} from "@/api/dataService";
import {FormInstance, FormRules, tabBarProps} from "element-plus";
import {ElMessage, ElMessageBox, TableColumnCtx} from "element-plus";
import * as XLSX from "xlsx";
import saveAs from "file-saver";
import Language from './language.vue'
import Professional from './professional.vue'

const showaddDialog = ref(false);

const disableSlide = ref(true);

// ===================== 更新时间自动刷新 =====================
const updateTime = ref('');

const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const refreshUpdateTime = () => {
  updateTime.value = formatDate(new Date());
  localStorage.setItem('businessSelectionUpdateTime', updateTime.value);
};

const loadPersistedUpdateTime = () => {
  const saved = localStorage.getItem('businessSelectionUpdateTime');
  if (saved) {
    updateTime.value = saved;
  } else {
    updateTime.value = '2026-06-30';
  }
};

const activeTab = ref('business');
const tabClick = async (tab) => {
  activeTab.value = tab.props.name
  currentPage.value = 1;
};

interface AddForm {
  zone: string;
  version: string;
  name: string;
  releaseTime: Date;
  modelSize: string;
  // type: string;
  // tune: string;
  compression: string;
  // modelType: string;
  framework: string;
  license: string;
  company: string;
  mode: string;
  TMG: string;
  DRB: string;
  responsiblePerson: string;
  direction: string;
  categorize: string;
  remark: string;
  minutes: string;
}

const initialFormData = {
  zone: "",
  version: "",
  name: "",
  releaseTime: null,
  modelSize: "",
  // type: "",
  // tune: "",
  compression: "",
  // modelType: "",
  framework: "",
  license: "",
  company: "",
  mode: "",
  TMG: "",
  DRB: "",
  responsiblePerson: "",
  direction: "",
  categorize: "",
  remark: "",
  edit_time: "",
  minutes: "",
};

const exportToExcel = () => {
  const orderedData = tableData.value.map((item) => ({
    序号: item.ID,
    领域: item.zone,
    版本: item.version,
    智能方向: item.direction,
    模型分类: item.categorize,
    模型名称: item.name,
    官方发布时间: item.releaseTime,
    模型大小: item.modelSize,
    部署框架: item.framework,
    开源协议: item.license,
    发布公司: item.company,
    TMG裁决: item.TMG,
    DRB裁决: item.DRB,
    裁决纪要: item.minutes,
    // 类型: item.type,
    // 领域微调: item.tune,
    // 模型类别: item.modelType,
    选型责任人: item.responsiblePerson,
    最后修改时间: item.edit_time,
    备注: item.remark,
  }));
  const worksheet = XLSX.utils.json_to_sheet(orderedData);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Sheet1");
  const excelBuffer = XLSX.write(workbook, {
    bookType: "xlsx",
    type: "array",
  });
  const blob = new Blob([excelBuffer], {type: "application/octet-stream"});
  saveAs(blob, "模型选型.xlsx");
};

// 使用 reactive 创建响应式数据
const formData = reactive<AddForm>({...initialFormData});

const addFormRef = ref<FormInstance>();

const rules = reactive<FormRules<AddForm>>({
  name: [{required: true, message: "请输入模型名称", trigger: "blur"}],
});

const tableData = ref([]);

// 定义分页相关变量
const pageSize = ref(20);
const currentPage = ref(1);
const totalItems = computed(() => filteredModelSelection.value.length);

// 分页数据计算属性
const paginatedInfo = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return filteredModelSelection.value.slice(start, end);
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
  // textAlign: "center",
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
};

const dialogTitle = computed(() => (isEdit.value ? "编辑数据" : "新增数据"));

const closeDialog = () => {
  console.log("close dialog!");
  Object.assign(formData, initialFormData);
  showaddDialog.value = false;
  isEdit.value = false;
};

const addModelSelect = () => {
  console.log(formData);
  if (isEdit.value) {
    modifymodelSelect(formData).then((response) => {
      loadData();
      refreshUpdateTime();
    });
  } else {
    addmodelSelect(formData)
        .then((response) => {
          console.log("接口返回数据:", response);
          showaddDialog.value = false;
          loadData();
          refreshUpdateTime();
        })
        .catch((error) => {
          console.error("接口调用失败:", error);
        });
  }
  closeDialog();
};

const isEdit = ref(false);

const startEdit = (row) => {
  // row.editing = !row.editing;
  editData.value[row.ID] = row;
  console.log(editData.value);
  Object.assign(formData, row);
  showaddDialog.value = true;
  isEdit.value = true;
};

const editData = ref([]);

const handleRadioChange = (row, field, value) => {
  // 如果当前值相同则置空，否则设置新值
  row[field] = row[field] === value ? "" : value;
  handleChange(row, field);
};

const handleChange = (row, field) => {
  // 临时数据变化时，更新临时数据
  console.log(row[field]);
  editData.value[row.ID][field] = row[field];
  console.log(editData.value);
};

const closeEdit = (row) => {
  row.editing = false;
  editData.value[row.ID] = {};
  loadData();
};

const saveEdit = (row) => {
  row.editing = false;
  console.log(row);
  modifymodelSelect(row).then((response) => {
    loadData();
    refreshUpdateTime();
  });
};

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除序号为 ${row.ID} 的数据项吗？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning",
  })
      .then(() => {
        // 执行删除操作
        deleteModelSelect(row);
        ElMessage({
          type: "success",
          message: "删除成功",
        });
      })
      .catch(() => {
        //   ElMessage({
        //     type: "info",
        //     message: "已取消删除",
        //   });
      });
};

const deleteModelSelect = (row) => {
  const ids = [row.ID];
  deletemodelSelectionByID(ids).then((response) => {
    loadData();
    refreshUpdateTime();
  });
};

const zoneFilterName = ref([]);
const versionFilterName = ref([]);
const directionFiltername = ref([]);
const categorizeFilterName = ref([]);
const nameFilterName = ref([]);
const releaseTimeFilterName = ref([]);
const modelSizeFilterName = ref([]);
const frameworkFilterName = ref([]);
const licenseFilterName = ref([]);
const companyFilterName = ref([]);
const TMGFilterName = ref([]);
const DRBFilterName = ref([]);
const responsiblePersonFilterName = ref([]);
const remarkFilterName = ref([]);
const editTimeFilterName = ref([]);
const minutesFilterName = ref([]);

const zoneFilters = ref([]);
const versionFilters = ref([]);
const directionFilters = ref([]);
const categorizeFilters = ref([]);
const nameFilters = ref([]);
const releaseTimeFilters = ref([]);
const modelSizeFilters = ref([]);
const frameworkFilters = ref([]);
const licenseFilters = ref([]);
const companyFilters = ref([]);
const TMGFilters = ref([]);
const DRBFilters = ref([]);
const responsiblePersonFilters = ref([]);
const remarkFilters = ref([]);
const editTimeFilters = ref([]);
const minutesFilters = ref([]);

function getUniqueFilters(field, data) {
  return [
    ...new Set(
        data
            .map((item) => item[field])
            .filter(
                (value) => value !== null && value !== "" && value !== undefined
            )
    ),
  ].map((value) => ({text: value, value}));
}

const loadFilters = () => {
  // 模型选型数据
  zoneFilters.value = getUniqueFilters("zone", tableData.value);
  versionFilters.value = getUniqueFilters("version", tableData.value);
  directionFilters.value = getUniqueFilters("direction", tableData.value);
  categorizeFilters.value = getUniqueFilters("categorize", tableData.value);
  nameFilters.value = getUniqueFilters("name", tableData.value);
  releaseTimeFilters.value = getUniqueFilters("releaseTime", tableData.value);
  modelSizeFilters.value = getUniqueFilters("modelSize", tableData.value);
  frameworkFilters.value = getUniqueFilters("framework", tableData.value);
  licenseFilters.value = getUniqueFilters("license", tableData.value);
  companyFilters.value = getUniqueFilters("company", tableData.value);
  TMGFilters.value = getUniqueFilters("TMG", tableData.value);
  DRBFilters.value = getUniqueFilters("DRB", tableData.value);
  responsiblePersonFilters.value = getUniqueFilters(
      "responsiblePerson",
      tableData.value
  );
  remarkFilters.value = getUniqueFilters("remark", tableData.value);
  editTimeFilters.value = getUniqueFilters("edit_time", tableData.value);
  minutesFilters.value = getUniqueFilters("minutes", tableData.value);
};

const filterHandler = (
    value: string,
    row: AddForm,
    column: TableColumnCtx<AddForm>
) => {
  console.log("filterHandler:", column, column.property, value, row);
  const property = column.property;
  if (!property) {
    console.error("Column property is undefined");
    return false;
  }
  return row[property] === value;
};

const handleFilterChange = (filters) => {
  console.log("filters");
  console.log(filters);
  zoneFilterName.value = filters.zone || [];
  versionFilterName.value = filters.version || [];
  directionFiltername.value = filters.direction || [];
  categorizeFilterName.value = filters.categorize || [];
  nameFilterName.value = filters.name || [];
  releaseTimeFilterName.value = filters.releaseTime || [];
  modelSizeFilterName.value = filters.modelSize || [];
  frameworkFilterName.value = filters.framework || [];
  licenseFilterName.value = filters.license || [];
  companyFilterName.value = filters.company || [];
  TMGFilterName.value = filters.TMG || [];
  DRBFilterName.value = filters.DRB || [];
  responsiblePersonFilterName.value = filters.responsiblePerson || [];
  remarkFilterName.value = filters.remark || [];
  editTimeFilterName.value = filters.edit_time || [];
  minutesFilterName.value = filters.minutes || [];
  loadFilters();

  // currentPage.value = 1;
};

const filteredModelSelection = computed(() => {
  const filters = {
    zone: zoneFilterName.value,
    version: versionFilterName.value,
    direction: directionFiltername.value,
    categorize: categorizeFilterName.value,
    name: nameFilterName.value,
    releaseTime: releaseTimeFilterName.value,
    modelSize: modelSizeFilterName.value,
    framework: frameworkFilterName.value,
    license: licenseFilterName.value,
    company: companyFilterName.value,
    TMG: TMGFilterName.value,
    DRB: DRBFilterName.value,
    responsiblePerson: responsiblePersonFilterName.value,
    remark: remarkFilterName.value,
    editTime: editTimeFilterName.value,
    minutes: minutesFilterName.value,
  };

  return tableData.value.filter((row) => {
    return Object.keys(filters).every((key) => {
      const filterValues = filters[key];
      const rowValue = row[key];
      return filterValues.length === 0 || filterValues.includes(rowValue);
    });
  });
});

const loadData = async () => {
  try {
    const response = await getAllmodelSelect();
    tableData.value = response.data;
    loadFilters();
  } catch (error) {
    console.error("Error fetching data:", error);
  }
};

onMounted(async () => {
  loadData();
  loadAIPerformanceData();
  loadPersistedUpdateTime();
});

// 针对AI性能表格的数据管理
const fwFilterName = ref([]);
const inputSeqFiltername = ref([]);
const outputSeqFilterName = ref([]);
const modelNameFilterName = ref([]);
const quantizeFilterName = ref([]);

const fwFilters = ref([]);
const modelNameFilters = ref([]);
const quantizeFilters = ref([]);

const loadAIPerformanceFilters = () => {
  // AI门神数据
  fwFilters.value = getUniqueFilters("framework", performanceTableData.value);
  modelNameFilters.value = getUniqueFilters("modelName", performanceTableData.value);
  quantizeFilters.value = getUniqueFilters("quantize", performanceTableData.value);
};

const handleSortChange = ({column, prop, order}) => {
  sortConfig.value = {prop, order};
};
const sortConfig = ref({prop: "", order: ""});

const sortedData = computed(() => {
  let {prop, order} = sortConfig.value;
  if (!prop || !order) {
    prop = "id";
    order = "descending";
  }
  return [...filteredAIPerformance.value].sort((a, b) => {
    let formatA = a[prop] ?? 0;
    let formatB = b[prop] ?? 0;
    return order == 'ascending' ? (formatA - formatB) : (formatB - formatA);
  });
});

const handleAIPerformanceFilterChange = (filters) => {
  fwFilterName.value = filters.framework || [];
  modelNameFilterName.value = filters.modelName || [];
  quantizeFilterName.value = filters.quantize || [];
  loadAIPerformanceFilters();
};

const filteredAIPerformance = computed(() => {
  const filters = {
    framework: fwFilterName.value,
    modelName: modelNameFilterName.value,
    quantize: quantizeFilterName.value,
  };

  return performanceTableData.value.filter((row) => {
    return Object.keys(filters).every((key) => {
      const filterValues = filters[key];
      const rowValue = row[key];
      return filterValues.length === 0 || filterValues.includes(rowValue);
    });
  });
});

const totalAIPerformanceItems = computed(() => sortedData.value.length);

const pageInfoAIPerformance = computed(() => {
  console.log('enter pageInfoAIPerformance');
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return sortedData.value.slice(start, end);
});

const exportPerformanceToExcel = () => {

}
const performanceTableData = ref([]);
const loadAIPerformanceData = async () => {
    try {
        const response = await getAIPerformanceData();
        // 适配门神接口变动
        const originalData = response.data.data
        originalData.forEach((el) => {
            const transformData = {
                framework: el.serviceInfo.framework,
                serviceType: el.serviceInfo.serviceType,
                modelName: el.serviceInfo.modelName,
                quantize: el.serviceInfo.quantize,
                inputTokenThroughput: el.benchmarkInfo.systemPerformance.inputTokenThroughput,
                outputTokenThroughput: el.benchmarkInfo.systemPerformance.outputTokenThroughput,
                requestNum: el.benchmarkInfo.systemPerformance.requestNum,
                memoryUsageRate: el.envInfo.memoryUsageRate,
                npuAverageUsage: el.envInfo.npuAverageUsage,
                npuAverageMemoryUsage: el.envInfo.npuAverageMemoryUsage,
                npuAverageMemoryBandwidth: el.envInfo.npuAverageMemoryBandwidth
            }
            performanceTableData.value.push(transformData);
        })
        loadAIPerformanceFilters();
    } catch (error) {
        console.error("loadAIPerformanceData err:", error);
    }
}


</script>

<style scoped>
.tableBox {
  margin: 0px 10px;
}

.buttonRow {
  height: 36px; /* 保持与标题一致或略高 */
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 12px; /* 下方间距 */
}

.update-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: auto;
  color: #606060;
  font-size: 14px;
}

.update-label {
  font-weight: 500;
  white-space: nowrap;
}

.update-divider {
  width: 1px;
  height: 14px;
  background: #d0d0d0;
}

.titleContainer {
  display: flex;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  line-height: 36px;
  height: 36px;
  margin-bottom: 10px;
}

.titleContainer span:nth-child(-n + 2) {
  color: #969696;
}

.selectInfoTable {
  font-size: 14px;
}

.tabsContainer :deep(.el-tabs__header) {
  margin-left: 20px;
}

.tabsContainer :deep(.el-tabs__item) {
  font-size: 18px;
  z-index: 1;
}
</style>
