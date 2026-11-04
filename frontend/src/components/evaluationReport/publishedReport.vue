<template>
    <div class="container">
        <div class="titleContainer">
            <span style="padding: 0 5px"></span>
            <img src="/images/return.png" class="returnicon" @click="goBack" style="left:10px;" />
            <span style="padding: 0 20px;"></span>
            <span style="font-size:18px;font-weight:600;">已发布报告</span>
        </div>

        <div class="report-header-buttons" style="justify-content: space-between;">
            <div class="report-type-section">
                <el-button type="primary" class="customButton" @click="uploadReport()">发布报告</el-button>
            </div>

            <el-table :data="tempTasksData" stripe height="750px" :header-cell-style="tableHeaderStyle"
                :row-key="(row) => row.id" :expand-row-keys="expandedRowKeys" @expand-change="onExpandChange"
                v-loading="loading" element-loading-text="加载中...">
                <el-table-column type="expand">
                    <template #default="props">
                        <div v-for="(reportTypes, baseModel) in props.row.types" :key="baseModel"
                            style="margin-bottom:12px;">
                            <div style="font-weight:600;font-size:14px;margin-bottom:6px;color:#303133;">{{ baseModel }}
                            </div>
                            <el-descriptions border direction="vertical">
                                <el-descriptions-item v-for="(info, reportType) in reportTypes" :key="reportType"
                                    :label="reportType">
                                    {{info?.filter((item) => {
                                        return item !== baseModel
                                    }).join(', ') || '无'}}
                                </el-descriptions-item>
                            </el-descriptions>
                        </div>
                    </template>
                </el-table-column>
                <el-table-column prop="id" label="发布报告ID" align="center" show-overflow-tooltip />
                <el-table-column prop="report_name" label="报告名称" align="center" show-overflow-tooltip width="500" />
                <el-table-column prop="task_id" label="任务ID" align="center" show-overflow-tooltip />
                <el-table-column prop="model_names" label="基准模型" align="center" show-overflow-tooltip />
                <!-- <el-table-column prop="status" label="状态" align="center">
                    <template #default="{ row }">
                        <el-tag :type="statusTagType(row.status)" size="large" v-if="row.status !== 'failed'">{{
                            row.status }}</el-tag>
                        <el-tooltip :content="row.error" placement="top" v-else>
                            <el-tag :type="statusTagType(row.status)" size="large">{{ row.status }}</el-tag>
                        </el-tooltip>
                    </template>
        </el-table-column>-->
                <!-- <el-table-column prop="create_time" label="任务创建时间" align="center" />
                <el-table-column prop="complete_time" label="任务结束时间" align="center">
                    <template #default="{ row }">{{ row.complete_time || '-' }}</template>
        </el-table-column>-->
                <!-- <el-table-column prop="userName" label="任务创建人" align="center" /> -->
                <el-table-column prop="publish_time" label="发布时间" align="center" />
                <el-table-column prop="publisher" label="发布人" align="center" />
                <el-table-column label="操作" align="center" width="140">
                    <template #default="{ row }">
                        <el-tooltip content="下载" placement="top">
                            <el-button link type="primary" size="large" :disabled="row.status !== 'completed'"
                                @click="downloadTaskReport(row)">
                                <el-icon>
                                    <Download />
                                </el-icon>
                            </el-button>
                        </el-tooltip>
                        <el-tooltip content="预览" placement="top">
                            <el-button link type="primary" size="large" :disabled="row.status !== 'completed'"
                                @click="previewReport(row)">
                                <el-icon>
                                    <View />
                                </el-icon>
                            </el-button>
                        </el-tooltip>
                        <el-tooltip v-if="row.can_edit !== false" content="删除" placement="top">
                            <el-button link type="danger" size="large" :disabled="row.status === 'running'"
                                @click="handleDeleteTask(row)">
                                <el-icon>
                                    <Delete />
                                </el-icon>
                            </el-button>
                        </el-tooltip>
                        <el-tooltip v-if="row.can_edit !== false" content="更新" placement="top">
                            <el-button link type="primary" size="large" :disabled="row.status !== 'completed'"
                                @click="handleUpdateReport(row)">
                                <el-icon>
                                    <Refresh />
                                </el-icon>
                            </el-button>
                        </el-tooltip>
                    </template>
                </el-table-column>
            </el-table>
        </div>

        <el-dialog v-model="uploadDialogVisible" title="发布报告" width="760px" :close-on-click-modal="false"
            :before-close="handleExcelDialogClose">
            <div style="display:flex;flex-direction:column;gap:16px;">
                <!-- 报告名称 -->
                <div style="display:flex;align-items:flex-start;gap:8px;">
                    <span
                        style="white-space:nowrap;font-size:13px;color:#606266;min-width:56px;line-height:32px;">报告名称</span>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        <el-input v-model="reportName" placeholder="留空则自动生成报告名称" style="width: 540px" clearable />
                        <div v-if="!reportName && autoReportName"
                            style="font-size:12px;color:#909399;padding-left:4px;line-height:1.3;">
                            <span style="color:#606266;">自动命名：</span>
                            {{ autoReportName }}
                        </div>
                    </div>
                    <el-tooltip content="未输入时将根据基准模型和报告类型自动命名，随选择实时变更" placement="top">
                        <el-icon style="color:#909399;cursor:pointer;margin-top:6px;">
                            <InfoFilled />
                        </el-icon>
                    </el-tooltip>
                </div>
                <!-- 基准模型输入 -->
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="white-space:nowrap;font-size:13px;color:#606266;min-width:56px;">基准模型</span>
                    <el-input v-model="baseModelInput" placeholder="多个模型用&amp;连接，例如 Qwen3.5-27B&amp;Qwen3.6-72B（最多3个）"
                        style="width: 540px" clearable @update:model-value="onBaseModelInputChange" />
                    <el-tag v-if="parsedBaseModels.length > 0" type="info" size="small">已解析 {{ parsedBaseModels.length
                    }}/3
                        个模型</el-tag>
                </div>

                <!-- 每个基准模型分别选报告类型和对比模型 -->
                <template v-for="bm in parsedBaseModels" :key="bm">
                    <div style="border:1px solid #e8e8e8;border-radius:6px;padding:12px;">
                        <div style="font-size:14px;font-weight:600;margin-bottom:10px;color:#303133;">{{ bm }}</div>
                        <div style="display:flex;flex-direction:column;gap:10px;">
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span
                                    style="white-space:nowrap;font-size:13px;color:#606266;min-width:56px;">报告类型</span>

                                <el-select :model-value="getBaseModelReportTypes(bm)" multiple collapse-tags
                                    collapse-tags-tooltip placeholder="选择报告类型，模型暂无分数的类型为灰" style="width: 540px"
                                    @update:model-value="(v) => setBaseModelReportTypes(bm, v)">
                                    <el-option-group v-for="group in getGroupedReportTypeOptions(bm)" :key="group.label"
                                        :label="group.label">
                                        <el-option v-for="item in group.options" :key="item.value" :label="item.label"
                                            :value="item.value">
                                            <span>{{ item.label }}</span>
                                        </el-option>
                                    </el-option-group>
                                </el-select>
                            </div>
                            <div v-for="rt in getBaseModelReportTypes(bm)" :key="rt"
                                style="display:flex;align-items:center;gap:8px;padding-left:64px;">
                                <span class="report-type-label-dialog">{{ getReportTypeLabel(rt) }}对比模型</span>
                                <el-select :model-value="getBaseModelCompareModels(bm, rt)" multiple :multiple-limit="5"
                                    collapse-tags collapse-tags-tooltip placeholder="选择对比模型，可输入模型名进行筛选(不分大小写)" style="width: 420px"
                                    @update:model-value="(v) => setBaseModelCompareModels(bm, rt, v)" filterable>
                                    <el-option v-for="item in getCompareModelOptions(bm, rt)" :key="item.value"
                                        :label="item.label" :value="item.value" />
                                </el-select>
                            </div>
                        </div>
                    </div>
                </template>

                <!-- 文件上传 -->
                <div v-if="parsedBaseModels.length > 0" style="border-top:1px solid #e8e8e8;padding-top:12px;">
                    <el-upload ref="upload" drag action :http-request="uploadFile" :on-success="handleSuccess"
                        :on-error="handleError" :limit="1" :on-exceed="handleExceed" accept=".ppt, .pptx, .pdf">
                        <el-icon class="el-icon--upload">
                            <upload-filled />
                        </el-icon>
                        <div class="el-upload__text">
                            将文件拖到此处，或
                            <em>点击上传</em>
                        </div>
                        <div class="el-upload__tip" slot="tip">只能上传PPT/PPTX、PDF文件</div>
                    </el-upload>
                </div>
            </div>
            <template #footer>
                <el-button @click="handleExcelDialogClose">取消</el-button>
                <el-button type="primary" @click="handlePublishConfirm">确认发布</el-button>
            </template>
        </el-dialog>

        <!-- 更新报告文件弹窗 -->
        <el-dialog v-model="updateDialogVisible" title="更新报告文件" width="480px" :close-on-click-modal="false"
            :before-close="handleUpdateDialogClose">
            <div style="padding: 8px 0; display:flex; flex-direction:column; gap:12px;">
                <div style="font-size:13px;color:#606266;line-height:1.5;">
                    请选择新的报告文件上传，将<span style="color:#f56c6c;">覆盖</span>原报告文件（文件路径与文件名保持不变）。
                </div>
                <el-upload ref="updateUpload" drag action :http-request="updateUploadFile" :limit="1"
                    :on-exceed="handleUpdateExceed" accept=".ppt, .pptx, .pdf">
                    <el-icon class="el-icon--upload">
                        <upload-filled />
                    </el-icon>
                    <div class="el-upload__text">
                        将文件拖到此处，或
                        <em>点击上传</em>
                    </div>
                    <div class="el-upload__tip" slot="tip">只能上传PPT/PPTX、PDF文件</div>
                </el-upload>
            </div>
            <template #footer>
                <el-button @click="handleUpdateDialogClose">取消</el-button>
                <el-button type="primary" @click="handleUpdateConfirm">确认更新</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox, UploadInstance } from "element-plus";
