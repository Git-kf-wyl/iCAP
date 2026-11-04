<template>
  <div class="paper-agent-container">
    <!-- 顶部导航栏 -->
    <div class="header">
      <div class="flex items-center">
        <div class="pl-2">论文分析控制台</div>
        <el-button
          class="nav-btn"
          text
          type="primary"
          @click="navigateToDailyResults"
        >
          <el-icon style="margin-right: 4px"><Search /></el-icon>
          在线论文检索入口
        </el-button>
      </div>
    </div>

    <div class="main-content" v-loading="loading">
      <!-- 状态卡片 -->
      <div class="status-card">
        <div class="status-header">
          <h3>服务状态</h3>
          <span :class="['status-badge', status.running ? 'running' : 'idle']">
            {{ status.running ? "运行中" : "空闲" }}
          </span>
        </div>
        <div class="status-body">
          <div class="status-item">
            <span class="label">当前阶段</span>
            <span class="value">{{ formatStatus(status.current_stage) }}</span>
          </div>
          <div class="status-item">
            <span class="label">进度信息</span>
            <span class="value">{{ status.current_progress || "等待操作" }}</span>
          </div>
          <div class="status-item">
            <span class="label">上次运行</span>
            <span class="value">{{ formatTime(status.last_run_time) }}</span>
          </div>
          <div class="status-item">
            <span class="label">上次结果</span>
            <span class="value">
              <span v-if="status.last_run_status === 'success'" class="text-success">成功</span>
              <span v-else-if="status.last_run_status === 'failed'" class="text-danger">失败</span>
              <span v-else>暂无</span>
            </span>
          </div>
          <div class="status-item" v-if="status.last_run_paper_count > 0">
            <span class="label">处理论文数</span>
            <span class="value">{{ status.last_run_paper_count }} 篇</span>
          </div>
          <div class="status-item" v-if="status.last_run_error">
            <span class="label">错误信息</span>
            <span class="value text-danger">{{ status.last_run_error }}</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮组 -->
      <div class="action-card">
        <h3>操作</h3>
        <div class="action-buttons">
          <el-button
            type="primary"
            :disabled="status.running"
            :loading="status.running && status.current_stage !== 'idle'"
            @click="startPipeline"
            size="large"
          >
            <el-icon style="margin-right: 6px"><Upload /></el-icon>
            开始全量搜索
          </el-button>
          <el-button
            type="success"
            :disabled="status.running"
            @click="startQuickDemo"
            size="large"
          >
            <el-icon style="margin-right: 6px"><Lightning /></el-icon>
            快速演示
          </el-button>
          <el-button
            type="warning"
            :disabled="status.running"
            @click="openSearchDialog"
            size="large"
          >
            <el-icon style="margin-right: 6px"><Search /></el-icon>
            定制化论文搜索
          </el-button>
        </div>
      </div>

      <!-- 进度条（运行时显示） -->
      <div class="progress-card" v-if="status.running">
        <h3>运行进度</h3>
        <div class="progress-steps">
          <div :class="['step', status.current_stage === 'fetching' ? 'active' : '',
            ['analyzing', 'generating', 'done'].includes(status.current_stage) ? 'completed' : '']">
            <div class="step-icon">1</div>
            <div class="step-label">获取论文</div>
          </div>
          <div class="step-connector" :class="['analyzing', 'generating', 'done'].includes(status.current_stage) ? 'completed' : ''"></div>
          <div :class="['step', status.current_stage === 'analyzing' ? 'active' : '',
            ['generating', 'done'].includes(status.current_stage) ? 'completed' : '']">
            <div class="step-icon">2</div>
            <div class="step-label">LLM分析</div>
          </div>
          <div class="step-connector" :class="['generating', 'done'].includes(status.current_stage) ? 'completed' : ''"></div>
          <div :class="['step', status.current_stage === 'generating' ? 'active' : '',
            ['done'].includes(status.current_stage) ? 'completed' : '']">
            <div class="step-icon">3</div>
            <div class="step-label">生成报告</div>
          </div>
          <div class="step-connector" :class="status.current_stage === 'done' ? 'completed' : ''"></div>
          <div :class="['step', status.current_stage === 'done' ? 'completed' : '']">
            <div class="step-icon">4</div>
            <div class="step-label">完成</div>
          </div>
        </div>
        <div class="progress-message">{{ status.current_progress }}</div>
      </div>

      <!-- 定制化搜索结果区域 -->
      <div class="search-result-card" v-if="searchResultData.length > 0">
        <div class="search-result-header">
          <h3>定制搜索结果</h3>
          <div class="search-result-meta">
            <span class="search-meta-item">关键词：<strong>{{ lastSearchParams.keywords }}</strong></span>
            <span class="search-meta-item" v-if="lastSearchParams.date_from">起始：<strong>{{ lastSearchParams.date_from }}</strong></span>
            <span class="search-meta-item" v-if="lastSearchParams.date_to">截止：<strong>{{ lastSearchParams.date_to }}</strong></span>
            <span class="search-meta-item" v-if="lastSearchParams.category">归类：<strong>{{ lastSearchParams.category }}</strong></span>
            <span class="search-meta-item">结果：<strong>{{ searchResultData.length }} 篇</strong></span>
            <span class="search-meta-item" v-if="lastSearchParams.local_count > 0">本地匹配：<strong class="text-success">{{ lastSearchParams.local_count }} 篇</strong></span>
            <span class="search-meta-item" v-if="lastSearchParams.arxiv_count > 0">arXiv补充：<strong class="text-warning">{{ lastSearchParams.arxiv_count }} 篇</strong></span>
          </div>
          <div class="search-result-actions">
            <el-button size="small" @click="refreshSearchResult">刷新结果</el-button>
            <el-button size="small" type="primary" @click="downloadSearchExcel">下载Excel</el-button>
            <el-button size="small" @click="clearSearchResult">清除结果</el-button>
          </div>
        </div>

        <div class="table-box">
          <el-table
            :data="searchPaginatedData"
            max-height="600px"
            :header-cell-style="tableHeaderStyle"
            :cell-style="tableCellStyle"
            border
            stripe
            style="width: 100%"
          >
            <el-table-column type="index" label="序号" width="55px" align="center" />

            <!-- 标题 -->
            <el-table-column
              prop="title"
              label="标题"
              min-width="280px"
              align="center"
              :show-overflow-tooltip="false"
            >
              <template #default="{ row }">
                <div class="cell-with-tooltip">
                  <el-tooltip placement="top" :show-after="300" popper-class="rich-tooltip">
                    <template #content>
                      <div class="tooltip-content-wrapper">
                        <p class="tooltip-text">{{ row.title }}</p>
                        <el-button class="tooltip-copy-btn" text size="small" type="primary" @click.stop="copyText(row.title)">
                          <el-icon style="margin-right: 4px"><CopyDocument /></el-icon>复制
                        </el-button>
                      </div>
                    </template>
                    <span class="cell-ellipsis">{{ row.title }}</span>
                  </el-tooltip>
                  <el-button class="copy-btn" text size="small" @click.stop="copyText(row.title)">
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                </div>
              </template>
            </el-table-column>

            <!-- 作者 -->
            <el-table-column
              prop="authors"
              label="作者"
              min-width="220px"
              align="center"
              :show-overflow-tooltip="false"
            >
              <template #default="{ row }">
                <el-tooltip placement="top" :content="formatAuthors(row.authors)" :show-after="300" popper-class="rich-tooltip">
                  <span class="cell-ellipsis">{{ formatAuthors(row.authors) }}</span>
                </el-tooltip>
              </template>
            </el-table-column>

            <!-- 发布日期 -->
            <el-table-column
              prop="发布日期"
              label="发布日期"
              width="170px"
              align="center"
            >
              <template #default="{ row }">
                <span>{{ formatDateStr(row['发布日期']) }}</span>
              </template>
            </el-table-column>

            <!-- 归类（LLM分析字段） -->
            <el-table-column
              prop="归类"
              label="归类"
              width="140px"
              align="center"
              :show-overflow-tooltip="true"
            >
              <template #default="{ row }">
                <el-tag v-if="row['归类']" type="warning" size="small" effect="plain">
                  {{ row['归类'] }}
                </el-tag>
                <span v-else class="text-muted">—</span>
              </template>
            </el-table-column>

            <!-- 主分类 -->
            <el-table-column
              prop="primary_category"
              label="arXiv分类"
              width="100px"
              align="center"
              :show-overflow-tooltip="true"
            >
              <template #default="{ row }">
                <span>{{ row.primary_category }}</span>
              </template>
            </el-table-column>

            <!-- 摘要 -->
            <el-table-column
              prop="abstract"
              label="摘要"
              min-width="260px"
              align="center"
              :show-overflow-tooltip="false"
            >
              <template #default="{ row }">
                <div class="cell-with-tooltip">
                  <el-tooltip placement="top" :show-after="300" popper-class="rich-tooltip">
                    <template #content>
                      <div class="tooltip-content-wrapper">
                        <p class="tooltip-text">{{ row.abstract }}</p>
                        <el-button class="tooltip-copy-btn" text size="small" type="primary" @click.stop="copyText(row.abstract)">
                          <el-icon style="margin-right: 4px"><CopyDocument /></el-icon>复制全文
                        </el-button>
                      </div>
                    </template>
                    <span class="cell-ellipsis">{{ truncateText(row.abstract, 100) }}</span>
                  </el-tooltip>
                  <el-button class="copy-btn" text size="small" @click.stop="copyText(row.abstract)">
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                </div>
              </template>
            </el-table-column>

            <!-- 链接 -->
            <el-table-column prop="链接" label="arXiv链接" width="90px" align="center">
              <template #default="{ row }">
                <el-link :href="row['链接'] || row.entry_id" target="_blank" :underline="false">
                  <el-icon><Link /></el-icon>
                </el-link>
              </template>
            </el-table-column>

            <!-- PDF下载 -->
            <el-table-column prop="pdf_url" label="PDF下载" width="100px" align="center">
              <template #default="{ row }">
                <el-button
                  text
                  type="primary"
                  size="small"
                  @click="downloadPdf(row.pdf_url, row.title)"
                >
                  <el-icon style="margin-right: 4px"><Download /></el-icon>
                  下载
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <div class="search-pagination">
            <span class="total-text">总计: {{ searchResultData.length }} 条</span>
            <el-pagination
              background
              layout="sizes, prev, pager, next, jumper"
              :page-sizes="[10, 20, 50]"
              :page-size="searchPageSize"
              :total="searchResultData.length"
              :current-page="searchCurrentPage"
              @size-change="handleSearchSizeChange"
              @current-change="handleSearchCurrentChange"
            ></el-pagination>
          </div>
        </div>
      </div>

      <!-- 说明卡片 -->
      <div class="info-card">
        <h3>说明</h3>
        <div class="info-content">
          <p><strong>paperAgent</strong> 是一个 arXiv 每日论文自动化工具，自动完成论文采集、LLM分析、Excel报告生成的全流程。</p>
          <ul>
            <li><strong>全量搜索</strong>：从arXiv获取最多200篇 cs.AI 论文，逐篇下载PDF、提取文本、调用LLM进行分析（摘要翻译、创新点总结、关键词提取、分类），最终生成格式化的Excel报告</li>
            <li><strong>快速演示</strong>：获取少量论文并用LLM进行Top 3推荐分析，快速了解当日论文概况</li>
            <li><strong>定制化搜索</strong>：按关键词、发布时间周期、技术类别搜索论文，结果只对当前用户可见</li>
            <li><strong>数据来源</strong>：<el-link href="http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending" target="_blank">arXiv cs.AI</el-link></li>
            <li><strong>每日自动</strong>：系统会在每日凌晨 0:00 自动执行一次完整管线，结果可在"每日搜索结果"页面查看</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 定制搜索弹窗 -->
    <el-dialog
      v-model="searchDialogVisible"
      title="定制化论文搜索"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="searchFormRef"
        :model="searchForm"
        :rules="searchRules"
        label-width="100px"
        label-position="left"
      >
        <el-form-item label="关键词" prop="keywords">
          <el-input
            v-model="searchForm.keywords"
            placeholder="输入关键词，多个词用逗号分隔，如: LLM, agent, reasoning"
          />
          <div class="form-tip">将在论文标题和摘要中搜索这些关键词</div>
        </el-form-item>

        <el-form-item label="发布时间">
          <div class="date-range-wrapper">
            <el-date-picker
              v-model="searchForm.date_from"
              type="date"
              placeholder="起始日期"
              value-format="YYYY-MM-DD"
              style="width: 180px"
            />
            <span class="date-separator">~</span>
            <el-date-picker
              v-model="searchForm.date_to"
              type="date"
              placeholder="截止日期"
              value-format="YYYY-MM-DD"
              style="width: 180px"
            />
          </div>
        </el-form-item>

        <el-form-item label="技术类别">
          <el-select
            v-model="searchForm.category"
            placeholder="选择技术类别（可选）"
            clearable
            style="width: 100%"
          >
            <el-option label="语言模型/推理模型" value="语言模型/推理模型" />
            <el-option label="视觉模型/多模态" value="视觉模型/多模态" />
            <el-option label="AI Agent/智能体" value="AI Agent/智能体" />
            <el-option label="传统机器学习" value="传统机器学习" />
            <el-option label="决策推理" value="决策推理" />
            <el-option label="仿真" value="仿真" />
            <el-option label="推荐搜索" value="推荐搜索" />
            <el-option label="其他" value="其他" />
          </el-select>
          <div class="form-tip">不选则搜索全部类别</div>
        </el-form-item>

        <el-form-item label="搜索篇数">
          <el-slider
            v-model="searchForm.max_results"
            :min="5"
            :max="20"
            :step="1"
            show-input
            style="width: 100%"
          />
          <div class="form-tip">上限为20篇</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="searchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="searchLoading" @click="submitSearch">
          开始搜索
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, ref, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { API_AGENT_URL } from "@/utils/Constants.js";
import * as XLSX from "xlsx";
import saveAs from "file-saver";

