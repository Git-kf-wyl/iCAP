<script setup>

</script>

<template>
  <div class="deployment-view">
    <div class="fuyao-deployment-view-wrapper">
      <iframe class="fuyao-deployment-view" src="https://fuyao.rnd.huawei.com/modelDeployTask?formType=create"/>
    </div>
  </div>
</template>

<style scoped>

.deployment-view {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
  padding: 20px 16px 8px 16px;
  background-color: #f6f6f8;
}

.fuyao-deployment-view-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.fuyao-deployment-view {
  position: relative;
  --sidebar-width: 267px;
  --header-hight: 55px;
  width: calc(100% + var(--sidebar-width) + 2px);
  height: calc(100% + var(--header-hight) + 2px);
  left: calc(-1 * var(--sidebar-width));
  top: calc(-1 * var(--header-hight));
}

</style>