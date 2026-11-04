<template>
  <div class="rankDetailContainer">
    <div class="rankDetailTitleContainer">
      <span style="padding: 0 8px;"></span>
      <!-- <el-icon @click="goBack" style="cursor: pointer;">
        <Back />
      </el-icon>
      <span @click="goBack" style="color:rgba(18, 19, 22, 0.8);cursor: pointer;">返回</span>-->
      <img src="/images/return.png" class="returnicon" @click="goBack" />
      <span style="padding: 0 20px;"></span>
      <span @click="goBack" style="color: #969696;cursor: pointer;">模型榜单</span>
      <span style="padding: 0 8px;font-weight:600;font-size:18px;">/</span>
      <span style="font-weight:600;font-size:18px;">{{ displayTitle }}</span>
    </div>
    <div class="cardContainer">
      <div class="tableContainer">
        <el-table
          :data="sortedModels"
          :header-cell-style="tableHeaderStyle"
          fit
          border
          show-header
          :expand-row-keys="expandedRowKeys"
          :row-key="row => row.id"
          class="scoreTable"
          @sort-change="handleSortChange"
          @filter-change="handleFilterChange"
          :default-sort="{ prop: 'averageScore', order: 'descending' }"
        >
          <el-table-column type="expand" width="1">
            <template #default="{ row }">
              <div v-if="isRowExpanded(row)" class="expanded-row-container">
                <table class="custom-score-table" style="width: 100%; border-collapse: collapse;">
                  <thead>
                    <tr>
                      <th
                        v-for="subject in expandedInfo.triSubsets"
                        :key="subject.name"
                      >{{ subject.name }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td
                        v-for="subject in expandedInfo.triSubsets"
                        :key="subject.name"
                      >{{ formatValue(subject.score) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </el-table-column>

          <el-table-column fixed label="名次" width="60" align="center">
            <template #default="{ $index }">
              <span>{{ $index + 1 }}</span>
            </template>
          </el-table-column>

          <el-table-column
            fixed
            prop="name"
            label="模型"
            column-key="name"
            :filters="modelFilters"
            :filter-method="filterModels"
            min-width="200"
          >
            <template #default="{ row }">
              <div class="verticalBox">
                <span>{{ row.name }}</span>
                <span class="bottomNote">{{ row.publisher }}</span>
              </div>
            </template>
            <template #header>
              <span>模型</span>
              <el-button style="margin-left: 8px; padding: 0; border: none; background: none;">
                <el-icon name="document" />
              </el-button>
            </template>
          </el-table-column>

          <el-table-column label="评测时间" min-width="110">
            <template #default="{ row }">
              <div class="verticalBox">
                <!-- <span>{{ formatDate(row.createTime) }}</span> -->
                <span>{{ formatDate(row.updateTime) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            prop="type"
            label="类型"
            column-key="type"
            :filters="typeFilters"
            :filter-method="filterTypes"
            min-width="90"
          >
            <template #default="{ row }">
              <el-tag>{{ row.type }}</el-tag>
            </template>
            <template #header>
              <span>类型</span>
              <el-button style="margin-left: 8px; padding: 0; border: none; background: none;">
                <el-icon name="document" />
              </el-button>
            </template>
          </el-table-column>

          <el-table-column
            prop="parameter"
            label="模型参数"
            column-key="parameter"
            :filters="parameterFilters"
            :filter-method="filterParameters"
            min-width="120"
          >
            <template #default="{ row }">
              <span>{{ row.parameter }}</span>
            </template>
            <template #header>
              <span>模型参数</span>
              <el-button style="margin-left: 8px; padding: 0; border: none; background: none;">
                <el-icon name="document" />
              </el-button>
            </template>
          </el-table-column>

          <el-table-column prop="averageScore" label="平均分" sortable="custom" min-width="170">
            <template #default="{ row }">
              <span>{{ formatValue(row.averageScore) }}</span>
            </template>
          </el-table-column>

          <el-table-column
            v-for="subsetName in getSubsetKeys(currentType)"
            :key="subsetName"
            :label="getLabel(currentType, subsetName)"
            :prop="subsetName"
            sortable="custom"
            min-width="170"
            align="center"
          >
            <template #default="scope">
              <div class="table-cell-container">
                <div class="cell-left">
                  <span
                    :class="{ 'bold-text': scope.row.highest.includes(subsetName) }"
                  >{{ formatValue(scope.row[subsetName]) }}</span>
                </div>
                <div class="cell-right" v-if="scope.row.highest.some(item=>item===subsetName)">
                  <img style="width: 80%; height: 80%;" src="/images/medel_yellow.png" />
                </div>
                <!-- <div
                  class="cell-right"
                  v-if="getTriSubsets(scope.row?.subsets || {}, subsetName).length > 0"
                >
                  <el-button
                    @click="toggleSubjectExpand(scope.row, subsetName)"
                    size="small"
                    :style="{
                        border: 'none',
                        backgroundColor: 'transparent',
                        padding: '0 5px',
                        height: 'auto',
                        width: 'auto',
                        lineHeight: '1',
                        verticalAlign: 'middle'
                      }"
                  >
                    <img
                      :src="isCellExpanded(scope.row, subsetName) ? ArrowUp : ArrowDown"
                      alt="Expand Icon"
                      class="expand-icon"
                    />
                  </el-button>
                </div>-->
              </div>
            </template>
          </el-table-column>
          <!-- <el-table-column label="操作" width="70">
            <template #default="scope">
              <el-tooltip content="回退" placement="top" effect="dark">
                <el-button link type="primary" size="large" @click="handelRefresh(scope.row)">
                  <el-icon>
                    <RefreshLeft />
                  </el-icon>
                </el-button>
              </el-tooltip>
            </template>
          </el-table-column>-->
        </el-table>

        <!-- <div class="pagination">
          <span class="total-text">总计: {{totalItems}}</span>
          <el-pagination
            background
            layout="sizes, prev, pager, next, jumper"
            :page-sizes="[10, 20]"
            :page-size="pageSize"
            :total="totalItems"
            @size-change="handleSizeChange"
            @current-change="handleCurrentChange"
          ></el-pagination>
        </div>-->
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="选择参数">
      <el-form>
        <el-form-item label="测试集">
          <el-select v-model="selectedParam1" placeholder="请选择测试集">
            <el-option
              v-for="item in options1"
              :key="getLabel(currentType,item)"
              :label="getLabel(currentType,item)"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="回退时间">
          <el-select v-model="selectedParam2" placeholder="请选择回退时间">
            <el-option
              v-for="item in options2"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="cancelConfirm">取消</el-button>
          <el-button type="primary" @click="confirmSelection">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import locale from "element-plus/es/locale/lang/zh-cn";
import { STRINGS } from "@/utils/Constants.js";
import { DATASET_MAPPING, useRankingStore } from "@/stores/rankingStore";
import { formatValue, formatDate } from "./utils";
import ArrowUp from "@/assets/ArrowUp.png";
import ArrowDown from "@/assets/ArrowDown.png";
import { ElMessage } from "element-plus";

// 加载数据
const models = ref([]);
const rankingStore = useRankingStore();
const loadData = async () => {
  try {
    await rankingStore.getRankingData();
    let rawData;
    if (currentType === "ruler1") {
      rawData = [...rankingStore.ruler1Values];
    } else {
      rawData = rankingStore.ruler2Values[currentType];
    }

    console.log("rawData");
    console.log(rawData);

    // 把每个子集分数挂到顶层字段
    models.value = rawData.map((row) => {
      const flatRow = { ...row };
      // console.log("flatRow");
      // console.log(flatRow);

      getSubsetKeys(currentType).forEach((subsetName) => {
        const matched = row.subsets.find((item) => item.key === subsetName);
        // console.log("matched");
        // console.log(matched);
        flatRow[subsetName] =
          matched?.score !== undefined ? matched.score : STRINGS.DASH;
        if (matched && matched.tri_subsets && matched.tri_subsets.length > 0) {
          flatRow[subsetName] = {};
          getSubsetKeys(subsetName).forEach((tri_subsetName) => {
            // console.log(tri_subsetName);
            const tri_matched = matched.tri_subsets.find(
              (item) => item.name === tri_subsetName
            );
            if (tri_matched) {
              // console.log("tri_matched!!!");
              // console.log(tri_matched);
              flatRow[subsetName][tri_subsetName] =
                tri_matched?.score !== undefined
                  ? tri_matched.score
                  : STRINGS.DASH;
            }
          });
        }
      });
      // console.log("flatRow");
      // console.log(flatRow);

      return flatRow;
    });

    //标记最高分测试集
    let dataSets = getSubsetKeys(currentType);
    // console.log("dataSets");
    // console.log(dataSets);
    dataSets.forEach((subSet) => {
      const triDatasets = getTriSubsetName(subSet);
      if (triDatasets && triDatasets.length > 0) {
        dataSets = dataSets.filter((item) => item !== subSet);
        dataSets = [...dataSets, ...triDatasets];
        // console.log("triDatasets");
        // console.log(triDatasets);
      }
    });
    console.log("dataSets");
    console.log(dataSets);

    const maxScores = {};
    models.value.forEach((model) => {
      Object.keys(model).forEach((key) => {
        if (key === "box_tool_use") {
          // console.log(model[key]);
          Object.keys(model[key]).forEach((tri) => {
            if (dataSets.some((dataset) => dataset === tri)) {
              if (!maxScores[tri] || model[key][tri] > maxScores[tri]) {
                maxScores[tri] = model[key][tri];
              }
            }
          });
        } else if (dataSets.some((dataset) => dataset === key)) {
          if (!maxScores[key] || model[key] > maxScores[key]) {
            maxScores[key] = model[key];
          }
        }
      });
    });

    console.log("maxScores");
    console.log(maxScores);

    models.value.forEach((model) => {
      model.highest = [];
      for (const key in model) {
        if (key === "box_tool_use") {
          console.log(Object.keys(model[key]));
          Object.keys(model[key]).forEach((tri) => {
            if (
              dataSets.some((dataset) => dataset === tri) &&
              model[key][tri] === maxScores[tri]
            ) {
              model.highest.push(tri);
            }
          });
        } else if (
          dataSets.some((dataset) => dataset === key) &&
          model[key] === maxScores[key]
        ) {
          model.highest.push(key);
        }
      }
    });

    console.log("models");
    console.log(models.value);
  } catch (error) {
    console.error("Error fetching data:", error);
  }
};

// 处理筛选
const selectedModelNames = ref([]);
const selectedTypes = ref([]);
const selectedParameters = ref([]);

const allModels = ref([]);
const allTypes = ref([]);
const allParameters = ref([]);

const filterModels = (values, row) => {
  return values.length === 0 || values.includes(row.name);
};

const filterTypes = (values, row) => {
  return values.length === 0 || values.includes(row.type);
};

const filterParameters = (values, row) => {
  return values.length === 0 || values.includes(row.parameter);
};

const modelFilters = computed(() => {
  const source = allModels.value || [];

  return source.map((name) => ({
    text: name,
    value: name,
  }));
});

const typeFilters = computed(() => {
  const source = allTypes.value || [];

  return source.map((name) => ({
    text: name,
    value: name,
  }));
});

const parameterFilters = computed(() => {
  const source = allParameters.value || [];

  return source.map((name) => ({
    text: name,
    value: name,
  }));
});

const handleFilterChange = (filters) => {
  selectedModelNames.value = filters.name || [];
  selectedTypes.value = filters.type || [];
  selectedParameters.value = filters.parameter || [];

  currentPage.value = 1;
};

const filteredModels = computed(() => {
  const modelValues = selectedModelNames.value;
  const typeValues = selectedTypes.value;
  const paramValues = selectedParameters.value;

  return models.value.filter((row) => {
    const matchModel =
      modelValues.length === 0 || modelValues.includes(row.name);
    const matchType = typeValues.length === 0 || typeValues.includes(row.type);
    const matchParam =
      paramValues.length === 0 || paramValues.includes(row.parameter);
    return matchModel && matchType && matchParam;
  });
});

// 处理排序
const sortConfig = ref({ prop: "", order: "" });

const handleSortChange = ({ column, prop, order }) => {
  sortConfig.value = { prop, order };
};

const sortedModels = computed(() => {
  if (!Array.isArray(models.value) || models.value.length === 0) {
    return [];
  }

  let { prop, order } = sortConfig.value;
  if (!prop || !order) {
    prop = "averageScore";
    order = "descending";
  }

  const isAsc = order === "ascending";
  return [...filteredModels.value].sort((a, b) => {
    const valA = parseFloat(a[prop]);
    const valB = parseFloat(b[prop]);

    const isValANumber = !isNaN(valA);
    const isValBNumber = !isNaN(valB);

    if (isValANumber && isValBNumber) {
      return isAsc ? valA - valB : valB - valA;
    }

    if (!isValANumber && !isValBNumber) return 0;
    if (!isValANumber) return isAsc ? -1 : 1;
    if (!isValBNumber) return isAsc ? 1 : -1;
  });
});

// 处理分页
const pageSize = ref(10);
const currentPage = ref(1);
const totalItems = computed(() => sortedModels.value.length);

const paginatedModels = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return sortedModels.value.slice(start, start + pageSize.value);
});

const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1; // 切换每页数量时回到第一页
};

const handleCurrentChange = (val) => {
  currentPage.value = val;
};

locale.el.pagination = {
  pagesize: "项/页",
  goto: "跳转",
  pageClassifier: "页",
};

// 展开行
const expandedRowKeys = ref(null);
const expandedInfo = ref(null);

const isRowExpanded = (row) => {
  return Boolean(
    expandedRowKeys.value && expandedRowKeys.value.includes(row.id)
  );
};

const isCellExpanded = (row, subsetName) => {
  return Boolean(
    expandedInfo.value &&
      expandedInfo.value.row &&
      expandedInfo.value.row === row &&
      expandedInfo.value.subsetName &&
      expandedInfo.value.subsetName === subsetName
  );
};

const toggleSubjectExpand = (row, subsetName) => {
  const subject = row.subsets.find((s) => s.key === subsetName);

  if (isRowExpanded(row)) {
    expandedRowKeys.value = [];
    expandedInfo.value = null;
  } else {
    expandedRowKeys.value = [row.id];
    expandedInfo.value = {
      row: row,
      subsetName: subsetName,
      triSubsets: subject?.tri_subsets || [],
    };
  }
};

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
};

