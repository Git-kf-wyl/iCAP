<template>
  <div class="task-detail">
    <div class="datasetRegistTitleContainer">
      <span style="padding: 0 14px"></span>
      <!-- <el-icon @click="goBack" style="cursor: pointer;">
        <Back />
      </el-icon>
      <span @click="goBack" style="color:rgba(18, 19, 22, 0.8);cursor: pointer;">返回</span> -->
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:28px;">
      <span style="padding: 0 20px"></span>
      <span @click="goBack" style="color: #969696;cursor: pointer;">数据集开发</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>
      <span v-if="is_register" style="font-size:18px;font-weight:600;">修改测试集</span>
      <span v-else style="font-size:18px;font-weight:600;">注册测试集</span>
    </div>

    <div class="task-info">
      <div class="card model-info-card">
        <h1 class="card-title" v-if="is_register">修改测试集</h1>
        <h1 class="card-title" v-else >注册测试集</h1>

        <div class="card-container">
          <div class="card question-table-card">
            <p class="card-title"></p>
            <div class="input_line">
              <span class="input_title">Dataset_name:</span>
              <el-input class="el_input" v-model="form.dataset_name" placeholder="示例：mmlu" style />
            </div>
            <div class="input_line">
              <span class="input_title">Dataset_id:</span>
              <el-input
                class="el_input"
                v-model="form.dataset_id"
                placeholder="示例： aisf_mmlu"
                style
                :disabled="is_register"
              />
            </div>

          <!-- 发布状态 -->
            <div class="input_line">
              <span class="input_title">可见范围:</span>
              <el-switch v-model="form.is_published" active-text="对所有用户开放" inactive-text="仅自己可见" />
              <el-tooltip content="发布后所有人均可查看测试集详情" placement="top">
                <span class="help-icon">?</span>
              </el-tooltip>
            </div>
            <!-- 使用状态 -->
            <div class="input_line">
              <span class="input_title">使用状态:</span>
              <el-switch v-model="form.in_use" active-text="使用中" inactive-text="未使用" style="--el-switch-on-color: #67c23a" />
              <el-tooltip content="标记该测试集当前是否正在使用，使用中的测试集会带有“使用中”标识" placement="top">
                <span class="help-icon">?</span>
              </el-tooltip>
            </div>
            <div class="input_line">
              <span class="input_title">Few_Shot_Num:</span>
              <el-input-number v-model="form.few_shot_num" :min="0" :max="16"></el-input-number>
            </div>
            <div class="input_line">
              <span class="input_title">Is_Open_Source:</span>
              <el-radio v-model="form.is_open_source" :label="true">是</el-radio>
              <el-radio v-model="form.is_open_source" :label="false">否</el-radio>
            </div>
            <div class="input_line">
              <span class="input_title">Need_LLMJudge:</span>
              <el-radio v-model="form.need_llmjudge" :label="true">是</el-radio>
              <el-radio v-model="form.need_llmjudge" :label="false">否</el-radio>
            </div>
            <div class="input_line">
              <span class="input_title">Description:</span>
              <el-input
                class="el_input"
                v-model="form.description"
                placeholder="示例： aisf_mmlu"
                style
              />
            </div>
            <div class="input_line">
              <span class="input_title">Tags:</span>
              <el-cascader
                v-model="selectedTag"
                :options="cascaderTags"
                :props="cascaderProps"
                :show-all-levels="false"
                clearable
                placeholder="请选择"
                class="el_input"
                @change="onTagsChange"
                style="flex: 0 0 50%;"
              />
            </div>

            <!-- 记忆模式：子业务表格 -->
           <template v-if="isMemoryMode">
              <div class="memory-table-container">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                  <span style="font-weight:bold;">子业务列表（可填写默认测评参数）</span>
                  <el-button type="primary" size="small" @click="addMemoryRow">添加业务</el-button>
                </div>
                <el-table :data="memoryRows" border style="width:100%;" max-height="1000">
                  <el-table-column label="业务名称" min-width="180">
                    <template #default="{ row, $index }">
                      <el-input v-model="row.name" placeholder="请输入业务名称" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="prompt_version" min-width="140">
                    <template #default="{ row }">
                      <el-input v-model="row.prompt_version" placeholder="默认值" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="eval_type" min-width="140">
                    <template #default="{ row }">
                      <el-input v-model="row.eval_type" placeholder="默认值" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="use_fewshot" min-width="120">
                    <template #default="{ row }">
                      <el-select v-model="row.use_fewshot" placeholder="默认值" size="small">
                        <el-option label="true" :value="true" />
                        <el-option label="false" :value="false" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="裁判prompt" min-width="140">
                    <template #default="{ row }">
                      <el-input type="textarea"  v-model="row.judge_prompt" placeholder="judge_prompt" size="small" />
                    </template>
                  </el-table-column>
                  <el-table-column label="Prompt文件 (.txt)" min-width="260">
                    <template #default="{ row }">
                      <div style="display:flex;flex-direction:column;gap:4px;">
                        <div v-for="(pf, idx) in (row.promptFileList || [])" :key="idx"
                          style="display:flex;align-items:center;gap:4px;">
                          <span v-if="pf.status === 'uploading'" class="file-status-icon uploading" />
                          <span v-else-if="pf.status === 'success'" class="file-status-icon success">&#10003;</span>
                          <span
                            style="font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{
                            pf.name }}</span>
                          <el-button v-if="pf.status === 'success'" size="small" type="danger" link
                            @click="removeMemoryFile(row, 'prompt', idx)"><el-icon>
                              <Delete />
                            </el-icon></el-button>
                        </div>
                        <el-upload :auto-upload="true" action=""
                          :http-request="(opts) => uploadMemoryFile(row, 'prompt', opts)" :on-change="() => false"
                          :show-file-list="false" accept=".txt">
                          <el-button size="small" type="primary">上传文件</el-button>
                          <template #tip>
                            <div class="el-upload__tip">仅支持 .txt</div>
                          </template>
                        </el-upload>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="测试集文件 (.xlsx)" min-width="260">
                    <template #default="{ row }">
                      <div style="display:flex;flex-direction:column;gap:4px;">
                        <div v-for="(tf, idx) in (row.testFileList || [])" :key="idx"
                          style="display:flex;align-items:center;gap:4px;">
                          <span v-if="tf.status === 'uploading'" class="file-status-icon uploading" />
                          <span v-else-if="tf.status === 'success'" class="file-status-icon success">&#10003;</span>
                          <span
                            style="font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{
                            tf.name }}</span>
                          <el-button v-if="tf.status === 'success'" size="small" type="danger" link
                            @click="removeMemoryFile(row, 'test', idx)"><el-icon>
                              <Delete />
                            </el-icon></el-button>
                        </div>
                        <el-upload :auto-upload="true" action=""
                          :http-request="(opts) => uploadMemoryFile(row, 'test', opts)" :on-change="() => false"
                          :show-file-list="false" accept=".xlsx">
                          <el-button size="small" type="primary">上传文件</el-button>
                          <template #tip>
                            <div class="el-upload__tip">仅支持 .xlsx</div>
                          </template>
                        </el-upload>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="100">
                    <template #default="{ $index }">
                      <el-button type="danger" size="small" @click="removeMemoryRow($index)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </template>
            
            <template v-if="!isMemoryMode">
            <div class="input_line">
              <span class="input_title">All_Subsets:</span>
              <el-input
                class="el_input"
                v-model="subset_list"
                placeholder="所有可选子集，多个用逗号分隔,示例: level1,level2"
                style
              />
            </div>
            <div class="input_line">
              <span class="input_title">Default_Subset:</span>
              <el-input
                class="el_input"
                v-model="default_subsets"
                placeholder="运行时默认子集,多个用逗号分隔,示例: level1"
                style
              />
            </div>
            <div class="input_line">
              <span class="input_title">DataSet_Cases:</span>
              <el-input
                class="el_input"
                v-model="form.dataSet_cases"
                placeholder="请输入测试集用例数量"
                style
              />
            </div>
            <div class="input_line">
              <span class="input_title">Metric_list:</span>
              <el-select
                v-model="form.metric_list"
                multiple
                clearable
                placeholder="请选择"
                class="el_input"
              >
                <el-option v-for="item in metricOptions" :key="item" :label="item" :value="item" />
              </el-select>
            </div>
            <div class="input_line">
              <span class="input_title">Default_System_Prompt:</span>
              <el-input
                class="el_input"
                type="textarea"
                v-model="form.system_prompt"
                style
              />
            </div>
            <div class="input_line">
              <span class="input_title">Default_User_Prompt:</span>
              <el-input
                class="el_input"
                type="textarea"
                v-model="form.user_prompt"
                style
              />
            </div>
            <div class="input_line">
              <span class="input_title">Few_shot_file:</span>
              <el-upload
                class="upload-demo"
                :file-list="few_files"
                drag
                :auto-upload="true"
                action=""
                :http-request="fewUploadFile"
                multiple
                :on-change="fewOnChangeFile"
                :before-remove="fewBeforeRemove"
                :on-remove="fewOnRemoveFile"
                style="width: 100%"
              >
                <i class="el-icon-upload"></i>
                <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
                <div class="el-upload__tip" slot="tip">支持xlsx,json,csv等多种格式</div>
              </el-upload>
            </div>
            <div class="input_line">
              <span class="input_title">File:</span>
              <el-upload
                class="upload-demo"
                :file-list="files"
                drag
                :auto-upload="true"
                action=""
                :http-request="uploadFile"
                multiple
                :on-change="onChangeFile"
                :before-remove="beforeRemove"
                :on-remove="onRemoveFile"
                style="width: 100%"
              >
                <i class="el-icon-upload"></i>
                <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
                <div class="el-upload__tip" slot="tip">支持xlsx,json,csv等多种格式</div>
              </el-upload>
            </div>
            </template>
            <div class="input_line">
              <el-button type="primary" v-if="is_register" @click="datasetEdit">修改</el-button>
              <el-button type="primary" v-else @click="datasetRegister">注册</el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref, onMounted, inject } from "vue";
