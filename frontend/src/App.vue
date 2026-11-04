<script setup>
import {defineAsyncComponent} from 'vue'
import {useRoute} from 'vue-router'
import {navigationPending} from './navigation.js'
import PageLoading from './components/PageLoading.vue'
const route=useRoute()
const Visualization=defineAsyncComponent({loader:()=>import('./components/visualization.vue'),loadingComponent:PageLoading,delay:0})
</script>
<template>
  <div v-if="navigationPending" class="navigation-progress" role="status" aria-live="polite">正在打开页面…</div>
  <router-view v-if="route.meta.authPage"/><Visualization v-else/>
</template>
<style>
.navigation-progress{position:fixed;top:0;left:0;right:0;z-index:10000;height:3px;background:linear-gradient(90deg,#409eff,#a0cfff,#409eff);background-size:200% 100%;animation:icap-progress 1s linear infinite;color:#2878ee;font:13px/1.5 Arial,sans-serif;padding-top:6px;text-align:center;pointer-events:none}
@keyframes icap-progress{to{background-position:-200% 0}}
@media(prefers-reduced-motion:reduce){.navigation-progress{animation:none}}
</style>
