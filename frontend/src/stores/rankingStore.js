import { defineStore } from 'pinia';
import { getCurrentFullRes } from '@/api/dataService';
import { STRINGS } from "@/utils/Constants.js";

export const DATASET_MAPPING = {
    'ruler1': {
        subsets: ['mmlu', 'mmlu_redux', 'aime24', 'aime25', 'aime26', 'live_code_bench', 'gpqa', 'bfcl_v3', 'ifeval'
        ],
        labels: {
            mmlu: 'MMLU',
            mmlu_redux: 'MMLU-Redux',
            aime24: 'AIME2024',
            aime25: 'AIME2025',
            aime26: 'AIME2026',
            live_code_bench: 'LiveCodeBench',
            gpqa: 'GPQA-Diamond',
            bfcl_v3: 'BFCL',
            ifeval: 'IFEval',
        },
    },
    'service': {
        subsets: ['tool_chose', 'param_extra', 'intent_detect'],
        labels: {
            tool_chose: '工具选择',
            param_extra: '工具填参',
            intent_detect: '意图识别',
            // style: '风格',
            // emotion: '情感',
        },
    },
    'box_tool_use': {
        subsets: [
            // 'view', 'fit', 'call',
        ],
        labels: {
            // view: '观影',
            // fit: '健身',
            // call: '亲情通话',
        },
    },
    'aisf_llm_gaixie': {
        subsets: [
            // "外挂fewshot库",
            // "不外挂fewshot库"
            "上下文信息无法支持内容补全",
            "上下文信息无法支持指代消解",
            "需内容补全",
            "需指代消解",
            "意图模糊",
            "意图完备"
        ],
        labels: {
            // 外挂fewshot库: "外挂fewshot库",
            // 不外挂fewshot库: "不外挂fewshot库",
            "上下文信息无法支持内容补全":"上下文信息无法支持内容补全",
            "上下文信息无法支持指代消解":"上下文信息无法支持指代消解",
            "需内容补全":"需内容补全",
            "需指代消解":"需指代消解",
            "意图模糊":"意图模糊",
            "意图完备":"意图完备"
        },
    },
    'aisf_llm_yitu': {
        subsets: [
            "单意图",
            "两意图",
            "三意图"
        ],
        labels: {
            "单意图": "单意图",
            "两意图": "两意图",
            "三意图": "三意图"
        },
    },
    'multiRuler1': {
        subsets: ['HallusionBench', 'MMMU', 'MMStar', 'OCRBench', 'ScreenSpot_Pro', 'librispeech_asr', 'MMAU', 'MMAR',
            'Fleurs', 'MELD', 'Video-MME', 'MVBench', 'DailyOmni', 'WorldSense'
        ],
        labels: {
            HallusionBench: 'Hallusion',
            MMMU: 'MMMU',
            MMStar: 'MMStar',
            OCRBench: 'OCR',
            ScreenSpot_Pro: 'ScreenSpot',
            librispeech_asr: 'librispeech',
            MMAU: 'MMAU',
            MMAR: 'MMAR',
            Fleurs: 'Fleurs',
            MELD: 'MELD',
            "Video-MME": 'VideoMME',
            MVBench: 'MVBench',
            DailyOmni: 'DailyOmni',
            WorldSense: 'WorldSense'
        },
    },
    multiaisf_banxue: {
        subsets: ['注意力检测', '坐姿检测'],
        labels: {
            '注意力检测': '注意力检测',
            '坐姿检测': '坐姿检测',
        },
    },
    multiaisf_gui_plan: {
        subsets: [
            "影音娱乐-长视频(腾讯视频)",
            "影音娱乐--音乐(QQ音乐)",
            "影音娱乐-长视频(爱奇艺)",
            "影音娱乐-长视频(优酷视频)",
            "影音娱乐-长视频(芒果TV)",
            "影音娱乐--音乐(网易云音乐)",
            "影音娱乐--音乐(酷狗音乐)",
            "影音娱乐-短剧(红果)",
            "系统工具-应用安装(应用市场)",
            "游戏(咸鱼之王)",
            "游戏(蛋仔派对)",
            "游戏(开心消消乐)",
            "游戏(剑网3)",
            "通讯-运营商APP(中国联通)"
        ],
        labels: {
            "影音娱乐-长视频(腾讯视频)": "长视频(腾讯视频)",
            "影音娱乐--音乐(QQ音乐)": "音乐(QQ音乐)",
            "影音娱乐-长视频(爱奇艺)": "长视频(爱奇艺)",
            "影音娱乐-长视频(优酷视频)": "长视频(优酷视频)",
            "影音娱乐-长视频(芒果TV)": "长视频(芒果TV)",
            "影音娱乐--音乐(网易云音乐)": "音乐(网易云音乐)",
            "影音娱乐--音乐(酷狗音乐)": "音乐(酷狗音乐)",
            "影音娱乐-短剧(红果)": "短剧(红果)",
            "系统工具-应用安装(应用市场)": "应用安装(应用市场)",
            "游戏(咸鱼之王)": "游戏(咸鱼之王)",
            "游戏(蛋仔派对)": "游戏(蛋仔派对)",
            "游戏(开心消消乐)": "游戏(开心消消乐)",
            "游戏(剑网3)": "游戏(剑网3)",
            "通讯-运营商APP(中国联通)": "运营商APP(中国联通)"
        },
    },
    multiaisf_gui_vla: {
        subsets: [
            "影音娱乐-长视频(腾讯视频)",
            "影音娱乐--音乐(QQ音乐)",
            "影音娱乐-长视频(爱奇艺)",
            "影音娱乐-长视频(优酷视频)",
            "影音娱乐-长视频(芒果TV)",
            "影音娱乐--音乐(网易云音乐)",
            "影音娱乐--音乐(酷狗音乐)",
            "影音娱乐-短剧(红果)",
            "系统工具-应用安装(应用市场)",
            "游戏(咸鱼之王)",
            "游戏(蛋仔派对)",
            "游戏(开心消消乐)",
            "游戏(剑网3)",
            "通讯-运营商APP(中国联通)"
        ],
        labels: {
            "影音娱乐-长视频(腾讯视频)": "长视频(腾讯视频)",
            "影音娱乐--音乐(QQ音乐)": "音乐(QQ音乐)",
            "影音娱乐-长视频(爱奇艺)": "长视频(爱奇艺)",
            "影音娱乐-长视频(优酷视频)": "长视频(优酷视频)",
            "影音娱乐-长视频(芒果TV)": "长视频(芒果TV)",
            "影音娱乐--音乐(网易云音乐)": "音乐(网易云音乐)",
            "影音娱乐--音乐(酷狗音乐)": "音乐(酷狗音乐)",
            "影音娱乐-短剧(红果)": "短剧(红果)",
            "系统工具-应用安装(应用市场)": "应用安装(应用市场)",
            "游戏(咸鱼之王)": "游戏(咸鱼之王)",
            "游戏(蛋仔派对)": "游戏(蛋仔派对)",
            "游戏(开心消消乐)": "游戏(开心消消乐)",
            "游戏(剑网3)": "游戏(剑网3)",
            "通讯-运营商APP(中国联通)": "运营商APP(中国联通)"
        },
    }
};

