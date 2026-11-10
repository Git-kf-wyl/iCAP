<template>
  <div @pointerover.passive="prefetchMenu" @focusin="prefetchMenu">
  <ReadCacheStatus v-if="token" />
  <login v-if="!token" :token_value="token" @update:token_value="handleUpdate"></login>
  <el-container v-else style="height: 100vh; display: flex; flex-direction: column;">
    <el-header v-show="!reportPreviewStore.isFullscreen" style="padding: 0; height: 80px; width: 100%;min-width: 500px;z-index: 1001;background-color: #fff; ">
      <div class="iconMenu" style="height: 80px;">
        <div style="display: flex; align-items: center; cursor: pointer; flex-shrink: 0;" @click="goToHome">
          <img
            style="width: 70px; height: 70px; margin-left: 30px"
            src="/images/netcore-mark-v1.png"
            alt="CloudCore Network"
          />
          <span class="iconMenuTitle">InnovationCore</span>
          <span class="iconMenuTitle">AI</span>
          <span class="iconMenuTitle">Platform</span>
        </div>

        <!-- Yellow navigation, shared authentication and local adapter -->
        <el-menu
          mode="horizontal"
          :ellipsis="false"
          :default-active="headActive"
          @select="handleNavSelect"
          class="headMenu"
        >
          <el-menu-item index="/" @click="goToHome" class="nav-item">首页</el-menu-item>
          <el-menu-item index="dataEval" @click="goToModule('dataEval')" class="nav-item">数据&amp;评测</el-menu-item>
          <el-menu-item index="maas" @click="goToModule('maas')" class="nav-item">MaaS服务</el-menu-item>
          <el-menu-item index="app" @click="goToModule('app')" class="nav-item">Agent应用</el-menu-item>
        </el-menu>

        <div style="margin-right: 20px; flex-shrink: 0;"><el-button link @click="router.push('/password/change')">账户安全</el-button>
          <!-- <el-tooltip content="权限设置" placement="top" effect="dark" v-if="!!auth.token">
            <el-button type="primary" link size="large" class="iconMenuButton" @click="manegeRight">
              <el-icon><Setting /></el-icon>
            </el-button>
          </el-tooltip> -->
          <el-tooltip content="意见反馈" placement="top" effect="dark">
            <el-button type="primary" link size="large" class="iconMenuButton" @click="feedback">
              <el-icon>
                <ChatDotSquare />
              </el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="平台Wiki" placement="top" effect="dark">
            <el-button type="primary" link size="large" class="iconMenuButton" @click="toWiki">
              <el-icon>
                <QuestionFilled />
              </el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="报告" placement="top" effect="dark">
            <el-dropdown placement="bottom" trigger="hover" @command="handleCommand" close-on-click-modal>
              <el-button class="iconMenuButton" link>
                <el-icon style="color:#409EFF">
                  <Tickets/>
                </el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="genarate">生成报告</el-dropdown-item>
                  <el-dropdown-item command="reported">已发布报告</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </el-tooltip>
          <el-tooltip content="用户登出" placement="top" effect="dark">
            <el-button type="primary" link size="large" style="width:100px" :loading="loggingOut" :disabled="loggingOut" @click="loginOut">
              <el-icon>
                <User />
              </el-icon>
              <span style="margin-left: 10px;">{{ token }}</span>
            </el-button>
          </el-tooltip>
        </div>
      </div>
    </el-header>
    <el-container style="flex: 1; display: flex;max-height:calc(100vh - 80px)">
      <el-aside
        v-show="!isHomePage && !isChatPage && !reportPreviewStore.isFullscreen"
        style="transition: width .2s cubic-bezier(.34,.69,.1,1);z-index: 1000;border-right: 1px solid rgb(230, 230, 230);"
        :style="{ width: currentWidth }"
      >
        <el-scrollbar>
          <el-menu
            :key="currentModule"
            :collapse="isCollapse"
            @open="handleOpen"
            @close="handleClose"
            style="height: 100%; transition: width .2s cubic-bezier(.34,.69,.1,1); border-right:0 !important;"
            router
            :collapse-transition="false"
            :default-active="activePath"
            :default-openeds="defaultOpeneds"
            @select="handleSelect"
          >
            <!-- <img
            style="width: 100%; height: auto;object-fit: cover; object-position: center; position: relative; left: 2px; top: 8px;"
            src="/images/icap-mark-v1.svg"
            alt="iCAP"
            />-->
              <!-- ===== MaaS服务 模块菜单 ===== -->
              <template v-if="currentModule === 'maas'">
                <el-menu-item index="/rankingScore" route="/rankingScore">
                  <el-icon><Histogram /></el-icon>
                  <span class="menuItem">模型榜单</span>
                </el-menu-item>
                <el-menu-item index="/modelSquare" route="/modelSquare">
                  <el-icon><Box /></el-icon>
                  <span class="menuItem">模型广场</span>
                </el-menu-item>
                <el-sub-menu index="/userStatistics" class="insideMenu">
                  <template #title>
                    <el-icon><Coin /></el-icon>
                    <span class="menuItem">运营看板</span>
                  </template>
                  <el-menu-item index="/userStatistics" route="/userStatistics">
                    <el-icon><Coin /></el-icon>
                    <span style="font-weight:500">用户运营</span>
                  </el-menu-item>
                  <el-menu-item index="/userStatistics/eval" route="/userStatistics/eval">
                    <el-icon><DataLine /></el-icon>
                    <span style="font-weight:500">评测运营</span>
                  </el-menu-item>
                  <el-menu-item index="/userStatistics/apikey" route="/userStatistics/apikey">
                    <el-icon><Key /></el-icon>
                    <span style="font-weight:500">API Key</span>
                  </el-menu-item>
                </el-sub-menu>
              </template>

              <!-- ===== 数据&评测 模块菜单 ===== -->
              <template v-if="currentModule === 'dataEval'">
                <el-menu-item index="/datasets/manage"><el-icon><Files /></el-icon><span class="menuItem">我的数据资源</span></el-menu-item>
                <el-sub-menu index="/dataCenter" class="insideMenu">
                  <template #title>
                    <el-icon><Coin /></el-icon>
                    <span class="menuItem">数据中心</span>
                  </template>
                  <el-menu-item index="/dataCenter/evalDatasetDevelopment" route="/dataCenter/evalDatasetDevelopment">
                    <el-icon><Coin /></el-icon>
                    <span style="font-weight:500">测试集仓库</span>
                  </el-menu-item>
                  <el-sub-menu index="/dataCenter/dataGovernance" class="insideMenu">
                    <template #title>
                      <el-icon><Management /></el-icon>
                      <span class="menuItem" style="font-weight: 500;">数据治理</span>
                    </template>
                    <el-sub-menu index="/dataCenter/dataGovernance/aisfCompanion" class="thirdLevelMenu">
                      <template #title>
                        <span class="thirdLevelTitle" style="font-weight: 700;">AISF-伴学</span>
                      </template>
                      <el-menu-item index="/dataCenter/datasetAnnotation" route="/dataCenter/datasetAnnotation">
                        <span style="font-weight:500; padding-left: 16px;">在线标注</span>
                      </el-menu-item>
                    </el-sub-menu>
                  </el-sub-menu>
                </el-sub-menu>
                <el-sub-menu index="/modelEvaluation" class="insideMenu">
                  <template #title>
                    <el-icon><DataLine /></el-icon>
                    <span class="menuItem">模型评测服务</span>
                  </template>
                  <el-menu-item index="/modelEvaluation/onlineAssessment" route="/modelEvaluation/onlineAssessment" v-if="!!auth.token">
                    <el-icon><DataBoard /></el-icon>
                    <span style="font-weight:500">任务列表</span>
                  </el-menu-item>
                  <el-menu-item index="/modelEvaluation/evaluationResult" route="/modelEvaluation/evaluationResult">
                    <el-icon><DataBoard /></el-icon>
                    <span style="font-weight:500">评测结果</span>
                  </el-menu-item>
                  <el-menu-item index="/modelEvaluation/onlineEvaluation" route="/modelEvaluation/onlineEvaluation" v-if="auth.role === 'admin'">
                    <el-icon><DataAnalysis /></el-icon>
                    <span style="font-weight:500">在线评估</span>
                  </el-menu-item>
                </el-sub-menu>
                <el-sub-menu index="/harnessEval" class="insideMenu">
                  <template #title>
                    <el-icon><Cpu /></el-icon>
                    <span class="menuItem">harness评测</span>
                  </template>
                  <el-menu-item index="/harnessEval/online" route="/harnessEval/online" v-if="!!auth.token">
                    <el-icon><DataBoard /></el-icon>
                    <span style="font-weight:500">harness在线评估</span>
                  </el-menu-item>
                </el-sub-menu>
                <el-sub-menu index="/agentEval" class="insideMenu">
                  <template #title>
                    <el-icon><Compass /></el-icon>
                    <span class="menuItem">agent评测服务</span>
                  </template>
                  <el-menu-item index="/agentcompass" route="/agentcompass">
                    <el-icon><DataAnalysis /></el-icon>
                    <span style="font-weight:500">agentCompass在线评估</span>
                  </el-menu-item>
                </el-sub-menu>
                <el-sub-menu index="/evalMap" class="insideMenu">
                  <template #title>
                    <el-icon><MapLocation /></el-icon>
                    <span class="menuItem">评测地图</span>
                  </template>
                  <el-menu-item index="/evalMap" route="/evalMap">
                    <el-icon><DataBoard /></el-icon>
                    <span style="font-weight:500">研究总览</span>
                  </el-menu-item>
                  <el-menu-item index="/evalMap/benchmarks" route="/evalMap/benchmarks">
                    <el-icon><Search /></el-icon>
                    <span style="font-weight:500">Benchmark 浏览器</span>
                  </el-menu-item>
                  <el-menu-item index="/evalMap/capabilities" route="/evalMap/capabilities">
                    <el-icon><Histogram /></el-icon>
                    <span style="font-weight:500">能力图谱</span>
                  </el-menu-item>
                  <el-menu-item index="/evalMap/vendors" route="/evalMap/vendors">
                    <el-icon><Coin /></el-icon>
                    <span style="font-weight:500">厂商关注</span>
                  </el-menu-item>
                  <el-menu-item index="/evalMap/compare" route="/evalMap/compare">
                    <el-icon><Connection /></el-icon>
                    <span style="font-weight:500">对比工作台</span>
                  </el-menu-item>
                  <el-menu-item index="/evalMap/methodology" route="/evalMap/methodology">
                    <el-icon><Setting /></el-icon>
                    <span style="font-weight:500">方法论与 SMART</span>
                  </el-menu-item>
                </el-sub-menu>
              </template>

              <!-- ===== Agent应用 模块菜单 ===== -->
              <template v-if="currentModule === 'app'">
                <el-menu-item index="/skill-evolution"><el-icon><MagicStick /></el-icon><span class="menuItem">Skill 自进化</span></el-menu-item>
                <el-menu-item index="/chat" route="/chat">
                  <el-icon><ChatDotSquare /></el-icon>
                  <span class="menuItem">Chat助手</span>
                </el-menu-item>
                <el-menu-item index="/agentCenter/deepSeekHarness" route="/agentCenter/deepSeekHarness">
                  <el-icon><DataAnalysis /></el-icon>
                  <span class="menuItem">DeepSeek Harness</span>
                </el-menu-item>
                <el-sub-menu index="/agentCenter/download" class="insideMenu">
                  <template #title>
                    <el-icon><Download /></el-icon>
                    <span class="menuItem">权重/数据高速下载</span>
                  </template>
                  <el-menu-item index="/dataCenter/huggingfaceDownload" route="/dataCenter/huggingfaceDownload">
                    <el-icon><Coin /></el-icon>
                    <span style="font-weight:500">HuggingFace</span>
                  </el-menu-item>
                  <el-menu-item index="/dataCenter/modelscopeDownload" route="/dataCenter/modelscopeDownload">
                    <el-icon><Coin /></el-icon>
                    <span style="font-weight:500">ModelScope</span>
                  </el-menu-item>
                </el-sub-menu>
                <el-sub-menu index="/agentCenter/paper" class="insideMenu">
                  <template #title>
                    <el-icon><Document /></el-icon>
                    <span class="menuItem">研究助手</span>
                  </template>
