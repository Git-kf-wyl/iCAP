<template>
  <div class="home-page">
    <!-- ==================== Section 1: 走马灯 ==================== -->
    <div class="block text-center">
      <el-carousel height="300px" motion-blur :interval="8000" indicator-position="outside">
        <el-carousel-item v-for="(slide, index) in carouselSlides" :key="index">
          <div class="carousel-slide" @click="navigateTo(slide.path)">
            <span v-if="index === 1" class="imageReportName">{{reportName}}</span>
            <img :src="slide.image" :alt="slide.title" class="carousel-image" />
          </div>
        </el-carousel-item>
      </el-carousel>
    </div>
    <div class="hero-section">
      <div class="hero-content">
        <h1 class="hero-title">云核心网 AI 创新平台</h1>
        <p class="hero-subtitle">打造易用的通用MaaS、办公助手、测评服务 一体化平台，助力核心网AI应用创新</p>
      </div>
    </div>

    <div style="margin: 0 15%;">
      <!-- ==================== Section 2: 业务功能卡片 ==================== -->
      <div class="cards-section">
        <div
          v-for="card in functionCards"
          :key="card.path"
          class="function-card"
          @click="navigateTo(card.path)"
        >
          <div class="card-icon-wrapper" :style="{ background: card.bgColor }">
            <el-icon :size="iconSize" color="#fff">
              <component :is="card.icon" />
            </el-icon>
          </div>
          <div style="display: flex;flex-direction: column;">
            <span class="card-title">{{ card.title }}</span>
            <span class="card-desc">{{ card.desc }}</span>
          </div>
        </div>
      </div>

      <div style="margin: 30px 0;"></div>

      <!-- ==================== Section 3: 均分柱状图 ==================== -->
      <!-- 尺子一：通用榜单（合并为一个卡片，内部用横线分隔） -->
      <div class="ruler1-section">
        <div class="ruler1-header">
          <div class="section-header-left">
            <span class="section-header-title">尺子一：通用榜单</span>
            <span class="section-header-sub">基于权威开源评测集的实测结果，发布覆盖文本，视觉和音频的模型通用能力排行榜</span>
          </div>
          <el-button link type="primary" @click="goToRanking('llm')">查看全部 &gt;</el-button>
        </div>
        <div ref="ruler1SectionRef" class="ruler1-body">
          <!-- 大语言模型均分柱状图 -->
          <div class="ruler1-chart-item">
            <div class="chart-header">
              <div class="panel-header">
                <span class="panel-title">大语言模型排行</span>
              </div>
              <div
                class="header-information"
              >测试集包括MMLU-REDUX,AIME2026,LiveCodeBench,GPQA_Diamond,IF-Eval，根据各测试集实测分数取平均进行排名</div>
            </div>
            <div class="chart-wrapper" v-loading="llmLoading">
              <rankingScoreBarChart :data="llmChartData" title />
            </div>
          </div>

          <!-- 视觉模型均分柱状图 -->
          <div class="ruler1-chart-item ruler1-chart-item--mid">
            <div class="chart-header">
              <div class="panel-header">
                <span class="panel-title">视觉模型排行</span>
              </div>
              <div class="header-information">测试集包括MMMU,MMStar,Video-MME，根据各测试集实测分数取平均进行排名</div>
            </div>
            <div class="chart-wrapper" v-loading="visionLoading">
              <rankingScoreBarChart :data="visionChartData" title />
            </div>
          </div>

          <!-- 音频模型均分柱状图 -->
          <div class="ruler1-chart-item ruler1-chart-item--mid">
            <div class="chart-header">
              <div class="panel-header">
                <span class="panel-title">音频模型排行</span>
              </div>
              <div class="header-information">测试集包括MMAU,MMAR,WorldSense，根据各测试集实测分数取平均进行排名</div>
            </div>
            <div class="chart-wrapper" v-loading="audioLoading">
              <rankingScoreBarChart :data="audioChartData" title />
            </div>
          </div>

          <!-- Agent模型均分柱状图 -->
          <div class="ruler1-chart-item">
            <div class="chart-header">
              <div class="panel-header">
                <span class="panel-title">Agent模型排行</span>
              </div>
              <div class="header-information">测试集包括tau3_bench,mcp_atlas,terminal_bench2.1,claw_eval，根据各测试集实测分数取平均进行排名</div>
            </div>
            <div class="chart-wrapper" v-loading="agentLoading">
              <rankingScoreBarChart :data="agentChartData" title />
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== Section 4: 尺子二榜单（锚点 + 柱状图） ==================== -->
      <div class="ruler2-section">
        <div class="ruler2-header">
          <div class="section-header-left">
            <span class="panel-title">尺子二：领域榜单</span>
            <span class="section-header-sub">发布覆盖AISF各领域模型能力排行榜，其他业务领域可按需接入平台</span>
          </div>
          <el-button link type="primary" @click="goToRuler2Ranking">查看全部 &gt;</el-button>
        </div>
        <div class="ruler2-body" v-loading="ruler2Loading">
          <!-- 左侧锚点导航 -->
          <div class="ruler2-anchor-col">
            <el-affix :offset="100">
              <el-anchor :container="mainContainerRef" :offset="20">
                <el-anchor-link>
                  <span style="font-weight: 700;">AISF</span>
                  <template #sub-link>
                    <el-anchor-link
                      v-for="cat in ruler2SubCategoryList"
                      :key="cat.key"
                      :href="'#' + cat.key"
                    >{{ cat.label }}</el-anchor-link>
                  </template>
                </el-anchor-link>
              </el-anchor>
            </el-affix>
          </div>
          <!-- 右侧柱状图列表（两列网格） -->
          <div class="ruler2-charts-col" ref="mainContainerRef">
            <div class="ruler2-charts-grid" ref="ruler2GridRef">
              <div
                v-for="cat in ruler2SubCategoryList"
                :key="cat.key"
                :id="cat.key"
                ref="ruler2ChartItemRefs"
                class="ruler2-chart-item"
              >
                <div class="ruler2-chart-header-area">
                  <div
                    class="ruler2-chart-title"
                    @click="goToRuler2SubCategory(cat.key)"
                  >{{ cat.label }}</div>
                  <div class="header-information">{{cat.desc}}</div>
                </div>
                <div class="ruler2-chart-wrapper">
                  <rankingScoreBarChart :data="getRuler2ChartData(cat.key)" :title="''" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onBeforeUnmount, computed, nextTick, defineAsyncComponent } from "vue";