import { Delete } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";
import { save_datasets, edit_datasets, upload_file } from "@/api/dataSetApi";
import { ElMessage, ElMessageBox } from "element-plus";
import { manager_list } from "@/consts/copyrightConsts.js";
import { compileScript } from "vue/compiler-sfc";
import { ComponentModel } from "echarts";

const route = useRoute();
const router = useRouter();
const query = route.query;
const few_files = ref([]);
const files = ref([]);
const up_few_files = ref([]);
const up_files = ref([]);
const subset_list = ref("");
const default_subsets = ref("");
const metric_list = ref("");
const currentUsername = localStorage.getItem("username") || "";
const system_prompt=ref("")
const is_register = ref(false);
const form = reactive({
  dataset_name: "",
  dataset_id: "",
  subset_list: [],
  metric_list: [],
  default_subsets: [],
  dataSet_cases:"",
  few_shot_num: "",
  testcase_tags: [],
  description: "",
  is_open_source: true,
  content: "",
  need_llmjudge: false,
  file_list: [],
  few_file_list: [],
  system_prompt:"",
  user_prompt:"",
  is_published: false,
  in_use: true,
  viewer_users: [],
  download_users:[],
  editor_users: (currentUsername && !manager_list.includes(currentUsername)) ? [currentUsername] : [],
});
// 记忆模式相关
const isMemoryMode = ref(false);
const memoryRows = ref([]);
// 级联选择器的中间值：选中时是 ["文本", "意图"]，最终提交时只保留最后一级
const selectedTag = ref([]);