<el-menu-item index="research-insight" @click="openResearch('/paper-insight/')">论文洞察</el-menu-item>
<el-menu-item index="research-studio" @click="openResearch('/research-studio/')">科研工作室</el-menu-item>
                  <el-menu-item index="/agentCenter/paperAgent" route="/agentCenter/paperAgent">
                    <el-icon><Search /></el-icon>
                    <span style="font-weight:500">论文检索</span>
                  </el-menu-item>
                  <el-menu-item index="/agentCenter/hjfy" route="/agentCenter/hjfy">
                    <el-icon><Mic /></el-icon>
                    <span style="font-weight:500">论文翻译</span>
                  </el-menu-item>
                </el-sub-menu>
                <!-- PPT生成助手 已隐藏，后续再加回来 -->
                <!-- <el-menu-item index="/agentCenter/officeAssistant" route="/agentCenter/officeAssistant">
                  <el-icon><DataAnalysis /></el-icon>
                  <span class="menuItem">PPT生成助手</span>
                </el-menu-item> -->
                <!-- DeepResearch 已隐藏，后续再加回来 -->
                <!-- <el-menu-item index="/agentCenter/deepResearch" route="/agentCenter/deepResearch">
                  <el-icon><DataAnalysis /></el-icon>
                  <span class="menuItem">DeepResearch</span>
                </el-menu-item> -->