import { View, InfoFilled, Refresh } from "@element-plus/icons-vue";
import {
    downloadEvalReport,
    getAllPublishedTasks,
    deletePublishedTask,
    directPublishReport,
    updatePublishedReport
} from "@/api/runService.js";
import { getCurrentFullRes, getMultiModelData } from "@/api/dataService.js";

const router = useRouter();
const goBack = () => {
    router.back();
};

const props = defineProps({});

const tempTasksData = ref([]);
const expandedRowKeys = ref([]);
const loading = ref(false);

const onExpandChange = (row, expandedRows) => {
    expandedRowKeys.value = expandedRows.map((r) => r.id);
};

const statusTagType = (status) => {
    switch (status) {
        case "completed":
            return "success";
        case "running":
            return "primary";
        case "failed":
            return "danger";
        default:
            return "warning";
    }
};

const emit = defineEmits(["report-generated"]);

/** 基准模型在各报告类型下是否有数据 */
const baseModelExistsMap = ref({});

// ========== 数据加载 ==========

/** ruler1Data: { [modelKey]: {...} } — key 存在即表示该模型有 ruler1 数据 */
let ruler1Data = null;
/** ruler2Data: { [modelKey]: { result: [{ dataset_name, metrics, ...}] } } */
let ruler2Data = null;
let mmlRuler1Data = null;
let mmlRuler2Data = null;

