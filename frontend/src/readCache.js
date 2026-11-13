import axios from 'axios'
import {reactive} from 'vue'

// Only read-only lists and catalogue metadata are eligible. Chat, credentials,
// account endpoints, file bodies and execution commands always use the network.
const paths = new Set(['/v1/get_model_info','/v1/get_current_full_res','/v1/get_current_multi_full_res',
  '/v1/get_testcase_info','/v1/dataset/counts','/v1/get_all_published_tasks','/v1/get_all_report_tasks',
  '/v1/get_evaluation_result','/v1/lmarena/leaderboard','/v1/get_run_test_progress_list','/api/models','/api/datasets','/api/evaluations','/api/skill-evolution/capabilities'])
const homepagePaths = new Set(['/v1/get_current_full_res','/v1/get_current_multi_full_res','/v1/get_all_published_tasks'])
const bootstrapPaths = new Set([...paths].filter(path=>path.startsWith('/v1/') && !path.endsWith('get_run_test_progress_list')))
const evaluationPaths=new Set(['/v1/get_current_full_res','/v1/get_current_multi_full_res','/v1/lmarena/leaderboard','/v1/get_evaluation_result','/v1/get_run_test_progress_list','/v1/get_all_report_tasks','/v1/get_all_published_tasks','/api/evaluations'])
let evaluationRevision='', revisionTimer, revisionPending=false
const records = new Map(), inflight = new Map(), listeners = new Set()
const MAX_AGE = 20 * 60 * 1000
let session = '', scope = '', epoch = 0, ready = Promise.resolve(), database, boot = null
const clone = value => JSON.parse(JSON.stringify(value))
const failures=new Set()
export const readCacheStatus=reactive({stale:false})
function failed(path,value){if(value)failures.add(path);else failures.delete(path);readCacheStatus.stale=failures.size>0}
export const cacheStats = {hits:0, network:0, joined:0}
function announce(path) { for (const listener of listeners) listener(path) }
export function onReadUpdate(listener) { listeners.add(listener); return ()=>listeners.delete(listener) }