<!--                <el-menu-item index="/agentCenter/promptOptimizer" route="/agentCenter/promptOptimizer">-->
<!--                  <el-icon><EditPen /></el-icon>-->
<!--                  <span class="menuItem">Prompt优化器</span>-->
<!--                </el-menu-item>-->
              </template>

              <!-- ===== AI School 模块菜单 ===== -->
              

              <!-- ===== 数据治理Pipeline 模块菜单 ===== -->
              

             <el-menu-item @click="toggleCollapse">
               <template v-if="isCollapse">
                 <el-icon>
                   <Expand />
                 </el-icon>
               </template>
               <template v-else>
                 <el-icon>
                   <Fold />
                 </el-icon>
               </template>
               <span style="font-size: 16px; font-weight:500">收起导航</span>
             </el-menu-item>
          </el-menu>
        </el-scrollbar>
      </el-aside>
      <el-main style="padding: 0; min-width: 500px; flex: 1;height:100%">
        <router-view v-slot="{ Component, route: pageRoute }"><keep-alive :include="retainedPages" :max="5"><component :is="Component" :key="pageRoute.path" /></keep-alive></router-view>
      </el-main>
    </el-container>
  </el-container>
  <el-drawer
    v-model="drawer"
    title="意见反馈"
    :direction="direction"
    :before-close="handleDrawerClose"
    size="50%"
  >
    <el-button @click="showSubmitFeedback = true" type="primary" v-if="auth.role!=='admin'">提交反馈</el-button>
    <el-table :data="feedbackTableInfo" :header-cell-style="tableHeaderStyle">
      <el-table-column prop="id" label="提出时间" :formatter="formatTimestamp" align="center" />
      <el-table-column prop="content" label="反馈内容" align="center" show-overflow-tooltip />
      <el-table-column prop="status" label="处理状态" align="center">
        <template #default="{ row }">
          <el-tag
            :type="statusTagType(row.status)"
            size="large"
            style="width: 80px"
          >{{row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="userName" label="提出人" align="center" show-overflow-tooltip v-if="auth.role==='admin'"/>
      <el-table-column prop="result" label="结果反馈" align="center" show-overflow-tooltip />
      <el-table-column prop="endTime" label="闭环时间" :formatter="formatTimestamp" align="center" />
      <el-table-column label="操作" width="90px" align="center" v-if="auth.role==='admin'">
        <template #default="{ row }">
          <el-tooltip content="编辑" placement="top" v-if="!row.editing">
            <el-button link type="primary" size="large" @click="startEdit(row)">
              <el-icon>
                <Edit />
              </el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <el-button link type="primary" size="large" @click="handleDelete(row)">
              <el-icon>
                <Delete />
              </el-icon>
            </el-button>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>
    <el-dialog
      v-model="showSubmitFeedback"
      :title="isEdit ? '回应反馈' : '提交反馈'"
      @close="handleCloseFeedback"
    >
      <el-form>
        <el-form-item>
          <el-input
            type="textarea"
            v-model="feedbackContent"
            :placeholder="isEdit ? '请输入回应反馈内容' : '请输入提交反馈内容'"
            :rows="5"
          ></el-input>
        </el-form-item>
        <el-form-item label="状态变更：" v-if="isEdit">
          <el-select v-model="feedBackStstus" placeholder="可改变反馈状态">
            <el-option label="完成" value="completed" />
            <el-option label="否决" value="rejected" />
            <el-option label="处理中" value="processing" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSubmitFeedback = false">取消</el-button>
        <el-button type="primary" @click="feedbackSubmit">提交</el-button>
      </template>
    </el-dialog>
  </el-drawer>
  </div>
</template>

<script lang="ts" setup>
import {useAIModelStore} from "@/stores/aiModel.js";
import {computed, onMounted, ref, watch} from "vue";
import {retainedPages,prefetchMenu} from '@/fastRoutes.js';
import ReadCacheStatus from './ReadCacheStatus.vue';
import {
  Document,
  Menu as IconMenu,
  Location,
  Setting,
  Ticket,
  Key,
} from "@element-plus/icons-vue";
import { ElAside } from "element-plus";
import { useRoute, useRouter } from "vue-router";
import { Cpu, Tickets, ArrowDown, EditPen, ChatDotSquare, Search, Download, MapLocation } from "@element-plus/icons-vue";
import Login from "@/components/login.vue";
import { useAuth } from "@/blue/stores/auth.js";
import { userLogout } from "@/api/userMgr.js";
import { useStore } from "vuex";
import { useReportPreviewStore } from "@/stores/reportPreview.js";
import type { DrawerProps } from "element-plus";
import {
  getFeedbackInfo,
  modifyFeedbackInfo,
  deleteFeedbackInfo,
  registerFeedbackInfo,
} from "@/api/dataService.js";
import { ElMessage, ElMessageBox } from "element-plus";

const route = useRoute();
const router = useRouter();
const store = useStore();
const reportPreviewStore = useReportPreviewStore();
const auth = useAuth();
const token = computed(() => auth.token ? auth.username : '');
const isCollapse = ref(false);
const currentWidth = ref("200px");
const isPopupVisible = ref(false);

const currentModule = ref('maas');

// 当前用户是否创建过任务，用于决定是否展示“任务列表”菜单

// 根据路由 path 自动推导当前模块
function resolveModuleFromPath(path: string): string {
  if (path === '' || path === '/') return 'maas';
  if (path.startsWith('/skill-evolution')) return 'app';
  if (path.startsWith('/agentcompass')) return 'dataEval';
  if (path.startsWith('/datasets/manage')) return 'dataEval';
  if (path.startsWith('/harnessEval')) return 'dataEval';
  if (path.startsWith('/agentEval')) return 'dataEval';
  if (path.startsWith('/harnessBench')) return 'dataEval';
  if (path.startsWith('/chat')) return 'app'; // Chat助手归在Agent应用下
  if (path.startsWith('/agent') || path === '/dataCenter/huggingfaceDownload' || path === '/dataCenter/modelscopeDownload') return 'app';
  if (path.startsWith('/dataCenter') || path.startsWith('/modelEvaluation') || path.startsWith('/evalMap')) return 'dataEval';
  if (path.startsWith('/dataPipeline')) return 'dataPipeline'; // 数据治理Pipeline
  if (path.startsWith('/aiSchool')) return 'aiSchool';
  return 'maas';
}

/** 顶部导航高亮：首页/数据&评测/MaaS服务/Agent应用/AI School 各自对应固定 index */
const headActive = computed(() => {
  if (route.path === '/') return '/';
  if (currentModule.value === 'dataEval') return 'dataEval';
  if (currentModule.value === 'dataPipeline') return 'dataPipeline';
  if (currentModule.value === 'maas') return 'maas';
  if (currentModule.value === 'app') return 'app';
  if (currentModule.value === 'aiSchool') return 'aiSchool';
  return route.path;
});

const isHomePage = computed(() => route.path === "/");
// Chat助手现在位于Agent应用侧边栏中，应当显示侧边栏
const isChatPage = computed(() => false);

const goToHome = () => {
  currentModule.value = 'maas';
  router.push("/");
};

const openResearch = path => window.open('https://research.icapblue.com'+path,'_blank','noopener,noreferrer');
const goToChat = () => {
  currentModule.value = 'app';
  router.push("/chat");
};


onMounted(()=>{
  useAIModelStore().fetchModels();
  currentModule.value = resolveModuleFromPath(route.path);
})

// 监听路由变化自动同步模块，确保从首页跳转时左侧菜单正确切换
watch(() => route.path, (newPath) => {
  currentModule.value = resolveModuleFromPath(newPath);
});

const loggingOut = ref(false);
const loginOut = async () => {
  if (loggingOut.value) return;
  loggingOut.value = true;
  try {
    const revoked = await auth.logout();
    if (!revoked) ElMessage.warning('本地已退出，服务器会话注销未确认');
    location.assign('/login');
  } finally { loggingOut.value = false; }
}
const handleUpdate = () => auth.refreshProfile();

const handleOpen = (key: string, keyPath: string[]) => {
  // console.log(key, keyPath);
};
const handleClose = (key: string, keyPath: string[]) => {
  // console.log(key, keyPath);
};

const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value;
  const newValue = currentWidth.value === "200px" ? "64px" : "200px";
  setTimeout(() => {
    currentWidth.value = newValue;
  }, 0);
};

const validMenuPaths = [
  "/harnessEval",
  "/harnessEval/online",
  "/agentEval",
  "/agentcompass",
  "/evalMap",
  "/evalMap/benchmarks",
  "/evalMap/capabilities",
  "/evalMap/vendors",
  "/evalMap/compare",
  "/evalMap/methodology",
  "/rankingScore",
  "/modelEvaluation",
  "/modelEvaluation/modelProgress",
  "/modelEvaluation/onlineAssessment",
  "/modelEvaluation/evaluationResult",
  "/modelSquare",
  "/dataCenter",
  "/dataCenter/datasetDevelopment",
  "/dataCenter/datasetAnnotation",
  "/modelEvaluation/languageEvaluation",
  "/modelEvaluation/multipleEvaluation",
  "/modelEvaluation/evaluationResult",
  "/agentCenter/officeAssistant",
  "/agentCenter/deepResearch",
  "/agentCenter/promptOptimizer",
  "/agentCenter/deepSeekHarness",
  "/agentCenter/hjfy",
  "/agentCenter/paperAgent",
  "/dataCenter/huggingfaceDownload",
  "/dataCenter/modelscopeDownload",
  "/modelDeploy",
  "/aiSchool/ModelArchitecture",
  "/aiSchool/Desktop",
  "/aiSchool/Inference",
  // 数据治理Pipeline 模块
  "/dataPipeline",
  "/dataPipeline/home",
  "/dataPipeline/overview",
  "/dataPipeline/pipeline",
  "/dataPipeline/task-pool",
  "/dataPipeline/task-generation/generate",
  "/dataPipeline/task-generation/augmentation",
  "/dataPipeline/collection",
  "/dataPipeline/collection/phone-factory",
  "/dataPipeline/collection/tree-building",
  "/dataPipeline/quality",
  "/dataPipeline/correction",
  "/dataPipeline/correction/expert-action",
  "/dataPipeline/correction/cot-generation",
  "/dataPipeline/data-publishing/archive",
  "/dataPipeline/data-publishing/overview",
  "/dataPipeline/model-training",
  "/dataPipeline/model-training/data-mixture",
  "/dataPipeline/model-training/launch",
  "/dataPipeline/model-training/validation",
  "/dataPipeline/model-publishing",
  "/dataPipeline/model-iteration-evaluation",
  "/dataPipeline/scenario-studio",
  "/dataPipeline/phone-factory",
];

const activePath = computed(() => {
  const path = route.path;
  console.log("activePath", path);

  if (path === "" || path === "/") {
    return "";
  }

  // 如果当前路径直接匹配某个菜单项
  if (validMenuPaths.includes(path)) {
    return path;
  }

  // 分割路径（去掉空字符串）
  const segments = path.split("/").filter((s) => s !== "");
  let currentPath = "";
  for (let i = 0; i < segments.length; i++) {
    currentPath = "/" + segments.slice(0, i + 1).join("/");
    // 只检查前两级（即i=0和i=1）
    if (i >= 2) {
      break;
    }
    if (segments.length === 2 && validMenuPaths.includes(currentPath)) {
      return currentPath;
    } else if (i === 1 && validMenuPaths.includes(currentPath)) {
      return currentPath;
    }
  }

  return path;
});

const handleSelect = (index) => {
  // 点击侧边栏时同步切换模块
  if (index.startsWith('/agent') || index === '/dataCenter/huggingfaceDownload' || index === '/dataCenter/modelscopeDownload' || index === '/chat') {
    currentModule.value = 'app';
  } else if (index === '/modelDeploy') {
    currentModule.value = 'maas';
  } else if (index.startsWith('/dataCenter') || index.startsWith('/modelEvaluation') || index.startsWith('/evalMap')) {
    currentModule.value = 'dataEval';
  } else if (index.startsWith('/dataPipeline')) {
    currentModule.value = 'dataPipeline';
  } else if (index.startsWith('/aiSchool')) {
    currentModule.value = 'aiSchool';
  } else {
    currentModule.value = 'maas';
  }

  if (index === "/rankingScore") {
    store.dispatch("rankingScore/updateActiveTab", "ruler1");
    store.dispatch("rankingScore/updateActiveSphereTab", "operations");
  } else if (index === "/modelEvaluation/onlineAssessment") {
    store.dispatch("taskTable/updatePageNum", 1);
  } else if (index === "/dataCenter/datasetDevelopment") {
    store.dispatch("updateTags", []);
    store.dispatch("updateScreeningType", "all");
  } else if (index === "/dataCenter/evalDatasetDevelopment") {
    // 从可视化布局进入测试集仓库时，重置为默认卡片模式
    store.dispatch("updateViewMode", "card");
  } else if (index === "/modelSquare") {
    store.dispatch("updateSelectedCategories", []);
    store.dispatch("updateSelectedTags", []);
    store.dispatch("updateSelectedSizeRange", {
      label: "全部",
      min: 0,
      max: Infinity,
    });
    store.dispatch("updateDeployType", "all");
  }
};

const defaultOpeneds = computed<string[]>(() => {
  if (currentModule.value === 'maas') {
    return [];
  } else if (currentModule.value === 'dataEval') {
    return ["/modelEvaluation", "/dataCenter", "/evalMap"];
  } else if (currentModule.value === 'app') {
    return ["/agentCenter/download", "/agentCenter/paper"];
  } else if (currentModule.value === 'dataPipeline') {
    return ["/dataPipeline/task-pool", "/dataPipeline/collection", "/dataPipeline/correction", "/dataPipeline/model-training"];
  } else if (currentModule.value === 'aiSchool') {
    return [];
  }
  return [];
});

const toWiki = () => {
  router.push('/operations');
};

const manegeRight = () =>{

}

const drawer = ref(false);
const showSubmitFeedback = ref(false);

const feedback = async () => {
  const res = await getFeedbackInfo({
    userName: token.value,
  });
  const data = res.data;

  feedbackTableInfo.value = data;

  drawer.value = true;
};

const handleDrawerClose = () => {
  drawer.value = false;
};

const direction = ref<DrawerProps["direction"]>("rtl");

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
  fontSize: "14px",
};

