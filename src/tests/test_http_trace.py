"""ASGI response instrumentation must preserve streaming and avoid body reads."""

import asyncio
import sys
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace
from opentelemetry.instrumentation._semconv import _OpenTelemetrySemanticConventionStability
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleware.http_trace import HttpTraceMiddleware
from core.observability import _SanitizingSpanExporter


@pytest.mark.asyncio
async def test_trace_header_precedes_stream_completion_without_buffering(monkeypatch):
    release = asyncio.Event()
    started = asyncio.Event()
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/event-stream")]})
        await send({"type": "http.response.body", "body": b"data: first\n\n", "more_body": True})
        started.set()
        await release.wait()
        await send({"type": "http.response.body", "body": b"data: last\n\n", "more_body": False})

    async def receive():
        pytest.fail("Tracing must not consume the request body")

    async def send(message):
        sent.append(message)

    provider = TracerProvider()
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    wrapped = HttpTraceMiddleware(app)
    scope = {
        "type": "http", "method": "POST", "path": "/api", "scheme": "http",
        "http_version": "1.1", "server": ("localhost", 80), "query_string": b"",
        "headers": [(b"traceparent", b"00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")],
    }
    task = asyncio.create_task(wrapped(scope, receive, send))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert not task.done()
        assert dict(sent[0]["headers"])[b"x-trace-id"] == b"4bf92f3577b34da6a3ce929d0e0e4736"
        assert sent[1]["body"] == b"data: first\n\n"
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=2)
        provider.shutdown()
    assert sent[-1]["body"] == b"data: last\n\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["", "http", "http/dup"])
async def test_real_http_spans_are_sanitized_in_all_semconv_modes(monkeypatch, mode):
    monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", mode)
    # This setting is cached process-wide by OTel; restore its state after each case.
    monkeypatch.setattr(_OpenTelemetrySemanticConventionStability, "_initialized", False)
    monkeypatch.setattr(_OpenTelemetrySemanticConventionStability, "_OTEL_SEMCONV_STABILITY_SIGNAL_MAPPING", {})
    monkeypatch.delenv("OTEL_PYTHON_STARLETTE_EXCLUDED_URLS", raising=False)
    raw, exported = InMemorySpanExporter(), InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(raw))
    provider.add_span_processor(SimpleSpanProcessor(_SanitizingSpanExporter(exported)))
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        pytest.fail("Tracing must not read the body")

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "method": "POST", "path": "/private-path", "scheme": "http",
        "http_version": "1.1", "server": ("private-server", 8000),
        "client": ("203.0.113.7", 5555), "query_string": b"token=private-token",
        "headers": [(b"host", b"private-host"), (b"user-agent", b"private-agent")],
    }
    try:
        await HttpTraceMiddleware(app)(scope, receive, send)
        original, = raw.get_finished_spans()
        sanitized, = exported.get_finished_spans()
        assert "203.0.113.7" in original.to_json()  # prove the instrumentation emitted it
        for sensitive in ("203.0.113.7", "private-host", "private-agent", "private-token", "private-path", "private-server"):
            assert sensitive not in sanitized.to_json()
        assert sanitized.context == original.context
        assert sanitized.attributes.get("http.status_code", sanitized.attributes.get("http.response.status_code")) == 200
        assert dict(sent[0]["headers"])[b"x-trace-id"] == format(sanitized.context.trace_id, "032x").encode()
    finally:
        provider.shutdown()


@pytest.mark.asyncio
async def test_excluded_url_has_no_span_or_trace_header(monkeypatch):
    monkeypatch.setenv("OTEL_PYTHON_STARLETTE_EXCLUDED_URLS", "http://localhost/health")
    provider = TracerProvider()
    exported = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exported))
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        pytest.fail("Tracing must not read the body")

    async def send(message):
        sent.append(message)

    try:
        await HttpTraceMiddleware(app)({
            "type": "http", "method": "GET", "path": "/health", "scheme": "http",
            "http_version": "1.1", "server": ("localhost", 80), "query_string": b"", "headers": [],
        }, receive, send)
        assert exported.get_finished_spans() == ()
        assert b"x-trace-id" not in dict(sent[0]["headers"])
    finally:
        provider.shutdown()
