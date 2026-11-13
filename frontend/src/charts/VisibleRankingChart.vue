<script setup>
import {defineAsyncComponent, onMounted, onBeforeUnmount, ref} from 'vue'
const props = defineProps({data: {type: Array, required: true}, title: {type: String, default: ''}})
const Chart = defineAsyncComponent(() => import('./rankingScoreBarChart.vue'))
const host = ref(null)
const visible = ref(false)
let observer
onMounted(() => {
  if (typeof IntersectionObserver === 'undefined') {visible.value = true; return}
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      visible.value = true
      observer.disconnect()
    }
  }, {rootMargin: '150px'})
  observer.observe(host.value)
})
onBeforeUnmount(() => observer?.disconnect())
</script>
<template>
  <div ref="host" class="visible-ranking-chart">
    <Chart v-if="visible" :data="props.data" :title="props.title" />
    <div v-else class="chart-placeholder" aria-hidden="true"></div>
  </div>
</template>
<style scoped>
.visible-ranking-chart,.chart-placeholder{width:100%;height:100%;min-height:120px}
</style>
