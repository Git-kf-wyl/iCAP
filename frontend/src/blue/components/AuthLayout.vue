<script setup>
import footer from '@/assets/loginFooter.png'
</script>
<template><div class="login-base"><main class="login-container"><h1>云核 AI 创新平台</h1><slot /></main><footer><img :src="footer" alt="InnovationCore AI"/><div>InnovationCore AI Platform</div></footer></div></template>
<style scoped>
.login-base{background:#8fc4f3;min-height:100vh;display:flex;flex-direction:column;align-items:center;color:#303133;font-family:Arial,"Microsoft YaHei",sans-serif;}
.login-container{background:#fafafa;width:min(440px,calc(100vw - 64px));box-sizing:border-box;margin:8vh auto 5vh;padding:32px;box-shadow:0 0 10px #0002;border-radius:8px;flex:1;}
h1{text-align:center;font-size:24px;font-weight:600;margin:0 0 28px;}.login-container :deep(h2){font-size:20px;margin:0 0 10px;}
.login-container :deep(.subtitle){color:#909399;font-size:13px;line-height:1.7;margin:8px 0 22px;}.login-container :deep(.el-form-item__label){color:#303133;font-weight:600;}
.login-container :deep(.el-input__wrapper){min-height:34px;}.login-container :deep(.el-button--primary){background:#56adff;border-color:#56adff;}.login-container :deep(a){color:#409eff;text-decoration:none;}
footer{width:100%;text-align:center;font-size:12px;color:#606266;background:white;}footer img{display:block;width:100%;max-height:130px;object-fit:cover;}footer div{padding:10px;}
@media(min-height:900px){.login-container{flex:0 1 auto;margin-top:15vh;}}
</style>