const feedbackTableInfo = ref([]);

const statusTagType = (status) => {
  switch (status) {
    case "completed":
      return "success";
    case "processing":
      return "primary";
    case "rejected":
      return "danger";
    default:
      return "warning";
  }
};

const feedbackContent = ref("");

const handleCloseFeedback = () => {
  feedbackContent.value = "";
  isEdit.value = false;
};

const content = ref("");
const feedBackStstus = ref("");
const editID = ref("");
const currentUserName = ref("");

const feedbackSubmit = () => {
  if (isEdit.value) {
    modifyFeedbackInfo({
      content: content.value,
      result: feedbackContent.value,
      status: feedBackStstus.value,
      id: editID.value,
      userName: currentUserName.value,
    }).then(
      (res) => {
        showSubmitFeedback.value = false;
        feedback();
        if (res.data.status === "failed") {
          ElMessage({
            type: "error",
            message: "编辑失败：" + res.data.res,
          });
          return;
        }
      },
      (err) => {
        ElMessage({
          type: "error",
          message: "编辑失败：" + err.data.res,
        });
        return;
      }
    );
  } else {
    registerFeedbackInfo({
      content: feedbackContent.value,
      status: "processing",
      result: "",
      userName: localStorage.getItem('username'),
    }).then(
      (res) => {
        showSubmitFeedback.value = false;
        feedback();
        if (res.data.status === "failed") {
          ElMessage({
            type: "error",
            message: "新增失败：" + res.data.res,
          });
          return;
        }
      },
      (err) => {
        ElMessage({
          type: "error",
          message: "新增失败：" + err.data.res,
        });
        return;
      }
    );
  }
};

