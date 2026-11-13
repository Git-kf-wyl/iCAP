from __future__ import annotations

import contextvars
import functools
import inspect
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_identity = contextvars.ContextVar('harness_probe_identity', default={})
_lock = threading.Lock()
_log = logging.getLogger('harness.probe')


def serialize(value: Any) -> Any:
    if hasattr(value, 'model_dump'):
        return serialize(value.model_dump(mode='json'))
    if isinstance(value, dict):
        return {str(k): ('[redacted]' if any(s in str(k).lower() for s in
                ('api_key', 'authorization', 'secret', 'password')) else serialize(v))
                for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serialize(v) for v in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def bind_identity(**values):
    """Use a ContextVar so concurrent agents cannot overwrite one another."""
    return _identity.set({**_identity.get(), **values})


def record(kind: str, **data):
    """Durable local evidence; OTel IDs link each record to its native trace."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span().get_span_context()
        trace_id = format(span.trace_id, '032x') if span.is_valid else None
        span_id = format(span.span_id, '016x') if span.is_valid else None
    except ImportError:
        trace_id = span_id = None
    subject_fields = {}
    try:
        from openjiuwen.harness.execution_subject import current_execution_subject
        subject = current_execution_subject()
        if subject:
            subject_fields = {'agent_id':subject.subject_id, 'parent_agent_id':subject.parent_subject_id,
                              'agent_kind':subject.kind, 'native_session_id':subject.session_id}
    except ImportError:
        pass
    row = serialize({'event_id': uuid.uuid4().hex, 'kind': kind, 'timestamp': time.time(),
                     'run_id': os.getenv('HARNESS_RUN_ID'), 'task_id': os.getenv('HARNESS_TASK_ID'),
                     'round': os.getenv('HARNESS_ROUND'), **_identity.get(), **subject_fields,
                     'trace_id': trace_id, 'span_id': span_id, **data})
    path = Path(os.environ.get('HARNESSBENCH_TRACE', '/trace')) / 'context-probe.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    # A single append write prevents concurrent snapshots interleaving.
    payload = (json.dumps(row, ensure_ascii=False) + '\n').encode()
    with _lock:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.fchmod(fd,0o644)
        try:
            with os.fdopen(fd, 'ab') as stream:
                stream.write(payload)
        except BaseException:
            raise
    return row


def _safe_record(kind, **data):
    try:
        return record(kind, **data)
    except Exception:
        _log.exception('Context probe evidence write failed')
        return None


def wrap_context_class(cls):
    """Wrap concrete implementations, never the abstract base method."""
    original = cls.__dict__.get('get_context_window')
    if original is None or getattr(original, '__isabstractmethod__', False):
        return False
    if getattr(original, '__harness_probe__', False):
        return False
    if not inspect.iscoroutinefunction(original):
        raise TypeError(f'{cls.__name__}.get_context_window must be async')

    @functools.wraps(original)
    async def wrapped(self, *args, **kwargs):
        started = time.perf_counter()
        try:
            before = self.get_messages()
            if inspect.isawaitable(before):
                before = await before
            before = serialize(before)
        except Exception:
            before = None
        # The real call and all original return values/errors remain intact.
        try:
            from opentelemetry import trace
            manager = trace.get_tracer('icap.harness.context').start_as_current_span('context.window')
        except ImportError:
            from contextlib import nullcontext
            manager = nullcontext(None)
        with manager as span:
            try:
                window = await original(self, *args, **kwargs)
            except BaseException as exc:
                _safe_record('context.error', context_id=str(getattr(self, 'context_id', '')),
                             error_type=type(exc).__name__, elapsed_ms=(time.perf_counter()-started)*1000)
                raise
            after = serialize(window)
            row = _safe_record('context.window', context_id=str(getattr(self, 'context_id', '')),
                               native_session_id=str(getattr(self, '_session_id', '')),
                               implementation=f'{cls.__module__}.{cls.__qualname__}', before=before,
                               window=after, elapsed_ms=(time.perf_counter()-started)*1000)
            if span is not None and row is not None:
                span.set_attribute('langfuse.observation.type', 'SPAN')
                span.set_attribute('langfuse.observation.input', json.dumps({'messages':before}, ensure_ascii=False))
                span.set_attribute('langfuse.observation.output', json.dumps(after, ensure_ascii=False))
                span.set_attribute('langfuse.observation.metadata', json.dumps({
                    k:row[k] for k in ('event_id','run_id','task_id','round','context_id')}, ensure_ascii=False))
            return window
    wrapped.__harness_probe__ = True
    cls.get_context_window = wrapped
    return True


def install():
    from openjiuwen.core.context_engine.base import ModelContext
    from openjiuwen.core.context_engine.context.context import SessionModelContext
    wrapped = []
    def visit(base):
        for cls in base.__subclasses__():
            if wrap_context_class(cls):
                wrapped.append(f'{cls.__module__}.{cls.__qualname__}')
            visit(cls)
    visit(ModelContext)
    # Future concrete subclasses are covered, including external providers.
    if not getattr(ModelContext, '__harness_subclass_probe__', False):
        previous = ModelContext.__dict__.get('__init_subclass__')
        def init_subclass(cls, **kwargs):
            if previous is not None:
                previous.__get__(None, cls)(**kwargs)
            else:
                super(ModelContext, cls).__init_subclass__(**kwargs)
            wrap_context_class(cls)
        ModelContext.__init_subclass__ = classmethod(init_subclass)
        ModelContext.__harness_subclass_probe__ = True
    _safe_record('probe.installed', implementations=wrapped,
                 concrete=f'{SessionModelContext.__module__}.{SessionModelContext.__qualname__}')
    return wrapped


def flush():
    try:
        from openjiuwen.extensions.observability.setup import force_flush_provider
        return force_flush_provider(timeout_millis=15000)
    except ImportError:
        return False


def install_span_correlation():
    """Discover every native trace, including MetaAgent's hashed-session roots."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SpanProcessor
    provider=trace.get_tracer_provider()
    if getattr(provider, '__harness_correlation__', False): return
    class Correlator(SpanProcessor):
        def __init__(self): self.seen=set();self.guard=threading.Lock()
        def on_start(self, span, parent_context=None):
            context=span.get_span_context()
            tid=format(context.trace_id,'032x')
            with self.guard:
                if tid in self.seen: return
                self.seen.add(tid)
            _safe_record('trace.seen',trace_id=tid,span_id=format(context.span_id,'016x'),name=span.name)
        def on_end(self, span):
            context=span.get_span_context()
            _safe_record('trace.observation',trace_id=format(context.trace_id,'032x'),
                         span_id=format(context.span_id,'016x'),name=span.name,
                         parent_span_id=format(span.parent.span_id,'016x') if span.parent else None,
                         attributes={k:v for k,v in (span.attributes or {}).items() if k.startswith(('gen_ai.usage.','gen_ai.operation.','gen_ai.request.model','gen_ai.response.model','langfuse.observation.type'))},
                         start_time=span.start_time,end_time=span.end_time,
                         status=str(span.status.status_code),
                         events=[{'name':e.name,'attributes':dict(e.attributes or {}),'timestamp':e.timestamp}
                                 for e in span.events])
        def shutdown(self): pass
        def force_flush(self, timeout_millis=30000): return True
    if not hasattr(provider,'add_span_processor'):
        raise RuntimeError('OTel provider is not initialized')
    provider.add_span_processor(Correlator())
    provider.__harness_correlation__=True