const typeConfig = {
  ruler1: {
    title: "大语言模型榜单详情",
  },
  operations: {
    title: "运维智能榜单详情",
  },
  service: {
    title: "业务智能榜单详情",
  },
  box_tool_use: {
    title: "算力主机榜单详情",
  },
  aisf_llm_gaixie: {
    title: "AISF LLM 改写",
  },
  aisf_llm_yitu: {
    title: "AISF LLM 意图",
  },
};

const getSubsetKeys = (field) => {
  const fieldMapping = DATASET_MAPPING[field];
  return fieldMapping?.subsets || [];
};
const getTriSubsetName = (obj) => {
  const fieldMapping = DATASET_MAPPING[obj];
  return fieldMapping?.subsets || [];
};

const getLabel = (datasetKey, subsetName) => {
  return DATASET_MAPPING[datasetKey]?.labels?.[subsetName] || subsetName;
};

const getCellWidth = (inputString) => {
  return 60 + inputString.length * 12;
};

const getTriSubsets = (subsets, subsetName) => {
  const matched = subsets.find((item) => item.key === subsetName);

  if (matched && currentType === "service") {
    return matched.tri_subsets;
  } else {
    return [];
  }
};

const dialogVisible = ref(false);
const selectedParam1 = ref("");
const selectedParam2 = ref("");
const options1 = ref([]);
const options2 = ref([
  { value: "optionA", label: "选项A" },
  { value: "optionB", label: "选项B" },
]);

