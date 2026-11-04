<template>
  <div class="arxiv-daily-container">
    <!-- 顶部导航栏 -->
    <div class="header">
      <div class="flex items-center">
        <div class="pl-2">论文检索</div>
        <el-button
          class="nav-btn"
          text
          type="primary"
          @click="navigateToPaperAgent"
        >
          <el-icon style="margin-right: 4px"><ArrowLeft /></el-icon>
          论文分析控制台
        </el-button>
      </div>
    </div>

    <div class="main-content" v-loading="loading">
      <!-- 表格操作栏 -->
      <div class="tableBox">
        <div class="buttonRow">
          <div class="update-info">
            <span class="update-label">更新频率：每日凌晨</span>
            <span class="update-divider"></span>
            <span class="update-label">数据时间：{{ updateTime }}</span>
          </div>
          <el-button class="createTaskbtn" @click="fetchFullData">刷新数据</el-button>
          <el-button class="createTaskbtn" type="primary" @click="downloadExcel">下载 Excel</el-button>
          <el-button class="createTaskbtn" type="success" @click="downloadCsv">下载 CSV</el-button>
        </div>

        <el-table
          :data="paginatedInfo"
          max-height="100%"
          :header-cell-style="tableHeaderStyle"
          :cell-style="tableCellStyle"
          v-loading="loading"
          border
          stripe
          @filter-change="handleFilterChange"
        >
          <el-table-column type="index" label="序号" width="55px" align="center" />

          <!-- 标题 -->
          <template v-if="columnKeys.has('title')">
            <el-table-column
              prop="title"
              label="标题"
              min-width="280px"
              align="center"
              :show-overflow-tooltip="false"
              column-key="title"
              :filters="getColumnFilters('title')"
              :filter-method="filterHandler"
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
          </template>

          <!-- 作者 -->
          <template v-if="columnKeys.has('authors')">
            <el-table-column
              prop="authors"
              label="作者"
              min-width="220px"
              align="center"
              :show-overflow-tooltip="false"
              column-key="authors"
              :filters="getColumnFilters('authors')"
              :filter-method="filterHandler"
            >
              <template #default="{ row }">
                <el-tooltip placement="top" :content="formatAuthors(row.authors)" :show-after="300" popper-class="rich-tooltip">
                  <span class="cell-ellipsis">{{ formatAuthors(row.authors) }}</span>
                </el-tooltip>
              </template>
            </el-table-column>
          </template>

          <!-- 链接 -->
          <template v-if="columnKeys.has('entry_id')">
            <el-table-column prop="entry_id" label="链接" width="80px" align="center" column-key="entry_id">
              <template #default="{ row }">
                <el-link :href="row.entry_id" target="_blank" :underline="false">
                  <el-icon><Link /></el-icon>
                </el-link>
              </template>
            </el-table-column>
          </template>

          <!-- abstract（原始英文摘要） -->
          <template v-if="columnKeys.has('abstract')">
            <el-table-column prop="abstract" label="abstract" min-width="280px" align="center" :show-overflow-tooltip="false" column-key="abstract">
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
          </template>

          <!-- 摘要（中文摘要） -->
          <template v-if="columnKeys.has('摘要')">
            <el-table-column prop="摘要" label="摘要" min-width="240px" align="center" :show-overflow-tooltip="false" column-key="摘要">
              <template #default="{ row }">
                <div class="cell-with-tooltip">
                  <el-tooltip placement="top" :show-after="300" popper-class="rich-tooltip">
                    <template #content>
                      <div class="tooltip-content-wrapper">
                        <p class="tooltip-text">{{ row['摘要'] }}</p>
                        <el-button class="tooltip-copy-btn" text size="small" type="primary" @click.stop="copyText(row['摘要'])">
                          <el-icon style="margin-right: 4px"><CopyDocument /></el-icon>复制全文
                        </el-button>
                      </div>
                    </template>
                    <span class="cell-ellipsis">{{ truncateText(row['摘要'], 100) }}</span>
                  </el-tooltip>
                  <el-button class="copy-btn" text size="small" @click.stop="copyText(row['摘要'])">
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </template>

          <!-- 创新点总结 -->
          <template v-if="columnKeys.has('创新点总结')">
            <el-table-column prop="创新点总结" label="创新点总结" min-width="200px" align="center" :show-overflow-tooltip="true" column-key="创新点总结">
              <template #default="{ row }">
                <span>{{ row['创新点总结'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 关键词 -->
          <template v-if="columnKeys.has('关键词')">
            <el-table-column prop="关键词" label="关键词" min-width="180px" align="center" :show-overflow-tooltip="true" column-key="关键词">
              <template #default="{ row }">
                <span>{{ row['关键词'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 机构 -->
          <template v-if="columnKeys.has('机构')">
            <el-table-column prop="机构" label="机构" min-width="180px" align="center" :show-overflow-tooltip="true" column-key="机构">
              <template #default="{ row }">
                <span>{{ row['机构'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 归类 -->
          <template v-if="columnKeys.has('归类')">
            <el-table-column prop="归类" label="归类" min-width="160px" align="center" :show-overflow-tooltip="true" column-key="归类">
              <template #default="{ row }">
                <span>{{ row['归类'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 核心技术 -->
          <template v-if="columnKeys.has('核心技术')">
            <el-table-column prop="核心技术" label="核心技术" min-width="180px" align="center" :show-overflow-tooltip="true" column-key="核心技术">
              <template #default="{ row }">
                <span>{{ row['核心技术'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 应用方向 -->
          <template v-if="columnKeys.has('应用方向')">
            <el-table-column prop="应用方向" label="应用方向" min-width="180px" align="center" :show-overflow-tooltip="true" column-key="应用方向">
              <template #default="{ row }">
                <span>{{ row['应用方向'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 发布日期 -->
          <template v-if="columnKeys.has('发布日期')">
            <el-table-column prop="发布日期" label="发布日期" width="150px" align="center" column-key="发布日期"
              :filters="getColumnFilters('发布日期')" :filter-method="filterHandler">
              <template #default="{ row }">
                <span>{{ row['发布日期'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- pdf_url - 改为PDF下载按钮 -->
          <template v-if="columnKeys.has('pdf_url')">
            <el-table-column prop="pdf_url" label="PDF下载" width="100px" align="center" column-key="pdf_url">
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
          </template>

          <!-- 主分类 -->
          <template v-if="columnKeys.has('主分类')">
            <el-table-column prop="主分类" label="主分类" width="120px" align="center" column-key="主分类"
              :filters="getColumnFilters('主分类')" :filter-method="filterHandler">
              <template #default="{ row }">
                <span>{{ row['主分类'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- arxiv_comment -->
          <template v-if="columnKeys.has('arxiv_comment')">
            <el-table-column prop="arxiv_comment" label="arxiv_comment" width="160px" align="center" :show-overflow-tooltip="true" column-key="arxiv_comment">
              <template #default="{ row }">
                <span>{{ row['arxiv_comment'] }}</span>
              </template>
            </el-table-column>
          </template>

          <!-- 其他未预先定义的列（排除 processed） -->
          <template v-for="col in otherDynamicColumns" :key="col.prop">
            <el-table-column
              :prop="col.prop"
              :label="col.label"
              :width="col.width"
              :min-width="col.minWidth || '120px'"
              :align="col.align || 'center'"
              :filters="col.filters"
              :filter-method="filterHandler"
              :column-key="col.prop"
              :show-overflow-tooltip="true"
            >
              <template #default="{ row }">
                <span v-if="isUrl(row[col.prop])">
                  <el-link :href="row[col.prop]" target="_blank" type="primary">{{ row[col.prop] }}</el-link>
                </span>
                <span v-else>{{ row[col.prop] }}</span>
              </template>
            </el-table-column>
          </template>
        </el-table>

        <div class="pagination">
          <span class="total-text">总计: {{ totalItems }} 条</span>
          <el-pagination
            background
            layout="sizes, prev, pager, next, jumper"
            :page-sizes="[20, 50, 100]"
            :page-size="pageSize"
            :total="totalItems"
            :current-page="currentPage"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          ></el-pagination>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { API_AGENT_URL } from "@/utils/Constants.js";
import * as XLSX from "xlsx";
import saveAs from "file-saver";

// ========== 状态 ==========
const loading = ref(false);
const tableData = ref<any[]>([]);
const columns = ref<any[]>([]);
const updateTime = ref("");
const activeFilters = ref<Record<string, string[]>>({});

// ========== 路由 ==========
const router = useRouter();

// ========== API ==========
const apiBase = API_AGENT_URL;

// ========== 导航 ==========
const navigateToPaperAgent = () => {
  router.push({ name: "arxivDailyResults" });
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
    // fallback
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

const isUrl = (value: any): boolean => {
  if (!value || typeof value !== "string") return false;
  try {
    new URL(value);
    return value.startsWith("http://") || value.startsWith("https://");
  } catch {
    return false;
  }
};

// ========== 列管理 ==========
// 显式定义了顺序和展示的列（这些列由模板中的显式 el-table-column 处理）
const EXPLICIT_COLUMNS = new Set([
  "title", "authors", "entry_id", "abstract",
  "摘要", "创新点总结", "关键词", "机构", "归类", "核心技术", "应用方向",
  "发布日期", "pdf_url", "主分类", "arxiv_comment"
]);
// 需要排除的列
const EXCLUDED_COLUMNS = new Set(["processed"]);

// 当前数据中存在的列名集合
const columnKeys = computed(() => new Set(columns.value.map((c) => c.prop)));

// 其他动态列：既不在显式列中、也不在排除列表中的列
const otherDynamicColumns = computed(() =>
  columns.value.filter((c) => !EXPLICIT_COLUMNS.has(c.prop) && !EXCLUDED_COLUMNS.has(c.prop))
);

// 获取某列的筛选选项
const getColumnFilters = (prop: string): { text: string; value: string }[] => {
  const col = columns.value.find((c) => c.prop === prop);
  return col ? col.filters : [];
};

// ========== 分页 ==========
const pageSize = ref(20);
const currentPage = ref(1);
const totalItems = computed(() => filteredData.value.length);

const paginatedInfo = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return filteredData.value.slice(start, end);
});

const handleSizeChange = (val: number) => {
  pageSize.value = val;
  currentPage.value = 1;
};

const handleCurrentChange = (val: number) => {
  currentPage.value = val;
};

// ========== 筛选 ==========
const filterHandler = (value: string, row: any, column: any): boolean => {
  const property = column.property;
  if (!property) return false;
  return String(row[property]) === String(value);
};

const handleFilterChange = (filters: Record<string, string[]>) => {
  activeFilters.value = {};
  for (const [key, vals] of Object.entries(filters)) {
    if (vals && vals.length > 0) {
      activeFilters.value[key] = vals;
    }
  }
  currentPage.value = 1;
  rebuildColumnFilters();
};

const filteredData = computed(() => {
  const filters = activeFilters.value;
  const filterKeys = Object.keys(filters);
  if (filterKeys.length === 0) return tableData.value;

  return tableData.value.filter((row) => {
    return filterKeys.every((key) => {
      const vals = filters[key];
      return vals.length === 0 || vals.includes(String(row[key]));
    });
  });
});

// 从数据中提取唯一值
const getFilterOptions = (data: any[], field: string): { text: string; value: string }[] => {
  const unique = [
    ...new Set(
      data
        .map((item) => item[field])
        .filter((v) => v !== null && v !== "" && v !== undefined)
        .map((v) => String(v))
    ),
  ].sort();
  return unique.map((v) => ({ text: v, value: v }));
};

// 重建列的筛选选项
const rebuildColumnFilters = () => {
  columns.value.forEach((col) => {
    if (!col.noFilter) {
      col.filters = getFilterOptions(tableData.value, col.prop);
    }
  });
};

// ========== 获取数据 ==========
const fetchFullData = async () => {
  loading.value = true;
  try {
    // 尝试获取 CSV
    try {
      const csvResp = await fetch(`${apiBase}paper_agent/latest_csv`);
      if (csvResp.ok) {
        const csvText = await csvResp.text();
        const parsed = parseCSV(csvText);
        if (parsed.data.length > 0) {
          tableData.value = parsed.data;
          buildColumns(parsed.headers);
          rebuildColumnFilters();
          updateTime.value = formatDate(new Date());
          ElMessage.success(`加载成功，共 ${parsed.data.length} 条记录`);
          return;
        }
      }
    } catch (_e) {
      // CSV 失败则尝试 Excel
    }

    // 尝试获取 Excel
    const excelResp = await fetch(`${apiBase}paper_agent/latest_excel_data`);
    if (excelResp.ok) {
      const arrayBuffer = await excelResp.arrayBuffer();
      const workbook = XLSX.read(arrayBuffer, { type: "array" });
      const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
      const jsonData = XLSX.utils.sheet_to_json(firstSheet, { defval: "" });
      if (jsonData.length > 0) {
        const headers = Object.keys(jsonData[0] as object);
        tableData.value = jsonData as any[];
        buildColumns(headers);
        rebuildColumnFilters();
        updateTime.value = formatDate(new Date());
        ElMessage.success(`加载成功，共 ${jsonData.length} 条记录`);
        return;
      }
    }

    // 尝试从 results 接口获取最新文件
    const resultsResp = await fetch(`${apiBase}paper_agent/results`);
    if (resultsResp.ok) {
      const results = await resultsResp.json();
      if (results.length > 0) {
        const sorted = [...results].sort(
          (a, b) => new Date(b.modified).getTime() - new Date(a.modified).getTime()
        );
        const latest = sorted.find(
          (r: any) => r.type === ".xlsx" || r.type === ".csv"
        );
        if (latest) {
          const fileResp = await fetch(
            `${apiBase}paper_agent/results/${latest.filename}`
          );
          if (fileResp.ok) {
            const blob = await fileResp.blob();
            const arrayBuffer = await blob.arrayBuffer();
            const workbook = XLSX.read(arrayBuffer, { type: "array" });
            const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
            const jsonData = XLSX.utils.sheet_to_json(firstSheet, { defval: "" });
            if (jsonData.length > 0) {
              const headers = Object.keys(jsonData[0] as object);
              tableData.value = jsonData as any[];
              buildColumns(headers);
              rebuildColumnFilters();
              updateTime.value = formatDate(new Date());
              ElMessage.success(`加载成功，共 ${jsonData.length} 条记录`);
              return;
            }
          }
        }
      }
    }

    ElMessage.info("暂无数据，请先运行全量搜索");
  } catch (e) {
    console.error("获取数据失败:", e);
    ElMessage.error("获取数据失败: " + (e as Error).message);
  } finally {
    loading.value = false;
  }
};

// ========== CSV 解析 ==========
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

// ========== 构建列定义 ==========
const buildColumns = (headers: string[]) => {
  const columnConfig: Record<string, { label: string; width?: number; minWidth?: string }> = {
    title: { label: "标题", minWidth: "300px" },
    id: { label: "ID", width: 80 },
    entry_id: { label: "链接", width: 100 },
    published: { label: "发布日期", width: 180 },
    updated: { label: "更新日期", width: 180 },
    summary: { label: "摘要", minWidth: "400px" },
    authors: { label: "作者", minWidth: "250px" },
    categories: { label: "分类", minWidth: "150px" },
    comment: { label: "备注", minWidth: "150px" },
    primary_category: { label: "主分类", width: 120 },
  };

  columns.value = headers.map((h) => {
    const config = columnConfig[h] || { label: h };
    return {
      prop: h,
      label: config.label || h,
      width: config.width || undefined,
      minWidth: config.minWidth || "120px",
      align: "center" as const,
      filters: [] as { text: string; value: string }[],
      filterMethod: filterHandler,
      filterPlacement: "bottom",
    };
  });
};

// ========== 下载 ==========
const downloadExcel = async () => {
  if (tableData.value.length === 0) {
    ElMessage.warning("暂无数据可下载");
    return;
  }
  try {
    const worksheet = XLSX.utils.json_to_sheet(filteredData.value);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "arXiv Papers");
    const excelBuffer = XLSX.write(workbook, { bookType: "xlsx", type: "array" });
    const blob = new Blob([excelBuffer], { type: "application/octet-stream" });
    saveAs(blob, `arxiv_papers_${formatDateForFile(new Date())}.xlsx`);
    ElMessage.success("下载成功");
  } catch (e) {
    ElMessage.error("下载失败: " + (e as Error).message);
  }
};

const downloadCsv = async () => {
  if (tableData.value.length === 0) {
    ElMessage.warning("暂无数据可下载");
    return;
  }
  try {
    const data = filteredData.value;
    const headers = columns.value.map((c) => c.prop);
    const csvLines = [headers.join(",")];
    data.forEach((row) => {
      const values = headers.map((h) => {
        const val = String(row[h] ?? "");
        // 转义引号和逗号
        if (val.includes(",") || val.includes('"') || val.includes("\n")) {
          return `"${val.replace(/"/g, '""')}"`;
        }
        return val;
      });
      csvLines.push(values.join(","));
    });
    const blob = new Blob([csvLines.join("\n")], { type: "text/csv;charset=utf-8" });
    saveAs(blob, `arxiv_papers_${formatDateForFile(new Date())}.csv`);
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
    // 用fetch下载PDF，然后保存本地
    const resp = await fetch(pdfUrl);
    if (!resp.ok) {
      // 如果fetch失败，直接在新窗口打开（让浏览器处理下载）
      window.open(pdfUrl, "_blank");
      return;
    }
    const blob = await resp.blob();
    const safeTitle = title.replace(/[^\w\u4e00-\u9fa5\- ]/g, "_").slice(0, 80);
    saveAs(blob, `${safeTitle}.pdf`);
    ElMessage.success("PDF下载已开始");
  } catch {
    // 出错时直接在新标签页打开
    window.open(pdfUrl, "_blank");
  }
};

// ========== 工具函数 ==========
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

// ========== 定时刷新：每日零点自动触发全量管线 ==========
const scheduleMidnightPipeline = () => {
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(0, 0, 0, 0);
  const msUntilMidnight = tomorrow.getTime() - now.getTime();

  // 检查今天是否已经运行过
  const lastRunDate = localStorage.getItem("arxivDailyPipelineLastRun");
  const today = formatDate(now);

  setTimeout(async () => {
    // 零点触发全量管线
    try {
      await fetch(`${apiBase}paper_agent/fetch_and_analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_papers: 200 }),
      });
      localStorage.setItem("arxivDailyPipelineLastRun", today);
      // 等待一段时间后刷新数据
      setTimeout(() => {
        fetchFullData();
      }, 60000);
    } catch (e) {
      console.error("定时管线触发失败:", e);
    }

    // 递归安排下一次
    scheduleMidnightPipeline();
  }, msUntilMidnight);
};

// ========== 生命周期 ==========
onMounted(async () => {
  // 加载更新时间
  const saved = localStorage.getItem("arxivDailyUpdateTime");
  updateTime.value = saved || formatDate(new Date());

  // 加载数据
  await fetchFullData();

  // 检查今天是否已经自动运行过管线，如果没有则立即运行
  const today = formatDate(new Date());
  const lastRun = localStorage.getItem("arxivDailyPipelineLastRun");
  if (lastRun !== today) {
    try {
      const resp = await fetch(`${apiBase}paper_agent/status`);
      if (resp.ok) {
        const status = await resp.json();
        if (!status.running) {
          // 空闲状态，触发管线
          const startResp = await fetch(`${apiBase}paper_agent/fetch_and_analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ max_papers: 200 }),
          });
          if (startResp.ok || startResp.status === 409) {
            localStorage.setItem("arxivDailyPipelineLastRun", today);
            // 等待一段时间后刷新数据
            setTimeout(() => {
              fetchFullData();
            }, 60000);
          }
        }
      }
    } catch (e) {
      console.error("自动触发管线失败:", e);
    }
  }

  // 安排每日零点自动触发
  scheduleMidnightPipeline();
});

onUnmounted(() => {
  // 页面销毁时不做特殊处理，定时器在 scheduleMidnightPipeline 中递归安排
});
</script>

<style scoped>
.arxiv-daily-container {
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

.tableBox {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  width: 100%;
  overflow-x: auto;
}

.tableBox :deep(.el-table) {
  width: 100%;
}

.buttonRow {
  height: 36px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 12px;
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

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.total-text {
  font-size: 14px;
  color: #606060;
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

.cell-text.hidden {
  display: none;
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

/* tooltip 内容样式（全局样式不 scope 才能穿透） */
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
</style>