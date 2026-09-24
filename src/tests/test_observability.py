"""Tests for core.observability — OTel TracerProvider bootstrap."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.sdk.trace.sampling import Decision
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from core.observability import _SERVICE_NAME, _SanitizingSpanExporter, init_tracing


class TestInitTracing:
    def test_standard_sampler_environment_controls_root_sampling(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", "parentbased_traceidratio")
        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.05")

        with patch("core.observability.HTTPXClientInstrumentor"):
            with patch("core.observability.fastmcp_settings"):
                with patch("core.observability.trace.set_tracer_provider") as mock_set:
                    init_tracing()

        sampler = mock_set.call_args[0][0].sampler
        assert sampler.should_sample(None, 1, "sampled").decision == Decision.RECORD_AND_SAMPLE
        assert sampler.should_sample(
            None,
            (1 << 128) - 1,
            "dropped",
        ).decision == Decision.DROP

    def test_no_endpoint_creates_provider_without_exporter(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

        with patch("core.observability.HTTPXClientInstrumentor") as mock_httpx:
            with patch("core.observability.fastmcp_settings") as mock_starlette:
                with patch("core.observability.trace.set_tracer_provider") as mock_set:
                    init_tracing()

                    mock_set.assert_called_once()
                    provider = mock_set.call_args[0][0]
                    from opentelemetry.sdk.trace import TracerProvider
                    assert isinstance(provider, TracerProvider)
                    mock_httpx.return_value.instrument.assert_called_once_with()
                    assert mock_starlette.telemetry_mode == "propagation_only"

    @pytest.mark.parametrize(
        "variable",
        ["OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"],
    )
    def test_with_endpoint_creates_environment_configured_otlp_exporter(
        self, monkeypatch, variable
    ):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv(variable, "http://localhost:4318")

        mock_exporter = MagicMock()
        mock_processor = MagicMock()

        with patch("core.observability.HTTPXClientInstrumentor"):
            with patch("core.observability.fastmcp_settings"):
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

                            # Let the exporter implement the standard OTel env contract,
                            # including appending /v1/traces to the generic endpoint.
                            mock_exporter_cls.assert_called_once_with()
                            sanitized_exporter = mock_processor_cls.call_args[0][0]
                            assert isinstance(sanitized_exporter, _SanitizingSpanExporter)
                            assert sanitized_exporter._delegate is mock_exporter

    def test_transport_instrumentors_always_called(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

        with patch("core.observability.HTTPXClientInstrumentor") as mock_httpx:
            with patch("core.observability.fastmcp_settings") as mock_starlette:
                with patch("core.observability.trace.set_tracer_provider"):
                    init_tracing()
                    mock_httpx.return_value.instrument.assert_called_once_with()
                    assert mock_starlette.telemetry_mode == "propagation_only"

    def test_resource_uses_safe_environment_metadata(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-mcp")
        monkeypatch.setenv("CODEALIVE_MCP_VERSION", "sha-deadbeef")
        monkeypatch.setenv("POD_NAME", "mcp-abc")
        monkeypatch.setenv("POD_NAMESPACE", "codealive")
        monkeypatch.setenv("NODE_NAME", "gke-node-1")
        monkeypatch.setenv("ENVIRONMENT", "production")

        with patch("core.observability.HTTPXClientInstrumentor"):
            with patch("core.observability.fastmcp_settings"):
                with patch("core.observability.trace.set_tracer_provider") as mock_set:
                    init_tracing()

        attrs = dict(mock_set.call_args[0][0].resource.attributes)
        assert attrs["service.name"] == "custom-mcp"
        assert attrs["service.version"] == "sha-deadbeef"
        assert attrs["service.instance.id"] == "mcp-abc"
        assert attrs["deployment.environment.name"] == "production"
        assert attrs["k8s.namespace.name"] == "codealive"
        assert attrs["k8s.pod.name"] == "mcp-abc"
        assert attrs["k8s.node.name"] == "gke-node-1"
        assert attrs["k8s.container.name"] == "mcp-server"

    def test_service_name_defaults_when_metadata_is_absent(self, monkeypatch):
        for variable in (
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
            "OTEL_SERVICE_NAME",
            "CODEALIVE_MCP_VERSION",
            "POD_NAME",
            "POD_NAMESPACE",
            "NODE_NAME",
            "ENVIRONMENT",
            "DEPLOYMENT_ENVIRONMENT",
        ):
            monkeypatch.delenv(variable, raising=False)

        with patch("core.observability.HTTPXClientInstrumentor"):
            with patch("core.observability.fastmcp_settings"):
                with patch("core.observability.trace.set_tracer_provider") as mock_set:
                    init_tracing()

        resource_attrs = dict(mock_set.call_args[0][0].resource.attributes)
        assert resource_attrs["service.name"] == _SERVICE_NAME


def test_exporter_removes_sensitive_framework_telemetry():
    delegate = MagicMock()
    delegate.export.return_value = MagicMock()
    exporter = _SanitizingSpanExporter(delegate)
    context = SpanContext(
        trace_id=1,
        span_id=2,
        is_remote=False,
        trace_flags=TraceFlags.SAMPLED,
    )
    span = ReadableSpan(
        name="tools/call semantic_search",
        context=context,
        resource=Resource.create({"service.name": "codealive-mcp"}),
        kind=SpanKind.SERVER,
        attributes={
            "mcp.method.name": "tools/call",
            "gen_ai.tool.name": "semantic_search",
            "enduser.id": "client-secret-id",
            "mcp.session.id": "session-secret",
            "mcp.resource.uri": "repo://secret/path",
            "url.full": "https://mcp.example/api?code=oauth-secret",
            "url.query": "code=oauth-secret",
            "http.request.header.authorization": ("Bearer secret",),
        },
        events=(
            Event(
                "exception",
                {
                    "exception.type": "ValueError",
                    "exception.message": "secret query text",
                    "exception.stacktrace": "secret stack",
                },
                1,
            ),
        ),
        status=Status(StatusCode.ERROR, "secret query text"),
    )

    exporter.export((span,))

    exported = delegate.export.call_args[0][0][0]
    assert exported.context == context
    assert exported.attributes == {
        "mcp.method.name": "tools/call",
        "gen_ai.tool.name": "semantic_search",
    }
    assert exported.status.status_code == StatusCode.ERROR
    assert exported.status.description is None
    assert exported.events[0].attributes == {"exception.type": "ValueError"}
    assert "secret" not in exported.to_json()
