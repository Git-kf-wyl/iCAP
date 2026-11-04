<script lang="ts" setup>
import { reactive, ref, computed, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { Minus } from "@element-plus/icons-vue";
import router from "@/router/index.js";
import { useAIModelStore } from "@/stores/aiModel.js";
import { ChatService } from "@/services/chatService.js";
import { useRoute } from "vue-router";
import { ModelService } from "@/services/modelService.js";
import { API_BASE_URL } from "@/utils/Constants.js";
import { getLocalISOString } from "@/utils/TimeUtils.js";
import type { TabsPaneContext, TabPaneName } from "element-plus";
import { INTERPRETATION_TAGS } from "@/utils/Constants.js";

const formRef = ref(null);
const store = useAIModelStore();
const route = useRoute();

const seriesOptions = ["pangu", "qwen2", "qwen3", "deepseek"];
const vendorOptions = ["华为", "阿里巴巴", "月之暗面", "腾讯"];
const tagOptions = [
  "reason",
  "chat",
  "tools",
  "math",
  "coder",
  "others",
  "ASR",
  "MT",
  "TTS",
];
const categoryOptions = [
  { label: "自然语言大模型", value: "LLM" },
  { label: "多模态大模型", value: "MLLM" },
];
const yesNoOptions = [
  { label: "是", value: true },
  { label: "否", value: false },
];
const methodOptions = ["POST", "GET", "PUT", "DELETE"];

// 3. 新增一个 ref，用来标记当前是“新增”还是“编辑”
const isEditMode = ref(false);

const isChatModel = ref(true);

const form = reactive({
  model_id: "",
  status: true,
  info: {
    model_name: "",
    model_desc: "",
    model_doc: "",
    series: seriesOptions.at(0),
    vendor: vendorOptions.at(0),
    tags: [],
    category: [categoryOptions.at(0).value],
    size: 0,
    context_length: 32,
    isInternalDeployed: true,
    creation_date: getLocalISOString().split("T")[0],
    zone: false,
  },
  config: {
    is_openai_format: true,
    endpoint: [""], // 至少一个
    api_key: "",
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
        is_openai_format: true,
        params: [
          { key: "max_tokens", value: 4000 },
          { key: "top_p", value: 1.0 },
          { key: "top_k", value: 40 },
          { key: "temperature", value: 0.7 },
        ],
      },
      {
        endpoint: "",
        api_key: "",
        request_method: "POST",
        body: "",
        extra_headers: [{ key: "", value: "" }],
        is_openai_format: false,
        resp_prefix: "",
        resp_tail: "",
        params: [
          { key: "max_tokens", value: 4000 },
          { key: "top_p", value: 1.0 },
          { key: "top_k", value: 40 },
          { key: "temperature", value: 0.7 },
        ],
      },
    ],
    api_params_available: [],
  },
});

onMounted(async () => {
  const modelId = route.query.modelId;
  const type = route.query.type;
  if (modelId && modelId !== "") {
    isEditMode.value = true;
    try {
      const data = await ModelService.getOneModelInfo(modelId);
      console.log("onMounted data", data);
      Object.assign(form, data);
      form.info.zone = false;

      // activeName.value =
      //   data.config.is_openai_format === true ? "OpenAI" : "unOpenAI";
      const APIParams = data.config.api_params;
      activeName.value =
        APIParams[0].is_openai_format === true ? "OpenAI" : "unOpenAI";
      editableTabsOpen.value = APIParams.filter(
        (item) => item.is_openai_format === true
      ).map((item, index) => ({
        title: "节点" + (index + 1),
        name: "节点" + (index + 1),
        apiParameter: item,
      }));
      editableTabsUnOpen.value = APIParams.filter(
        (item) => item.is_openai_format === false
      ).map((item, index) => ({
        title: "节点" + (index + 1),
        name: "节点" + (index + 1),
        apiParameter: item,
      }));

      isChatModel.value = !INTERPRETATION_TAGS.some((item) =>
        data.info.tags.includes(item)
      );
      console.log("获取模型信息成功");
    } catch (error) {
      if (type === "add") {
        form.model_id = modelId;
        form.info.model_name = modelId;
      } else {
        ElMessage.error("获取模型信息失败");
      }
    }
  }
});

// 用于自定义校验 params
const configParams = computed(() => form.config.params);