import { useRouter } from "vue-router";
import {
  Promotion,
  ChatSquare,
  Histogram,
  Connection,
  Coin,
  Box,
  DataLine,
  DataAnalysis,
  Tickets,
} from "@element-plus/icons-vue";
import { getCurrentFullRes, getMultiModelData } from "@/api/dataService.js";
import { getAllPublishedTasks } from "@/api/runService.js";
import { useStore } from "vuex";
const rankingScoreBarChart = defineAsyncComponent(() => import("@/charts/rankingScoreBarChart.vue"));
import { ModelService } from "@/services/modelService.js";
import { useReportPreviewStore } from "@/stores/reportPreview.js";

const reportPreviewStore = useReportPreviewStore();

const setFullscreen = (val) => {
  reportPreviewStore.setFullscreen(val);
};

const router = useRouter();
const store = useStore();

// ===================== 业务功能卡片 =====================
const functionCards = [
  //   {
  //     title: "模型对话",
  //     desc: "在线体验模型对话能力",
  //     path: "/experienceCenter/textConversation",
  //     icon: ChatSquare,
  //     bgColor: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  //   },
  {
    title: "模型榜单",
    desc: "两把尺子评估结果汇总",
    path: "/rankingScore",
    icon: Histogram,
    bgColor: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
  },
  {
    title: "评测集管理",
    desc: "尺子一与尺子二的评测集在线管理",
    path: "/dataCenter/evalDatasetDevelopment",
    icon: Coin,
    bgColor: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  },
  {
    title: "评估报告",
    desc: "查看已发布的模型评估报告",
    path: "/PublishedReport",
    icon: Tickets,
    bgColor: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
  },
  //   {
  //     title: "模型选型",
  //     desc: "智能推荐最优模型",
  //     path: "/modelSelection",
  //     icon: Connection,
  //     bgColor: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
  //   },
  //   {
  //     title: "数据中心",
  //     desc: "管理训练与评测数据集",
  //     path: "/dataCenter/evalDatasetDevelopment",
  //     icon: Coin,
  //     bgColor: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
  //   },
  //   {
  //     title: "模型广场",
  //     desc: "浏览注册模型库",
  //     path: "/modelSquare",
  //     icon: Box,
  //     bgColor: "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
  //   },
  {
    title: "办公助手",
    desc: "PPT生成/权重下载/论文翻译...",
    path: "/dataCenter/huggingfaceDownload",
    icon: DataAnalysis,
    bgColor: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  },
];

// ===================== 轮播图配置 =====================
import imgNewModel from "@/assets/1_new_model.png";
import imgEvalReport from "@/assets/2_eval_report.png";

