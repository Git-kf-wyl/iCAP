import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { setActivePinia, createPinia } from 'pinia'

const values = new Map()
globalThis.localStorage = { getItem:key=>values.get(key)??null, setItem:(key,value)=>values.set(key,String(value)), removeItem:key=>values.delete(key) }
const api = globalThis.sessionFixtureApi = {}
await mkdir('.runtime-tests',{recursive:true})
const source = (await readFile('src/blue/stores/auth.js','utf8')).replace("import { api } from '../api'",'const api = globalThis.sessionFixtureApi')
await writeFile('.runtime-tests/auth-under-test.mjs',source)
const {useAuth} = await import('../.runtime-tests/auth-under-test.mjs')
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
const fresh=()=>{values.clear();setActivePinia(createPinia());localStorage.setItem('ic_token','existing-session');return useAuth()}
const profile={id:'user',username:'user',role:'user',has_security_questions:true}
let calls=0
let pending=deferred()
api.get=()=>{calls++;return pending.promise}
let auth=fresh()
const first=auth.validateNavigation()
const second=auth.validateNavigation()
assert.equal(calls,1,'simultaneous guards must share initial validation')
pending.resolve(profile)
assert.equal(await first,true);assert.equal(await second,true)
for(let i=0;i<20;i++)assert.equal(await auth.validateNavigation(),true)
assert.equal(calls,1,'menu clicks must not require another network round trip')

const clock=Date.now
Date.now=()=>clock()+61000
pending=deferred();let invalidated=0
for(let i=0;i<20;i++)assert.equal(await auth.validateNavigation(()=>invalidated++),true)
assert.equal(calls,2,'stale sessions must revalidate once in the background')
pending.reject({response:{status:401}})
await new Promise(resolve=>setTimeout(resolve,0))
assert.equal(auth.token,'');assert.equal(invalidated,1,'revocation must invalidate navigation')
Date.now=clock

auth=fresh();pending=deferred();api.get=()=>pending.promise
const previous=auth.refreshProfile()
api.post=async()=>({...profile,username:'new-user',access_token:'new-session'})
await auth.login({username:'new-user',password:'test-only'})
pending.reject({response:{status:401}})
await previous
assert.equal(auth.token,'new-session','a delayed old 401 must not erase a new login')
assert.equal(auth.username,'new-user')
let posts=0;pending=deferred();api.post=()=>{posts++;return pending.promise}
const exits=[auth.logout(),auth.logout(),auth.logout()]
assert.equal(posts,1,'repeated logout clicks must send only one revocation')
pending.resolve({})
await Promise.all(exits)
assert.equal(auth.token,'')
console.log('PASS navigation avoids 20 auth round trips; single validation; background revocation; session race; single logout')