const rules = {
  model_id: [{ required: true, message: "请输入模型 ID", trigger: "blur" }],
  "info.model_name": [
    { required: true, message: "请输入模型名称", trigger: "blur" },
  ],
  "info.series": [{ required: true, message: "请选择系列", trigger: "change" }],
  "info.vendor": [{ required: true, message: "请选择厂商", trigger: "change" }],
  "info.category": [
    {
      type: "array",
      required: true,
      min: 1,
      message: "请选择至少一个分类",
      trigger: "change",
    },
  ],
  "info.isInternalDeployed": [
    { required: true, message: "请选择是否内部部署", trigger: "change" },
  ],
  // "config.endpoint": [
  //   {
  //     type: "array",
  //     required: true,
  //     min: 1,
  //     message: "请至少添加一个 Endpoint",
  //     trigger: "change",
  //   },
  // ],
  // 隐藏字段，用于校验 params 的 value
  configParams: [
    {
      validator: (rule, value, callback) => {
        const empty = form.config.params.filter((p) => !p.value);
        console.log(empty);
        if (empty.length) {
          callback(new Error("请填写所有参数值"));
        } else {
          callback();
        }
      },
      trigger: "blur",
    },
  ],
};

function addEndpoint() {
  form.config.endpoint.push("");
}

function removeEndpoint(i) {
  form.config.endpoint.splice(i, 1);
}

function addHeader() {
  form.config.extra_headers.push({ key: "", value: "" });
}

function removeHeader(i) {
  form.config.extra_headers.splice(i, 1);
}

const addHeader2 = (item) => {
  item.apiParameter.extra_headers.push({
    key: "",
    value: "",
  });
  // console.log(item);
};

const removeHeader2 = (item, index) => {
  item.apiParameter.extra_headers.splice(index, 1);
  // console.log(item);
};

function addParam(item) {
  item.apiParameter.params.push({
    key: "",
    value: "",
  });
  // form.config.params.push({ key: "", value: "" });
}

function removeParam(item, i) {
  item.apiParameter.params.splice(i, 1);
  // form.config.params.splice(i, 1);
}

const handleSubmit = () => {
  const apiParamsOpen = editableTabsOpen.value
    .map((item) => {
      if (item.apiParameter.endpoint && item.apiParameter.endpoint !== "") {
        return item.apiParameter;
      }
    })
    .filter((item) => item !== undefined);
  const apiParamsUnOpen = editableTabsUnOpen.value
    .map((item) => {
      if (item.apiParameter.endpoint && item.apiParameter.endpoint !== "") {
        return item.apiParameter;
      }
    })
    .filter((item) => item !== undefined);

  // 将两个数组合并
  form.config.api_params = apiParamsOpen.concat(apiParamsUnOpen);
  console.log("form");
  console.log(form);
  // return;
  formRef.value.validate(async (valid) => {
    if (!valid) {
      return ElMessage.error("请完善表单信息");
    }
    // 做一遍自定义校验
    try {
      await new Promise((resolve, reject) => {
        rules.configParams[0].validator(null, configParams.value, (err) =>
          err ? reject(err) : resolve()
        );
      });
    } catch (err) {
      return ElMessage.error(err.message);
    }

    // Now you’re in an async function, you can await:
    try {
      const data = isEditMode.value
        ? await ModelService.modifyModel(form)
        : await ModelService.registerModel(form);
      ElMessage.success("提交成功");
      store.setModels(data);
    } catch (err) {
      console.error(err);
      ElMessage.error("提交失败");
    }
  });
};

const debug = reactive({
  isStream: true, // 是否流式
  prompt: "", // 输入
  response: "", // 输出/响应
  loading: false, // 发送按钮 loading
  isStreaming: false, // 正在流式
  controller: null, // AbortController 用于中断流式
});