const isEdit = ref(false);

const startEdit = (row) => {
  isEdit.value = true;
  showSubmitFeedback.value = true;
  content.value = row.content;
  feedBackStstus.value = row.status;
  feedbackContent.value = row.content;
  editID.value = row.id;
  currentUserName.value = row.userName;
};

const handleDelete = async (row) => {
  ElMessageBox.confirm(`确定要删除序号为 ${row.id} 的数据项吗？`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning",
  })
    .then(() => {
      // 执行删除操作
      deleteFeedbackInfo([row.id]).then(
        (res) => {
          feedback();
          if (res.data.status === "failed") {
            ElMessage({
              type: "error",
              message: "删除失败：" + res.data.res,
            });
            return;
          }
        },
        (err) => {
          ElMessage({
            type: "error",
            message: "删除失败：" + err.data.res,
          });
          return;
        }
      );
      ElMessage({
        type: "success",
        message: "删除成功",
      });
    })
    .catch(() => {});
};

const formatTimestamp = (row, column, timestamp) => {
  if (!timestamp) return "-";
  // 将13位时间戳转换为Date对象
  const date = new Date(Number(timestamp));
  // 格式化为 YYYY-MM-DD HH:mm:ss
  return date
    .toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false, // 24小时制
    })
    .replace(/\//g, "-"); // 将斜杠替换为短横};
};