// ========== 状态 ==========
const status = ref({
  running: false,
  last_run_time: null,
  last_run_duration: null,
  last_run_status: null,
  last_run_paper_count: 0,
  last_run_error: null,
  current_progress: "",
  current_stage: "",
});

const loading = ref(false);
const polling = ref(false);
let pollingTimer = null;

// ========== 定制搜索状态 ==========
const searchDialogVisible = ref(false);
const searchLoading = ref(false);
const searchFormRef = ref(null);
const searchResultData = ref<any[]>([]);
const lastSearchParams = ref({
  keywords: "",
  date_from: "",
  date_to: "",
  category: "",
  max_results: 20,
  local_count: 0,
  arxiv_count: 0,
});
const searchCurrentPage = ref(1);
const searchPageSize = ref(10);

const searchForm = ref({
  keywords: "",
  date_from: null as string | null,
  date_to: null as string | null,
  category: "",
  max_results: 20,
});

const searchRules = {
  keywords: [{ required: true, message: "请输入搜索关键词", trigger: "blur" }],
};

// ========== API 调用 ==========
const apiBase = API_AGENT_URL;
const router = useRouter();

// ========== 用户名 ==========
const getUsername = (): string => {
  return localStorage.getItem("username") || "anonymous";
};

const fetchStatus = async () => {
  try {
    const resp = await fetch(`${apiBase}paper_agent/status`);
    if (resp.ok) {
      const data = await resp.json();
      status.value = data;
      return data;
    }
  } catch (e) {
    console.error("获取状态失败:", e);
  }
  return null;
};

