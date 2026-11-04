<script setup>
import {defineAsyncComponent} from 'vue'
import {useRoute} from 'vue-router'
const route=useRoute()
const Visualization=defineAsyncComponent(()=>import('./components/visualization.vue'))
</script>
<template><router-view v-if="route.meta.authPage"/><Visualization v-else/></template>
