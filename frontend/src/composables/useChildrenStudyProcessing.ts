import {
    attentionEnum,
    sittingPostureEnum,
    distanceEnum,
    seatStatusEnum,
    dimensionKeys,
    dimensionNames,
    statusDimensionNameMap,
} from "@/components/statistics/childrenStudyConstants";

// ====================================================================
// Pure data processing functions extracted from childrenStudyStastics.vue
// ====================================================================

export function processAccuracyData(data) {
    if (!data || data.length === 0) {
        return [
            { metric: "总正确率", value: "-" },
            { metric: "总数量", value: data.length },
            { metric: "全部正确数量", value: "-" },
            { metric: "平均completion_tokens", value: "-" },
            { metric: "平均prompt_tokens", value: "-" },
            { metric: "平均total_tokens", value: "-" },
            { metric: "平均cost_time", value: "-" },
        ];
    }
    const positiveCount = data.filter((item) => item.result === 1).length;
    const positiveProbability = ((positiveCount / data.length) * 100).toFixed(2) + "%";
    const totalCost_time = data.reduce((sum, item) => sum + item.response_time, 0);
    const averageCost_time = (totalCost_time / data.length).toFixed(4);
    const totalCompletionTokens = data.reduce((sum, item) => sum + item.completion_tokens, 0);
    const averageCompletionTokens = (totalCompletionTokens / data.length).toFixed(2);
    const totalPromptTokens = data.reduce((sum, item) => sum + item.prompt_tokens, 0);
    const averagePromptTokens = (totalPromptTokens / data.length).toFixed(2);
    const totalTotalTokens = data.reduce((sum, item) => sum + item.total_tokens, 0);
    const averageTotalTokens = (totalTotalTokens / data.length).toFixed(2);
    return [
        { metric: "总正确率", value: positiveProbability },
        { metric: "总数量", value: data.length },
        { metric: "全部正确数量", value: positiveCount },
        { metric: "平均completion_tokens", value: averageCompletionTokens },
        { metric: "平均prompt_tokens", value: averagePromptTokens },
        { metric: "平均total_tokens", value: averageTotalTokens },
        { metric: "平均cost_time", value: averageCost_time + "s" },
    ];
}

export function processStatusTableData(data) {
    if (!data || data.length === 0) return [];
    const dimKeys = ["attention_status", "attention_category", "sitting_posture_status", "sitting_posture_category",
        // "distance_status", "seat_status"
    ];
    const matchCountMap = {}; const validSamplesMap = {};
    dimKeys.forEach((key) => { matchCountMap[key] = 0; validSamplesMap[key] = 0; });
    data.forEach((item) => {
        dimKeys.forEach((key) => {
            if (item.gold?.hasOwnProperty(key) && item.pred?.hasOwnProperty(key)) {
                validSamplesMap[key] += 1;
                if (item.gold[key].split(/[，,]/).some((tag) => tag.trim() === item.pred[key])) matchCountMap[key] += 1;
            }
        });
    });
    return dimKeys.map((key) => {
        const validCount = validSamplesMap[key]; const matchCount = matchCountMap[key];
        if (validCount === 0) return { dimension: statusDimensionNameMap[key] || key, totalSamples: "-", count: "-", accuracy: "-" };
        return { dimension: statusDimensionNameMap[key] || key, totalSamples: validCount, count: matchCount, accuracy: ((matchCount / validCount) * 100).toFixed(2) + "%" };
    });
}

export function processCostTimeTableData(data) {
    const intervals = [];
    for (let i = 0; i < 10; i++) intervals.push({ min: i, max: i + 1, label: `${i}s~${i + 1}s` });
    intervals.push({ min: 10, max: Infinity, label: "10s以上" });
    const counts = new Array(intervals.length).fill(0); const total = data.length;
    data.forEach((item) => { const rt = item.response_time; if (rt < 0) return; if (rt >= 10) counts[10]++; else counts[Math.floor(rt)]++; });
    return intervals.map((interval, index) => ({ interval: interval.label, count: counts[index], percentage: total > 0 ? ((counts[index] / total) * 100).toFixed(2) + "%" : "0.00%" }));
}