function db() {
  if (!globalThis.indexedDB) return Promise.resolve(null)
  if (!database) database = new Promise(resolve=>{
    const request = indexedDB.open('icap-read-snapshots-v1',3)
    const timer=setTimeout(()=>resolve(null),300)
    request.onupgradeneeded=()=>{
      if(request.result.objectStoreNames.contains('snapshots'))request.transaction.objectStore('snapshots').clear()
      else request.result.createObjectStore('snapshots',{keyPath:'key'})
    }
    request.onsuccess=()=>{
      clearTimeout(timer)
      request.result.onversionchange=()=>request.result.close()
      resolve(request.result)
    }
    request.onerror=request.onblocked=()=>{clearTimeout(timer);resolve(null)}
  })
  return database
}
async function disk(action, value) {
  try {
    const database=await db();if(!database)return []
    return await new Promise(resolve=>{
      const tx=database.transaction('snapshots',action==='getAll'?'readonly':'readwrite')
      const request=tx.objectStore('snapshots')[action](...(value===undefined?[]:[value]))
      request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve([])
      tx.onabort=()=>resolve([])
    })
  } catch { return [] }
}
export function clearReadCache() {
  clearInterval(revisionTimer);revisionTimer=null;evaluationRevision=''
  epoch++;session='';scope='';records.clear();inflight.clear();boot=null;ready=Promise.resolve()
  failures.clear();readCacheStatus.stale=false
  // Queue the clear before a subsequent login queues its reads/writes.
  void disk('clear')
  announce('*')
}
export function activateReadCache(token) {
  if (!token || token===session) return ready
  epoch++;session=token;scope='';records.clear();inflight.clear();boot=null
  evaluationRevision=''
  if(globalThis.document && !revisionTimer){revisionTimer=setInterval(checkEvaluationRevision,10000);revisionTimer.unref?.()}
  const generation=epoch
  ready=(async()=>{
    if (!globalThis.crypto?.subtle) return
    const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token))
    if(token!==session)return
    scope=[...new Uint8Array(digest)].map(x=>x.toString(16).padStart(2,'0')).join('')
    if(generation!==epoch)return
    for (const row of await disk('getAll') || []) {
      if(generation!==epoch)return
      if(row.scope===scope && Date.now()-row.time<MAX_AGE && paths.has(new URL(row.url,'https://icap.invalid').pathname)) {
        const current=records.get(row.url)
        if(!current || current.time<row.time)records.set(row.url,row)
      } else void disk('delete',row.key)
    }
  })()
  return ready
}
function safeData(value) {
  if(!value || typeof value!=='object')return true
  return Object.entries(value).every(([key,item])=>
    !(/^(api_key|password|access_token|refresh_token|authorization|secret)$/i.test(key) && item) && safeData(item))
}
function store(url,data,generation) {
  if(generation!==epoch || !session || !safeData(data))return
  const previous=records.get(url)
  const encoded=JSON.stringify(data)
  if(!encoded || encoded.length>1000000)return
  const row={key:scope+'|'+url,scope,url,time:Date.now(),data:clone(data)}
  records.set(url,row)
  if(records.size>40){const oldest=records.keys().next().value;const removed=records.get(oldest);records.delete(oldest);void disk('delete',removed.key)}
  if(scope)void disk('put',row)
  if(previous && JSON.stringify(previous.data)!==encoded)announce(new URL(url,'https://icap.invalid').pathname)
}
export function invalidateReads() {
  epoch++;records.clear();inflight.clear();boot=null
  void disk('clear');announce('*')
}
export function invalidateEvaluationReads() {
  epoch++;inflight.clear();boot=null
  for(const [url,row] of records)if(evaluationPaths.has(new URL(url,'https://icap.invalid').pathname)){
    records.delete(url);void disk('delete',row.key)
  }
  for(const path of evaluationPaths)announce(path)
}
export async function checkEvaluationRevision() {
  if(!session || revisionPending || globalThis.document?.visibilityState==='hidden')return
  const token=session
  revisionPending=true
  try{
    const response=await fetch('/api/evaluation/revision',{headers:{Authorization:'Bearer '+token},cache:'no-store'})
    if(!response.ok || token!==session)return
    const data=await response.json()
    if(token!==session)return
    if(typeof data.revision==='string' && data.revision!==evaluationRevision){
      evaluationRevision=data.revision;invalidateEvaluationReads()
    }
  }catch{}finally{revisionPending=false}
}
export function retryReads() {
  for(const row of records.values())row.time=Math.min(row.time,Date.now()-16000)
  announce('*')
}
export function seedReads(entries) {
  for(const [url,data] of Object.entries(entries||{}))if(paths.has(new URL(url,'https://icap.invalid').pathname))store(url,data,epoch)
}
export function startWorkspaceBootstrap(client=axios) {
  if(!session || boot)return boot?.promise
  const token=session,generation=epoch
  const current={promise:null}
  current.promise=(async()=>{
    await ready
    const response=await client.get('/api/workspace/bootstrap',{timeout:12000,silentError:true,icapBootstrap:true})
    if(token===session && generation===epoch){seedReads(response.data.entries);evaluationRevision=response.data.evaluation_revision || ''}
  })().catch(()=>{}).finally(()=>{if(boot===current)boot=null})
  boot=current
  return current.promise
}
function keyFor(config) {
  const url=new URL(axios.getUri(config),globalThis.location?.origin || 'https://icap.invalid')
  url.searchParams.sort()
  return {url:url.pathname+url.search,path:url.pathname,sameOrigin:url.origin===(globalThis.location?.origin || 'https://icap.invalid')}
}
export function installReadCache(client) {
  // axios.create inherits defaults: never wrap an already wrapped adapter.
  const network=client.defaults.adapter.icapNetwork || axios.getAdapter(client.defaults.adapter)
  client.defaults.adapter=async config=>{
    const {url,path,sameOrigin}=keyFor(config)
    const method=(config.method||'get').toLowerCase()
    const eligible=method==='get' && sameOrigin && paths.has(path) && !config.signal && !config.cancelToken && !config.responseType
    if(!eligible || !session || localStorage.getItem('ic_token')!==session) {
      const response=await network(config)
      if(sameOrigin && path==='/v1/update_top_chart')invalidateEvaluationReads()
      if(sameOrigin && !['get','head','options'].includes(method) && !path.startsWith('/api/auth/') && !path.startsWith('/v1/get_') && !path.includes('/chat') && !path.startsWith('/v1/dataset/update/'))invalidateReads()
      return response
    }
    const token=session
    const assertSession=()=>{if(session!==token || localStorage.getItem('ic_token')!==token)throw new axios.CanceledError('Session changed',config)}
    await ready;assertSession()
    const generation=epoch
    const responseFrom=row=>({data:clone(row.data),status:200,statusText:'OK',headers:{'content-type':'application/json'},config,request:null})
    const refresh=()=>{
      if(inflight.has(url)){cacheStats.joined++;return inflight.get(url)}
      cacheStats.network++
      const promise=network({...config,timeout:config.timeout || 15000}).then(response=>{
        assertSession()
        if(generation!==epoch)throw new axios.CanceledError('Data changed during request',config)
        let data=response.data
        if(typeof data==='string'){try{data=JSON.parse(data)}catch{return response}}
        store(url,data,generation)
        failed(path,false)
        return {...response,data:clone(data)}
      }).catch(error=>{
        if(!axios.isCancel(error) && generation===epoch && records.has(url))failed(path,true)
        if(error.response?.status===401 && generation===epoch && localStorage.getItem('ic_token')===session){
          clearReadCache();window.dispatchEvent(new Event('icap:session-expired'))
        }
        throw error
      }).finally(()=>{if(inflight.get(url)===promise)inflight.delete(url)})
      inflight.set(url,promise);return promise
    }
    let row=records.get(url)
    if(!row && boot && bootstrapPaths.has(path)){
      // Bootstrap is an optimization, not a prerequisite for this page's data.
      // Give a nearly complete snapshot a short chance to avoid duplicate reads.
      let timer
      try {
        if(homepagePaths.has(path))await Promise.race([boot.promise,new Promise(resolve=>{timer=setTimeout(resolve,120)})])
        else await boot.promise
      }
      finally {clearTimeout(timer)}
      assertSession();row=records.get(url)
    }
    if(generation!==epoch)throw new axios.CanceledError('Data changed during request',config)
    const freshFor=(path.endsWith('get_run_test_progress_list') || path==='/api/evaluations')?3000:15000
    if(row && Date.now()-row.time<MAX_AGE && generation===epoch) {
      cacheStats.hits++
      if(Date.now()-row.time>freshFor)refresh().catch(()=>{})
      return responseFrom(row)
    }
    const response=await refresh()
    return {...response,data:clone(response.data),config}
  }
  client.defaults.adapter.icapNetwork=network
}