/**
 * 报告类型 → 可用对比模型列表（不含基准模型）
 * key: 报告类型 value，如 "0", "1", ...
 * value: [{ value: modelKey, label: modelKey }, ...]
 */
const reportTypeModelOptions = ref({});


// ========== 判断模型是否在 ruler2 的指定 scene 下有数据 ==========

/**
 * 判断 ruler2Data 中某个模型是否包含指定 scene 的数据
 * @param {object} data — ruler2Data 或 mmlRuler2Data
 * @param {string} modelKey — 模型标识
 * @param {string} scene — dataset_name，如 "operations", "aisf_llm_gaixie"
 */
const modelHasRuler2Scene = (data, modelKey, scene) => {
    const entry = data[modelKey];
    if (!entry || !Array.isArray(entry.result)) return false;
    return entry.result.some(
        (r) => r.dataset_name === scene && r.metrics?.length > 0
    )
}
/**
 * 判断 ruler1Data 中某个模型是否包含指定 scenes 中的至少一个测试集数据
 */
const modelHasRuler1Scenes = (data, modelKey, scenes) => {
    const entry = data[modelKey];
    if (!entry) return false;
    if (entry.result && Array.isArray(entry.result)) {
        return entry.result.some(
            (r) => scenes.includes(r.dataset_name) && r.metrics?.length > 0
        );
    }
    return true;
};

