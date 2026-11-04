<script setup>
import {ref,onMounted,onUnmounted,reactive} from 'vue'
import {ElMessage} from 'element-plus'
import {api} from '../blue/api'
import './blue-features.css'
const models=ref([]),datasets=ref([]),benchmarks=ref({}),enabled=ref(false),rows=ref([]),creating=ref(false),detail=ref(null)
const form=reactive({model_id:'',dataset_id:'',benchmark:'Dev',visibility:'private'})
let timer
async function load(){const [m,d,b,t]=await Promise.all([api.get('/models'),api.get('/datasets'),api.get('/agent-benchmarks'),api.get('/evaluations')]);models.value=m;datasets.value=d;benchmarks.value=b.benchmarks;enabled.value=b.enabled;rows.value=t.filter(row=>row.benchmark in b.benchmarks);if(detail.value)detail.value=rows.value.find(row=>row.id===detail.value.id)||detail.value}
async function create(){if(!form.model_id||!form.dataset_id)return ElMessage.warning('请选择模型和资源');creating.value=true;try{await api.post('/evaluations',form);ElMessage.success('任务已提交');await load()}finally{creating.value=false}}
async function action(row,action){await api.patch('/evaluations/'+row.id,{action});await load()}
onMounted(async()=>{await load();timer=setInterval(load,5000)});onUnmounted(()=>clearInterval(timer))
</script>
<template><section class="blue-feature"><div class="page-heading"><div><h1>AgentCompass 测评</h1><p class="subtitle">复用平台模型连接，运行 Agent 基准并查看任务日志与结果。</p></div><el-tag :type="enabled?'success':'info'">{{enabled?'执行环境已启用':'执行环境尚未启用'}}</el-tag></div>
<el-alert v-if="!enabled" title="当前服务保留 AgentCompass 接口和历史任务；管理员启用执行环境后可提交新任务。" type="info" :closable="false"/>
<section class="card"><el-form label-position="top" class="form-grid"><el-form-item label="模型"><el-select v-model="form.model_id"><el-option v-for="row in models" :key="row.id" :value="row.id" :label="row.name"/></el-select></el-form-item><el-form-item label="基准"><el-select v-model="form.benchmark"><el-option v-for="(row,id) in benchmarks" :key="id" :value="id" :label="row.benchmark+' · '+row.harness"/></el-select></el-form-item><el-form-item label="关联资源"><el-select v-model="form.dataset_id"><el-option v-for="row in datasets" :key="row.id" :value="row.id" :label="row.name"/></el-select></el-form-item><el-form-item label="可见范围"><el-select v-model="form.visibility"><el-option label="仅自己可见" value="private"/><el-option label="对所有用户开放" value="public"/></el-select></el-form-item></el-form><el-button type="primary" :disabled="!enabled" :loading="creating" @click="create">提交测评</el-button></section>
<section class="card"><h2>测评任务</h2><el-table :data="rows" empty-text="暂无任务"><el-table-column prop="model_name" label="模型"/><el-table-column prop="benchmark" label="基准"/><el-table-column prop="status" label="状态"/><el-table-column label="进度"><template #default="{row}"><el-progress :percentage="row.progress||0"/></template></el-table-column><el-table-column label="操作"><template #default="{row}"><el-button link type="primary" @click="detail=row">详情</el-button><el-button v-if="['queued','running','paused'].includes(row.status)" link @click="action(row,'cancel')">取消</el-button></template></el-table-column></el-table></section>
<el-drawer :model-value="!!detail" title="任务详情" size="65%" @close="detail=null"><template v-if="detail"><p>{{detail.model_name}} · {{detail.status}}</p><pre>{{(detail.logs||[]).join('\n')}}</pre><h3>结果</h3><pre>{{detail.result?JSON.stringify(detail.result,null,2):'任务尚未产生结果'}}</pre></template></el-drawer></section></template>
