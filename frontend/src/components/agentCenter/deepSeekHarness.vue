<script setup>
import { useRouter } from 'vue-router'
const router=useRouter()
</script>
<template><div style="padding:32px;background:#fff;border-radius:8px;margin:20px"><el-result icon="info" title="此扩展服务尚未部署" sub-title="原工程通过外部服务提供此功能，仓库中未包含其服务端。可先使用智能对话或 Skill 自进化。"><template #extra><el-button type="primary" @click="router.push('/chat')">智能对话</el-button><el-button @click="router.push('/skill-evolution')">Skill 自进化</el-button></template></el-result></div></template>