"""Thin node API: the host owns the persistent sidecar, MetaAgent owns routing."""

from pathlib import Path
from typing import Any


async def invoke(
    sidecar: Any,
    inputs: dict[str, Any],
    *,
    session_id: str,
    request_id: str,
    trace_context: dict[str, str] | None = None,
) -> Any:
    return await sidecar.run(
        inputs, session_id=session_id, request_id=request_id, trace_context=trace_context
    )


if __name__ == "__main__":
    from host_adapter import execute_node  # type: ignore[import-not-found]

    execute_node(Path(__file__).resolve().parents[2])
