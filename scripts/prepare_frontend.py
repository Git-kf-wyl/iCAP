from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / 'frontend'
ORIGINAL = Path('D:/icap/icap_yellow_source/frontend_original')
BLUE = Path('D:/icap/iCAP/iCAP/frontend/src')

# The previous implementation lives only in src/blue, so Vite cannot resolve
# the old router.js instead of Yellow's router/index.js.
for source in BLUE.rglob('*'):
    if source.is_file() and not (ORIGINAL / 'src' / source.relative_to(BLUE)).exists():
        target = FRONT / 'src' / source.relative_to(BLUE)
        if target.is_file():
            target.unlink()

def read(name):
    return (FRONT / name).read_text(encoding='utf-8-sig')

def write(name, value):
    path = FRONT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + '\n', encoding='utf-8')

router = (ORIGINAL / 'src/router/index.js').read_text(encoding='utf-8-sig')
router = re.sub(r'^import .*@/components/aiSchool/.*\n', '', router, flags=re.M)
start = router.index('// ===== 数据治理 Pipeline 模块（')
end = router.index('const router =', start)
router = router[:start] + router[end:]
router = re.sub(r'^.*path: .*/aiSchool/.*\n', '', router, flags=re.M)
router = router[:router.index('        // ===== 数据治理 Pipeline 模块路由')]
extras = {
    '/skill-evolution': 'SkillEvolution',
    '/models/manage': 'Models',
    '/datasets/manage': 'Datasets',
    '/agentcompass': 'Evaluations',
    '/operations': 'Operations',
}
for route, component in extras.items():
    name = component + 'Extension'
    write('src/integration/' + name + '.vue', f'''<script setup>
import View from '../blue/views/{component}.vue'
import '../integration/blue-features.css'
</script>
<template><section class="blue-feature"><View /></section></template>''')
    router += f"        {{ path: '{route}', component: () => import('../integration/{name}.vue') }},\n"
for route, component in [('/login','Login'),('/register','Register'),('/password/reset','PasswordSecurity'),('/password/change','PasswordSecurity'),('/security-questions/setup','SecurityQuestionsSetup')]:
    public = route in ('/login','/register','/password/reset')
    router += f"        {{ path: '{route}', component: () => import('../blue/views/{component}.vue'), meta: {{ authPage: true, public: {str(public).lower()} }} }},\n"
for old, new in {'/models':'/modelSquare','/leaderboard':'/rankingScore','/datasets':'/dataCenter/evalDatasetDevelopment','/evaluations':'/modelEvaluation/onlineAssessment','/reports':'/PublishedReport','/agents':'/chat','/deployments':'/modelDeploy'}.items():
    router += f"        {{ path: '{old}', redirect: '{new}' }},\n"
router += '''        { path: '/:pathMatch(.*)*', redirect: '/' },
    ],
})
router.beforeEach(to => {
    const token = localStorage.getItem('ic_token')
    if (!to.meta.public && !token) return {path:'/login',query:{redirect:to.fullPath}}
    if (to.meta.public && token) return '/'
    document.title = 'InnovationCore AI Platform'
})
export default router;
'''
write('src/router/index.js', router)

layout = (ORIGINAL / 'src/components/visualization.vue').read_text(encoding='utf-8-sig')
def remove_template(text, condition):
    marker = f'<template v-if="currentModule === \'{condition}\'">'
    start = text.index(marker)
    depth = 0
    for match in re.finditer(r'</?template\b[^>]*>', text[start:]):
        depth += -1 if match[0].startswith('</') else 1
        if depth == 0:
            return text[:start] + text[start + match.end():]
    raise ValueError('Unbalanced layout template')

for module in ('aiSchool','dataPipeline'):
    layout = remove_template(layout, module)
    layout = re.sub(r'^.*<el-menu-item index="' + module + r'".*\n', '', layout, flags=re.M)
layout = layout.replace('const token = ref("");', "const auth = useAuth();\nconst token = computed(() => auth.token ? auth.username : '');")
layout = layout.replace('import Login from "@/components/login.vue";', 'import Login from "@/components/login.vue";\nimport { useAuth } from "@/blue/stores/auth.js";')
layout = re.sub(r'^\s*token\.value = .*;?\n', '', layout, flags=re.M)
layout = layout.replace("evaluator_list.includes(token)", "!!auth.token").replace("token==='admin'", "auth.role==='admin'").replace("token!=='admin'", "auth.role!=='admin'")
start = layout.index('const loginOut = () => {')
end = layout.index('const handleOpen', start)
layout = layout[:start] + '''const loginOut = async () => {
  await auth.logout();
  localStorage.removeItem('username');
  router.replace('/login');
}
const handleUpdate = () => auth.refreshProfile();

''' + layout[end:]
layout = layout.replace("if (path.startsWith('/chat'))", "if (path.startsWith('/skill-evolution')) return 'app';\n  if (path.startsWith('/agentcompass')) return 'dataEval';\n  if (path.startsWith('/datasets/manage')) return 'dataEval';\n  if (path.startsWith('/chat'))")
layout = layout.replace("<template v-if=\"currentModule === 'app'\">", """<template v-if="currentModule === 'app'">
                <el-menu-item index="/skill-evolution"><el-icon><MagicStick /></el-icon><span class="menuItem">Skill 自进化</span></el-menu-item>""")
