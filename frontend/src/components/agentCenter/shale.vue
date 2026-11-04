<script lang="ts" setup>
import {ref, onMounted, onBeforeUnmount} from 'vue';
import axios from 'axios';
import {SHALE_URL, DEFAULT_CONFIG} from "@/utils/Constants.js";
const embeddedUrl = ref('');
// const embeddedUrl = ref(
//   "http://6080-iqoveibukjjt110hk3c8p.service.consul:3002/vnc.html?autoconnect=true&resize=scale"
// );

const loading = ref(true);
const error = ref(null);
const userid = ref("");
// �Ӻ�˻�ȡ��̬URL
const fetchVncUrl = async () => {
  // try {
  //   // const response = await axios.get('/api/get-vnc-url'); // �滻Ϊʵ��API·��
  //   userid.value = localStorage.getItem('username');
  //   const response = await axios.post(`${SHALE_URL}create-sandbox`, {
  //     user_id: userid.value
  //   }, DEFAULT_CONFIG);
  //   if (response.data && response.data.desktop_url) {
  //     const dynamicUrl = response.data.desktop_url;
  //
  //     // ��ȫУ�飺ȷ����Consul����
  //     if (!dynamicUrl.includes('.service.consul')) {
  //       throw new Error('��Ч��URL����');
  //     }
  //
  //     // ��URL����󴫵ݸ�Nginx����
  //     const encodedUrl = encodeURIComponent(dynamicUrl);
  //     embeddedUrl.value = `/vnc-proxy?url=${encodedUrl}`;
  //   } else {
  //     throw new Error('���δ������ЧURL');
  //   }
  // } catch (err) {
  //   console.error('��ȡVNC URLʧ��:', err);
  //   error.value = err.message || '��ȡ���ӵ�ַʧ��';
  // } finally {
  //   loading.value = false;
  // }
  const dynamicUrl = "http://6080-indqwplux1hp1w7jbrbd6.service.consul:3002/vnc.html?autoconnect=true&resize=scale";   // &resize=scale
  const timestamp = Date.now();  // ��ǰʱ���
  const encodedUrl = encodeURIComponent(dynamicUrl);
  embeddedUrl.value = `/vnc-proxy?url=${encodedUrl}&_t=${timestamp}`;
  console.log(embeddedUrl.value)
  // const base64Url = btoa(dynamicUrl);  // Base64 ����
  // embeddedUrl.value = `/vnc-proxy?b64=${base64Url}`;
  loading.value = false;
};

onMounted(() => {
  fetchVncUrl();
});

onBeforeUnmount(() => {
  embeddedUrl.value = "";
});

</script>

<!--<template>-->
<!--  <div class="chatCenterContainer">-->
<!--    <div style="height: 100%;">-->
<!--      <iframe :src="embeddedUrl" width="100%" height="100%" frameborder="0"></iframe>-->
<!--    </div>-->
<!--  </div>-->
<!--</template>-->
<template>
  <div class="chatCenterContainer">
    <div v-if="loading" style="height: 100%; display: flex; align-items: center; justify-content: center;">
      <div>��������VNC...</div>
    </div>

    <div v-else-if="error" style="height: 100%; display: flex; align-items: center; justify-content: center; color: red;">
      <div>{{ error }}</div>
    </div>

    <div v-else style="height: 100%;">
      <iframe
        :src="embeddedUrl"
        width="100%"
        height="100%"
        frameborder="0"
        allow="clipboard-read; clipboard-write"
        style="border: none;"
      ></iframe>
    </div>
  </div>
</template>

<style scoped>
.chatCenterContainer {
  box-sizing: border-box;
  padding: 28px;
  background-color: rgb(245, 245, 245);
  width: 100%;
  height: 100%;
  /* min-height: 100vh; */
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  gap: 16px;
  /* overflow: hidden; */
}
</style>