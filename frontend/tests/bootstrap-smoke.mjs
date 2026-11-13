import { Window } from 'happy-dom'
import vm from 'node:vm'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import {createHash} from 'node:crypto'
const win=new Window({url:'https://icapblue.test/',settings:{disableCSSFileLoading:true,disableJavaScriptFileLoading:true}})
const mode=process.argv[2]||'fresh'
for(const key of ['window','document','navigator','location','history','localStorage','sessionStorage','Node','Element','HTMLElement','SVGElement','ShadowRoot','Document','DocumentFragment','HTMLInputElement','HTMLTextAreaElement','HTMLSelectElement','MutationObserver','Event','CustomEvent','NodeFilter']){
 const value=key==='window'?win:win[key]
 Object.defineProperty(globalThis,key,{value,configurable:true,writable:true})
}
globalThis.getComputedStyle=win.getComputedStyle.bind(win)
globalThis.requestAnimationFrame=win.requestAnimationFrame.bind(win)
globalThis.cancelAnimationFrame=win.cancelAnimationFrame.bind(win)
globalThis.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}}
const requests=[]
const requestTimes=[]
const snapshot={entries:{
 '/v1/get_current_full_res':{ruler1:{},ruler2:{}},'/v1/get_current_multi_full_res':{ruler1:{},ruler2:{}},
 '/v1/get_all_published_tasks':[],'/v1/get_all_report_tasks':[],'/v1/get_evaluation_result':{},'/v1/dataset/counts':{},'/v1/lmarena/leaderboard':[],
 '/v1/get_testcase_info?is_field=1':{},'/v1/get_testcase_info?is_field=2':{},'/v1/get_testcase_info?is_field=3':{},
 '/v1/get_model_info':[{model_id:'deepseek-fixture',status:1,is_available:true,can_edit:false,visibility:'public',
  info:{model_name:'DeepSeek-Cache-Fixture',display_name:'DeepSeek-Cache-Fixture',model_desc:'cache fixture',series:'DeepSeek',vendor:'DeepSeek',tags:['chat'],category:['LLM'],size:'',context_length:32768,isInternalDeployed:false,creation_date:'',zone:'云端',logo_url:''},
  config:{filter:{head:'',tail:''},extra_headers:[],api_params:[],api_params_available:[],params:[]}}]
}}
globalThis.fetch=async input=>{
 const url=new URL(typeof input==='string'?input:input.url,win.location.href);requests.push(url.pathname)
 if(url.pathname==='/api/auth/me')return new Response(JSON.stringify(mode==='expired'?{detail:'expired'}:{id:'test',username:'test',role:'user',has_security_questions:true}),{status:mode==='expired'?401:200,headers:{'Content-Type':'application/json'}})
 return new Response(JSON.stringify([]),{status:200,headers:{'Content-Type':'application/json'}})
}
win.fetch=globalThis.fetch
class TestXHR {
 constructor(){this.onloadend=null;this.upload={addEventListener(){},removeEventListener(){}};this.withCredentials=false}
 open(method,url){this.method=method;this.url=url;this.readyState=1}
 setRequestHeader(){}
 getAllResponseHeaders(){return 'content-type: application/json\r\n'}
 addEventListener(){}
 removeEventListener(){}
 abort(){}
 send(){const finish=()=>{
  const url=new URL(this.url,win.location.href);requests.push(url.pathname)
  requestTimes.push({path:url.pathname,time:Date.now()})
  if(mode==='offline'&&url.pathname==='/api/auth/me'){this.onerror?.(new win.Event('error'));return}
  this.status=url.pathname==='/api/auth/me'&&mode==='expired'?401:200
  this.statusText=this.status===401?'Unauthorized':'OK';this.responseURL=url.href;this.readyState=4
  this.responseText=JSON.stringify(url.pathname==='/api/auth/me'?(this.status===401?{detail:'expired'}:{id:'test',username:'test',role:'user',has_security_questions:true}):mode==='fast'&&url.pathname==='/api/workspace/bootstrap'?snapshot:[])
  this.response=this.responseText;this.onloadend?.()
 };if(mode==='fast')setTimeout(finish,3000);else if(mode==='navigation'&&new URL(this.url,win.location.href).pathname==='/api/auth/me')setTimeout(finish,700);else queueMicrotask(finish)}
}
globalThis.XMLHttpRequest=TestXHR
win.XMLHttpRequest=TestXHR
const append=win.Node.prototype.appendChild
win.Node.prototype.appendChild=function(node){const result=append.call(this,node);if(node.tagName==='LINK')setImmediate(()=>node.dispatchEvent(new win.Event('load')));return result}
win.document.body.innerHTML='<div id="app"></div>'
if(mode!=='fresh')win.localStorage.setItem('ic_token','test-only-token')
const errors=[]
process.on('unhandledRejection',e=>{errors.push(String(e?.stack||e))})
process.on('uncaughtException',e=>{errors.push(String(e?.stack||e))})
const dist=resolve('dist');const html=await readFile(resolve(dist,'index.html'),'utf8');win.document.body.innerHTML=html.match(/<body>([\s\S]*?)<\/body>/)[1];
win.navigator.sendBeacon=()=>true;for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInThisContext(match[1]);
const entry=html.match(/src="([^\"]+\.js)"/)[1]
if(['server-session','fast'].includes(mode)){
 const script=win.document.createElement('script');script.id='icap-session';script.type='application/json'
 script.textContent=JSON.stringify({profile:{id:'test',username:'test',role:'user',has_security_questions:true},expires_at:Math.floor(Date.now()/1000)+300,fingerprint:createHash('sha256').update('test-only-token').digest('hex')})
 win.document.head.appendChild(script)
}
try{await import(pathToFileURL(resolve(dist,entry.slice(1))))}catch(e){errors.push(String(e.stack||e))}
await new Promise(r=>setTimeout(r,mode==='fast'?6500:3500))
if(mode==='fast'){
 const click=label=>{
  const item=[...win.document.querySelectorAll('.el-menu-item')].find(el=>el.textContent.trim()===label)
  if(!item)throw new Error('Missing menu: '+label)
  item.dispatchEvent(new win.MouseEvent('click',{bubbles:true}))
 }
 const timings=[]
 for(const [label,path,text] of [['MaaS服务','/modelSquare','DeepSeek-Cache-Fixture'],['数据&评测','/dataCenter/evalDatasetDevelopment','基准资源社区'],['首页','/','云核心网 AI 创新平台'],['MaaS服务','/modelSquare','DeepSeek-Cache-Fixture']]){
  const start=Date.now();click(label)
  while((win.location.pathname!==path || !win.document.querySelector('#app')?.textContent.includes(text) || win.document.querySelector('.el-loading-mask:not([style*="display: none"])'))&&Date.now()-start<1500)await new Promise(r=>setTimeout(r,10))
  const elapsed=Date.now()-start;timings.push({page:path,content_ms:elapsed})
  if(elapsed>=1500){errors.push('Warm page content delayed: '+path);console.log(JSON.stringify({diagnostic:path,text:win.document.querySelector('#app')?.textContent.slice(-1600),masks:[...win.document.querySelectorAll('.el-loading-mask')].map(el=>({style:el.getAttribute('style'),parent:el.parentElement?.className}))}))}
 }
 if(requests.includes('/api/auth/me'))errors.push('Extra auth request despite verified session')
 if(requests.filter(path=>path==='/api/workspace/bootstrap').length!==1)errors.push('Bootstrap request must be shared')
 const homepageReads=new Set(['/v1/get_current_full_res','/v1/get_current_multi_full_res','/v1/get_all_published_tasks'])
 if(requests.some(path=>path.startsWith('/v1/') && !homepageReads.has(path)))errors.push('Seeded pages repeated API requests')
 for(const path of homepageReads)if(requests.filter(value=>value===path).length>1)errors.push('Homepage fallback repeated: '+path)
 console.log(JSON.stringify({simulated_network_ms:3000,content_timings:timings}))
}
if(mode==='navigation'){
 const click=label=>{
  const item=[...win.document.querySelectorAll('.el-menu-item')].find(el=>el.textContent.trim()===label)
  if(!item)throw new Error('Missing menu: '+label)
  item.dispatchEvent(new win.MouseEvent('click',{bubbles:true}))
 }
 const started=Date.now();click('MaaS服务')
 while(win.location.pathname!=='/modelSquare'&&Date.now()-started<500)await new Promise(r=>setTimeout(r,10))
 const elapsed=Date.now()-started
 if(win.location.pathname!=='/modelSquare')errors.push('Menu navigation blocked on authentication')
 if(requests.filter(path=>path==='/api/auth/me').length!==1)errors.push('Repeated auth round trip on menu navigation')
 const homeReads=requestTimes.filter(row=>['/v1/get_all_published_tasks','/v1/get_current_full_res','/v1/get_current_multi_full_res'].includes(row.path))
 if(new Set(homeReads.map(row=>row.path)).size!==3)errors.push('Missing homepage data requests')
 console.log(JSON.stringify({navigation_ms:elapsed,auth_round_trips:requests.filter(path=>path==='/api/auth/me').length,homepage_read_start_spread_ms:Math.max(...homeReads.map(row=>row.time))-Math.min(...homeReads.map(row=>row.time))}))
}
console.log(JSON.stringify({mode,path:win.location.pathname,text:win.document.querySelector('#app')?.textContent?.slice(0,600),errors,requests},null,2))
const output=win.document.querySelector('#app')?.textContent||''
if(mode==='server-session'&&requests.includes('/api/auth/me'))errors.push('Server session bootstrap triggered an unnecessary auth request')
const expected=mode==='offline'?output.includes('重新加载'):['navigation','fast'].includes(mode)?win.location.pathname==='/modelSquare':['valid','server-session'].includes(mode)?output.includes('云核心网 AI 创新平台'):win.location.pathname==='/login'&&output.includes('登录平台')
process.exit(errors.length||!expected?1:0)