/**
 * 判断 ruler2Data 中某个模型是否包含指定 scenes 中的至少一个测试集数据（且有分数）
 */
const modelHasRuler2Scenes = (data, modelKey, scenes) => {
    const entry = data[modelKey];
    if (!entry || !Array.isArray(entry.result)) return false;
    return entry.result.some(
        (r) => scenes.includes(r.dataset_name) && r.metrics?.length > 0
    );
};

// ========== 加载数据并构建 reportTypeModelOptions / baseModelExistsMap ==========

const loadResultData = async () => {
    const llmData = (await getCurrentFullRes()).data;
    ruler1Data = llmData.ruler1;
    ruler2Data = llmData.ruler2;
    const multiData = (await getMultiModelData()).data;
    mmlRuler1Data = multiData.ruler1;
    mmlRuler2Data = multiData.ruler2;

    // 计算各报告类型的可用模型选项（全部模型，不做过滤）
    const options = {};

    for (const rt of Object.keys(REPORT_TYPE_SCENE_MAP)) {
        const cfg = REPORT_TYPE_SCENE_MAP[rt];
        let sourceData = null;

        if (cfg.source === "llm") {
            sourceData = cfg.type === "ruler1" ? ruler1Data : ruler2Data;
        } else {
            sourceData = cfg.type === "ruler1" ? mmlRuler1Data : mmlRuler2Data;
        }

        if (!sourceData) {
            options[rt] = [];
            continue;
        }

        const modelKeys = Object.keys(sourceData);
        const filtered = modelKeys
            .filter((key) => {
                if (cfg.scene === null) {
                    return true;
                }
                if (cfg.scenes) {
                    // ruler2 类型用 modelHasRuler2Scenes（检查 metrics 是否有值）
                    if (cfg.type === "ruler2") {
                        return modelHasRuler2Scenes(sourceData, key, cfg.scenes);
                    }
                    return modelHasRuler1Scenes(sourceData, key, cfg.scenes);
                }
                return modelHasRuler2Scene(sourceData, key, cfg.scene);
            })
            .map((key) => ({ value: key, label: key }));

        options[rt] = filtered;
    }

    reportTypeModelOptions.value = options;

    // 构建每个模型在每个报告类型下是否有数据的映射
    const existsMap = {};
    const allModelKeys = new Set();
    Object.values(options).forEach((arr) =>
        arr.forEach((item) => allModelKeys.add(item.value))
    );
    allModelKeys.forEach((modelKey) => {
        existsMap[modelKey] = {};
        for (const rt of Object.keys(REPORT_TYPE_SCENE_MAP)) {
            const cfg = REPORT_TYPE_SCENE_MAP[rt];
            let sourceData = null;
            if (cfg.source === "llm") {
                sourceData = cfg.type === "ruler1" ? ruler1Data : ruler2Data;
            } else {
                sourceData = cfg.type === "ruler1" ? mmlRuler1Data : mmlRuler2Data;
            }
            if (!sourceData) {
                existsMap[modelKey][rt] = false;
                continue;
            }
            if (!(modelKey in sourceData)) {
                existsMap[modelKey][rt] = false;
                continue;
            }
            if (cfg.scene === null) {
                existsMap[modelKey][rt] = true;
                continue;
            }
            if (cfg.scenes) {
                // ruler2 类型用 modelHasRuler2Scenes
                if (cfg.type === "ruler2") {
                    existsMap[modelKey][rt] = modelHasRuler2Scenes(
                        sourceData,
                        modelKey,
                        cfg.scenes
                    );
                } else {
                    existsMap[modelKey][rt] = modelHasRuler1Scenes(
                        sourceData,
                        modelKey,
                        cfg.scenes
                    );
                }
                continue;
            }
            existsMap[modelKey][rt] = modelHasRuler2Scene(
                sourceData,
                modelKey,
                cfg.scene
            );
        }
    });
    baseModelExistsMap.value = existsMap;
};

