# MCP trace correlation

There are two scopes: the HTTP transport request and the MCP message. They need
not have the same parent or even the same trace. OpenTelemetry's MCP conventions
recommend message metadata as parent and a span link to the ambient transport:
https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/mcp.md

## Contract

- HTTP `traceparent` / `tracestate` are extracted by explicit ASGI instrumentation.
  Missing or invalid context starts a new transport trace. Host/auth rejections
  inside the app are covered. Excluded URLs deliberately have no tracing header.
- Valid `params._meta.traceparent` parents the MCP SERVER span, with an ambient
  HTTP span link where applicable. Without valid metadata the HTTP/current context
  remains the parent. STDIO accepts the same metadata without needing HTTP.
- Startup selects FastMCP `propagation_only`; our middleware owns one MCP SERVER
  span per request. The tool hook enriches it; it does not create a duplicate.
- Existing HTTPX instrumentation injects the active context into backend calls.
  ASP.NET Core continues that W3C trace and creates its own span. Do not manually
  overwrite backend tracing headers or use `HttpContext.TraceIdentifier` as Trace ID.
- `X-Trace-Id` is an additive **response** header containing the HTTP span's
  32-character Trace ID. Incoming `X-Trace-Id` is ignored. No second ID is generated.
  With ordinary HTTP propagation it equals the backend Trace ID. With metadata-only
  or conflicting contexts, the MCP/backend trace can differ; follow its HTTP span
  link. Never claim this header identifies every message on a stream.
- The header is sent at response start without buffering or parsing bodies. SSE
  headers may precede tool dispatch. Requests failing before the instrumented app,
  including proxy-generated errors, need proxy-side diagnostics instead.
- Caddy should pass tracing headers through unchanged. It need not generate spans
  or inspect MCP bodies. Browsers require an explicitly scoped CORS expose-header
  configuration to read the custom response header; this change adds no CORS grants.
- Trace IDs exist without an exporter and on unsampled requests; an ID does not
  promise a retained Tempo trace. Respect sampling. Arbitrary metadata baggage is
  not copied downstream by our MCP extraction, and payloads/tokens are not added
  to spans.

For timeout investigation clients should record outgoing `traceparent`, request
time and JSON-RPC ID before sending. A response header cannot help if no response
arrives. `X-Trace-Id` is a convenience for support, not an MCP/W3C requirement.

## Local verification

`uv run --locked --extra test pytest src/tests/ -q` covers real HTTP and stdio,
old SDK clients, no/header/meta/conflicting/invalid/unsampled contexts, concurrent
isolation, backend propagation, in-band errors, cancellation cleanup, and SSE
header delivery before stream completion. A local OTLP receiver verifies the
message parent, HTTP link and absence of duplicate native FastMCP spans.

On 2026-09-16 a separate local chain was also exercised:
client → Caddy 2.10.2 → this MCP entrypoint → ASP.NET Core 10 minimal endpoint.
The .NET endpoint reported `Activity.Current.TraceId`, `SpanId`, `ParentSpanId`
and the incoming header. Before this change HTTP-only context was lost; after it,
the supplied Trace ID survived and the .NET parent matched the outbound HTTP span.
Metadata-only and context-free calls were also checked. This is framework-level
interoperability evidence, not a full production backend or live OAuth test.

No production deployment, sampling change, timeout change or logging-retention
change is part of this tracing commit.
