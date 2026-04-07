# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation and Setup
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

## Dependency Rules

- Keep Python dependency specifiers exact where this repository already pins them, including test extras and `build-system`.
- If `pyproject.toml` changes affect resolved packages, verify the result through the lock/install path used by CI.
- Do not introduce floating versions in CI or release automation when exact pins are practical.

### Running the MCP Server
```bash
# Basic run with stdio transport
python src/codealive_mcp_server.py

# With debug mode enabled
python src/codealive_mcp_server.py --debug

# With SSE transport
python src/codealive_mcp_server.py --transport sse --host 0.0.0.0 --port 8000

# With custom API key and base URL
python src/codealive_mcp_server.py --api-key YOUR_KEY --base-url https://custom.url
```

### Docker Usage
```bash
# Build Docker image
docker build -t codealive-mcp .

# Run with Docker
docker run --rm -i -e CODEALIVE_API_KEY=your_key_here codealive-mcp
```

### Testing

#### Quick Smoke Test
After making local changes, quickly verify everything works:
```bash
# Using make (recommended)
make smoke-test

# Or directly
python smoke_test.py

# With valid API key for full testing
CODEALIVE_API_KEY=your_key python smoke_test.py
```

The smoke test:
- ✓ Verifies server starts and connects via stdio
- ✓ Checks all tools are registered correctly
- ✓ Tests each tool responds appropriately
- ✓ Validates parameter handling
- ✓ Runs in ~5 seconds

#### Unit Tests
Run comprehensive unit tests with pytest:
```bash
# Using make
make unit-test

# Or directly
pytest src/tests/ -v

# With coverage
pytest src/tests/ -v --cov=src
```

#### All Tests
Run both smoke tests and unit tests:
```bash
make test
```

## Architecture

This is a Model Context Protocol (MCP) server that provides AI clients with access to CodeAlive's semantic code search and analysis capabilities.

### Core Components

- **`codealive_mcp_server.py`**: Main entry point — bootstraps logging, tracing, registers tools and middleware
- **Five tools**: `get_data_sources`, `codebase_search`, `fetch_artifacts`, `codebase_consultant`, `get_artifact_relationships`
- **`core/client.py`**: `CodeAliveContext` dataclass + `codealive_lifespan` (httpx.AsyncClient lifecycle, `_server_ready` flag)
- **`core/logging.py`**: loguru structured JSON logging + PII masking + OTel context injection
- **`core/observability.py`**: OpenTelemetry TracerProvider setup with OTLP export
- **`middleware/`**: `N8NRemoveParametersMiddleware` (strips n8n extra params) + `ObservabilityMiddleware` (OTel spans per tool call)

### Key Architectural Patterns

1. **FastMCP Framework**: Uses FastMCP 3.x with lifespan context, middleware hooks, and built-in `Client` for testing
2. **HTTP Client Management**: Single persistent `httpx.AsyncClient` with connection pooling, created in lifespan
3. **Streaming Support**: `codebase_consultant` uses SSE streaming (`response.aiter_lines()`) for chat completions
4. **Environment Configuration**: Supports both .env files and command-line arguments with precedence
5. **Error Handling**: Centralized in `utils/errors.py` — all tools use `handle_api_error()` with `method=` prefix
6. **N8N Middleware**: Strips extra parameters (sessionId, action, chatInput, toolCallId) from n8n tool calls before validation
7. **Observability Middleware**: Wraps every `tools/call` in an OTel span with GenAI semantic conventions

### Data Flow

1. AI client connects to MCP server via stdio/HTTP transport
2. Client calls tools (`get_data_sources` → `codebase_search` → `fetch_artifacts` / `codebase_consultant`)
3. Middleware chain runs: N8N cleanup → ObservabilityMiddleware (OTel span + log correlation)
4. Tool translates MCP call to CodeAlive API request (with `X-CodeAlive-*` headers)
5. Response parsed, formatted as XML or text, returned to AI client

### Environment Variables