const handleCommand = (command: string | number | object) => {
  switch (command) {
    case "genarate":
      router.push("/EvaluationReport");
      break;
    case 'reported':
      router.push("/PublishedReport");
      break;
    default:
      router.push("/EvaluationReport");
  }
};

/** 顶部导航一级入口点击：切换模块并跳转到对应首页 */
const goToModule = (module: string) => {
  currentModule.value = module;
  if (module === 'maas') {
    router.push('/modelSquare');
  } else if (module === 'app') {
    // 默认进入 Chat 助手页面
    router.push('/chat');
  } else if (module === 'dataEval') {
    // 从可视化布局进入测试集仓库时，重置为默认卡片模式
    store.dispatch("updateViewMode", "card");
    router.push('/dataCenter/evalDatasetDevelopment');
  } else if (module === 'aiSchool') {
    router.push('/aiSchool/ModelArchitecture');
  } else if (module === 'dataPipeline') {
    router.push('/dataPipeline/home');
  }
};

/** 顶部 el-menu 选中时同步触发 sidebar 的 store 逻辑 */
const handleNavSelect = (index: string) => {
  // 根据选中的路由自动切换模块
  const path = index;
  if (path === 'dataEval') {
    currentModule.value = 'dataEval';
  } else if (path === 'maas') {
    currentModule.value = 'maas';
  } else if (path === 'app') {
    currentModule.value = 'app';
  } else if (path === 'aiSchool') {
    currentModule.value = 'aiSchool';
  } else if (path === 'dataPipeline') {
    currentModule.value = 'dataPipeline';
  } else if (path === '/' || path.startsWith('/')) {
    currentModule.value = resolveModuleFromPath(path);
  }
  // 复用已有的 handleSelect 逻辑，与 sidebar 保持一致的 store 操作
  handleSelect(index);
};