export function processSourceTableData(data) {
    const sourceMap = {};
    data.forEach((item) => { const s = item.source; if (!sourceMap[s]) sourceMap[s] = []; sourceMap[s].push(item); });
    const results = [];
    Object.keys(sourceMap).forEach((source) => {
        const items = sourceMap[source];
        const total = items.length;
        const correct = items.filter((item) => Object.keys(item.gold).filter((k) => dimensionKeys.hasOwnProperty(k)).every((k) => item.gold[k].split(/[，,]/).some((tag) => tag.trim() === item.pred[k]))).length;
        results.push({ 图片来源: source, 总正确率_总数量: total, 总正确率_正确数量: correct, 总正确率_正确率: total > 0 ? ((correct / total) * 100).toFixed(2) + "%" : "0.00%" });
    });
    return results;
}

export function processResolutionTableData(data) {
    const group = {};
    data.forEach((item) => { const res = item.resolution; if (!group[res]) group[res] = { total: 0, correct: 0 }; group[res].total++; if (item.result) group[res].correct++; });
    const tableData = Object.keys(group).map((resolution) => { const { total, correct } = group[resolution]; return { resolution, total, correct, accuracy: total > 0 ? ((correct / total) * 100).toFixed(2) + "%" : "0.00%" }; });
    tableData.sort((a, b) => a.resolution.localeCompare(b.resolution)); return tableData;
}

export function processCategoryData(data) {
    const scenePrefixes = ["attention", "sitting_posture", "distance"];
    const stats = {};
    scenePrefixes.forEach((prefix) => { stats[prefix] = { total: 0, bothSuccess: 0, mainSuccessSubFail: 0, mainFailSubSuccess: 0 }; });
    data.forEach((item) => {
        const { gold, pred } = item;
        scenePrefixes.forEach((prefix) => {
            const mainKey = `${prefix}_status`; const subKey = `${prefix}_category`;
            if (gold[mainKey] !== undefined && gold[subKey] !== undefined) {
                stats[prefix].total++;
                const mainMatch = gold[mainKey].trim().split(/[，,]/).some((tag) => tag.trim() === pred[mainKey]);
                const subMatch = gold[subKey].trim().split(/[，,]/).some((tag) => tag.trim() === pred[subKey]);
                if (mainMatch && subMatch) stats[prefix].bothSuccess++;
                else if (mainMatch && !subMatch) stats[prefix].mainSuccessSubFail++;
                else if (!mainMatch && subMatch) stats[prefix].mainFailSubSuccess++;
            }
        });
    });
    const result = {};
    scenePrefixes.forEach((prefix) => {
        const sceneData = stats[prefix]; const sceneName = dimensionKeys[`${prefix}_status`].replace("大类", "检测场景");
        result[prefix] = [{ scene: sceneName, type: "大小类都成功", total: sceneData.total, count: sceneData.bothSuccess, ratio: sceneData.total ? ((sceneData.bothSuccess / sceneData.total) * 100).toFixed(2) + "%" : "0.00%" }, { scene: sceneName, type: "大类成功小类失败", total: sceneData.total, count: sceneData.mainSuccessSubFail, ratio: sceneData.total ? ((sceneData.mainSuccessSubFail / sceneData.total) * 100).toFixed(2) + "%" : "0.00%" }, { scene: sceneName, type: "大类失败小类成功", total: sceneData.total, count: sceneData.mainFailSubSuccess, ratio: sceneData.total ? ((sceneData.mainFailSubSuccess / sceneData.total) * 100).toFixed(2) + "%" : "0.00%" }];
    });
    return result;
}

