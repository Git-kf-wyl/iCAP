#!/usr/bin/env bash
# 把本地 metaAgent 源码同步进 vendored 构建上下文，并打印新的源码摘要。
# 用法: bash tools/harness_bench/sync_metaagent_src.sh [/path/to/metaAgent]
set -euo pipefail
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="${1:-$REPO/metaAgent}"
VEND="$REPO/docker/harnesses/metaagent/metaagent-src"
[ -f "$SRC/pyproject.toml" ] || { echo "找不到 metaAgent 源码: $SRC" >&2; exit 1; }
rsync -a --delete "$SRC/src" "$VEND/"
for f in pyproject.toml README.md uv.lock LICENSE; do [ -f "$SRC/$f" ] && cp -a "$SRC/$f" "$VEND/$f"; done
find "$VEND" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
python3 - "$REPO" <<'PY'
import sys, pathlib
repo = pathlib.Path(sys.argv[1]); sys.path.insert(0, str(repo / "tools"))
import harness_runtime as hr
print("synced from:", "metaAgent")
print("new source sha256:", hr.harness_source_sha256(hr.SPECS["metaagent"]))
PY