const onTagsChange = (val) => {
  // val 是 ["文本", "意图"] 或 null（清除时）
  if (val && val.length > 0) {
    // 提交时只需要最后一级的标签值
    form.testcase_tags = [val[val.length - 1]];
  } else {
    form.testcase_tags = [];
  }
  // 判断是否包含"记忆"标签，展开子业务表格
  isMemoryMode.value = form.testcase_tags.includes("记忆");
  // 非记忆模式时清空子业务列表
  if (!isMemoryMode.value) {
    memoryRows.value = [];
  }
};

const addMemoryRow = () => {
  memoryRows.value.push({
    name: "",
    prompt_version: "",
    eval_type: "",
    judge_prompt:"",
    use_fewshot: false,
    promptFileList: [],
    testFileList: [],
    promptFileNames: [],
    testFileNames: [],
  });
};

const removeMemoryRow = (index) => {
  memoryRows.value.splice(index, 1);
};

const uploadMemoryFile = async (row, type, file) => {
  const formData = new FormData();
  formData.append("file", file.file);
  // 先添加一条"上传中"的记录
  const tempIndex = type === "prompt" ? (row.promptFileList || []).length : (row.testFileList || []).length;
  const tempItem = { name: file.file.name, url: "", status: "uploading" };
  if (type === "prompt") {
    if (!row.promptFileList) row.promptFileList = [];
    row.promptFileList.push({ ...tempItem });
  } else {
    if (!row.testFileList) row.testFileList = [];
    row.testFileList.push({ ...tempItem });
  }
  await upload_file(formData).then((res) => {
    const filename = res.data.filename;
    if (type === "prompt") {
      if (!row.promptFileNames) row.promptFileNames = [];
      row.promptFileNames.push(filename);
      if (row.promptFileList[tempIndex]) {
        row.promptFileList[tempIndex].url = filename;
        row.promptFileList[tempIndex].status = "success";
      }
    } else {
      if (!row.testFileNames) row.testFileNames = [];
      row.testFileNames.push(filename);
      if (row.testFileList[tempIndex]) {
        row.testFileList[tempIndex].url = filename;
        row.testFileList[tempIndex].status = "success";
      }
    }
  }).catch(() => {
    // 上传失败移除该记录
    if (type === "prompt") {
      row.promptFileList.splice(tempIndex, 1);
    } else {
      row.testFileList.splice(tempIndex, 1);
    }
  });
};