const handelRefresh = (row) => {
  console.log(row);
  options1.value = getSubsetKeys(currentType);
  console.log(options1.value);
  dialogVisible.value = true;
};

const confirmSelection = () => {
  ElMessage({
    message: `您选择了: 参数1 - ${selectedParam1.value}, 参数2 - ${selectedParam2.value}`,
    type: "success",
  });
  selectedParam1.value = "";
  selectedParam2.value = "";
  dialogVisible.value = false;
};

const cancelConfirm = () => {
  selectedParam1.value = "";
  selectedParam2.value = "";
  dialogVisible.value = false;
};

// 路由和标题显示
const route = useRoute();
const currentType = (route.query.type as string) || "ruler1";
const config = typeConfig[currentType] || typeConfig["ruler1"];
const displayTitle = computed(() => config.title);

const router = useRouter();
const goBack = () => {
  router.back();
};

// 组件挂载时加载数据
onMounted(async () => {
  await loadData();

  allModels.value = [...new Set(models.value.map((item) => item.name))];
  allTypes.value = [...new Set(models.value.map((item) => item.type))];
  allParameters.value = [
    ...new Set(models.value.map((item) => item.parameter)),
  ];

  selectedModelNames.value = [...allModels.value];
  selectedTypes.value = [...allTypes.value];
  selectedParameters.value = [...allParameters.value];
});

