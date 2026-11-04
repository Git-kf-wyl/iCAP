<script lang="ts" setup>
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { addLogData, getLogData } from "@/api/dataService.js";

const token = ref("");
const embeddedUrl = ref("https://hjfy.top/");

const text = ref("");

const submit = () => {
  // 定义正则表达式，用于校验URL格式
  const urlPattern = /^(.*?)\S{4}\.\S{5}(v\d+)?$/;
  const regex = /\b\d{4}\.\d{4,5}(?:v\d+)?\b/g;
  // 校验text.value的值
  if (urlPattern.test(text.value)) {
    // 校验通过，解析id
    const id = text.value.match(regex);
    // console.log('id')
    // console.log(id)
    // 打开新页面
    window.open(`https://hjfy.top/arxiv/${id}`, "_blank");
    addLogData({
      user_id: token.value,
      timestamp: Date.now(),
      type: "hjfy",
      content: {
        url: id[0],
      },
    })
      .then((response) => {
        console.log(response);
        loadHistory();
      })
      .catch((e) => {
        console.log("日志添加失败，error：" + e);
      });
  } else {
    // 校验不通过，提示用户
    ElMessage({
      message: "请输入正确的URL格式，例如: https://arxiv.org/abs/1706.03762",
      type: "warning",
    });
  }
};

const allLogData = ref([
  // {
  //   active: true,
  //   content: {
  //     url: "1706.03762",
  //   },
  //   timestamp: 1765175700955,
  //   type: "hjfy",
  //   user_id: "w30076576",
  // },
  // {
  //   active: true,
  //   content: {
  //     url: "2512.01870v1",
  //   },
  //   timestamp: 1765175701955,
  //   type: "hjfy",
  //   user_id: "w30076576",
  // },
]);

const formatDate = (timestamp) => {
  if (!timestamp) return "";

  const date = new Date(Number(timestamp));
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, "0");
  const day = date.getDate().toString().padStart(2, "0");
  const hours = date.getHours().toString().padStart(2, "0");
  const minutes = date.getMinutes().toString().padStart(2, "0");
  const seconds = date.getSeconds().toString().padStart(2, "0");

  return `${year}-${month}-${day}  ${hours}:${minutes}:${seconds}`;
};

const loadHistory = async () => {
  const response = await getLogData({
    user_id: token.value,
    type: "hjfy",
  });
  const data = response.data;
  allLogData.value = data.data;
};

onMounted(async () => {
  token.value = localStorage.getItem("username");
  await loadHistory();
});
</script>

