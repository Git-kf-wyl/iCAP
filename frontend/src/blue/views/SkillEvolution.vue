<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, downloadFile } from '../api'
import EChart from '../components/EChart.vue'
import SkillEvolutionCreate from '../components/SkillEvolutionCreate.vue'
import SkillFileManager from '../components/SkillFileManager.vue'
import VisibilityTag from '../components/VisibilityTag.vue'
import { useAuth } from '../stores/auth'

const route = useRoute(), router = useRouter(), auth = useAuth()
const jobs = ref([]), capabilities = ref({ models: [], execution_modes: ['direct'] })
const selected = ref(null), dialog = ref(false), busy = ref(false), loading = ref(false), tab = ref('results')
const workspaceTab = ref('tasks'), createOperation = ref('evolve'), initialSkill = ref('')
let timer, polling = false, stopped = false
const names = { queued: '等待执行', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消', interrupted: '已中断' }
const operations = { evolve: '迭代优化', evaluate: '仅测评', bootstrap: '生成初版' }
const active = computed(() => jobs.value.filter(j => ['queued', 'running'].includes(j.status)).length)
const rounds = computed(() => selected.value?.result?.rounds || [])
const activeRound = ref('')
const round = computed(() => rounds.value.find(r => String(r.index) === activeRound.value) || rounds.value.at(-1))
const canManage = computed(() => selected.value && (auth.role === 'admin' || selected.value.owner_user_id === auth.userId))
const chart = computed(() => ({ tooltip: { trigger: 'axis' }, grid: { top: 22, left: 40, right: 22, bottom: 30 },
  xAxis: { type: 'category', data: rounds.value.filter(r => r.score != null).map(r => `第 ${r.index} 轮`) },
  yAxis: { type: 'value', min: 0, max: 100 }, series: [{ type: 'line', smooth: false, symbolSize: 8,
    data: rounds.value.filter(r => r.score != null).map(r => r.score), lineStyle: { color: '#5375ed', width: 3 },
    itemStyle: { color: '#5375ed' }, areaStyle: { color: 'rgba(83,117,237,.08)' },
    markLine: { silent: true, symbol: 'none', data: [{ yAxis: selected.value?.config?.threshold || 85, label: { formatter: '目标' } }] } }] }))

function statusType(status) { return status === 'completed' ? 'success' : ['failed', 'cancelled', 'interrupted'].includes(status) ? 'danger' : 'warning' }
function score(value) { return value == null ? '—' : Number(value).toFixed(1) }
function date(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—' }
function openCreate(operation = 'evolve') { createOperation.value = operation; initialSkill.value = ''; dialog.value = true }
async function created(row) { workspaceTab.value = 'tasks'; await choose(row); await load() }
async function load() {
  if (polling || stopped) return
  polling = true
  try {
    jobs.value = await api.get('/skill-evolution/jobs', { silentError: true })
    const id = selected.value?.id || route.query.job || jobs.value[0]?.id
    if (id) selected.value = await api.get(`/skill-evolution/jobs/${id}`, { silentError: true })
  } catch { /* keep the last successful snapshot during a temporary disconnection */ }
  finally { polling = false; loading.value = false }
}
async function choose(job) { selected.value = await api.get(`/skill-evolution/jobs/${job.id}`); activeRound.value = ''; router.replace({ query: { job: job.id } }); tab.value = 'results' }
async function action(command) {
  busy.value = true
  try { selected.value = await api.post(`/skill-evolution/jobs/${selected.value.id}/${command}`); await load() }
  finally { busy.value = false }
}
async function copyPath(path) { try { await navigator.clipboard.writeText(path); ElMessage.success('任务目录已复制') } catch { ElMessage.info('请选中目录文字手动复制') } }
async function download(name) {
  try { await downloadFile(`/skill-evolution/jobs/${selected.value.id}/artifacts/${name}`, `${selected.value.name}-${name}`) }
  catch (error) { ElMessage.error(error.message) }
}
function reuse() { createOperation.value = 'evolve'; initialSkill.value = selected.value?.result?.optimized_skill || ''; dialog.value = true }
onMounted(async () => {
  try { capabilities.value = await api.get('/skill-evolution/capabilities') } catch { /* existing records remain available */ }
  loading.value = true; await load(); timer = setInterval(load, 5000)
})
onUnmounted(() => { stopped = true; clearInterval(timer) })
</script>

<template>
  <div class="page-heading">
    <div><h1>Skill 自进化</h1><p class="subtitle">用真实业务用例衡量效果，让 Skill 在执行、评审与改写中持续改进。</p></div>
    <div class="workspace-actions"><el-button :type="workspaceTab==='files' ? 'primary' : 'default'" plain @click="workspaceTab=workspaceTab==='files' ? 'tasks' : 'files'">{{ workspaceTab==='files' ? '返回任务' : '文件管理' }}</el-button><el-button type="primary" @click="openCreate('evolve')">＋ 启动自进化</el-button></div>
  </div>
  <div class="pipeline" aria-label="Skill 工作流水线">
    <button type="button" :class="{current:createOperation==='bootstrap' && dialog}" @click="openCreate('bootstrap')"><span class="stage-number">01</span><div><strong>生成 Skill</strong><p>业务场景 · 参考文件 · 脚本</p><small>输出 Skill.md 初稿</small></div><span class="stage-action">开始 →</span></button>
    <button type="button" :class="{current:workspaceTab==='data'}" @click="workspaceTab='data'"><span class="stage-number">02</span><div><strong>生成数据 <em>规划中</em></strong><p>Skill · 种子用例 · 测评工程</p><small>输出配比后的数据</small></div></button>
    <button type="button" :class="{current:workspaceTab==='tasks'}" @click="workspaceTab='tasks'; openCreate('evolve')"><span class="stage-number">03</span><div><strong>自进化</strong><p>Skill.md · 优化训练数据集</p><small>输出优化后的 Skill.md</small></div><span class="stage-action">开始 →</span></button>
    <div class="future-stage"><span class="stage-number">04</span><div><strong>第三方测评 <em>规划中</em></strong><p>独立测评数据集</p><small>输出测评报告</small></div></div>
  </div>
  <section v-if="workspaceTab==='files'" class="card"><SkillFileManager /></section>
  <section v-else-if="workspaceTab==='data'" class="card data-placeholder"><h2>数据工程</h2><p>此模块预留：根据 Skill 内容、种子数据的维度与用例，以及业务测评工程，生成并配比优化数据。</p><p>当前可以在文件库管理已有的数据集，再进入自进化使用。</p><el-button @click="workspaceTab='files'">管理已有文件</el-button><el-button type="primary" @click="openCreate('evolve')">使用已有数据开始自进化</el-button></section>
  <template v-else>
  <div class="evo-stats">
    <div><span class="muted">任务总数</span><strong>{{ jobs.length }}</strong></div>
    <div><span class="muted">执行中／等待中</span><strong>{{ active }}</strong></div>
    <div><span class="muted">已完成</span><strong>{{ jobs.filter(j => j.status === 'completed').length }}</strong></div>
    <div class="stats-note"><span class="signal" /><span>两套真实优化引擎<br><small class="muted">A · 受控迭代　B · 自适应进阶</small></span></div>
  </div>
  <div v-if="!jobs.length && !loading" class="card welcome">
    <div class="welcome-icon">⟳</div><h2>让业务经验成为更好的 Skill</h2><p class="muted">上传 SKILL.md 和测评用例，选择优化引擎，追踪每一轮的效果和改动。</p>
    <div class="welcome-flow"><span>① 准备 Skill 与用例</span><b>→</b><span>② 执行与评审</span><b>→</b><span>③ 提炼经验、迭代改写</span><b>→</b><span>④ 下载最佳 Skill</span></div>
    <el-button type="primary" @click="openCreate('evolve')">创建第一个任务</el-button>
  </div>
  <div v-else class="evo-layout" v-loading="loading">
    <aside class="card job-list">
      <div class="list-head"><h3>任务记录</h3><el-button text @click="load">刷新</el-button></div>
      <button v-for="job in jobs" :key="job.id" class="job-item" :class="{ selected: selected?.id === job.id }" @click="choose(job)">
        <div class="job-title"><strong>{{ job.name }}</strong><el-tag size="small" :type="statusType(job.status)">{{ names[job.status] }}</el-tag></div>
        <div class="job-meta">{{ job.engine === 'opt' ? 'A · 业务推荐' : 'B · 进阶' }} · {{ operations[job.operation] }} · {{ job.case_count }} 条</div>
        <div class="job-bottom"><span>{{ date(job.created_at) }}</span><b v-if="job.result?.best_score != null">{{ score(job.result.best_score) }} 分</b></div>
        <el-progress v-if="['running','queued'].includes(job.status)" :percentage="job.progress" :stroke-width="3" :show-text="false" />
      </button>
    </aside>
    <section v-if="selected" class="job-detail">
      <div class="card detail-header">
        <div class="detail-title"><div><h2>{{ selected.name }}</h2><div class="job-meta">{{ selected.engine === 'opt' ? 'A · Outcome-Partitioned Tuning' : 'B · 自适应进阶优化' }} · {{ operations[selected.operation] }} · {{ selected.execution_mode === 'direct' ? '单 API 执行' : 'Hermes Agent' }}</div></div><VisibilityTag :visibility="selected.visibility" /></div>
        <div class="run-status"><el-tag :type="statusType(selected.status)">{{ names[selected.status] }}</el-tag><span>{{ selected.phase || '等待任务执行' }}</span><span class="muted">模型调用 {{ selected.model_calls }} / {{ selected.config?.max_model_calls }}</span></div>
        <div v-if="selected.workspace_path" class="workspace-path"><span>任务目录</span><code>{{ selected.workspace_path }}</code><el-button link type="primary" @click="copyPath(selected.workspace_path)">复制</el-button></div>
        <el-progress v-if="['running','queued'].includes(selected.status)" :percentage="selected.progress" :stroke-width="7" />
        <el-alert v-if="selected.error" :title="selected.error" type="error" :closable="false" show-icon />
        <div class="detail-actions">
          <el-button v-if="canManage && ['queued','running'].includes(selected.status)" type="danger" plain :loading="busy" @click="action('cancel')">取消任务</el-button>
          <el-button v-if="canManage && ['failed','interrupted','cancelled'].includes(selected.status)" :loading="busy" @click="action('resume')">从断点续跑</el-button>
          <el-button v-if="selected.result?.optimized_skill" type="primary" @click="download('optimized_skill.md')">下载最佳 Skill</el-button>
          <el-button v-if="selected.status === 'completed'" @click="download('artifacts.zip')">下载结果包</el-button>
          <el-button v-if="selected.result?.optimized_skill" text @click="reuse">基于此版本新建</el-button>
        </div>
      </div>
      <div class="card result-card">
        <el-tabs v-model="tab">
          <el-tab-pane label="效果与用例" name="results">
            <div v-if="selected.operation === 'bootstrap'" class="empty">{{ selected.status === 'completed' ? '初版 Skill 已生成，请打开「最佳 Skill」查看或下载。' : '正在根据业务需求生成 Skill…' }}</div>
            <template v-else>
              <div class="score-cards"><div><span>初始评分</span><strong>{{ score(selected.result?.initial_score) }}</strong></div><div><span>历史最佳</span><strong class="best-score">{{ score(selected.result?.best_score) }}</strong></div><div><span>最新轮次</span><strong>{{ selected.current_round || rounds.length }}<small> / {{ selected.operation === 'evaluate' ? 1 : selected.config?.rounds }}</small></strong></div></div>
              <EChart v-if="rounds.some(r => r.score != null)" :option="chart" style="height:220px" />
              <div v-else class="chart-placeholder">完成首轮评审后，这里会展示评分曲线。</div>
              <div class="round-heading"><h3>逐用例结果</h3><el-select v-if="rounds.length" v-model="activeRound" placeholder="最新轮次" style="width:150px"><el-option v-for="r in rounds" :key="r.index" :label="`第 ${r.index} 轮 · ${score(r.score)} 分`" :value="String(r.index)" /></el-select></div>
              <el-table :data="round?.cases || []" empty-text="用例完成后将显示执行输出和评审依据" row-key="id">
                <el-table-column type="expand"><template #default="{ row }"><div class="case-detail"><h4>模型输出</h4><pre>{{ row.output || '无输出' }}</pre><h4>评审反馈</h4><pre>{{ row.feedback || JSON.stringify(row.analysis, null, 2) }}</pre><template v-if="row.trajectory?.length"><h4>Hermes 执行轨迹 · {{ row.trajectory.length }} 步</h4><ol class="trajectory"><li v-for="(step,i) in row.trajectory" :key="i"><strong>{{ step.tool_name || {user_request:'用户输入',assistant_response:'Agent 回答',assistant_tool_request:'工具请求',tool_result:'工具返回'}[step.action_type] || step.role }}</strong><small class="muted"> · {{ step.action_type }}</small><pre>{{ step.tool_input || step.tool_output || step.content || '—' }}</pre></li></ol></template><template v-if="row.large_output"><h4>对照大模型输出</h4><pre>{{ row.large_output }}</pre><details v-if="row.large_trajectory?.length"><summary>对照模型执行轨迹（{{ row.large_trajectory.length }} 步）</summary><pre>{{ JSON.stringify(row.large_trajectory, null, 2) }}</pre></details></template><template v-if="row.knowledge && Object.keys(row.knowledge).length"><h4>提炼知识与证据</h4><pre>{{ JSON.stringify(row.knowledge, null, 2) }}</pre></template><el-alert v-if="row.error" :title="row.error" type="error" :closable="false" /></div></template></el-table-column>
                <el-table-column prop="id" label="用例" width="105" /><el-table-column label="得分" width="80"><template #default="{ row }">{{ score(row.score) }}</template></el-table-column>
                <el-table-column v-if="selected.execution_mode === 'hermes'" label="过程 / 简洁 / 结果" min-width="145"><template #default="{ row }">{{ score(row.process_score) }} / {{ score(row.conciseness_score) }} / {{ score(row.result_score) }}</template></el-table-column>
                <el-table-column label="分类" width="120"><template #default="{ row }"><el-tag size="small" :type="row.route === 'SUCCESS' ? 'success' : row.route === 'KNOWLEDGE' ? 'primary' : 'warning'">{{ {SUCCESS:'成功',FAILURE:'待改进',KNOWLEDGE:'可提炼知识',INVALID:'无效'}[row.route] || row.route }}</el-tag></template></el-table-column>
                <el-table-column label="输出摘要" min-width="150"><template #default="{ row }"><span class="output-summary">{{ row.error || row.output || '—' }}</span></template></el-table-column>
              </el-table>
            </template>
          </el-tab-pane>
          <el-tab-pane label="最佳 Skill" name="skill"><pre v-if="selected.result?.optimized_skill" class="skill-preview">{{ selected.result.optimized_skill }}</pre><div v-else class="empty">任务完成后可查看历史最佳 Skill。</div></el-tab-pane>
          <el-tab-pane label="经验与演进" name="experience"><div v-if="selected.engine === 'opt'" class="field-hint">A 引擎保存成功／失败分组经验及拒绝反馈；B 还维护跨轮经验池和对照知识。</div><pre class="skill-preview">{{ JSON.stringify(selected.result?.experience_pool && Object.keys(selected.result.experience_pool).length ? selected.result.experience_pool : rounds.map(r=>({round:r.index,experience:r.experience})), null, 2) }}</pre><h3 v-if="selected.result?.lineage?.length">版本演进</h3><pre v-if="selected.result?.lineage?.length" class="skill-preview">{{ JSON.stringify(selected.result.lineage, null, 2) }}</pre></el-tab-pane>
          <el-tab-pane label="运行日志" name="logs"><pre class="run-logs">{{ selected.logs?.join('\n') || '等待日志…' }}</pre></el-tab-pane>
          <el-tab-pane label="生效配置" name="config"><div class="field-hint">API 凭据由后端按模型引用加载。A、B 的最佳版本与最后版本分别保存。</div><pre class="skill-preview">{{ JSON.stringify(selected.config, null, 2) }}</pre></el-tab-pane>
        </el-tabs>
      </div>
    </section>
  </div>

  </template>
  <SkillEvolutionCreate v-model="dialog" :operation="createOperation" :capabilities="capabilities" :initial-skill="initialSkill" @created="created" />
</template>

<style scoped>
.evo-stats{display:grid;grid-template-columns:repeat(3,1fr) 1.6fr;gap:24px;padding:20px 26px;background:#fff;border:1px solid #e9edf4;border-radius:14px;margin-bottom:22px}.evo-stats>div{display:flex;flex-direction:column;gap:8px}.evo-stats strong{font-size:27px;line-height:1.2}.evo-stats .stats-note{flex-direction:row;align-items:center;justify-content:flex-end;line-height:1.8}.evo-layout{display:grid;grid-template-columns:300px minmax(0,1fr);gap:20px;align-items:start}.job-list{padding:0;max-height:820px;overflow:auto}.list-head{padding:14px 18px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #eef1f7}.list-head h3{margin:0}.job-item{display:block;width:100%;text-align:left;border:0;border-bottom:1px solid #eef1f7;background:#fff;cursor:pointer;padding:18px 16px;border-left:3px solid transparent;color:inherit;font:inherit}.job-item:hover{background:#fafbff}.job-item.selected{background:#f1f5ff;border-left-color:#5375ed}.job-title{display:flex;gap:10px;align-items:center;justify-content:space-between}.job-title strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:175px}.job-meta{font-size:12px;color:#7b869b;margin:8px 0;line-height:1.6}.job-bottom{font-size:11px;color:#8d97a8;display:flex;justify-content:space-between;gap:8px;margin-bottom:8px}.job-bottom b{color:#5375ed}.job-detail{display:flex;flex-direction:column;gap:18px;min-width:0}.detail-header{padding:24px}.detail-title{display:flex;justify-content:space-between;gap:15px}.detail-title h2{margin:0;font-size:22px}.run-status{display:flex;align-items:center;gap:12px;margin:16px 0;flex-wrap:wrap;font-size:13px}.detail-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.detail-actions .el-button+.el-button{margin-left:0}.result-card{padding:10px 22px 24px}.score-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin:12px 0}.score-cards>div{background:#f7f9fd;border-radius:10px;padding:17px;display:flex;flex-direction:column;gap:9px}.score-cards span{font-size:12px;color:#8290a5}.score-cards strong{font-size:30px}.score-cards small{font-size:14px;color:#94a0b2}.best-score{color:#4f73e5}.chart-placeholder{padding:60px 0;text-align:center;color:#9aa6b8;border:1px dashed #e3e8f1;border-radius:10px;margin:18px 0}.round-heading{display:flex;align-items:center;justify-content:space-between;margin:15px 0}.round-heading h3{margin:0;font-size:15px}.output-summary{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;color:#657189}.case-detail{padding:4px 24px 20px;background:#fafbfe}.case-detail h4{margin:12px 0 8px}.case-detail pre,.skill-preview{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fc;padding:18px;border-radius:10px;max-height:650px;overflow:auto;font-size:13px;line-height:1.8;color:#34425a}.run-logs{white-space:pre-wrap;overflow-wrap:anywhere;background:#172237;color:#dce6f7;padding:20px;border-radius:10px;height:480px;overflow:auto;font:12px/1.8 Consolas,monospace}.engine-picker{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:2px 0 24px}.engine-picker button{text-align:left;border:1px solid #dfe5ef;border-radius:12px;background:white;padding:18px;cursor:pointer;color:#52617a}.engine-picker button.chosen{border:2px solid #5578eb;background:#f5f8ff;padding:17px}.engine-picker button>div{display:flex;justify-content:space-between;font-size:16px;color:#213653}.engine-picker p{line-height:1.7;font-size:13px;margin:10px 0}.engine-picker small{font-size:11px;color:#8190a8}.input-toolbar,.upload-label{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px}.upload-label{font-size:13px;color:#53627a}.file-button{display:inline-flex;cursor:pointer;border:1px solid #dbe2ef;border-radius:6px;padding:6px 10px;color:#5272d8;font-size:12px;background:white}.file-button input{display:none}.model-fields{margin-top:18px}.resource-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.call-settings{margin-top:20px}.weight-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.weight-grid .el-input-number{width:100%}.welcome{text-align:center;padding:55px 25px}.welcome-icon{font-size:42px;color:#5276ec}.welcome h2{margin-top:12px}.welcome-flow{display:flex;gap:12px;justify-content:center;margin:30px 0;font-size:13px;color:#5f7090;flex-wrap:wrap}.welcome-flow b{color:#bcc7d8}.form-grid .el-select{width:100%}.evo-dialog .el-collapse{margin:10px 0}.field-hint{font-size:12px;color:#8793a8;line-height:1.8;margin-top:7px}
@media(max-width:1100px){.evo-layout{grid-template-columns:250px minmax(0,1fr)}.evo-stats{grid-template-columns:repeat(3,1fr)}.stats-note{display:none!important}}@media(max-width:760px){.evo-layout{grid-template-columns:1fr}.job-list{max-height:260px}.engine-picker{grid-template-columns:1fr}.weight-grid{grid-template-columns:1fr 1fr}.evo-stats{gap:14px;padding:18px}.score-cards{gap:8px}.score-cards>div{padding:12px}.score-cards strong{font-size:25px}.result-card{padding:8px 12px}.detail-header{padding:18px}}

.workspace-path{display:flex;align-items:center;gap:10px;font-size:12px;margin:12px 0;color:#909399}.workspace-path code{overflow-wrap:anywhere;user-select:all}.workspace-actions{display:flex;gap:10px}.pipeline{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0 22px}.pipeline>button,.future-stage{display:flex;gap:12px;padding:17px 13px;background:#fff;border:1px solid #dcdfe6;border-radius:4px;text-align:left;position:relative;min-height:133px;color:#303133}.pipeline>button{cursor:pointer;font:inherit}.pipeline>button:hover,.pipeline>button.current{border-color:#409eff;background:#ecf5ff}.stage-number{font-size:21px;font-weight:600;color:#a8abb2}.pipeline strong{font-size:15px}.pipeline p{font-size:12px;line-height:1.6;margin:10px 0 6px;color:#606266}.pipeline small{color:#909399;font-size:11px}.pipeline em{font-size:10px;font-style:normal;background:#f0f2f5;color:#909399;padding:3px 5px;margin-left:4px}.stage-action{position:absolute;bottom:10px;right:12px;font-size:11px;color:#409eff}.future-stage{background:#fafafa;color:#909399}.data-placeholder{padding:35px!important}.data-placeholder p{color:#909399;font-size:14px;line-height:1.9}.evo-stats{border-radius:4px}.detail-header,.score-cards>div,.job-list{border-radius:4px}.trajectory{padding-left:18px}.trajectory pre{max-height:250px;overflow:auto}
@media(max-width:1250px){.pipeline{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:650px){.pipeline{grid-template-columns:1fr}.pipeline>button,.future-stage{min-height:110px}.workspace-path{display:flex;align-items:center;gap:10px;font-size:12px;margin:12px 0;color:#909399}.workspace-path code{overflow-wrap:anywhere;user-select:all}.workspace-actions{flex-wrap:wrap}}
</style>