const removeMemoryFile = (row, type, index) => {
  if (type === "prompt") {
    if (index !== undefined && index !== null) {
      row.promptFileNames.splice(index, 1);
      row.promptFileList.splice(index, 1);
    } else {
      row.promptFileNames = [];
      row.promptFileList = [];
    }
  } else {
    if (index !== undefined && index !== null) {
      row.testFileNames.splice(index, 1);
      row.testFileList.splice(index, 1);
    } else {
      row.testFileNames = [];
      row.testFileList = [];
    }
  }
  return true;
};

const metricOptions = ref([
  "AverageAccuracy",
  "AveragePass@1",
  "Pass@1",
  "Pass@2",
  "Pass@3",
  "Pass@4",
  "Pass@5",
  "Pass@6",
  "Pass@7",
  "Pass@8",
  "Pass@9",
  "Pass@10",
  "Pass@11",
  "Pass@12",
  "Pass@13",
  "Pass@14",
  "Pass@15",
  "Pass@16",
]);
const response = ref({});
const activeTab = ref("");

const fewOnChangeFile = (file, fileList) => {};

const fewOnRemoveFile = (file, fileList) => {
  up_few_files.value = up_few_files.value.filter((item) => !item.includes(file.name));
};

const onChangeFile = (file, fileList) => {};

const onRemoveFile = (file, fileList) => {
  up_files.value = up_files.value.filter((item) => !item.includes(file.name));
};

const fewUploadFile = async (file) => {
  const formData = new FormData();
  formData.append("file", file.file);
  await upload_file(formData).then((res) => {
    up_few_files.value.push(res.data.filename);
  });
};

const uploadFile = async (file) => {
  const formData = new FormData();
  formData.append("file", file.file);
  await upload_file(formData).then((res) => {
    up_files.value.push(res.data.filename);
  });
};