layout = layout.replace("<template v-if=\"currentModule === 'maas'\">", """<template v-if="currentModule === 'maas'">
                <el-menu-item index="/models/manage"><el-icon><Setting /></el-icon><span class="menuItem">模型连接管理</span></el-menu-item>
                <el-menu-item index="/operations"><el-icon><Monitor /></el-icon><span class="menuItem">服务监控</span></el-menu-item>""")
layout = layout.replace("<template v-if=\"currentModule === 'dataEval'\">", """<template v-if="currentModule === 'dataEval'">
                <el-menu-item index="/agentcompass"><el-icon><Compass /></el-icon><span class="menuItem">AgentCompass 测评</span></el-menu-item>
                <el-menu-item index="/datasets/manage"><el-icon><Files /></el-icon><span class="menuItem">我的数据资源</span></el-menu-item>""")
layout = layout.replace('<!-- 导航入口 - 居中 -->', '<!-- Yellow navigation, shared authentication and local adapter -->')
layout = layout.replace('<div style="margin-right: 20px; flex-shrink: 0;">', '<div style="margin-right: 20px; flex-shrink: 0;"><el-button link @click="router.push(\'/password/change\')">账户安全</el-button>')
layout = re.sub(r'window\.open\([^;]+;', "router.push('/operations');", layout)
write('src/components/visualization.vue', layout)

main = (ORIGINAL / 'src/main.js').read_text(encoding='utf-8-sig')
main = re.sub(r"import './dataPipeline/dataPipeline.global.css'", "import './platformNetwork.js'", main)
main = main.replace('app.use(router)\napp.use(createPinia())', 'app.use(createPinia())\napp.use(router)')
write('src/main.js', main)
write('src/App.vue', '''<script setup>
import {watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import Visualizaton from './components/visualization.vue'
import {useAuth} from './blue/stores/auth.js'
import {useAIModelStore} from './stores/aiModel.js'
const route=useRoute(), router=useRouter(), auth=useAuth(), models=useAIModelStore()
watch(()=>auth.token,async token=>{if(token){if(await auth.refreshProfile()) await models.fetchModels();else router.replace('/login')}},{immediate:true})
</script>
<template><router-view v-if="route.meta.authPage"/><Visualizaton v-else/></template>''')

constants = read('src/utils/Constants.js')
end = constants.index('export const DEFAULT_CONFIG')
constants = '''export const URLS={BASE:window.location.origin,BASE_HTTPS:window.location.origin,SESSION:'/api/auth/me',WS:'/ws/monitor'};
export const STRINGS={EMPTY:'',DASH:'-'};
export const API_BASE_URL='/v1/';
export const API_AGENT_URL='/v1/';
export const DATA_FACTORY_API='/v1/data-factory/';
export const DATA_FACTORY_LOG_WS=(location.protocol==='https:'?'wss://':'ws://')+location.host+'/v1/data-factory/';
export const DEPLOY_API_BASE='/v1/deployment/';
export const API_MENSHEN_URL='/v1/performance';
export const PAYLOAD_MENSHEN={product:'LLM'};
''' + constants[end:]
write('src/utils/Constants.js', constants)
write('src/consts/copyrightConsts.js', '''export const evaluator_list={includes:()=>!!localStorage.getItem('ic_token')};
export const manager_list={includes:()=>localStorage.getItem('ic_role')==='admin'};''')

auth = read('src/blue/stores/auth.js')
auth = auth.replace("localStorage.setItem('ic_user', username.value)", "localStorage.setItem('ic_user', username.value)\n    localStorage.setItem('username', username.value)")
auth = auth.replace("localStorage.removeItem('ic_user')", "localStorage.removeItem('ic_user')\n    localStorage.removeItem('username')")
write('src/blue/stores/auth.js',auth)
login = read('src/blue/views/Login.vue').replace('用户名登录','手机号登录').replace('用户名', '手机号 / 管理员账号').replace('请输入账号', '请输入手机号')
write('src/blue/views/Login.vue',login)

chat = read('src/components/experienceCenter/textConversation.vue')
chat = chat.replace('&& modelWhiteName.includes(id)', '')
write('src/components/experienceCenter/textConversation.vue', chat)
models = read('src/stores/aiModel.js').replace('state.models.find(m => m.status && m.is_available).model_id', "state.models.find(m => m.status && m.is_available)?.model_id || ''")
write('src/stores/aiModel.js',models)

write('vite.config.js', '''import {fileURLToPath,URL} from 'node:url'
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({plugins:[vue()],resolve:{alias:{'@':fileURLToPath(new URL('./src',import.meta.url))}},
  build:{sourcemap:false},server:{host:'127.0.0.1',port:5174,proxy:{'/api':'http://127.0.0.1:8081','/v1':'http://127.0.0.1:8081','/ws':{target:'ws://127.0.0.1:8081',ws:true}}}})''')
print('Yellow frontend prepared with isolated Blue extensions')
