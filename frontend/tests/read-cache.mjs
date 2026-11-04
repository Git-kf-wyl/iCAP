import assert from 'node:assert/strict'
import axios from 'axios'
import 'fake-indexeddb/auto'
const values=new Map()
globalThis.localStorage={getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value)}
globalThis.location={origin:'https://icap.test'}
globalThis.window=new EventTarget()
const tick=()=>new Promise(resolve=>setTimeout(resolve,10))
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
let cache=await import('../src/readCache.js')
let calls=0, data={name:'old'}, handler=async()=>data
const transport=async config=>{calls++;return {data:JSON.stringify(await handler(config)),config,status:200,statusText:'OK',headers:{}}}
const api=axios.create({adapter:transport})
cache.installReadCache(api)
const login=async token=>{localStorage.setItem('ic_token',token);await cache.activateReadCache(token)}
await login('test-session-one')
let wait=deferred();handler=()=>wait.promise
const first=api.get('/api/models'),second=api.get('/api/models')
await tick();assert.equal(calls,1)
wait.resolve(data);await Promise.all([first,second])
assert.equal((await api.get('/api/models')).data.name,'old');assert.equal(calls,1)
const inherited=api.create();cache.installReadCache(inherited)
assert.equal((await inherited.get('/api/models')).data.name,'old','inherited adapters must not double wrap')
assert.equal((await Promise.race([inherited.get('/api/datasets'),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Inherited adapter deadlocked')),1000))])).data.name,'old')
assert.equal(calls,2)
await tick()
// A new JS context restores the same verified session from IndexedDB.
cache=await import('../src/readCache.js?reload')
const restored=axios.create({adapter:transport});cache.installReadCache(restored)
await login('test-session-one')
assert.equal((await restored.get('/api/models')).data.name,'old');assert.equal(calls,2)

const clock=Date.now
Date.now=()=>clock()+16000
handler=async()=>{await new Promise(r=>setTimeout(r,3000));return {name:'new'}}
let changed=0;cache.onReadUpdate(path=>{if(path==='/api/models')changed++})
const start=performance.now()
assert.equal((await restored.get('/api/models')).data.name,'old')
const cachedMs=performance.now()-start;assert.ok(cachedMs<100)
await new Promise(r=>setTimeout(r,3100))
assert.equal((await restored.get('/api/models')).data.name,'new');assert.equal(changed,1)
Date.now=clock

// Writes drop old snapshots; a late read cannot restore stale data or update a caller.
cache.invalidateReads();wait=deferred();handler=config=>config.method==='post'?{}:wait.promise
const old=restored.get('/api/models');const oldResult=old.catch(error=>error)
await tick();await restored.post('/api/models',{name:'edited'});wait.resolve({name:'before-edit'})
assert.ok(axios.isCancel(await oldResult))
handler=async()=>({name:'edited'})
assert.equal((await restored.get('/api/models')).data.name,'edited')

cache.invalidateReads();wait=deferred();handler=()=>wait.promise
const oldUser=restored.get('/api/models').catch(error=>error)
await tick();await login('test-session-two');wait.resolve({name:'private-one'})
assert.ok(axios.isCancel(await oldUser))
handler=async()=>({name:'private-two'})
assert.equal((await restored.get('/api/models')).data.name,'private-two')
cache.clearReadCache();await tick();await login('test-session-two')
const before=calls;await restored.get('/api/models');assert.equal(calls,before+1,'logout must clear persistent snapshots')

cache.invalidateReads();handler=async()=>({api_key:'test-only-secret'})
const beforeSecret=calls;await restored.get('/api/models');await restored.get('/api/models')
assert.equal(calls,beforeSecret+2,'credentials must never enter cache')
handler=async()=>({ok:true})
const beforeAuth=calls;await restored.get('/api/auth/me');await restored.get('/api/auth/me')
assert.equal(calls,beforeAuth+2,'authentication must never use a data snapshot')

await restored.get('/api/models');Date.now=()=>clock()+16000
handler=async()=>{throw new Error('offline')}
assert.deepEqual((await restored.get('/api/models')).data,{ok:true});await tick()
assert.equal(cache.readCacheStatus.stale,true,'failed background updates must be visible')
let revoked=0;window.addEventListener('icap:session-expired',()=>revoked++)
handler=async()=>{throw {response:{status:401}}}
await restored.get('/api/models');await tick();assert.equal(revoked,1)
Date.now=clock
console.log(JSON.stringify({pass:'dedup, persistent restore, update, mutation/session races, logout, secrets, offline, revocation',cached_read_ms:Math.round(cachedMs*100)/100,simulated_network_ms:3000}))