const extractedParam = (modelName) => {
    const regex = /[-_](\d+[bB])[-_]?/gi;
    const match = modelName.match(regex);

    if (match) {
        return match[0].replace(/^[-_]/, '')
            .replace(/[-_]$/, '')
            .replace(/b/gi, 'B');
    } else {
        return STRINGS.DASH;
    }
}

export const useRankingStore = defineStore('ranking', {
    state: () => ({
        ruler1Values: [],
        ruler2Values: {
            aisf_llm_gaixie: [],
            aisf_llm_yitu: [],
        },
    }),
    actions: {
        async getRankingData() {
            try {
                const response = await getCurrentFullRes();
                this.processRawData(response.data);
            } catch (error) {
                console.error('Error fetching ranking data:', error);
            }
        },

        processRawData(rawData) {
            this.ruler1Values = this.processRuler1ModelData(rawData.ruler1 || {});
            this.ruler2Values = this.processRuler2ModelData(rawData.ruler2 || {});
        },

        processRuler1ModelData(ruler1Data) {
            const values = [];

            Object.entries(ruler1Data).forEach(([modelName, modelGroup]) => {
                const param = extractedParam(modelName);
                let type = STRINGS.DASH;
                let average = 0;

                const targetScores = [];
                const result = modelGroup?.result || [];
                result.forEach(subset => {
                    const subsetName = subset?.dataset_name || STRINGS.DASH;
                    if (DATASET_MAPPING.ruler1.subsets.includes(subsetName)) {
                        targetScores.push({
                            key: subsetName,
                            score: subset?.score || 0,
                        })
                    } else if (subsetName === 'average') {
                        average = subset?.score || 0;
                        type = subset.type || STRINGS.DASH;
                    }
                });

                const value = {
                    id: values.length + 1,
                    name: modelName || STRINGS.DASH,
                    createTime: modelGroup?.creation_date || STRINGS.DASH,
                    updateTime: modelGroup?.update_date || STRINGS.DASH,
                    type: type,
                    averageScore: Number(average),
                    publisher: modelGroup?.publisher || STRINGS.DASH,
                    new: modelGroup?.is_new || false,
                    parameter: param,
                    subsets: targetScores,
                };
                values.push(value);
            });

            return values;
        },

        processRuler2ModelData(ruler2Data) {
            const output = {
                aisf_llm_gaixie: [],
                aisf_llm_yitu: [],
            };

            Object.entries(ruler2Data).forEach(([modelName, modelGroup]) => {
                const param = extractedParam(modelName);

                const result = modelGroup?.result || [];
                result.forEach(item => {
                    const datasetName = item.dataset_name;

                    const mapping = DATASET_MAPPING[datasetName];
                    if (!mapping) return;

                    const subsetsList = item.metrics
                        ?.flatMap(metric => metric.categories)
                        ?.flatMap(category => category.subsets) || [];
                    const targetSubset = mapping.subsets.map(subsetName => {
                        return {
                            key: subsetName,
                            score: (subsetsList.find(s => s.name === subsetName)?.score || -1),
                            tri_subsets: (subsetsList.find(s => s.name === subsetName)?.tri_subsets || []),
                        };
                    });

                    const scores = targetSubset.map(i => i.score).filter((num) => num !== -1);
                    const average = scores.length > 0
                        ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(4)
                        : '0.0000';

                    const value = {
                        id: output[datasetName].length + 1,
                        name: modelName,
                        createTime: modelGroup?.creation_date || STRINGS.DASH,
                        updateTime: modelGroup?.update_date || STRINGS.DASH,
                        // 当前测试集的测评时间（用于尺子二榜单展示测评时间）
                        testTime: item.test_time || "",
                        type: item.type || STRINGS.DASH,
                        averageScore: item.score ? item.score : Number(average),
                        publisher: modelGroup?.publisher || STRINGS.DASH,
                        new: modelGroup?.is_new || false,
                        parameter: param,
                        subsets: targetSubset,
                    };

                    output[datasetName].push(value);
                });
            });

            return output;
        },
    }
});