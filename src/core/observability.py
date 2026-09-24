"""OpenTelemetry setup for CodeAlive MCP server.

Initialises a ``TracerProvider`` with an OTLP/HTTP exporter when either the
generic or traces-specific OTLP endpoint is configured. Otherwise tracing is
configured without an exporter so the rest of the code can call
``trace.get_tracer()`` unconditionally.

Explicit ASGI and HTTPX instrumentation connect inbound MCP requests to outbound
CodeAlive API calls without recording request or response bodies.
"""

import atexit
import os
from collections.abc import Sequence

from fastmcp import settings as fastmcp_settings
from loguru import logger
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Status

_SERVICE_NAME = "codealive-mcp"

_SENSITIVE_ATTRIBUTE_PREFIXES = (
    "enduser.",
    "http.request.header.",
    "http.response.header.",
)
_SENSITIVE_ATTRIBUTES = {
    "client.address",
    "client.port",
    # ASGI 0.64b0 emits legacy names by default; http/dup emits both sets.
    "net.peer.ip",
    "net.peer.port",
    "http.host",
    "http.server_name",
    "http.target",
    "http.user_agent",
    "http.url",
    "mcp.session.id",
    "mcp.resource.uri",
    "network.peer.address",
    "network.peer.port",
    "server.address",
    "url.path",
    "url.full",
    "url.query",
    "user_agent.original",
}


class _SanitizingSpanExporter(SpanExporter):
    """Remove client data added by framework auto-instrumentation before export."""

    def __init__(self, delegate: SpanExporter) -> None:
        self._delegate = delegate

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._delegate.export(tuple(self._sanitize(span) for span in spans))

    def shutdown(self) -> None:
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._delegate.force_flush(timeout_millis)

    @staticmethod
    def _sanitize(span: ReadableSpan) -> ReadableSpan:
        attributes = {
            key: value
            for key, value in span.attributes.items()
            if key not in _SENSITIVE_ATTRIBUTES
            and not key.startswith(_SENSITIVE_ATTRIBUTE_PREFIXES)
        }
        events = tuple(
            Event(
                event.name,
                {"exception.type": event.attributes["exception.type"]}
                if event.name == "exception"
                and event.attributes
                and "exception.type" in event.attributes
                else {},
                event.timestamp,
            )
            for event in span.events
        )
        return ReadableSpan(
            name=span.name,
            context=span.context,
            parent=span.parent,
            resource=span.resource,
            attributes=attributes,
            events=events,
            links=span.links,
            kind=span.kind,
            status=Status(span.status.status_code),
            start_time=span.start_time,
            end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )


def _resource_attributes() -> dict[str, str]:
    """Build low-cardinality resource identity from deployment metadata only."""
    attributes = {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", _SERVICE_NAME),
        "k8s.container.name": "mcp-server",
    }
    optional_attributes = {
        "service.version": os.environ.get("CODEALIVE_MCP_VERSION"),
        "service.instance.id": os.environ.get("POD_NAME")
        or os.environ.get("HOSTNAME"),
        "deployment.environment.name": os.environ.get("DEPLOYMENT_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT"),
        "k8s.namespace.name": os.environ.get("POD_NAMESPACE"),
        "k8s.pod.name": os.environ.get("POD_NAME"),
        "k8s.node.name": os.environ.get("NODE_NAME"),
    }
    attributes.update(
        {key: value for key, value in optional_attributes.items() if value}
    )
    return attributes


def init_tracing() -> None:
    """Bootstrap OpenTelemetry tracing.

    * If a generic or traces-specific OTLP endpoint is set, traces are exported
      via OTLP/HTTP (protobuf). The exporter reads the standard OTel env vars so
      it can apply the correct ``/v1/traces`` path semantics.
    * Otherwise a provider without an exporter is configured (no network I/O).
    * HTTPX client instrumentation is always enabled so that ``traceparent``
      propagates to the CodeAlive backend regardless of whether traces are
      exported.
    """
    otlp_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    ) or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    resource = Resource.create(_resource_attributes())

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Do not pass the endpoint explicitly. The exporter distinguishes the
        # signal-specific URL from the generic base URL and appends /v1/traces
        # only where the OTel environment-variable contract requires it.
        exporter = OTLPSpanExporter()
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(_SanitizingSpanExporter(exporter))
        )
        trace.set_tracer_provider(provider)

        logger.info(
            "OTel tracing enabled, exporting to {endpoint}",
            endpoint=otlp_endpoint,
        )
    else:
        # Lightweight provider so trace IDs still appear in logs,
        # but nothing is exported.
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        logger.info("OTel tracing enabled (no exporter configured)")

    # Flush pending spans on process exit
    atexit.register(provider.shutdown)

    # HTTP instrumentation is explicit in the transport middleware: globally
    # patching Starlette here misses FastMCP's already-imported Starlette class.
    # Own the MCP spans in our middleware, including metadata-first parenting.
    # Native FastMCP 4.0.3 prefers ambient HTTP context over message metadata.
    fastmcp_settings.telemetry_mode = "propagation_only"
    HTTPXClientInstrumentor().instrument()
