import assert from 'node:assert/strict'
import {readFile,writeFile,unlink} from 'node:fs/promises'
import {Window} from 'happy-dom'
import {parse,compileScript} from '@vue/compiler-sfc'
import {transform} from 'esbuild'
const win=new Window()
for(const k of ['window','document','HTMLElement','Element','SVGElement','Node'])globalThis[k]=k==='window'?win:win[k]
let intersect,disconnected=0
class Observer {constructor(fn){intersect=fn}observe(){}disconnect(){disconnected++}}
globalThis.IntersectionObserver=Observer
const source=await readFile(new URL('../src/charts/VisibleRankingChart.vue',import.meta.url),'utf8')
const {descriptor}=parse(source)
let code=compileScript(descriptor,{id:'visible-chart-test',inlineTemplate:true}).content
code=code.replace("import('./rankingScoreBarChart.vue')","Promise.resolve({props:['data','title'],render(){return h('span',{class:'loaded-chart'},this.title)}})")
code="import {h} from 'vue';\n"+code
const temp=new URL('./.visible-chart-test.mjs',import.meta.url)
await writeFile(temp,(await transform(code,{loader:'js',format:'esm'})).code)
try{
 const {default:Component}=await import(temp)
 const {createApp,nextTick,reactive}=await import('vue')
 const props=reactive({data:[],title:'first'})
 const host=win.document.createElement('div');win.document.body.append(host)
 const app=createApp(Component,props);app.mount(host)
 await nextTick();assert.equal(host.querySelector('.loaded-chart'),null)
 intersect([{isIntersecting:false}]);await nextTick();assert.equal(host.querySelector('.loaded-chart'),null)
 intersect([{isIntersecting:true}]);await new Promise(r=>setTimeout(r,20));await nextTick()
 assert.equal(host.querySelector('.loaded-chart')?.textContent,'first')
 assert.equal(disconnected,1)
 app.unmount();assert.equal(disconnected,2)
 console.log('Offscreen chart stays unloaded; viewport intersection mounts chart; observer cleaned up')
}finally{await unlink(temp)}