/**
 * 从后端获取本模型的全部发布报告，填充表格
 */
const loadTasksData = async () => {
    try {
        const resp = await getAllPublishedTasks();
        tempTasksData.value = resp.data; // 后端返回已按 create_time 倒序排列的列表
    } catch (err) {
        console.warn("获取报告任务列表失败:", err);
    }
};

/**
 * 下载表格中某行对应的报告
 */
const downloadTaskReport = (row) => {
    if (!row.published_filepath) {
        ElMessage({ type: "warning", message: "该任务无报告文件可下载" });
        return;
    }
    downloadEvalReport({ filepath: row.published_filepath })
        .then((response) => {
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const a = document.createElement("a");
            a.href = url;
            a.download = row.published_filepath.split("/").pop().split("\\").pop();
            a.click();
            window.URL.revokeObjectURL(url);
            ElMessage({ type: "success", message: "下载成功" });
        })
        .catch((err) => {
            ElMessage({
                type: "error",
                message: "下载失败: " + (err.response?.data?.error || err.message),
            });
        });
};

const previewReport = (row) => {
    if (!row.id) {
        ElMessage({ type: "warning", message: "该任务无报告ID" });
        return;
    }
    const url = router.resolve({ name: 'ReportPreview', query: { id: row.id } });
    window.open(url.href, '_self');
};

/**
 * 删除表格中某行对应的报告任务（弹出确认框）
 */
