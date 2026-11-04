<template>
    <div class="rankDetailContainer">
        <div class="rankDetailTitleContainer">
            <span style="padding: 0 8px;"></span>
            <img src="/images/return.png" class="returnicon" @click="goBack" />
            <span style="padding: 0 20px;"></span>
            <span @click="goBack" style="color: #969696;cursor: pointer;">模型榜单</span>
            <span style="padding: 0 8px;font-weight:600;font-size:18px;">/</span>
            <span style="font-weight:600;font-size:18px;">{{ displayTitle }}</span>
        </div>
        <div class="cardContainer">
            <div class="tableContainer">
                <el-table :data="sortedTableData" :header-cell-style="tableHeaderStyle" class="scoreTable" border stripe>
                    <el-table-column label="时间" prop="time" min-width="80" sortable />
                    <el-table-column label="模型名" prop="model_name" min-width="100" sortable />
                    <el-table-column label="分数" prop="elo" min-width="80" sortable />
                    <el-table-column label="系列名" prop="organization" min-width="100" sortable />
                    <el-table-column label="开源/闭源" prop="openSource" min-width="80" sortable>
                        <template #default="scope">
                            {{ scope.row.openSource === 'open' ? '开源' : '闭源' }}
                        </template>
                    </el-table-column>
                    <el-table-column label="排名" prop="rank" min-width="80" sortable />
                    <el-table-column label="有效投票数" prop="votes" min-width="100" sortable />
                </el-table>
            </div>
        </div>
    </div>
</template>

<script lang="ts" setup>
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { API_BASE_URL } from "@/utils/Constants.js";
import axios from "axios";

const tableData = ref([]);
const tableHeaderStyle = {
    backgroundColor: "#f5f6fd",
    color: "#000000",
};

const route = useRoute();
const router = useRouter();
const goBack = () => {
    router.back();
};

const displayTitle = ref("模型竞技场（LMArena）榜单详情");

// 排序：闭源高分 -> 闭源低分 -> 开源高分 -> 开源低分
const sortedTableData = computed(() => {
    return [...tableData.value].sort((a, b) => {
        // 闭源（closed）排前面，开源（open）排后面
        if (a.openSource !== b.openSource) {
            return a.openSource === 'closed' ? -1 : 1;
        }
        // 相同类型按分数从高到低
        return (b.elo || 0) - (a.elo || 0);
    });
});

const loadArenaData = async () => {
    try {
        const response = await axios.get(`${API_BASE_URL}lmarena/leaderboard`);
        const data = response.data;

        const transformedData = data.map((row) => {
            const openSource = row["closed/open"] === "open" ? "open" : "closed";
            return {
                time: row.time,
                model_name: row.model_name || row.model || "",
                elo: row.elo || 0,
                organization: row.organization || "-",
                openSource: openSource,
                rank: row.rank || "-",
                votes: row.votes || "-",
            };
        });

        tableData.value = transformedData;
    } catch (error) {
        console.error("获取LM Arena排行榜数据失败:", error);
    }
};

onMounted(async () => {
    await loadArenaData();
});
</script>

<style scoped>
/* 保持原有的样式不变 */
.rankDetailTitleContainer {
    position: relative;
    align-items: center;
    color: rgba(18, 19, 22, 0.8);
    background-color: #fff;
    line-height: 50px;
    height: 50px;
    margin-bottom: 18px;
}

.rankDetailContainer {
    height: calc(100% - 80px);
}

.tableContainer {
    height: 100%;
    overflow-x: auto;
    overflow-y: auto;
    margin: 0 auto;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    white-space: nowrap;
}

.scoreTable {
    font-size: medium;
    min-width: max-content;
    width: auto;
    table-layout: auto;
    white-space: nowrap;
}

.cardContainer {
    height: 100%;
}
</style>