onMounted(() => {
  const query = route.query;
  if (query.type) {
    activeTab.value = query.type;
    if (activeTab.value === "openSource") {
      tags.value = commonTags.value;
    } else if (activeTab.value === "domain") {
      tags.value = domainTags.value;
    } else if (activeTab.value === "dev") {
      tags.value = domainTags.value;
    }
    syncCascaderTags();
  }
  if (query.id) {
    is_register.value = true;
    const jso = JSON.parse(query.value);
    Object.assign(form, jso);
    // 兼容旧数据：扁平数组、旧级联格式，转为可用格式
    if (jso.testcase_tags && jso.testcase_tags.length > 0) {
      if (typeof jso.testcase_tags[0] === "string") {
        // 旧数据：["意图"] => 查找所属父级，构建完整级联路径
        form.testcase_tags = jso.testcase_tags.map((tag) => {
          for (const group of tags.value) {
            if (group.options.some((opt) => opt.value === tag)) {
              return [group.label, tag];
            }
          }
          return [tag];
        });
      } else if (Array.isArray(jso.testcase_tags[0])) {
        // 旧级联格式 [["文本","意图"]] 或 [["意图"]]，补齐完整路径
        form.testcase_tags = jso.testcase_tags.map((item) => {
          if (item.length === 1) {
            const tag = item[0];
            for (const group of tags.value) {
              if (group.options.some((opt) => opt.value === tag)) {
                return [group.label, tag];
              }
            }
          }
          return item;
        });
      }
      // 同步 selectedTag 用于级联选择器回显（取第一条路径）
      if (form.testcase_tags.length > 0) {
        selectedTag.value = [...form.testcase_tags[0]];
      }
      // 内部只保留最后一级用于提交，确保一维数组 ["意图"]
      form.testcase_tags = form.testcase_tags.map((item) => item[item.length - 1]);
      // 判断是否记忆模式
      if (form.testcase_tags.includes("记忆")) {
        isMemoryMode.value = true;
      }
    }
    if (jso.subset_list) {
      subset_list.value = jso.subset_list.join(",");
    }
    if (jso.metric_list) {
      metric_list.value = jso.metric_list.join(",");
    }
    if (jso.default_subsets) {
      default_subsets.value = jso.default_subsets.join(",");
    }
    form.dataset_id = query.id;
    if (jso.file_list && jso.file_list.length > 0) {
      files.value = jso.file_list.map((item) => {
        return { name: item.split("\\").pop(0).split("/").pop(0), url: "xxx" };
      });
    }
    if (jso.few_file_list && jso.few_file_list.length > 0) {
      few_files.value = jso.few_file_list.map((item) => {
        return { name: item.split("\\").pop(0).split("/").pop(0), url: "xxx" };
      });
    }
    up_few_files.value = jso.few_file_list;
    up_files.value = jso.file_list;
    // 记忆模式：恢复子业务列表
    if (jso.memory_business_list) {
      isMemoryMode.value = true;
      memoryRows.value = jso.memory_business_list.map((item) => ({
        name: item.name,
        prompt_version: item.prompt_version || "",
        eval_type: item.eval_type || "",
        judge_prompt:item.judge_prompt || "",
        use_fewshot: item.use_fewshot ?? false,
        promptFileNames: item.prompt_file ? (Array.isArray(item.prompt_file) ? [...item.prompt_file] : [item.prompt_file]) : [],
        testFileNames: item.test_file ? (Array.isArray(item.test_file) ? [...item.test_file] : [item.test_file]) : [],
        promptFileList: item.prompt_file ? (Array.isArray(item.prompt_file) ? item.prompt_file.map(f => ({ name: f.split("/").pop().split("\\").pop(), url: f, status: "success" })) : [{ name: item.prompt_file.split("/").pop().split("\\").pop(), url: item.prompt_file, status: "success" }]) : [],
        testFileList: item.test_file ? (Array.isArray(item.test_file) ? item.test_file.map(f => ({ name: f.split("/").pop().split("\\").pop(), url: f, status: "success" })) : [{ name: item.test_file.split("/").pop().split("\\").pop(), url: item.test_file, status: "success" }]) : [],
      }));
    }
  }
});

const tags = ref([]);

// 级联选择器配置：hover 展开
const cascaderProps = {
  expandTrigger: "hover",
  // multiple: true,
  // emitPath: true,
  value: "value",
  label: "label",
  children: "children",
};

// 将 commonTags/domainTags 转换为 el-cascader 所需的格式（value + children）
const toCascaderOptions = (groups) =>
  groups.map((group) => ({
    value: group.label,
    label: group.label,
    children: group.options.map((opt) => ({
      value: opt.value,
      label: opt.label,
    })),
  }));

const cascaderTags = ref([]);

// 监听 tags 变化，同步 cascaderTags
const syncCascaderTags = () => {
  cascaderTags.value = toCascaderOptions(tags.value);
};

