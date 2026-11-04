import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import DOMPurify from 'dompurify'
import router from './router';
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn';
import { createPinia } from 'pinia'
import './common/style.css'
// 数据治理 Pipeline 模块全局样式（内部类名与主工程隔离，不影响其它页面）
import './platformNetwork.js'
import stores from './stores';


const app = createApp(App).use(ElementPlus, { locale: zhCn })

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(stores)
app.config.globalProperties.$sanitizeHtml = value => DOMPurify.sanitize(String(value ?? ''))
router.onError(error => window.__icapBoot?.fail('navigation','',error?.message || String(error)))
// Finish authentication and its asset cookie before importing protected views.
router.isReady().then(() => {
  app.mount('#app')
  window.__icapBoot?.complete()
}).catch(error => window.__icapBoot?.fail('navigation','',error?.message || String(error)))
