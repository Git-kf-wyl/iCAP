import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve, dirname } from 'node:path'
import { pathToFileURL } from 'node:url'
import { parse, compileScript } from '@vue/compiler-sfc'
const win = new Window({url:'https://icapblue.test/skill-evolution'})
for (const key of ['window','document','navigator','location','history','localStorage','sessionStorage','Node','Element','HTMLElement','SVGElement','ShadowRoot','Document','DocumentFragment','HTMLInputElement','HTMLTextAreaElement','HTMLSelectElement','MutationObserver','Event','MouseEvent','KeyboardEvent','FocusEvent','CustomEvent','NodeFilter','File','FormData']) Object.defineProperty(globalThis,key,{value:key==='window'?win:win[key],configurable:true,writable:true})
globalThis.getComputedStyle=win.getComputedStyle.bind(win)
globalThis.requestAnimationFrame=win.requestAnimationFrame.bind(win)
globalThis.cancelAnimationFrame=win.cancelAnimationFrame.bind(win)
globalThis.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}}
const { importParameters }=await import('../src/blue/skillEvolutionConfig.js')
const imported=importParameters('SELF_EVOLVE_CASES_LIMIT=\nJUDGMENT_WEIGHT_PROCESS=0\nJUDGMENT_WEIGHT_CONCISENESS=0.2\nJUDGMENT_WEIGHT_RESULT=0.4\nOUTPUT_WEIGHT_WORD=1\nAPI_KEY=DO-NOT-SEND\nSELF_EVOLVE_RESUME=/private/path',{execution_mode:'direct',judgment_weights:{process:0,conciseness:0,result:1},output_weights:{},cases_limit:7})
assert.equal(imported.form.cases_limit,null)
assert.deepEqual(imported.form.judgment_weights,{process:0,conciseness:0,result:1})
assert.ok(!JSON.stringify(imported).includes('DO-NOT-SEND'))
assert.ok(!JSON.stringify(imported.form).includes('/private/path'))
const directory=resolve('.runtime-tests/skill-workspace');await mkdir(directory,{recursive:true})
const compiled=new Map()
async function compile(path){
 path=resolve(path);if(compiled.has(path))return compiled.get(path)
 const target=resolve(directory,`${compiled.size}.mjs`);compiled.set(path,target)
 const {descriptor}=parse(await readFile(path,'utf8'))
 let code=compileScript(descriptor,{id:'test'+compiled.size,inlineTemplate:true}).content
 const imports=[...code.matchAll(/from\s+['"]([^'"]+)['"]/g)]
 for(const match of imports){
  const specifier=match[1];if(!specifier.startsWith('.'))continue
  let replacement
  if(specifier.endsWith('/api'))replacement=pathToFileURL(resolve(directory,'api.mjs')).href
  else if(specifier.endsWith('.vue'))replacement=pathToFileURL(await compile(resolve(dirname(path),specifier))).href
  else replacement=pathToFileURL(resolve(dirname(path),specifier+'.js')).href
  code=code.replaceAll(`'${specifier}'`,`'${replacement}'`).replaceAll(`"${specifier}"`,`"${replacement}"`)
 }
 await writeFile(target,code);return target
}
globalThis.skillFixture={files:[],requests:[],dataset:[],next:1}
await writeFile(resolve(directory,'api.mjs'),`export const api={
 get:async(path)=>path.endsWith('/files')?{items:globalThis.skillFixture.files,limits:{upload_bytes:94371840}}:{content:JSON.stringify(globalThis.skillFixture.dataset),name:'cases.json',path:'/var/lib/icap/skill-files/owner/upload/cases.json'},
 post:async(path,body)=>{const f=globalThis.skillFixture;if(path.endsWith('/upload')){const item={id:'file-'+f.next++,kind:'file',name:'cases.json',relative_path:'cases.json',path:'/var/lib/icap/skill-files/owner/upload/cases.json',size:1000};f.files.push(item);return {items:[item]}}f.requests.push(body);return{id:'new-job'}},delete:async()=>({})};export async function downloadFile(){}`)
