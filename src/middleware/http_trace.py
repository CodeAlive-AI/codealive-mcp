"""Explicit HTTP tracing: FastMCP imports Starlette before global patching.

X-Trace-Id identifies the HTTP transport span, never a second generated ID.
SSE headers can precede MCP dispatch, so message traces link to this span when
their own metadata selects a different trace. No body buffering is required.
"""

from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware
from opentelemetry.trace import Span
from opentelemetry.util.http import get_excluded_urls
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_TRACE_ID = "codealive.http_trace_id"


def _capture_trace_id(span: Span, scope: Scope) -> None:
    context = span.get_span_context()
    if context.is_valid:
        scope[_TRACE_ID] = format(context.trace_id, "032x")


class HttpTraceMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = OpenTelemetryMiddleware(
            app,
            server_request_hook=_capture_trace_id,
            excluded_urls=get_excluded_urls("STARLETTE"),
            exclude_spans=["receive", "send"],
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_trace_id(message: Message) -> None:
            trace_id = scope.get(_TRACE_ID)
            if message["type"] == "http.response.start" and trace_id:
                headers = [
                    (key, value) for key, value in message.get("headers", [])
                    if key.lower() != b"x-trace-id"
                ]
                message = {
                    **message,
                    "headers": [*headers, (b"x-trace-id", trace_id.encode("ascii"))],
                }
            await send(message)

        await self.app(scope, receive, send_with_trace_id)