const testData = [
  {
    id: 0,
    name: "name_01",
    class01: 90,
    class02: 85,
  },
  {
    id: 1,
    name: "name_02",
    class01: 80,
    class02: 100,
  },
];
</script>

<style scoped>
.tableContainer {
  height: 100%;
  /* overflow-x: auto;
  overflow-y: auto; */
  margin: 0 auto;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  white-space: nowrap;
}

.scoreTable {
  font-size: medium;
  /* min-width: max-content; */
  /* height: calc(100% - 500px); */
  height: 100%;
  width: 100%;
  table-layout: auto;
  white-space: nowrap;
}

.score_table .el-table__row {
  height: 67px;
}

:deep(.el-table__expand-column) {
  visibility: hidden;
}

.scoreTable td .cell {
  white-space: nowrap;
  padding: 8px 12px;
}

.scoreTable :deep(th) {
  font-size: 14px;
}

.scoreTable :deep(td) {
  font-size: 14px;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.total-text {
  color: #666;
  font-size: 16px;
}

:deep(.el-table__expanded-cell) {
  background-color: #f4f3f9 !important;
}

.expanded-row-container {
  margin: 10px 20px;
  display: table !important;
  width: 100%;
}

.custom-score-table {
  border-collapse: collapse;
  table-layout: auto;
  width: fit-content;
  background: transparent;
}

.custom-score-table th,
.custom-score-table td {
  text-align: left;
  border: none;
}

.custom-score-table th {
  color: #000;
  background-color: #fff;
  font-weight: normal;
  white-space: nowrap;
}

.custom-score-table td {
  background-color: #f4f3f9;
}

.table-cell-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.cell-left {
  text-align: left;
  flex: 1;
}

.cell-right {
  display: flex;
  align-items: center;
  height: 100%;
}

.expand-icon {
  width: 10%;
  height: 10%;
  vertical-align: middle;
  object-fit: contain;
}

.verticalBox {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.bottomNote {
  color: #999;
  font-size: 10px;
  margin-top: 4px;
}

.rankDetailTitleContainer {
  position: relative;
  align-items: center;
  color: rgba(18, 19, 22, 0.8);
  background-color: #fff;
  line-height: 50px;
  /* height: 36px; */
  height: 50px;
  margin-bottom: 18px;
}

.rankDetailContainer {
  height: 100%;
}

.cardContainer {
  height: calc(100% - 100px);
}

.bold-text {
  font-weight: bold;
}
</style>