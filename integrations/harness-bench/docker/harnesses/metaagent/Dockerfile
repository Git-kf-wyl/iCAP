# metaAgent harness 镜像（标准两段结构）。
#
# base = python:3.12-slim-bookworm + 17 包 task-toolchain（复用 docker/openclaw/requirements.lock）
#        + bash/git/sqlite3/ripgrep/ca-certificates。
# 与 openjiuwen harness 的关键差异：meta-agent pin 的是 gitcode agent-core@4cd9df838
# （≠ PyPI 0.1.19 wheel），必须从源码安装，build 需要 git 与 gitcode.com 可达。
#
# 已知坑规避（见 docs/接入文档/）：
# 1. filelock 写文件锁 bug：内核 _async_read_write_lock.py 把 acquire/release 拆进
#    两个 asyncio task，与 filelock>=4.1.0 的 task 归属校验冲突 → 钉 filelock<4.1
#    （与 metaAgent uv.lock 的 3.32.7 同线）。
# 2. python-docx 版本冲突：内核依赖 python-docx>=1.2.0，会升级锁定的 1.1.2 →
#    跳过 verify_toolchain.py 版本检查（功能向后兼容，同 openjiuwen 先例）。
# node 运行时来源（pinned digest）。264 等 Node 任务要求 agent 侧能执行 node；
# 任务自带 package.json 且只用内置 node:test，无需 npm/node_modules。
FROM docker.io/library/node@sha256:e21fc383b50d5347dc7a9f1cae45b8f4e2f0d39f7ade28e4eef7d2934522b752 AS node-bin

FROM python:3.12-slim-bookworm AS task-toolchain

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
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

# metaAgent + pin 内核。git 依赖（agent-core@4cd9df838、intelli-router）均走 gitcode，
# 国内可达；不依赖 github.com。
COPY docker/harnesses/metaagent/metaagent-src /opt/metaagent-src
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      /opt/metaagent-src \
    && rm -rf /opt/metaagent-src

# 钉 filelock（见文件头注释 1）；uv.lock 锁定线为 3.32.7。
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      "filelock==3.32.7"

FROM python:3.12-slim-bookworm

USER root
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST

COPY --from=task-toolchain /usr/local/ /usr/local/
# 与 tasks/264/environment/candidate.Dockerfile 同一手法：剥 node 二进制及其 C++ 运行时依赖。
COPY --from=node-bin /usr/local/bin/node /usr/local/bin/node
COPY --from=node-bin /usr/lib/x86_64-linux-gnu/libstdc++.so.6* /usr/lib/x86_64-linux-gnu/
COPY --from=node-bin /lib/x86_64-linux-gnu/libgcc_s.so.1 /lib/x86_64-linux-gnu/
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
      /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list 2>/dev/null || true \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates bash git sqlite3 ripgrep ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 272 等媒体任务的 instruction 明确要求 harness 镜像具备 ffmpeg/ffprobe（ffmpeg 包已含二者）。

# 094 的 environment/verify_environment.py 精确比对 PyYAML==6.0.2，而 task-toolchain
# 装的是 6.0.3；不钉版本会在任务环境准备阶段直接判 fail。
RUN python -m pip install --disable-pip-version-check --no-cache-dir 'PyYAML==6.0.2'

# 注意：不跑 verify_toolchain.py 的版本检查——meta-agent pin 的内核依赖
# python-docx>=1.2.0，会升级 task-toolchain 锁定的 1.1.2（功能向后兼容），
# 与 openjiuwen harness 同理（见 docs/接入文档/openjiuwen接入.md 坑 2）。

COPY docker/harnesses/metaagent/eval-package /opt/harnessbench/eval-package
COPY docker/harnesses/metaagent/metaagent_eval.py /opt/harnessbench/metaagent_eval.py
COPY docker/harnesses/metaagent/entrypoint.sh /opt/harness/bin/run
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 \
    && chmod 0755 /opt/harness/bin/run /opt/harnessbench/metaagent_eval.py \
    && chmod -R a+rX /opt/harnessbench/eval-package

USER 1000:1000
ENTRYPOINT ["/opt/harness/bin/run"]
