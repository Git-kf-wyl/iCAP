import assert from 'node:assert/strict'
import axios from 'axios'
const saved=new Map([['ic_token','home-test-token']])
globalThis.localStorage={getItem:k=>saved.get(k)||null}
globalThis.location={origin:'https://icap.test'}
globalThis.window=new EventTarget()
const cache=await import('../src/readCache.js')
await cache.activateReadCache('home-test-token')
let finishBootstrap
const bootstrap=new Promise(resolve=>{finishBootstrap=resolve})
cache.startWorkspaceBootstrap({get:()=>bootstrap})
let calls=0
const api=axios.create({adapter:async config=>{calls++;return {data:JSON.stringify({ruler1:{test:1}}),status:200,statusText:'OK',headers:{},config}}})
cache.installReadCache(api)
const start=performance.now()
const [a,b]=await Promise.all([api.get('/v1/get_current_full_res'),api.get('/v1/get_current_full_res')])
assert.equal(a.data.ruler1.test,1);assert.equal(b.data.ruler1.test,1)
assert.ok(performance.now()-start<1000,'homepage data must not wait for a hung bootstrap')
assert.equal(calls,1,'concurrent homepage requests must stay deduplicated')
finishBootstrap({data:{entries:{},evaluation_revision:'test'}})
cache.clearReadCache()
console.log('Slow bootstrap no longer blocks homepage; duplicate reads remain joined')