/** 导航栏 dropdown 命令：直接跳转到对应路由 */
const navCommand = (path: string) => {
  router.push(path);
};
</script>

<style>

.popup {
  position: fixed;
  top: 20%;
  left: 30%;
  transform: translate(-20%, -20%);
  width: 270px;
  height: 80px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s;
}
.fade-enter, .fade-leave-to /* .fade-leave-active in <2.1.8 */ {
  opacity: 0;
}

body {
  margin: 0;
}

/* 调整菜单行间距 */
.el-menu {
  --el-menu-item-height: 52px;
  --el-menu-sub-item-height: 42px;
}

/* 一级目录 - 保持原有字体大小 */
.menuItem {
  margin-left: 0px;
  display: block;
  text-align: left;
  font-size: 14px;
  align-items: center;
  font-style: normal;
  font-weight: 600;
  /* 减少行高来缩小行间距 */
  line-height: 1.3;
  /* font-family: '仿宋' */
}

/* 二级目录 - 稍微缩小字体 */
.el-sub-menu .el-menu-item {
  font-size: 13px;
  line-height: 1.3;
}

/* 三级目录 - 继续缩小字体，并增加左侧边距 */
.el-sub-menu .el-sub-menu .el-menu-item {
  font-size: 12px;
  padding-left: 60px !important;
  line-height: 1.3;
}

