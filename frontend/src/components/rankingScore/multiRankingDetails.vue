<template>
  <div class="container">
    <div class="titleContainer">
      <span style="padding: 0 8px;"></span>
      <img src="/images/return.png" class="returnicon" @click="goBack" style="left:16px;" />
      <span style="padding: 0 20px;"></span>
      <span @click="goBack" style="color: #969696;cursor: pointer;">模型榜单</span>
      <span style="padding: 0 8px;font-size:18px;font-weight:600;">/</span>
      <span style="font-size:18px;font-weight:600;">{{ displayTitle }}</span>
    </div>
    <div class="cardContainer">
      <div class="tableContainer">
        <el-table
          :data="tableData"
          :header-cell-style="tableHeaderStyle"
          fit
          show-header
          border
          :expand-row-keys="expandedRowKeys"
          :row-key="row => row.id"
          class="scoreTable"
          @sort-change="handleSortChange"
          @filter-change="handleFilterChange"
          :default-sort="{ prop: 'averageScore', order: 'descending' }"
        >

          <el-table-column label="名次" width="60">
            <template #default="{ $index }">
              <span>{{ $index + 1 }}</span>
            </template>
          </el-table-column>

          <el-table-column
            prop="name"
            label="模型"
            column-key="name"
            :filters="modelFilters"
            :filter-method="filterModels"
            filter-multiple
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

          <el-table-column label="评测时间" min-width="100">
            <template #default="{ row }">
              <div class="verticalBox">
                <!-- <span>{{ formatDate(row.createTime) }}</span> -->
                <span>{{ formatDate(row.updateTime) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="averageScore" label="平均分" sortable="custom" min-width="100">
            <template #default="{ row }">
              <span>{{ formatValue(row.averageScore) }}</span>
            </template>
          </el-table-column>

          <!-- <div v-show="currentType==='multiRuler1'"> -->
          <el-table-column
            v-for="(column, index) in getSubsetKeys(currentType)"
            :key="index"
            :label="getLabel(currentType,column)"
            sortable="custom"
            min-width="100"
          >
            <!-- :min-width="getCellWidth(column)" -->
            <template #default="{ row }">
              <div class="table-cell-container">
                <div class="cell-left">
                  <span>{{ formatValue(row[column]) }}</span>
                </div>
                <div class="cell-right" v-if="row.highest.some(item=>item===column)">
                  <img style="width: 80%; height: 80%;" src="/images/medel_yellow.png" />
                </div>
              </div>
            </template>
          </el-table-column>
        </el-table>
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
import { DATASET_MAPPING } from "@/stores/rankingStore";
import { formatValue, formatDate } from "./utils";
import { getMultiModelData } from "@/api/dataService.js";

const tableData = ref([]);

// 处理筛选
const selectedModelNames = ref([]);
const selectedTypes = ref([]);
const selectedParameters = ref([]);

const allModels = ref([]);

const filterModels = (values, row) => {
  return values.length === 0 || values.includes(row.name);
};

const modelFilters = computed(() => {
  const source = allModels.value || [];

  return source.map((name) => ({
    text: name,
    value: name,
  }));
});

const handleFilterChange = (filters) => {
  selectedModelNames.value = filters.name || [];
  selectedTypes.value = filters.type || [];
  selectedParameters.value = filters.parameter || [];
};

// 处理排序
const sortConfig = ref({ prop: "", order: "" });

const handleSortChange = ({ column, prop, order }) => {
  sortConfig.value = { prop, order };
};

// 展开行
const expandedRowKeys = ref(null);
const expandedInfo = ref(null);

const isRowExpanded = (row) => {
  return Boolean(
    expandedRowKeys.value && expandedRowKeys.value.includes(row.id)
  );
};

const tableHeaderStyle = {
  backgroundColor: "#f5f6fd",
  color: "#000000",
};

const typeConfig = {
  multiRuler1: {
    title: "多模态通用榜单详情",
  },
  multiaisf_banxue: {
    title: "AISF-伴学榜单详情",
  },
  multiaisf_gui_plan: {
    title: "AISF-GUI规划榜单详情",
  },
  multiaisf_gui_vla: {
    title: "AISF-GUI操控榜单详情",
  },
};

const getSubsetKeys = (field) => {
  const fieldMapping = DATASET_MAPPING[field];
  return fieldMapping?.subsets || [];
};

const getLabel = (datasetKey, subsetName) => {
  return DATASET_MAPPING[datasetKey]?.labels?.[subsetName] || subsetName;
};

// 路由和标题显示
const route = useRoute();
const currentType = (route.query.type as string) || "multiRuler1";
const currentSubType = (route.query.subType as string) || "";
const config = typeConfig[currentType] || typeConfig["multiRuler1"];
const displayTitle = computed(() => config.title);

const router = useRouter();
const goBack = () => {
  router.back();
};

const multiModelRuler1DataInfo = ref([]);

const loadMultiRuler1Data = (data) => {

  const ruler1Array = [];
  const ruler1Models = Object.keys(data);

  ruler1Models.forEach((modelName) => {
    const model = data[modelName];
    const result = model.result;
    const dataSets = result.map((item) => {
      return {
        name: item.dataset_name,
        score: item.score,
      };
    });
    // console.log(dataSets);
    let sum = 0;

    sum = result.reduce((acc, cur) => {
      return acc + cur.score;
    }, 0);
    const averageScore = result.length > 0 ? sum / result.length : 0;
    const newObj = {
      name: modelName,
      publisher: model.publisher,
      averageScore: averageScore,
      new: model.is_new,
      updateTime: model.update_date,
    };
    getSubsetKeys("multiRuler1").forEach((subsetName) => {
      const matched = dataSets.find((item) => item.name === subsetName);
      newObj[subsetName] =
        matched?.score !== undefined ? matched.score : STRINGS.DASH;
    });
    // console.log(newObj);
    ruler1Array.push(newObj);
  });

  //标记最高分测试集
  const dataSets = getSubsetKeys(currentType);
  const maxScores = {};
  ruler1Array.forEach((model) => {
    Object.keys(model).forEach((key) => {
      if (dataSets.some((dataset) => dataset === key)) {
          if (model[key] === "-") {
              return
          }
          if (!maxScores[key] || model[key] > maxScores[key]) {
              maxScores[key] = model[key];
          }
      }
    });
  });

  ruler1Array.forEach((models) => {
    models.highest = [];
    for (const key in models) {
      if (
        dataSets.some((dataset) => dataset === key) &&
        models[key] === maxScores[key]
      ) {
        models.highest.push(key);
      }
    }
  });

    multiModelRuler1DataInfo.value = ruler1Array.sort((a, b) => b.averageScore - a.averageScore);

    allModels.value = [
        ...new Set(multiModelRuler1DataInfo.value.map((item) => item.name)),
    ];
};

const multiModelRuler2DataInfo = ref([]);

const loadMultiRuler2Data = (data) => {
  const transformedArray = [];
  const modelNames = Object.keys(data);
  modelNames.forEach((modelName) => {
    const model = data[modelName];
    const result = model.result[0];
    const subsets = result.metrics[0].categories[0].subsets;
    const tri_subsets = {};

    const newObj = {
      name: modelName,
      publisher: model.publisher,
      averageScore: result.score,
      new: model.is_new,
      updateTime: model.update_date,
    };

    subsets.forEach((subset) => {
      if (subset.tri_subsets && subset.tri_subsets.length > 0) {
        subset.tri_subsets.forEach((tri_subset) => {
          newObj[tri_subset.name] = tri_subset.score;
        });
      } else {
        newObj[subset.name] = subset.score;
      }
    });

    transformedArray.push(newObj);
  });
  transformedArray.sort((a, b) => b.averageScore - a.averageScore);

  const dataSets = getSubsetKeys(currentType);
  const maxScores = {};
  transformedArray.forEach((model) => {
    Object.keys(model).forEach((key) => {
      if (dataSets.some((dataset) => dataset === key)) {
        if (!maxScores[key] || model[key] > maxScores[key]) {
          maxScores[key] = model[key];
        }
      }
    });
  });
  transformedArray.forEach((models) => {
    models.highest = [];
    for (const key in models) {
      if (
        dataSets.some((dataset) => dataset === key) &&
        models[key] === maxScores[key]
      ) {
        models.highest.push(key);
      }
    }
  });

  multiModelRuler2DataInfo.value = transformedArray;
  allModels.value = [
    ...new Set(multiModelRuler2DataInfo.value.map((item) => item.name)),
  ];
};

const dynamicColumns = computed(() => {
  if (
    currentType === "multiRuler1" ||
    multiModelRuler2DataInfo.value.length === 0
  )
    return [];
  const firstRow = multiModelRuler2DataInfo.value[0];
  return Object.keys(firstRow).filter(
    (key) =>
      ![
        "name",
        "averageScore",
        "new",
        "publisher",
        "rank",
        "updateTime",
      ].includes(key)
  );
});

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

function filterCurLabelData(ori_data, label) {
  const result = {};
  for (const out_key in ori_data) {
    const filteredItems = ori_data[out_key]['result'].filter(item => item.dataset_name === label);
    if (filteredItems.length > 0) {
      ori_data[out_key]['result'] = filteredItems;
      result[out_key] = ori_data[out_key]
    }
  }
  return result
}

const loadData = async () => {
  try {
    const data = (await getMultiModelData()).data;
    if (currentType === "multiRuler1") {
      loadMultiRuler1Data(data.ruler1);
      tableData.value = multiModelRuler1DataInfo.value;
    } else {
      let ruler2Data = data.ruler2;
      ruler2Data = filterCurLabelData(ruler2Data, currentSubType)
      loadMultiRuler2Data(ruler2Data);
      tableData.value = multiModelRuler2DataInfo.value;
    }
  } catch (error) {
    console.error("Error fetching data:", error);
  }
};

onMounted(async () => {
  loadData();
});
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

.titleContainer {
  background-color: #fff;
}

.container {
  /* padding: 0; */
  margin: 0;
  max-width: 100%;
  height: 100%;
}

.cardContainer {
  height: calc(100% - 100px);
}
</style>