import {useAuth} from '../blue/stores/auth.js'
import { createRouter, createWebHistory } from 'vue-router';
const homePage = () => import('@/components/homePage.vue');
const rankingScore = () => import('../components/rankingScore/rankingScore.vue');
const rankingDetails = () => import('../components/rankingScore/rankingDetails.vue');
const multiRankingDetails = () => import('../components/rankingScore/multiRankingDetails.vue');
const evaluationReport = () => import('../components/rankingScore/evaluationReport.vue');
const textConversation = () => import('@/components/experienceCenter/textConversation.vue');
const chatPage = () => import('@/components/experienceCenter/textConversation.vue');
const onlineAssessment = () => import('@/components/modelEvaluation/onlineAssessment.vue');
const datasetRegister = () => import('@/components/dataCenter/datasetDevelopmentForm/datasetRegister.vue');
const datasetDetail = () => import('@/components/dataCenter/datasetDevelopmentForm/datasetDetail.vue');
const evalDatasetDevelopment = () => import('@/components/dataCenter/evalDatasetDevelopment.vue');
const trainDatasetDevelopment = () => import('@/components/dataCenter/trainDatasetDevelopment.vue');
const huggingfaceDownload = () => import('@/components/dataCenter/huggingfaceDownload.vue');
const modelscopeDownload = () => import('@/components/dataCenter/modelscopeDownload.vue');
const modelSquare = () => import('@/components/modelSquare/modelSquare.vue');
const modelRegister = () => import('@/components/modelSquare/modelSquareForms/modelSquareForms.vue');
const modelDetails = () => import('@/components/modelSquare/modelDetails.vue');
const TaskDetail = () => import('@/components/modelEvaluation/onlineAssessmentForms/taskDetail.vue');
const ResultDetail = () => import('@/components/modelEvaluation/onlineAssessmentForms/resultDetail.vue');
const modelSelection = () => import('@/components/modelTypeSelection/modelSelection.vue');
const deploymentView = () => import('@/components/deploymentView/deploymentView.vue');
const modelDeploy = () => import('@/components/deploymentView/modelDeploy.vue');
const modelConfig = () => import('@/components/dataCenter/modelConfig.vue');
const modelComparison = () => import('@/components/rankingScore/modelComparison.vue');
const datasetComparison = () => import('@/components/rankingScore/datasetComparison.vue');
const dify = () => import('@/components/agentCenter/dify.vue');
const coze = () => import('@/components/agentCenter/coze.vue');
const owl = () => import('@/components/agentCenter/owl.vue');
const officeAssistant = () => import('@/components/agentCenter/officeAssistant.vue');
const onlineEvaluation = () => import('@/components/modelEvaluation/onlineEvaluation.vue');
const languageEvaluation = () => import('@/components/modelEvaluation/languageEvaluation.vue');
const multipleEvaluation = () => import('@/components/modelEvaluation/multipleEvaluation.vue');
const statistics = () => import('@/components/statistics/statistics.vue');
const interpretation = () => import('@/components/modelEvaluation/interpretation/index.vue');
const interpretationResult = () => import('@/components/modelEvaluation/interpretationResult.vue');
const modelEvalReportProgress = () => import('@/components/modelEvaluation/modelEvalReportProgress.vue');
const evaluationResultList = () => import('@/components/modelEvaluation/evaluationResult.vue');
const shale = () => import('@/components/agentCenter/shale.vue');
const deepResearch = () => import('@/components/agentCenter/deepResearch.vue');
const hjfy = () => import('@/components/agentCenter/hjfy.vue');
// promptOptimizer 已下线，保留 import 供后续恢复
// import promptOptimizer from '@/components/agentCenter/promptOptimizer.vue';
const paperAgent = () => import('@/components/agentCenter/paperAgent.vue');
const arXivDailyResults = () => import('@/components/agentCenter/arXivDailyResults.vue');
const datasetAnnotation = () => import('@/components/dataCenter/datasetAnnotation.vue');
const collectionVisualization = () => import('@/components/dataCenter/collectionVisualization.vue');
const HomeVisualization = () => import('@/components/dataCenter/HomeVisualization.vue');
const DeviceDetailVisualization = () => import('@/components/dataCenter/DeviceDetailVisualization.vue');
const vlaDataSceneView = () => import('@/components/dataCenter/vlaDataOverview/vlaDataSceneView.vue');
const vlaDataAppView = () => import('@/components/dataCenter/vlaDataOverview/vlaDataAppView.vue');
const LMArenaDetails = () => import('@/components/rankingScore/LMArenaDetails.vue');
const ReportGenerationPanel = () => import('@/components/evaluationReport/ReportGenerationPanel.vue');
const PublishedReport = () => import('@/components/evaluationReport/publishedReport.vue');
const ReportPreview = () => import('@/components/evaluationReport/reportPreview.vue');
const UserStatistics = () => import('@/components/userStatistics/userStatistics.vue');
const deepSeekHarness = () => import('@/components/agentCenter/deepSeekHarness.vue');
const evalMapView = () => import('@/components/dataCenter/evalMapView.vue');
const router = createRouter({
    history: createWebHistory(),
    routes: [
        { path: '/', component: homePage },

        { path: '/chat', component: chatPage },
        { path: '/rankingScore', component: rankingScore },
        { path: '/rankingScore/RankingDetails', component: rankingDetails },
        { path: '/rankingScore/MultiRankingDetails', component: multiRankingDetails },
        { path: '/rankingScore/LMArenaDetails', component: LMArenaDetails },
        { path: '/EvaluationReport', component: ReportGenerationPanel },
        { path: '/PublishedReport', component: PublishedReport },
        { path: '/PublishedReport/preview', name: 'ReportPreview', component: ReportPreview },
        { path: '/rankingScore/ModelComparison', component: modelComparison },
        { path: '/rankingScore/DatasetComparison', component: datasetComparison },
        { path: '/deployment', component: deploymentView },
        { path: '/modelDeploy', component: modelDeploy },
        { path: '/agentCenter/dify', component: dify },
        { path: '/agentCenter/coze', component: coze },
        { path: '/agentCenter/owl', component: owl },
        { path: '/agentCenter/officeAssistant', component: officeAssistant },
        { path: '/agentCenter/shaleComputer', component: shale },
        { path: '/agentCenter/deepResearch', component: deepResearch },
        { path: '/agentCenter/hjfy', component: hjfy },
        // promptOptimizer 已下线
        // { path: '/agentCenter/promptOptimizer', component: promptOptimizer },
        { path: '/agentCenter/arxivDailyResults', component: paperAgent, name: 'arxivDailyResults' },
        { path: '/agentCenter/paperAgent', component: arXivDailyResults, name: 'paperAgent' },
        {
            path: '/modelEvaluation/modelEvalReportProgress',
            name: 'modelEvalReportProgress',
            component: modelEvalReportProgress,
        },
        {
            path: '/modelEvaluation/onlineAssessment',
            name: 'onlineAssessment',
            component: onlineAssessment,
        },
        {
            path: '/modelEvaluation/multipleEvaluation/evaluationResult',
            name: 'evaluationResult',
            component: interpretationResult,
        },
        {
            path: '/modelEvaluation/evaluationResult',
            name: 'evaluationResultList',
            component: evaluationResultList,
        }, {
            path: '/modelEvaluation/languageEvaluation',
            name: 'languageEvaluation',
            component: languageEvaluation,
        }, {
            path: '/modelEvaluation/multipleEvaluation',
            name: 'multipleEvaluation',
            component: multipleEvaluation,
        }, {
            path: '/modelEvaluation/multipleEvaluation/interpretation',
            name: 'interpretation',
            component: interpretation,
        },
        {
            path: '/modelEvaluation/onlineAssessment/taskDetail',
            name: 'taskDetail',
            component: TaskDetail,
        },
        {
            path: '/modelEvaluation/evaluationResult/resultDetail',
            name: 'resultDetail',
            component: ResultDetail,
        },
        {
            path: '/modelEvaluation/onlineEvaluation',
            name: 'onlineEvaluation',
            component: onlineEvaluation,
        },
        { path: '/dataCenter/evalDatasetDevelopment', name: 'evalDatasetDevelopment', component: evalDatasetDevelopment },
        { path: '/dataCenter/trainDatasetDevelopment', name: 'trainDatasetDevelopment', component: trainDatasetDevelopment },
        { path: '/dataCenter/huggingfaceDownload', name: 'huggingfaceDownload', component: huggingfaceDownload },
        { path: '/dataCenter/modelscopeDownload', name: 'modelscopeDownload', component: modelscopeDownload },
        { path: '/dataCenter/modelConfig', name: 'modelConfig', component: modelConfig },
        { path: '/dataCenter/datasetAnnotation', name: 'datasetAnnotation', component: datasetAnnotation },
        { path: '/dataCenter/collectionVisualization', name: 'collectionVisualization', component: collectionVisualization },
        { path: '/dataCenter/homeVisualization', name: 'homeVisualization', component: HomeVisualization },
        { path: '/dataCenter/deviceDetail/:id', name: 'deviceDetail', component: DeviceDetailVisualization },
        { path: '/dataCenter/vlaDataOverview/vlaDataSceneView', name: 'vlaDataSceneView', component: vlaDataSceneView },
        { path: '/dataCenter/vlaDataOverview/vlaDataAppView', name: 'vlaDataAppView', component: vlaDataAppView },
        { path: '/dataCenter/evalDatasetDevelopment/datasetRegister', name: 'datasetRegister', component: datasetRegister },
        { path: '/dataCenter/evalDatasetDevelopment/datasetDetail', name: 'datasetDetail', component: datasetDetail },
        // 评测地图（llm_bench 集成）
        { path: '/evalMap', name: 'evalMapOverview', component: evalMapView },
        { path: '/evalMap/benchmarks', name: 'evalMapBenchmarks', component: evalMapView },
        { path: '/evalMap/capabilities', name: 'evalMapCapabilities', component: evalMapView },
        { path: '/evalMap/vendors', name: 'evalMapVendors', component: evalMapView },
        { path: '/evalMap/compare', name: 'evalMapCompare', component: evalMapView },
        { path: '/evalMap/methodology', name: 'evalMapMethodology', component: evalMapView },
        { path: '/modelSquare', component: modelSquare },
        { path: '/modelSquare/edit', component: modelRegister, name: 'modelRegister' },
        { path: '/modelSelection', component: modelSelection },
        { path: '/modelSquare/details', component: modelDetails, name: 'modelDetails' },
        { path: '/experienceCenter/textConversation', component: textConversation },
        { path: '/statistics', component: statistics },
        { path: '/userStatistics', component: UserStatistics },
        { path: '/userStatistics/eval', component: UserStatistics },
        { path: '/userStatistics/apikey', component: UserStatistics },
        { path: '/agentCenter/deepSeekHarness', component: deepSeekHarness },
        { path: '/skill-evolution', component: () => import('../integration/SkillEvolutionExtension.vue') },
        { path: '/models/manage', component: () => import('../integration/ModelsExtension.vue') },
        { path: '/datasets/manage', component: () => import('../integration/DatasetsExtension.vue') },
        { path: '/agentcompass', component: () => import('../integration/EvaluationsExtension.vue') },
        { path: '/operations', component: () => import('../integration/OperationsExtension.vue') },
        { path: '/login', component: () => import('../blue/views/Login.vue'), meta: { authPage: true, public: true } },
        { path: '/register', component: () => import('../blue/views/Register.vue'), meta: { authPage: true, public: true } },
        { path: '/password/reset', component: () => import('../blue/views/PasswordSecurity.vue'), meta: { authPage: true, public: true } },
        { path: '/password/change', component: () => import('../blue/views/PasswordSecurity.vue'), meta: { authPage: true, public: false } },
        { path: '/security-questions/setup', component: () => import('../blue/views/SecurityQuestionsSetup.vue'), meta: { authPage: true, public: false } },
        { path: '/models', redirect: '/modelSquare' },
        { path: '/leaderboard', redirect: '/rankingScore' },
        { path: '/datasets', redirect: '/dataCenter/evalDatasetDevelopment' },
        { path: '/evaluations', redirect: '/modelEvaluation/onlineAssessment' },
        { path: '/reports', redirect: '/PublishedReport' },
        { path: '/agents', redirect: '/chat' },
        { path: '/deployments', redirect: '/modelDeploy' },
        { path: '/:pathMatch(.*)*', redirect: '/' },
    ],
})
router.beforeEach(async to => {
    const token = localStorage.getItem('ic_token')
    if (!to.meta.public && !token) return {path:'/login',query:{redirect:to.fullPath}}
    if (token) {
        const valid=await useAuth().refreshProfile()
        if (!valid && !to.meta.public) return {path:'/login',query:{redirect:to.fullPath}}
        if (valid && to.meta.public) return '/'
    }
    document.title = 'InnovationCore AI Platform'
})
export default router;
