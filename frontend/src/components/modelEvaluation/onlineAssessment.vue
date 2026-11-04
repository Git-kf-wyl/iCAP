<!--任务列表页-->
<template>
  <div class="container" v-loading.fullscreen.lock="downloadLoading" element-loading-text="下载中...">
    <div style="height: 10px;"></div>
    <div class="cardContainer" style="margin-top: 0;">
      <el-table
        :data="paginatedTasks"
        fit
        stripe
        size="small"
        show-header
        class="TaskInfoTable"
        :header-cell-style="tableHeaderStyle"
        :default-sort="{ prop: 'ID', order: 'descending' }"
        v-loading="loading"
        @sort-change="handleSortChange"
        @filter-change="handleFilterChange"
      >
        <!-- <el-table-column type="index" label="序号" width="60" /> -->
        <el-table-column
          prop="name"
          label="任务名称"
          min-width="80"
          show-overflow-tooltip
          align="center"
          fixed="left"
        />
        <el-table-column
          prop="model_id"
          label="模型"
          sortable
          min-width="150"
          show-overflow-tooltip
          align="center"
          :filters="modelFilters"
          :filter-method="filterHandler"
          column-key="model_id"
        />
        <el-table-column prop="modelType" label="模型类型" min-width="80" align="center" />
        <el-table-column
          prop="datasets"
          label="测试集"
          min-width="200"
          show-overflow-tooltip
          align="center"
        />
        <el-table-column
          prop="assessmentType"
          label="评估类型"
          min-width="130"
          align="center"
          sortable
          :filters="assessmentTypeFilters"
          :filter-method="filterHandler"
          column-key="assessmentType"
        />
        <el-table-column
          prop="status"
          label="状态"
          min-width="90"
          align="center"
          sortable
          :filters="statusFilters"
          :filter-method="filterHandler"
          column-key="status"
        >
          <template #default="{ row }">
            <el-tooltip content="查看运行日志" placement="top">
              <el-button link type="primary" size="large" @click="runLog(row.ID)">
                <el-tag
                  :type="statusTagType(row.status)"
                  size="large"
                  style="width: 80px"
                >{{ row.status }}</el-tag>
              </el-button>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="120" align="center">
          <template #default="{ row }">
            <div style="display: flex; align-items: center">
              <el-progress
                :percentage="row.progress * 100"
                :color="row.progress === 1 ? '#05af12' : '#0087ff'"
                :show-text="false"
                style="flex: 1"
              ></el-progress>
              <el-tooltip content="任务详情" placement="top">
                <span
                  :class="row.progress === 1 ? 'progressValueOk' : 'progressValueNotOk'"
                  @click="handleProgressClick(row)"
                >{{ (row.progress * 100).toFixed(0) }}%</span>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建时间" min-width="120" align="center" />
        <el-table-column label="耗时" min-width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'running'">统计中</el-tag>
            <el-tag type="danger" v-else-if="!row.runningTime">未统计</el-tag>
            <span v-else>{{ formatSeconds(row.runningTime) || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="creator"
          label="创建人"
          min-width="120"
          align="center"
          sortable
          :filters="creatorFilters"
          :filter-method="filterHandler"
          column-key="creator"
        />
        <el-table-column
          prop="description"
          label="描述"
          width="60"
          align="center"
          column-key="description"
          show-overflow-tooltip
        />
        <el-table-column fixed="right" label="操作" min-width="180" align="center">
          <template #default="{ row }">
            <el-tooltip content="评测详情" placement="top">
              <el-button
                link
                type="primary"
                size="large"
                @click="showRowResult(row)"
                v-show="row.assessmentType != 'AISF发布评估'"
              >
                <el-icon>
                  <Document />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="下载测评文件" placement="top">
              <el-button link type="primary" size="large" @click="downloadData(row)">
                <el-icon>
                  <Download />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip content="删除任务信息" placement="top" v-if="manager_list.includes(token)">
              <el-button link type="primary" size="large" @click="openDeleteByID(row.ID)">
                <el-icon>
                  <Delete />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip
              content="重新测评"
              placement="top"
              v-if="manager_list.includes(token) && (row.status !== 'running' && !isinterpretation(row)) || (row.status === 'paused')"
            >
              <el-button
                link
                type="primary"
                size="large"
                @click="reRun(row)"
                v-show="row.assessmentType != 'AISF发布评估'"
              >
                <el-icon>
                  <Refresh />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip
              content="暂停任务"
              placement="top"
              v-else-if="manager_list.includes(token) && !isinterpretation(row) && row.status === 'running'"
            >
              <el-button
                link
                type="primary"
                size="large"
                @click="pauseTask(row.name, row.ID)"
                v-show="row.assessmentType != 'AISF发布评估'"
              >
                <el-icon>
                  <VideoPause />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip
              content="提交结果"
              placement="top"
              v-if="manager_list.includes(token) && !isinterpretation(row) && row.status==='completed'"
            >
              <el-button
                link
                type="primary"
                size="large"
                @click="asyncScore(row)"
                :disabled="row.assessmentType === 'AISF开发评估'"
              >
                <el-icon>
                  <Upload />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip
              content="更新MOS"
              placement="top"
              v-if="manager_list.includes(token) && (row.assessmentType === 'TTS' || row.assessmentType === 'ASR+MT+TTS')"
            >
              <el-button link type="primary" size="large" @click="updateMOS(row)">
                <el-icon>
                  <Upload />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip
              content="更新评测结果"
              placement="top"
              v-if="manager_list.includes(token) && isChildStudy(row)&&row.status === 'completed'"
            >
              <el-button link type="primary" size="large" @click="submitExcel(row)">
                <el-icon>
                  <UploadFilled />
                </el-icon>
              </el-button>
            </el-tooltip>
            <el-tooltip
              :content="row.assessmentType.startsWith('AISF') ? '下载测评表格' : '下载测评报告'"
              placement="top"
              v-if="!isinterpretation(row) && !isChildStudy(row)"
            >
              <el-button
                link
                type="primary"
                size="large"
                @click="handelDownLoadReport(row)"
                :disabled="row.assessmentType == 'AISF发布评估'"
              >
                <el-icon>
                  <tickets />
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
    <el-dialog v-model="refreshDialogVisible" title="重新测评" :close-on-click-modal="false" width="40%">
      <el-radio-group v-model="selectedOption" @change="handleRadioChange" class="radio-group">
        <el-radio
          v-for="item in testCardOption"
          :key="item.value"
          :label="item.value"
          class="custom-radio"
        >
          <span class="radio-label">{{ item.label }}</span>
        </el-radio>
      </el-radio-group>
      <div>
        <el-select v-model="datasets" multiple clearable placeholder="请选择" class="el_input">
          <el-option v-for="value in currentRowDataset" :key="value" :label="value" :value="value" />
        </el-select>
      </div>
      <div style="margin-top: 12px; text-align: right;">
        <el-button type="primary" size="small" @click="openDatasetConfigDialog">配置测试参数</el-button>
      </div>
      <template #footer>
        <el-button @click="refreshDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="openDatasetConfigDialog">下一步：配置测试参数</el-button>
      </template>
    </el-dialog>

    <!-- 数据集参数配置弹窗 -->
    <el-dialog v-model="datasetConfigDialogVisible" title="配置测试参数" :close-on-click-modal="false" width="80%">
      <div v-if="editableDatasetArgs.length === 0" style="text-align: center; color: #999; padding: 20px;">
        请先在"重新测评"弹窗中选择测试集
      </div>
      <div v-else>
        <div
          v-for="(item, index) in editableDatasetArgs"
          :key="item.dataset_name"
          style="border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin-bottom: 12px;"
        >
          <div style="font-weight: 600; font-size: 15px; margin-bottom: 12px; color: #303133;">
            {{ item.dataset_name }}
            <span v-if="isMemoryDataset(item)" style="color: #0067d1;">（记忆）</span>
          </div>
          <el-form label-width="150px" label-position="left" size="small">
            <el-form-item label="eval_batch_size">
              <el-input-number
                v-model="item.eval_batch_size"
                :min="1"
                :max="128"
                controls-position="right"
                style="width: 200px;"
              />
            </el-form-item>
            <el-form-item label="generate_config">
              <el-input
                v-model="item.generate_config"
                type="textarea"
                :rows="3"
                placeholder='例如：{"max_tokens":4096,"temperature":0.6,"top_p":0.95,"top_k":40,"request_nums":4}'
              />
              <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                请输入有效的JSON字符串，与原始数据格式保持一致
              </div>
            </el-form-item>
          </el-form>
          <!-- 记忆测试集子业务编辑表（结构与 dataSetSelectForm.vue 保持一致） -->
          <template v-if="isMemoryDataset(item)">
            <div style="display: flex; justify-content: space-between; align-items: center; margin: 16px 0 8px;">
              <span style="font-weight: bold; font-size: 14px;">记忆子业务参数</span>
            </div>
            <el-table :data="item.memoryBusinessParams" border style="width: 100%;" class="memory-sub-table">
              <el-table-column label="选择" width="60">
                <template #default="scope">
                  <el-checkbox v-model="scope.row.selected" />
                </template>
              </el-table-column>
              <el-table-column prop="name" label="子业务" min-width="120" />
              <el-table-column prop="prompt_version" label="prompt_version" min-width="140">
                <template #default="scope">
                  <el-input v-model="scope.row.prompt_version" placeholder="请输入" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="eval_type" label="eval_type" min-width="140">
                <template #default="scope">
                  <el-input v-model="scope.row.eval_type" placeholder="请输入" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="use_fewshot" label="use_fewshot" min-width="120">
                <template #default="scope">
                  <el-select v-model="scope.row.use_fewshot" placeholder="请选择" size="small">
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
                    <el-radio-group v-model="scope.row.selectedPromptFile" size="small">
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
                    <el-radio-group v-model="scope.row.selectedTestFile" size="small">
                      <el-radio v-for="(tf, idx) in scope.row.testFileList" :key="idx" :value="tf.url" style="margin-right:0;margin-bottom:2px;">
                        {{ tf.name }}
                      </el-radio>
                    </el-radio-group>
                  </div>
                  <span v-else style="color:#999;font-size:12px;">无</span>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </div>
        <!-- 改写业务参数（结构与 startEvaluationForm.vue 保持一致） -->
        <!-- <template v-if="isRewriteSelected">
          <div style="border: 1px solid #e0e0e0; border-radius: 6px; padding: 16px; margin-bottom: 12px;">
            <div style="font-weight: 600; font-size: 15px; margin-bottom: 12px; color: #303133;">
              改写业务参数
            </div>
            <el-form label-width="200px" label-position="left" size="small">
              <el-form-item label="enable_fewshot">
                <el-radio v-model="rewriteFormData.enable_fewshot" :label="true">是</el-radio>
                <el-radio v-model="rewriteFormData.enable_fewshot" :label="false">否</el-radio>
              </el-form-item>
              <el-form-item label="enable_fixed_fewshot">
                <el-radio v-model="rewriteFormData.enable_fixed_fewshot" :label="true">是</el-radio>
                <el-radio v-model="rewriteFormData.enable_fixed_fewshot" :label="false">否</el-radio>
              </el-form-item>
              <el-form-item label="fewshot_retrieval_mode">
                <el-select v-model="rewriteFormData.fewshot_retrieval_mode" placeholder="请选择" style="width: 240px;">
                  <el-option label="query" value="query" />
                  <el-option label="prev_crurent" value="prev_crurent" />
                </el-select>
              </el-form-item>
              <el-form-item label="fewshot_example_field">
                <el-select v-model="rewriteFormData.fewshot_example_field" placeholder="请选择" style="width: 240px;">
                  <el-option label="no_thought_example" value="no_thought_example" />
                  <el-option label="prompt_example" value="prompt_example" />
                </el-select>
              </el-form-item>
              <el-form-item label="fewshot_top_k">
                <el-input-number v-model="rewriteFormData.fewshot_top_k" :min="0" controls-position="right" style="width: 240px;" />
              </el-form-item>
              <el-form-item label="fewshot_score_threshold">
                <el-input-number
                  v-model="rewriteFormData.fewshot_score_threshold"
                  :min="0"
                  :max="1"
                  :step="0.01"
                  controls-position="right"
                  style="width: 240px;"
                />
              </el-form-item>
              <el-form-item label="max_fewshot_examples">
                <el-input-number v-model="rewriteFormData.max_fewshot_examples" :min="0" controls-position="right" style="width: 240px;" />
              </el-form-item>
              <el-form-item label="max_context_turns">
                <el-input-number v-model="rewriteFormData.max_context_turns" :min="0" controls-position="right" style="width: 240px;" />
              </el-form-item>
            </el-form>
          </div>
        </template> -->
      </div>
      <template #footer>
        <el-button @click="datasetConfigDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmDatasetConfig">确认并运行</el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="downloadDialogVisible"
      title="下载测评文件"
      :close-on-click-modal="false"
      width="20%"
    >
      <div>
        <el-select v-model="downloadSelectData" placeholder="测评集测评完成才会显示" class="el_input" multiple>
          <el-option v-for="value in datasetsWithAll" :key="value" :label="value" :value="value" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="downloadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="downloadSubmit">下载</el-button>
      </template>
    </el-dialog>
    <!-- 模型名称编辑弹窗 -->
    <el-dialog v-model="modelEditDialogVisible" title="提交结果" :close-on-click-modal="false" width="30%">
      <div>
        <el-form label-width="100px" label-position="left" size="small">
          <el-form-item label="模型名称">
            <el-input
              v-model="currentRowModelName"
              placeholder="请输入模型名称"
              style="width: 100%;"
            />
          </el-form-item>
        </el-form>
        <div style="font-size: 12px; color: #909399; margin-top: -8px; margin-left: 100px;">
          修改后将以此名称推送到结果列表
        </div>
      </div>
      <template #footer>
        <el-button @click="modelEditDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmModelEdit">下一步</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reloadDialogVisible" title="提交结果" :close-on-click-modal="false" width="20%">
      <div>
        <el-select v-model="reloadSelectData" placeholder="请选择测评集" class="el_input" multiple>
          <el-option v-for="value in reloadWithAll" :key="value" :label="value" :value="value" />
        </el-select>
      </div>
      <template #footer>
        <el-button @click="reloadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="reloadSubmit">提交</el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="runLogDialogVisible"
      title="运行日志"
      :before-close="closeLog"
      :close-on-click-modal="true"
      @close="runLogClose"
      width="60%"
    >
      <div>
        <pre class="logContent">{{ logContent }}</pre>
      </div>
      <template #footer>
        <el-button @click="runLogClose">关闭</el-button>
        <!-- <el-button type="primary" @click="reStartEvaluate">确定</el-button> -->
      </template>
    </el-dialog>
    <el-dialog
      v-model="dialogVisible"
      title="更新MOS（上传Excel文件)"
      width="30%"
      :before-close="handleClose"
    >
      <el-upload
        ref="upload"
        drag
        action
        :http-request="uploadFile"
        :on-success="handleSuccess"
        :on-error="handleError"
        multiple
        :limit="1"
        :on-exceed="handleExceed"
        accept=".xlsx"
      >
        <el-icon class="el-icon--upload">
          <upload-filled />
        </el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或
          <em>点击上传</em>
        </div>
        <div class="el-upload__tip" slot="tip">只能上传Excel文件</div>
      </el-upload>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleClose">关闭</el-button>
          <!-- <el-button type="primary" @click="handleConfirm">确认</el-button> -->
        </div>
      </template>
    </el-dialog>
    <el-dialog
      v-model="excelDialogVisible"
      title="上传儿童伴读评测结果Excel文件"
      width="30%"
      :before-close="handleExcelDialogClose"
    >
      <el-upload
        ref="upload"
        drag
        action
        :http-request="uploadFile"
        :on-success="handleSuccess"
        :on-error="handleError"
        multiple
        :limit="1"
        :on-exceed="handleExceed"
        accept=".xlsx"
      >
        <el-icon class="el-icon--upload">
          <upload-filled />
        </el-icon>
        <div class="el-upload__text">
          将文件拖到此处，或
          <em>点击上传</em>
        </div>
        <div class="el-upload__tip" slot="tip">只能上传Excel文件</div>
      </el-upload>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleExcelDialogClose">关闭</el-button>
          <!-- <el-button type="primary" @click="handleConfirm">确认</el-button> -->
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onUnmounted, computed, reactive } from "vue";
import { useRouter } from "vue-router";
import { useTaskStore } from "@/stores/taskStore";
import {
  ElMessage,
  ElMessageBox,
  ElLoading,
  TableColumnCtx,
  UploadInstance,
  UploadProps,
  UploadRawFile,
  genFileId,
  rowProps,
} from "element-plus";
import { Delete, Document, Download } from "@element-plus/icons-vue";
import {
  getList,
  startRun,
  startRun2,
  startRun3,
  startRunMul,
  deleteById,
  pauseOneTask,
  getProgress,
  resumeOneTask,
} from "@/api/runService.js";
import {
  downloadFile,
  getFilePath,
  getLogs,
  updateScore,
} from "@/api/runService.js";
import { ModelService } from "@/services/modelService.js";
import {
  get_datasets,
  downloadExcell,
  downloadAisfReport,
  uploadMOSFile,
  uploadTestResult,
} from "@/api/dataSetApi.js";
import { writeEvaluationResult } from "@/api/dataService";
import { INTERPRETATIONS_TYPES } from "@/utils/Constants.js";
import Docxtemplater from "docxtemplater";
import { saveAs } from "file-saver";
import PizZip from "pizzip";
import { useStore } from "vuex";
import JSZip from "jszip";
import {manager_list} from '@/consts/copyrightConsts'

const token = ref("");
const store = useStore();
const taskStore = useTaskStore();
const downloadSelectData = ref([]);
const datasets = ref([]);
const currentRow = ref({});
const currentRowDataset = ref({});
const logContent = ref("");
const downloadDialogVisible = ref(false);
const downloadDialogType = ref("");
const refreshDialogVisible = ref(false);
const runLogDialogVisible = ref(false);
const reloadDialogVisible = ref(false);

const reloadSelectData = ref([]);
const reloadWithAll = ref([]);
const reloadTaskId = ref("");
let interval1;

const assessmentTypeFilterName = ref([]);
const statusFilterName = ref([]);
const creatorFilterName = ref([]);
const modelFilterName = ref([]);

const assessmentTypeFilters = ref([]);
const statusFilters = ref([]);
const creatorFilters = ref([]);
const modelFilters = ref([]);

function getUniqueFilters(field, data) {
  // 检查 data 是否为数组
  if (!Array.isArray(data)) {
    console.error("data is not an array:", data);
    return [];
  }

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

interface AddForm {
  assessmentType: string;
  status: string;
  creator: string;
  model_id: string;
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

// 当前用户是否为评测管理员（管理员可查看全部任务，普通用户仅可查看自己创建的任务）
const isManager = computed(() => manager_list.includes(token.value));

// 用户可见的任务数据：管理员展示全部，普通用户仅展示自己创建的任务
const userScopedTaskData = computed(() => {
  if (isManager.value) {
    return data_list.arr;
  }
  return data_list.arr.filter((row) => row.creator === token.value);
});

const loadFilter = () => {
  assessmentTypeFilters.value = getUniqueFilters(
    "assessmentType",
    userScopedTaskData.value
  );
  statusFilters.value = getUniqueFilters("status", userScopedTaskData.value);
  creatorFilters.value = getUniqueFilters("creator", userScopedTaskData.value);
  modelFilters.value = getUniqueFilters("model_id", userScopedTaskData.value);
};

const handleFilterChange = (filters) => {
  // console.log("filters");
  // console.log(filters);
  assessmentTypeFilterName.value = filters.assessmentType || [];
  statusFilterName.value = filters.status || [];
  creatorFilterName.value = filters.creator || [];
  modelFilterName.value = filters.model_id || [];
  loadFilter();
};

const filteredTaskData = computed(() => {
  const filters = {
    assessmentType: assessmentTypeFilterName.value,
    status: statusFilterName.value,
    creator: creatorFilterName.value,
    model_id: modelFilterName.value,
  };

  return userScopedTaskData.value.filter((row) => {
    return Object.keys(filters).every((key) => {
      const filterValues = filters[key];
      const rowValue = row[key];
      return filterValues.length === 0 || filterValues.includes(rowValue);
    });
  });
});

const formatSeconds = computed(() => (seconds) => {
  if (seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;
    const padZero = (value) => value.toString().padStart(2, "0");
    const integerSeconds = Math.floor(remainingSeconds);
    return `${padZero(hours)}:${padZero(minutes)}:${padZero(integerSeconds)}`;
  } else {
    return "00:00:00";
  }
});

const reRun = (row) => {
  // console.log("row");
  // console.log(row);
  // if (isChildStudy(row) || isYitu(row)) {
  //   ElMessageBox.confirm(
  //     '确认继续此任务："' + row.name + '" ？',
  //     "提示",
  //     {
  //       confirmButtonText: "确认",
  //       cancelButtonText: "取消",
  //       type: "warning",
  //     }
  //   )
  //     .then(() => {
  //       if (row.status !== "completed") {
  //         resumeOneTask({ task_id: row.ID }).then(
  //           (res) => {
  //             if (res.data.success == true) {
  //               ElMessage({
  //                 type: "success",
  //                 message: "续测成功",
  //               });
  //               getTasksList();
  //             } else {
  //               ElMessage({
  //                 type: "error",
  //                 message: res.data.error,
  //               });
  //             }
  //           },
  //           (err) => {
  //             ElMessage({
  //               type: "error",
  //               message: "续测失败：" + err.response.data.error,
  //             });
  //           }
  //         );
  //       } else {
  //         reStartEvaluate();
  //       }
  //     })
  //     .catch(() => {
  //       // ElMessage({
  //       //   type: "info",
  //       //   message: "取消停止",
  //       // });
  //     });
  // } else {
  datasets.value = [];
  refreshDialogVisible.value = true;
  currentRow.value = { task_id: row.ID, ...row.taskConfig };
  currentRowDataset.value = row.datasets;
  datasets.value = row.datasets;
  // console.log("currentRow");
  // console.log(currentRow.value);
  // }
};

const closeLog = () => {
  runLogDialogVisible.value = false;
  logContent.value = "";
};

const runLogClose = () => {
  runLogDialogVisible.value = false;
  logContent.value = "";
  clearInterval(interval1);
};

const reloadSubmit = () => {
  writeEvaluationResult({
    task_id: reloadTaskId.value,
    dataset_names: reloadSelectData.value,
    model_id: currentRowModelName.value,
  }).then(
    (res) => {
      reloadDialogVisible.value = false;
      ElMessage({
        type: "success",
        message: "更新成功",
      });
      // 将修改后的模型名称存入 localStorage，用于覆盖评测结果页面拉取的旧值
      // 使用 (task_id + '__' + dataset) 作为 key，确保精确定位到行
      try {
        const modelOverrides = JSON.parse(localStorage.getItem('evalModelOverrides') || '{}');
        reloadSelectData.value.forEach((dataset) => {
          const key = String(reloadTaskId.value) + '__' + dataset;
          modelOverrides[key] = currentRowModelName.value;
        });
        localStorage.setItem('evalModelOverrides', JSON.stringify(modelOverrides));
      } catch (e) {
        console.warn('保存 evalModelOverrides 失败', e);
      }
      // 同步调用 updateScore（update_top_chart）接口更新榜单上的模型名称
      reloadSelectData.value.forEach((dataset) => {
        updateScore({
          task_id: reloadTaskId.value,
          testcase: [dataset],
          model_id: currentRowModelName.value,
        });
      });
    },
    (err) => {
      reloadDialogVisible.value = false;
      ElMessage({
        type: "error",
        message: "更新失败" + err,
      });
    }
  );
};

const runLog = async (ID) => {
  logContent.value = "";
  runLogDialogVisible.value = true;
  const response = await getLogs({ task_id: ID }).then(
    (res) => {
      ElMessage({
        type: "success",
        message: "获取日志成功",
      });
      logContent.value = res.data.logs;
      interval1 = setInterval(async () => {
        await getLogs({ task_id: ID }).then(
          (response) => {
            logContent.value = response.data.logs;
          },
          (err) => {
            ElMessage({
              type: "error",
              message: "日志获取失败",
            });
            clearInterval(interval1);
          }
        );
      }, 5000);
    },
    (error) => {
      ElMessage({
        type: "error",
        message: "日志获取失败: " + error,
      });
    }
  );
};

const asyncScore = (row) => {
  if (row.status !== "completed") {
    ElMessage({
      type: "warning",
      message: "测评未成功，成功后再上传更新",
    });
    return;
  }

  // 设置当前行的模型名称（供编辑弹窗使用）
  currentRowModelName.value = row.model_id || row.model_name || '';
  asyncScoreCurrentRow.value = row;
  modelEditDialogVisible.value = true;
};

// 模型名称编辑弹窗相关
const modelEditDialogVisible = ref(false);
const currentRowModelName = ref('');
const asyncScoreCurrentRow = ref(null);

const confirmModelEdit = () => {
  const row = asyncScoreCurrentRow.value;
  if (!row) return;

  modelEditDialogVisible.value = false;
  reloadDialogVisible.value = true;
  reloadWithAll.value = row.datasets;
  reloadSelectData.value = row.datasets.slice(0, 1);
  reloadTaskId.value = row.ID;
};

// locale.el.pagination = {
//   pagesize: "项/页",
//   goto: "跳转",
//   pageClassifier: "页",
// };

const selectedOption = ref(1);

const downloadLoading = ref(false);

// const downloadSubmit = () => {};

function downloadNotAisf() {
  downloadSelectData.value.forEach((element) => {
    getFilePath({
      task_id: downloadDatasetID.value,
      dataset: element,
      assessmentType: curAssessmentType.value,
      evaluationType: curEvaluationType.value ?? "INTERPRETATION",
    }).then(
      (res) => {
        console.log(res);
        downloadDialogVisible.value = false;
        if (res.data.length === 0) {
          ElMessage({
            type: "error",
            message: "无文件",
          });
          return;
        }

        if (res.data.length === 1) {
          // 单个文件直接下载
          downloadFile({ filepath: res.data[0] }).then(
            (response) => {
              const url = window.URL.createObjectURL(new Blob([response.data]));
              const a = document.createElement("a");
              a.href = url;
              a.download = res.data[0].split("/").pop().split("\\").pop(); // 设置下载的文件名
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
          );
        } else {
          // 多个文件，打包成.zip文件下载
          const zip = new JSZip();
          const promises = res.data.map((file) => {
            return downloadFile({ filepath: file }).then(
              (response) => {
                zip.file(
                  file.split("/").pop().split("\\").pop(),
                  response.data,
                  { binary: true }
                );
              },
              (err) => {
                ElMessage({
                  type: "error",
                  message: "下载失败: " + err.response.data.error,
                });
              }
            );
          });

          Promise.all(promises).then(() => {
            zip.generateAsync({ type: "blob" }).then((content) => {
              saveAs(content, downloadDatasetID.value + ".zip");
              ElMessage({
                type: "success",
                message: "下载成功",
              });
            });
          });
        }
      },
      (err) => {
        ElMessage({
          type: "error",
          message: "获取文件列表失败: " + err.response.data.error,
        });
        downloadDialogVisible.value = false;
      }
    );
  });
}

function downloadAisf() {
  downloadSelectData.value.forEach((element) => {
    const requestData = {
      task_id: downloadDatasetID.value,
      datasets: element,
      username: username.value,
    };
    downloadAisfReport(requestData).then(
      (res) => {
        res.data;
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const a = document.createElement("a");
        a.href = url;
        a.download = downloadDatasetID.value + ".zip";
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
    );
  });
}

const downloadSubmit = () => {
  if (downloadSelectData.value.indexOf("all") !== -1) {
    downloadSelectData.value = downloadSelectData.value.filter(
      (e) => e === "all"
    );
  }
  if (downloadDialogType.value !== "AISF发布评估") {
    downloadNotAisf();
  } else {
    downloadAisf();
  }
};

const datasetsWithAll = ref([]);
const downloadDatasetID = ref("");

const reStartEvaluate = () => {
  const loading = ElLoading.service({
    lock: true,
    text: "卖力加载中...",
  });
  currentRow.value.datasets = datasets.value;
  // dataset_args 已在 confirmDatasetConfig 中更新，此处不再重复过滤
  currentRow.value.retry_content_none = selectedOption.value === 0;
  console.log("currentRow", currentRow.value);

  if (currentRow.value.evaluationType === "multiple") {
    if (currentRow.value.assessmentType === "通用评估(Ruler1)") {
      startRunMul({ ...currentRow.value, username: username.value })
        .then((response) => {
          ElMessage({
            type: "success",
            message: "运行成功",
          });
          loading.close();
          // 重新获取下task状态
          getTaskStatus(currentRow.value.task_id);
        })
        .catch((error) => {
          ElMessage({
            type: "error",
            message: "运行失败：" + error,
          });
        });
    }
    //  else if (currentRow.value.assessmentType === "领域评估(Ruler2)") {
    //   startRunMul2(currentRow.value)
    //     .then((response) => {
    //       ElMessage({
    //         type: "success",
    //         message: "运行成功",
    //       });
    //       loading.close();
    //     })
    //     .catch((error) => {
    //       ElMessage({
    //         type: "error",
    //         message: "运行失败：" + error,
    //       });
    //     });
    // } else if (currentRow.value.assessmentType === "AISF开发评估") {
    //   startRunMul3(currentRow.value)
    //     .then((response) => {
    //       ElMessage({
    //         type: "success",
    //         message: "运行成功",
    //       });
    //       loading.close();
    //     })
    //     .catch((error) => {
    //       ElMessage({
    //         type: "error",
    //         message: "运行失败：" + error,
    //       });
    //     });
    // }
  } else {
    if (currentRow.value.assessmentType === "通用评估(Ruler1)") {
      startRun({ ...currentRow.value, username: username.value })
        .then((response) => {
          ElMessage({
            type: "success",
            message: "运行成功",
          });
          loading.close();
          // 重新获取下task状态
          getTaskStatus(currentRow.value.task_id);
        })
        .catch((error) => {
          ElMessage({
            type: "error",
            message: "运行失败：" + error,
          });
        });
    } else if (currentRow.value.assessmentType === "领域评估(Ruler2)") {
      startRun2({ ...currentRow.value, username: username.value })
        .then((response) => {
          ElMessage({
            type: "success",
            message: "运行成功",
          });
          loading.close();
          // 重新获取下task状态
          getTaskStatus(currentRow.value.task_id);
        })
        .catch((error) => {
          ElMessage({
            type: "error",
            message: "运行失败：" + error,
          });
        });
    } else if (currentRow.value.assessmentType === "AISF开发评估") {
      startRun3({ ...currentRow.value, username: username.value })
        .then((response) => {
          ElMessage({
            type: "success",
            message: "运行成功",
          });
          loading.close();
          // 重新获取下task状态
          getTaskStatus(currentRow.value.task_id);
        })
        .catch((error) => {
          ElMessage({
            type: "error",
            message: "运行失败：" + error,
          });
        });
    }
  }
  loading.close();
  refreshDialogVisible.value = false;
};

const getTaskStatus = (task_id) => {
  getProgress(task_id).then((res) => {
    const index = data_list.arr.findIndex((item) => item.ID === task_id);
    if (index !== -1) {
      data_list.arr[index] = res.data;
    }
  });
};

const statusTagType = (status) => {
  switch (status) {
    case "completed":
      return "success";
    case "running":
      return "primary";
    case "failed":
      return "danger";
    default:
      return "warning";
  }
};

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
};

const router = useRouter();

const handleProgressClick = (row) => {
  // console.log("row");
  // console.log(row);
  if (row.taskConfig.evaluationType === "multiple") {
    router.push({
      name: "multipleEvaluation",
      query: {
        task_id: row.ID,
      },
    });
  } else if (row.taskConfig.evaluationType === "language") {
    router.push({
      name: "languageEvaluation",
      query: {
        task_id: row.ID,
      },
      // params: {
      //   config: JSON.stringify(row),
      // },
    });
  } else if (INTERPRETATIONS_TYPES.includes(row.taskConfig.assessmentType)) {
    router.push({
      name: "interpretation",
      query: {
        task_id: row.ID,
      },
    });
  } else {
    router.push({
      name: "languageEvaluation",
      query: {
        task_id: row.ID,
      },
      // params: {
      //   config: JSON.stringify(row),
      // },
    });
    console.log("router to evaluation error!");
  }
};

const showRowResult = (task) => {
  // console.log(task);
  router.push({
    name: "taskDetail",
    query: {
      taskId: task.ID,
      model_name: task.model_name,
      datasets: JSON.stringify(task.datasets),
      assessmentType: task.assessmentType,
    },
  });
};

const pauseTask = (name, ID) => {
  ElMessageBox.confirm(
    '确认停止此评估任务："' + name + '" ？（停止后点击开始可继续执行此任务）',
    "提示",
    {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning",
    }
  )
    .then(() => {
      pauseOneTask({ task_id: ID }).then(
        (res) => {
          if (res.data.success == true) {
            ElMessage({
              type: "success",
              message: "暂停成功",
            });
            // 暂停成功，将本地任务状态置为 paused
            const task = data_list.arr.find((item) => item.ID === ID);
            if (task) {
              task.status = "paused";
            }
            getTasksList();
          } else {
            ElMessage({
              type: "error",
              message: res.data.error,
            });
            // 请求返回错误，将本地任务状态置为 failed
            const task = data_list.arr.find((item) => item.ID === ID);
            if (task) {
              task.status = "failed";
            }
          }
        },
        (err) => {
          ElMessage({
            type: "error",
            message: "暂停失败：" + err.response.data.error,
          });
          // 请求失败，将本地任务状态置为 failed
          const task = data_list.arr.find((item) => item.ID === ID);
          if (task) {
            task.status = "failed";
          }
        }
      );
    })
    .catch(() => {
      ElMessage({
        type: "info",
        message: "取消停止",
      });
    });
};

const openDeleteByID = (ID) => {
  ElMessageBox.confirm("确认删除 ID 为 " + ID + " 的评估任务信息？", "提示", {
    confirmButtonText: "确认",
    cancelButtonText: "取消",
    type: "warning",
  })
    .then(() => {
      // taskStore.tasks = taskStore.tasks.filter((task) => task.ID !== ID);
      // taskStore.saveToLocalStorage();
      deleteById({ task_id: ID }).then(
        (res) => {
          ElMessage({
            type: "success",
            message: "删除成功",
          });
          getList().then((res) => {
            data_list.arr = res.data;
          });
        },
        (err) => {
          ElMessage({
            type: "error",
            message: "删除失败：" + err.response.data.error,
          });
        }
      );
    })
    .catch(() => {
      ElMessage({
        type: "info",
        message: "取消删除",
      });
    });
};

const testCardOption = ref([
  { value: 1, label: "索引续测" },
  { value: 0, label: "内容续测" },
]);

// 数据集参数配置弹窗相关
const datasetConfigDialogVisible = ref(false);
const editableDatasetArgs = ref([]);

// ============================================================
// 记忆业务子表 & 改写业务参数（续测时随任务配置提交给后端）
// 结构与 dataSetSelectForm.vue / startEvaluationForm.vue 保持一致
// ============================================================

// 判断某条 dataset_args 是否为“记忆”业务
const isMemoryDataset = (item) =>
  !!item &&
  (item.isMemory === true ||
    (Array.isArray(item.testcase_tags) && item.testcase_tags.includes("记忆")));

// 改写业务参数键名与默认值（默认值取自 startEvaluationForm.vue）
const rewriteParamKeys = [
  "enable_fewshot",
  "enable_fixed_fewshot",
  "fewshot_retrieval_mode",
  "fewshot_example_field",
  "fewshot_top_k",
  "fewshot_score_threshold",
  "max_fewshot_examples",
  "max_context_turns",
];
const rewriteDefaults = {
  enable_fewshot: true,
  enable_fixed_fewshot: true,
  fewshot_retrieval_mode: "query",
  fewshot_example_field: "no_thought_example",
  fewshot_top_k: 5,
  fewshot_score_threshold: 0.61,
  max_fewshot_examples: 5,
  max_context_turns: 5,
};
const rewriteFormData = ref({});

// 所选测试集中是否包含“改写”业务（用于控制改写参数区块显隐）
const isRewriteSelected = computed(() => {
  return editableDatasetArgs.value.some(
    (item) =>
      Array.isArray(item.testcase_tags) && item.testcase_tags.includes("改写")
  );
});

// 从原任务（currentRow.generate_config）读取改写参数，无则回退默认值
const initRewriteFormData = () => {
  let stored = {};
  const raw = currentRow.value.generate_config;
  if (raw && typeof raw === "object") {
    stored = raw;
  } else if (typeof raw === "string" && raw.trim() !== "") {
    try {
      stored = JSON.parse(raw);
    } catch (e) {
      stored = {};
    }
  }
  const result = {};
  rewriteParamKeys.forEach((key) => {
    result[key] = stored[key] !== undefined ? stored[key] : rewriteDefaults[key];
  });
  rewriteFormData.value = result;
};

const openDatasetConfigDialog = () => {
  // 根据用户选择的测试集过滤 dataset_args
  const filteredArgs = currentRow.value.dataset_args.filter((item) =>
    datasets.value.includes(item.dataset_name)
  );
  if (filteredArgs.length === 0) {
    ElMessage({
      type: "warning",
      message: "请先选择至少一个测试集",
    });
    return;
  }
  // 深拷贝一份供编辑，避免影响原始数据；记忆测试集兜底 memoryBusinessParams 为数组
  editableDatasetArgs.value = filteredArgs.map((item) => ({
    ...item,
    generate_config: item.generate_config || "",
    eval_batch_size: item.eval_batch_size ?? 1,
    memoryBusinessParams: isMemoryDataset(item)
      ? Array.isArray(item.memoryBusinessParams)
        ? item.memoryBusinessParams
        : []
      : item.memoryBusinessParams,
  }));
  // 初始化改写业务参数（优先读取原任务已有值）
  initRewriteFormData();
  // 关闭上一个弹窗，打开配置弹窗
  refreshDialogVisible.value = false;
  datasetConfigDialogVisible.value = true;
};

const confirmDatasetConfig = () => {
  // 校验 generate_config 是否为合法的 JSON 字符串
  for (const item of editableDatasetArgs.value) {
    if (item.generate_config && item.generate_config.trim() !== "") {
      try {
        JSON.parse(item.generate_config);
      } catch (e) {
        ElMessage({
          type: "error",
          message: `数据集 "${item.dataset_name}" 的 generate_config 不是合法的 JSON 字符串，请检查`,
        });
        return;
      }
    }
  }
  // 将修改后的参数写回 currentRow（含记忆子表的 memoryBusinessParams）
  currentRow.value.dataset_args = editableDatasetArgs.value.map((item) => ({ ...item }));
  // 将改写业务参数写回 currentRow.generate_config（仅当所选测试集包含“改写”）
  if (isRewriteSelected.value) {
    currentRow.value.generate_config = {
      ...(currentRow.value.generate_config || {}),
      ...rewriteFormData.value,
    };
  }
  datasetConfigDialogVisible.value = false;
  // 执行重新测评
  reStartEvaluate();
};

const handleRadioChange = (value) => {
  console.log("当前选中项:", value);
};

//  只有下载评测文件的时候赋值使用
const curAssessmentType = ref("");
const curEvaluationType = ref("");

const downloadData = (row) => {
  curAssessmentType.value = row.assessmentType;
  curEvaluationType.value = row.taskConfig.evaluationType;
  downloadDialogVisible.value = true;
  downloadDialogType.value = row.assessmentType;
  let le;
  if (row.status === "running") {
    le = row.result[row.model_name]
      .filter((item) => item.progress !== 0)
      .map((map) => map.dataset_name);
  } else if (
    !INTERPRETATIONS_TYPES.some((item) => row.assessmentType === item)
  ) {
    le = row.result[row.model_name].map((map) => map.dataset_name);
  }
  if (le && le.length === 0) {
    datasetsWithAll.value = [];
  } else if (INTERPRETATIONS_TYPES.includes(row.assessmentType)) {
    datasetsWithAll.value = ["all"];
  } else {
    if (downloadDialogType.value !== "AISF发布评估") {
      datasetsWithAll.value = ["all", ...le];
    } else {
      datasetsWithAll.value = [...le];
    }
  }
  downloadDatasetID.value = row.ID;
  downloadSelectData.value = [];
};

const downLoadReportData = ref({
  id: "",
  creator: "",
  createTime: "",
  modelName: "",
  // versionName: "CloudCore Digital Evaluation Platform",
  modelDesc: "",
  series: "",
  vendor: "",
  tags: [],
  category: [],
  size: 0,
  contextLength: 0,
  createdDate: "",
  dataSetInfo: [],
  // sunsets:
  // {
  //   name:'',
  //   size:'',
  //   score:'',
  //   runningTime:'',
  // }
});

const flattenObjects = (array) => {
  console.log("array");
  console.log(array);
  if (!Array.isArray(array)) {
    console.error("传入的参数不是数组1");
    return array;
  }

  const result = [];

  for (let i = 0; i < array.length; i++) {
    const obj = array[i];
    // if (!Array.isArray(obj)) {
    //   console.error("传入的参数不是数组2");
    //   return array;
    // }
    // 将对象的每个属性值添加到结果数组中
    Object.keys(obj).forEach((key) => {
      result.push(obj[key]);
    });
  }

  return result;
};

const handelDownLoadReport = async (row) => {
  console.log("下载评测报告！！！");
  console.log(row);
  downLoadReportData.value.dataSetInfo = [];
  const modelInfo = await ModelService.getOneModelInfo(row.model_id);
  let dataSetInfo = {};
  if (row.assessmentType === "通用评估(Ruler1)") {
    const dataSetResponse = await get_datasets("1");
    dataSetInfo = dataSetResponse.data;

    const dataSetNames = Object.keys(dataSetInfo).filter((dataSet) => {
      return row.datasets.includes(dataSet);
    });
    // console.log("dataSetNames");
    // console.log(dataSetNames);

    dataSetNames.forEach((dataSetName) => {
      // console.log("subset_list");
      // console.log(dataSetInfo[dataSetName].subset_list);
      // let subsets = [];
      // dataSetInfo[dataSetName].subset_list.forEach((subSet) => {
      //   subsets.push({
      //     name: subSet,
      //   });
      // });

      let categories = [];

      row.result[row.model_name].forEach((item) => {
        if (item.dataset_name === dataSetName) {
          categories = item.metrics[0].categories;
        }
      });

      // console.log("result");
      // console.log(categories);
      let subsets = categories.reduce((acc, cur, index) => {
        // 将当前元素的 subsets 数组添加到累加器 acc 中
        return acc.concat({
          ...cur.subsets,
        });
      }, []);

      if (subsets.length > 0) {
        subsets = flattenObjects(subsets);
      }
      subsets.forEach((item, index, arr) => {
        item.isLast = index === arr.length - 1;
      });
      console.log("subsets");
      console.log(subsets);

      subsets = subsets.length === 0 ? ["default"] : subsets;
      downLoadReportData.value.dataSetInfo.push({
        dataSetName: dataSetName,
        desc: dataSetInfo[dataSetName].description,
        subSets: subsets.map((item, index) => {
          if (index < subsets.length - 1) {
            // item.name += ",";
            return item;
          } else {
            return item;
          }
        }),
      });
    });
    // console.log("dataSetNames");
    // console.log(dataSetNames);
  } else if (row.assessmentType === "领域评估(Ruler2)") {
    const dataSetResponse = await get_datasets("2");
    dataSetInfo = dataSetResponse.data;

    const dataSetNames = Object.keys(dataSetInfo).filter((dataSet) => {
      return row.datasets.includes(dataSet);
    });

    dataSetNames.forEach((dataSetName) => {
      // console.log("subset_list");
      // console.log(dataSetInfo[dataSetName].subset_list);
      // let subsets = [];
      // dataSetInfo[dataSetName].subset_list.forEach((subSet) => {
      //   subsets.push({
      //     name: subSet,
      //   });
      // });
      let categories = [];

      row.result[row.model_name].forEach((item) => {
        if (item.dataset_name === dataSetName) {
          categories = item.metrics[0].categories;
        }
      });

      // console.log("result");
      // console.log(categories);
      let subsets = categories.reduce((acc, cur, index) => {
        // 将当前元素的 subsets 数组添加到累加器 acc 中
        return acc.concat({
          ...cur.subsets,
        });
      }, []);

      console.log("subsets");
      console.log(subsets);
      if (subsets.length > 0) {
        subsets = flattenObjects(subsets);
      }
      subsets.forEach((item, index, arr) => {
        item.isLast = index === arr.length - 1;
      });
      console.log("subsets");
      console.log(subsets);

      subsets = subsets.length === 0 ? ["default"] : subsets;
      downLoadReportData.value.dataSetInfo.push({
        dataSetName: dataSetName,
        desc: dataSetInfo[dataSetName].description,
        subSets: subsets.map((item, index) => {
          if (index < subsets.length - 1) {
            // item.name += ",";
            return item;
          } else {
            return item;
          }
        }),
      });
    });
    // console.log("dataSetNames");
    // console.log(dataSetNames);
  } else if (row.assessmentType === "AISF开发评估") {
    const requestData = {
      task_id: row.ID,
      datasets: row.datasets.join(","),
    };
    // console.log("requestData");
    // console.log(requestData);
    await downloadExcell(requestData).then(
      (res) => {
        // console.log("res");
        // console.log(res);
        res.data;
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const a = document.createElement("a");
        a.href = url;
        if (row.datasets.length > 1) {
          a.download = row.ID + ".zip";
        } else {
          a.download = row.ID + ".xlsx";
        }
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
    );
    return;
  } else if (row.assessmentType === "同声传译评估") {
    ElMessage({
      type: "warning",
      message: "同声传译暂无测试集",
    });
  } else {
    console.error("导出失败：测试集获取失败");
    alert(`文档生成失败：测试集获取失败`);
  }
  downLoadReportData.value.id = row.ID ? row.ID : "";
  downLoadReportData.value.creator = row.creator ? row.creator : "";
  if (row.createTime) {
    downLoadReportData.value.createTime = row.createTime.substring(0, 10);
  } else {
    downLoadReportData.value.createTime = "";
  }
  downLoadReportData.value.modelName = row.model_name ? row.model_name : "";
  downLoadReportData.value.modelDesc = modelInfo.info.model_desc
    ? modelInfo.info.model_desc
    : "";
  downLoadReportData.value.series = modelInfo.info.series
    ? modelInfo.info.series
    : "";
  downLoadReportData.value.vendor = modelInfo.info.vendor
    ? modelInfo.info.vendor
    : "";
  downLoadReportData.value.tags =
    modelInfo.info.tags.length > 0
      ? modelInfo.info.tags.map((item, index) => {
          if (index < modelInfo.info.tags.length - 1) {
            return item + ",";
          } else {
            return item;
          }
        })
      : [];
  downLoadReportData.value.category =
    modelInfo.info.category.length > 0
      ? modelInfo.info.category.map((item, index) => {
          if (index < modelInfo.info.category.length - 1) {
            return item + ",";
          } else {
            return item;
          }
        })
      : [];
  downLoadReportData.value.size = modelInfo.info.size ? modelInfo.info.size : 0;
  downLoadReportData.value.contextLength = modelInfo.info.context_length
    ? modelInfo.info.context_length
    : 0;
  downLoadReportData.value.createdDate = modelInfo.info.createdDate
    ? modelInfo.info.createdDate
    : "";

  console.log("downLoadReportData");
  console.log(downLoadReportData.value);
  // return;
  downLoadReport(downLoadReportData.value);
};

const downLoadReport = (reportData) => {
  console.log("开始获取模板文件...");
  fetch("/v1/templates/evaluation-report.docx")
    .then((response) => response.arrayBuffer())
    .then((arrayBuffer) => {
      console.log("文件大小:", arrayBuffer.byteLength, "bytes");

      const zip = new PizZip(arrayBuffer);
      const doc = new Docxtemplater();

      // 添加关键配置
      doc.loadZip(zip);
      doc.setOptions({
        paragraphLoop: true, // 处理跨段落文本
        linebreaks: true, // 保留换行符
      });

      // doc.setData(data);
      doc.setData(reportData);

      try {
        doc.render();
        console.log("文档渲染完成");
      } catch (error) {
        console.error("渲染错误：", error);
        // 输出详细错误信息
        if (error.properties && error.properties.errors) {
          error.properties.errors.forEach((e) => {
            console.error("模板错误:", e);
          });
        }
        throw error;
      }

      // 生成输出
      const out = doc.getZip().generate({
        type: "blob",
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });

      // 保存文件
      saveAs(out, `${reportData.id}.docx`);
    })
    .catch((error) => {
      console.error("导出失败：", error);
      alert(`文档生成失败: ${error.message}`);
    });
};

// 处理排序
const sortConfig = ref({ prop: "", order: "" });

const handleSortChange = ({ column, prop, order }) => {
  sortConfig.value = { prop, order };
};

const sortedTaskData = computed(() => {
  if (!Array.isArray(data_list.arr) || data_list.arr.length === 0) {
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
// const currentPage = ref(1);
const currentPage = computed(() => store.getters["taskTable/getPageNum"]);
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
  // currentPage.value = 1; // 切换每页数量时回到第一页
  store.dispatch("taskTable/updatePageNum", 1);
  console.log(store.getters["taskTable/getPageNum"]);
  console.log(currentPage.value);
};

// 处理页码改变
const handleCurrentChange = (val) => {
  // currentPage.value = val;
  store.dispatch("taskTable/updatePageNum", val);
  console.log(store.getters["taskTable/getPageNum"]);
  console.log(currentPage.value);
};

const data_list = reactive({
  arr: [],
});

const isinterpretation = (row) => {
  return INTERPRETATIONS_TYPES.some((item) => row.assessmentType === item);
};

const isChildStudy = (row) => {
  if (
    !row.datasets ||
    row.datasets.length === 0 ||
    !row.taskConfig.dataset_args
  ) {
    return false;
  }

  for (const dataset of row.taskConfig.dataset_args) {
    if (!dataset || !dataset.testcase_tags?.includes("儿童伴读")) {
      return false;
    }
  }
  return true;
};

const isYitu = (row)=>{
  if (
    !row.datasets ||
    row.datasets.length === 0 ||
    !row.taskConfig.dataset_args
  ) {
    return false;
  }

  for (const dataset of row.taskConfig.dataset_args) {
    if (!dataset || !dataset.testcase_tags?.includes("意图")) {
      return false;
    }
  }
  return true;
}

const upLoadTaskId = ref();
const uploadTask = ref();
const dialogVisible = ref(false);
const updateMOS = (row) => {
  console.log("row");
  console.log(row);
  upLoadTaskId.value = row.ID;
  dialogVisible.value = true;
};
const uploadFile = async (file) => {
  const isLt2M = file.file.size / 1024 / 1024 < 10;
  if (!isLt2M) {
    ElMessage.error("上传文件大小不能超过 10MB!");
    upload.value!.clearFiles();
  } else {
    const formData = new FormData();
    formData.append("task_id", upLoadTaskId.value);
    formData.append("file", file.file);

    if (!isChildStudy(uploadTask.value)) {
      try {
        const response = await uploadMOSFile(formData);
        console.log("上传成功:", response.data);
      } catch (error) {
        console.error("上传失败:", error);
      }
    } else {
      formData.append("dataset_name", uploadTask.value.datasets[0]);
      try {
        const response = await uploadTestResult(formData);
        console.log("上传成功:", response.data);
      } catch (error) {
        console.error("上传失败:", error);
      }
    }
  }
  upLoadTaskId.value = "";
};
const handleSuccess = (response, file, fileList) => {
  ElMessage.success("文件上传成功");
  console.log("文件上传成功", response, file, fileList);
};

const handleError = (error, file, fileList) => {
  ElMessage.error("文件上传失败");
  console.log("文件上传失败", error, file, fileList);
};

const handleConfirm = () => {
  ElMessage.success("确认上传");
  dialogVisible.value = false;
};

const upload = ref<UploadInstance>();
const handleExceed: UploadProps["onExceed"] = (files) => {
  upload.value!.clearFiles();
  const file = files[0] as UploadRawFile;
  file.uid = genFileId();
  upload.value!.handleStart(file);
};
const handleClose = () => {
  upload.value!.clearFiles();
  upLoadTaskId.value = "";
  dialogVisible.value = false;
};

const excelDialogVisible = ref(false);

const submitExcel = (row) => {
  console.log("row");
  console.log(row);
  uploadTask.value = row;
  upLoadTaskId.value = row.ID;
  excelDialogVisible.value = true;
};

const handleExcelDialogClose = () => {
  upload.value!.clearFiles();
  uploadTask.value = null;
  upLoadTaskId.value = "";
  excelDialogVisible.value = false;
};

const loading = ref(true);
const username = ref("");

const getTasksList = () => {
  getList().then((res) => {
    data_list.arr = res.data;
    taskStore.setTasks(res.data);
    loading.value = false;
    loadFilter();
  });
};

let pollTimer = null;

const startPolling = () => {
  stopPolling();
  pollTimer = setInterval(() => {
    getList().then((res) => {
      // 只更新表格数据，不重置分页、筛选、排序、dialog 等任何 UI 状态
      data_list.arr = res.data;
      taskStore.setTasks(res.data);
      // 静默更新筛选下拉选项，不影响用户已选的筛选条件
      loadFilter();
    });
  }, 15000);
};

const stopPolling = () => {
  if (pollTimer !== null) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

onMounted(() => {
  token.value = localStorage.getItem('username');
  username.value = localStorage.getItem("username");
  if (testCardOption.value.length > 0) {
    selectedOption.value = testCardOption.value[0].value;
  }

  getTasksList();
  startPolling();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<style>
.custom-width {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.titleContainer {
  display: flex;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  line-height: 36px;
  height: 36px;
  margin-bottom: 0px !important;
}

.titleContainer span:nth-child(-n + 2) {
  color: #969696;
}

.title {
  display: inline-block;
  font-size: 16px;
  font-weight: 600;
  color: rgba(18, 19, 22, 0.8);
}

.createTaskbtn {
  margin-left: auto;
  display: flex;
  background-color: #0067d1;
  color: white;
  border: none;
  box-shadow: none;
  height: 100%;
  padding: 0 14px;
  font-size: 14px;
}

.createTaskbtn:hover {
  background-color: #008cd4 !important;
  color: white;
}

.createTaskbtn:active {
  background-color: #0067d1 !important;
  color: white;
}

.TaskInfoTable {
  font-size: medium;
}

.TaskInfoTable .el-table__row {
  height: 4rem;
}

.option-container {
  display: flex;
  justify-content: space-between;
  margin: 0px 40px;
  gap: 40px;
}

.option {
  width: 400px;
  height: 400px;
  background-color: white;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  cursor: pointer;
  padding: 20px;
  border: solid gray 1px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.option.selected {
  border-color: rgb(61, 147, 228);
  background-color: #d8ebff;
}

.option:hover {
  background-color: #d8ebff;
}

.option .title {
  margin-bottom: 10px;
  font-size: 22px;
  color: blue;
}

.option .descriptions {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  font-size: 16px !important;
}

.option .descriptions .el-icon {
  margin-right: 8px;
}

.pagination {
  display: flex;
  justify-content: space-between;
  /* 让“总计”靠左，分页控件靠右 */
  align-items: center;
  margin-top: 16px;
}

.total-text {
  color: #666;
  /* 根据页面风格自定义颜色 */
  font-size: 16px;
}

.logContent {
  white-space: pre-wrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.progressValueOk {
  cursor: pointer;
  margin-left: 10px;
  color: #05af12;
  text-decoration: underline;
  width: 53px;
}

.progressValueNotOk {
  cursor: pointer;
  margin-left: 10px;
  color: #0087ff;
  text-decoration: underline;
  width: 53px;
}

/* 记忆子业务编辑表（与 dataSetSelectForm.vue 保持一致） */
.memory-sub-table {
  border: 1px solid rgb(221, 221, 221);
  border-radius: 5px;
  margin-top: 4px;
}
</style>
