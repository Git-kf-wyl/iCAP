import assert from 'node:assert/strict'
import {readFile,writeFile,mkdir} from 'node:fs/promises'
import axios from 'axios'

await mkdir('.runtime-tests',{recursive:true})
const source=(await readFile('src/api/runService.js','utf8')).replace(/import \{ API_AGENT_URL, API_BASE_URL \} from [^;]+;/,"const API_AGENT_URL='/v1/', API_BASE_URL='/v1/';")
await writeFile('.runtime-tests/run-service.mjs',source)
const {updateScore}=await import('../.runtime-tests/run-service.mjs')
const calls=[],get=axios.get
axios.get=async(url,config)=>{calls.push({url,...config});return {data:{info:'success'}}}
try{
 await updateScore({task_id:'one',testcase:['mmlu','gpqa']})
 await updateScore({'task_id[]':['two'],'testcase[]':['MMMU']})
 assert.deepEqual(calls.map(call=>call.params),[
  {'task_id[]':['one'],'testcase[]':['mmlu','gpqa']},
  {'task_id[]':['two'],'testcase[]':['MMMU']},
 ])
 assert.ok(calls.every(call=>call.url==='/v1/update_top_chart'))
}finally{axios.get=get}
console.log('PASS scalar and array publications use the original server array contract')
