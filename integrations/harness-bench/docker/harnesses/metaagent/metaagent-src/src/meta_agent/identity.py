"""Immutable request correlation and collision-safe native session identity."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ExecutionIdentity:
    product_id: str
    agent_id: str
    session_id: str
    request_id: str
    execution_id: str

    def __post_init__(self) -> None:
        for value in self.as_dict().values():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Execution identity fields must be non-empty strings")

    def as_dict(self) -> dict[str, str]:
        return asdict(self)

    @property
    def child_session_id(self) -> str:
        """Preserve native memory across requests, isolating product/agent/session."""
        payload = json.dumps(
            [self.product_id, self.agent_id, self.session_id],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return "meta-agent-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
