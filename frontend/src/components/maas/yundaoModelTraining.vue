<template>
  <div class="yundao-model-training-container">
    <iframe
      :src="trainingSrc"
      class="training-frame"
      width="100%"
      height="100%"
      frameborder="0"
    ></iframe>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const TRAINING_URL =
  'https://csb.roma.huawei.com/csb/#/hec/eiwizard/training/com.huawei.cloudcore.aidata.governance/trainingjobv2'

const trainingSrc = computed(() => {
  const url = new URL(TRAINING_URL)
  const token = new URL(window.location.href).searchParams.get('token')
  if (token) {
    url.searchParams.set('token', token)
  }
  return url.href
})
</script>

<style scoped>
.yundao-model-training-container {
  width: 100%;
  height: calc(100vh - 80px);
  overflow: hidden;
}

.training-frame {
  display: block;
  border: none;
}
</style>