const carouselSlides = [
  {
    image: imgNewModel,
    title: "模型广场",
    path: "/modelSquare",
  },
  {
    image: imgEvalReport,
    title: "评估报告",
    path: "/PublishedReport/preview",
  },
];

const reportName = ref("");
const latestReportId = ref<number | null>(null);

const navigateTo = async (path: string) => {
  // 评估报告：跳转到最新发布报告的预览页
  if (path === "/PublishedReport/preview") {
    if (latestReportId.value !== null) {
      setFullscreen(true);
      router.push({
        name: "ReportPreview",
        query: { id: latestReportId.value },
      });
    } else {
      // 无缓存数据时回退到列表页
      router.push(path);
    }
    return;
  }
  router.push(path);
};

// ===================== 响应式尺寸 =====================
const iconSize = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  updateFlag.value; // 依赖 resize 重新计算
  const w = window.innerWidth;
  if (w < 768) return 18;
  if (w < 1200) return 22;
  return 28;
});

// 窗口 resize 时重新计算
const updateFlag = ref(0);
const onResize = () => {
  updateFlag.value++;
  syncHeaderHeights();
};
window.addEventListener("resize", onResize);
onBeforeUnmount(() => window.removeEventListener("resize", onResize));

// ===================== 大语言模型数据 =====================
const LLM_DATASET_KEYS = [
  "mmlu_redux",
  "aime26",
  "live_code_bench",
  "gpqa",
  "ifeval",
];
const VISION_DATASET_KEYS = ["MMMU", "MMStar", "Video-MME"];
const AUDIO_DATASET_KEYS = ["MMAU", "MMAR", "WorldSense"];
// Agent 测试集（与 rankingScore.vue 保持一致）
const AGENT_DATASET_KEYS = [
  "tau3_bench",
  "mcp_atlas",
  "terminal_bench2.1",
  "claw_eval",
];

// ============= 白名单（与 rankingScore.vue 保持一致） =============
const LLM_WHITELIST = new Set([
  "Qwen3-235B-A22B-Thinking-2507",
  "Qwen3-30B-A3B-Thinking-2507",
  "Qwen3-32B",
  "Qwen3-14B",
  "Qwen3-8B",
  "Qwen3.5-397B-A17B",
  "Qwen3.5-122B-A10B",
  "Qwen3.5-35B-A3B",
  "Qwen3.5-27B",
  "Qwen3.5-9B",
  "Qwen3.5-4B",
  "Qwen3.6-35B-A3B",
  "Qwen3.6-27B",
  "Qwen3.8-27B",
  "DeepSeek-V3.2",
  "DeepSeek-V4-Flash",
  "DeepSeek-V4-Pro",
  "gemma-4-12B",
]);

const VISION_WHITELIST = new Set([
  "Qwen3.5-397B-A17B",
  "Qwen3.5-122B-A10B",
  "Qwen3.5-35B-A3B",
  "Qwen3.5-27B",
  "Qwen3.5-9B",
  "Qwen3.5-4B",
  "Qwen3.6-35B-A3B",
  "Qwen3.6-27B",
  "Qwen3.8-27B",
  "Qwen3-VL-235B-A22B-Thinking",
  "Qwen3-VL-30B-A3B-Thinking",
  "Qwen3-VL-8B-Thinking",
  "Qwen3-VL-4B-Thinking",
  "Qwen3-VL-32B-Thinking",
  "gemma-4-12B",
]);

const AUDIO_WHITELIST = new Set([
  "Qwen3-Omni-30B-A3B-Instruct",
  "Qwen2.5-Omni-7B",
]);

const llmRawData = ref({});
const visionRawData = ref({});
const audioRawData = ref({});
const llmLoading = ref(true);
const visionLoading = ref(true);
const audioLoading = ref(true);
const agentLoading = ref(true);

// ===================== 尺子二数据 =====================
const mainContainerRef = ref(null);
const ruler2RawData = ref({});
const ruler2Loading = ref(true);

// ===== 头部高度同步 =====
const ruler1SectionRef = ref(null);
const ruler2GridRef = ref(null);
const ruler2ChartItemRefs = ref([]);

