# 验证记录（2026-11-06）

本次已实际执行检查，所有修复均已落盘。真实 MetaAgent 生命周期和原生工具执行通过；没有把远端模型回复模拟成真实火山调用，也没有将权限失败标为通过。

## 修复

1. **asyncio 线程完成后阻塞**：最小复现表明 asyncio socketpair 的 `send` 返回 `PermissionError: EPERM`；线程已经空闲，但事件循环仍在 epoll 等待。入口在该限制存在时启用 50ms 定时唤醒，同时覆盖 shutdown 阶段。原有 filelock 3.32.7 未降级、未修改。
2. **独立 pytest 收集失败**：在 harness-bench 的 pytest 配置中声明 `pythonpath = ["src"]`，不再依赖其他测试的导入顺序。
3. **任务目录统计过期**：使用仓库的 `build_catalog.py` 重新生成 CSV；只更新与已有任务变更对应的 12 行统计，没有改任务要求。
4. **火山请求与构建代理接线**：搜索客户端启用环境代理；服务检查支持 `--proxy`；受信控制器的模型代理支持 `HARNESSBENCH_UPSTREAM_PROXY`，HTTPS 使用 CONNECT，HTTP 使用绝对 URL，遵守 NO_PROXY；Linux 构建支持 host 网络访问本机 127.0.0.1:7890。
5. **镜像 Python 选择**：MetaAgent 镜像明确使用已有 Python 3.12，避免锁文件同步时额外下载解释器；模型/裁决/搜索缺少配置时清楚报告 BLOCKED。

## 实际测试结果

| 检查 | 结果 |
|---|---|
| 回答 → 模型客户端 → final answer → trace → close | 通过 |
| 原生 write_file → read_file → bash，并校验实际磁盘文件 | 通过 |
| MetaAgent 调用 web_search → VolcanoSearch 请求构造/响应解析 | 通过，远端 HTTP 使用固定回复 |
| 模型返回 HTTP 401 → 错误传播、错误 summary、资源清理 | 通过 |
| 所有用例中的任务自带 AGENT.md 保留 | 通过 |
| 针对接入、裁决、目录和代理的回归 | **111 passed，41 subtests passed** |
| 全部 harness-bench 控制面测试 | **530 passed，19 failed，634 subtests passed** |
| 19 个失败的原因 | 全部在创建本地 HTTP server 时被沙箱以 EPERM 拒绝；涉及 model_budget_proxy、probe_model_service |
| 真实火山执行模型、裁决模型、搜索 | 已尝试预检，缺少模型 ID 和 API key，BLOCKED |
| 127.0.0.1:7890 代理连接 | 已尝试，TCP socket 操作被沙箱以 EPERM 拒绝 |
| Docker | 已尝试，Docker socket 连接被拒绝 |
| 两个真实端到端 benchmark 任务 | 被 Docker/凭证前置条件阻塞，未执行 |

全量测试的 19 个失败不计为通过。受限沙箱的系统调用权限无法通过修改 Python、代理地址或项目配置解除，因此不能宣称所有环境问题都已解决或两个真实任务已经通过。仍需允许 Docker socket、本地 TCP/监听的执行环境，以及真实火山配置。

## 可检查的落盘证据

本机的 `metaAgent/.artifacts/harness-bench-final/` 保存：

- `results.json`：每项状态、退出码和日志位置。
- `answer/`、`tools/`、`search/`、`model-error/`：各自的 workspace、配置和 trace。
- `tools/workspace/answer.txt` = `42`，`shell.txt` = `shell-ok`。
- `harness-tests.log`：完整全量测试输出和失败堆栈。
- `service-model.log`、`service-judge.log`、`service-search.log`：真实服务预检的缺失配置记录。
- `docker.log`：Docker 权限失败原文。

使用 [README](README.md) 中的一条命令可重跑全部检查，并生成新的独立证据目录。未修改沙箱策略、Docker socket 权限或系统依赖。
