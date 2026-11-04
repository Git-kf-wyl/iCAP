import {fileURLToPath,URL} from 'node:url'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import {gzipSync} from 'node:zlib'
const compressedAssets={name:'icap-compressed-assets',generateBundle(_,bundle){
  for(const item of Object.values(bundle))if(/\.(js|css)$/.test(item.fileName))
    this.emitFile({type:'asset',fileName:item.fileName+'.gz',source:gzipSync(item.type==='chunk'?item.code:item.source,{level:6})})
}}
export default defineConfig({esbuild:{drop:["console","debugger"]},plugins:[vue(),compressedAssets],resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},
  build:{sourcemap:false,manifest:true,rollupOptions:{output:{manualChunks(id){
    if(!id.includes('node_modules'))return
    if(/node_modules\/(?:@vue\/|vue\/|vue-router\/|pinia\/|vuex\/)/.test(id))return 'vue-runtime'
    if(id.includes('@element-plus/icons-vue'))return 'icons'
    if(id.includes('element-plus'))return 'element-plus'
    if(id.includes('echarts')||id.includes('zrender'))return 'charts'
  }}}},server:{host:'127.0.0.1',port:5174,proxy:{'/api':'http://127.0.0.1:8082','/v1':'http://127.0.0.1:8082','/ws':{target:'ws://127.0.0.1:8082',ws:true}}}})