function syncHeaderHeights() {
  // 尺子一：每行 3 个 chart-header 等高
  if (ruler1SectionRef.value) {
    const headers = ruler1SectionRef.value.querySelectorAll('.chart-header');
    if (headers.length) {
      let maxH = 0;
      headers.forEach((h: HTMLElement) => {
        maxH = Math.max(maxH, h.scrollHeight);
      });
      headers.forEach((h: HTMLElement) => {
        h.style.minHeight = maxH + 'px';
        h.style.boxSizing = 'border-box';
      });
    }
  }

  // 尺子二：每行 2 个 ruler2-chart-header-area 等高
  // 按 grid 的实际布局分组（每行2个）
  if (ruler2GridRef.value && ruler2ChartItemRefs.value.length) {
    const gridWidth = ruler2GridRef.value.getBoundingClientRect().width;
    const items = ruler2ChartItemRefs.value;
    // 获取 grid 列宽信息（用第一列宽度判断一行能放几个）
    const gridComputed = getComputedStyle(ruler2GridRef.value);
    const gridColWidth = parseFloat(gridComputed.getPropertyValue('grid-template-columns').split(' ')[0]);
    const gap = parseFloat(gridComputed.gap) || 24;
    const colsPerRow = Math.floor((gridWidth + gap) / (gridColWidth + gap));

    // 按行分组
    const rows: HTMLElement[][] = [];
    let currentRow: HTMLElement[] = [];
    items.forEach((item, idx) => {
      currentRow.push(item);
      if (currentRow.length === colsPerRow || idx === items.length - 1) {
        rows.push(currentRow);
        currentRow = [];
      }
    });

    rows.forEach((row) => {
      const headers = row.map((el) =>
        el.querySelector?.('.ruler2-chart-header-area')
      ).filter(Boolean);
      if (headers.length > 1) {
        const maxH = Math.max(...headers.map((h) => h.scrollHeight));
        headers.forEach((h) => {
          h.style.minHeight = maxH + 'px';
          h.style.boxSizing = 'border-box';
        });
      }
    });
  }
}

// 尺子二子类别列表（固定配置，与 rankingScore.vue 一致）
const ruler2SubCategoryList = [
  {
    key: "aisf_banxue_attention",
    label: "伴学注意力检测",
    desc: "注意力检测测试集：通过控制设备摆放、光照、遮挡、人数等环境变量，覆盖儿童在单种及多种注意力状态下的多维度组合场景，评估系统对注意力行为的识别准确率。根据排除注意力检测预期结果为遮挡和其他(无效用例)后计算的准确率进行排名。",
  },
  {
    key: "aisf_banxue_posture",
    label: "伴学坐姿检测",
    desc: "在同样的环境变量干扰下，覆盖儿童单种及多种坐姿异常状态，并结合异常行为，评估系统对坐姿姿态的识别准确率。根据排除以下子场景计算的准确率进行排名：a.注意力小类-单次结果取值为遮挡、其他（无效用例）b.坐姿小类 取值为 遮挡、其他、无（无效用例）c.实际注意力小类取值为'睡觉','玩电子设备','使用电子设备','玩玩具','吃零食','离座' d.实际注意力小类取值为'东张西望'并且实际坐姿小类取值不是'仰头'、'仰躺'",
  },
  {
    key: "aisf_llm_gaixie",
    label: "改写",
    desc: "分别对是否进行fewshot外挂说明（指模型外部连接存储fewshot的数据库，根据用户问题检索对应few shot，并和用户问题合并输入模型）进行测试，对结果取均分进行排名",
  },
  {
    key: "aisf_llm_yitu",
    label: "意图",
    desc: "基于意图个数（1~3），并在多意图上叠加依赖分析，覆盖已有的各类skill，构建800条测试集，对各个意图数量（1~3）的测评结果取平均进行排名",
  },
  {
    key: "aisf_memory_cuiqu",
    label: "记忆萃取",
    desc: "通过从对话中提取8类正例（身份、偏好、关系等）并排除6类反例（问句、指令、一次性事件等），结合8条边界规则及5种更新操作（覆盖重复、共存、冲突、无关及混合场景），评估模型对用户长期画像记忆的准确提取与动态更新能力。",
  },
  {
    key: "aisf_memory_zhaohui",
    label: "记忆召回",
    desc: "通过判定查询是否需要调用记忆（6类黑名单 vs 8类白名单），并对多层级匹配（精确匹配、语义相关、多维度独立匹配）及去重逻辑进行分层测试，评估模型从记忆列表中精准筛选出与查询相关的用户记忆的能力。",
  },
  {
    key: "aisf_gui_plan",
    label: "VLM(GUI操控规划)",
    desc: "选择影音视频、安装运维、短视频等场景的12个常用APP构建，每个细分场景分别构建难、中、易用例各3个，总计300个用例，进行测评。本榜单用于评测GUI Agent中的操控规划模型，根据 (成功+部分成功)/任务总数 进行排名",
  },
  {
    key: "aisf_gui_vla",
    label: "VLA(GUI操控执行)",
    desc: "选择影音视频、安装运维、短视频等场景的12个常用APP构建，每个细分场景分别构建难、中、易用例各3个，总计300个用例，进行测评。本榜单用于评测GUI Agent中的操控执行模型，根据 (成功+部分成功)/任务总数 进行排名",
  },
  {
    key: "aisf_llm_skilltican",
    label: "skill提参",
    desc: "暂无",
  },
  {
    key: "aisf_llm_guican",
    label: "GUI提参",
    desc: "评估模型根据GUI界面生成语料进行提参的能力",
  },
  {
    key: "aisf_llm_banxue",
    label: "伴学提参",
    desc: "评估模型在伴学场景下进行提参的能力",
  },
  {
    key: "aisf_llm_coordinator",
    label: "Coordinator",
    desc: "评估Coordinator模型调度各技能并生成上下文的能力",
  },
];

