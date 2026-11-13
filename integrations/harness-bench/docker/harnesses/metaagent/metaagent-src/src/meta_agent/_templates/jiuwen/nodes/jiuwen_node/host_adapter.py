"""Staff maps the real node request/response to the already active sidecar."""

from pathlib import Path


def execute_node(package_root: Path) -> None:
    # Read actual host identity/inputs, call the persistent sidecar and map output.
    # Preserve INPUT_REQUIRED and trace context. Do not instantiate a runtime per call.
    raise RuntimeError(
        "META_HOST_NOT_CONFIGURED: staff must connect this node to the persistent sidecar"
    )
