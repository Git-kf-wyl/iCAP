# 服务器维护的配套工程

- `harness-bench/`：2026-11-13 从生产 `/opt/harness-bench` 回收的维护源码，包含服务器未提交的 OpenJiuwen / MetaAgent 适配与任务资产。
- `harness-langfuse-lab/`：辅助构建文件、指标与 Hook 说明；不包含定制 Langfuse Web 镜像的原始 Next.js 工程。

来源、调用链、环境依赖与验证结果见 `../docs/SERVER_SYNC_20261113.md`。凭据、数据库和运行结果均不随源码同步。生产路径默认不变；本地开发 HarnessBench 时配置 `HARNESS_BENCH_REPO` 为此目录下的 `harness-bench` 绝对路径。