<template>
  <div class="chatCenterContainer">
    <!-- <div style="height: 100%;"> -->
    <!-- <iframe :src="embeddedUrl" width="100%" height="100%" frameborder="0"></iframe> -->
    <!-- </div> -->
    <div class="header">
      <div class="flex items-center">
        <span class="shrink-0" aria-label="Home">
          <img alt="logo" class="h-8 w-8" src="/images/hjfy.png" />
        </span>
        <div class="pl-2">幻觉翻译</div>
      </div>
    </div>
    <div
      class="max-w-screen relative grid flex-1 grid-cols-[1fr_2.5rem_auto_2.5rem_1fr] grid-rows-[2rem_1px_auto_1px_1fr] [--pattern-fg:var(--color-gray-950)]/5"
    >
      <div class="col-start-3 row-start-3 flex flex-col p-4">
        <div class="w-full">
          <div class="relative right-0">
            <ul
              class="relative flex flex-wrap px-2 py-2 list-none rounded-full bg-stone-100 dark:bg-stone-800"
            >
              <li class="z-30 flex-auto text-center">
                <a
                  style="cursor:auto;"
                  class="z-30 flex items-center justify-center w-full px-0 py-2 text-sm mb-0 transition-all ease-in-out border-0 rounded-md cursor-pointer text-slate-600 dark:text-slate-400 hover:text-indigo-500"
                >
                  <img
                    class="w-4 h-4 mr-1"
                    src="data:image/svg+xml,%3csvg%20id='logomark'%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2017.732%2024.269'%3e%3cg%20id='tiny'%3e%3cpath%20d='M573.549,280.916l2.266,2.738,6.674-7.84c.353-.47.52-.717.353-1.117a1.218,1.218,0,0,0-1.061-.748h0a.953.953,0,0,0-.712.262Z'%20transform='translate(-566.984%20-271.548)'%20fill='%23bdb9b4'/%3e%3cpath%20d='M579.525,282.225l-10.606-10.174a1.413,1.413,0,0,0-.834-.5,1.09,1.09,0,0,0-1.027.66c-.167.4-.047.681.319,1.206l8.44,10.242h0l-6.282,7.716a1.336,1.336,0,0,0-.323,1.3,1.114,1.114,0,0,0,1.04.69A.992.992,0,0,0,571,293l8.519-7.92A1.924,1.924,0,0,0,579.525,282.225Z'%20transform='translate(-566.984%20-271.548)'%20fill='%23b31b1b'/%3e%3cpath%20d='M584.32,293.912l-8.525-10.275,0,0L573.53,280.9l-1.389,1.254a2.063,2.063,0,0,0,0,2.965l10.812,10.419a.925.925,0,0,0,.742.282,1.039,1.039,0,0,0,.953-.667A1.261,1.261,0,0,0,584.32,293.912Z'%20transform='translate(-566.984%20-271.548)'%20fill='%23bdb9b4'/%3e%3c/g%3e%3c/svg%3e"
                    alt="arXiv 论文"
                  />arXiv 论文
                </a>
              </li>
            </ul>
          </div>
        </div>
        <div class="pt-4">
          <div class="rounded-xl text-sm/7 text-gray-700 dark:text-gray-100">
            <p class="mb-2">
              输入 arXiv 地址或 ID，或点击这几个示例：
              <a
                class="text-zinc-950 dark:text-zinc-100 underline decoration-zinc-950/50 data-hover:decoration-zinc-950 mr-2"
                href="https://hjfy.top/arxiv/2501.14787"
                target="_blank"
              >2501.14787</a>
              <a
                class="text-zinc-950 dark:text-zinc-100 underline decoration-zinc-950/50 data-hover:decoration-zinc-950 mr-2"
                href="https://hjfy.top/arxiv/2503.06072"
                target="_blank"
              >2503.06072</a>
              <a
                class="text-zinc-950 dark:text-zinc-100 underline decoration-zinc-950/50 data-hover:decoration-zinc-950 mr-2"
                href="https://hjfy.top/arxiv/2412.05265"
                target="_blank"
              >2412.05265</a>
            </p>
            <form>
              <!-- <input name="arxivInput" type="text" placeholder="https://arxiv.org/abs/1706.03762"
              class="py-2 px-4 bg-white dark:bg-stone-900 block w-full border border-gray-300 rounded-lg transition-all duration-200 ease-in sm:text-sm outline-none focus:border-slate-900 focus:ring-3 focus:ring-slate-300" />-->
              <el-form @submit.native.prevent="submit">
                <el-input
                  v-model="text"
                  placeholder="https://arxiv.org/abs/1706.03762"
                  @keyup.enter.native="submit"
                ></el-input>
                <p class="mt-2 text-sm text-red-600" id="email-error"></p>
                <div class="mt-4">
                  <el-button
                    type="submit"
                    @click="submit"
                    class="rounded-md bg-slate-900 dark:bg-slate-500 px-4 py-2 text-sm font-semibold text-white cursor-pointer transition-all duration-300 ease-in shadow-xs hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-600"
                  >翻译</el-button>
                </div>
              </el-form>
              <div class="mt-4">
                <p>近期访问的 arXiv 论文</p>
                <!-- 动态渲染日志条目 -->
                <div
                  v-for="(log, index) in allLogData"
                  :key="index"
                  class="text-ellipsis flex between"
                >
                  <!-- class="text-zinc-950 dark:text-zinc-100 underline decoration-zinc-950/50 data-hover:decoration-zinc-950 mr-2" -->
                  <el-link
                    v-if="log.active"
                    :href="`https://hjfy.top/arxiv/${log.content.url}`"
                    target="_blank"
                  >
                    <!-- 显示arXiv编号 -->
                    <span class="font-mono">[{{ log.content.url }}]</span>
                    <!-- 仅当存在标题时显示 -->
                    {{ log.content.title ? ' ' + log.content.title : '' }}
                  </el-link>
                  <span>{{formatDate(log.timestamp)}}</span>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>
      <div
        class="relative right-px col-start-2 row-span-full row-start-1 border-x border-x-(--pattern-fg) bg-[image:repeating-linear-gradient(315deg,_var(--pattern-fg)_0,_var(--pattern-fg)_1px,_transparent_0,_transparent_50%)] bg-[size:10px_10px] bg-fixed"
      ></div>
      <div
        class="relative left-px col-start-4 row-span-full row-start-1 border-x border-x-(--pattern-fg) bg-[image:repeating-linear-gradient(315deg,_var(--pattern-fg)_0,_var(--pattern-fg)_1px,_transparent_0,_transparent_50%)] bg-[size:10px_10px] bg-fixed"
      ></div>
      <div class="relative -bottom-px col-span-full col-start-1 row-start-2 h-px bg-(--pattern-fg)"></div>
      <div class="relative -top-px col-span-full col-start-1 row-start-4 h-px bg-(--pattern-fg)"></div>
    </div>
  </div>
