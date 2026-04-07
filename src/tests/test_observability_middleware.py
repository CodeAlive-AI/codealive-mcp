"""Tests for middleware.observability_middleware — OTel spans and loguru context."""

import sys
from typing import Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from middleware.observability_middleware import ObservabilityMiddleware


class _CollectingExporter(SpanExporter):
    """Minimal in-memory exporter that collects finished spans."""

    def __init__(self):
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def get_finished_spans(self) -> list[ReadableSpan]:
        return list(self.spans)


@pytest.fixture
def otel_setup():
    """Create a TracerProvider with in-memory exporter and patch the middleware's _tracer.

    Avoids touching the global TracerProvider (which can only be set once per process).
    Instead we patch the module-level ``_tracer`` so the middleware uses our provider.
    """
    exporter = _CollectingExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    with patch("middleware.observability_middleware._tracer", tracer):
        yield exporter

    provider.shutdown()


def _make_context(tool_name: str = "codebase_search"):
    ctx = MagicMock()
    ctx.message.name = tool_name
    return ctx


# ---------------------------------------------------------------------------
# Successful tool call
# ---------------------------------------------------------------------------

class TestSuccessfulToolCall:
    @pytest.mark.asyncio
    async def test_returns_result_from_call_next(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context("codebase_search")
        call_next = AsyncMock(return_value="<results>xml</results>")

        result = await middleware.on_call_tool(context, call_next)

        assert result == "<results>xml</results>"
        call_next.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_creates_span_with_correct_attributes(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context("get_data_sources")
        call_next = AsyncMock(return_value="ok")

        await middleware.on_call_tool(context, call_next)

        spans = otel_setup.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "tool get_data_sources"
        assert span.attributes["gen_ai.operation.name"] == "execute_tool"
        assert span.attributes["gen_ai.tool.name"] == "get_data_sources"
        assert span.attributes["mcp.tool.name"] == "get_data_sources"
        assert span.attributes["mcp.method"] == "tools/call"

    @pytest.mark.asyncio
    async def test_span_status_ok_on_success(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context()
        call_next = AsyncMock(return_value="ok")

        await middleware.on_call_tool(context, call_next)

        span = otel_setup.get_finished_spans()[0]
        assert span.status.status_code == trace.StatusCode.OK

    @pytest.mark.asyncio
    async def test_handles_missing_tool_name(self, otel_setup):
        middleware = ObservabilityMiddleware()
        # message exists but has no .name attribute
        context = MagicMock()
        context.message = type("Msg", (), {})()
        call_next = AsyncMock(return_value="ok")

        await middleware.on_call_tool(context, call_next)

        span = otel_setup.get_finished_spans()[0]
        assert span.name == "tool unknown"
        assert span.attributes["mcp.tool.name"] == "unknown"


# ---------------------------------------------------------------------------
# Failed tool call
# ---------------------------------------------------------------------------

class TestFailedToolCall:
    @pytest.mark.asyncio
    async def test_propagates_exception(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context()
        call_next = AsyncMock(side_effect=RuntimeError("connection timeout"))

        with pytest.raises(RuntimeError, match="connection timeout"):
            await middleware.on_call_tool(context, call_next)

    @pytest.mark.asyncio
    async def test_span_status_error_on_failure(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context("codebase_consultant")
        call_next = AsyncMock(side_effect=ValueError("bad input"))

        with pytest.raises(ValueError):
            await middleware.on_call_tool(context, call_next)

        span = otel_setup.get_finished_spans()[0]
        assert span.status.status_code == trace.StatusCode.ERROR
        assert "bad input" in span.status.description

    @pytest.mark.asyncio
    async def test_span_records_exception_event(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context()
        call_next = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            await middleware.on_call_tool(context, call_next)

        span = otel_setup.get_finished_spans()[0]
        exception_events = [e for e in span.events if e.name == "exception"]
        assert len(exception_events) >= 1
        # At least one event must carry the exception details
        types = [e.attributes["exception.type"] for e in exception_events]
        messages = [e.attributes["exception.message"] for e in exception_events]
        assert "RuntimeError" in types
        assert "boom" in messages
