"""ASGI response instrumentation must preserve streaming and avoid body reads."""

import asyncio
import sys
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleware.http_trace import HttpTraceMiddleware, _capture_trace_id


@pytest.mark.asyncio
async def test_trace_header_precedes_stream_completion_without_buffering():
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
    wrapped = HttpTraceMiddleware(app)
    # Inject a local provider instead of changing the process-global provider.
    wrapped.app = OpenTelemetryMiddleware(app, tracer_provider=provider, server_request_hook=_capture_trace_id, exclude_spans=["receive", "send"])
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