</template>

<style scoped>
.chatCenterContainer {
  box-sizing: border-box;
  /* padding: 28px; */
  background-color: rgb(245, 245, 245);
  width: 100%;
  height: 100%;
  /* min-height: 100vh; */
  display: flex;
  flex-direction: column;
  justify-content: stretch;
  align-items: stretch;
  /* gap: 16px; */
  /* overflow: hidden; */
}

.header {
  padding-inline: 0.5rem;
  border-top-color: color-mix(in oklab,
      oklch(0.13 0.028 261.692) 5%,
      transparent);
  border-bottom-color: oklab(0.13 -0.00404584 -0.0277062 / 0.05);
  border-bottom-width: 1px;
  background-color: #fff;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.h-8 {
  height: 3rem;
}

.w-8 {
  width: 3rem;
}

.pl-2 {
  padding-left: 0.5rem;
  font-size: 18px;
  font-weight: 700;
}

@supports (color: color-mix(in lab, red, red)) {
  .\[--pattern-fg\:var\(--color-gray-950\)\]\/5 {
    --pattern-fg: color-mix(in oklab, var(--color-gray-950) 5%, transparent);
  }
}

.\[--pattern-fg\:var\(--color-gray-950\)\]\/5 {
  --pattern-fg: #0307120d;
}

.grid-rows-\[2rem_1px_auto_1px_1fr\] {
  grid-template-rows: 2rem 1px auto 1px 1fr;
}

.grid-cols-\[1fr_2\.5rem_auto_2\.5rem_1fr\] {
  grid-template-columns: 1fr 2.5rem auto 2.5rem 1fr;
}

.flex-1 {
  flex: 1;
}

.max-w-screen {
  max-width: 100vw;
  background-color: #fff;
}

.grid {
  display: grid;
}

.relative {
  position: relative;
}

*,
:after,
:before,
::backdrop {
  box-sizing: border-box;
  border: 0 solid;
  margin: 0;
  padding: 0;
}

.p-4 {
  padding: 1rem;
}

.flex-col {
  flex-direction: column;
}

.row-start-3 {
  grid-row-start: 3;
}

.col-start-3 {
  grid-column-start: 3;
}

.w-full {
  width: 100%;
}

.right-0 {
  right: 0;
}

.py-2 {
  padding-block: 0.5rem;
}

.px-2 {
  padding-inline: 0.5rem;
}

.bg-stone-100 {
  /* background-color: oklch(97% 0.001 106.424); */
}

.rounded-full {
  border-radius: 3.40282e38px;
}

.flex-wrap {
  flex-wrap: wrap;
}

.list-none {
  list-style-type: none;
}

ol,
ul,
menu {
  list-style: none;
}

.text-center {
  text-align: center;
}

.flex-auto {
  flex: auto;
}

.z-30 {
  z-index: 30;
}

.justify-center {
  justify-content: center;
}

.ease-in-out {
  --tw-ease: cubic-bezier(.4, 0, .2, 1);
  transition-timing-function: cubic-bezier(.4, 0, .2, 1);
}

.transition-all {
  transition-property: all;
  transition-timing-function: var(--tw-ease,
      var(--default-transition-timing-function));
  transition-duration: calc(1.25 / .875)
}

.text-slate-600 {
  color: var(--color-slate-600);
}

.text-sm {
  font-size: 0.875rem;
  line-height: var(--tw-leading, var(--text-sm--line-height));
}

.px-0 {
  padding-inline: 0;
}

.border-0 {
  border-style: solid;
  border-width: 0;
}

.rounded-md {
  border-radius: var(--radius-md);
}

.justify-center {
  justify-content: center;
}