export function processCorrectRateTableData(data) {
    const dimensionsConfig = {
        attention_category: { name: "注意力小类", categories: attentionEnum, comboLabel: "组合类" },
        sitting_posture_category: { name: "坐姿小类", categories: sittingPostureEnum, comboLabel: "组合类" },
    };
    const result = {};
    Object.keys(dimensionsConfig).forEach((dimensionKey) => {
        const config = dimensionsConfig[dimensionKey];
        const stats = [...config.categories, config.comboLabel].reduce((acc, category) => { acc[category] = { total: 0, correct: 0 }; return acc; }, {});
        data.forEach((item) => {
            const normalKey = config.categories[0];
            let goldValue = item.gold[dimensionKey]?.replaceAll(",", "，").trim();
            if (!goldValue) return;
            const isCombo = config.comboLabel !== "组合类" ? goldValue.includes("，") && !goldValue.split("，").some((i) => i.trim() === normalKey) : goldValue.includes("，");
            let category = isCombo ? config.comboLabel : goldValue;
            if (!stats[category]) { if (goldValue.split("，").some((i) => i.trim() === normalKey)) category = normalKey; else return; }
            stats[category].total += 1;
            const predValue = item.pred[dimensionKey];
            const isCorrect = goldValue.includes("，") ? predValue != null && goldValue.split("，").some((i) => i.trim() === predValue) : predValue === goldValue;
            if (isCorrect) stats[category].correct += 1;
        });
        let totalTotal = 0, totalCorrect = 0;
        const tableData = [];
        config.categories.forEach((category) => {
            const s = stats[category]; totalTotal += s.total; totalCorrect += s.correct;
            tableData.push({ category, description: `预期为${category}（且模型返回正确）`, total: s.total, correct: s.correct, correctRate: s.total > 0 ? ((s.correct / s.total) * 100).toFixed(2) + "%" : "0.00%" });
        });
        const cs = stats[config.comboLabel]; totalTotal += cs.total; totalCorrect += cs.correct;
        tableData.push({ category: config.comboLabel, description: `预期为${config.comboLabel}（且模型返回正确）`, total: cs.total, correct: cs.correct, correctRate: cs.total > 0 ? ((cs.correct / cs.total) * 100).toFixed(2) + "%" : "0.00%" });
        tableData.push({ category: "合计", description: "", total: totalTotal, correct: totalCorrect, correctRate: totalTotal > 0 ? ((totalCorrect / totalTotal) * 100).toFixed(2) + "%" : "0.00%" });
        result[dimensionKey] = tableData;
    });
    return result;
}

export function processFalseAlarmTableData(data) {
    const dimensionsConfig = {
        attention_category: { name: "注意力小类", categories: attentionEnum, comboLabel: "异常组合类" },
        sitting_posture_category: { name: "坐姿小类", categories: sittingPostureEnum, comboLabel: "异常组合类" },
    };
    const result = {};
    Object.keys(dimensionsConfig).forEach((dimensionKey) => {
        const config = dimensionsConfig[dimensionKey];
        const stats = [...config.categories, config.comboLabel].reduce((acc, category) => { acc[category] = { total: 0, error: 0 }; return acc; }, {});
        data.forEach((item) => {
            const normalKey = config.categories[0];
            const goldValue = item.gold[dimensionKey]?.replaceAll(",", "，").trim();
            if (!goldValue) return;
            const isCombo = config.comboLabel !== "组合类" ? goldValue.includes("，") && !goldValue.split("，").some((i) => i.trim() === normalKey) : goldValue.includes("，");
            let category = isCombo ? config.comboLabel : goldValue;
            if (!stats[category]) {
                if (category.split(/[，,]/).some((i) => i.trim() === normalKey)) {
                    category = normalKey; stats[category].total += 1;
                    const predValue = item.pred[dimensionKey];
                    if (predValue == null || !goldValue.split("，").some((i) => i.trim() === predValue)) stats[category].error += 1;
                }
                return;
            }
            stats[category].total += 1;
            const predValue = item.pred[dimensionKey];
            if (predValue == null || !goldValue.split("，").some((i) => i.trim() === predValue)) stats[category].error += 1;
        });
        let totalTotal = 0, totalError = 0;
        const tableData = [];
        config.categories.forEach((category, index) => {
            const s = stats[category]; totalTotal += s.total; totalError += s.error;
            tableData.push({ category, description: index === 0 && dimensionKey !== "seat_status" ? `预期里包含${category}（但模型返回错误）` : `预期为${category}（但模型返回错误）`, total: s.total, error: s.error, errorRate: s.total > 0 ? ((s.error / s.total) * 100).toFixed(2) + "%" : "0.00%" });
        });
        const cs = stats[config.comboLabel]; totalTotal += cs.total; totalError += cs.error;
        tableData.push({ category: config.comboLabel, description: `预期为${config.comboLabel}（但模型返回错误）`, total: cs.total, error: cs.error, errorRate: cs.total > 0 ? ((cs.error / cs.total) * 100).toFixed(2) + "%" : "0.00%" });
        tableData.push({ category: "合计", description: "", total: totalTotal, error: totalError, errorRate: totalTotal > 0 ? ((totalError / totalTotal) * 100).toFixed(2) + "%" : "0.00%" });
        result[dimensionKey] = tableData;
    });
    return result;
}

