"""Optional OpenTelemetry SDK setup for exporting smart-tts traces."""

from __future__ import annotations

import os

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "smart-tts otel extension requires opentelemetry-sdk and OTLP exporter. "
        "Install with: pip install smart-tts[otel-sdk]"
    ) from exc

from smart_tts.telemetry import is_enabled

__all__ = [
    "configure_tracing",
    "shutdown_tracing",
]


_provider: TracerProvider | None = None


def configure_tracing(
    *,
    service_name: str = "smart-tts",
    endpoint: str | None = None,
    exporter: SpanExporter | None = None,
    console: bool = False,
) -> TracerProvider:
    """Configure OTLP (or console) trace export for smart-tts spans.

    Reads ``OTEL_EXPORTER_OTLP_ENDPOINT`` when ``endpoint`` is omitted.
    Set ``console=True`` or ``OTEL_TRACES_CONSOLE=1`` for local debugging.
    """
    global _provider

    if not is_enabled():
        raise ImportError("opentelemetry-api is required. Install with: pip install smart-tts[otel]")

    if _provider is not None:
        return _provider

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
            "service.namespace": "smart-tts",
        }
    )
    provider = TracerProvider(resource=resource)

    if exporter is None and (console or os.getenv("OTEL_TRACES_CONSOLE", "").strip() in {"1", "true", "yes"}):
        exporter = ConsoleSpanExporter()

    if exporter is None:
        exporter = OTLPSpanExporter(
            endpoint=endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        )

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def shutdown_tracing() -> None:
    """Flush and shut down the configured tracer provider."""
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
