const { createApp } = Vue;

const SELF_BUILT_BENCHMARKS = ['aisf_iot'];

const RUN_PARAM_DEFS = [
  // 模型
  { key: 'model_base_url', flag: '--model-base-url', group: '模型', type: 'text', required: true, placeholder: 'https://.../compatible-mode/v1', help: '模型 API 地址；直连第三方模型必填（阿里云填 compatible-mode/v1 端点），留空读环境变量 OPENAI_BASE_URL，也可填 ${VAR} 引用自定义环境变量' },
  { key: 'model_api_key', flag: '--model-api-key', group: '模型', type: 'text', required: true, placeholder: '', help: '模型 API 密钥；直连第三方模型必填，留空读环境变量 OPENAI_API_KEY，也可填 ${VAR} 引用自定义环境变量' },
  { key: 'model_api_protocol', flag: '--model-api-protocol', group: '模型', type: 'select', options: ['auto', 'openai-chat', 'openai-responses', 'anthropic'], help: '模型 API 协议；默认 auto（=harness 默认），不确定就选 auto，OpenAI 兼容端点选 openai-chat' },
  { key: 'model_params', flag: '--model-params', group: '模型', type: 'json', placeholder: '{"temperature": 0, "max_tokens": 32768}', help: '模型推理参数（JSON），如 temperature/max_tokens/reasoning_effort；用于覆盖 harness 默认，不填用默认' },
  // 环境
  { key: 'environment', flag: '--env', group: '环境', type: 'select', options: ['host_process', 'docker'], help: '运行环境：host_process 宿主机直接跑（轻量/调试）；docker 容器隔离（装依赖/改系统/不可信代码，如 swebench）。默认 host_process' },
  { key: 'env_params', flag: '--env-params', group: '环境', type: 'json', placeholder: '{"image": "...", "workspace": "/workspace"}', help: '环境 provider 配置（JSON）；只在需要覆盖默认环境配置时填，如 docker 的 workspace / mounts / resources；host_process 通常留空' },
  { key: 'env_open_qps', flag: '--env-open-qps', group: '环境', type: 'text', placeholder: 'docker=2, modal=1', help: '环境打开限速（provider=qps，如 docker=2，逗号分隔）；高并发起环境怕打爆 provider 时才设，0/负数不限速，一般留空' },
  // benchmark / harness
  { key: 'benchmark_params', flag: '--benchmark-params', group: 'Benchmark/Harness', type: 'json', placeholder: '{"sample_ids": ["pydata__xarray-3993"], "eval_timeout": 1800}', help: 'Benchmark 参数（JSON），如 sample_ids 筛选要跑的样本、eval_timeout 评测超时；不填跑全部' },
  { key: 'harness_params', flag: '--harness-params', group: 'Benchmark/Harness', type: 'json', placeholder: '{"step_limit": 250, "cost_limit": 3.0}', help: 'Harness 参数（JSON），如 step_limit 步数上限、cost_limit 费用上限、timeout 超时；控制 agent 运行行为' },
  // 任务 / 执行
  { key: 'task_concurrency', flag: '--task-concurrency', group: '任务/执行', type: 'number', min: 1, placeholder: '如 2', help: '本次 run 内最大并发物理尝试数；默认 32（并发跑多个 task），机器/API 扛不住就调小' },
  { key: 'k', flag: '--k', group: '任务/执行', type: 'number', min: 1, placeholder: '如 1', help: '每个 task 最多独立尝试次数；默认 1，配合 attempt_strategy 用（k>1 多试几次提通过率）' },
  { key: 'attempt_strategy', flag: '--attempt-strategy', group: '任务/执行', type: 'select', options: ['avg', 'pass'], help: '重复尝试聚合策略（配合 k）；avg=k 次取平均，pass=k 次任一过即过。默认 avg' },
  { key: 'max_retries', flag: '--max-retries', group: '任务/执行', type: 'number', placeholder: '如 0', help: '匹配任务/评分错误的最大重试次数；默认 0（不重试），配合 retry_pattern_list 决定重试哪些错误' },
  { key: 'retry_pattern_list', flag: '--retry-pattern-list', group: '任务/执行', type: 'json', placeholder: '["Timeout", "Connection"]', help: '错误重试白名单（正则，JSON 数组，如 ["Timeout","Connection"]）；只重试匹配这些正则的错误，不填则任何错误都重试' },
  // 输出 / 结果
  { key: 'run_id', flag: '--run-id', group: '输出/结果', type: 'text', placeholder: '自定义 run 目录名', help: 'run 目录名（run id）；留空自动用时间戳，填了自定义好记的名字' },
  { key: 'run_name', flag: '--run-name', group: '输出/结果', type: 'text', placeholder: '结果命名空间', help: '结果命名空间（results_dir 下的分组子目录）；多组对比实验时用不同 run_name 分组' },
  { key: 'results_dir', flag: '--results-dir', group: '输出/结果', type: 'text', placeholder: 'results', help: '结果根目录；默认 results，结果写到 <results_dir>/<benchmark>/<model>/<run_id> 下' },
  { key: 'reuse', flag: '--reuse', group: '输出/结果', type: 'text', placeholder: 'run_id（留空不复用）', help: '复用指定 run id 的结果；默认不复用，填 run_id 可续跑/复用已有结果' },
  // 超时 / 资源
  { key: 'timeout_seconds', flag: '--timeout-seconds', group: '超时/资源', type: 'number', placeholder: '360000（0 禁用）', help: '总评测超时秒数（默认 360000，0 禁用）' },
  { key: 'provider_limit', flag: '--provider-limit', group: '超时/资源', type: 'text', placeholder: 'docker=2, modal=1', help: '每个 provider 最多同时并发的环境实例数（provider=count，如 docker=2，逗号分隔）；0=不限，默认 128' },
  // 日志 / 进度
  { key: 'log_level', flag: '--log-level', group: '日志/进度', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help: '控制台日志级别（DEBUG 最详细→CRITICAL 最精简）；默认 INFO' },
  { key: 'file_log_level', flag: '--file-log-level', group: '日志/进度', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help: '运行日志文件级别（DEBUG 最详细→CRITICAL 最精简）；默认 DEBUG' },
  // 分析
  { key: 'enable_analysis', flag: '--enable-analysis', group: '分析', type: 'bool', help: '评测后是否运行分析；默认开启，配合 analysis_params 控制跑哪些分析器' },
  { key: 'analysis_params', flag: '--analysis-params', group: '分析', type: 'json', placeholder: '{"analyzers": ["ExceptionAnalyzer"]}', help: '分析参数（JSON）；如 {"analyzers":["ExceptionAnalyzer"]} 只跑指定分析器，{"exclude_analyzers":[]} 启用全部' },
  // 依赖 / 配置
  { key: 'auto_install_dependencies', flag: '--auto-install-dependencies', group: '依赖/配置', type: 'bool', help: '缺少依赖时自动安装可信的可选组件（默认关闭）' },
];

