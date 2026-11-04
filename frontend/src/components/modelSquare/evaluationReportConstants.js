// LLM 通用测试集维度（与 rankingScore.vue 尺子一大语言模型一致）
export const LLM_RULER1_DIMENSIONS = [
  "mmlu",
  "aime24",
  "aime25",
  "live_code_bench",
  "gpqa",
  "bfcl_v3",
  "ifeval",
  "mmlu_redux",
  "aime26",
]

// LLM 领域测试集（Ruler2 AISF-改写，与 rankingScore.vue 一致）
export const LLM_RULER2_DATASETS = [
  "om_alarm_diag",
  "om_mml_generate",
  "明确代词指向",
  "省略主语",
  "省略宾语",
  "省略主体",
  "省略服务名",
  "主题明确",
  "询问历史细节信息",
  "单意图-易",
  "多意图-易",
  "上下文理解",
  "单意图-难",
  "多意图-难",
  // "外挂fewshot库",
  // "不外挂fewshot库",
  "上下文信息无法支持内容补全",
  "上下文信息无法支持指代消解",
  "需内容补全",
  "需指代消解",
  "意图模糊",
  "意图完备"
]

// MLLM 通用测试集维度
export const MLLM_RULER1_DIMENSIONS = [
  "HallusionBench",
  "MMMU",
  "MMStar",
  "OCRBench",
  "DailyOmni",
  "librispeech_asr",
  "Fleurs",
  "MELD",
  "MMAU",
  "MMAR",
  "Video-MME",
  "WorldSense",
  "ScreenSpot_Pro",
  "MVBench",
]

// MLLM 领域测试集（Ruler2）
export const MLLM_RULER2_DATASETS = [
  "注意力检测",
  "坐姿检测",
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
  "通讯-运营商APP(中国联通)",
]

