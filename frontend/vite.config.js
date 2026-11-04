import {fileURLToPath,URL} from 'node:url'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import {gzipSync} from 'node:zlib'
import {readFileSync,writeFileSync,readdirSync} from 'node:fs'
import {resolve,join} from 'node:path'
let outputDirectory
// Vite replaces preload markers and finalizes CSS after generateBundle hooks.
const compressedAssets={name:'icap-compressed-assets',configResolved(config){outputDirectory=resolve(config.root,config.build.outDir)},closeBundle(){
  const assets=join(outputDirectory,'assets')
  for(const name of readdirSync(assets))if(/\.(js|css)$/.test(name)){
    const path=join(assets,name)
    writeFileSync(path+'.gz',gzipSync(readFileSync(path),{level:6}))
  }
}}
export default defineConfig({esbuild:{drop:["console","debugger"]},plugins:[vue(),compressedAssets],resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},
  build:{sourcemap:false,manifest:true,rollupOptions:{output:{entryFileNames:'assets/[name]-[hash]-boot2.js',chunkFileNames:'assets/[name]-[hash]-boot2.js',assetFileNames:'assets/[name]-[hash]-boot2[extname]',manualChunks(id){
    if(!id.includes('node_modules'))return
    if(/node_modules\/(?:@vue\/|vue\/|vue-router\/|pinia\/|vuex\/)/.test(id))return 'vue-runtime'
    if(id.includes('@element-plus/icons-vue'))return 'icons'
    if(id.includes('element-plus'))return 'element-plus'
    if(id.includes('echarts')||id.includes('zrender'))return 'charts'
  }}}},server:{host:'127.0.0.1',port:5174,proxy:{'/api':'http://127.0.0.1:8082','/v1':'http://127.0.0.1:8082','/ws':{target:'ws://127.0.0.1:8082',ws:true}}}})
