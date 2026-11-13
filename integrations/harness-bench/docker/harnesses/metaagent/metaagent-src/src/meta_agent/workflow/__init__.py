"""Standalone native Workflow assembly for MetaAgent packages."""

from .ir import WorkflowIR, compile_workflow, parse_workflow_ir

__all__ = ["WorkflowIR", "compile_workflow", "parse_workflow_ir"]