// 从 ruler2 数据中提取指定子类别 top10
// 对 aisf_banxue_attention / aisf_banxue_posture，需从 aisf_banxue 的 subsets 中提取子项分数
const BANXUE_SUBSET_MAP: Record<string, string> = {
  aisf_banxue_attention: "注意力检测",
  aisf_banxue_posture: "坐姿检测",
};

function getRuler2Top10(
  ruler2Raw: Record<string, any>,
  subKey: string
): { name: string; value: number }[] {
  const rows: { name: string; value: number }[] = [];
  // 判断是否需要从 banxue 的 subsets 中取子项分数
  const subSetName = BANXUE_SUBSET_MAP[subKey];
  const actualDatasetName = subSetName ? "aisf_banxue" : subKey;

  Object.entries(ruler2Raw).forEach(
    ([modelName, modelGroup]: [string, any]) => {
      const matched = (modelGroup?.result || []).find(
        (item: any) => item.dataset_name === actualDatasetName
      );
      if (!matched) return;

      let avgScore: number | null = null;

      if (subSetName) {
        // 从 subsets 中提取对应子项的 score
        const subsets = matched?.metrics?.[0]?.categories?.[0]?.subsets || [];
        const subItem = subsets.find((s: any) => s.name === subSetName);
        avgScore = subItem?.score != null ? Number(subItem.score) : null;
      } else {
        avgScore = matched.score != null ? Number(matched.score) : null;
      }

      if (avgScore == null) return;
      rows.push({ name: modelName, value: avgScore, color: ModelService.getModelColor(modelName) });
    }
  );
  rows.sort((a, b) => b.value - a.value);
  return rows.slice(0, 10);
}

function getRuler2ChartData(subKey: string): { name: string; value: number }[] {
  return getRuler2Top10(ruler2RawData.value, subKey);
}

function processRuler1RowWithWhitelist(
  modelName: string,
  modelGroup: any,
  datasetKeys: string[],
  whitelist: Set<string>
): { name: string; value: number | null; isPending: boolean } | null {
  const result = modelGroup?.result || [];
  let scoreSum = 0;
  let scoreCount = 0;
  const scores: Record<string, number | null> = {};
  datasetKeys.forEach((dsKey) => {
    const matched = result.find((item: any) => item.dataset_name === dsKey);
    if (matched && matched.score != null) {
      scores[dsKey] = matched.score;
      scoreSum += matched.score;
      scoreCount++;
    } else {
      scores[dsKey] = null;
    }
  });
  const avg = scoreCount > 0 ? scoreSum / scoreCount : null;

  if (whitelist.has(modelName)) {
    const allHaveScores = datasetKeys.every((dsKey) => scores[dsKey] != null);
    if (!allHaveScores) {
      // 白名单中但分数不全 → 标记为"评测中"
      return { name: modelName, value: null, isPending: true };
    }
  } else {
    const allHaveScores = datasetKeys.every((dsKey) => scores[dsKey] != null);
    if (!allHaveScores) return null; // 不在白名单且分数不全 → 过滤
  }
  return { name: modelName, value: avg, isPending: false };
}

function filterTop10WithWhitelist(
  rawObj: Record<string, any>,
  datasetKeys: string[],
  whitelist: Set<string>
): { name: string; value: number }[] {
  const rows: { name: string; value: number | null; isPending: boolean }[] = [];
  Object.entries(rawObj).forEach(([modelName, modelGroup]) => {
    const row = processRuler1RowWithWhitelist(
      modelName,
      modelGroup,
      datasetKeys,
      whitelist
    );
    if (row) rows.push(row);
  });
  // 排序：评测中排最前（不参与展示），其余按均分降序
  rows.sort((a, b) => {
    if (a.isPending && !b.isPending) return -1;
    if (!a.isPending && b.isPending) return 1;
    const avgA = a.value != null ? a.value : -1;
    const avgB = b.value != null ? b.value : -1;
    return avgB - avgA;
  });
  return rows
    .filter((r) => !r.isPending && r.value != null)
    .slice(0, 10)
    .map((r) => ({ name: r.name, value: r.value!, color: ModelService.getModelColor(r.name) }));
}