- `CODEALIVE_API_KEY`: Required API key for CodeAlive service
- `CODEALIVE_BASE_URL`: API base URL (defaults to https://app.codealive.ai)
- `CODEALIVE_IGNORE_SSL`: Set to disable SSL verification (debug mode)
- `DEBUG_MODE`: Set to `true` to enable DEBUG-level logging
- `OTEL_EXPORTER_OTLP_ENDPOINT`: If set, traces are exported via OTLP/HTTP to this endpoint

### Data Source Types

- **Repository**: Individual code repositories with URL and repository ID
- **Workspace**: Collections of repositories accessible via workspace ID
- Tool calls can target specific repositories or entire workspaces for broader context

### Integration Patterns

The server is designed to integrate with:
- Claude Desktop/Code (via settings.json configuration)
- Cursor (via MCP settings panel)
- VS Code with GitHub Copilot (via settings.json)
- Continue (via config.yaml)
- n8n (via AI Agent node with MCP tools)
- Any MCP-compatible AI client

Key integration considerations:
- AI clients should use `get_data_sources` first to discover available repositories/workspaces, then use those IDs for targeted search and chat operations
- **n8n Integration**: The server includes middleware to automatically strip n8n's extra parameters (sessionId, action, chatInput, toolCallId) from tool calls, so n8n works out of the box without any special configuration

## Logging Best Practices

This project uses **loguru** for structured JSON logging. All logs go to **stderr** (safe for stdio MCP transport). Follow these rules strictly when writing or modifying code.

### Rules

1. **Always use loguru, never print() or stdlib logging.** Import: `from loguru import logger`. No `import logging` in application code — stdlib is intercepted via `_InterceptHandler` and routed through loguru automatically.

2. **All logs go to stderr.** The stdio MCP transport uses stdout for protocol messages. Any stray `print()` or stdout write will corrupt the MCP protocol and break the client. If you add a new log sink, it must target `sys.stderr`.

3. **Never call `response.text` without a debug guard.** `log_api_response()` is protected by `_is_debug_enabled()` because reading `response.text` consumes the response body. The `codebase_consultant` tool streams SSE via `response.aiter_lines()` — calling `.text` first would silently consume the stream and produce empty results. If you add new response logging, always check `_is_debug_enabled()` first:
   ```python
   if not _is_debug_enabled():
       return  # Do NOT touch response body at INFO level
   ```

4. **Mask PII in logs.** User queries, questions, messages, and response bodies must never appear in full in logs. Use `_sanitize_body()` for request bodies and truncate response bodies to `_RESPONSE_BODY_MAX_LEN`. The PII fields list is in `_PII_FIELDS` — extend it if you add tools that accept user content.

5. **Mask Authorization headers.** Always replace `Authorization` header values with `"Bearer ***"` in logs. See the pattern in `log_api_request()`.

6. **Use structured logging fields, not string interpolation.** Prefer `logger.bind(request_id=rid).debug("message")` or `logger.info("msg {key}", key=value)` over f-strings in the message. This makes logs machine-parseable.

7. **Use `logger.configure(patcher=...)` for global context injection** (like OTel trace_id). Do NOT pass `patcher` to `logger.add()` — loguru 0.7.x does not support it there.

### OTel Trace Correlation

Every log record automatically gets `trace_id` and `span_id` injected by `_otel_patcher` (registered via `logger.configure`). The `ObservabilityMiddleware` also uses `logger.contextualize(trace_id=..., tool=...)` so all logs within a tool call carry the correlation ID. Do not duplicate this — it's automatic.

## Observability Best Practices

### OpenTelemetry Tracing

- **TracerProvider** is initialized once in `core/observability.py` via `init_tracing()`, called at startup in `main()`.
- If `OTEL_EXPORTER_OTLP_ENDPOINT` is set, traces export via OTLP/HTTP; otherwise a no-op provider is used (trace IDs still appear in logs).
- **`atexit.register(provider.shutdown)`** ensures pending spans are flushed on process exit. Do not skip this if modifying the init logic.
- **HTTPX auto-instrumentation** (`HTTPXClientInstrumentor`) injects `traceparent` headers into all outbound HTTP calls. Do not add manual propagation.

### Middleware Spans

The `ObservabilityMiddleware` creates a span per tool call with these attributes:
- `gen_ai.operation.name` = `"execute_tool"`
- `gen_ai.tool.name` / `mcp.tool.name` = tool name
- `mcp.method` = `"tools/call"`

On errors, the span gets `StatusCode.ERROR` + `record_exception()`. Do not add redundant span creation inside tool functions — the middleware handles it.

### Adding New Tools — Observability Checklist

When adding a new tool, ensure:
1. The tool receives `ctx: Context` as its first argument (required for lifespan context and logging)
2. API requests include all four `X-CodeAlive-*` headers: `Integration`, `Tool`, `Client`, plus `Authorization`
3. Call `log_api_request()` before and `log_api_response()` after the HTTP call
4. Errors go through `handle_api_error(ctx, e, "description", method=_TOOL_NAME)` — this ensures the `[tool_name]` prefix in error messages
5. The middleware automatically wraps the tool in an OTel span — no manual span creation needed

## Tool Response Conventions

### Hint other MCP tools when the response implies a follow-up call

If a tool's response is **meant to be used as input to another MCP tool**, the
response itself MUST embed a `hint` (or equivalent) directing the agent to that
follow-up tool. The hint should explain *what to call next, with what value,
and why*. Do NOT rely on the agent to remember workflow rules from the tool
description alone — descriptions are not always re-read mid-conversation, but
the response is always in front of the model when it decides what to do next.

Examples in this repo:
- `codebase_search` returns a `hint` field telling the agent that `description`
  is a triage pointer only and that real understanding must come from
  `fetch_artifacts(identifier)` or a local `Read(path)`. Implementation:
  `_SEARCH_HINT` in `src/utils/response_transformer.py`.
- `fetch_artifacts` emits a `<hint>…get_artifact_relationships…</hint>` element
  whenever an artifact has call relationships, telling the agent it can drill
  down further. Implementation: `_build_artifacts_xml` in
  `src/tools/fetch_artifacts.py`.

When you add or change a tool whose output is structurally a "pointer" to data
held by another tool (identifiers, IDs, references), add or update the hint in
the same change. If you remove a follow-up workflow, remove the stale hint too.

## Testing Best Practices

The project has **183 tests** across three tiers: unit tests, e2e tool tests, and smoke tests.

### Test Tiers

| Tier | Files | What it tests | How to run |
|------|-------|---------------|------------|
| **Unit** | `test_*.py` (except `test_e2e_*`) | Individual functions, XML builders, error handling, PII masking, middleware | `pytest src/tests/ -v` |
| **E2E** | `test_e2e_tools.py` | Full MCP protocol: Client → FastMCP → tool → mock HTTP → response | `pytest src/tests/test_e2e_tools.py -v` |
| **Smoke** | `smoke_test.py` | Real server startup via stdio, tool registration, basic invocations | `python smoke_test.py` |

### E2E Test Pattern (FastMCP Client)

E2E tests use FastMCP's built-in `Client` class with `httpx.MockTransport` for the backend. This is the canonical pattern — use it for all new tool tests:

```python
from fastmcp import Client, FastMCP

def _server(routes: dict) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server):
        transport = httpx.MockTransport(handler_dispatching_by_path)
        async with httpx.AsyncClient(transport=transport, base_url="https://test.local") as client:
            yield CodeAliveContext(client=client, api_key="", base_url="https://test.local")

    mcp = FastMCP("Test", lifespan=lifespan)
    mcp.tool()(your_tool)
    return mcp

async def test_tool():
    mcp = _server({"/api/endpoint": lambda r: httpx.Response(200, json={...})})
    async with Client(mcp) as client:
        result = await client.call_tool("tool_name", {"arg": "value"})
    assert "expected" in result.content[0].text
```

Key points:
- `httpx.MockTransport` — no network, no external dependencies, tests run in < 1 second
- Custom lifespan yields a real `CodeAliveContext` with a mock-backed httpx client
- `monkeypatch.setenv("CODEALIVE_API_KEY", ...)` for `get_api_key_from_context` fallback
- Use `raise_on_error=False` when testing error paths, then assert on `result.content[0].text`
- For SSE streaming (codebase_consultant), return `httpx.Response(200, text=sse_body)` — `aiter_lines()` works on buffered responses

### Unit Test Patterns

- **OTel tests**: Do NOT use `trace.set_tracer_provider()` in tests — it's global and can only be called once per process. Instead, patch the module-level `_tracer` variable:
  ```python
  with patch("middleware.observability_middleware._tracer", test_tracer):
      ...
  ```
- **Logging level tests**: Set `logging_module._current_level = "DEBUG"` in `setup_method`, restore to `"INFO"` in `teardown_method`.
- **Avoid `InMemorySpanExporter`** — it doesn't exist in current OTel SDK. Use a custom collector:
  ```python
  class _CollectingExporter(SpanExporter):
      def __init__(self):
          self.spans = []
      def export(self, spans):
          self.spans.extend(spans)
          return SpanExportResult.SUCCESS
  ```

### Testing Pitfalls to Avoid

1. **Never mock what you can test through the protocol.** Prefer e2e tests with `Client(mcp)` over mocking `ctx`, `ctx.request_context`, etc. The e2e approach catches middleware issues, lifespan bugs, and serialization problems that mocks hide.
2. **Never consume `response.text` in tests and then test streaming.** The `aiter_lines()` method works on MockTransport responses because httpx buffers the content, but calling `.text` first would consume it.
3. **Always test both success and error paths.** Every tool should have at least: happy path, empty/invalid input, backend HTTP error.
4. **Use `monkeypatch` for env vars, not `os.environ` directly.** This ensures cleanup even if a test fails.
5. **Mark async tests with `@pytest.mark.asyncio`.** The project uses `asyncio_mode = "strict"` — unmarked async tests will be silently skipped.

## Publishing and Releases

### Version Management
When making significant changes, consider incrementing the version in `pyproject.toml`:
```toml
version = "0.3.0"  # Increment for new features, bug fixes, or breaking changes
```

### Automated Publishing
The project uses automated publishing:
- **Trigger**: Push version change to `main` branch
- **Process**: Tests → Build → Docker → MCP Registry → GitHub Release
- **Result**: Available at `io.github.codealive-ai/codealive-mcp` in MCP Registry

### Version Guidelines
- **Patch** (0.2.0 → 0.2.1): Bug fixes, minor improvements
- **Minor** (0.2.0 → 0.3.0): New features, enhancements
- **Major** (0.2.0 → 1.0.0): Breaking changes, major releases

When implementing features or fixes, evaluate if they warrant a version bump for users to benefit from the changes through the MCP Registry.
