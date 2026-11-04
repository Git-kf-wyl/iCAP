# 云核 AI 创新平台 —— 前端实现说明书（总目录）

> 目标：任何人仅凭本套文档 + 源码仓库，即可**完整复现**该前端工程。
> 后端接口部分不在本说明书范围内（仅列出前端调用契约，便于对接）。

---

## 一、这套文档怎么读

| # | 文档 | 内容 | 适合谁 |
|---|------|------|--------|
| 00 | [00-工程总览.md](./00-工程总览.md) | 项目定位、技术栈、目录结构、启动方式、整体架构图 | 所有人（先读这篇） |
| 01 | [01-工程搭建与构建配置.md](./01-工程搭建与构建配置.md) | package.json、Vite 配置、依赖清单、构建产物、已知依赖缺口 | 负责跑起来的人 |
| 02 | [02-路由与导航架构.md](./02-路由与导航架构.md) | 全部路由表、主导航布局、菜单映射、权限名单 | 前端开发 |
| 03 | [03-状态管理.md](./03-状态管理.md) | Pinia stores + Vuex modules 全量清单与 state/action 明细 | 前端开发 |
| 04 | [04-API层与后端接口契约.md](./04-API层与后端接口契约.md) | 所有 API 模块、基础地址、端点清单、请求/响应约定 | 前后端联调 |
| 05 | [05-业务模块说明.md](./05-业务模块说明.md) | 按业务域逐个组件说明（模型广场/评测/数据中心/Agent/AI School/统计等） | 前端开发 |
| 06 | [06-数据治理Pipeline模块.md](./06-数据治理Pipeline模块.md) | dataPipeline 独立模块的深度说明（含状态机、3D 总览） | 维护数据飞轮的人 |
| 07 | [07-静态资源与二进制文件清单.md](./07-静态资源与二进制文件清单.md) | 全部图片/字体/Excel/PDF 等二进制资产清单与复现说明 | 复现者必读 |
| 08 | [08-复现指南与已知问题.md](./08-复现指南与已知问题.md) | 从零复现步骤、缺失依赖、已知 Bug、改造建议 | 复现者必读 |

---

## 二、一句话概括

这是一个基于 **Vue 3 (Composition API) + Vite 6 + Element Plus + ECharts + Pinia/Vuex** 的
**单页应用（SPA）**，中文界面，面向华为云核「AI 创新平台」，覆盖
**模型榜单 / 模型选型 / 模型广场 / 模型部署 / 数据中心 / 测评服务 / 评测地图 /
Agent 应用中心 / AI School / 运营看板 / 体验中心（文本·图像·语音·视频）/ 数据治理 Pipeline（数据飞轮）**
等十余个业务域。

工程内嵌了两个「子应用」：

1. `public/llm_bench/` —— 一个**纯静态原生 JS 应用**（Benchmark Atlas），通过 `<iframe>` 集成。
2. `src/dataPipeline/` —— 从 `AgenticDataFlywheel` 仓库迁入的**独立模块**（含 three.js 3D 总览）。

---

## 三、复现所需的最少步骤

```bash
# 1. 安装 Node（建议 18+/20+），进入工程根目录
cd frontEnd

# 2. 安装依赖（注意：package.json 缺少若干实际被引用的依赖，见 01 文档）
npm install

# 3. 补装缺失依赖（详见 01-工程搭建与构建配置.md 第 5 节）
npm i -D vitest
npm i lodash dayjs @vueuse/core three
npm i -D @vue-flow/core   # 仅当需要 Vue Flow 节点样式时

# 4. 启动开发服务器（端口固定 12096）
npm run dev

# 5. 生产构建
npm run build      # 产物在 dist/
npm run preview
```

> 后端地址硬编码在 `src/utils/Constants.js`，见 04 文档；`vite.config.js` 中另有
> `/api`、`/api1`、`/api2`、`/api3` 四个代理规则（见 01 文档第 3.2 节）。

---

## 四、重要提示（务必先看）

- **二进制资源不可省略**：`src/assets/`、`public/images/`、`public/data/`、
  `src/dataPipeline/assets/overview-icons/` 下存在大量 PNG/JPG/WebP/SVG/XLSX/DOCX/PDF，
  它们是页面视觉与部分功能的**硬依赖**，无法用代码生成。完整清单见 **07 文档**。
- **路由存在 2 处断链 + 2 处组件错位**：
  - `/dataPipeline/collection`、`/dataPipeline/correction` 缺父级 redirect（迁移遗漏）；
  - `/agentCenter/arxivDailyResults` 与 `/agentCenter/paperAgent` 的组件挂反了。
  见 **08 文档** 4.2 / 4.3 节。
- **`package.json` 与实际 import 不一致**（缺 `lodash`/`dayjs`/`@vueuse/core`/`vitest` 等），
  **不补装会构建失败**。见 **01 文档**第 5 节与 **08 文档** 4.1 节。
- **`src/stores/` 下同时存在 Pinia（12 个）与 Vuex（根 + 4 modules）两套状态方案**，
  且存在明显复制粘贴产生的失效代码（如 `taskStore.js` 引用未声明的 `ruler*Task`），
  见 **03 文档**第 5 节与 **08 文档** 4.5 节。
- **生产部署必须设置 `VITE_API_BASE_URL`**，否则 dataPipeline 模块请求
  会被 `/api` 代理 rewrite 打歪（开发环境尤甚）。见 **08 文档** 4.4 节。
- **`public/data/` 有 20 个文件未被 Git 跟踪**，仅从仓库克隆会缺失；
  但其中多数是冗余副本，可安全省略，见 **08 文档** 2.4 / 第 6 节。