/* ============ ②  调试按钮事件 ============ */
function handleSend() {
  // if (!form.config.endpoint.length || !form.config.endpoint[0]) {
  //   ElMessage.error("请先在右侧填写至少一个 Endpoint");
  //   return;
  // }
  debug.response = "";
  debug.loading = true;
  // 新增：创建 AbortController
  const controller = new AbortController();
  debug.controller = controller;
  console.log("form:", form.config);

  const curConfig = {
    messages: [{ role: "user", content: debug.prompt }],
    temperature: form.config.api_params[0].params?.find(
      (p) => p.key === "temperature"
    )?.value,
    max_tokens: form.config.api_params[0].params?.find(
      (p) => p.key === "max_tokens"
    )?.value,
    top_p: form.config.api_params[0].params?.find((p) => p.key === "top_p")
      ?.value,
    top_k: form.config.api_params[0].params?.find((p) => p.key === "top_k")
      ?.value,
  };

  // 流式输出
  if (debug.isStream) {
    ChatService.sendMsgStream(
      {
        endpoint: `${API_BASE_URL}stream_chat`,
        model: form.model_id,
        config: curConfig,
        signal: controller.signal,
        query: debug.prompt,
      },
      (message) => {
        debug.isStreaming = true;
        debug.response = message;
      },
      (message, error) => {
        // debug.response = message;
        debug.loading = false;
        debug.isStreaming = false;
        if (error) {
          console.error("请求失败");
        } else {
          console.log("请求成功");
        }
      }
      // form.config.extra_headers.reduce(function (acc, item) {
      //   if (item.key && item.key !== "") {
      //     acc[item.key] = item.value;
      //     return acc;
      //   }
      // }, {})
    );
  }

  // 非流式输出
  else {
    const payload = {
      model: form.model_id,
      query: debug.prompt,
      config: curConfig,
    };
    const payloadStr = JSON.stringify(payload);
    console.log("aaa payloadStr", payloadStr);
    ChatService.sendMsgNotStream(
      payload,
      (message) => {
        debug.isStreaming = true;
        debug.response = message;
      },
      (message, error) => {
        debug.response = message;
        debug.loading = false;
        debug.isStreaming = false;
        if (error) {
          console.error("请求失败");
        } else {
          console.log("请求成功");
        }
      }
    );
    // ChatService.sendCompanyApiMessage(
    //     {
    //       endpoint: UURL,
    //       apiKey: form.config.api_key,
    //       model: form.model_id,
    //       messages: [{role: "user", content: debug.prompt}],
    //       signal: controller.signal,
    //     },
    //     (message) => {
    //       debug.isStreaming = true;
    //       debug.response = message;
    //     },
    //     (message, error) => {
    //       debug.response = message;
    //       debug.loading = false;
    //       debug.isStreaming = false;
    //       if (error) {
    //         ElMessage.error("请求失败");
    //       } else {
    //         ElMessage.success("请求成功");
    //       }
    //     },
    //     form.config.extra_headers.reduce(function (acc, item) {
    //       if (item.key && item.key !== "") {
    //         acc[item.key] = item.value;
    //         return acc;
    //       }
    //     }, {})
    // );
  }
}

function handleStop() {
  if (debug.controller) {
    debug.controller.abort(); // 直接中断 fetch
    debug.controller = null;
  }
  debug.isStreaming = false;
  debug.loading = false;
}

const activeName = ref("OpenAI");

const handleTabClick = (tab: TabsPaneContext) => {
  const name = tab.props.name;
  if (name === "OpenAI") {
    form.config.is_openai_format = true;
  } else if (name === "unOpenAI") {
    form.config.is_openai_format = false;
  } else {
    console.log("TabsError!!!");
  }
};

const editableTabsValueOpen = ref("节点1");
const editableTabsOpen = ref([
  { title: "节点1", name: "节点1", apiParameter: form.config.api_params[0] },
]);

const editableTabsValueUnOpen = ref("节点1");
const editableTabsUnOpen = ref([
  {
    title: "节点1",
    name: "节点1",
    apiParameter: form.config.api_params[1],
  },
]);

