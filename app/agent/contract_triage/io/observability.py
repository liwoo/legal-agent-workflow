"""OpenTelemetry wiring — ships Agent Framework traces to Langfuse (or any OTLP
backend) so every triage run is observable end-to-end.

The Microsoft Agent Framework emits OpenTelemetry spans following the GenAI
semantic conventions. Enabling it here means each run produces:

    invoke_agent <name>   — the agent invocation
      └─ chat <model>     — the underlying LLM call (prompt/response as attrs)
      └─ execute_tool <f> — a tool call (args/result as attrs)

plus a `triage_contract` parent span we add around the workflow run.

This is a **no-op unless configured** — with no ``ENABLE_OTEL`` / OTLP endpoint
the app runs untraced, and importing this module never fails even if the OTLP
exporter package is missing.

Configuration (all injected by ``make up`` via ``e2e/stack.env``):

    ENABLE_OTEL=true
    OTEL_SERVICE_NAME=contract-triage-api
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:3001/api/public/otel/v1/traces
    OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf   # Langfuse: HTTP only, no gRPC
    OTEL_EXPORTER_OTLP_TRACES_HEADERS=Authorization=Basic <base64(pk:sk)>
    ENABLE_SENSITIVE_DATA=true                         # prompts/responses — dev only
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

_log = logging.getLogger(__name__)
_configured = False


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def setup_observability() -> bool:
    """Configure Agent Framework OpenTelemetry export. Idempotent.

    Returns ``True`` when tracing is active, ``False`` when it is disabled or the
    optional dependencies are missing. Safe to call from every entrypoint.
    """
    global _configured
    if _configured:
        return True

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if not (_truthy("ENABLE_OTEL") and endpoint):
        return False

    try:
        from agent_framework.observability import configure_otel_providers
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except Exception as exc:  # pragma: no cover - optional deps
        _log.warning(
            "ENABLE_OTEL is set but OpenTelemetry deps are unavailable (%s); "
            "install the 'otel' extra to export traces.",
            exc,
        )
        return False

    # Agent Framework gates instrumentation on this; configure_otel_providers also
    # enables it, but set it explicitly so it applies before any client is built.
    os.environ.setdefault("ENABLE_INSTRUMENTATION", "true")
    sensitive = _truthy("ENABLE_SENSITIVE_DATA")

    # The HTTP OTLP exporter reads OTEL_EXPORTER_OTLP_TRACES_{ENDPOINT,HEADERS}
    # from the environment. Construct it explicitly so we always use HTTP —
    # Langfuse does not accept gRPC.
    exporter = OTLPSpanExporter()
    try:
        configure_otel_providers(exporters=[exporter], enable_sensitive_data=sensitive)
    except TypeError:  # pragma: no cover - tolerate signature drift
        configure_otel_providers(exporters=[exporter])

    _configured = True
    _log.info(
        "OpenTelemetry enabled → %s (service=%s, sensitive=%s)",
        endpoint,
        os.getenv("OTEL_SERVICE_NAME", "agent_framework"),
        sensitive,
    )
    return True


@contextmanager
def workflow_span(name: str, **attributes: Any) -> Iterator[Any]:
    """Open a top-level span around a workflow run so the agent/LLM/tool spans
    nest underneath it. A no-op when tracing is not configured."""
    if not _configured:
        yield None
        return
    try:
        from agent_framework.observability import get_tracer

        tracer = get_tracer()
    except Exception:  # pragma: no cover
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)
        yield span


def record_workflow_attribute(name: str, value: Any) -> None:
    """Attach a numeric / string attribute to the currently active OTEL span.

    Used by ``finalize`` to emit the model's confidence in the terminal decision
    as trace-level metadata — the value lands on the ``triage_contract`` span
    (or whatever span is active), so Langfuse's OTEL bridge surfaces it in the
    trace attributes view. Configure a "Score from Metadata" derivation in the
    Langfuse UI if you want it promoted to a first-class Score.
    """
    if not _configured or value is None:
        return
    try:
        from opentelemetry.trace import get_current_span

        span = get_current_span()
    except Exception:  # pragma: no cover
        return
    if span is None:
        return
    try:
        span.set_attribute(name, value)
    except Exception:  # pragma: no cover — set_attribute rejects unusual types
        pass