const llmChartData = computed(() =>
  filterTop10WithWhitelist(llmRawData.value, LLM_DATASET_KEYS, LLM_WHITELIST)
);
const visionChartData = computed(() =>
  filterTop10WithWhitelist(
    visionRawData.value,
    VISION_DATASET_KEYS,
    VISION_WHITELIST
  )
);
const audioChartData = computed(() =>
  filterTop10WithWhitelist(
    audioRawData.value,
    AUDIO_DATASET_KEYS,
    AUDIO_WHITELIST
  )
);

// Agent 数据来自 ruler1（getCurrentFullRes），与 rankingScore.vue 的 agentModels 逻辑一致：
// 保留具备任一 Agent 测试集分数的模型，缺失项算均分时跳过，无分数则过滤
function filterAgentTop10(rawObj, datasetKeys): { name: string; value: number }[] {
  const rows: { name: string; value: number | null }[] = [];
  Object.entries(rawObj).forEach(([modelName, modelGroup]) => {
    const result = modelGroup?.result || [];
    if (!result.some((item: any) => datasetKeys.includes(item.dataset_name))) {
      return;
    }
    let scoreSum = 0;
    let scoreCount = 0;
    datasetKeys.forEach((dsKey) => {
      const matched = result.find((item: any) => item.dataset_name === dsKey);
      if (matched && matched.score != null) {
        scoreSum += matched.score;
        scoreCount++;
      }
    });
    if (scoreCount === 0) return; // 无任何实测分数则过滤
    rows.push({ name: modelName, value: scoreSum / scoreCount });
  });
  rows.sort((a, b) => (b.value ?? -1) - (a.value ?? -1));
  return rows
    .slice(0, 10)
    .map((r) => ({
      name: r.name,
      value: r.value!,
      color: ModelService.getModelColor(r.name),
    }));
}

const agentChartData = computed(() =>
  filterAgentTop10(llmRawData.value, AGENT_DATASET_KEYS)
);

const goToRanking = (modality?: string) => {
  store.dispatch("rankingScore/updateActiveTab", "ruler1");
  router.push({
    path: "/rankingScore",
    query: { fromTab: "ruler1", fromModality: modality || "llm" },
  });
};

const goToRuler2Ranking = () => {
  store.dispatch("rankingScore/updateActiveTab", "ruler2");
  router.push({
    path: "/rankingScore",
    query: { fromTab: "ruler2" },
  });
};

const goToRuler2SubCategory = (subKey: string) => {
  // 伴学注意力检测/伴学坐姿检测统一跳转到 aisf_banxue 详情页
  const SUB_KEY_MAP: Record<string, string> = {
    aisf_banxue_attention: "aisf_banxue",
    aisf_banxue_posture: "aisf_banxue",
  };
  const targetKey = SUB_KEY_MAP[subKey] || subKey;
  store.dispatch("rankingScore/updateActiveTab", "ruler2");
  router.push({
    path: "/rankingScore",
    query: { fromTab: "ruler2", fromSubKey: targetKey },
  });
};

