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
const manifest=JSON.parse(readFileSync('dist/.vite/manifest.json','utf8'))
const seen=new Set()
function visit(key){
  if(seen.has(key))return
  seen.add(key)
  const row=manifest[key]
  assert(!row.file.startsWith('assets/charts-'),'Homepage must render before ECharts downloads')
  assert(!row.file.startsWith('assets/xlsx-'),'Model square must render before the Excel parser downloads')
  for(const dependency of row.imports||[])visit(dependency)
}
visit('src/components/homePage.vue')
visit('src/components/modelSquare/modelSquare.vue')
console.log('PASS homepage and model square exclude deferred chart/Excel runtimes')