const domainTags = ref([
  {
    label: "文本",
    options: [
      {
        value: "改写",
        label: "改写",
      },
      {
        value: "意图",
        label: "意图",
      },
      {
        value: "记忆",
        label: "记忆",
      },
      {
        value: "skill提参",
        label: "skill提参",
      },
      {
        value: "GUI提参",
        label: "GUI提参",
      },
      {
        value: "伴学提参",
        label: "伴学提参",
      },
      {
        value: "Coordinator",
        label: "Coordinator",
      },
    ],
  },
  {
    label: "图像",
    options: [
      {
        value: "儿童伴读",
        label: "儿童伴读",
      }
    ],
  },
]);

const commonTags = ref([
    {
        label: "文本",
        options: [
            {
                value: "知识百科",
                label: "知识百科",
            },
            {
                value: "逻辑推理",
                label: "逻辑推理",
            },
            {
                value: "数学",
                label: "数学",
            },
            {
                value: "代码",
                label: "代码",
            },
            {
                value: "工具",
                label: "工具",
            },
            {
                value: "指令遵从",
                label: "指令遵从",
            },
            {
                value: "长文本",
                label: "长文本",
            },
            {
                value: "Agent",
                label: "Agent",
            },
        ],
    },
    {
        label: "图像",
        options: [
            // {
            //     value: "百科知识",
            //     label: "百科知识",
            // },
            // {
            //     value: "图片推理",
            //     label: "图片推理",
            // },
            // {
            //     value: "OCR",
            //     label: "OCR",
            // },
            // {
            //     value: "空间理解",
            //     label: "空间理解",
            // },
            // {
            //     value: "GUI",
            //     label: "GUI",
            // },
      {
        value: "图像理解",
        label: "图像理解",
      },
      {
        value: "图像推理",
        label: "图像推理",
      },
        ],
    },
    {
        label: "音频",
        options: [
            {
                value: "语音识别",
                label: "语音识别",
            },
            // {
            //     value: "语音翻译",
            //     label: "语音翻译",
            // },
            // {
            //     value: "情绪感知",
            //     label: "情绪感知",
            // },
            {
                value: "音频理解",
                label: "音频理解",
            },
            {
                value: "音频推理",
                label: "音频推理",
            },
        ],
    },
    {
        label: "视频",
        options: [
            {
                value: "视频理解",
                label: "视频理解",
            },
            // {
            //     value: "多模态理解",
            //     label: "多模态理解",
            // },
            // {
            //     value: "多模态推理",
            //     label: "多模态推理",
            // },
        ],
    },
]);

const goBack = () => {
  router.push( {name: 'evalDatasetDevelopment', query: {type: activeTab.value}});
};

const submitBack = () => {
  router.push( {name: 'evalDatasetDevelopment', query: {type: activeTab.value, refresh: true}});
};

const datasetRegister = () => {
  if (isMemoryMode.value) {
    for (let i = 0; i < memoryRows.value.length; i++) {
      const row = memoryRows.value[i];
      if (!row.name) {
        ElMessage({ type: "error", message: `第 ${i + 1} 行请填写业务名称` });
        return;
      }
      if (!row.promptFileNames || row.promptFileNames.length === 0) {
        ElMessage({ type: "error", message: `第 ${i + 1} 行请上传Prompt文件` });
        return;
      }
      if (!row.testFileNames || row.testFileNames.length === 0) {
        ElMessage({ type: "error", message: `第 ${i + 1} 行请上传测试集文件` });
        return;
      }
    }
    form.memory_business_list = memoryRows.value.map((row) => ({
      name: row.name,
      prompt_version: row.prompt_version,
      eval_type: row.eval_type,
      judge_prompt:row.judge_prompt,
      use_fewshot: row.use_fewshot,
      prompt_file: row.promptFileNames,
      test_file: row.testFileNames,
    }));
  }
  form.register = currentUsername;
  if (form.dataset_id === "") {
    ElMessage({
      type: "error",
      message: "请输入dataset_id",
    });
    return;
  }
  // 级联选择器值扁平化：[["文本","意图"]] => ["意图"]
  // form.testcase_tags = (form.testcase_tags || []).map((item) => item[0] || item);
  if (activeTab.value === "openSource") {
    form.is_field = "1";
  } else if (activeTab.value === "domain") {
    form.is_field = "2";
  } else if (activeTab.value === "dev") {
    form.is_field = "3";
  }
  if (!isMemoryMode.value) {
    form.subset_list =
      subset_list.value.length === 0 ? [] : subset_list.value.split(",");
    form.default_subsets =
      default_subsets.value.length === 0 ? [] : default_subsets.value.split(",");
    form.few_file_list = up_few_files.value;
    form.file_list = up_files.value;
  }
  save_datasets(form).then(
    (res) => {
      ElMessage({
        type: "success",
        message: "注册成功",
      });
      submitBack();
    },
    (err) => {
      ElMessage({
        type: "error",
        message:
          "注册失败: " +
          (JSON.parse(err.request.response)["err_info"] !== undefined
            ? JSON.parse(err.request.response)["err_info"]
            : err),
      });
    }
  );
};