const GROUP_HELP = {
  '输出/结果': '结果目录结构：<results_dir>/[<run_name>/]<benchmark>/<model>/<run_id/>\n\n默认（全留空）：\nresults/swebench_verified/qwen3.5-plus/20260921_094339/\n\n有值（run_name=exp1，run_id=my-run）：\nresults/exp1/swebench_verified/qwen3.5-plus/my-run/\n\nrun_id：run 目录名，留空自动时间戳\nrun_name：results_dir 下的分组子目录，留空不加\nresults_dir：结果根目录，默认 results\nreuse：复用指定 run_id 结果，留空不复用',
};

// 对比评估：任务信息对比的维度（横向表头顺序）
const COMPARE_DIMS = [
  { key: 'benchmark', label: 'Benchmark' },
  { key: 'harness', label: 'Harness' },
  { key: 'model', label: 'Model' },
  { key: 'environment', label: 'Environment' },
];

// 对比评估：统计指标对比（六个指标，各画一张横向柱状图）
const COMPARE_METRICS = [
  { key: 'correct', label: '正确率', fmt: 'rate' },
  { key: 'wall', label: '用例执行时间', fmt: 'duration' },
  { key: 'latency', label: '平均每条用例时延', fmt: 'seconds' },
  { key: 'total_tokens', label: 'token 消耗数', fmt: 'number' },
  { key: 'avg_tokens', label: '平均 token 消耗', fmt: 'number' },
  { key: 'avg_steps', label: '有效用例平均轨迹步数', fmt: 'number' },
];

// 对比评估：任务配色（按选中顺序取色，区分不同任务）
const COMPARE_COLORS = ['#2563eb', '#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#db2777', '#65a30d'];

const ANALYZER_HELP_GROUPS = [
  { group: '统计型', items: [
    { name: 'BasicMetricAnalyzer', desc: '轨迹基础统计：步数、工具调用数、平均每步工具、工具分布。纯统计不判 badcase。', params: '' },
    { name: 'TrajectoryTimeCostAnalyzer', desc: '轨迹总墙钟时长；默认纯统计，超 max_seconds 才 flag。', params: 'max_seconds（时长阈值，默认不限）' },
  ]},
  { group: '报错/异常型', items: [
    { name: 'ExceptionAnalyzer', desc: '运行时异常，traceback 指纹归类（类型/位置/根因）。', params: '' },
    { name: 'TerminalBench2ExceptionAnalyzer', desc: '异常检测的 TerminalBench2 变体，额外识别环境级错误。', params: '' },
    { name: 'TruncationAnalyzer', desc: '输出被截断（stop_reason=length/max_tokens）。', params: '' },
    { name: 'JSONErrorAnalyzer', desc: 'JSON 格式错误（缺 JSON 或混多余文本）。', params: '' },
    { name: 'EmptyContentAnalyzer', desc: '死步：只有 reasoning、无 content 且无工具调用。', params: '' },
    { name: 'CompletionLengthAnalyzer', desc: '单步输出 token 数超 max_tokens 阈值。', params: 'max_tokens（默认 131072）' },
  ]},
  { group: '效率型', items: [
    { name: 'LLMInferLatencyAnalyzer', desc: 'LLM 推理时延异常（逐步 llm_infer_ms）。', params: 'p90_threshold / p95_threshold / max_threshold / step_threshold' },
    { name: 'ToolExecutionLatencyAnalyzer', desc: '工具/环境动作时延异常（env_action_ms）。', params: 'p90_threshold / p95_threshold / max_threshold / step_threshold' },
  ]},
  { group: '重复/死循环型', items: [
    { name: 'ContentRepetitionAnalyzer', desc: 'content 重复/循环（字符连跑、重复句/短语/子串）。', params: 'min_text_len、char_run_min、sentence_min_dup、phrase_ngram_sizes、substring_min_len' },
    { name: 'ReasoningRepetitionAnalyzer', desc: 'reasoning 重复/循环。', params: '同 ContentRepetitionAnalyzer' },
    { name: 'StepToolRepetitionAnalyzer', desc: '单步内重复调同名同参工具。', params: 'threshold（重复比例，默认 0.2）' },
    { name: 'CrossStepToolRepetitionAnalyzer', desc: '跨步重复调同一工具。', params: 'threshold（默认 0.2）' },
    { name: 'ConsecutiveToolRepetitionAnalyzer', desc: '连续相同工具调用（死循环）。', params: 'consecutive_threshold（连续次数，默认 5）' },
    { name: 'TerminalBench2ConsecutiveToolRepetitionAnalyzer', desc: '连续工具重复的 TerminalBench2 变体，排除按键等待。', params: '' },
  ]},
  { group: '语言/内容型', items: [
    { name: 'ContentMixedLangAnalyzer', desc: 'content 中英混用。', params: 'min_cjk（最少中文数，默认 10）、min_en_chars（最少英文数，默认 10）' },
    { name: 'ReasoningMixedLangAnalyzer', desc: 'reasoning 中英混用。', params: 'min_cjk、min_en_chars' },
    { name: 'ContentKeywordAnalyzer', desc: 'content 泄露特殊 token（<think>、<tool_call> 等）。', params: 'keywords（敏感 token 列表）' },
    { name: 'ReasoningKeywordAnalyzer', desc: 'reasoning 泄露特殊 token。', params: 'keywords' },
  ]},
  { group: '网络/终端型（仅 terminal_bench_2）', items: [
    { name: 'NetworkOperationAnalyzer', desc: '网络操作占比（curl/pip install/git clone 等）。', params: 'threshold（占比 %，默认 20）' },
    { name: 'TerminalBench2CommandRunningAnalyzer', desc: '上一条命令还没跑完就敲下一个键。', params: 'prompt_chars、wait_keystrokes' },
  ]},
  { group: '作弊检测', items: [
    { name: 'HackDetectionAnalyzer', desc: '两阶段奖励欺骗检测：规则高召回 + LLM 高精度。', params: 'model、enable_llm_verification、rule_threshold、only_correct' },
  ]},
  { group: 'LLM 定性分析（需额外调 LLM）', items: [
    { name: 'QualitativeAnalyzer', desc: '单轨迹 LLM 定性分析：阶段标注、叙事分段、错误步汇总。', params: 'model、chunk_size（每批步数，默认 15）、render_mode、max_retries、temperature' },
    { name: 'MultiQualitativeAnalyzer', desc: '双轨迹对比（目标 run vs 正确参考 run）。', params: 'reference_dir（参考目录）、require_reference' },
  ]},
];