const navigateToDailyResults = () => {
  router.push({ name: "paperAgent" });
};

const startPipeline = async () => {
  try {
    const resp = await fetch(`${apiBase}paper_agent/fetch_and_analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_papers: 200 }),
    });
    if (resp.status === 409) {
      ElMessage.warning("任务正在运行中，请等待完成");
      return;
    }
    if (resp.ok) {
      ElMessage.success("论文分析任务已启动，请在后台等待完成");
      startPolling();
    } else {
      const err = await resp.json();
      ElMessage.error("启动失败: " + (err.error || "未知错误"));
    }
  } catch (e) {
    ElMessage.error("请求失败: " + e.message);
  }
};

const startQuickDemo = async () => {
  try {
    const resp = await fetch(`${apiBase}paper_agent/quick_demo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (resp.status === 409) {
      ElMessage.warning("任务正在运行中，请等待完成");
      return;
    }
    if (resp.ok) {
      ElMessage.success("快速演示已启动");
      startPolling();
    } else {
      const err = await resp.json();
      ElMessage.error("启动失败: " + (err.error || "未知错误"));
    }
  } catch (e) {
    ElMessage.error("请求失败: " + e.message);
  }
};

// ========== 定制搜索 ==========
const openSearchDialog = () => {
  searchForm.value = {
    keywords: "",
    date_from: null,
    date_to: null,
    category: "",
    max_results: 20,
  };
  searchDialogVisible.value = true;
};

const submitSearch = async () => {
  if (!searchFormRef.value) return;

  try {
    await searchFormRef.value.validate();
  } catch {
    return;
  }

  searchLoading.value = true;
  try {
    const username = getUsername();
    const body: Record<string, any> = {
      keywords: searchForm.value.keywords,
      max_results: searchForm.value.max_results,
      username: username,
    };
    if (searchForm.value.date_from) body.date_from = searchForm.value.date_from;
    if (searchForm.value.date_to) body.date_to = searchForm.value.date_to;
    if (searchForm.value.category) body.category = searchForm.value.category;

    const resp = await fetch(`${apiBase}paper_agent/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (resp.status === 409) {
      ElMessage.warning("完整管线正在运行中，请等待完成后再搜索");
      return;
    }

    if (!resp.ok) {
      const err = await resp.json();
      ElMessage.error("搜索失败: " + (err.error || "未知错误"));
      return;
    }

    const result = await resp.json();
    ElMessage.success(`搜索成功，共 ${result.count} 篇论文（本地匹配 ${result.local_count || 0} 篇，arXiv补充 ${result.arxiv_count || 0} 篇）`);

    // 保存搜索参数（含统计信息）
    lastSearchParams.value = {
      keywords: searchForm.value.keywords,
      date_from: searchForm.value.date_from || "",
      date_to: searchForm.value.date_to || "",
      category: searchForm.value.category || "",
      max_results: searchForm.value.max_results,
      local_count: result.local_count || 0,
      arxiv_count: result.arxiv_count || 0,
    };

    searchDialogVisible.value = false;

    // 加载搜索结果
    await loadSearchResult();

  } catch (e) {
    ElMessage.error("搜索请求失败: " + (e as Error).message);
  } finally {
    searchLoading.value = false;
  }
};

const loadSearchResult = async () => {
  try {
    const username = getUsername();
    const resp = await fetch(`${apiBase}paper_agent/search_csv?username=${encodeURIComponent(username)}`);
    if (!resp.ok) {
      return;
    }

    const csvText = await resp.text();
    const parsed = parseCSV(csvText);
    if (parsed.data.length > 0) {
      searchResultData.value = parsed.data;
      searchCurrentPage.value = 1;
    }
  } catch (e) {
    console.error("加载搜索结果失败:", e);
  }
};

const refreshSearchResult = () => {
  loadSearchResult();
};

const clearSearchResult = () => {
  searchResultData.value = [];
  lastSearchParams.value = {
    keywords: "",
    date_from: "",
    date_to: "",
    category: "",
    max_results: 20,
    local_count: 0,
    arxiv_count: 0,
  };
};

// 搜索结果分页
const searchPaginatedData = computed(() => {
  const start = (searchCurrentPage.value - 1) * searchPageSize.value;
  const end = start + searchPageSize.value;
  return searchResultData.value.slice(start, end);
});

const handleSearchSizeChange = (val: number) => {
  searchPageSize.value = val;
  searchCurrentPage.value = 1;
};

const handleSearchCurrentChange = (val: number) => {
  searchCurrentPage.value = val;
};

// 搜索结果下载
const downloadSearchExcel = () => {
  if (searchResultData.value.length === 0) {
    ElMessage.warning("暂无数据可下载");
    return;
  }
  try {
    const worksheet = XLSX.utils.json_to_sheet(searchResultData.value);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Search Results");
    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const blob = new Blob([excelBuffer], { type: "application/octet-stream" });
    const timestamp = formatDateForFile(new Date());
    saveAs(blob, `search_arxiv_${timestamp}.xlsx`);
    ElMessage.success("下载成功");
  } catch (e) {
    ElMessage.error("下载失败: " + (e as Error).message);
  }
};

// ========== PDF下载 ==========
const downloadPdf = async (pdfUrl: string, title: string) => {
  if (!pdfUrl) {
    ElMessage.warning("PDF链接不可用");
    return;
  }
  try {
    const resp = await fetch(pdfUrl);
    if (!resp.ok) {
      window.open(pdfUrl, "_blank");
      return;
    }
    const blob = await resp.blob();
    const safeTitle = title.replace(/[^\w\u4e00-\u9fa5\- ]/g, "_").slice(0, 80);
    saveAs(blob, `${safeTitle}.pdf`);
    ElMessage.success("PDF下载已开始");
  } catch {
    window.open(pdfUrl, "_blank");
  }
};

// ========== CSV解析 ==========
const parseCSV = (text: string): { headers: string[]; data: any[] } => {
  const lines = text.split("\n").filter((l) => l.trim());
  if (lines.length === 0) return { headers: [], data: [] };

  const parseLine = (line: string): string[] => {
    const result: string[] = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        inQuotes = !inQuotes;
      } else if (ch === "," && !inQuotes) {
        result.push(current.trim());
        current = "";
      } else {
        current += ch;
      }
    }
    result.push(current.trim());
    return result;
  };

  const headers = parseLine(lines[0]).map((h) => h.replace(/^"|"$/g, ""));
  const data = [];
  for (let i = 1; i < lines.length; i++) {
    const values = parseLine(lines[i]).map((v) => v.replace(/^"|"$/g, ""));
    if (values.length === headers.length) {
      const row: Record<string, string> = {};
      headers.forEach((h, idx) => {
        row[h] = values[idx] || "";
      });
      data.push(row);
    }
  }
  return { headers, data };
};

// ========== 轮询 ==========
const startPolling = () => {
  polling.value = true;
  if (pollingTimer) clearInterval(pollingTimer);
  pollingTimer = setInterval(async () => {
    const s = await fetchStatus();
    if (s && !s.running) {
      polling.value = false;
      clearInterval(pollingTimer);
      pollingTimer = null;
      ElMessage.success("任务已完成！可前往「每日搜索结果」页面查看");
    }
  }, 3000);
};

// ========== 生命周期 ==========
// ========== 每日零点自动触发全量管线 ==========
const runDailyPipeline = async () => {
  try {
    const resp = await fetch(`${apiBase}paper_agent/fetch_and_analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_papers: 200 }),
    });
    if (resp.ok || resp.status === 409) {
      const today = formatDate(new Date());
      localStorage.setItem("arxivDailyPipelineLastRun", today);
      startPolling();
    }
  } catch (e) {
    console.error("定时管线触发失败:", e);
  }
};

