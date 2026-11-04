<template>
  <div class="dataset_detail" v-loading="pageLoading">
    <div class="DetailtitleContainer">
      <span style="padding: 0 10px"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:28px;" />
      <span style="padding: 0 20px;"></span>
      <span style="color:#eee;">|</span>
      <span style="padding: 0 8px"></span>
      <span style="font-size:18px;font-weight:600;">详情</span>
    </div>

    <div class="task-info">
      <el-card :body-style="{ padding: '10px', 'border-radius': '8px' }">
        <h1 style="margin: 0px">{{ item.dataset_name || "TEST" }}</h1>
        <div class="tagsBox" v-if="item.tags && item.tags.length">
          <div v-for="tag in item.tags" :key="tag" class="tags">{{ tag || "标签" }}</div>
        </div>
        <div class="description_data">
          <span>{{ item.description || "暂无描述" }}</span>
        </div>
        <div class="other_info">
          <el-avatar
            :size="30"
            :src="item.is_open_source ? '/images/hugface.svg' : '/images/icon.png'"
          ></el-avatar>
          <div>{{ item.group || groupDefault }}</div>
          <div class="littleInfo_1" v-if="item.establish_time">
            <el-icon>
              <Clock />
            </el-icon>
            <span>{{ item.establish_time.split(" ")[0] }}</span>
          </div>
          <div class="littleInfo_2">
            <el-icon>
              <Download />
            </el-icon>
            <span>{{ item.download_count || 0 }}</span>
          </div>
          <div class="littleInfo_3">
            <el-icon>
              <View />
            </el-icon>
            <span>{{ item.view_count || 0 }}</span>
          </div>
        </div>
      </el-card>
    </div>
    <div class="card-container">
      <el-tabs v-model="activeName" @tab-click="tabClick">
        <el-tab-pane name="first" class="tabClass">
          <template #label>
            <span style="font-size: 18px;">测试集介绍</span>
          </template>
          <div style="display: flex">
            <div style="margin-left: auto">
              <el-button type="primary" @click="downloadSubmit" v-if="hasDownloadPermission">下载测评集</el-button>
              <el-button type="primary" @click="editContent" v-if="!edit && hasEditPermission">修改</el-button>
              <el-button type="primary" @click="saveContent" v-if="edit">保存</el-button>
              <el-button type="danger" @click="cancleContent" v-if="edit">取消</el-button>
            </div>
          </div>
          <div class="is-container">
            <div v-if="edit" style="border: 1px solid #ccc; width: 100%; margin-top: 10px">
              <Toolbar
                style="border-bottom: 1px solid #ccc"
                :editor="editorRef"
                :defaultConfig="toolbarConfig"
                :mode="mode"
              />
              <Editor
                style="height: 500px; overflow-y: hidden"
                v-model="htmlValue"
                :defaultConfig="editorConfig"
                :mode="mode"
                @onCreated="handleCreated"
              />
            </div>
            <div v-else v-html="$sanitizeHtml(item.content)"></div>
          </div>
        </el-tab-pane>
        <el-tab-pane name="detail" class="tabClass" v-if="hasViewPermission">
          <template #label>
            <span style="font-size: 18px;">详情展示</span>
          </template>
          <div class="detail-files-container" v-loading="detailLoading">
            <div v-if="detailFiles.length === 0 && !detailLoading" class="empty-tip">暂无文件数据</div>
            <TreeNodeComp
              v-for="(file, fileIndex) in detailFiles"
              :key="fileIndex"
              :node="file"
              :depth="0"
              :localPath="local_path"
              :isField="item.is_field"
              :datasetId="dataset_id"
            />
          </div>
        </el-tab-pane>
        <el-tab-pane name="compare" class="tabClass" v-if="showCompareTab">
          <template #label>
            <span style="font-size: 18px;">测试集对比</span>
          </template>
          <div class="compare-tab-wrap">
            <DatasetComparison
              :from-tab="compareFromTab"
              :dataset-key="compareDatasetKey"
              :display-name="compareDisplayName"
              :scenes="compareScenes"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script lang="ts" setup>