const handleDeleteTask = (row) => {
    ElMessageBox.confirm(
        `确定删除id为 "${row.id}" 的已发布报告吗？此操作不可恢复。`,
        "删除确认",
        { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" }
    )
        .then(async () => {
            try {
                await deletePublishedTask(row.id);
                ElMessage({ type: "success", message: "删除成功" });
                await loadTasksData();
            } catch (err) {
                ElMessage({
                    type: "error",
                    message: "删除失败: " + (err.response?.data?.error || err.message),
                });
            }
        })
        .catch(() => {
            // 用户取消，不做处理
        });
};

const tableHeaderStyle = {
    backgroundColor: "#f5f6fd",
    color: "#000000",
};

// ========== 发布报告弹窗相关 ==========

const baseModelInput = ref('')
const reportName = ref("")
const upload = ref<UploadInstance>();
const uploadDialogVisible = ref(false);
const selectedFile = ref(null)

// 报告类型定义
const REPORT_TYPE_DEFS = [
    { label: "大语言", value: "0" },
    { label: "视觉", value: "1" },
    { label: "音频", value: "2" },
    { label: "AISF-改写", value: "3" },
    { label: "AISF-伴学", value: "6" },
    { label: "AISF-操控规划", value: "7" },
    { label: "AISF-操控执行", value: "8" },
    { label: "AISF-意图", value: "9" },
    { label: "AISF-记忆", value: "10" },
];

const REPORT_TYPE_SCENE_MAP = {
    0: { source: "llm", type: "ruler1", scene: null },
    1: { source: "mml", type: "ruler1", scenes: ["MMMU", "MMStar", "Video-MME"] },
    2: { source: "mml", type: "ruler1", scenes: ["librispeech_asr", "MMAU", "MMAR", "WorldSense"] },
    3: { source: "llm", type: "ruler2", scene: "aisf_llm_gaixie" },
    6: { source: "mml", type: "ruler2", scene: "aisf_banxue" },
    7: { source: "mml", type: "ruler2", scene: "aisf_gui_plan" },
    8: { source: "mml", type: "ruler2", scene: "aisf_gui_vla" },
    9: { source: "llm", type: "ruler2", scene: "aisf_llm_yitu" },
    10: { source: "llm", type: "ruler2", scenes: ["aisf_memory_cuiqu", "aisf_memory_zhaohui"] },
};

const REPORT_TYPE_BIZ_NAME = {
    "0": "大语言通用",
    "1": "视觉通用",
    "2": "音频通用",
    "3": "AISF改写",
    "6": "AISF伴学",
    "7": "AISF操控规划",
    "8": "AISF操控执行",
    "9": "AISF意图",
    "10": "AISF记忆",
};

/** 尺子分组标签 */
const RULER_LABELS = {
    ruler1: "尺子一",
    ruler2: "尺子二",
};

/**
 * 获取某个基准模型的分组报告类型选项（按尺子分组）
 */
const getGroupedReportTypeOptions = (bm) => {
    const groups = { ruler1: [], ruler2: [] };
    const opts = getReportTypeOptionsForBaseModel(bm);
    for (const opt of opts) {
        const ruler = getRuler(opt.value) || "ruler1";
        groups[ruler].push(opt);
    }
    return [
        { label: RULER_LABELS.ruler1, options: groups.ruler1 },
        { label: RULER_LABELS.ruler2, options: groups.ruler2 },
    ];
};


const getRuler = (rt) => {
    const cfg = REPORT_TYPE_SCENE_MAP[rt];
    if (!cfg) return null;
    return cfg.type === "ruler1" ? "ruler1" : "ruler2";
};

const isRuler1Type = (rt) => getRuler(rt) === "ruler1";

// 将 baseModelInput 按 & 拆分为数组，最多3个
const parsedBaseModels = computed(() => {
    const raw = baseModelInput.value || '';
    const parts = raw.split('&').map(s => s.trim()).filter(s => s.length > 0);
    return parts.slice(0, 3);
});

/** 每个基准模型选择的报告类型 */
const baseModelReportTypes = ref({});
/** 每个基准模型+报告类型选择的对比模型 */
const baseModelCompareModels = ref({});

const getBaseModelReportTypes = (bm) => baseModelReportTypes.value[bm] ?? [];
const setBaseModelReportTypes = (bm, val) => {
    baseModelReportTypes.value[bm] = val;
};
const getBaseModelCompareModels = (bm, rt) =>
    baseModelCompareModels.value[`${bm}_${rt}`] ?? [];
const setBaseModelCompareModels = (bm, rt, val) => {
    baseModelCompareModels.value[`${bm}_${rt}`] = val;
};

const getReportTypeLabel = (value) => {
    const opt = REPORT_TYPE_DEFS.find((o) => o.value === value);
    return opt ? opt.label : value;
};

const getReportTypeOptionsForBaseModel = (bm) => {
    return REPORT_TYPE_DEFS.map((def) => ({
        ...def,
        baseModelExists: baseModelExistsMap.value[bm]?.[def.value] ?? false,
    }));
};

const getModelsForReportType = (reportType) => {
    return reportTypeModelOptions.value[reportType] ?? [];
};

const getCompareModelOptions = (bm, rt) => {
    const all = getModelsForReportType(rt);
    return all.filter((item) => item.value !== bm);
};

// 基准模型输入变化时清理已移除模型的数据
const onBaseModelInputChange = () => {
    const current = parsedBaseModels.value;
    Object.keys(baseModelReportTypes.value).forEach((bm) => {
        if (!current.includes(bm)) {
            delete baseModelReportTypes.value[bm];
            Object.keys(baseModelCompareModels.value).forEach((key) => {
                if (key.startsWith(bm + "_")) {
                    delete baseModelCompareModels.value[key];
                }
            });
        }
    });
};

/**
 * 为单个基准模型生成报告名称片段（与 ReportGenerationPanel.vue 一致）
 */
const generateSingleModelReportName = (modelName, types) => {
    if (!types || types.length === 0)
        return { name: modelName, hasUserInput: false };

    const bizNames = types.map((rt) => REPORT_TYPE_BIZ_NAME[rt] || `类型${rt}`);

    const hasRuler1 = types.some((rt) => isRuler1Type(rt));
    const hasRuler2 = types.some((rt) => !isRuler1Type(rt));
    const crossRuler = hasRuler1 && hasRuler2;

    const ALL_R1_TYPES = REPORT_TYPE_DEFS.filter((d) =>
        isRuler1Type(d.value)
    ).map((d) => d.value);
    const ALL_R2_TYPES = REPORT_TYPE_DEFS.filter(
        (d) => !isRuler1Type(d.value)
    ).map((d) => d.value);

    const selectedR1 = types.filter((rt) => isRuler1Type(rt));
    const selectedR2 = types.filter((rt) => !isRuler1Type(rt));

    const r1Full =
        ALL_R1_TYPES.length > 0 && selectedR1.length === ALL_R1_TYPES.length;
    const r2Full =
        ALL_R2_TYPES.length > 0 && selectedR2.length === ALL_R2_TYPES.length;

    if (!crossRuler) {
        const isR1 = hasRuler1;
        if ((isR1 && r1Full) || (!isR1 && r2Full)) {
            const rulerName = isR1 ? "通用尺子一" : "通用尺子二";
            return { name: `${modelName}${rulerName}评估报告`, hasUserInput: false };
        }
        const bizCount = isR1 ? selectedR1.length : selectedR2.length;
        if (bizCount <= 2) {
            const names = isR1
                ? selectedR1.map((rt) => REPORT_TYPE_BIZ_NAME[rt])
                : selectedR2.map((rt) => REPORT_TYPE_BIZ_NAME[rt]);
            return {
                name: `${modelName}${names.join("与")}评估报告`,
                hasUserInput: false,
            };
        }
        const names = isR1
            ? selectedR1.map((rt) => REPORT_TYPE_BIZ_NAME[rt])
            : selectedR2.map((rt) => REPORT_TYPE_BIZ_NAME[rt]);
        return {
            name: `${modelName}（${names.join("+")}）评估报告`,
            hasUserInput: false,
        };
    }

    if (r1Full && r2Full) {
        return { name: `${modelName}全量评估报告`, hasUserInput: false };
    }

    const allBizNames = types.map((rt) => REPORT_TYPE_BIZ_NAME[rt]);
    if (types.length <= 2) {
        return {
            name: `${modelName}${allBizNames.join("与")}评估报告`,
            hasUserInput: false,
        };
    }
    return {
        name: `${modelName}（${allBizNames.join("+")}）评估报告`,
        hasUserInput: false,
    };
};

/**
 * 自动报告名称
 */
const autoReportName = computed(() => {
    if (reportName.value && reportName.value.trim()) {
        return reportName.value.trim();
    }
    const bms = parsedBaseModels.value;
    if (bms.length === 0) return "";

    const parts = [];
    for (const bm of bms) {
        const types = baseModelReportTypes.value[bm] || [];
        if (types.length === 0) {
            parts.push(bm);
        } else {
            const { name } = generateSingleModelReportName(bm, types);
            parts.push(name);
        }
    }
    if (parts.length === 0) return "";
    if (parts.length === 1) return parts[0];
    const stripped = parts.map((p) => p.replace(/评估报告$/, ""));
    return stripped.join(" & ") + "评估报告";
});

const uploadReport = () => {
    baseModelInput.value = '';
    reportName.value = '';
    baseModelReportTypes.value = {};
    baseModelCompareModels.value = {};
    selectedFile.value = null;
    uploadDialogVisible.value = true;
    if (upload.value) {
        upload.value!.clearFiles();
    }
};

const handleExcelDialogClose = () => {
    if (upload.value) {
        upload.value!.clearFiles();
    }
    uploadDialogVisible.value = false;
};

const handlePublishConfirm = () => {
    // 校验
    if (parsedBaseModels.value.length === 0) {
        ElMessage({ type: "warning", message: "请填写基准模型名称" });
        return;
    }
    for (const bm of parsedBaseModels.value) {
        const types = baseModelReportTypes.value[bm];
        if (!types || types.length === 0) {
            ElMessage({ type: "warning", message: `请为基准模型"${bm}"选择报告类型` });
            return;
        }
        // for (const rt of types) {
        //     const cm = baseModelCompareModels.value[`${bm}_${rt}`];
        //     if (!cm || cm.length === 0) {
        //         ElMessage({ type: "warning", message: `请为基准模型"${bm}"的报告类型"${getReportTypeLabel(rt)}"选择对比模型` });
        //         return;
        //     }
        // }
    }
    if (!selectedFile.value) {
        ElMessage({ type: "warning", message: "请选择要上传的报告文件" });
        return;
    }

    const finalReportName = autoReportName.value || `发布报告_${Date.now()}`;

    // 构造参数：结构参考 genReport，但通过 FormData 附带文件
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    formData.append("userName", localStorage.getItem("username"));
    formData.append("report_name", finalReportName);
    formData.append("model_names", JSON.stringify(parsedBaseModels.value));

    const compareModels = {};
    const compareType = {};
    for (const bm of parsedBaseModels.value) {
        const types = baseModelReportTypes.value[bm];
        const bmCompareModels = {};
        for (const rt of types) {
            bmCompareModels[rt] = baseModelCompareModels.value[`${bm}_${rt}`];
        }
        compareModels[bm] = bmCompareModels;
        compareType[bm] = [...types].sort().join(",");
    }
    formData.append("compare_models", JSON.stringify(compareModels));
    formData.append("compare_type", JSON.stringify(compareType));

    ElMessage({ type: "info", message: "正在发布报告..." });

    directPublishReport(formData)
        .then((resp) => {
            ElMessage({ type: "success", message: "发布成功" });
            handleExcelDialogClose();
            loadTasksData();
        })
        .catch((err) => {
            ElMessage({ type: "error", message: "发布失败: " + (err.response?.data?.error || err.message) });
        });
};

const uploadFile = async (options) => {
    selectedFile.value = options.file;
    options.onSuccess(options.file);
};

const handleSuccess = (response) => {
    // 文件选择成功，实际提交在 handlePublishConfirm 中
};

const handleError = (err) => {
    ElMessage({ type: "error", message: "文件上传失败: " + (err.message || "未知错误") });
};

const handleExceed = () => {
    ElMessage({ type: "warning", message: "每次只能上传一个文件" });
};

// ========== 更新报告文件 ==========

const updateDialogVisible = ref(false);
const updateSelectedFile = ref(null);
const currentUpdateRow = ref(null);
const updateUpload = ref<UploadInstance>();

const handleUpdateReport = (row) => {
    currentUpdateRow.value = row;
    updateSelectedFile.value = null;
    updateDialogVisible.value = true;
    if (updateUpload.value) {
        updateUpload.value!.clearFiles();
    }
};

const handleUpdateDialogClose = () => {
    if (updateUpload.value) {
        updateUpload.value!.clearFiles();
    }
    updateDialogVisible.value = false;
    currentUpdateRow.value = null;
};

const updateUploadFile = async (options) => {
    updateSelectedFile.value = options.file;
    options.onSuccess(options.file);
};

const handleUpdateExceed = () => {
    ElMessage({ type: "warning", message: "每次只能上传一个文件" });
};

const handleUpdateConfirm = () => {
    if (!updateSelectedFile.value) {
        ElMessage({ type: "warning", message: "请选择要上传的报告文件" });
        return;
    }

    const formData = new FormData();
    formData.append("id", currentUpdateRow.value.id);
    formData.append("file", updateSelectedFile.value);
    formData.append("userName", localStorage.getItem("username"));

    ElMessage({ type: "info", message: "正在更新报告文件..." });

    updatePublishedReport(formData)
        .then((resp) => {
            ElMessage({ type: "success", message: "更新成功" });
            handleUpdateDialogClose();
            loadTasksData();
        })
        .catch((err) => {
            ElMessage({
                type: "error",
                message: "更新失败: " + (err.response?.data?.error || err.message),
            });
        });
};

let tasksPollTimer = null;

onMounted(async () => {
    loading.value = true;
    try {
        await loadResultData();
        await loadTasksData();
    } finally {
        loading.value = false;
    }
    tasksPollTimer = setInterval(loadTasksData, 15000);
});

onBeforeUnmount(() => {
    if (tasksPollTimer) {
        clearInterval(tasksPollTimer);
    }
});
</script>

<style scoped>
.customButton {
    font-size: 14px;
    float: right;
    margin-right: 10px;
}

.customButton :deep(.circular) {
    margin-top: 10px;
    width: 25px;
    height: 25px;
}

.report-type-section {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
}

.report-buttons {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.report-header-buttons {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin: 0 10px;
    padding: 10px;
    background-color: #fff;
    /* border-bottom: 1px solid rgb(230, 230, 230); */
}

.el-table__expand-icon>.el-icon {
    font-size: 20px;
}

/* 基准模型没有数据的报告类型：下拉选项文字灰色 */
:deep(.report-type-option-dimmed) {
    color: #c0c4cc !important;
}

.report-type-label-dialog {
    font-size: 13px;
    white-space: nowrap;
    color: #606266;
    min-width: 56px;
}

.titleContainer {
    background-color: #fff;
    line-height: 50px;
    height: 50px;
}

.container {
    /* gap: 0; */
    /* margin: 0; */
    max-width: 100%;
}
</style>