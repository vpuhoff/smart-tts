import pytest

from smart_tts.extensions.otel import configure_tracing, shutdown_tracing
from smart_tts.telemetry import is_enabled, span


@pytest.mark.skipif(not is_enabled(), reason="opentelemetry-api is not installed")
def test_configure_tracing_console_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    import smart_tts.extensions.otel as otel_ext

    monkeypatch.setattr(otel_ext, "_provider", None)
    try:
        provider = configure_tracing(console=True)
        assert provider is not None

        with span("smart_tts.test.configure"):
            pass
    finally:
        shutdown_tracing()
