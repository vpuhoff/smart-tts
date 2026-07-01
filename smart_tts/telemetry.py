"""OpenTelemetry spans for smart-tts (no-op without opentelemetry-api)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment,misc]
    StatusCode = None  # type: ignore[assignment,misc]

TRACER_NAME = "smart_tts"


class _NullSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def set_status(self, status: Any) -> None:
        return None

    def record_exception(self, exception: BaseException) -> None:
        return None


def is_enabled() -> bool:
    """Return True when opentelemetry-api is installed."""
    return _OTEL_AVAILABLE


class _NullTracer:
    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Iterator[_NullSpan]:
        yield _NullSpan()


def get_tracer() -> Any:
    if not _OTEL_AVAILABLE or trace is None:
        return _NullTracer()
    from smart_tts._version import __version__

    return trace.get_tracer(TRACER_NAME, __version__)


def attr_value(value: Any) -> bool | int | float | str:
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def set_span_attributes(span: Any, attributes: Mapping[str, Any] | None) -> None:
    if attributes is None:
        return
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, attr_value(value))


def current_trace_id() -> str | None:
    """Return the current trace id as hex, if tracing is active."""
    if not _OTEL_AVAILABLE or trace is None:
        return None
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None
    return format(context.trace_id, "032x")


def current_span_id() -> str | None:
    if not _OTEL_AVAILABLE or trace is None:
        return None
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None
    return format(context.span_id, "016x")


def task_attributes(task: Any) -> dict[str, Any]:
    model = getattr(task, "model", None)
    return {
        "smart_tts.voice_id": getattr(task, "voice_id", None),
        "smart_tts.model": model.value if model is not None else None,
        "smart_tts.language": getattr(task, "language", None),
        "smart_tts.emotion": getattr(task, "emotion", None),
        "smart_tts.use_case": getattr(task, "use_case", None),
        "smart_tts.char_count": len(getattr(task, "text", "") or ""),
        "smart_tts.enhance_text": getattr(task, "enhance_text", None),
        "smart_tts.has_music": bool(getattr(task, "music_prompt", None) or getattr(task, "music_path", None)),
        "smart_tts.has_ambient": bool(
            getattr(task, "ambient_prompt", None) or getattr(task, "ambient_path", None)
        ),
    }


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """Start a sync span; no-op when OpenTelemetry is not installed."""
    if not _OTEL_AVAILABLE or trace is None:
        null_span = _NullSpan()
        set_span_attributes(null_span, attributes)
        yield null_span
        return

    tracer = get_tracer()
    with tracer.start_as_current_span(name) as active_span:
        set_span_attributes(active_span, attributes)
        try:
            yield active_span
        except Exception as exc:
            active_span.record_exception(exc)
            if Status is not None and StatusCode is not None:
                active_span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


@asynccontextmanager
async def async_span(name: str, **attributes: Any) -> AsyncIterator[Any]:
    """Start an async span; no-op when OpenTelemetry is not installed."""
    if not _OTEL_AVAILABLE or trace is None:
        null_span = _NullSpan()
        set_span_attributes(null_span, attributes)
        yield null_span
        return

    tracer = get_tracer()
    with tracer.start_as_current_span(name) as active_span:
        set_span_attributes(active_span, attributes)
        try:
            yield active_span
        except Exception as exc:
            active_span.record_exception(exc)
            if Status is not None and StatusCode is not None:
                active_span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