const handleTabsEditOpen = (
  targetName: TabPaneName | undefined,
  action: "remove" | "add"
) => {
  if (action === "add") {
    const newTabIndex = editableTabsOpen.value.length + 1;
    const newTabName = `节点${newTabIndex}`;
    editableTabsOpen.value.push({
      title: newTabName,
      name: newTabName,
      apiParameter: {
        endpoint: "",
        api_key: "",
        is_openai_format: true,
        params: [
          { key: "max_tokens", value: 4000 },
          { key: "top_p", value: 1.0 },
          { key: "top_k", value: 40 },
          { key: "temperature", value: 0.7 },
        ],
      },
    });
    editableTabsValueOpen.value = newTabName;
  } else if (action === "remove") {
    if (editableTabsOpen.value.length + editableTabsUnOpen.value.length <= 1) {
      ElMessage({
        type: "warning",
        message: "至少需一个节点",
      });
      return;
    } else if (editableTabsOpen.value.length > 1) {
      const targetIndex = editableTabsOpen.value.findIndex(
        (tab) => tab.name === targetName
      );
      if (targetIndex === -1) {
        return;
      }

      // 获取当前激活的tab名称
      const currentActiveName = editableTabsValueOpen.value;

      // 计算新的激活项索引
      let newActiveIndex = editableTabsOpen.value.findIndex(
        (tab) => tab.name === currentActiveName
      );
      if (newActiveIndex > targetIndex) {
        newActiveIndex -= 1;
      } else if (newActiveIndex === targetIndex) {
        // 如果当前激活的tab就是被删除的tab，选择下一个或上一个
        newActiveIndex = Math.max(0, targetIndex - 1);
      }

      // 过滤掉被删除的tab
      const newTabs = editableTabsOpen.value.filter(
        (tab, index) => index !== targetIndex
      );

      // 重新生成所有tab的name和title
      newTabs.forEach((tab, newIndex) => {
        tab.name = `节点${newIndex + 1}`;
        tab.title = `节点${newIndex + 1}`;
      });

      // 更新激活项的名称
      if (newActiveIndex >= 0 && newActiveIndex < newTabs.length) {
        editableTabsValueOpen.value = newTabs[newActiveIndex].name;
      } else {
        // 如果没有合适的激活项，选择最后一个
        editableTabsValueOpen.value = newTabs[newTabs.length - 1].name;
      }

      // 更新editableTabs
      editableTabsOpen.value = newTabs;
    } else {
      editableTabsOpen.value = [];
    }
  }
};

const handleTabsEditUnOpen = (
  targetName: TabPaneName | undefined,
  action: "remove" | "add"
) => {
  if (action === "add") {
    const newTabIndex = editableTabsUnOpen.value.length + 1;
    const newTabName = `节点${newTabIndex}`;
    editableTabsUnOpen.value.push({
      title: newTabName,
      name: newTabName,
      apiParameter: {
        endpoint: "",
        api_key: "",
        request_method: "POST",
        body: "",
        extra_headers: [{ key: "", value: "" }],
        is_openai_format: false,
        resp_prefix: "",
        resp_tail: "",
        params: [
          { key: "max_tokens", value: 4000 },
          { key: "top_p", value: 1.0 },
          { key: "top_k", value: 40 },
          { key: "temperature", value: 0.7 },
        ],
      },
    });
    editableTabsValueUnOpen.value = newTabName;
  } else if (action === "remove") {
    if (editableTabsOpen.value.length + editableTabsUnOpen.value.length <= 1) {
      ElMessage({
        type: "warning",
        message: "至少需一个节点",
      });
      return;
    } else if (editableTabsUnOpen.value.length > 1) {
      const targetIndex = editableTabsUnOpen.value.findIndex(
        (tab) => tab.name === targetName
      );
      if (targetIndex === -1) {
        return;
      }

      // 获取当前激活的tab名称
      const currentActiveName = editableTabsValueUnOpen.value;

      // 计算新的激活项索引
      let newActiveIndex = editableTabsUnOpen.value.findIndex(
        (tab) => tab.name === currentActiveName
      );
      if (newActiveIndex > targetIndex) {
        newActiveIndex -= 1;
      } else if (newActiveIndex === targetIndex) {
        // 如果当前激活的tab就是被删除的tab，选择下一个或上一个
        newActiveIndex = Math.max(0, targetIndex - 1);
      }

      // 过滤掉被删除的tab
      const newTabs = editableTabsUnOpen.value.filter(
        (tab, index) => index !== targetIndex
      );

      // 重新生成所有tab的name和title
      newTabs.forEach((tab, newIndex) => {
        tab.name = `节点${newIndex + 1}`;
        tab.title = `节点${newIndex + 1}`;
      });

      // 更新激活项的名称
      if (newActiveIndex >= 0 && newActiveIndex < newTabs.length) {
        editableTabsValueUnOpen.value = newTabs[newActiveIndex].name;
      } else {
        // 如果没有合适的激活项，选择最后一个
        editableTabsValueUnOpen.value = newTabs[newTabs.length - 1].name;
      }

      // 更新editableTabs
      editableTabsUnOpen.value = newTabs;
    } else {
      editableTabsUnOpen.value = [];
    }
  }
};