export function processMissedRateTableData(data) {
    const compositeCategoryMap = {
        attention_category: "异常组合类", sitting_posture_category: "异常组合类",
        // distance_status: "异常组合类", seat_status: "组合类"
    };
    const dimensionConfigs = [
        { key: "attention_category", normalValue: "集中", suffix: "（但模型返回为集中）" },
        { key: "sitting_posture_category", normalValue: "正常", suffix: "（但模型返回正常）" },
    ];
    const categoryOrders = { attention_category: [...attentionEnum.filter((x) => x !== "集中"), "异常组合类"], sitting_posture_category: [...sittingPostureEnum.filter((x) => x !== "正常"), , "异常组合类"] };
    const result = {};
    dimensionConfigs.forEach(({ key, normalValue, suffix }) => {
        const order = categoryOrders[key];
        const compositeCategory = compositeCategoryMap[key];
        const stat = { totalCount: 0, missCount: 0, categories: {} };
        order.forEach((cat) => { stat.categories[cat] = { total: 0, miss: 0 }; });
        data.forEach((item) => {
            const goldValue = item.gold[key]?.replaceAll(",", "，").trim();
            const predValue = item.pred[key];
            if (!goldValue || goldValue === normalValue) return;
            let actualCategory;
            if (goldValue.includes("，") && goldValue.split("，").every((i) => categoryOrders[key].includes(i))) actualCategory = compositeCategory;
            else { if (!order.includes(goldValue)) return; actualCategory = goldValue; }
            if (!stat.categories[actualCategory]) return;
            stat.categories[actualCategory].total += 1; stat.totalCount += 1;
            if (predValue === normalValue) { stat.categories[actualCategory].miss += 1; stat.missCount += 1; }
        });
        const tableData = order.map((category) => {
            const cs = stat.categories[category];
            return { dimension: category, description: `预期为${category}${suffix}`, total: cs.total, miss: cs.miss, missRate: cs.total > 0 ? (cs.miss / cs.total * 100).toFixed(2) + "%" : "0.00%" };
        });
        tableData.push({ dimension: "合计", description: "", total: stat.totalCount, miss: stat.missCount, missRate: stat.totalCount > 0 ? (stat.missCount / stat.totalCount * 100).toFixed(2) + "%" : "0.00%" });
        result[key] = tableData;
    });
    return result;
}

export function processDifficultyTableData(data) {
    const createStats = () => ({ 简单: { total: 0, correct: 0 }, 中等: { total: 0, correct: 0 }, 困难: { total: 0, correct: 0 } });
    const attentionStats = createStats();
    const seatStatusStats = createStats();
    // const distanceStats = createStats();
    // const sittingPostureStats = createStats();

    const hasAttentionDiff = data.some((item) => "attention_difficulty" in item);
    const hasSeatStatusDiff = data.some((item) => "seat_status_difficulty" in item);
    // const hasDistanceDiff = data.some((item) => "distance_difficulty" in item);
    // const hasSittingPostureDiff = data.some((item) => "sitting_posture_difficulty" in item);

    data.forEach((item) => {
        if (hasAttentionDiff && item.attention_difficulty) {
            const d = item.attention_difficulty; attentionStats[d].total++;
            if (item.gold.attention_category.split(/[，,]/).map((s) => s.trim()).includes(item.pred.attention_category.trim()) && item.gold.attention_status.split(/[，,]/).map((s) => s.trim()).includes(item.pred.attention_status.trim())) attentionStats[d].correct++;
        }
        if (hasSeatStatusDiff && item.seat_status_difficulty) {
            const d = item.seat_status_difficulty; seatStatusStats[d].total++;
            if (item.gold.seat_status.split(/[，,]/).map((s) => s.trim()).includes(item.pred.seat_status.trim())) seatStatusStats[d].correct++;
        }
        // if (hasDistanceDiff && item.distance_difficulty) {
        //     const d = item.distance_difficulty; distanceStats[d].total++;
        //     if (item.gold.distance_status && item.gold.distance_status.split(/[，,]/).map((s) => s.trim()).includes(item.pred.distance_status.trim())) distanceStats[d].correct++;
        // }
        // if (hasSittingPostureDiff && item.sitting_posture_difficulty) {
        //     const d = item.sitting_posture_difficulty; sittingPostureStats[d].total++;
        //     if (item.gold.sitting_posture_category.split(/[，,]/).map((s) => s.trim()).includes(item.pred.sitting_posture_category.trim()) && item.gold.sitting_posture_status.split(/[，,]/).map((s) => s.trim()).includes(item.pred.sitting_posture_status.trim())) sittingPostureStats[d].correct++;
        // }
    });

    const generateTableData = (stats, hasData) =>
        ["简单", "中等", "困难"].map((level) => {
            if (!hasData) return { level, total: "-", correct: "-", accuracy: "-" };
            const { total, correct } = stats[level];
            return { level, total, correct, accuracy: total > 0 ? (correct / total * 100).toFixed(2) + "%" : "0.00%" };
        });

    return {
        attention: generateTableData(attentionStats, hasAttentionDiff), seatStatus: generateTableData(seatStatusStats, hasSeatStatusDiff),
        //  distance: generateTableData(distanceStats, hasDistanceDiff), sittingPosture: generateTableData(sittingPostureStats, hasSittingPostureDiff)
    };
}

