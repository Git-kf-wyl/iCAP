<script setup>
import { computed } from 'vue'
import deepseekLogo from '../assets/deepseek.svg'

const props = defineProps({ model: { type: Object, required: true } })
const source = computed(() => props.model.logo_url ||
  (props.model.provider?.toLowerCase() === 'deepseek' ? deepseekLogo : '/images/icap-mark-v1.svg'))
</script>

<template>
  <span class="model-logo">
    <img :src="source" :alt="`${model.provider || 'iCAP'} Logo`" />
  </span>
</template>

<style scoped>
.model-logo { display:inline-flex; align-items:center; justify-content:center; flex:none; width:100px; height:44px; padding:5px; border-radius:10px; background:#f4f6fa; color:#40506b; font-size:16px; font-weight:800; }
.model-logo img { max-width:100%; max-height:100%; object-fit:contain; }
</style>
