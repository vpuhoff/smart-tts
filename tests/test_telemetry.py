from __future__ import annotations

import pytest

from smart_tts.telemetry import (
    async_span,
    current_span_id,
    current_trace_id,
    is_enabled,
    span,
    task_attributes,
)
from smart_tts.models import SynthesisTask


def test_span_noop_without_provider() -> None:
    with span("smart_tts.test", foo="bar") as active_span:
        active_span.set_attribute("smart_tts.ok", True)
    assert current_trace_id() is None


def test_task_attributes() -> None:
    task = SynthesisTask(text="Привет", voice_id="voice-1", language="ru")
    attrs = task_attributes(task)
    assert attrs["smart_tts.voice_id"] == "voice-1"
    assert attrs["smart_tts.char_count"] == len("Привет")


@pytest.mark.skipif(not is_enabled(), reason="opentelemetry-api is not installed")
def test_span_records_finished_span(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("smart_tts.telemetry.get_tracer", lambda: provider.get_tracer("smart_tts"))

    with span("smart_tts.test.synthesize", **{"smart_tts.voice_id": "voice-1"}):
        pass

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].name == "smart_tts.test.synthesize"
    assert finished[0].attributes["smart_tts.voice_id"] == "voice-1"


@pytest.mark.asyncio
@pytest.mark.skipif(not is_enabled(), reason="opentelemetry-api is not installed")
async def test_async_span_records_finished_span(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr("smart_tts.telemetry.get_tracer", lambda: provider.get_tracer("smart_tts"))

    async with async_span("smart_tts.test.async", **{"smart_tts.mixed": False}):
        pass

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].name == "smart_tts.test.async"
    assert finished[0].attributes["smart_tts.mixed"] is False


@pytest.mark.skipif(not is_enabled(), reason="opentelemetry-api is not installed")
def test_current_trace_and_span_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    monkeypatch.setattr("smart_tts.telemetry.get_tracer", lambda: provider.get_tracer("smart_tts"))

    with span("smart_tts.test.trace"):
        trace_id = current_trace_id()
        span_id = current_span_id()

    assert trace_id is not None
    assert span_id is not None
    assert len(trace_id) == 32
    assert len(span_id) == 16
