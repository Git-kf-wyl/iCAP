import {readFileSync,readdirSync} from 'node:fs'
import {gunzipSync} from 'node:zlib'
import assert from 'node:assert/strict'
let checked=0
for(const name of readdirSync('dist/assets')){
  if(!/\.(js|css)$/.test(name))continue
  const raw=readFileSync('dist/assets/'+name)
  const compressed=gunzipSync(readFileSync('dist/assets/'+name+'.gz'))
  assert.deepEqual(compressed,raw,'Compressed response differs from the final build: '+name)
  if(name.endsWith('.js'))assert(!raw.includes('__VITE_PRELOAD__'),'Unresolved build marker: '+name)
  checked++
}
console.log('PASS final compressed asset integrity:',checked,'files')