export function processPrecisionAndFDRTableData(data) {
    const dimensionsConfig = { attention_category: { categories: attentionEnum }, sitting_posture_category: { categories: sittingPostureEnum } };
    const result = {};
    Object.keys(dimensionsConfig).forEach((dimensionKey) => {
        const categories = dimensionsConfig[dimensionKey].categories;
        const categoryStats = {};
        categories.forEach((cat) => { categoryStats[cat] = { TP: 0, TN: 0, FP: 0, FN: 0 }; });
        data.forEach((item) => {
            const predValue = item.pred[dimensionKey]; const goldValue = item.gold[dimensionKey]?.replaceAll("，", ",");
            if (!goldValue || !predValue) return;
            const goldArray = goldValue.split(",").map((i) => i.trim());
            categories.forEach((category) => {
                const isGP = goldArray.includes(category); const isPP = predValue === category;
                if (isGP && isPP) categoryStats[category].TP++;
                else if (!isGP && isPP) categoryStats[category].FP++;
                else if (isGP && !isPP) categoryStats[category].FN++;
                else categoryStats[category].TN++;
            });
        });
        result[dimensionKey] = categories.map((category) => {
            const { TP, TN, FP, FN } = categoryStats[category];
            const precision = TP + FP > 0 ? TP / (TP + FP) : 0;
            const recall = TP + FN > 0 ? TP / (TP + FN) : 0;
            return {
                小类名: category, TP, TN, FP, FN, 精确率: (precision * 100).toFixed(2) + "%", 召回率: (recall * 100).toFixed(2) + "%",
                漏报率: ((1 - recall) * 100).toFixed(2) + "%", 误发现率: ((1 - precision) * 100).toFixed(2) + "%"
            };
        });
    });
    return result;
}

export function processIndicatorData(data) {
    const dimensionsConfig = { attention_category: { categories: attentionEnum, normalTag: "集中" }, sitting_posture_category: { categories: sittingPostureEnum, normalTag: "正常" } };
    const result = {};
    Object.keys(dimensionsConfig).forEach((dimensionKey) => {
        const { categories, normalTag } = dimensionsConfig[dimensionKey];
        const categoryStats = {};
        categories.forEach((cat) => { categoryStats[cat] = { TP: 0, TN: 0, FP: 0, FN: 0 }; });
        data.forEach((item) => {
            const predValue = item.pred[dimensionKey]; const goldValue = item.gold[dimensionKey]?.replaceAll("，", ",");
            if (!goldValue || !predValue) return;
            const firstGoldTag = goldValue.split(",")[0].trim();
            categories.forEach((category) => {
                const isGP = firstGoldTag === category; const isPP = predValue === category;
                if (isGP && isPP) categoryStats[category].TP++;
                else if (!isGP && isPP) categoryStats[category].FP++;
                else if (isGP && !isPP) categoryStats[category].FN++;
                else categoryStats[category].TN++;
            });
        });
        result[dimensionKey] = categories.map((category) => {
            const { TP, TN, FP, FN } = categoryStats[category];
            const precision = TP + FP > 0 ? TP / (TP + FP) : 0;
            const recall = TP + FN > 0 ? TP / (TP + FN) : 0;
            return { 小类名: category, TP, TN, FP, FN, "精确率计算(TP/(TP+FP))": TP + FP === 0 ? "0" : `${TP}/${TP + FP}`, 精确率: (precision * 100).toFixed(2) + "%", "召回率计算(TP/(TP+FN))": TP + FN === 0 ? "0" : `${TP}/${TP + FN}`, 召回率: (recall * 100).toFixed(2) + "%" };
        });
    });
    return result;
}

