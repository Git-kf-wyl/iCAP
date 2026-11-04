<script setup>
import {readCacheStatus,retryReads} from '../readCache.js'
</script>
<template>
  <div v-if="readCacheStatus.stale" class="read-cache-status" role="status">
    连接暂时不稳定，当前显示已保存的数据。<button @click="retryReads">重新同步</button>
  </div>
</template>
<style scoped>
.read-cache-status{position:fixed;right:24px;bottom:20px;z-index:2050;padding:10px 16px;border:1px solid #e4d4a2;border-radius:8px;background:#fffbea;color:#735b21;font-size:13px;box-shadow:0 2px 12px #0001}
button{margin-left:8px;border:0;background:none;color:#337ecc;cursor:pointer}
</style>
