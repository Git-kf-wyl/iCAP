# MetaAgent harness（新分支布局）

`python tools/run_benchmark.py --harness metaagent ...` 使用本仓库**内置**的 MetaAgent：

| 组成 | 路径 |
| --- | --- |
| 被测源码（vendored） | `docker/harnesses/metaagent/metaagent-src/`（`src/`、`pyproject.toml`、`README.md`、`uv.lock`） |
| 评测配置包 | `docker/harnesses/metaagent/eval-package/`（`meta_agent.yaml` + `skills/`） |
| 容器入口 | `docker/harnesses/metaagent/entrypoint.sh`、`metaagent_eval.py` |
| 镜像 | `harnessbench/metaagent:0.2.0`（`tools/harness_runtime.py` 的 SPECS） |
| 驱动脚本 | `tools/harness_bench/`（`run_full274.sh`、`run_smoke15.sh`、`verify.py`、`check_adapter.py`） |

源码摘要把 `docker/harnesses/metaagent/**`（不含 `*.bak-*`、`__pycache__`）计入，因此同步源码后会自动触发镜像重建。

同步本地 checkout 到 vendored 上下文：

```bash
bash tools/harness_bench/sync_metaagent_src.sh /path/to/metaAgent
```

如需临时改用仓库外的 checkout：把该 checkout 放到本仓库 `metaAgent/`，驱动脚本会自动优先使用它。
