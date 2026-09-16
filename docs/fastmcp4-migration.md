# FastMCP 4 compatibility

Runtime pins: FastMCP 4.0.3 and MCP SDK 2.2.0. The newer 4.0.4 release
was inside the repository's seven-day quarantine at migration time.

The endpoint, tool names/schemas, Bearer and OAuth credential handling, and
Tool API v3 response formats are unchanged. SDK v2 uses snake_case Python
attributes; MCP JSON still uses camelCase aliases. We do not require customers
to upgrade their MCP clients together with this server.

`src/tests/test_http_compatibility.py` starts the real entrypoint with a local
fake backend, exercises current clients in auto and legacy modes, and runs a
separate MCP SDK 1.28.1 client over HTTP and stdio. It checks wire aliases,
in-band errors, Unicode, missing credentials, concurrent credential isolation,
and n8n's extra arguments. The old-client environment is isolated with uv;
its first run needs package-index access. Installation failures fail the gate.

Run both commands before release:

```sh
PYTHON_DOTENV_DISABLED=1 uv run --locked --extra test pytest src/tests/ -q
PYTHON_DOTENV_DISABLED=1 FASTMCP_MCP_CAMELCASE_COMPAT=false uv run --locked --extra test pytest src/tests/ -q
```

FastMCP's internal HTTP stack uses httpx2. Our Tool API client and token exchange
continue using the separately pinned httpx; their error handling and HTTPX
instrumentation must not be mechanically converted to httpx2. The existing
`X-CodeAlive-Client: fastmcp-v3` label is deliberately retained as a compatibility
identifier, not a report of the installed framework version.

This change does not adopt background tasks, MRTR, shared session stores or
public caching. It does not diagnose or fix the reported production timeouts.
OAuth unit/protocol tests are local; live customer OAuth providers and individual
GUI clients still require release validation. No production rollout is implied.
