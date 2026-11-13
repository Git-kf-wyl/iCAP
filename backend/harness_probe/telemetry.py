"""Initialize the same native observation exporter used by the proven demo."""
import os
from contextlib import contextmanager
from .capture import bind_identity, record, flush, install


def configure():
    install()
    from openjiuwen.extensions.observability.config import ObservabilityConfig
    from openjiuwen.harness.observability import acquire_observability
    acquire_observability(ObservabilityConfig(
        service_name='icap-harness-' + os.environ.get('HARNESS_AGENT', 'openjiuwen'),
        exporter='langfuse', endpoint=os.environ['LANGFUSE_OTEL_ENDPOINT'],
        langfuse_public_key=os.environ['LANGFUSE_PUBLIC_KEY'],
        langfuse_secret_key=os.environ['LANGFUSE_SECRET_KEY'],
        langfuse_ingestion_version=4, attribute_value_max_length=0, max_attributes=4096,
    ))
    from .capture import install_span_correlation
    install_span_correlation()


@contextmanager
def task_span(session_id, prompt):
    from openjiuwen.harness.observability import open_agent_run_span, close_agent_run_span
    bind_identity(session_id=session_id, agent_id=os.environ.get('HARNESS_AGENT'))
    span = open_agent_run_span(session_id=session_id, mode='harness.benchmark')
    if span is None:
        raise RuntimeError('Native agent tracing was not initialized')
    span.set_attribute('langfuse.trace.name', os.environ.get('HARNESS_TASK_ID', 'harness.task'))
    span.set_attribute('langfuse.trace.metadata.run_id', os.environ.get('HARNESS_RUN_ID', ''))
    span.set_attribute('langfuse.trace.metadata.task_id', os.environ.get('HARNESS_TASK_ID', ''))
    span.set_attribute('langfuse.observation.input', prompt)
    from opentelemetry import trace
    scope=trace.use_span(span, end_on_exit=False)
    scope.__enter__()
    record('agent.started')
    try:
        yield span
    except BaseException as exc:
        record('agent.failed', error_type=type(exc).__name__)
        close_agent_run_span(span, session_id=session_id, exception=exc)
        raise
    else:
        record('agent.completed')
        close_agent_run_span(span, session_id=session_id)
    finally:
        scope.__exit__(None, None, None)
        flush()