function onBack() {
  router.push({
    path: "/modelSquare",
  });
}
</script>

<template>
  <div class="edit-center-container">
    <!-- <div class="pageTitle">
      <span style="color: grey" @click="onBack">模型广场 /</span>模型注册
    </div>-->
    <div class="editTitleContainer">
      <span style="padding: 0 14px"></span>
      <!-- <el-icon @click="onBack" style="cursor: pointer;">
        <Back />
      </el-icon>
      <span @click="onBack" style="color:rgba(18, 19, 22, 0.8);cursor: pointer;">返回</span>-->
      <img src="/images/return.png" class="returnicon" @click="onBack" style="left:28px;" />
      <span style="padding: 0 20px;"></span>
      <span @click="onBack" style="color: #969696;cursor: pointer;">模型广场</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>
      <span style="font-size:18px;font-weight:600;">{{isEditMode ? '编辑模型参数' : '注册模型'}}</span>
    </div>

    <div class="pageContent">
      <h4 class="title">{{isEditMode ? '编辑模型参数' : '注册模型'}}</h4>
      <div class="panels">
        <div class="left-panel">
          <el-card
            class="debug-card"
            style="max-width:520px; width:100%;border: none; box-shadow: none"
          >
            <h4 style="margin:0;border: none">样例调试</h4>
            <br />

            <!-- 是否流式 -->
            <el-form label-width="80px">
              <el-form-item label="流式">
                <el-switch v-model="debug.isStream" active-text="开" inactive-text="关" />
              </el-form-item>

              <!-- 输入 -->
              <el-form-item label="输入">
                <el-input
                  type="textarea"
                  :rows="6"
                  v-model="debug.prompt"
                  placeholder="请输入测试 Prompt"
                />
              </el-form-item>

              <!-- 响应 -->
              <el-form-item label="响应">
                <el-input
                  type="textarea"
                  :rows="10"
                  readonly
                  v-model="debug.response"
                  placeholder="等待响应…"
                />
              </el-form-item>

              <!-- 按钮 -->
              <el-form-item>
                <el-button
                  type="default"
                  plain
                  :disabled="!debug.isStreaming"
                  @click="handleStop"
                >停止响应</el-button>
                <el-button
                  type="primary"
                  :loading="debug.loading"
                  @click="handleSend"
                  :disabled="!isChatModel"
                >发送</el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </div>
        <hr />
        <div class="right-panel">
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="120px"
            style="max-width: 500px"
          >
            <el-divider>
              <h3>
                <b>基本信息</b>
              </h3>
            </el-divider>

            <!-- 基本信息 -->
            <el-form-item label="模型 ID" prop="model_id">
              <el-input v-model="form.model_id" :disabled="isEditMode" placeholder="请输入模型id，不能与现有id重复"/>
            </el-form-item>
            <el-form-item label="模型名称" prop="info.model_name">
              <el-input v-model="form.info.model_name" placeholder="请输入模型名，是调用时用到的model"/>
            </el-form-item>
            <el-form-item label="模型描述">
              <el-input type="textarea" v-model="form.info.model_desc" rows="2" />
            </el-form-item>
            <el-form-item label="系列" prop="info.series">
              <el-input v-model="form.info.series" placeholder="请选择或输入系列，如pangu、qwen、deepseek等" />
            </el-form-item>
            <el-form-item label="厂商" prop="info.vendor">
              <el-input v-model="form.info.vendor" placeholder="请选择或输入厂商，如华为、阿里巴巴、腾讯等" />
            </el-form-item>
            <el-form-item label="标签">
              <el-select
                v-model="form.info.tags"
                multiple
                filterable
                allow-create
                placeholder="请选择或输入"
              >
                <el-option v-for="opt in tagOptions" :key="opt" :label="opt" :value="opt" />
              </el-select>
            </el-form-item>
            <el-form-item label="分类" prop="info.category">
              <el-select v-model="form.info.category" multiple placeholder="请选择分类">
                <el-option
                  v-for="opt in categoryOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="大小 (Billion)">
              <el-input-number v-model="form.info.size" :min="0" />
            </el-form-item>
            <el-form-item label="上下文长度">
              <el-input-number v-model="form.info.context_length" :min="0" />
            </el-form-item>

            <el-form-item label="内部部署" prop="info.isInternalDeployed">
              <el-select v-model="form.info.isInternalDeployed" placeholder="请选择">
                <el-option
                  v-for="opt in yesNoOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="发布日期">
              <el-date-picker
                v-model="form.info.creation_date"
                type="date"
                placeholder="请选择日期"
                style="width:100%;"
              />
            </el-form-item>

            <el-form-item label="是否可用" prop="info.isInternalDeployed">
              <el-select v-model="form.status" placeholder="请选择">
                <el-option
                  v-for="opt in yesNoOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="选择分区" prop="info.zone">
              <el-switch
                v-model="form.info.zone"
                active-text="黄区"
                inactive-text="绿区"
                :style="{ '--el-switch-on-color': 'yellow', '--el-switch-off-color': 'green'}"
              />
            </el-form-item>

            <br />

            <el-divider>
              <h3>
                <b>接口配置</b>
              </h3>
            </el-divider>

            <el-tabs v-model="activeName" class="demo-tabs" @tab-click="handleTabClick">
              <el-tab-pane label="OpenAI" name="OpenAI">
                <el-tabs
                  v-model="editableTabsValueOpen"
                  type="card"
                  editable
                  class="demo-tabs"
                  @edit="handleTabsEditOpen"
                >
                  <el-tab-pane
                    v-for="item in editableTabsOpen"
                    :key="item.name"
                    :label="item.title"
                    :name="item.name"
                  >
                    <el-form-item label="节点URL" prop="config.endpoint" :rules="endpointRule">
                      <div
                        style="display:flex; align-items:center; margin-bottom:10px; width:100%;"
                      >
                        <el-input
                          v-model="item.apiParameter.endpoint"
                          placeholder="请输入 URL"
                          style="flex:1;"
                        />
                      </div>
                    </el-form-item>

                    <el-form-item label="API秘钥">
                      <el-input v-model="item.apiParameter.api_key" placeholder="请输入 API秘钥" />
                    </el-form-item>

                    <!-- ============ 参数 列表 ============ -->
                    <el-form-item label="默认超参" prop="configParams">
                      <!-- 每行一个 Endpoint -->
                      <div
                        v-for="(p, i) in item.apiParameter.params"
                        :key="i"
                        style="display:flex; align-items:center; margin-bottom:8px;"
                      >
                        <el-input v-model="p.key" placeholder="Key" style="margin-right:8px;" />
                        <el-input
                          v-model.number="p.value"
                          placeholder="Value"
                          style="margin-right:8px;"
                          type="number"
                          v-if="p.key==='max_tokens'||p.key==='top_p'||p.key==='top_k'||p.key==='temperature'"
                        />
                        <el-input
                          v-model="p.value"
                          placeholder="Value"
                          style="margin-right:8px;"
                          v-else
                        />
                        <el-button
                          size="small"
                          type="danger"
                          :icon="Minus"
                          @click="removeParam(item,i)"
                          circle
                        />
                      </div>
                      <!-- 添加按钮独占一行，放在下方 -->
                      <el-button
                        type="primary"
                        style="min-width: 150px; margin-left: auto"
                        @click="addParam(item)"
                      >添加参数</el-button>
                    </el-form-item>
                  </el-tab-pane>
                </el-tabs>
              </el-tab-pane>
              <el-tab-pane label="非OpenAI" name="unOpenAI">
                <el-tabs
                  v-model="editableTabsValueUnOpen"
                  type="card"
                  editable
                  class="demo-tabs"
                  @edit="handleTabsEditUnOpen"
                >
                  <el-tab-pane
                    v-for="item in editableTabsUnOpen"
                    :key="item.name"
                    :label="item.title"
                    :name="item.name"
                  >
                    <el-form-item label="节点URL" prop="config.endpoint">
                      <div
                        style="display:flex; align-items:center; margin-bottom:10px; width:100%;"
                      >
                        <el-input
                          v-model="item.apiParameter.endpoint"
                          placeholder="请输入 URL"
                          style="flex:1;"
                        />
                      </div>
                    </el-form-item>

                    <el-form-item label="API秘钥">
                      <el-input v-model="item.apiParameter.api_key" placeholder="请输入 API秘钥" />
                    </el-form-item>

                    <el-form-item label="请求方法">
                      <el-select
                        v-model="item.apiParameter.request_method"
                        placeholder="请选择 请求方法"
                        disabled
                      >
                        <el-option v-for="m in methodOptions" :key="m" :label="m" :value="m" />
                      </el-select>
                    </el-form-item>

                    <el-form-item label="请求体模板">
                      <el-input type="textarea" v-model="item.apiParameter.body" :rows="3" />
                    </el-form-item>

                    <el-form-item label="额外请求头" prop="config.extra_headers">
                      <div
                        v-for="(h, i) in item.apiParameter.extra_headers"
                        :key="i"
                        style="display:flex; align-items:center; margin-bottom:8px;"
                      >
                        <el-input v-model="h.key" placeholder="Key" style="margin-right:8px;" />
                        <el-input v-model="h.value" placeholder="Value" style="margin-right:8px;" />
                        <el-button
                          type="danger"
                          :icon="Minus"
                          size="small"
                          @click="removeHeader2(item,i)"
                          circle
                        />
                      </div>
                      <el-button
                        type="primary"
                        style="min-width: 150px; margin-left: auto"
                        @click="addHeader2(item)"
                      >添加请求头</el-button>
                    </el-form-item>

                    <el-form-item label="响应前缀">
                      <el-input v-model="item.apiParameter.resp_prefix" />
                    </el-form-item>

                    <el-form-item label="响应后缀">
                      <el-input v-model="item.apiParameter.resp_tail" />
                    </el-form-item>

                    <!-- ============ 参数 列表 ============ -->
                    <el-form-item label="默认超参" prop="configParams">
                      <!-- 每行一个 Endpoint -->
                      <div
                        v-for="(p, i) in item.apiParameter.params"
                        :key="i"
                        style="display:flex; align-items:center; margin-bottom:8px;"
                      >
                        <el-input v-model="p.key" placeholder="Key" style="margin-right:8px;" />
                        <el-input
                          v-model.number="p.value"
                          placeholder="Value"
                          style="margin-right:8px;"
                          type="number"
                          v-if="p.key==='max_tokens'||p.key==='top_p'||p.key==='top_k'||p.key==='temperature'"
                        />
                        <el-input
                          v-model="p.value"
                          placeholder="Value"
                          style="margin-right:8px;"
                          v-else
                        />
                        <el-button
                          size="small"
                          type="danger"
                          :icon="Minus"
                          @click="removeParam(item,i)"
                          circle
                        />
                      </div>
                      <!-- 添加按钮独占一行，放在下方 -->
                      <el-button
                        type="primary"
                        style="min-width: 150px; margin-left: auto"
                        @click="addParam(item)"
                      >添加参数</el-button>
                    </el-form-item>
                  </el-tab-pane>
                </el-tabs>
              </el-tab-pane>
            </el-tabs>
            <br />
            <el-divider>
              <h3>
                <b>模型参数</b>
              </h3>
            </el-divider>

            <el-form-item label="思考标识">
              <el-row :gutter="20">
                <el-col :span="12">
                  <el-input v-model="form.config.filter.head" placeholder="head" />
                </el-col>
                <el-col :span="12">
                  <el-input v-model="form.config.filter.tail" placeholder="tail" />
                </el-col>
              </el-row>
            </el-form-item>

            <br />

            <el-form-item>
              <el-button
                type="primary"
                @click="handleSubmit"
                style="min-width: 150px; margin-left: auto;"
              >提交</el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
* {
  box-sizing: border-box;
}

.edit-center-container {
  box-sizing: border-box;
  /* padding: 20px 28px; */
  background-color: rgb(245, 245, 245);
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  gap: 16px;
  overflow: hidden;
}

.pageTitle {
  flex: 0;
  color: #191919;
  font-size: 16px;
  font-weight: bold;
  font-family: "鸿蒙黑体", sans-serif;
}

.pageContent {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  gap: 16px;
  max-width: 100%;
  margin: 0 28px;
  background-color: white;
  border-radius: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 24px;
}

.title {
  flex: 0 0 1;
  margin: 0;
  font-size: 24px;
  font-weight: bold;
  border: none;
  box-shadow: none;
}

.panels {
  flex: 1 1 0;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: stretch;
  min-height: 0;
}

.panels .left-panel,
.panels .right-panel {
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  display: flex;
  justify-content: center;
}

.panels hr {
  width: 1px;
  height: 100%;
  margin: 0;
  background-color: rgb(216, 216, 216);
  outline: none;
  border: none;
}

.editTitleContainer {
  display: flex;
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  height: 50px;
  /* margin-left: 15px; */
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