const datasetEdit = () => {
  if (isMemoryMode.value) {
    for (let i = 0; i < memoryRows.value.length; i++) {
      const row = memoryRows.value[i];
      if (!row.name) {
        ElMessage({ type: "error", message: `第 ${i + 1} 行请填写业务名称` });
        return;
      }
      if (!row.promptFileNames || row.promptFileNames.length === 0) {
        ElMessage({ type: "error", message: `第 ${i + 1} 行请上传Prompt文件` });
        return;
      }
      if (!row.testFileNames || row.testFileNames.length === 0) {
        ElMessage({ type: "error", message: `第 ${i + 1} 行请上传测试集文件` });
        return;
      }
    }
    form.memory_business_list = memoryRows.value.map((row) => ({
      name: row.name,
      prompt_version: row.prompt_version,
      eval_type: row.eval_type,
      judge_prompt:row.judge_prompt,
      use_fewshot: row.use_fewshot,
      prompt_file: row.promptFileNames,
      test_file: row.testFileNames,
    }));
  }
  if (activeTab.value === "openSource") {
    form.is_field = "1";
  } else if (activeTab.value === "domain") {
    form.is_field = "2";
  } else if (activeTab.value === "dev") {
    form.is_field = "3";
  }
  if (!isMemoryMode.value) {
    form.subset_list =
      subset_list.value.length === 0 ? [] : subset_list.value.split(",");
    form.default_subsets =
      default_subsets.value.length === 0 ? [] : default_subsets.value.split(",");
    form.few_file_list = up_few_files.value;
    form.file_list = up_files.value;
  }
  edit_datasets(form).then(
    (res) => {
      ElMessage({
        type: "success",
        message: "修改成功",
      });
      submitBack();
    },
    (err) => {
      ElMessage({
        type: "error",
        message: "修改失败: " + err,
      });
    }
  );
};
</script>

<style scoped>
/* 基础样式 */
.task-detail {
  padding: 0;
  background-color: #f5f5f5;
}

.el_input {
  flex: 0 0 50%;
}

.input_title {
  white-space: nowrap;
  width: 200px;
}

.input_line {
  display: flex;
  align-items: center;
  margin-top: 20px;
}

.datasetRegistTitleContainer {
  display: flex;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  margin-bottom: 18px;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin: 0 28px;
}

.card {
  background-color: #ffffff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.card-title {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 12px;
  margin-left: 16px;
}

.model-info-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.model-content p {
  margin: 0;
}

.card-container {
  display: flex;
  gap: 20px;
  width: 50%;
}

.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #dcdfe6;
  color: #fff;
  font-size: 12px;
  font-weight: bold;
  cursor: pointer;
  margin-left: 6px;
  flex-shrink: 0;
}

.help-icon:hover {
  background: #409eff;
}

.question-tag-card {
  flex: 1 1 30%;
}

.question-table-card {
  flex: 1 1 50%;
}

.problem-table {
  width: 100%;
  border-collapse: collapse;
}
.problem-table th,
.problem-table td {
  border: 1px solid #e0e0e0;
  padding: 8px;
  text-align: center;
}
.problem-table th {
  background-color: #f5f5f5;
}

.memory-table-container {
  margin-top: 20px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.file-status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.file-status-icon.uploading {
  border: 2px solid #409eff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: file-spinner 0.6s linear infinite;
}

.file-status-icon.success {
  background: #67c23a;
  border-radius: 50%;
  color: #fff;
  font-size: 12px;
  font-weight: bold;
}

@keyframes file-spinner {
  to { transform: rotate(360deg); }
}
</style>
