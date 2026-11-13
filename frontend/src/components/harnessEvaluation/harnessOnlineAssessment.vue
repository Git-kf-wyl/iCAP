<script setup>
import { ref } from 'vue'
const failed = ref(false)
</script>
<template>
  <section class="harness-lab-container">
    <div v-if="failed" role="alert">评测观测服务连接失败，请稍后刷新重试。</div>
    <iframe
      src="/harness-lab/harness"
      title="Harness 评测与调用链监控"
      referrerpolicy="same-origin"
      @error="failed = true"
    />
  </section>
</template>
<style scoped>
.harness-lab-container { height: calc(100vh - 96px); min-height: 600px; background: #fafafa; }
iframe { display: block; width: 100%; height: 100%; border: 0; }
</style>