// LLM Ruler2 Cascader 选项结构
export const LLM_RULER2_OPTIONS = [
  {
    value: "aisf_llm_gaixie",
    label: "AISF LLM 改写",
    children: [
      // { value: "外挂fewshot库", label: "外挂fewshot库", disabled: false },
      // { value: "不外挂fewshot库", label: "不外挂fewshot库", disabled: false },
      {label:"上下文信息无法支持内容补全",value:"上下文信息无法支持内容补全"},
      {label:"上下文信息无法支持指代消解",value:"上下文信息无法支持指代消解"},
      {label:"需内容补全",value:"需内容补全"},
      {label:"需指代消解",value:"需指代消解"},
      {label:"意图模糊",value:"意图模糊"},
      {label:"意图完备",value:"意图完备"}
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_yitu",
    label: "AISF LLM 意图",
    children: [
      { value: "单意图", label: "单意图", disabled: false },
      { value: "两意图", label: "两意图", disabled: false },
      { value: "三意图", label: "三意图", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_memory_cuiqu",
    label: "记忆萃取",
    children: [
      { value: "记忆萃取-信息点提取", label: "信息点提取", disabled: false },
      { value: "记忆萃取-更新", label: "更新", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_memory_zhaohui",
    label: "记忆召回",
    children: [
      { value: "记忆召回-查询扩写", label: "查询扩写", disabled: false },
      { value: "记忆召回-总结过滤", label: "总结过滤", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_skilltican",
    label: "skill提参",
    children: [
      { value: "宽松通过率", label: "宽松通过率", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_guican",
    label: "GUI提参",
    children: [
      { value: "GUI提参", label: "GUI提参", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_banxue",
    label: "伴学提参",
    children: [
      { value: "提参", label: "提参", disabled: false },
      { value: "总结", label: "总结", disabled: false },
      { value: "提醒", label: "提醒", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_llm_coordinator",
    label: "Coordinator",
    children: [
      { value: "Coordinator", label: "Coordinator", disabled: false },
    ],
    disabled: false,
  },
]

// MLLM Ruler2 Cascader 选项结构
export const MLLM_RULER2_OPTIONS = [
  {
    value: "aisf_banxue",
    label: "儿童伴读",
    children: [
      { value: "注意力检测", label: "注意力检测", disabled: false },
      { value: "坐姿检测", label: "坐姿检测", disabled: false },
    ],
    disabled: false,
  },
  {
    value: "aisf_gui_plan",
    label: "AISF-GUI规划",
    children: [
      {
        value: "影音娱乐-长视频(腾讯视频)",
        label: "长视频(腾讯视频)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(QQ音乐)",
        label: "音乐(QQ音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(爱奇艺)",
        label: "长视频(爱奇艺)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(优酷视频)",
        label: "长视频(优酷视频)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(芒果TV)",
        label: "长视频(芒果TV)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(网易云音乐)",
        label: "音乐(网易云音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(酷狗音乐)",
        label: "音乐(酷狗音乐)",
        disabled: false,
      },
      { value: "影音娱乐-短剧(红果)", label: "短剧(红果)", disabled: false },
      {
        value: "系统工具-应用安装(应用市场)",
        label: "应用安装(应用市场)",
        disabled: false,
      },
      { value: "游戏(咸鱼之王)", label: "咸鱼之王", disabled: false },
      { value: "游戏(蛋仔派对)", label: "蛋仔派对", disabled: false },
      { value: "游戏(开心消消乐)", label: "开心消消乐", disabled: false },
      { value: "游戏(剑网3)", label: "剑网3", disabled: false },
      {
        value: "通讯-运营商APP(中国联通)",
        label: "运营商APP(中国联通)",
        disabled: false,
      },
    ],
    disabled: false,
  },
  {
    value: "aisf_gui_vla",
    label: "AISF-GUI操控",
    children: [
      {
        value: "影音娱乐-长视频(腾讯视频)",
        label: "长视频(腾讯视频)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(QQ音乐)",
        label: "音乐(QQ音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(爱奇艺)",
        label: "长视频(爱奇艺)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(优酷视频)",
        label: "长视频(优酷视频)",
        disabled: false,
      },
      {
        value: "影音娱乐-长视频(芒果TV)",
        label: "长视频(芒果TV)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(网易云音乐)",
        label: "音乐(网易云音乐)",
        disabled: false,
      },
      {
        value: "影音娱乐--音乐(酷狗音乐)",
        label: "音乐(酷狗音乐)",
        disabled: false,
      },
      { value: "影音娱乐-短剧(红果)", label: "短剧(红果)", disabled: false },
      {
        value: "系统工具-应用安装(应用市场)",
        label: "应用安装(应用市场)",
        disabled: false,
      },
      { value: "游戏(咸鱼之王)", label: "咸鱼之王", disabled: false },
      { value: "游戏(蛋仔派对)", label: "蛋仔派对", disabled: false },
      { value: "游戏(开心消消乐)", label: "开心消消乐", disabled: false },
      { value: "游戏(剑网3)", label: "剑网3", disabled: false },
      {
        value: "通讯-运营商APP(中国联通)",
        label: "运营商APP(中国联通)",
        disabled: false,
      },
    ],
    disabled: false,
  },
]

// Ruler2 场景列表（用于查找最佳匹配）
export const LLM_RULER2_SCENE_LIST = ["operations", "aisf_llm_gaixie", "aisf_llm_yitu", "aisf_memory_cuiqu", "aisf_memory_zhaohui",'aisf_llm_skilltican', 'aisf_llm_guican', 'aisf_llm_banxue', 'aisf_llm_coordinator']
export const MLLM_RULER2_SCENE_LIST = ["aisf_banxue", "aisf_gui_plan", "aisf_gui_vla"]

// MLLM Ruler1 维度分组
export const VISUAL_DIMENSIONS = ["MMMU", "MMStar", "Video-MME"];
export const AUDIO_DIMENSIONS = ["librispeech_asr", "MMAU", "MMAR", "WorldSense"];
export const OTHER_MLLM_R1 = ["HallusionBench", "OCRBench", "DailyOmni", "Fleurs", "MELD", "ScreenSpot_Pro", "MVBench"];

/**
 * 业务维度映射表（与 publishedReport.vue 的 REPORT_TYPE_SCENE_MAP 逻辑一致）
 * 用于 modelCompareTab.vue 按业务维度分别过滤可选的对比模型
 */
export const BIZ_SCENE_MAP = [
  { bizKey: "llmGeneral", label: "大语言通用", source: "llm", type: "ruler1", scenes: null },
  { bizKey: "llmDomain", label: "大语言领域", source: "llm", type: "ruler2", scene: null },
  { bizKey: "visualGeneral", label: "视觉-通用", source: "mml", type: "ruler1", scenes: ["MMMU", "MMStar", "Video-MME"] },
  { bizKey: "audioGeneral", label: "音频-通用", source: "mml", type: "ruler1", scenes: ["librispeech_asr", "MMAU", "MMAR", "WorldSense"] },
  { bizKey: "otherGeneral", label: "其他-通用", source: "mml", type: "ruler1", scenes: ["HallusionBench", "OCRBench", "DailyOmni", "Fleurs", "MELD", "ScreenSpot_Pro", "MVBench"] },
  { bizKey: "mllmDomain", label: "多模态领域", source: "mml", type: "ruler2", scene: null },
];


// 默认展示的测试集（与 rankingScore.vue 表格展示的列一致）
export const LLM_RULER1_DEFAULT_DIMENSIONS = [
  "mmlu_redux",
  "aime26",
  "live_code_bench",
  "gpqa",
  "ifeval",
]

export const MLLM_RULER1_DEFAULT_DIMENSIONS = [
  "MMMU",
  "MMStar",
  "Video-MME",
  // "MMAU",
  // "MMAR",
  // "WorldSense",
]

