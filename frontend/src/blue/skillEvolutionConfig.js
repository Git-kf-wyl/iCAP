export const outputKinds = [
  { key: 'word', name: '关键词', description: '用例 data 中的 whitelist 必须命中，blacklist 不得命中。' },
  { key: 'format', name: 'JSON 格式', description: '依据用例的格式示例校验结构；data 为空时使用下方统一示例。' },
  { key: 'onlyllm', name: 'Rubric 评审', description: 'data 是评审规则文件路径。上传该文件并关联任务，由评审模型读取规则。' },
  { key: 'text', name: '文本结果', description: '对照 data 中的期望文本评审模型输出。' },
  { key: 'tool', name: '工具结果', description: '对照 data 中序列化的工具结果或目标状态进行评审。' },
  { key: 'file', name: '文件结果', description: '使用 expect_path 指向期望文本文件；Hermes 的 actual_path 是用例工作目录内的产物路径。' },
  { key: 'device_state', name: '表格 / 设备状态', description: 'Spreadsheet 使用 J23=January 等期望单元格值，读取实际生成的 output.xlsx 验证。' },
]
const weights = (active) => Object.fromEntries(outputKinds.map(k => [k.key, active.includes(k.key) ? 1 : 0]))
export const identityFormat = '[{"topic":"个人身份","subtopic":"姓名","details":"用户的名字是林月"}]'
export const presets = [
  { id: 'rewrite', name: '改写 / 记忆关键词 · 单 API', execution_mode: 'direct', judgment_weights: { process: 0, conciseness: 0, result: 1 }, output_weights: weights(['word', 'format']), format_example: identityFormat, description: '关键词约束 + JSON 结构校验。统一格式示例需按业务修改。' },
  { id: 'memory', name: '记忆 · 文本 / 工具结果 · 单 API', execution_mode: 'direct', judgment_weights: { process: 0, conciseness: 0, result: 1 }, output_weights: weights(['text', 'tool']), format_example: '', description: '对照预期文本和工具状态评审；单 API 只计算结果分，不使用 Agent 过程分。' },
  { id: 'memory_rubric', name: '记忆 · Rubric 评审 · 单 API', execution_mode: 'direct', judgment_weights: { process: 0, conciseness: 0, result: 1 }, output_weights: weights(['onlyllm']), format_example: '', description: '用例 onlyllm.data 指向上传的 Rubric 文件，不能把文件路径当作标准答案。' },
  { id: 'spreadsheet', name: 'Spreadsheet · Hermes', execution_mode: 'hermes', judgment_weights: { process: 0.4, conciseness: 0.2, result: 0.4 }, output_weights: weights(['device_state']), format_example: '', description: '上传原始工作簿或 ZIP，复制服务器路径至 input_path，再关联文件；Agent 实际生成 output.xlsx 并校验单元格。' },
  { id: 'custom', name: '自定义配置', description: '保留当前设置，自行调整执行方式、各类权重和优化参数。' },
]
export function applyPreset(form, id) {
  const preset = presets.find(p => p.id === id)
  if (!preset) throw new Error('未知业务模式')
  form.preset = id
  if (id !== 'custom') for (const key of ['execution_mode', 'judgment_weights', 'output_weights', 'format_example']) form[key] = structuredClone(preset[key])
  return form
}
export function parseDataset(text) {
  const result = JSON.parse(text)
  if (!Array.isArray(result) || !result.length) throw new Error('数据集须是非空 JSON 用例数组')
  if (result.length > 10000) throw new Error('单个任务最多 10,000 条用例')
  return result
}
const envFields = {
  SELF_EVOLVE_CASES_LIMIT: 'cases_limit', SELF_EVOLVE_ROUNDS: 'rounds', SELF_EVOLVE_MAX_ROUNDS: 'rounds',
  SELF_EVOLVE_THRESHOLD: 'threshold', SELF_EVOLVE_MAX_EDITS: 'max_edits',
  SELF_EVOLVE_MAX_MODEL_CALLS: 'max_model_calls', MAX_MODEL_CALLS: 'max_model_calls',
  SELF_EVOLVE_RESULT_THRESHOLD: 'result_threshold', SELF_EVOLVE_OUTCOME_SPLIT_THRESHOLD: 'outcome_split_threshold',
  SELF_EVOLVE_STALL_THRESHOLD: 'stall_threshold', SELF_EVOLVE_STALL_ROUNDS: 'stall_rounds',
  SELF_EVOLVE_EXPLORATION_ITERATIONS: 'exploration_iterations', SELF_EVOLVE_SUCCESS_CASE_LIMIT: 'success_case_limit', SELF_EVOLVE_FAILURE_CASE_LIMIT: 'failure_case_limit',
  MAX_TOKENS: 'max_tokens', TEMPERATURE: 'temperature', TIMEOUT: 'timeout',
  JUDGMENT_WEIGHT_PROCESS: 'judgment_weights.process', JUDGMENT_WEIGHT_CONCISENESS: 'judgment_weights.conciseness', JUDGMENT_WEIGHT_RESULT: 'judgment_weights.result',
  ...Object.fromEntries(outputKinds.map(k => [`OUTPUT_WEIGHT_${k.key.toUpperCase()}`, `output_weights.${k.key}`])),
}
export function importParameters(text, form) {
  const next = JSON.parse(JSON.stringify(form)), ignored = [], applied = []
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Z_0-9]+)\s*=\s*(.*?)\s*$/)
    if (!match) continue
    const [, name] = match
    let value = match[2]
    if (/^(['"]).*\1$/.test(value)) value = value.slice(1, -1)
    else value = value.replace(/\s+#.*$/, '').trim()
    if (name === 'OUTPUT_FORMAT_EXAMPLE') { if (value) JSON.parse(value); next.format_example = value; applied.push(name); continue }
    const path = envFields[name]
    if (!path) { ignored.push(name); continue }
    const number = value === '' && path === 'cases_limit' ? null : Number(value)
    if ((value === '' && path !== 'cases_limit') || (number !== null && !Number.isFinite(number))) throw new Error(`${name} 必须为数字`)
    const [parent, child] = path.split('.')
    if (child) next[parent][child] = number
    else next[parent] = number
    applied.push(name)
  }
  if (next.execution_mode === 'direct') next.judgment_weights = { process: 0, conciseness: 0, result: 1 }
  next.preset = 'custom'
  return { form: next, ignored, applied }
}