const {createApp,nextTick}=await import('vue'), ElementPlus=(await import('element-plus')).default
const Component=(await import(pathToFileURL(await compile('src/blue/components/SkillEvolutionCreate.vue')))).default
const mount=(operation='evolve')=>{const el=document.createElement('div');document.body.append(el);const app=createApp(Component,{modelValue:true,operation,capabilities:{models:[{id:'platform-default',name:'Qwen',provider:'Aliyun',configured:true}],engines:[{id:'opt',name:'A'},{id:'enhanced',name:'B'}],execution_modes:['direct','hermes']}});app.config.errorHandler=(e)=>{console.error(e.stack);throw e};app.use(ElementPlus);app.mount(el);return app}
const flush=async()=>{await nextTick();await new Promise(r=>setTimeout(r,40));await nextTick()}
const click=async text=>{const button=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);assert.ok(button,`button ${text}`);button.click();await flush()}
const set=async(el,value)=>{assert.ok(el);el.value=value;el.dispatchEvent(new win.Event('input',{bubbles:true}));el.dispatchEvent(new win.Event('change',{bubbles:true}));await flush()}
const app=mount();await flush()
assert.ok(document.body.textContent.includes('JSON 格式'))
assert.ok(!document.body.textContent.includes('任务方式'))
await set(document.querySelector('input[placeholder="给这次任务一个名称"]'),'600-case original-format upload')
await set(document.querySelector('textarea[placeholder*="Skill 全文"]'),'Extract structured identity information.')
const rows=Array.from({length:600},(_,i)=>({id:'case-'+i,type:'memory',sub_type:'identity',input:[{type:'json',data:JSON.stringify([{role:'user',content:'林月'}])}],key_steps:[],output:[{type:'word',data:{whitelist:['林月']}},{type:'format',data:''}],pre_condition:[],input_path:'/var/lib/icap/skill-files/owner/upload/input.xlsx',output_weights:{word:1,format:1}}))
skillFixture.dataset=rows
const input=document.querySelector('input[accept=".json"]')
Object.defineProperty(input,'files',{value:[new File([JSON.stringify(rows)],'cases.json',{type:'application/json'})],configurable:true})
input.dispatchEvent(new win.Event('change',{bubbles:true}));await flush();await flush()
assert.ok(document.body.textContent.includes('600 条用例'))
assert.ok(document.body.textContent.includes('/var/lib/icap/skill-files/owner/upload/cases.json'))
assert.ok(document.body.textContent.includes('已关联 1 个文件'))
await click('开始自进化')
assert.equal(skillFixture.requests.length,1)
assert.equal(skillFixture.requests[0].dataset.length,600)
assert.equal(skillFixture.requests[0].cases_limit,null)
assert.deepEqual(skillFixture.requests[0].dataset[0],rows[0])
assert.deepEqual(skillFixture.requests[0].managed_file_ids,['file-1'])
assert.deepEqual(skillFixture.requests[0].judgment_weights,{process:0,conciseness:0,result:1})
assert.equal(skillFixture.requests[0].output_weights.format,1)
const preset=document.querySelector('.el-select');preset.click();await flush()
const option=[...document.querySelectorAll('.el-select-dropdown__item')].find(e=>e.textContent.includes('Spreadsheet'))
assert.ok(option);option.click();await flush()
assert.ok(document.body.textContent.includes('Hermes'))
await click('开始自进化')
assert.equal(skillFixture.requests[1].preset,'spreadsheet')
assert.equal(skillFixture.requests[1].execution_mode,'hermes')
assert.equal(skillFixture.requests[1].output_weights.device_state,1)
assert.deepEqual(skillFixture.requests[1].judgment_weights,{process:.4,conciseness:.2,result:.4})
const processInput=[...document.querySelectorAll('.dimension-box .el-form-item')].find(el=>el.textContent.includes('过程：')).querySelector('input')
await set(processInput,'0');await click('开始自进化')
assert.deepEqual(skillFixture.requests[2].judgment_weights,{process:0,conciseness:.2,result:.4})
assert.ok(document.body.textContent.includes('精简度 33.3%'))
app.unmount();await flush()
skillFixture.files=[{id:'book',kind:'file',name:'book.xlsx',relative_path:'book.xlsx',path:'/var/lib/icap/skill-files/book.xlsx',size:100},{id:'reference',kind:'file',name:'reference.py',relative_path:'reference.py',path:'/var/lib/icap/skill-files/reference.py',size:100}]
const generationApp=mount('bootstrap');await flush()
assert.ok(document.body.textContent.includes('脚本仅作为参考，不执行'))
assert.ok(!document.body.textContent.includes('用作输入'))
const bookRow=[...document.querySelectorAll('.el-table__row')].find(el=>el.textContent.includes('book.xlsx'))
assert.ok(bookRow.querySelector('input').disabled)
const scriptRow=[...document.querySelectorAll('.el-table__row')].find(el=>el.textContent.includes('reference.py'))
scriptRow.querySelector('input').click();await flush()
await set(document.querySelector('input[placeholder="给这次任务一个名称"]'),'生成草稿')
await set(document.querySelector('textarea[placeholder*="描述任务"]'),'根据脚本接口设计表格操作 Skill')
await click('生成 Skill 初稿')
assert.equal(skillFixture.requests[3].operation,'bootstrap')
assert.deepEqual(skillFixture.requests[3].managed_file_ids,['reference'])
generationApp.unmount();await win.happyDOM.cancelAsync()
console.log('PASS real Vue task form: 600 uploaded cases, preserved original JSON and file paths, associated managed files, rewrite and Hermes presets')
process.exit(0)