import {
  reactive,
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  shallowRef,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { manager_list } from "@/consts/copyrightConsts";
import { useDatasetStore } from "@/stores/datasetStore";
import {
  edit_datasets,
  get_dataset_files,
  getDatasetTree,
  upload_file,
  downloadDatasetZip,
  get_datasets,
} from "@/api/dataSetApi";
import { downloadFile } from "@/api/runService";
import { ElMessage } from "element-plus";
import "@wangeditor/editor/dist/css/style.css";
import { Editor, Toolbar } from "@wangeditor/editor-for-vue";
import { API_BASE_URL } from "@/utils/Constants.js";
import { useStore } from "vuex";
import TreeNodeComp from "./TreeNodeComp.vue";
import DatasetComparison from "@/components/rankingScore/datasetComparison.vue";
import {
  matchTag,
  resolveTagKey,
  resolveScenesByTags,
} from "@/components/rankingScore/datasetComparisonConfig";

const dimensions = ref([]);
const datasetStore = useDatasetStore();
const barValues = ref([]);
const route = useRoute();
const router = useRouter();
const store = useStore();
const query = route.query;
const edit = ref(false);
const item = reactive({
  dataset_name: "",
  tags: [],
  description: "",
  group: "",
  establish_time: "",
  downloadTime: "",
  viewTime: "",
  is_open_source: true,
  content: "",
  is_published: false,
  viewer_users: [],
  download_users: [],
  editor_users: [],
});
const local_path = ref("");
const tableData = reactive([]);
const datasets = ref({});
const content = ref("");
const dataset_id = ref("");
const multipleTable = ref(null);
const actionTab = ref("");
const multipleSelection = ref([]);
const htmlValue = ref("");
const token = ref("");
const currentUsername = localStorage.getItem("username") || "";
const isManager = manager_list.includes(currentUsername);

// 判断用户名是否匹配（支持前缀匹配，例如当前用户 "123" 可匹配名单中的 "123456"）
const matchUser = (list = [], username) => {
  return list.some((u) => u === "all" || u === username || u.startsWith(username));
};

// 判断当前用户是否有查看权限
const hasViewPermission = computed(() => {
  if (isManager) return true; // 管理员拥有全部权限
  if (item.is_published) return true; // 已发布，所有人可查看
  // 未发布：必须在 viewer_users 或 editor_users 中
  const viewers = item.viewer_users || [];
  const download_users = item.download_users || [];
  const editors = item.editor_users || [];
  return (
    currentUsername === item.register ||
    matchUser(viewers, currentUsername) ||
    matchUser(download_users, currentUsername) ||
    matchUser(editors, currentUsername)
  );
});

const hasDownloadPermission = computed(() => {
  if (isManager) return true; // 管理员默认拥有下载权限
  const download_users = item.download_users || [];
  const editors = item.editor_users || [];
  return (
    currentUsername === item.register ||
    matchUser(download_users, currentUsername) ||
    matchUser(editors, currentUsername)
  );
});

const hasEditPermission = computed(() => {
  if (isManager) return true; // 管理员默认拥有下载权限
  const editors = item.editor_users || [];
  return (
    currentUsername === item.register ||
    matchUser(editors, currentUsername)
  );
});

const groupDefault = ref("");
const editorRef = shallowRef();

const toolbarConfig = ref({
  excludeKeys: ["group-video", "fullScreen"],
});

const editorConfig = reactive({
  placeholder: "请输入内容...",
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
});

// 组件销毁时，也及时销毁编辑器
onBeforeUnmount(() => {
  const editor = editorRef.value;
  if (editor == null) return;
  editor.destroy();
});

const handleCreated = (editor) => {
  editorRef.value = editor;
};

// const getEvalResult = (full) => {
//   const results = [];
//   Object.keys(full).forEach((modeName) => {
//     const modeData = full[modeName];
//     if (modeData.result && Array.isArray(modeData.result)) {
//       modeData.result.forEach((result) => {
//         if (result.dataset_name === dataset_id.value) {
//           results.push({
//             model_name: modeName,
//             dataset_name: result.dataset_name,
//             score: result.score,
//           });
//         }
//       });
//     }
//   });
//   let sort_result = results.sort((a, b) => b.score - a.score);
//   dimensions.value = sort_result.slice(0, 5).map((item) => item.model_name);
//   barValues.value = sort_result.slice(0, 5).map((item) => item.score);
//   Object.assign(
//     tableData,
//     results.sort((a, b) => b.score - a.score)
//   );
//   sort_result.slice(0, 5).forEach((row) => {
//     // multipleTable.value.toggleRowSelection(row, true);
//   });
// };

onMounted(async () => {
  pageLoading.value = true;
  dataset_id.value = query.id;
  actionTab.value = query.type;
  const dataset = reactive({});
  let dataType = "";
  let isField = "";
  if (actionTab.value === "openSource") {
    groupDefault.value = "open";
    dataType = "ruler1";
    isField = "1";
  } else if (actionTab.value === "domain") {
    groupDefault.value = "domain";
    dataType = "ruler2";
    isField = "2";
  } else if (actionTab.value === "dev") {
    groupDefault.value = "dev";
    dataType = "ruler3";
    isField = "3";
  }
  try {
    let detail = datasetStore.getDatasetById(dataType, dataset_id.value);
    if (!detail) {
      // 刷新/直达页面时 store 为空，先从接口拉取并缓存再取详情
      const res = await get_datasets(isField);
      datasetStore.setDatasets(dataType, res.data);
      detail = datasetStore.getDatasetById(dataType, dataset_id.value);
    }
    Object.assign(item, detail || {});
    if (actionTab.value === "openSource") {
      local_path.value = item.local_path;
    } else {
      local_path.value = item.input_path;
    }
    htmlValue.value = item.content;
    token.value = localStorage.getItem("username");
  } catch (err) {
    console.error("获取数据集详情失败", err);
  } finally {
    pageLoading.value = false;
  }
});

const downloadSubmit = async () => {
  try {
    const res = await get_dataset_files({
      local_path: local_path.value,
      is_field: item.is_field,
      dataset: dataset_id.value,
      user_name: token.value,
    });
    const files = res.data;
    if (!files || files.length === 0) {
      ElMessage({ type: "error", message: "没有可供下载的文件" });
      return;
    }
    if (files.length === 1) {
      // 单个文件，直接下载
      const response = await downloadFile({ filepath: files[0] });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = files[0].split("/").pop().split("\\").pop();
      a.click();
      window.URL.revokeObjectURL(url);
    } else {
      // 多个文件或文件夹，压缩后下载
      const response = await downloadDatasetZip({
        filepaths: files,
        zip_name: dataset_id.value || "dataset",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${dataset_id.value || "dataset"}.zip`;
      a.click();
      window.URL.revokeObjectURL(url);
    }
    ElMessage({ type: "success", message: "下载成功" });
  } catch (err) {
    const msg = err.response?.data?.error || err.message || "下载失败";
    ElMessage({ type: "error", message: "下载失败: " + msg });
  }
};

// const handleSelectionChange = (rows) => {
//   // multipleSelection = ref(val).value;
//   // console.log(val);
//   if (rows) {
//     rows.forEach((row) => {
//       // multipleTable.value.toggleRowSelection(row, true);
//     });
//   } else {
//     multipleTable.value.clearSelection();
//   }
//   dimensions.value = rows.map((item) => {
//     return item.model_name;
//   });
//   barValues.value = rows.map((item) => {
//     return item.score;
//   });
// };

const form = reactive({
  dataset_id: "",
  dataset_name: "",
  testcase_tags: [],
  subset_list: [],
  default_subsets: [],
  description: "",
  few_shot_num: "",
  is_open_source: "",
  is_field: "",
  content: "",
  metric_list: [],
  file_list: [],
  few_file_list: [],
});
const activeName = ref("first");
const pageLoading = ref(false);

// ============ 测试集对比 tab ============
// 尺子二：一个标签下若有多个测试集，仅当当前测试集是该标签下"使用中"且最近更新的测试集时才展示对比 tab
const isRuler2InUse = computed(() => {
  const all = datasetStore.ruler2Datasets || {};
  const tagKey = resolveTagKey(item.testcase_tags || []);
  if (!tagKey) return false;
  const candidates = Object.entries(all).filter(([id, d]) =>
    (d.testcase_tags || []).some((t) => matchTag(t, tagKey))
  );
  if (candidates.length === 0) return false;
  const inUse = candidates.filter(([, d]) =>
    d.in_use === true || d.in_use === 1 || d.in_use === "1" || d.in_use === "true"
  );
  const pool = inUse.length > 0 ? inUse : candidates;
  pool.sort((a, b) => new Date(b[1].establish_time || 0) - new Date(a[1].establish_time || 0));
  return pool[0][0] === dataset_id.value;
});

// 尺子二：由当前测试集的标签反推场景列表（记忆/GUI 合并场景）
const compareScenes = computed(() => resolveScenesByTags(item.testcase_tags || []));

const showCompareTab = computed(() => {
  if (actionTab.value === "openSource") return !!item.dataset_name;
  if (actionTab.value === "domain")
    return compareScenes.value.length > 0 && isRuler2InUse.value;
  return false;
});

const compareFromTab = computed(() =>
  actionTab.value === "openSource" ? "ruler1" : "ruler2"
);
const compareDatasetKey = computed(() =>
  actionTab.value === "openSource" ? item.dataset_name || "" : ""
);
const compareDisplayName = computed(() => item.dataset_name || "");

// ============ 详情展示逻辑 ============
const detailFiles = ref([]);
const detailLoading = ref(false);

// 展开/折叠由 TreeNodeComp 内部处理，无需父组件介入

const fetchDetailFiles = async () => {
  detailLoading.value = true;
  try {
    const res = await getDatasetTree({
      local_path: local_path.value,
      is_field: item.is_field,
      dataset: dataset_id.value,
    });
    const data = res.data;
    if (!data || !data.tree || data.tree.length === 0) {
      detailFiles.value = [];
      return;
    }
    // 为每个节点注入 _fullPath 和运行时状态
    const injectPath = (nodes, parentPath) => {
      if (!nodes) return;
      for (const node of nodes) {
        node._fullPath = parentPath
          ? parentPath + "/" + node.file_name
          : node.file_name;
        node._expanded = false;
        node._loading = false;
        node._loaded = false;
        if (node._type === "directory" && node.children) {
          injectPath(node.children, node._fullPath);
        }
      }
    };
    injectPath(data.tree, "");
    detailFiles.value = data.tree;
  } catch (err) {
    ElMessage({
      type: "error",
      message: "获取文件列表失败: " + (err.message || ""),
    });
  } finally {
    detailLoading.value = false;
  }
};

// 切换到"详情展示"标签页时加载数据
const tabClick = (tab) => {
  if (tab.props.name === "detail" && detailFiles.value.length === 0) {
    fetchDetailFiles();
  }
};

const editContent = () => {
  htmlValue.value = item.content;
  edit.value = edit.value === true ? false : true;
};
const saveContent = () => {
  Object.keys(item).forEach((key) => {
    if (form[key] !== undefined) {
      form[key] = item[key];
    }
  });
  // return;
  edit.value = edit.value === true ? false : true;
  form.content = htmlValue.value;
  item.content = htmlValue.value;
  form.dataset_id = dataset_id.value;
  edit_datasets(form).then(
    (res) => {
      ElMessage({
        type: "success",
        message: "修改成功",
      });
    },
    (err) => {
      ElMessage({
        type: "error",
        message:
          "修改失败: " +
          (JSON.parse(err.request.response)["err_info"] !== undefined
            ? JSON.parse(err.request.response)["err_info"]
            : err),
      });
    }
  );
};
const cancleContent = () => {
  edit.value = edit.value === true ? false : true;
};

const goBack = () => {
  router.push({
    name: "evalDatasetDevelopment",
    query: { type: actionTab.value },
  });
};
</script>

<style scoped>
/* 基础样式 */
.dataset_detail {
  padding: 0;
  background-color: #f5f5f5;
}
.test {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #e7f1ff;
  color: #3a7aaf;
  border-radius: 8px;
  padding: 0px 3px;
  gap: 0.1rem;
}
.el-tabs {
  width: 100%;
}

.DetailtitleContainer {
  display: flex;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  margin-bottom: 10px;
  padding-left: 10px;
}

.task-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 0 28px;
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
  background-color: #ffffff;
  border-radius: 8px;
  display: flex;
  gap: 20px;
  padding: 10px;
  margin: 10px 28px 0;
}

/* 测试集对比 tab：占满页面剩余可视高度，避免图表需滚动才能看全 */
.compare-tab-wrap {
  height: calc(100vh - 280px);
  min-height: 480px;
  overflow: hidden;
}

.is-container {
  display: flex;
  min-height: calc(100vh - 60px);
}
.question-tag-card {
  flex: 1 1 30%;
}

.question-table-card {
  flex: 1 1 70%;
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
.description_data {
  overflow-wrap: break-word;
  margin: 20px 0px;
}
.tagsBox {
  margin-top: 10px;
  display: flex;
  gap: 0.5rem;
}

.tags {
  border-radius: 8px;
  padding: 0px 5px;
  color: rgb(75, 72, 255);
  background-color: rgba(220, 220, 255, 0.712);
  /* transform: scale(0.8); */
  transform-origin: top left;
}

.other_info {
  margin-top: 10px;
  display: flex;
  gap: 1rem;
  align-items: center;
}

.info_left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.littleInfo_1 {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #eaffed;
  color: #4aa155;
  border-radius: 8px;
  padding: 0px 2px;
  gap: 0.1rem;
  justify-content: center;
  width: 120px;
}

.littleInfo_2 {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #e7f1ff;
  color: #3a7aaf;
  border-radius: 8px;
  padding: 0px 3px;
  gap: 0.1rem;
  justify-content: center;
  width: 56px;
}

.littleInfo_3 {
  display: flex;
  align-items: center;
  height: 25px;
  background-color: #ffe7ff;
  color: #cf6ef5;
  border-radius: 8px;
  padding: 0px 3px;
  gap: 0.1rem;
  justify-content: center;
  width: 56px;
}

.back-area {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 10px;
  width: 50px;
  cursor: pointer;
}

/* ========== 详情展示标签页 ========== */
.detail-files-container {
  width: 100%;
  min-height: 200px;
}
.detail-files-container .empty-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 60px 0;
  color: #bfc4cc;
  font-size: 15px;
}
</style>
