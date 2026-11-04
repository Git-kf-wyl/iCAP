import {fileURLToPath,URL} from 'node:url'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({esbuild:{drop:["console","debugger"]},plugins:[vue()],resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},
  build:{sourcemap:false,manifest:true},server:{host:'127.0.0.1',port:5174,proxy:{'/api':'http://127.0.0.1:8082','/v1':'http://127.0.0.1:8082','/ws':{target:'ws://127.0.0.1:8082',ws:true}}}})
