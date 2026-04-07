"""OpenTelemetry setup for CodeAlive MCP server.

Initialises a ``TracerProvider`` with an OTLP/HTTP exporter when the
``OTEL_EXPORTER_OTLP_ENDPOINT`` env var is set.  Otherwise tracing is
configured as a no-op so the rest of the code can call ``trace.get_tracer()``
unconditionally.

HTTPX client instrumentation is always enabled so outbound HTTP calls
automatically get ``traceparent`` headers injected.
"""

import os

from loguru import logger
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

_SERVICE_NAME = "codealive-mcp"


def init_tracing() -> None:
    """Bootstrap OpenTelemetry tracing.

    * If ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, traces are exported via
      OTLP/HTTP (protobuf) to that endpoint.
    * Otherwise a no-op provider is configured (zero overhead).
    * HTTPX client instrumentation is always enabled so that ``traceparent``
      propagates to the CodeAlive backend regardless of whether traces are
      exported.
    """
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    resource = Resource.create({"service.name": _SERVICE_NAME})

    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
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

    # Auto-instrument httpx so outbound requests carry traceparent
    HTTPXClientInstrumentor().instrument()
