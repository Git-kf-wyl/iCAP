# openjiuwen harness 镜像（标准两段结构）。
#
# base = python:3.12-slim-bookworm + 17 包 task-toolchain（复用 docker/openclaw/requirements.lock）
#        + bash/git/sqlite3/ripgrep/ca-certificates，内容等价于之前的 harnessbench/agent-tools:local。
# 历史：曾因 WSL 拉 python:3.12-slim-bookworm 层走 mirror 卡死，临时复用 agent-tools:local 作 base；
#       现换回标准两段结构，摆脱本地-only 的 agent-tools:local 依赖。
FROM python:3.12-slim-bookworm AS task-toolchain

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
      /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates bash git sqlite3 ripgrep \
    && rm -rf /var/lib/apt/lists/*
COPY docker/openclaw/requirements.lock /tmp/harnessbench-requirements.lock
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --requirement /tmp/harnessbench-requirements.lock \
    && rm /tmp/harnessbench-requirements.lock

FROM python:3.12-slim-bookworm

USER root
ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST

COPY --from=task-toolchain /usr/local/ /usr/local/
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
      /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates bash git sqlite3 ripgrep \
    && rm -rf /var/lib/apt/lists/*

# openjiuwen 内核。依赖重（transformers/pymilvus/matplotlib/numpy/opentelemetry…）。
# 注：源码 pyproject.toml 声明的 git 依赖 intelli-router（gitcode.com）在 PyPI wheel 里
# 已被替换成 gitcode-api，build 不需要 gitcode.com 可达（见接入文档 5.4 坑 3）。
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      "openjiuwen[cli]==0.1.19"

# 修复 filelock 版本冲突（详见 docs/接入文档/openjiuwen-filelock写文件锁bug定位.md）：
# openjiuwen 0.1.19 的 _acquire_file/_release_file 把 acquire/release 拆进两个 asyncio task，
# 与 filelock>=4.1.0 的「按 asyncio task 归属校验」冲突，write_file 报 Cannot close an active file lock。
# 锁回 openjiuwen 自己声明的下限 3.25.0（无该校验），不改 openjiuwen 源码。
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      "filelock==3.25.0"

# 注意：不跑 verify_toolchain.py 的版本检查——openjiuwen 依赖 python-docx>=1.2.0，
# 会把 task-toolchain 锁定的 python-docx==1.1.2 升级到 1.2.0，导致版本检查失败。
# 功能向后兼容（1.2.0 兼容 1.1.2），MVP 先跳过版本校验。
COPY docker/harnesses/openjiuwen/openjiuwen_eval.py /opt/harnessbench/openjiuwen_eval.py
COPY docker/harnesses/openjiuwen/entrypoint.sh /opt/harness/bin/run
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 \
    && chmod 0755 /opt/harness/bin/run /opt/harnessbench/openjiuwen_eval.py

USER 1000:1000
ENTRYPOINT ["/opt/harness/bin/run"]
