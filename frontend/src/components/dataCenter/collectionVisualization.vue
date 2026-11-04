<template>
  <div class="collection-visualization">
    <iframe
      :src="pageUrl"
      class="full-iframe"
      frameborder="0"
      allowfullscreen
    ></iframe>
  </div>
</template>

<script setup>
const pageUrl = 'http://10.189.206.203:8000/'
</script>

<style scoped>
.collection-visualization {
  width: 100%;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.full-iframe {
  width: 100%;
  height: 100%;
  border: none;
}
</style>