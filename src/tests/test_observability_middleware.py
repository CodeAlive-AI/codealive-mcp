"""Tests for middleware.observability_middleware — OTel spans and loguru context."""

import sys
from typing import Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from middleware.observability_middleware import ObservabilityMiddleware, _extract_tool_arguments


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


def _make_context(tool_name: str = "semantic_search", arguments: dict | None = None):
    ctx = MagicMock()
    ctx.message.name = tool_name
    ctx.message.arguments = arguments or {}
    return ctx


# ---------------------------------------------------------------------------
# Successful tool call
# ---------------------------------------------------------------------------

class TestSuccessfulToolCall:
    @pytest.mark.asyncio
    async def test_returns_result_from_call_next(self, otel_setup):
        middleware = ObservabilityMiddleware()
        context = _make_context("semantic_search")
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

    @pytest.mark.asyncio
    async def test_lifecycle_logs_only_include_tool_argument_shape(self, otel_setup):
        middleware = ObservabilityMiddleware()
        tool_arguments = {"identifier": "org/repo::src/svc.py::run", "profile": "callsOnly"}
        context = _make_context("get_artifact_relationships", tool_arguments)
        call_next = AsyncMock(return_value="ok")
        records = []
        handler_id = logger.add(lambda message: records.append(message.record), level="DEBUG")

        try:
            await middleware.on_call_tool(context, call_next)
        finally:
            logger.remove(handler_id)

        lifecycle = [
            record for record in records
            if record["message"].startswith("Tool call ")
        ]
        assert [record["level"].name for record in lifecycle] == ["DEBUG", "DEBUG"]
        expected_shape = {
            "identifier": {"type": "string", "length": len(tool_arguments["identifier"])},
            "profile": {"type": "string", "length": len(tool_arguments["profile"])},
        }
        assert lifecycle[0]["extra"]["tool_argument_shape"] == expected_shape
        assert lifecycle[1]["extra"]["tool_argument_shape"] == expected_shape
        assert tool_arguments["identifier"] not in str(lifecycle)


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
        context = _make_context("chat")
        call_next = AsyncMock(side_effect=ValueError("bad input"))

        with pytest.raises(ValueError):
            await middleware.on_call_tool(context, call_next)

        span = otel_setup.get_finished_spans()[0]
        assert span.status.status_code == trace.StatusCode.ERROR
        assert span.status.description == "ValueError"

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
        assert exception_events[0].attributes == {"exception.type": "RuntimeError"}

    @pytest.mark.asyncio
    async def test_failure_logs_warning_without_tool_values_or_error_message(self, otel_setup):
        middleware = ObservabilityMiddleware()
        tool_arguments = {
            "identifier": "org/repo::src/svc.py::run",
            "profile": "bogus",
            "max_count_per_type": 50,
        }
        context = _make_context("get_artifact_relationships", tool_arguments)
        call_next = AsyncMock(side_effect=ValueError("bad profile"))
        records = []
        handler_id = logger.add(lambda message: records.append(message.record), level="DEBUG")

        try:
            with pytest.raises(ValueError, match="bad profile"):
                await middleware.on_call_tool(context, call_next)
        finally:
            logger.remove(handler_id)

        failures = [record for record in records if record["message"] == "Tool call failed: get_artifact_relationships"]
        assert len(failures) == 1
        failure = failures[0]
        assert failure["level"].name == "WARNING"
        assert failure["extra"]["tool"] == "get_artifact_relationships"
        assert failure["extra"]["tool_argument_shape"] == {
            "identifier": {"type": "string", "length": len(tool_arguments["identifier"])},
            "profile": {"type": "string", "length": len(tool_arguments["profile"])},
            "max_count_per_type": {"type": "number"},
        }
        assert failure["extra"]["error_type"] == "ValueError"
        assert "error" not in failure["extra"]
        assert tool_arguments["identifier"] not in str(failure)
        assert "bad profile" not in str(failure)


class TestExtractToolArguments:
    def test_extracts_fastmcp_arguments(self):
        context = _make_context("tool", {"name": "value"})
        assert _extract_tool_arguments(context) == {"name": "value"}

    def test_extracts_json_rpc_params_arguments(self):
        context = MagicMock()
        context.message = {"params": {"arguments": {"identifier": "id"}}}
        assert _extract_tool_arguments(context) == {"identifier": "id"}

    def test_returns_empty_dict_when_unavailable(self):
        context = MagicMock()
        context.message = object()
        assert _extract_tool_arguments(context) == {}