.items-center {
  align-items: center;
}

.cursor-pointer {
  cursor: pointer;
}

.w-full {
  width: 100%;
}

.mb-0 {
  margin-bottom: 0;
}

.z-30 {
  z-index: 30;
}

.w-4 {
  width: 2rem;
}

.h-4 {
  height: 2rem;
}

.mr-1 {
  margin-right: 2rem;
}

.duration-300 {
  --tw-duration: 0.3s;
  transition-duration: 0.3s;
}

.text-slate-700 {
  color: oklch(37.2% 0.044 257.287);
}

.text-center {
  text-align: center;
}

.bg-white {
  background-color: #fff;
}

.rounded-full {
  border-radius: 3.40282e38px;
}

.block {
  display: block;
}

.z-10 {
  z-index: 10;
}

.absolute {
  position: absolute;
}

.pt-4 {
  padding-top: 2rem;
}

.mb-2 {
  margin-bottom: 0.5rem;
}

.rounded-xl {
  border-radius: 0.75rem;
}

.text-sm\/7 {
  font-size: 0.875rem;
  line-height: calc(0.25rem * 7);
}

.text-gray-700 {
  color: oklch(37.3% 0.034 259.733);
}

.underline {
  text-decoration-line: underline;
}

.text-zinc-950 {
  color: oklch(14.1% 0.005 285.823);
}

.mr-2 {
  margin-right: 0.5rem;
}

.decoration-zinc-950\/50 {
  text-decoration-color: color-mix(in oklab,
      oklch(14.1% 0.005 285.823) 50%,
      transparent);
}

.outline-none {
  --tw-outline-style: none;
  outline-style: none;
}

.sm\:text-sm {
  font-size: 0.875rem;
  line-height: calc(1.25 / 0.875);
}

.ease-in {
  --tw-ease: cubic-bezier(.4, 0, 1, 1) transition-timing-function: cubic-bezier(.4, 0, 1, 1)
}

.bg-slate-900 {
  background-color: oklch(20.8% .042 265.755);
}

.text-white {
  color: #fff
}

.px-4 {
  padding-inline: 1rem
}

.rounded-md {
  border-radius: .375rem;
}

.mt-4 {
  margin-top: 1rem
}

.bg-fixed {
  background-attachment: fixed;
}

.bg-\[size\:10px_10px\] {
  background-size: 10px 10px;
}

.bg-\[image\:repeating-linear-gradient\(315deg\,_var\(--pattern-fg\)_0\,_var\(--pattern-fg\)_1px\,_transparent_0\,_transparent_50\%\)\] {
  background-image: repeating-linear-gradient(315deg, color-mix(in oklab, oklch(13% .028 261.692)5%, transparent) 0, color-mix(in oklab, oklch(13% .028 261.692)5%, transparent) 1px, transparent 0, transparent 50%);
}

.border-x-\(--pattern-fg\) {
  border-inline-color: color-mix(in oklab, oklch(13% .028 261.692)5%, transparent);
}

.row-span-full {
  grid-row: 1 / -1;
}

.row-start-1 {
  grid-row-start: 1;
}

.col-start-2 {
  grid-column-start: 2;
}

.right-px {
  right: -1px;
}

.left-px {
  left: -1px;
}

.col-start-4 {
  grid-column-start: 4;
}

.h-px {
  height: 1px;
}

.row-start-2 {
  grid-row-start: 2;
}

.row-start-4 {
  grid-row-start: 4;
}

.col-start-1 {
  grid-column-start: 1;
}

.-bottom-px {
  bottom: -1px;
}

.col-span-full {
  grid-column: 1 / -1;
}

.-top-px {
  top: -1px;
}

.border-x {
  border-inline-start-style: solid;
  border-inline-end-style: solid;
  border-inline-width: 1px;
}

.text-sm\/7 {
  font-size: .875rem;
  line-height: calc(.25rem * 7);
}

.border-gray-300 {
  border-color: oklch(87.2% .01 258.338) !important;
}

.border {
  border: solid 1px;
}

.rounded-lg {
  border-radius: .5rem
}

.shrink-0 {
  flex-shrink: 0;
}

.bg-\(--pattern-fg\) {
    background-color: color-mix(in oklab,oklch(13% .028 261.692) 5%, transparent);
}

.text-ellipsis {
  text-overflow: ellipsis;
}

.between{
  justify-content: space-between;
}
</style>