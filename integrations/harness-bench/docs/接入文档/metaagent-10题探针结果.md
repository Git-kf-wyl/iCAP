# metaAgent 10 题环境探针结果报告

- **日期**：2026-11-05
- **模型**：`qwen3.8-27b` @ `ws-fonpfytrgypb84s5.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- **harness**：`metaagent:0.2.0`（grader:local）
- **目的**：验证 10 条难例/环境敏感用例的失败是**真实 agent 犯错**，而非外部环境（断网、缺工具、超时配置）导致。

## 1. 结论

**10 题中 9 题拿到有效 oracle 分数，环境侧零假 badcase；1 题（263）为已归因的环境性 infra error。**

| # | 题目 | oracle | 用时 | 归因 | 备注 |
|---|---|---|---|---|---|
| 1 | 097 k8s CA 轮转恢复 | **0.85** | — | 真实 agent 表现 | 替换 004（版本硬冲突） |
| 2 | 202 智能电表账单修正 | **0.92** | — | 真实 agent 表现 | SQLite 恢复，对照组 |
| 3 | 005 仓库回归二分修复 | **0.8** | 711s | 真实 agent 表现 | completion_timeout 修复后通过 |
| 4 | 262 用户服务注册修复 | **1.0** | 966s | 真实 agent 表现 | controller 镜像补拉后满分 |
| 5 | 264 Node 记录处理契约 | **0.4** | 1389s | 真实 agent 表现 | harness 内置 node 生效 |
| 6 | 272 视频压缩保真交付 | **1.0** | 523s | 真实 agent 表现 | 双侧 ffmpeg 修复生效 |
| 7 | 265 周报生成器 | **0.0** | 1321s | **真实 agent 失败** | 自报"一切验证通过"但 oracle 判 0（高估自己） |
| 8 | 052 本地 HTML 表单抽取 | **0.4** | 347s | 真实 agent 表现 | 600s 首帧超时修复后正常完成 |
| 9 | 094 告警路由修复 | **1.0** | 451s | 真实 agent 表现 | PyYAML 6.0.2 钉版 + alertmanager sidecar 链路 OK |
| 10 | 263 有状态 Python RPC | infrastructure_error | 1717s | **环境问题**（见 §3.3） | Docker Desktop 29.9.2 label 注入 |

**9 题均分 ≈ 0.71**；满分 3 题（262/272/094），高分类 2 题（097/202/005），低分 2 题（264/052=0.4），零分 1 题（265）。

## 2. 环境修复清单（本轮共 9 项，全部验证生效）

| # | 问题 | 修复 | 验证 |
|---|---|---|---|
| 1 | harness 镜像缺 ffmpeg/ffprobe（272 必死） | metaagent Dockerfile apt 加 ffmpeg | 272=1.0 |
| 2 | grader 镜像缺 ffmpeg（272 grader 抛 "runtime is not qualified"） | grader Dockerfile apt 加 ffmpeg | 272=1.0 |
| 3 | harness 缺 node（264 agent 侧无法自测） | pinned node 二进制 COPY stage | 264=0.4 |
| 4 | PyYAML 6.0.3 ≠ 094 要求 6.0.2 | 钉 `PyYAML==6.0.2` | 094=1.0 |
| 5 | 004 python-docx 1.1.2 vs 内核 ≥1.2.0 硬冲突 | 换 097 | 097=0.85 |
| 6 | `WORKFLOW_STREAM_FIRST_FRAME_TIMEOUT` 全局计时 600s 不重置 | 提到 7200/900/7200 | 052=0.4 |
| 7 | DeepAgent `completion_timeout` 默认 600s（整体超时） | eval-package YAML 加 `completion_timeout: 7200` | 005=0.8 |
| 8 | 262/263 controller 需要 pinned python digest，本地缺失触发 60s 隐式拉取超时 | 预拉 `python@sha256:d50fb7…` | 262=1.0 |
| 9 | grader 基础镜像 quay.io 国内不可达 | amtool 全库 0 引用，移除该 stage | grader 重建成功 |

另：Docker Desktop 自动升级 29.6.2→29.9.2 曾导致镜像全量丢失，已配 daocloud 镜像源并全部重建。

## 3. 未解决 / 遗留

### 3.1 265 = 0.0 的可复核性
agent 最后自报 "Everything is verified. The task is complete."，交付 `submission/generate_brief.py` 与 `output/summ…`，但 oracle 判 0。建议人工抽查 `artifacts/evaluations/<run>/tasks/265-*/` 下的交付物与 ground truth 对比，确认是 agent 交付内容错误而非评分误判（初步看是真实 agent 失败）。

### 3.2 264 = 0.4 部分分
正常完成，部分契约满足，属真实 agent 表现，无需复跑。

### 3.3 263 环境问题（唯一未拿到分数的题）
- **根因**：Docker Desktop 29.9.2 给每个容器自动注入 `desktop.docker.io/wsl-distro` label；263 验证器对 `Config.Labels` 做**严格相等**校验 → 恒 `infrastructure failure`。实验实锤（`docker create --label ...` 后 inspect 多出注入 label）。
- 262/264 的验证器无此校验，不受影响（262 拿 1.0 佐证）。
- **无官方关闭开关**。干净解法：**降级 Docker Desktop 至 29.6.2** 后复跑 263 单题（约 30–60 分钟）。
- 降级前注意：29.6.2 用 overlay2 存储，切回去镜像可能需要重建（脚本 `/home/gt_14/rebuild_images.sh` 已就绪）。

### 3.4 分批约束（后续全量跑必读）
`--experimental-task-environments` 要求所有选中题都有 `environment:` 块：
- **批 A**（262-265/272/097/005/202 等）：**不带**该参数；
- **批 B**（052/094 等 sidecar 服务题）：**必须带**。

## 4. 后续步骤

- [ ] 人工抽查 265 交付物（确认 0 分合理性）
- [ ] 决策：是否降级 Docker Desktop 复跑 263
- [ ] 全量 274 题按 §3.4 分批 + `--retry-infrastructure` 跑 shard（约 10h）
- [ ] 所有改动尚未 commit（metaagent 接入全套 + Dockerfile 修复 + 文档）

## 5. 关键产物路径

- 运行产物：`artifacts/evaluations/20261105-141711-qwen3.8-27b-metaagent-harnessbench/`（批 A）、同日 15:55 run（批 B）
- 日志：`/tmp/probe10a.log`（批1）、`probe10a2.log`（修复后重跑6题）、`probe10a3.log`（265/272）、`probe10a4.log`（052/094）
- 镜像：`harnessbench/metaagent:0.2.0`、`harnessbench/grader:local`