/* 三级菜单标题（AISF-伴学 / AISF-GUI操控） */
.thirdLevelMenu .thirdLevelTitle {
  font-size: 13px !important;
}

/* 三级菜单自身行间距 */
.thirdLevelMenu {
  --el-menu-sub-item-height: 36px !important;
}

/* 四级菜单项 - 缩进 */
.thirdLevelMenu .el-menu-item {
  font-size: 12px !important;
  padding-left: 80px !important;
  --el-menu-item-height: 34px !important;
}

.el-menu-item * {
  vertical-align: middle;
}

#title {
}

.iconMenu {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

/* 导航菜单居中容器 */
.iconMenu > .el-menu.headMenu {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  margin-left: 0;
}

.iconMenuTitle {
  margin-left: 5px;
  font-weight: 700;
  /* font-size:20px; */
  /* font-family:"华文隶书" */
}

.iconMenuTitle::first-letter{
  color:rgb(86, 89, 219);
}

.iconMenuButton {
  width: 50px;
  font-size: 18px;
}

.iconMenuButton .el-icon {
  font-size: 18px;
  width: 18px;
  height: 18px;
}

.iconMenuButton .el-icon svg {
  width: 18px !important;
  height: 18px !important;
}

.el-menu.el-menu--horizontal {
  border-bottom: none !important;
  background: transparent;
}

.el-menu--horizontal .el-menu-item,
.el-menu--horizontal .el-sub-menu__title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  background: transparent !important;
  height: 60px;
  line-height: 60px;
}

/* 导航菜单项 */
.nav-item {
  font-size: 18px !important;
  padding: 0 20px !important;
}

.headMenu{
  margin-left: auto;
}

.el-menu--horizontal .el-menu--popup{
  min-width: 120px !important;
}

.el-menu{
  background-color: transparent;
}
</style>
