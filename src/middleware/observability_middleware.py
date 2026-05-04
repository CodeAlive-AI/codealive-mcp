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

from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from fastmcp.server.middleware import Middleware

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
        tool_arguments = _extract_tool_arguments(context)

        with _tracer.start_as_current_span(
            f"tool {tool_name}",
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
                tool_arguments=tool_arguments,
            ):
                logger.debug("Tool call started: {tool}", tool=tool_name)

                try:
                    result = await call_next(context)
                except Exception as exc:
                    span.set_status(StatusCode.ERROR, str(exc))
                    span.record_exception(exc)
                    logger.bind(
                        error_type=type(exc).__name__,
                        error=str(exc),
                        tool_arguments=tool_arguments,
                    ).opt(exception=exc).warning("Tool call failed: {tool}", tool=tool_name)
                    raise

                span.set_status(StatusCode.OK)
                logger.debug("Tool call completed: {tool}", tool=tool_name)
                return result
