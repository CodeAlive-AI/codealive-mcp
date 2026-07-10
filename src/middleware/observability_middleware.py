"""Observability middleware — wraps every MCP tool call in an OTel span.

Span attributes follow the GenAI / MCP semantic conventions (April 2026):
  - ``gen_ai.operation.name``  = ``"execute_tool"``
  - ``gen_ai.tool.name``       = tool name
  - ``mcp.tool.name``          = tool name (MCP-specific alias)
  - ``mcp.method``             = ``"tools/call"``

The middleware also injects ``trace_id`` into loguru context via
``logger.contextualize`` so that every log emitted during the tool
execution carries the correlation ID.
"""

import time
from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from fastmcp.server.middleware import Middleware

from core.logging import _mapping_shape

if TYPE_CHECKING:
    from fastmcp.server.middleware import CallNext, MiddlewareContext

_tracer = trace.get_tracer("codealive-mcp.tools")


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
    """Wrap each ``tools/call`` in an OTel span and log its outcome."""

    async def on_call_tool(self, context: "MiddlewareContext", call_next: "CallNext"):
        tool_name = getattr(context.message, "name", "unknown")
        tool_argument_shape = _mapping_shape(_extract_tool_arguments(context))
        started_at = time.perf_counter()

        with _tracer.start_as_current_span(
            f"tool {tool_name}",
            record_exception=False,
            set_status_on_exception=False,
            attributes={
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_name,
                "mcp.tool.name": tool_name,
                "mcp.method": "tools/call",
            },
        ) as span:
            # Inject trace_id into loguru so every log inside the tool carries it
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
                    duration_ms = (time.perf_counter() - started_at) * 1000
                    error_type = type(exc).__name__
                    span.set_attribute("mcp.tool.duration_ms", duration_ms)
                    span.set_attribute("error.type", error_type)
                    span.set_status(StatusCode.ERROR, error_type)
                    span.add_event("exception", {"exception.type": error_type})
                    logger.bind(
                        duration_ms=duration_ms,
                        error_type=error_type,
                    ).warning("Tool call failed: {tool}", tool=tool_name)
                    raise

                duration_ms = (time.perf_counter() - started_at) * 1000
                span.set_attribute("mcp.tool.duration_ms", duration_ms)
                span.set_status(StatusCode.OK)
                logger.bind(duration_ms=duration_ms).debug(
                    "Tool call completed: {tool}",
                    tool=tool_name,
                )
                return result