export function processRecallAndMissRateTableData(data) {
    const dimensionsConfig = { attention_category: { categories: attentionEnum }, sitting_posture_category: { categories: sittingPostureEnum } };
    const result = { recall: {}, missRate: {} };
    Object.keys(dimensionsConfig).forEach((dimensionKey) => {
        const categories = dimensionsConfig[dimensionKey].categories;
        const categoryStats = {};
        categories.forEach((cat) => { categoryStats[cat] = { TP: 0, FN: 0 }; });
        data.forEach((item) => {
            const predValue = item.pred[dimensionKey];
            if (!predValue || !categories.includes(predValue)) return;
            const goldValue = item.gold[dimensionKey]?.replaceAll(",", "，").trim();
            if (!goldValue) return;
            goldValue.split("，").forEach((goldLabel) => {
                const trueLabel = goldLabel.trim();
                if (!categories.includes(trueLabel)) return;
                if (predValue === trueLabel) categoryStats[trueLabel].TP++; else categoryStats[trueLabel].FN++;
            });
        });
        result.recall[dimensionKey] = categories.map((category) => {
            const { TP, FN } = categoryStats[category]; const total = TP + FN;
            return { category, description: "真实为该类别的样本中被正确预测的比例", total, correct: TP, rate: total > 0 ? (TP / total * 100).toFixed(2) + "%" : "0.00%" };
        });
        result.missRate[dimensionKey] = categories.map((category) => {
            const { TP, FN } = categoryStats[category]; const total = TP + FN;
            return { category, description: "真实为该类别的样本中被漏报的比例", total, error: FN, rate: total > 0 ? (FN / total * 100).toFixed(2) + "%" : "0.00%" };
        });
    });
    return result;
}

export function processConfusionMatrixTableData(data, attentionResultEnum, postureResultEnum, distanceResultEnum, seatStatusResultEnum) {
    const dimensions = ["attention_category", "distance_status", "sitting_posture_category", "seat_status"];
    const keySets = {
        attention_category: { keys: attentionResultEnum.value, goldKeys: attentionEnum },
        distance_status: { keys: distanceResultEnum.value, goldKeys: distanceEnum },
        sitting_posture_category: { keys: postureResultEnum.value, goldKeys: sittingPostureEnum },
        seat_status: { keys: seatStatusResultEnum.value, goldKeys: seatStatusEnum }
    };
    const resultTables = [];
    dimensions.forEach((dimension) => {
        const { keys: predefinedKeys, goldKeys } = keySets[dimension];
        const goldValuesInOrder = [];
        const seen = new Set();
        data.forEach((item) => { const v = item.gold[dimension]; if (v !== undefined && !seen.has(v)) { seen.add(v); goldValuesInOrder.push(v); } });
        const predefinedValues = goldKeys.filter((k) => goldValuesInOrder.includes(k));
        const otherValues = goldValuesInOrder.filter((k) => !goldKeys.includes(k));
        const goldValues = [...predefinedValues, ...otherValues];
        const predValues = [...predefinedKeys];
        const countMatrix = Array.from({ length: goldValues.length }, () => Array(predValues.length).fill(0));
        data.forEach((item) => {
            const gv = item.gold[dimension]; const pv = item.pred?.[dimension];
            if (gv !== undefined && pv !== undefined) {
                const gi = goldValues.indexOf(gv); const pi = predValues.indexOf(pv);
                if (gi !== -1 && pi !== -1) countMatrix[gi][pi]++;
            }
        });
        const tableData = goldValues.map((goldVal, gi) => {
            const row = { goldValue: goldVal, dimensionName: dimensionNames[dimension] };
            predValues.forEach((predVal, pi) => { row[predVal.replace(/\s+/g, "_")] = countMatrix[gi][pi]; });
            return row;
        });
        resultTables.push({ dimension, dimensionName: dimensionNames[dimension], goldValues, predValues, tableData });
    });
    return { attention: resultTables[0], distance: resultTables[1], sitting: resultTables[2], searStatus: resultTables[3] };
}

