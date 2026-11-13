# 交付包

`agent.json`、`package.json.workflows` 和外层 Workflow 供 AgentFlow 使用。
存在 `package.json.meta_agent` 时，它选择包内 OpenJiuwen 的 Workflow / DeepAgent / Hybrid。
外层只调一次业务节点；Hybrid 的规则路由由 MetaAgent 内部执行。

这是开发起点。AgentFlow 文件参照现有仓库格式；真实 MMAgentWorker / sidecar 接入需 staff 适配，未宣称平台端到端验收。

## 本地运行

- AgentFlow-only：`python scripts/echo.py --input hello`，不依赖 MetaAgent。
- 其余模式：安装匹配的 MetaAgent runtime，执行 `meta-agent validate .` 和 `meta-agent run . --input-file inputs.json --session-id demo`。
- DeepAgent / Hybrid：先设置 `MODEL_NAME` 和 `META_AGENT_WORKSPACE`，宿主在激活前注册名为 `fusionmind` 的 InferenceTransport。未绑定时明确失败，不会调用虚构的服务。
- 直接连接 OpenAI-compatible 服务时，将 agent.yaml 的 model_client_config 改为原生 `client_provider: OpenAI`，用 ENV 占位符配置 api_base / api_key。
- JSON IR 与 Python factory 二选一；Hybrid 未命中才创建 DeepAgent。已有待答必须在同一运行实例续答，逐次 CLI 进程不保存对话。

## 平台接入

Jiuwen 包的 `nodes/jiuwen_node/jiuwen_node.py` 提供直接委派给 SidecarApp 的异步 `invoke` 函数。
`host_adapter.py` 是 staff 的外层节点接缝：读取实际宿主请求，调用已激活的持久 sidecar，按宿主约定输出结果。
模板不猜测 UDS、HTTP 或 DataBus wire protocol，也不为每个节点请求启动新的 DeepAgent。

宿主负责 activate/status/run/closesession/deactivate、鉴权与连接生命周期，调用 SidecarApp API。
`INPUT_REQUIRED` 应保留 session/request/execution 关联并转交用户；不要当作最终答案。
Workflow 的原生 ToolComponent 输出仍含 data/error_code/error_message，应由业务图按需要判断。

## 打包

`meta-agent-package pack . --output ../package.zip`

只包含 `package.files` 中的逐文件列表，新增代码/配置/Skill 时必须更新列表。
打包不执行 Python、不展开 ENV、不安装 requirements.txt、不包含未列出的 `.env`、日志或工作区。
SHA-256 打印到 stdout，ZIP 解压后根目录即为本包。不要把凭据填进配置或文件列表；发布前检查业务文件。
运行验证使用实际环境变量；打包后的 placeholder 保持不变。

## Linux 容器

在 MetaAgent 仓库构建 wheel 后，使用 `docker build -f Dockerfile.package -t meta-agent:packages .` 构建包运行镜像。
该目标复用 `meta-agent:local` 的锁定依赖；首次先按仓库 Dockerfile 构建此基础镜像。
将本包只读挂到 `/cfg`，将可写目录或 volume 挂到 `/state`：

```sh
docker run --rm --mount type=bind,src="$PWD",dst=/cfg,readonly \
  meta-agent:packages run /cfg --input-file /cfg/inputs.json --session-id demo
```

上述命令直接适用于无需模型的 Workflow。DeepAgent/Hybrid 需提供模型配置及宿主 transport 启动程序；
仅传 MODEL_NAME 不会自动注册平台 SDK。`/state` 为运行输出，包源目录应保持只读。
包运行镜像是本地包内 CLI，不暴露 MMAgentWorker API，也不是生产持久 sidecar 服务端。