// 页面状态持久化（sessionStorage：刷新保留，关标签页清除）
function loadSavedTab() {
  try { return sessionStorage.getItem('ac.activeTab') || 'benchmarks'; } catch (e) { return 'benchmarks'; }
}

function loadSavedDetail() {
  try {
    const d = JSON.parse(sessionStorage.getItem('ac.detail') || 'null');
    if (d && d.benchmark && d.model && d.run_id) {
      return { benchmark: d.benchmark, model: d.model, run_id: d.run_id, data: null };
    }
  } catch (e) { /* ignore */ }
  return null;
}

createApp({
  data() {
    return {
      activeTab: loadSavedTab(),
      detail: loadSavedDetail(),           // { benchmark, model, run_id, data }
      showRunInfo: false,
      showStats: false,
      showAnalysis: false,
      showDetail: false,
      showLog: false,
      showTaskDetailModal: false,
      showAnalyzerHelp: false,
      taskDetailData: null,
      taskDetailLoading: false,
      components: { benchmarks: [], harnesses: [] },
      benchmarkStatus: {},
      downloadingId: null,
      previewData: null,
      showPreviewModal: false,
      previewLoading: false,
      previewTitle: '',
      runs: [],
      runsPage: 1,
      runsPageSize: 10,
      runsJump: '',
      detailPage: 1,
      detailPageSize: 10,
      detailJump: '',
      selectedBenchmark: null,
      benchmarkDoc: null,
      benchmarkLoading: false,
      showBenchmarkModal: false,
      showHarnessModal: false,
      selectedHarness: null,
      harnessDoc: null,
      harnessLoading: false,
      runForm: {
        benchmark: '', harness: '', model: '',
        model_base_url: '', model_api_key: '', model_api_protocol: 'auto', model_params: '',
        environment: 'host_process', env_params: '', env_open_qps: '',
        benchmark_params: '', harness_params: '',
        task_concurrency: null, k: null, attempt_strategy: 'avg', max_retries: null, retry_pattern_list: '',
        run_id: '', run_name: '', results_dir: '', reuse: '',
        timeout_seconds: null, provider_limit: '',
        log_level: 'INFO', file_log_level: 'DEBUG',
        enable_analysis: true, analysis_params: '',
        auto_install_dependencies: false,
      },
      showRunModal: false,
      showCliModal: false,
      cliCommand: '',
      previewCommand: '',
      cliResult: null,
      cliValidation: null,
      cliLoading: false,
      _previewTimer: null,
      pollTimer: null,
      completionNotice: '',
      refreshNotice: null,
      _refreshTimer: null,
      startResult: null,
      runValidation: null,
      helpPopover: { visible: false, flag: '', text: '', x: 0, y: 0 },
      loading: false,
      compareMode: false,
      compareSelected: [],
      comparePanelOpen: false,
      compareData: [],
      compareLoading: false,
    };
  },

  computed: {
    info() { return this.detail && this.detail.data ? this.detail.data.run_info : null; },
    metrics() { return this.detail && this.detail.data ? this.detail.data.metrics : null; },
    runMetrics() { return this.detail && this.detail.data ? this.detail.data.run_metrics : null; },
    summary() { return this.runMetrics ? this.runMetrics.summary : {}; },
    analysisMarkdown() { return this.detail && this.detail.data ? this.detail.data.analysis_summary_md : null; },
    runLog() { return this.detail && this.detail.data ? this.detail.data.run_log : null; },
    analyzerHelpGroups() { return ANALYZER_HELP_GROUPS; },
    runSpecs() {
      const r = this.info && this.info.request;
      if (!r) return [];
      return [
        { key: 'benchmark', id: (r.benchmark && r.benchmark.id) || '', params: this.sanitizeParams(r.benchmark && r.benchmark.params) },
        { key: 'environment', id: (r.environment && r.environment.id) || '', params: this.sanitizeParams(r.environment && r.environment.params) },
        { key: 'harness', id: (r.harness && r.harness.id) || '', params: this.sanitizeParams(r.harness && r.harness.params) },
        { key: 'model', id: (r.model && r.model.id) || '', params: this.modelParams(r.model) },
      ];
    },

    headlineSeries() {
      const series = (this.metrics && this.metrics.series) || [];
      for (const s of series) if (s && s.role === 'headline') return s;
      return series[0] || null;
    },
    kpiCorrect() { return this.headlineSeries ? this.headlineSeries.value : null; },
    kpiCounts() {
      const c = this.headlineSeries ? this.headlineSeries.counts : null;
      if (!c) return '';
      return `evaluated=${c.evaluated} / total=${c.total} / error=${c.error}`;
    },
    kpiWall() {
      const exec = this.summary.execution_wall_seconds;
      if (exec !== null && exec !== undefined) return exec;
      const i = this.info;
      if (!i || !i.started_at || !i.finished_at) return null;
      const s = new Date(i.started_at).getTime();
      const f = new Date(i.finished_at).getTime();
      return (isNaN(s) || isNaN(f)) ? null : (f - s) / 1000;
    },
    kpiAvgLatency() { return this.summary.avg_latency_seconds; },
    kpiTotalTokens() { return this.summary.total_tokens; },
    kpiAvgTokens() { return this.summary.avg_tokens_per_task; },
    kpiAvgSteps() { return this.summary.avg_steps; },
    detailTasks() { return this.runMetrics ? (this.runMetrics.per_task || []) : []; },
    totalDetailPages() { return Math.max(1, Math.ceil(this.detailTasks.length / this.detailPageSize)); },
    pagedDetailTasks() {
      const page = Math.min(this.detailPage, this.totalDetailPages);
      const start = (page - 1) * this.detailPageSize;
      return this.detailTasks.slice(start, start + this.detailPageSize);
    },
    totalRuns() { return this.runs.length; },
    totalRunsPages() { return Math.max(1, Math.ceil(this.runs.length / this.runsPageSize)); },
    pagedRuns() {
      const page = Math.min(this.runsPage, this.totalRunsPages);
      const start = (page - 1) * this.runsPageSize;
      return this.runs.slice(start, start + this.runsPageSize);
    },
    runParamGroups() {
      const map = {};
      for (const d of RUN_PARAM_DEFS) (map[d.group] || (map[d.group] = [])).push(d);
      return Object.entries(map).map(([group, items]) => ({ group, items }));
    },
    publicBenchmarks() {
      return this.components.benchmarks
        .filter(b => !SELF_BUILT_BENCHMARKS.includes(b.id))
        .sort((a, b) => (this.isReady(a.id) ? 0 : 1) - (this.isReady(b.id) ? 0 : 1));
    },
    selfBuiltBenchmarks() {
      return this.components.benchmarks
        .filter(b => SELF_BUILT_BENCHMARKS.includes(b.id))
        .sort((a, b) => (this.isReady(a.id) ? 0 : 1) - (this.isReady(b.id) ? 0 : 1));
    },
    compareDims() { return COMPARE_DIMS; },
    compareTasks() {
      return this.compareData.map((c, i) => {
        const req = (c.data && c.data.run_info && c.data.run_info.request) || {};
        const dim = (k) => {
          const v = req[k];
          if (!v || typeof v !== 'object') return { id: '—', params: [] };
          const id = v.id || '—';
          let params = [];
          if (k === 'model') {
            params = this.flattenParams(this.modelParams(v));
          } else {
            params = this.flattenParams(this.sanitizeParams(v.params));
          }
          return { id, params };
        };
        const hl = this._headline(c.data && c.data.metrics);
        const s = (c.data && c.data.run_metrics && c.data.run_metrics.summary) || {};
        const info = (c.data && c.data.run_info) || {};
        const wall = (() => {
          if (s.execution_wall_seconds != null) return s.execution_wall_seconds;
          if (info.started_at && info.finished_at) {
            const a = new Date(info.started_at).getTime();
            const b = new Date(info.finished_at).getTime();
            if (!isNaN(a) && !isNaN(b)) return (b - a) / 1000;
          }
          return null;
        })();
        return {
          key: c.benchmark + '/' + c.model + '/' + c.run_id,
          run_id: c.run_id,
          color: COMPARE_COLORS[i % COMPARE_COLORS.length],
          benchmark: dim('benchmark'),
          harness: dim('harness'),
          model: dim('model'),
          environment: dim('environment'),
          stats: {
            correct: hl ? hl.value : null,
            wall: wall,
            latency: s.avg_latency_seconds != null ? s.avg_latency_seconds : null,
            total_tokens: s.total_tokens != null ? s.total_tokens : null,
            avg_tokens: s.avg_tokens_per_task != null ? s.avg_tokens_per_task : null,
            avg_steps: s.avg_steps != null ? s.avg_steps : null,
          },
        };
      });
    },
    compareMetrics() { return COMPARE_METRICS; },
  },

  methods: {
    sanitizeParams(obj) {
      if (obj === null || obj === undefined) return null;
      if (Array.isArray(obj)) return obj.map(x => this.sanitizeParams(x));
      if (typeof obj !== 'object') return obj;
      const out = {};
      for (const k of Object.keys(obj)) {
        if (k === 'api_key' || k === 'sample_ids') continue;
        out[k] = this.sanitizeParams(obj[k]);
      }
      return out;
    },
    modelParams(m) {
      if (!m) return null;
      const out = {};
      if (m.api_protocol) out.api_protocol = m.api_protocol;
      if (m.base_url) out.base_url = m.base_url;
      return out;
    },
    flattenParams(obj, prefix = '') {
      const out = [];
      if (obj === null || obj === undefined) return out;
      if (Array.isArray(obj)) {
        obj.forEach((v, i) => { out.push(...this.flattenParams(v, prefix ? `${prefix}[${i}]` : `[${i}]`)); });
        return out;
      }
      if (typeof obj === 'object') {
        for (const k of Object.keys(obj)) {
          out.push(...this.flattenParams(obj[k], prefix ? `${prefix}.${k}` : k));
        }
        return out;
      }
      out.push({ key: prefix, value: obj });
      return out;
    },
    showTab(tab) {
      this.detail = null;
      this.activeTab = tab;
      this._saveTab(tab);
      this._clearDetail();
    },
    _headline(metrics) {
      const series = (metrics && metrics.series) || [];
      for (const s of series) if (s && s.role === 'headline') return s;
      return series[0] || null;
    },
    toggleCompareMode() {
      this.compareMode = !this.compareMode;
      if (!this.compareMode) { this.compareSelected = []; this.comparePanelOpen = false; }
    },
    runKey(r) { return r.benchmark + '/' + r.model + '/' + r.run_id; },
    isSelected(r) { return this.compareSelected.indexOf(this.runKey(r)) >= 0; },
    toggleSelectRun(r) {
      const k = this.runKey(r);
      const i = this.compareSelected.indexOf(k);
      if (i >= 0) this.compareSelected.splice(i, 1);
      else this.compareSelected.push(k);
    },
    startCompare() {
      const sel = this.runs.filter(r => this.isSelected(r));
      if (sel.length < 2) return;
      this.comparePanelOpen = true;
      this.compareLoading = true;
      this.compareData = [];
      Promise.all(sel.map(r =>
        fetch(`/api/runs/${encodeURIComponent(r.benchmark)}/${encodeURIComponent(r.model)}/${encodeURIComponent(r.run_id)}`)
          .then(x => x.ok ? x.json() : null)
          .then(d => ({ benchmark: r.benchmark, model: r.model, run_id: r.run_id, data: d }))
          .catch(() => ({ benchmark: r.benchmark, model: r.model, run_id: r.run_id, data: null }))
      ))
        .then(list => { this.compareData = list; this.compareLoading = false; })
        .catch(e => { console.error(e); this.compareLoading = false; });
    },
    closeCompare() { this.comparePanelOpen = false; },
    cmpMax(m) {
      let max = 0;
      for (const t of this.compareTasks) {
        const v = t.stats && t.stats[m.key];
        if (typeof v === 'number' && v > max) max = v;
      }
      return max;
    },
    cmpPct(t, m) {
      const v = t.stats && t.stats[m.key];
      if (typeof v !== 'number' || v <= 0) return 0;
      const max = this.cmpMax(m);
      return max > 0 ? Math.max(2, Math.round(v / max * 100)) : 0;
    },
    cmpFmt(t, m) {
      const v = t.stats && t.stats[m.key];
      if (v === null || v === undefined) return '—';
      switch (m.fmt) {
        case 'rate': return this.fmtRate(v);
        case 'duration': return this.fmtDuration(v);
        case 'seconds': return this.fmtSeconds(v);
        default: return this.fmtNumber(v);
      }
    },

    isReady(id) { return this.benchmarkStatus[id] === true; },
    loadBenchmarkStatus() {
      fetch('/api/benchmark-status').then(r => r.json()).then(d => { this.benchmarkStatus = d; });
    },
    downloadBenchmark(id) {
      this.downloadingId = id;
      fetch(`/api/benchmark/${encodeURIComponent(id)}/download`, { method: 'POST' })
        .then(r => r.json())
        .then(d => {
          if (d.ok) {
            this.benchmarkStatus[id] = true;
          } else {
            alert(`下载失败: ${d.error || '未知错误'}`);
          }
        })
        .catch(e => { alert('下载失败: ' + e); })
        .finally(() => { this.downloadingId = null; });
    },
    previewBenchmark(id) {
      this.previewTitle = id;
      this.previewData = null;
      this.previewLoading = true;
      this.showPreviewModal = true;
      fetch(`/api/benchmark/${encodeURIComponent(id)}/preview`)
        .then(r => r.json())
        .then(d => { this.previewData = d; })
        .catch(e => { this.previewData = { ok: false, error: String(e), tasks: [], total: 0 }; })
        .finally(() => { this.previewLoading = false; });
    },
    closePreviewModal() { this.showPreviewModal = false; },
    deleteBenchmark(id) {
      if (!confirm(`确认删除 ${id} 的数据？删除后需重新下载。`)) return;
      fetch(`/api/benchmark/${encodeURIComponent(id)}/data`, { method: 'DELETE' })
        .then(r => r.json())
        .then(d => {
          if (d.ok) {
            this.benchmarkStatus[id] = false;
          } else {
            alert('删除失败');
          }
        })
        .catch(e => { alert('删除失败: ' + e); });
    },
    loadComponents() {
      fetch('/api/components').then(r => r.json()).then(d => { this.components = d; });
    },
    loadRuns() {
      fetch('/api/runs').then(r => r.json()).then(d => { this.runs = d; });
    },
    refreshRuns() {
      this.refreshNotice = null;
      fetch('/api/runs')
        .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(d => {
          this.runs = d;
          this.refreshNotice = { ok: true, text: '刷新成功' };
        })
        .catch(e => {
          this.refreshNotice = { ok: false, text: '刷新失败：' + e.message };
        })
        .finally(() => {
          if (this._refreshTimer) clearTimeout(this._refreshTimer);
          this._refreshTimer = setTimeout(() => { this.refreshNotice = null; }, 3000);
        });
    },
    goToRunsPage(n) {
      this.runsPage = Math.max(1, Math.min(this.totalRunsPages, Number(n) || 1));
    },
    jumpToRunsPage() {
      const n = parseInt(this.runsJump, 10);
      if (!isNaN(n) && n >= 1) this.goToRunsPage(n);
      this.runsJump = '';
    },
    goToDetailPage(n) {
      this.detailPage = Math.max(1, Math.min(this.totalDetailPages, Number(n) || 1));
    },
    jumpToDetailPage() {
      const n = parseInt(this.detailJump, 10);
      if (!isNaN(n) && n >= 1) this.goToDetailPage(n);
      this.detailJump = '';
    },
    selectBenchmark(id) {
      this.selectedBenchmark = id;
      this.benchmarkDoc = null;
      this.benchmarkLoading = true;
      this.showBenchmarkModal = true;
      fetch(`/api/docs/benchmark/${encodeURIComponent(id)}`)
        .then(r => r.json())
        .then(d => {
          if (this.selectedBenchmark !== id) return;
          this.benchmarkDoc = d;
        })
        .catch(e => {
          if (this.selectedBenchmark !== id) return;
          console.error(e);
          this.benchmarkDoc = { found: false, content: '' };
        })
        .finally(() => {
          if (this.selectedBenchmark === id) this.benchmarkLoading = false;
        });
    },
    closeBenchmarkModal() {
      this.showBenchmarkModal = false;
    },
    closeHarnessModal() {
      this.showHarnessModal = false;
    },
    selectHarness(id) {
      this.selectedHarness = id;
      this.showHarnessModal = true;
      this.harnessDoc = null;
      this.harnessLoading = true;
      fetch(`/api/docs/harness/${encodeURIComponent(id)}`)
        .then(r => r.json())
        .then(d => {
          if (this.selectedHarness !== id) return;
          this.harnessDoc = d;
        })
        .catch(e => {
          if (this.selectedHarness !== id) return;
          console.error(e);
          this.harnessDoc = { found: false, content: '' };
        })
        .finally(() => {
          if (this.selectedHarness === id) this.harnessLoading = false;
        });
    },
    renderMarkdown(content) {
      if (!content) return '';
      let html;
      if (window.marked && typeof marked.parse === 'function') html = marked.parse(content);
      else html = content;
      // 文档站内链接（href 以 / 开头）本地无对应路由，降级为纯文本，避免点击 404
      return html.replace(/<a\s+href="(\/[^"]*)"[^>]*>([\s\S]*?)<\/a>/g, '$2');
    },
    renderAnalysisSummary(md) {
      if (!md) return '';
      const lines = md.split('\n');
      const prelude = [];
      let html = '';
      let top = null;
      let sub = null;
      const esc = (s) => this.escapeHtml(s);
      const closeSub = () => {
        if (sub && top) {
          top.html += `<details class="as-section as-sub"><summary>${esc(sub.title)}</summary><div class="as-body markdown">${this.renderMarkdown(sub.lines.join('\n'))}</div></details>`;
          sub = null;
        }
      };
      const closeTop = () => {
        closeSub();
        if (top) {
          html += `<details class="as-section"><summary>${esc(top.title)}</summary><div class="as-body markdown">${this.renderMarkdown(top.lines.join('\n'))}${top.html}</div></details>`;
          top = null;
        }
      };
      for (const line of lines) {
        if (line.startsWith('## ')) {
          closeTop();
          top = { title: line.replace(/^#+\s*/, '').trim(), lines: [], html: '' };
        } else if (line.startsWith('### ')) {
          closeSub();
          sub = { title: line.replace(/^#+\s*/, '').trim(), lines: [] };
        } else if (sub) {
          sub.lines.push(line);
        } else if (top) {
          top.lines.push(line);
        } else {
          prelude.push(line);
        }
      }
      closeTop();
      return this.renderMarkdown(prelude.join('\n')) + html;
    },
    paramValue(d) {
      const raw = this.runForm[d.key];
      if (d.type === 'json') {
        if (!raw || !String(raw).trim()) return null;
        try { return JSON.parse(raw); }
        catch (e) { throw new Error(`${d.flag} 不是合法 JSON`); }
      }
      if (d.type === 'bool') return !!raw;
      if (d.type === 'number') {
        if (raw === null || raw === undefined || raw === '') return null;
        const n = Number(raw);
        if (isNaN(n)) throw new Error(`${d.flag} 必须是数字`);
        if (d.min !== undefined && n < d.min) throw new Error(`${d.flag} 不能小于 ${d.min}`);
        if (d.max !== undefined && n > d.max) throw new Error(`${d.flag} 不能大于 ${d.max}`);
        return n;
      }
      const s = (raw === null || raw === undefined) ? '' : String(raw).trim();
      return s === '' ? null : s;
    },
    buildRunPayload() {
      const payload = {
        benchmark: this.runForm.benchmark,
        harness: this.runForm.harness,
        model: this.runForm.model,
      };
      for (const d of RUN_PARAM_DEFS) payload[d.key] = this.paramValue(d);
      return payload;
    },
    showHelp(d, event, popH) {
      const popW = 340;
      const h = popH || 150;
      let x = event.clientX + 12;
      let y = event.clientY + 12;
      if (x + popW > window.innerWidth - 8) x = window.innerWidth - popW - 8;
      if (y + h > window.innerHeight - 8) y = event.clientY - h - 12;
      if (y < 8) y = 8;
      this.helpPopover = { visible: true, flag: d.flag, text: d.help, x, y };
    },
    hideHelp() { this.helpPopover.visible = false; },
    groupHelpFor(group) {
      return GROUP_HELP[group] || null;
    },
    showGroupHelp(group, event) {
      const help = this.groupHelpFor(group);
      if (!help) return;
      this.showHelp({ flag: group, help }, event, 360);
    },
    validateRunForm() {
      const errors = [];
      if (!String(this.runForm.benchmark || '').trim()) errors.push('benchmark 必填');
      if (!String(this.runForm.harness || '').trim()) errors.push('harness 必填');
      if (!String(this.runForm.model || '').trim()) errors.push('model 必填');
      for (const d of RUN_PARAM_DEFS) {
        const raw = this.runForm[d.key];
        if (d.type === 'json') {
          if (!raw || !String(raw).trim()) continue;
          try { JSON.parse(raw); } catch (e) { errors.push(`${d.flag} 不是合法 JSON`); }
        } else if (d.type === 'number') {
          if (raw === null || raw === undefined || raw === '') continue;
          const n = Number(raw);
          if (isNaN(n)) { errors.push(`${d.flag} 必须是数字`); continue; }
          if (d.min !== undefined && n < d.min) errors.push(`${d.flag} 不能小于 ${d.min}`);
          if (d.max !== undefined && n > d.max) errors.push(`${d.flag} 不能大于 ${d.max}`);
        } else if (d.type === 'select') {
          if (raw && !d.options.includes(raw)) errors.push(`${d.flag} 值非法，可选：${d.options.join(' / ')}`);
        }
      }
      return errors;
    },
    validateCliCommand() {
      const errors = [];
      const cmd = String(this.cliCommand || '').trim();
      if (!cmd) { errors.push('命令不能为空'); return errors; }
      const tokens = cmd.split(/\s+/);
      const head = tokens[0];
      let rest;
      if (head === 'agentcompass') {
        if (tokens.length < 2 || tokens[1] !== 'run') { errors.push('命令必须以 agentcompass run 开头'); return errors; }
        rest = tokens.slice(2);
      } else if (head === 'python' || head === 'python3') {
        if (tokens.length < 4 || tokens[1] !== '-m' || tokens[2] !== 'agentcompass.cli' || tokens[3] !== 'run') {
          errors.push('命令必须以 python -m agentcompass.cli run 开头');
          return errors;
        }
        rest = tokens.slice(4);
      } else {
        errors.push('命令必须以 agentcompass run 或 python -m agentcompass.cli run 开头');
        return errors;
      }
      const positional = [];
      for (const t of rest) {
        if (t.startsWith('-')) break;
        positional.push(t);
      }
      if (positional.length < 3) errors.push(`缺少位置参数 benchmark/harness/model（当前 ${positional.length} 个）`);
      return errors;
    },
    openRunForm() { this.runValidation = null; this.startResult = null; this.showRunModal = true; },
    closeRunForm() { this.showRunModal = false; },
    openCliForm() { this.cliValidation = null; this.cliResult = null; this.showCliModal = true; },
    closeCliForm() { this.showCliModal = false; },
    previewRunCommand() {
      if (!this.runForm.benchmark || !this.runForm.harness || !this.runForm.model) {
        this.previewCommand = '';
        return;
      }
      let previewPayload;
      try { previewPayload = this.buildRunPayload(); }
      catch (e) { this.previewCommand = ''; return; }
      fetch('/api/runs/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(previewPayload),
      })
        .then(r => r.json())
        .then(d => { this.previewCommand = d.command || ''; })
        .catch(() => { this.previewCommand = ''; });
    },
    submitRun() {
      const errors = this.validateRunForm();
      if (errors.length) {
        this.runValidation = { pass: false, errors };
        return;
      }
      let runPayload;
      try { runPayload = this.buildRunPayload(); }
      catch (e) { this.runValidation = { pass: false, errors: [e.message] }; return; }
      this.runValidation = { pass: true, errors: [] };
      this.loading = true;
      fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(runPayload),
      })
        .then(r => r.json())
        .then(d => {
          if (d.started) {
            this.runValidation = null;
            this.startResult = d;
            this.loadRuns();
            this.startCompletionPolling();
          } else {
            this.startResult = { error: d.detail || '启动失败' };
          }
        })
        .catch(e => { this.startResult = { error: String(e) }; })
        .finally(() => { this.loading = false; });
    },
    submitCli() {
      const errors = this.validateCliCommand();
      if (errors.length) {
        this.cliValidation = { pass: false, errors };
        return;
      }
      this.cliValidation = { pass: true, errors: [] };
      this.cliLoading = true;
      fetch('/api/runs/cli', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: this.cliCommand }),
      })
        .then(r => r.json())
        .then(d => {
          if (d.started) {
            this.cliValidation = null;
            this.cliResult = d;
            this.loadRuns();
            this.startCompletionPolling();
          } else {
            this.cliResult = { error: d.detail || '启动失败' };
          }
        })
        .catch(e => { this.cliResult = { error: String(e) }; })
        .finally(() => { this.cliLoading = false; });
    },
    startCompletionPolling() {
      this.stopCompletionPolling();
      this.completionNotice = '';
      const before = new Set((this.runs || []).map(r => `${r.benchmark}/${r.model}/${r.run_id}`));
      const check = () => {
        fetch('/api/runs')
          .then(r => r.json())
          .then(runs => {
            this.runs = runs;
            const newRun = runs.find(r => !before.has(`${r.benchmark}/${r.model}/${r.run_id}`));
            if (newRun && (newRun.status === 'completed' || newRun.status === 'error' || newRun.status === 'failed')) {
              this.stopCompletionPolling();
              this.completionNotice = (newRun.status === 'completed')
                ? '测评已完成，结果见下方评测任务列表'
                : '测评已结束（有错误），详情见下方评测任务列表';
            }
          })
          .catch(() => {});
      };
      check();
      this.pollTimer = setInterval(check, 2000);
    },
    stopCompletionPolling() {
      if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
    },
    openDetail(run) {
      this.detail = { benchmark: run.benchmark, model: run.model, run_id: run.run_id, data: null };
      this.detailPage = 1;
      this._saveDetail();
      this._fetchDetailData();
    },
    _fetchDetailData() {
      const { benchmark, model, run_id } = this.detail || {};
      if (!benchmark || !model || !run_id) return;
      fetch(`/api/runs/${encodeURIComponent(benchmark)}/${encodeURIComponent(model)}/${encodeURIComponent(run_id)}`)
        .then(r => r.json())
        .then(d => { if (this.detail) this.detail.data = d; })
        .catch(e => { console.error(e); });
    },
    _saveDetail() {
      try {
        if (!this.detail) return;
        sessionStorage.setItem('ac.detail', JSON.stringify({
          benchmark: this.detail.benchmark, model: this.detail.model, run_id: this.detail.run_id,
        }));
      } catch (e) { /* ignore */ }
    },
    _clearDetail() {
      try { sessionStorage.removeItem('ac.detail'); } catch (e) { /* ignore */ }
    },
    _saveTab(tab) {
      try { sessionStorage.setItem('ac.activeTab', tab); } catch (e) { /* ignore */ }
    },
    closeDetail() { this.detail = null; this._clearDetail(); },
    openTaskDetail(t) {
      const { benchmark, model, run_id } = this.detail || {};
      this.taskDetailData = null;
      this.taskDetailLoading = true;
      this.showTaskDetailModal = true;
      fetch(`/api/runs/${encodeURIComponent(benchmark)}/${encodeURIComponent(model)}/${encodeURIComponent(run_id)}/details/${encodeURIComponent(t.task_id)}`)
        .then(r => r.json())
        .then(d => { this.taskDetailData = d; })
        .catch(e => { this.taskDetailData = { task_id: t.task_id, data: null, error: String(e) }; })
        .finally(() => { this.taskDetailLoading = false; });
    },
    closeTaskDetail() { this.showTaskDetailModal = false; },
    openAnalyzerHelp() { this.showAnalyzerHelp = true; },
    closeAnalyzerHelp() { this.showAnalyzerHelp = false; },
    escapeHtml(s) {
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    },
    renderJsonTree(value, name, depth) {
      const d = depth || 0;
      const label = (name === undefined || name === null || name === '') ? '' : this.escapeHtml(name);
      const keyPart = label !== '' ? `<span class="json-key">${label}</span><span class="json-colon">:</span> ` : '';
      if (value === null) {
        return `<div class="json-row">${keyPart}<span class="json-null">null</span></div>`;
      }
      if (Array.isArray(value)) {
        const open = d < 1 && value.length <= 20;
        const inner = value.map((v, i) => this.renderJsonTree(v, String(i), d + 1)).join('');
        return `<details${open ? ' open' : ''}><summary>${keyPart}<span class="json-meta">Array(${value.length})</span></summary><div class="json-children">${inner}</div></details>`;
      }
      if (typeof value === 'object') {
        const keys = Object.keys(value);
        const open = d < 1 && keys.length <= 20;
        const inner = keys.map(k => this.renderJsonTree(value[k], k, d + 1)).join('');
        return `<details${open ? ' open' : ''}><summary>${keyPart}<span class="json-meta">Object(${keys.length})</span></summary><div class="json-children">${inner}</div></details>`;
      }
      const isStr = typeof value === 'string';
      const valCls = isStr ? 'json-val json-str' : 'json-val';
      const val = isStr ? this.escapeHtml(value) : this.escapeHtml(String(value));
      return `<div class="json-row">${keyPart}<span class="${valCls}">${val}</span></div>`;
    },

    statusTagClass(s) {
      s = String(s || '').toLowerCase();
      if (s === 'completed' || s === 'success') return 'correct';
      if (s === 'error' || s === 'failed' || s === 'run_error') return 'incorrect';
      if (s === 'running' || s === 'in_progress') return 'error';
      return '';
    },
    fmtRate(v) { return v === null || v === undefined ? '—' : (v * 100).toFixed(1) + '%'; },
    fmtProgress(r) {
      const t = r.total_tasks, f = r.finished_tasks;
      if (t === null || t === undefined || f === null || f === undefined) return '—';
      if (t <= 0) return '—';
      return `${f} / ${t}`;
    },
    fmtSeconds(v) {
      if (v === null || v === undefined) return '—';
      return Number(v).toFixed(2) + 's';
    },
    fmtDuration(v) {
      if (v === null || v === undefined) return '—';
      const s = Math.round(Number(v));
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      if (h > 0) return `${h}h ${m}m ${sec}s`;
      if (m > 0) return `${m}m ${sec}s`;
      return `${sec}s`;
    },
    fmtNumber(v) {
      if (v === null || v === undefined) return '—';
      return Number(v).toLocaleString();
    },
    fmtTime(iso) {
      if (!iso) return '—';
      const d = new Date(iso);
      return isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN', { hour12: false });
    },
    totalOf(tokens) {
      if (!tokens) return null;
      const keys = ['input_tokens', 'output_tokens', 'reasoning_output_tokens'];
      return keys.reduce((sum, k) => sum + (typeof tokens[k] === 'number' ? tokens[k] : 0), 0);
    },
  },

  watch: {
    runForm: {
      deep: true,
      handler() {
        clearTimeout(this._previewTimer);
        this._previewTimer = setTimeout(() => this.previewRunCommand(), 300);
      },
    },
    runs() {
      if (this.runsPage > this.totalRunsPages) this.runsPage = this.totalRunsPages;
    },
  },

  mounted() {
    this.loadComponents();
    this.loadBenchmarkStatus();
    this.loadRuns();
    if (this.detail) this._fetchDetailData();
  },
}).mount('#app');