// ===================== 生命周期 =====================
onMounted(async () => {
  let ruler2FromFullRes = {};
  let ruler2FromMultiRes = {};
  // These independent reads must start together over a high-latency WAN.
  const reportsReady = (async () => {
    try {
      const resp = await getAllPublishedTasks();
      const tasks = resp.data || [];
      if (tasks.length > 0) {
        reportName.value = `最新报告：${tasks[0].report_name}`;
        latestReportId.value = tasks[0].id;
      }
    } catch (err) {
      console.warn("获取最新发布报告信息失败:", err);
    }
  })();
  const llmReady = (async () => {
    try {
      const llmRes = await getCurrentFullRes();
      llmRawData.value = llmRes.data?.ruler1 || {};
      ruler2FromFullRes = llmRes.data?.ruler2 || {};
    } catch (err) {
      console.error("Failed to load LLM ranking data:", err);
    } finally {
      llmLoading.value = false;
      agentLoading.value = false;
    }
  })();
  const multiReady = (async () => {
    try {
      const multiRes = await getMultiModelData();
      const multiR1 = multiRes.data?.ruler1 || {};
      // 只保留包含视觉数据集 key 的模型
      const visionFiltered: Record<string, any> = {};
      Object.entries(multiR1).forEach(
        ([modelName, modelGroup]: [string, any]) => {
          const hasVision = (modelGroup?.result || []).some((item: any) =>
            VISION_DATASET_KEYS.includes(item.dataset_name)
          );
          if (hasVision) {
            visionFiltered[modelName] = modelGroup;
          }
        }
      );
      visionRawData.value = visionFiltered;

      // 从同一份 multiR1 数据中筛选音频模型
      const audioFiltered: Record<string, any> = {};
      Object.entries(multiR1).forEach(
        ([modelName, modelGroup]: [string, any]) => {
          const hasAudio = (modelGroup?.result || []).some((item: any) =>
            AUDIO_DATASET_KEYS.includes(item.dataset_name)
          );
          if (hasAudio) {
            audioFiltered[modelName] = modelGroup;
          }
        }
      );
      audioRawData.value = audioFiltered;

      ruler2FromMultiRes = multiRes.data?.ruler2 || {};

    } catch (err) {
      console.error("Failed to load vision/audio/ruler2 ranking data:", err);
    } finally {
      visionLoading.value = false;
      audioLoading.value = false;
    }
  })();
  await Promise.all([reportsReady, llmReady, multiReady]);
  // 合并 ruler2 数据：getCurrentFullRes 包含 aisf_llm_gaixie，
  // getMultiModelData 包含 aisf_banxue、aisf_gui_plan、aisf_gui_vla
  // 注意：两个 API 可能包含相同模型，需要合并 result 数组而非覆盖
  const multiRuler2 = ruler2FromMultiRes;
  const fullRuler2 = ruler2FromFullRes || {};
  const mergedRuler2: Record<string, any> = {};
  // 先合并 multiRuler2 的所有模型
  Object.entries(multiRuler2).forEach(
    ([modelName, modelGroup]: [string, any]) => {
      mergedRuler2[modelName] = JSON.parse(JSON.stringify(modelGroup));
    }
  );
  // 再将 fullRuler2 中模型的 result 合并进来（按 dataset_name 去重）
  Object.entries(fullRuler2).forEach(
    ([modelName, modelGroup]: [string, any]) => {
      if (mergedRuler2[modelName]) {
        // 合并 result 数组，按 dataset_name 去重
        const existingNames = new Set(
          (mergedRuler2[modelName]?.result || []).map(
            (r: any) => r.dataset_name
          )
        );
        (modelGroup?.result || []).forEach((item: any) => {
          if (!existingNames.has(item.dataset_name)) {
            mergedRuler2[modelName].result.push(item);
          }
        });
      } else {
        mergedRuler2[modelName] = JSON.parse(JSON.stringify(modelGroup));
      }
    }
  );
  ruler2RawData.value = mergedRuler2;
  ruler2Loading.value = false;
  await nextTick();
  syncHeaderHeights();
});
</script>

<style scoped>
.home-page {
  padding-top: 10px;
  background: linear-gradient(
    180deg,
    #f5f5f5 0%,
    #eaeaea 30%,
    #e0e0e0 60%,
    #d6d6d6 100%
  );
  display: flex;
  flex-direction: column;
  gap: clamp(6px, 1vh, 12px);
  /* padding: clamp(8px, 1.5vh, 16px) clamp(10px, 2vw, 20px); */
  min-height: calc(100vh - 80px);
  box-sizing: border-box;
}

.cards-section {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin: clamp(12px, 1vh, 20px);
  gap: clamp(20px, 3vw, 32px);
  flex-shrink: 0;
}

/* ==================== Hero Section ==================== */
.hero-section {
  border-radius: 12px;
  padding: clamp(10px, 2vh, 20px) clamp(16px, 4vw, 48px);
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}

/* .hero-section::before {
  content: "";
  position: absolute;
  top: -50%;
  right: -20%;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.05);
}

.hero-section::after {
  content: "";
  position: absolute;
  bottom: -30%;
  left: 60%;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
} */

.hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.hero-title {
  font-size: clamp(18px, 3.2vw, 32px);
  font-weight: 700;
  margin: 0 0 clamp(4px, 1vh, 12px) 0;
  letter-spacing: 1px;
}

.hero-subtitle {
  font-size: clamp(12px, 1.6vw, 16px);
  color: #303133;
  margin: 0;
  line-height: 1.6;
}