const scheduleMidnightPipeline = () => {
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(0, 0, 0, 0);
  const msUntilMidnight = tomorrow.getTime() - now.getTime();

  setTimeout(() => {
    runDailyPipeline();
    scheduleMidnightPipeline();
  }, msUntilMidnight);
};

onMounted(async () => {
  loading.value = true;
  await fetchStatus();
  loading.value = false;

  if (status.value.running) {
    startPolling();
  }

  const today = formatDate(new Date());
  const lastRun = localStorage.getItem("arxivDailyPipelineLastRun");
  if (lastRun !== today && !status.value.running) {
    runDailyPipeline();
  }

  scheduleMidnightPipeline();

  // 加载当前用户的搜索结果（如果有）
  await loadSearchResult();
});

onUnmounted(() => {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
});

// ========== 格式化 ==========
const formatDate = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const formatDateForFile = (date: Date): string => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${y}${m}${d}_${hh}${mm}`;
};

const formatDateStr = (dateStr: string): string => {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return dateStr;
  }
};

const formatTime = (isoStr) => {
  if (!isoStr) return "暂无";
  const d = new Date(isoStr);
  return d.toLocaleString("zh-CN");
};

const formatStatus = (s) => {
  const map = {
    idle: "空闲",
    fetching: "获取论文中",
    analyzing: "LLM分析中",
    generating: "生成报告中",
    done: "完成",
  };
  return map[s] || s;
};

// ========== 工具函数 ==========
const truncateText = (text: string, maxLen: number): string => {
  if (!text) return "";
  return text.length > maxLen ? text.slice(0, maxLen) + "..." : text;
};

const formatAuthors = (authors: any): string => {
  if (!authors) return "";
  if (typeof authors === "string") {
    let cleaned = authors.trim();
    if (cleaned.startsWith("[") && cleaned.endsWith("]")) {
      try {
        const parsed = JSON.parse(cleaned);
        if (Array.isArray(parsed)) {
          return parsed.join("; ").replace(/'/g, "");
        }
      } catch {
        cleaned = cleaned.slice(1, -1);
        return cleaned
          .split(",")
          .map((s) => s.trim().replace(/^["'\s]+|["'\s]+$/g, ""))
          .filter(Boolean)
          .join("; ");
      }
    }
    return cleaned;
  }
  if (Array.isArray(authors)) {
    return authors.join("; ").replace(/'/g, "");
  }
  return String(authors);
};

const copyText = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("已复制到剪贴板");
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
    ElMessage.success("已复制到剪贴板");
  }
};

const tableHeaderStyle = () => ({
  background: "#f5f7fa",
  color: "#333",
  fontWeight: 600,
});

const tableCellStyle = () => ({
  padding: "8px 4px",
});
</script>

<style scoped>
.paper-agent-container {
  box-sizing: border-box;
  background-color: rgb(245, 245, 245);
  width: 100%;
  min-height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  padding-inline: 0.5rem;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  background-color: #fff;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.pl-2 {
  padding-left: 0.5rem;
  font-size: 18px;
  font-weight: 700;
  margin-right: 24px;
}

.nav-btn {
  font-size: 14px;
}

.main-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 98%;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

/* 状态卡片 */
.status-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.status-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.running {
  background-color: #e6f7ff;
  color: #1890ff;
  border: 1px solid #91d5ff;
}

.status-badge.idle {
  background-color: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.status-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-item .label {
  font-size: 12px;
  color: #999;
}

.status-item .value {
  font-size: 14px;
  color: #333;
}

.text-success {
  color: #52c41a !important;
}

.text-danger {
  color: #ff4d4f !important;
}

.text-warning {
  color: #e6a23c !important;
}

.text-muted {
  color: #c0c4cc !important;
}

/* 操作卡片 */
.action-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.action-card h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* 进度条 */
.progress-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.progress-card h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
}

.progress-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.step-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #999;
  transition: all 0.3s;
}

.step.active .step-icon {
  background-color: #1890ff;
  color: #fff;
  box-shadow: 0 0 0 4px rgba(24, 144, 255, 0.2);
}

.step.completed .step-icon {
  background-color: #52c41a;
  color: #fff;
}

.step-label {
  font-size: 12px;
  color: #999;
}

.step.active .step-label {
  color: #1890ff;
  font-weight: 600;
}

.step.completed .step-label {
  color: #52c41a;
  font-weight: 600;
}

.step-connector {
  width: 60px;
  height: 2px;
  background-color: #f0f0f0;
  margin: 0 8px;
  margin-bottom: 26px;
}

.step-connector.completed {
  background-color: #52c41a;
}

.progress-message {
  text-align: center;
  font-size: 14px;
  color: #666;
  padding: 8px;
  background-color: #fafafa;
  border-radius: 4px;
}

/* 搜索结果卡片 */
.search-result-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  width: 100%;
  overflow-x: auto;
}

.search-result-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.search-result-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.search-result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: #666;
  flex: 1;
}

.search-meta-item {
  white-space: nowrap;
}

.search-meta-item strong {
  color: #333;
}

.search-result-actions {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.table-box {
  width: 100%;
}

.table-box :deep(.el-table) {
  width: 100%;
}

.search-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.total-text {
  font-size: 14px;
  color: #606060;
}

/* 说明卡片 */
.info-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.info-card h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 600;
}

.info-content {
  font-size: 14px;
  line-height: 1.8;
  color: #666;
}

.info-content ul {
  padding-left: 20px;
}

.info-content li {
  margin: 8px 0;
}

/* 单元格内容样式 */
.cell-with-tooltip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
}

.cell-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  flex: 1;
  min-width: 0;
  text-align: left;
}

.copy-btn {
  flex-shrink: 0;
  opacity: 0.4;
  transition: opacity 0.2s;
  padding: 2px;
  margin-left: 2px;
}

.copy-btn:hover {
  opacity: 1;
}

/* tooltip 内容样式 */
:deep(.rich-tooltip) {
  max-width: 600px !important;
}

:deep(.tooltip-content-wrapper) {
  max-height: 400px;
  overflow-y: auto;
  padding: 4px;
}

:deep(.tooltip-text) {
  margin: 0 0 8px 0;
  line-height: 1.6;
  font-size: 13px;
  word-break: break-word;
  white-space: pre-wrap;
}

:deep(.tooltip-copy-btn) {
  display: inline-flex;
  align-items: center;
}

/* 搜索弹窗样式 */
.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  line-height: 1.4;
}

.date-range-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-separator {
  color: #999;
  font-size: 14px;
}
</style>