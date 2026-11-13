FROM ghcr.io/astral-sh/uv:0.11.19-python3.11-trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable \
    && useradd --uid 10001 --create-home worker \
    && mkdir /state && chown worker:worker /state
ENV PATH="/app/.venv/bin:$PATH" \
    META_AGENT_WORKSPACE=/state/workspace \
    META_AGENT_TRACE=/state/trace \
    PYTHONUNBUFFERED=1
USER worker
WORKDIR /state
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import os,urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/admin/health',headers={'Authorization':'Bearer '+os.environ['META_WORKER_TOKEN']}),timeout=4)"
ENTRYPOINT ["meta-agent-worker", "/cfg", "--protocol", "a2a", "--host", "0.0.0.0", "--state-dir", "/state"]