/* ==================== Cards Section ==================== */
.function-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: clamp(4px, 0.8vh, 10px);
  padding: clamp(12px, 2vh, 24px) clamp(8px, 1.5vw, 40px);
  background: #fff;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.function-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.card-icon-wrapper {
  width: clamp(36px, 4.5vw, 56px);
  height: clamp(36px, 4.5vw, 56px);
  border-radius: clamp(8px, 1vw, 14px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-title {
  font-size: clamp(18px, 1.4vw, 20px);
  font-weight: 600;
  color: #1d2129;
}

.card-desc {
  font-size: clamp(12px, 0.9vw, 14px);
  color: #86909c;
  text-align: center;
  line-height: 1.4;
}

/* ==================== 尺子一区域（合并卡片） ==================== */
.ruler1-section {
  margin: clamp(12px, 1vh, 20px);
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.ruler1-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(8px, 1.5vh, 16px) clamp(10px, 2vw, 20px);
  border-bottom: 1px solid #e8e8e8;
}

.ruler1-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 600px;
}

.ruler1-chart-item {
  display: flex;
  flex-direction: column;
  min-height: 600px;
}

/* 除第一项外，其余项左侧加竖线分隔 */
.ruler1-chart-item--mid {
  border-left: 1px solid #e8e8e8;
}

.chart-wrapper {
  flex: 1;
  min-height: 0;
  padding: 8px;
}

.chart-header {
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid #e8e8e8;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(8px, 1.5vh, 16px) clamp(10px, 2vw, 20px);
}

.panel-title {
  font-size: clamp(13px, 1.5vw, 16px);
  font-weight: 600;
  color: #1d2129;
  position: relative;
  padding-left: 14px;
}

.panel-title::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 18px;
  background: linear-gradient(180deg, #4a6cf7, #1b3882);
  border-radius: 2px;
}

.header-information {
  padding: 0 10px 10px 20px;
  font-size: 0.5em;
  color: gray;
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: normal;
}

.carousel-slide {
  width: 100%;
  height: 100%;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.carousel-image {
  width: auto;
  height: 100%;
  max-width: 100%;
  object-fit: contain;
  display: block;
}

.imageReportName {
  position: absolute;
  left: 50%;
  top: 5%;
  transform: translateX(-50%);
  color: rgb(22, 26, 123);
  font-size: clamp(14px, 1.6vw, 22px);
  font-weight: 600;
  pointer-events: none;
  white-space: nowrap;
  z-index: 1;
}

:deep(.el-carousel__indicators) {
  left: auto !important;
  right: 0;
}

/* ==================== 尺子二区域 ==================== */
.ruler2-section {
  margin: clamp(12px, 1vh, 20px);
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.section-header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.section-header-title {
  font-size: clamp(13px, 1.5vw, 16px);
  font-weight: 600;
  color: #1d2129;
  position: relative;
  padding-left: 14px;
}

.section-header-title::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 18px;
  background: linear-gradient(180deg, #4a6cf7, #1b3882);
  border-radius: 2px;
}

.section-header-sub {
  font-size: 12px;
  color: #999;
}

.ruler2-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: clamp(8px, 1.5vh, 16px) clamp(10px, 2vw, 20px);
  border-bottom: 1px solid #e8e8e8;
}

.ruler2-body {
  display: flex;
  min-height: 400px;
}

.ruler2-anchor-col {
  width: 15em;
  flex-shrink: 0;
  border-right: 1px solid #e8e8e8;
  padding: 16px 12px;
  background: #fafafa;
}

.ruler2-anchor-col :deep(.el-anchor) {
  background: transparent;
}

.ruler2-anchor-col :deep(.el-anchor__item) {
  margin-bottom: 4px;
}

.ruler2-anchor-col :deep(.el-anchor__link) {
  font-size: 14px;
  padding: 6px 8px;
  border-radius: 4px;
}

.ruler2-anchor-col :deep(.el-anchor__link:hover) {
  background: #e8ecf4;
}

.ruler2-anchor-col :deep(.el-anchor__link.is-active) {
  color: #1b3882;
  font-weight: 600;
  background: #eef0fa;
}

.ruler2-charts-col {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  /* max-height: 600px; */
}

.ruler2-charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.ruler2-chart-item {
  break-inside: avoid;
  display: flex;
  flex-direction: column;
}

.ruler2-chart-header-area {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.ruler2-chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d2129;
  margin-bottom: 8px;
  padding-left: 12px;
  position: relative;
  cursor: pointer;
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: normal;
}

.ruler2-chart-title:hover {
  color: #1b3882;
}

.ruler2-chart-title::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 16px;
  background: linear-gradient(180deg, #4a6cf7, #1b3882);
  border-radius: 2px;
}

.ruler2-chart-wrapper {
  flex: 1;
  min-height: 400px;
}
</style>
