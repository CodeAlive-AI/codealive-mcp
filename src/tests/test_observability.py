"""Tests for core.observability — OTel TracerProvider bootstrap."""

import sys
from unittest.mock import patch, MagicMock

import pytest
from opentelemetry import trace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from core.observability import init_tracing, _SERVICE_NAME


class TestInitTracing:
    def test_no_endpoint_creates_provider_without_exporter(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        with patch("core.observability.HTTPXClientInstrumentor") as mock_instrumentor:
            with patch("core.observability.trace.set_tracer_provider") as mock_set:
                init_tracing()

                mock_set.assert_called_once()
                provider = mock_set.call_args[0][0]
                from opentelemetry.sdk.trace import TracerProvider
                assert isinstance(provider, TracerProvider)
                mock_instrumentor.return_value.instrument.assert_called_once()

    def test_with_endpoint_creates_otlp_exporter(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

        mock_exporter = MagicMock()
        mock_processor = MagicMock()

        with patch("core.observability.HTTPXClientInstrumentor") as mock_instrumentor:
            with patch("core.observability.trace.set_tracer_provider"):
                with patch(
                    "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
                    return_value=mock_exporter,
                ) as mock_exporter_cls:
                    with patch(
                        "opentelemetry.sdk.trace.export.BatchSpanProcessor",
                        return_value=mock_processor,
                    ) as mock_processor_cls:
                        init_tracing()

                        mock_exporter_cls.assert_called_once_with(endpoint="http://localhost:4318")
                        mock_processor_cls.assert_called_once_with(mock_exporter)
                        mock_instrumentor.return_value.instrument.assert_called_once()

    def test_httpx_instrumentor_always_called(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        with patch("core.observability.HTTPXClientInstrumentor") as mock_instrumentor:
            with patch("core.observability.trace.set_tracer_provider"):
                init_tracing()
                mock_instrumentor.return_value.instrument.assert_called_once()

    def test_service_name_in_resource(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        with patch("core.observability.HTTPXClientInstrumentor"):
            with patch("core.observability.trace.set_tracer_provider") as mock_set:
                init_tracing()

                provider = mock_set.call_args[0][0]
                resource_attrs = dict(provider.resource.attributes)
                assert resource_attrs["service.name"] == _SERVICE_NAME
