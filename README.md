# iCAP 私有 Yellow 重构版

本目录包含非公开业务源码。禁止推送至公开仓库、公开制品库或静态文件目录。原始源码保存在本机 D:/icap/icap_yellow_source；当前工程没有配置 Git 远端。

基础版本：Blue 170dd76；Yellow 17862a2c6c58b96e611a99c9e71642906b1ba050。

## 启动

使用 Python 3.12、Node.js 20.19+。安装 backend/requirements.txt 和 backend/requirements-yellow.txt，执行 npm ci && npm run build。在 backend 目录执行：

    python -m uvicorn adapter:app --host 127.0.0.1 --port 8081 --workers 1

全部业务接口统一由 backend/adapter.py 管理。同一进程提供构建后的前端，无需 Nginx。每个账号的原版业务配置和输出隔离存放在 INNOVATION_DATA_DIR/yellow/users 中。模型凭据仅保存在后端，前端始终调用同源接口。

生产环境设置 DEMO_MODE=false，沿用服务器 /etc/icap/production.env 的管理员密码、签名密钥和模型配置。禁止提交 .env、运行数据、认证数据库、日志或模型凭据。生产不使用演示账号。

## 迁移内容

沿用原版导航、模型广场、参数化多模型对话、数据集开发、通用/领域评测、榜单、报告和论文页面。保留 Blue 的手机号/密码/密保账户系统、模型多端点管理、资源可见性、Skill 自进化/Hermes、AgentCompass 和科研子站链接。移除 AI School 与数据治理 Pipeline。

原版工作簿位于 backend/yellow/services/aisf_rewrite/上下文数据标注09121440.xlsx。实际执行原版评测和评分流程；未提供的测试语料需上传。报告使用实际评测结果生成 PPTX，服务器 LibreOffice 负责 PDF 预览。

Hugging Face / ModelScope 下载写入账号资源库，支持私有或公开资源，不依赖原单位 S3。监控使用真实主机指标。代码评测仅在 Linux bubblewrap 隔离器验证通过后启用；隔离器没有网络、服务源码和模型密钥。

原单位设备实验室、VLA 硬件、独立 Dify/Coze/Owl/Harness、外部深度研究及语音/视觉模型服务未提供，页面和接口明确提示不可用。当前仅接入现有 DeepSeek 文本服务；没有导入原仓库的模型凭据或历史得分。

## 发布与回滚

发布至 /opt/icap/releases/<release>，由 icap.service 使用 /opt/icap-yellow-venv 运行。持久化数据仍在 /var/lib/icap。切换前备份数据、生产配置、systemd 配置和旧版本链接；通过本地暂存端口验证，再原子切换 /opt/icap/current 并重启。保留 Cloudflare Tunnel 和科研子站配置。

LICENSE 仅适用于原 Blue 代码；Yellow 私有业务源码不因此获得公开发布许可。保留第三方许可证。
