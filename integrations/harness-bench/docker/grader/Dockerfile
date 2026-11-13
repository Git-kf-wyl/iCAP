FROM python:3.10-bookworm@sha256:be77ec026cf35f6adf5f4f02015d50b7aadaac98659a02be1fc8ce18c396f652

USER root
# 国内镜像源：debian 换清华，避免 playwright --with-deps 的 apt 裸连 deb.debian.org 卡死
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' \
      /etc/apt/sources.list /etc/apt/sources.list.d/*.sources /etc/apt/sources.list.d/*.list 2>/dev/null || true
RUN test "$(git --version)" = "git version 2.39.5"
COPY docker/grader/requirements.lock /opt/harnessbench/requirements.lock
ARG HARNESSBENCH_PYPI_INDEX_URL=https://pypi.org/simple
ARG HARNESSBENCH_PYPI_TRUSTED_HOST=
RUN trusted_host_args="" \
    && if [ -n "$HARNESSBENCH_PYPI_TRUSTED_HOST" ]; then \
         trusted_host_args="--trusted-host $HARNESSBENCH_PYPI_TRUSTED_HOST"; \
       fi \
    && python3 -m pip install \
      --index-url "$HARNESSBENCH_PYPI_INDEX_URL" \
      $trusted_host_args \
      --no-cache-dir \
      --only-binary=:all: \
      --require-hashes \
      --requirement /opt/harnessbench/requirements.lock \
    && python3 -c 'import yaml; assert yaml.__version__ == "6.0.2"'
# 注：原镜像从 quay.io/prometheus/alertmanager COPY /bin/amtool 并自检 "version 0.32.1"。
# quay.io 在国内网络下不可达（实测 docker pull 12min 无进展，镜像站亦无白名单），
# 导致 grader 镜像完全无法构建。全库 274 题（tasks/ src/ tools/）经 grep 确认 0 处引用
# amtool —— 它对本 benchmark 没有任何功能作用，故移除。
# 若将来某题确需 amtool，请恢复 quay 引用并在有网环境预拉该镜像。

# 272 等媒体任务要求 grader 镜像具备 ffmpeg/ffprobe（tests/test_outcome.py 显式
# shutil.which 校验，缺失会直接抛 runtime is not qualified）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# BEGIN MULTIMODAL FRONTEND GRADER TOOLCHAIN
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
RUN python3 -m pip install --no-cache-dir --index-url "$HARNESSBENCH_PYPI_INDEX_URL" playwright==1.48.0 \
    && python3 -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright
# END MULTIMODAL FRONTEND GRADER TOOLCHAIN

COPY src/harnessbench/__init__.py /opt/harnessbench/harnessbench/__init__.py
COPY src/harnessbench/grading/ /opt/harnessbench/harnessbench/grading/
COPY docker/grader/grade_entrypoint.py /opt/harnessbench/grade_entrypoint.py
RUN find /opt/harnessbench -type d -exec chmod 0755 {} + \
    && find /opt/harnessbench -type f -exec chmod 0644 {} +

ARG HARNESSBENCH_GRADER_SOURCE_SHA256
LABEL org.harnessbench.grader-source-sha256="${HARNESSBENCH_GRADER_SOURCE_SHA256}"

USER 10002:10002
ENV HOME=/tmp PYTHONPATH=/opt/harnessbench
WORKDIR /workspace
ENTRYPOINT ["python3", "/opt/harnessbench/grade_entrypoint.py"]