export function processConfusionMatrixTableData2(data, attentionResultEnum, postureResultEnum) {
    const dimensions = ["attention_category", "sitting_posture_category"];
    const keySets = { attention_category: { keys: attentionResultEnum.value, goldKeys: attentionEnum }, sitting_posture_category: { keys: postureResultEnum.value, goldKeys: sittingPostureEnum } };
    const resultTables = [];
    dimensions.forEach((dimension) => {
        const { keys: predefinedKeys, goldKeys } = keySets[dimension];
        const predValues = [...predefinedKeys];
        const seen = new Set();
        const predefinedSet = new Set();
        const nonPredefinedLabels = [];
        data.forEach((item) => {
            const gv = item.gold[dimension]?.trim(); const pv = item.pred[dimension];
            if (gv !== undefined) {
                if (goldKeys.includes(gv) && !seen.has(gv)) { seen.add(gv); predefinedSet.add(gv); } else {
                    const parts = gv.split(/[，,]/).map((p) => p.trim());
                    if (parts.includes(pv) && !seen.has(pv)) { seen.add(pv); goldKeys.includes(pv) ? predefinedSet.add(pv) : nonPredefinedLabels.push(pv); } else if (parts[0] && !seen.has(parts[0])) { seen.add(parts[0]); goldKeys.includes(parts[0]) ? predefinedSet.add(parts[0]) : nonPredefinedLabels.push(parts[0]); }
                }
            }
        });
        const goldValues = [...goldKeys.filter((k) => predefinedSet.has(k)), ...nonPredefinedLabels];
        const countMatrix = Array.from({ length: goldValues.length }, () => Array(predValues.length).fill(0));
        data.forEach((item) => {
            const gv = item.gold[dimension]; const pv = item.pred?.[dimension];
            if (gv !== undefined && pv !== undefined && predValues.includes(pv)) {
                const goldSubValues = gv.split(/[，,]/).map((v) => v.trim());
                const actualGoldValue = goldSubValues.includes(pv) ? pv : goldSubValues[0];
                const gi = goldValues.indexOf(actualGoldValue); const pi = predValues.indexOf(pv);
                if (gi !== -1 && pi !== -1) countMatrix[gi][pi]++;
            }
        });
        const tableData = goldValues.map((goldVal, gi) => {
            const row = { goldValue: goldVal, dimensionName: dimensionNames[dimension] };
            predValues.forEach((predVal, pi) => { row[predVal.replace(/\s+/g, "_")] = countMatrix[gi][pi]; });
            return row;
        });
        resultTables.push({ dimension, dimensionName: dimensionNames[dimension], goldValues, predValues, tableData });
    });
    return { attention: resultTables[0], sitting: resultTables[1], distance: resultTables[2], searStatus: resultTables[3] };
}

export function processStatusPartTableData(attentionData, postureData) {
    const processDimension = ({ key, name, data }) => {
        if (!data || data.length === 0) return { dimension: name, totalSamples: "-", count: "-", accuracy: "-" };
        let validSamples = 0, matchCount = 0;
        data.forEach((item) => {
            if (item.gold?.hasOwnProperty(key) && item.pred?.hasOwnProperty(key)) {
                validSamples++;
                if (item.gold[key].split(/[，,]/).map((t) => t.trim()).includes(item.pred[key])) matchCount++;
            }
        });
        if (validSamples === 0) return { dimension: name, totalSamples: "-", count: "-", accuracy: "-" };
        return { dimension: name, totalSamples: validSamples, count: matchCount, accuracy: (matchCount / validSamples * 100).toFixed(2) + "%" };
    };
    return [
        { key: "attention_category", name: "注意力小类", data: attentionData },
        { key: "sitting_posture_category", name: "坐姿小类", data: postureData },
    ].map(processDimension);
}

export function extractDynamicEnums(allResults) {
    const enumMap = { attentionEnum, sittingPostureEnum, distanceEnum, seatStatusEnum };
    const enumConfigs = [
        { prop: "attention_category", enumName: "attentionEnum", result_name: "attentionResult" },
        { prop: "sitting_posture_category", enumName: "sittingPostureEnum", result_name: "postureResult" },
        // { prop: "distance_status", enumName: "distanceEnum", result_name: "distanceResult" },
        // { prop: "seat_status", enumName: "seatStatusEnum", result_name: "seatStatusResult" },
    ];
    const dynamicEnums = {};
    enumConfigs.forEach(({ prop, enumName, result_name }) => {
        const uniqueValuesSet = new Set(); const uniqueResultsSet = new Set();
        for (const taskResults of allResults) {
            if (!taskResults || !Array.isArray(taskResults)) continue;
            for (const qr of taskResults) {
                const goldVal = qr?.choices?.[0]?.review?.gold?.[prop];
                const predVal = qr?.choices?.[0]?.review?.pred?.[prop];
                if (goldVal) { String(goldVal).split(/[，,]/).forEach((e) => uniqueValuesSet.add(e.trim())); }
                if (predVal) { String(predVal).split(/[，,]/).forEach((e) => uniqueResultsSet.add(e.trim())); }
            }
        }
        const baseEnum = enumMap[enumName];
        const currentLabels = Array.from(uniqueValuesSet);
        const inBaseEnum = baseEnum.filter((l) => uniqueValuesSet.has(l));
        const extraLabels = currentLabels.filter((l) => !baseEnum.includes(l)).sort((a, b) => a.localeCompare(b, "zh"));
        dynamicEnums[enumName] = [...inBaseEnum, ...extraLabels];
        const currentLabelsResult = Array.from(uniqueResultsSet);
        const inBaseEnumResult = baseEnum.filter((l) => uniqueResultsSet.has(l));
        const extraLabelsResult = currentLabelsResult.filter((l) => !baseEnum.includes(l)).sort((a, b) => a.localeCompare(b, "zh"));
        dynamicEnums[result_name] = [...inBaseEnumResult, ...extraLabelsResult];
    });
    return dynamicEnums;
}

