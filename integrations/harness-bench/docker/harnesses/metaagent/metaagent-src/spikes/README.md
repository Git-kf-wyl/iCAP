# M1 风险原型

这里的代码用于验证 [PLAN](../PLAN.md) 的架构接缝，不作为 `meta_agent` wheel 的生产 API。模型输出和外部业务服务使用确定性替身；DAG 和团队适配实验使用锁定版本的真实 OpenJiuwen 内核。

| 原型 | 验证范围 | 用例 |
|---|---|---|
| `dag_harness.py` | 配置物化、Workflow 与 DeepAgent 组合、插件路由和控制状态 | `tests/integration/test_m1_dag_harness.py` |
| `team_adapter.py` | provider、成员运行时、配置引用和团队接线边界 | `tests/integration/test_m1_team_adapter.py` |
| `recovery.py` | 进程终止窗口、持久化操作身份、下游对账/去重和 fencing | `tests/fault_injection/test_m1_recovery.py` |

从仓库根目录运行：

```console
uv sync --locked
uv run --locked python -m pytest tests/integration/test_m1_dag_harness.py tests/integration/test_m1_team_adapter.py tests/fault_injection/test_m1_recovery.py -v
uv run --locked python scripts/check.py
```

Windows 异步内核运行需要允许本地 IPC 的执行环境。测试不需要真实模型凭据或平台服务。

测试通过表示所断言的行为成立，其中也包含“明确拒绝不支持配置”的断言。它不自动等于产品门禁通过。各项实际结果、阻断范围与后续工作见 [M1 验证记录](../docs/compatibility/m1-validation.md) 和 [M1 接线决策](../docs/adr/0001-m1-integration-boundaries.md)。
