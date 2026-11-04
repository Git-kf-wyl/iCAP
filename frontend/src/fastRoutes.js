import {defineComponent,defineAsyncComponent,h} from 'vue'
import PageLoading from './components/PageLoading.vue'

const loaders=new Map(),promises=new Map()
export const retainedPages=[]
const retained=new Set(['/','/modelSquare','/rankingScore','/PublishedReport','/dataCenter/evalDatasetDevelopment'])
const titles={'/':'平台首页','/modelSquare':'模型广场','/rankingScore':'模型榜单','/chat':'智能对话',
  '/PublishedReport':'评测报告','/dataCenter/evalDatasetDevelopment':'评测集仓库','/models/manage':'模型连接管理',
  '/modelEvaluation/onlineAssessment':'评测任务','/skill-evolution':'Skill 自进化'}
export function warmRoute(path) {
  const loader=loaders.get(path)
  if(!loader)return Promise.resolve()
  if(!promises.has(path))promises.set(path,loader().catch(error=>{promises.delete(path);throw error}))
  return promises.get(path)
}
export function instantRoute(record,index) {
  if(typeof record.component!=='function' || record.meta?.authPage)return record
  loaders.set(record.path,record.component)
  const name='WorkspacePage'+index
  if(retained.has(record.path))retainedPages.push(name)
  const Async=defineAsyncComponent({loader:()=>warmRoute(record.path),delay:0,
    loadingComponent:defineComponent({setup:()=>()=>h(PageLoading,{title:titles[record.path]||'工作台'})}),
    errorComponent:defineComponent({setup:()=>()=>h('div',{class:'route-error',role:'alert'},[
      h('p','页面暂时无法加载，请检查网络后重试。'),h('button',{onClick:()=>location.reload()},'重新加载')])}),
    onError(error,retry,fail,attempts){if(attempts<2)setTimeout(retry,600);else fail()},timeout:30000})
  // A synchronous route wrapper lets Vue Router commit the URL immediately.
  // The network only delays the inner content, never the navigation itself.
  return {...record,component:defineComponent({name,setup:()=>()=>h(Async)})}
}
let queue=[],running=0,enabled=false
function drain(){
  if(!enabled || document.visibilityState==='hidden')return
  while(running<2 && queue.length){
    const path=queue.shift();running++
    warmRoute(path).catch(()=>{}).finally(()=>{running--;setTimeout(drain,80)})
  }
}
export function prefetchRoute(path) {
  if(!enabled || !loaders.has(path))return
  queue=queue.filter(value=>value!==path);queue.unshift(path);drain()
}
export function startRouteWarmup(current) {
  if(enabled)return
  enabled=true
  if(navigator.connection?.saveData || /(^|-)2g$/.test(navigator.connection?.effectiveType||''))return
  queue=['/modelSquare','/chat','/dataCenter/evalDatasetDevelopment','/PublishedReport','/models/manage'].filter(path=>path!==current)
  const schedule=()=>globalThis.requestIdleCallback?requestIdleCallback(drain,{timeout:2000}):setTimeout(drain,300)
  warmRoute(current).catch(()=>{}).finally(schedule)
}
export function stopRouteWarmup(){enabled=false;queue=[]}
export function prefetchMenu(event) {
  const item=event.target.closest?.('.el-menu-item,a')
  if(!item)return
  const links={'首页':'/','MaaS服务':'/modelSquare','Agent应用':'/chat','数据&评测':'/dataCenter/evalDatasetDevelopment',
    '模型广场':'/modelSquare','模型榜单':'/rankingScore','智能对话':'/chat','Chat助手':'/chat','评测集仓库':'/dataCenter/evalDatasetDevelopment',
    '模型连接管理':'/models/manage','Skill 自进化':'/skill-evolution','评测任务':'/modelEvaluation/onlineAssessment'}
  const path=item.getAttribute('href') || links[item.textContent.trim()]
  if(path?.startsWith('/'))prefetchRoute(path)
}
