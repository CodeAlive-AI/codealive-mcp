"""Observability middleware — wraps every MCP tool call in an OTel span.

Span attributes follow the GenAI / MCP semantic conventions:
  - ``gen_ai.operation.name``  = ``"execute_tool"``
  - ``gen_ai.tool.name``       = tool name
  - ``mcp.tool.name``          = tool name (MCP-specific alias)
  - ``mcp.method.name``        = ``"tools/call"``

The middleware also injects ``trace_id`` into loguru context via
``logger.contextualize`` so that every log emitted during the tool
execution carries the correlation ID.
"""

import time
from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import context as otel_context, trace
from opentelemetry.trace import Link, SpanKind, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from fastmcp.server.middleware import Middleware

from core.logging import _mapping_shape

if TYPE_CHECKING:
    from fastmcp.server.middleware import CallNext, MiddlewareContext

_tracer = trace.get_tracer("codealive-mcp.tools")


def _message_parent(context: "MiddlewareContext") -> tuple[otel_context.Context | None, list[Link]]:
    """Prefer valid MCP metadata; link the independent HTTP/ambient context.

    https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md
    Extract only W3C tracing fields: arbitrary client baggage is not forwarded.
    """
    meta = getattr(context.message, "meta", None)
    fastmcp_context = getattr(context, "fastmcp_context", None)
    if not isinstance(meta, dict) and fastmcp_context is not None:
        try:
            meta = fastmcp_context.request_context.meta
        except (AttributeError, ValueError, RuntimeError):
            meta = None
    if not isinstance(meta, dict):
        return None, []
    carrier = {
        key: meta[key] for key in ("traceparent", "tracestate")
        if isinstance(meta.get(key), str)
    }
    extracted = TraceContextTextMapPropagator().extract(carrier, context=otel_context.Context())
    remote = trace.get_current_span(extracted)
    remote_context = remote.get_span_context()
    if not remote_context.is_valid:
        return None, []
    ambient = trace.get_current_span().get_span_context()
    distinct_ambient = ambient.is_valid and (
        ambient.trace_id, ambient.span_id
    ) != (remote_context.trace_id, remote_context.span_id)
    links = [Link(ambient)] if distinct_ambient else []
    return trace.set_span_in_context(remote), links


def _extract_tool_arguments(context: "MiddlewareContext") -> dict[str, Any]:
    """Best-effort extraction of raw MCP tool arguments from FastMCP middleware context."""
    message = getattr(context, "message", None)
    args = getattr(message, "arguments", None)
    if isinstance(args, dict):
        return dict(args)

    params = getattr(message, "params", None)
    if isinstance(params, dict):
        args = params.get("arguments")
        if isinstance(args, dict):
            return dict(args)
    else:
        args = getattr(params, "arguments", None)
        if isinstance(args, dict):
            return dict(args)

    if isinstance(message, dict):
        args = message.get("arguments")
        if isinstance(args, dict):
            return dict(args)

        params = message.get("params")
        if isinstance(params, dict):
            args = params.get("arguments")
            if isinstance(args, dict):
                return dict(args)

    return {}


class ObservabilityMiddleware(Middleware):
    """One MCP server span per request; tool hooks enrich it without nesting."""

    async def on_request(self, context: "MiddlewareContext", call_next: "CallNext"):
        method = context.method or "unknown"
        parent, links = _message_parent(context)
        tool = getattr(context.message, "name", "unknown") if method == "tools/call" else None
        with _tracer.start_as_current_span(
            f"{method} {tool}" if tool else method,
            context=parent,
            links=links,
            kind=SpanKind.SERVER,
            record_exception=False,
            set_status_on_exception=False,
            attributes={"mcp.method.name": method},
        ) as span:
            try:
                result = await call_next(context)
            except Exception as exc:
                error_type = type(exc).__name__
                span.set_attribute("error.type", error_type)
                span.set_status(StatusCode.ERROR, error_type)
                span.add_event("exception", {"exception.type": error_type})
                raise

            # In-band tool failures have no Python exception but are still errors.
            if getattr(result, "is_error", False) is True:
                span.set_attribute("error.type", "tool_error")
                span.set_status(StatusCode.ERROR, "tool_error")
            elif span.is_recording():
                span.set_status(StatusCode.OK)
            return result

    async def on_call_tool(self, context: "MiddlewareContext", call_next: "CallNext"):
        tool_name = getattr(context.message, "name", "unknown")
        tool_argument_shape = _mapping_shape(_extract_tool_arguments(context))
        started_at = time.perf_counter()

        span = trace.get_current_span()
        span.set_attributes({
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": tool_name,
            "mcp.tool.name": tool_name,
            "mcp.method.name": "tools/call",
        })
        # on_request owns the single MCP SERVER span. Do not nest another tool
        # span or override the context selected for this message.
        span_ctx = span.get_span_context()
        trace_id = format(span_ctx.trace_id, "032x") if span_ctx.trace_id else ""
        with logger.contextualize(
            trace_id=trace_id,
            tool=tool_name,
            tool_argument_shape=tool_argument_shape,
        ):
            logger.debug("Tool call started: {tool}", tool=tool_name)
            try:
                result = await call_next(context)
            except Exception as exc:
                logger.bind(
                    duration_ms=(time.perf_counter() - started_at) * 1000,
                    error_type=type(exc).__name__,
                ).warning("Tool call failed: {tool}", tool=tool_name)
                raise  # on_request records the exception once, without its text
            finally:
                span.set_attribute("mcp.tool.duration_ms", (time.perf_counter() - started_at) * 1000)
            logger.bind(duration_ms=(time.perf_counter() - started_at) * 1000).debug(
                "Tool call completed: {tool}", tool=tool_name,
            )
            return result
