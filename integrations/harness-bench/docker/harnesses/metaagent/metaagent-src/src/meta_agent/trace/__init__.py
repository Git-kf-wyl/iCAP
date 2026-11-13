"""Metadata-only local trace and native model lifecycle counters."""

from meta_agent.trace.rail import TraceRail
from meta_agent.trace.sink import JsonlTraceSink

ModelCallTraceRail = TraceRail

__all__ = ["JsonlTraceSink", "ModelCallTraceRail", "TraceRail"]
