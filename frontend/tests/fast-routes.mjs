import assert from 'node:assert/strict'
import {Window} from 'happy-dom'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
const win=new Window({url:'https://icap.test'})
for(const key of ['window','document','navigator','location','history','Node','Element','HTMLElement','SVGElement'])Object.defineProperty(globalThis,key,{value:key==='window'?win:win[key],configurable:true})
const {createApp,h,defineComponent,KeepAlive,ref,nextTick}=await import('vue')
const {createRouter,createMemoryHistory,RouterView}=await import('vue-router')
await mkdir('.runtime-tests',{recursive:true})
const source=(await readFile('src/fastRoutes.js','utf8')).replace("import PageLoading from './components/PageLoading.vue'","const PageLoading=defineComponent({setup:()=>()=>h('div','loading page')})")
await writeFile('.runtime-tests/routes-under-test.mjs',source)
const {instantRoute,retainedPages}=await import('../.runtime-tests/routes-under-test.mjs')
let finish,late,mounts=0
const pending=new Promise(resolve=>finish=resolve),pendingLate=new Promise(resolve=>late=resolve)
const routes=[{path:'/',component:()=>Promise.resolve(defineComponent({setup:()=>()=>h('div','home')}))},
 {path:'/modelSquare',component:()=>pending},{path:'/late',component:()=>pendingLate}].map(instantRoute)
const router=createRouter({history:createMemoryHistory(),routes})
const app=createApp({render:()=>h(RouterView,null,{default:({Component,route})=>h(KeepAlive,{include:retainedPages,max:4},()=>Component?h(Component,{key:route.path}):null)})})
app.use(router);await router.push('/');await router.isReady();app.mount(document.body)
const tick=()=>new Promise(r=>setTimeout(r,10))
await tick()
const start=performance.now();await router.push('/modelSquare');await nextTick()
const elapsed=performance.now()-start
assert.ok(elapsed<100);assert.ok(document.body.textContent.includes('loading page'),'route must paint without waiting for its module')
finish(defineComponent({setup(){mounts++;const n=ref(0);return()=>h('button',{onClick:()=>n.value++},'model '+n.value)}}))
await tick();document.querySelector('button').click();await nextTick()
await router.push('/');await tick();await router.push('/modelSquare');await tick()
assert.ok(document.body.textContent.includes('model 1'));assert.equal(mounts,1)
await router.push('/late');await nextTick();await router.push('/modelSquare')
late(defineComponent({setup:()=>()=>h('div','stale page')}));await tick()
assert.ok(document.body.textContent.includes('model 1'));assert.ok(!document.body.textContent.includes('stale page'))
app.unmount()
console.log(JSON.stringify({pass:'cold route commits before module download; KeepAlive preserves state; late route cannot replace current page',navigation_ms:Math.round(elapsed*100)/100}))
process.exit(0)
