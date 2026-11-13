# 2026-11-13 服务器源码同步与功能地图

## 来源与合并方式

- GitHub 基线：`origin/maas` 的 `8eeb1b53d0696334d1a6968767f30046a47f3055`；先快进本地 maas，再纳入生产源码差异，保留 GitHub 已有导航调整。
- 生产目录：`/opt/icap/releases/langfuse-20261113-observability-thinking`。该发布目录没有 `.git`；`release.json` 仍记录旧提交 `19ab286`，不能当作当前源码的完整版本标识。
- 生产相对 GitHub 有 18 个修改、22 个新增源码/测试文件。发布元数据、环境凭据、认证库、运行数据、日志、缓存和 dist 不纳入提交；缺失的本地导入工具与 `.env.example` 保留。
- 生产 HarnessBench 原始基线：`a3643dc`，另有未提交的 MetaAgent、容器网络与运行控制改动。完整维护源码和任务资产保存到 `integrations/harness-bench/`，不是 Git 子模块。
- 原分支备份：`backup/maas-before-server-sync-20261113`。

源码归档 SHA256：

| 来源 | SHA256 |
| --- | --- |
| iCAP 生产源码 | `e1ac549bf7eae7c2d7c3dea35a1481bffc8d65321d3b4657a7283fc39962efe8` |
| HarnessBench | `9032a833dd9c1b883f7efa64bbb82ddc7c2427519e3df702f07a39d3e0f503ea` |
| 观测工程辅助资料 | `dfbf4f45be5ff1d4a1dada4f608efe5ceea8a5d013598eefa0fad6e7b3ff035e` |

## 当前功能调用链

### Harness 在线评测

`/harnessEval/online` 的 Vue 页面嵌入同源 `/harness-lab/harness`。FastAPI 的 `harness_proxy.py` 校验 iCAP 登录 cookie、路径白名单和写请求来源，再代理到独立定制 Langfuse 页面，默认 `HARNESS_LAB_URL=http://127.0.0.1:3101`。

`backend/app/harness_eval.py` 提供 catalog、启动、列表、详情与停止接口。任务必须显式选择；生产观测运行限定 OpenJiuwen 与 MetaAgent，支持并发、温度、思考模式与档位。`harness_run_worker.py` 监管进程、保存退出状态并清理该运行标记的失败容器；实际 benchmark runner 来自 `HARNESS_BENCH_REPO`，生产默认 `/opt/harness-bench`。

新机器可把 `HARNESS_BENCH_REPO` 指向本仓库的 `integrations/harness-bench`，按该工程 README 构建对应镜像。仅拉源码不能替代 Docker、模型端点、观测服务与遥测运行包的配置。

### OpenJiuwen / MetaAgent

- HarnessBench OpenJiuwen：`integrations/harness-bench/docker/harnesses/openjiuwen/` 的镜像、entrypoint 与 eval wrapper，固定 `openjiuwen[cli]==0.1.19`，并处理 filelock 兼容性。
- HarnessBench MetaAgent：`docker/harnesses/metaagent/metaagent-src/` 内置源码、`eval-package/` 配置包及容器 wrapper。服务器新增了包加载/构建、workflow、sidecar、平台与模型服务适配；详见其 `docs/METAAGENT_HARNESS.md`。
- 控制层共享适配：`tools/harness_runtime.py`、`container_runtime.py`、`run_benchmark.py`、`proxy_env.py` 与 `tools/harness_bench/` 驱动脚本。
- AgentCompass 的 OpenJiuwen 是另外一条适配链：`backend/vendor/agentcompass/harnesses/openjiuwen.py`、`jiuwenswarm.py`，不要与 HarnessBench Docker wrapper 混淆。

### AgentCompass

平台层 `backend/app/evaluation/agentcompass_adapter.py` 把 Dev、GAIA、TerminalBench2.1 映射到 vendor 中的 benchmark/harness/environment，回写作业进度并通过 `agentcompass_reports.py` 转成 iCAP 报告。生产新增 vendor 的 HarnessBench benchmark、Docker recipe 与 OpenJiuwen/Swarm harness，并恢复其 CLI/web 入口。平台枚举与 vendor 注册范围不同，不能仅因为 vendor 存在就认为平台已开放对应入口。

### 可观测性与思考模式

`backend/harness_probe/` 采集上下文、模型及工具执行证据并计算指标；`harness_otlp_relay.py` 负责私有 OTLP 转发；`harness_observability.py` 通过后端凭据访问 Langfuse，并根据控制端参考答案与证据生成指标。缺少标准答案或证据会明确标记，不能当作零分或已完成评分。

`model_thinking.py` 统一检查模型声明的思考能力与档位。聊天和评测使用对应 endpoint 的 enabled/disabled schema；具体支持能力由模型配置决定。

`integrations/harness-langfuse-lab/` 保存服务器辅助构建文件、Hook 说明和指标定义。生产定制页面镜像是 `icap/langfuse-harness:4.79.0`；其 image ID 为 `sha256:ddee1aa8aa0fe82ce4085db5263bbc684b0e176749c87f79af06a2b3264ae4e7`。服务器已定位的 compose 工作目录只保留配置和 `.env`，没有原始 Next.js checkout，因此本次没有恢复该定制镜像的原始前端源码。后续重建该镜像需要原始构建工程或现有镜像；不要把辅助目录误认为完整 Langfuse 源码。

## 验证与已知限制

- 合并后 Vite 生产构建通过；登录启动四种场景、缓存/快速导航、首页 bootstrap、图表进入视口加载测试通过。
- 当前 Harness UI 已从旧勾选框页面迁移到 iframe，旧 `harness-selection.mjs` 不再适用，替换为 `harness-embed.mjs` 验证入口与错误提示。
- AgentCompass 平台适配测试：9 项通过。完整 vendor 导入依赖 Linux 的 `fcntl`，Windows 上无法通过该项。
- 服务器原有 Harness 控制层两组测试：102 项通过、34 个 subtest 通过、1 项失败。失败为已有测试仍要求 Dockerfile 包含已主动移除的 Alertmanager/amtool stage；这是生产快照现状，本次不修改 benchmark 或评分标准来消除失败。
- 未发起真实模型评测，也未重启或切换生产服务；此次操作为源码回收与 GitHub 同步。

开发时先确认目标是 iCAP 入口、HarnessBench runner、AgentCompass vendor 还是独立 Langfuse 页面。后端配置只留在服务器或本地环境，任何提交都不得包含 `.env`、真实 API key、用户数据、原始观测数据或运行目录。
