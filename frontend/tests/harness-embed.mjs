// The production UI now embeds the authenticated Harness Lab application.
import assert from 'node:assert/strict'
import {readFile,writeFile,unlink} from 'node:fs/promises'
import {Window} from 'happy-dom'
import {parse,compileScript} from '@vue/compiler-sfc'
import {transform} from 'esbuild'
const win=new Window({url:'https://icap.test'})
for(const k of ['window','document','navigator','Node','Element','HTMLElement','SVGElement','ShadowRoot','Document','DocumentFragment','Event'])Object.defineProperty(globalThis,k,{value:k==='window'?win:win[k],configurable:true,writable:true})
const source=await readFile('src/components/harnessEvaluation/harnessOnlineAssessment.vue','utf8')
const {descriptor}=parse(source)
const code=compileScript(descriptor,{id:'harness-embed-test',inlineTemplate:true}).content
const temp=new URL('./.harness-embed-test.mjs',import.meta.url)
await writeFile(temp,(await transform(code,{loader:'js',format:'esm'})).code)
let app
try {
 const {default:Component}=await import(temp)
 const {createApp,nextTick}=await import('vue')
 const root=document.createElement('div');document.body.append(root)
 app=createApp(Component);app.mount(root)
 const frame=root.querySelector('iframe')
 assert.ok(frame)
 assert.equal(frame.getAttribute('src'),'/harness-lab/harness')
 assert.equal(frame.getAttribute('referrerpolicy'),'same-origin')
 assert.ok(frame.getAttribute('title').includes('Harness'))
 assert.equal(root.querySelector('[role=alert]'),null)
 frame.dispatchEvent(new win.Event('error'));await nextTick()
 assert.ok(root.querySelector('[role=alert]')?.textContent.includes('连接失败'))
 console.log('PASS authenticated Harness Lab iframe route and connection-error fallback')
} finally {app?.unmount();await unlink(temp);await win.happyDOM.abort()}