export function processStabilityData(data) {
    const dimensions = [
        { key: "attention_category", categories: attentionEnum, resultKey: "attention" },
        { key: "sitting_posture_category", categories: sittingPostureEnum, resultKey: "sitting" },
    ];

    const result = {};
    dimensions.forEach(({ key, categories, resultKey }) => {
        // For each category, track which question numbers appear in each round
        // catQuestions[category] = { all: Set<j>, round0: Set<j>, round1: Set<j>, round2: Set<j> }
        const catQuestions = {};
        categories.forEach((cat) => {
            catQuestions[cat] = { all: new Set(), roundSets: [new Set(), new Set(), new Set()] };
        });

        data.forEach((item) => {
            const goldValue = item.pred[key];
            if (!goldValue) return;
            const j = parseInt(item.index.split("-")[1], 10);
            const i = parseInt(item.index.split("-")[0], 10);
            const labels = goldValue.split(/[，,]/).map((s) => s.trim()).filter((s) => categories.includes(s));
            labels.forEach((label) => {
                if (catQuestions[label]) {
                    catQuestions[label].all.add(j);
                    catQuestions[label].roundSets[i].add(j);
                }
            });
        });

        // Build table data (skip categories with 0 total)
        const tableData = categories
            .map((category) => {
                const cq = catQuestions[category];
                const total = cq.all.size;
                // Stable: question j appears in all rounds that exist
                // Find rounds that have data for this question set
                const nonEmptyRounds = cq.roundSets.filter((s) => s.size > 0);
                const stableCount = nonEmptyRounds.length <= 2
                    ? 0
                    : [...cq.all].filter((j) => nonEmptyRounds.every((s) => s.has(j))).length;
                return {
                    category,
                    count1: cq.roundSets[0].size,
                    count2: cq.roundSets[1].size,
                    count3: cq.roundSets[2].size,
                    total,
                    stableCount,
                    stabilityRate: total > 0 ? ((stableCount / total) * 100).toFixed(2) + "%" : "0.00%",
                };
            })
            .filter((row) => row.total > 0);

        // Add summary row
        const totalRow = {
            category: "总计",
            count1: tableData.reduce((s, r) => s + r.count1, 0),
            count2: tableData.reduce((s, r) => s + r.count2, 0),
            count3: tableData.reduce((s, r) => s + r.count3, 0),
            total: tableData.reduce((s, r) => s + r.total, 0),
            stableCount: tableData.reduce((s, r) => s + r.stableCount, 0),
            stabilityRate: "",
        };
        totalRow.stabilityRate = totalRow.total > 0
            ? ((totalRow.stableCount / totalRow.total) * 100).toFixed(2) + "%"
            : "0.00%";
        tableData.push(totalRow);

        result[resultKey] = tableData;
    });

    // Add total across all dimensions
    const allTableData = dimensions.flatMap((d) => result[d.resultKey] || []);
    const allRowsWithoutTotal = allTableData.filter((r) => r.category !== "总计");
    if (allRowsWithoutTotal.length > 0) {
        result.total = [{
            category: "总计",
            count1: allRowsWithoutTotal.reduce((s, r) => s + r.count1, 0),
            count2: allRowsWithoutTotal.reduce((s, r) => s + r.count2, 0),
            count3: allRowsWithoutTotal.reduce((s, r) => s + r.count3, 0),
            total: allRowsWithoutTotal.reduce((s, r) => s + r.total, 0),
            stableCount: allRowsWithoutTotal.reduce((s, r) => s + r.stableCount, 0),
            stabilityRate: "",
        }];
        result.total[0].stabilityRate = result.total[0].total > 0
            ? ((result.total[0].stableCount / result.total[0].total) * 100).toFixed(2) + "%"
            : "0.00%";
    }

    return result;
}