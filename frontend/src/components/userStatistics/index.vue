<template>
  <div class="user-statistics" v-loading="Loading">
    <!-- ======== 筛选栏：仅日期范围 ======== -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="20" align="middle">
        <el-col :span="8">
          <span class="filter-label">日期范围：</span>
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            unlink-panels
            range-separator="至"
            start-placeholder="起始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            @change="handleFilterChange"
          />
        </el-col>
      </el-row>
    </el-card>

    <!-- ======== 统计卡片 ======== -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ overview.total_operations }}</div>
          <div class="stat-label">总操作次数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ overview.active_users }}</div>
          <div class="stat-label">活跃用户数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ overview.daily_avg }}</div>
          <div class="stat-label">日均操作</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ overview.peak_day ? overview.peak_day.count : '-' }}</div>
          <div
            class="stat-label"
          >峰值日{{ overview.peak_day ? '(' + overview.peak_day.date + ')' : '' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ======== 图表区域 ======== -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="14">
        <el-card shadow="never">
          <UserTrendChart
            v-if="trendData.xAxis.length"
            :x-axis="trendData.xAxis"
            :series="trendData.series"
            height="400px"
          />
          <el-empty style=" height:400px" v-else description="暂无趋势数据" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <UserTypePieChart v-if="typeDistData.length" :data="typeDistData" height="400px" />
          <el-empty style=" height:400px" v-else description="暂无分布数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="chart-row">
      <el-col :span="14">
        <el-card shadow="never">
          <UserDeptBarChart
            v-if="deptData.dept4 && deptData.dept4.names.length"
            :data="deptData"
            height="400px"
          />
          <el-empty style=" height:400px" v-else description="暂无部门统计数据" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <UserActiveBarChart
            v-if="topUsersData.users.length"
            :users="topUsersData.users"
            :counts="topUsersData.counts"
            height="430px"
          />
          <el-empty style=" height:430px" v-else description="暂无排行数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- ======== 操作明细表格 ======== -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <span>操作明细</span>
          <div class="table-filters">
            <el-input
              v-model="detailKeyword"
              placeholder="搜索用户名"
              clearable
              style="width: 180px; margin-right: 12px"
              @change="handleDetailFilterChange"
            />
            <el-select
              v-model="detailTypes"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="操作类型"
              style="width: 180px"
              @change="handleDetailFilterChange"
            >
              <el-option label="全部" value />
              <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </div>
        </div>
      </template>
      <el-table
        v-loading="detailLoading"
        :data="detailRecords"
        stripe
        style="width: 100%"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-content">
              <p>
                <strong>完整请求：</strong>
              </p>
              <pre>{{ row.query || '无' }}</pre>
              <p>
                <strong>完整响应：</strong>
              </p>
              <pre>{{ row.response || '无' }}</pre>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="user_id" label="用户" width="120" />
        <el-table-column
          prop="dept"
          label="部门"
          width="500"
          show-overflow-tooltip
          :formatter="(row) => row.dept || '获取中...'"
        />
        <el-table-column prop="timestamp" label="时间" width="200" />
        <el-table-column prop="type" label="操作类型" width="250" />
        <el-table-column prop="model_id" label="模型" width="300" />
        <el-table-column prop="content" label="内容摘要" min-width="200" show-overflow-tooltip />
      </el-table>
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="detailPage"
          v-model:page-size="detailPageSize"
          :total="detailTotal"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="fetchDetails"
          @current-change="fetchDetails"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import {
  getOverview,
  getTrend,
  getTypeDistribution,
  getDepartmentStats,
  getTopUsers,
  getDetails,
  getTypeCandidates,
} from "@/api/userStatistics.js";
import UserTrendChart from "./charts/UserTrendChart.vue";
import UserTypePieChart from "./charts/UserTypePieChart.vue";
import UserDeptBarChart from "./charts/UserDeptBarChart.vue";
import UserActiveBarChart from "./charts/UserActiveBarChart.vue";

const Loading = ref(true);

// ===================== 筛选条件（仅日期范围影响图表） =====================
const dateRange = ref([]);
const typeOptions = ref([]);

// ===================== 明细表格筛选（仅影响明细） =====================
const detailKeyword = ref("");
const detailTypes = ref([]);

async function fetchTypeCandidates() {
  try {
    const { data } = await getTypeCandidates();
    if (data.code === 0) {
      typeOptions.value = (data.data.types || []).map((t) => ({
        label: t,
        value: t,
      }));
    }
  } catch (e) {
    console.error("获取操作类型候选列表失败", e);
  }
}

// ===================== 概览卡片 =====================
const overview = reactive({
  total_operations: 0,
  active_users: 0,
  daily_avg: 0,
  peak_day: null,
});

// ===================== 图表数据 =====================
const trendData = reactive({ xAxis: [], series: [] });
const typeDistData = ref([]);
const deptData = reactive({
  dept4: { names: [], counts: [] },
  dept5: { names: [], counts: [] },
  dept6: { names: [], counts: [] },
});
const topUsersData = reactive({ users: [], counts: [] });

// ===================== 明细表格 =====================
const detailLoading = ref(false);
const detailRecords = ref([]);
const detailTotal = ref(0);
const detailPage = ref(1);
const detailPageSize = ref(20);

// ===================== 数据获取 =====================
function buildParams() {
  const params = {};
  if (dateRange.value && dateRange.value.length === 2) {
    params.start_date = dateRange.value[0];
    params.end_date = dateRange.value[1];
  }
  return params;
}

async function fetchOverview() {
  try {
    const { data } = await getOverview(buildParams());
    if (data.code === 0) {
      Object.assign(overview, data.data);
    }
  } catch (e) {
    console.error("获取概览数据失败", e);
  }
}

async function fetchTrend() {
  try {
    const { data } = await getTrend(buildParams());
    if (data.code === 0) {
      trendData.xAxis = data.data.xAxis || [];
      trendData.series = data.data.series || [];
    }
  } catch (e) {
    console.error("获取趋势数据失败", e);
  }
}

async function fetchTypeDistribution() {
  try {
    const { data } = await getTypeDistribution(buildParams());
    if (data.code === 0) {
      typeDistData.value = data.data.items || [];
    }
  } catch (e) {
    console.error("获取类型分布失败", e);
  }
}

function filterDept(dept) {
  if (!dept || !dept.names) return { names: [], counts: [] };
  const filtered = dept.names.reduce(
    (acc, name, i) => {
      if (name !== "[]") {
        acc.names.push(name);
        acc.counts.push(dept.counts[i]);
      }
      return acc;
    },
    { names: [], counts: [] }
  );
  return filtered;
}

async function fetchDeptStats() {
  try {
    const { data } = await getDepartmentStats(buildParams());
    if (data.code === 0) {
      const d = data.data;
      deptData.dept4 = filterDept(d.dept4);
      deptData.dept5 = filterDept(d.dept5);
      deptData.dept6 = filterDept(d.dept6);
    }
  } catch (e) {
    console.error("获取部门统计失败", e);
  }
}

async function fetchTopUsers() {
  try {
    const { data } = await getTopUsers(buildParams());
    if (data.code === 0) {
      topUsersData.users = data.data.users || [];
      topUsersData.counts = data.data.counts || [];
    }
  } catch (e) {
    console.error("获取用户排行失败", e);
  }
}

async function fetchDetails() {
  detailLoading.value = true;
  try {
    const params = {
      ...buildParams(),
      page: detailPage.value,
      page_size: detailPageSize.value,
    };
    if (detailKeyword.value) params.keyword = detailKeyword.value;
    if (detailTypes.value.length) params.types = detailTypes.value.join(",");
    const { data } = await getDetails(params);
    if (data.code === 0) {
      detailRecords.value = data.data.records || [];
      detailTotal.value = data.data.total || 0;
    }
  } catch (e) {
    console.error("获取明细失败", e);
  } finally {
    detailLoading.value = false;
  }
}

// ===================== 事件处理 =====================
async function handleFilterChange() {
  Loading.value = true;
  detailPage.value = 1;
  try {
    await Promise.all([
      fetchOverview(),
      fetchTrend(),
      fetchTypeDistribution(),
      fetchDeptStats(),
      fetchTopUsers(),
      fetchDetails(),
    ]);
  } finally {
    Loading.value = false;
  }
}

/** 明细筛选（关键词/类型）变化时：重置到第1页再查询 */
function handleDetailFilterChange() {
  detailPage.value = 1;
  fetchDetails();
}

function handleExpandChange(row) {
  console.log("展开行", row.user_id);
}

// ===================== 生命周期 =====================
onMounted(async () => {
  await fetchTypeCandidates();
  handleFilterChange();
});
</script>

<style scoped>
.user-statistics {
  padding: 16px 20px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

/* ---- 统计卡片 ---- */
.stat-cards {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  cursor: default;
  border-radius: 8px;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-card .stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 6px;
}

/* ---- 图表行 ---- */
.chart-row {
  margin-bottom: 16px;
}

/* ---- 明细表格 ---- */
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.table-filters {
  display: flex;
  align-items: center;
}

.table-card {
  margin-bottom: 16px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.expand-content pre {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  max-height: 300px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>