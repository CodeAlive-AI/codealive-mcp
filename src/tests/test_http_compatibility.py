"""Real transports and an isolated SDK v1 client: no credentials or live backend.

The legacy gate intentionally fails if uv/dependency installation fails. Network
access is needed on its first run; uv caches the isolated, pinned client thereafter.
"""

import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "src/codealive_mcp_server.py"


def isolated_environment():
    return {
        **{key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "TMPDIR", "HOME") if key in os.environ},
        "PYTHON_DOTENV_DISABLED": "1",
        "FASTMCP_MCP_CAMELCASE_COMPAT": "false",
    }


@pytest.fixture(scope="module")
def live_mcp(tmp_path_factory):
    class Requests(list):
        def __init__(self):
            super().__init__()
            self.spans = []

    requests = Requests()

    class Backend(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            if self.path == "/v1/traces":
                from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
                export = ExportTraceServiceRequest.FromString(body)
                for resource in export.resource_spans:
                    for scope in resource.scope_spans:
                        requests.spans.extend((scope.scope.name, span) for span in scope.spans)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            payload = json.loads(body)
            credential = self.headers.get("Authorization")
            requests.append((payload, credential, dict(self.headers)))
            time.sleep(0.01)  # overlap independent requests for credential isolation
            if payload.get("query") == "error":
                result = {"obj": {"error": {"code": "invalid_tool_arguments"}}, "rendered": "repair input"}
            else:
                result = {"rendered": json.dumps({"query": payload.get("query"), "credential": credential, "text": "Привет"}, ensure_ascii=False)}
            body = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    backend = ThreadingHTTPServer(("127.0.0.1", 0), Backend)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **isolated_environment(),
        "CODEALIVE_BASE_URL": f"http://127.0.0.1:{backend.server_port}",
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{backend.server_port}",
        "OTEL_BSP_SCHEDULE_DELAY": "10",
    }
    log = tmp_path_factory.mktemp("mcp-http") / "server.log"
    with log.open("w+") as output:
        process = subprocess.Popen(
            [sys.executable, str(SERVER), "--transport", "http", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, env=env, stdout=output, stderr=output,
        )
        try:
            url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail(log.read_text())
                try:
                    if httpx.get(url + "/health", timeout=0.5).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("MCP startup timed out: " + log.read_text())
            yield url + "/api", env, requests
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            backend.shutdown()
            backend.server_close()
            thread.join(timeout=2)


def wire_result(response):
    response.raise_for_status()
    if response.headers["content-type"].startswith("application/json"):
        return response.json()
    return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))


async def wire_call(url, *, token=None, method="tools/call", params=None, headers=None):
    request_headers = {
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-11-25",
        **(headers or {}),
    }
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers=request_headers, json={
            "jsonrpc": "2.0", "id": 1, "method": method,
            "params": params if params is not None else {"name": "get_data_sources", "arguments": {}},
        })
    return response, wire_result(response)


@pytest.mark.asyncio
async def test_wire_aliases_errors_and_missing_auth(live_mcp):
    url, _, requests = live_mcp
    _, payload = await wire_call(url, method="tools/list", params={})
    tools = payload["result"]["tools"]
    assert len(tools) == 11
    assert all("inputSchema" in tool and "input_schema" not in tool for tool in tools)
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    before = len(requests)
    _, missing = await wire_call(url)
    assert missing["result"]["isError"] is True
    assert len(requests) == before
    _, error = await wire_call(url, token="fake", params={"name": "get_data_sources", "arguments": {"query": "error"}})
    assert error["result"]["isError"] is True
    assert error["result"]["structuredContent"]["error"]["code"] == "invalid_tool_arguments"


@pytest.mark.asyncio
async def test_concurrent_credentials_and_n8n_arguments(live_mcp):
    url, _, _ = live_mcp
    async def request(index):
        _, payload = await wire_call(url, token=f"fake-{index}", params={
            "name": "get_data_sources", "arguments": {"query": str(index), "sessionId": "ignored", "chatInput": "ignored"},
        })
        result = payload["result"]
        assert not result["isError"]
        assert json.loads(result["content"][0]["text"]) == {"query": str(index), "credential": f"Bearer fake-{index}", "text": "Привет"}
    await asyncio.gather(*(request(index) for index in range(8)))


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_current_client_both_protocol_eras(live_mcp, mode):
    url, _, _ = live_mcp
    async with Client(url, auth="fake-current", mode=mode, timeout=10) as client:
        assert len(await client.list_tools()) == 11
        result = await client.call_tool("get_data_sources", {})
        assert not result.is_error
        assert "Привет" in result.content[0].text


def test_actual_sdk_v1_http_and_stdio(live_mcp):
    url, env, _ = live_mcp
    uv = shutil.which("uv")
    assert uv, "uv is required for the isolated legacy SDK compatibility gate"
    script = '''
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
async def check(read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        assert len(tools.tools) == 11
        assert all(t.inputSchema and t.annotations.readOnlyHint for t in tools.tools)
        result = await session.call_tool("get_data_sources", {})
        assert result.isError is False
        assert "Привет" in result.content[0].text
        error = await session.call_tool("get_data_sources", {"query":"error"})
        assert error.isError is True
        assert error.structuredContent["error"]["code"] == "invalid_tool_arguments"
async def main():
    async with streamablehttp_client(sys.argv[1], headers={"Authorization":"Bearer fake-legacy"}) as (read, write, _):
        await check(read, write)
    env = dict(os.environ, CODEALIVE_API_KEY="fake-legacy")
    async with stdio_client(StdioServerParameters(command=sys.argv[2], args=[sys.argv[3]], env=env)) as (read, write):
        await check(read, write)
asyncio.run(main())
'''
    result = subprocess.run(
        [uv, "run", "--no-project", "--isolated", "--with", "mcp==1.28.1", "--exclude-newer", "2026-09-09T00:00:00Z", "python", "-c", script, url, sys.executable, str(SERVER)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["http", "meta", "both", "different", "invalid", "none", "unsampled"])
async def test_trace_propagation_over_real_http(live_mcp, case):
    url, _, requests = live_mcp
    http_trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    meta_trace = "5bf92f3577b34da6a3ce929d0e0e4736" if case == "different" else http_trace
    flags = "00" if case == "unsampled" else "01"
    traceparent = f"00-{http_trace}-00f067aa0ba902b7-{flags}"
    headers = {"X-Trace-Id": "untrusted-never-echo-this"}
    if case in {"http", "both", "different", "unsampled"}:
        headers.update(traceparent=traceparent, tracestate="vendor=value")
    elif case == "invalid":
        headers["traceparent"] = "invalid"
    params = {"name": "get_data_sources", "arguments": {"query": "trace-" + case}}
    if case in {"meta", "both", "different"}:
        params["_meta"] = {"traceparent": f"00-{meta_trace}-11f067aa0ba902b7-01", "tracestate": "vendor=meta"}
    elif case == "invalid":
        params["_meta"] = {"traceparent": 123}
    response, payload = await wire_call(url, token="fake-trace", headers=headers, params=params)
    assert payload["result"]["isError"] is False
    response_id = response.headers["x-trace-id"]
    assert len(response_id) == 32 and int(response_id, 16) != 0
    outbound = next(item[2] for item in reversed(requests) if item[0].get("query") == "trace-" + case)
    parts = outbound["traceparent"].split("-")
    if case in {"meta", "both", "different"}:
        assert parts[1] == meta_trace
        assert outbound["tracestate"] == "vendor=meta"
    else:
        assert parts[1] == response_id
    if case in {"http", "both", "different", "unsampled"}:
        assert response_id == http_trace
    assert parts[2] not in {"00f067aa0ba902b7", "11f067aa0ba902b7"}
    if case == "unsampled":
        assert int(parts[3], 16) & 1 == 0


@pytest.mark.asyncio
async def test_trace_context_isolated_across_concurrent_requests(live_mcp):
    url, _, requests = live_mcp
    async def request(index):
        expected = f"{index + 1:032x}"
        response, _ = await wire_call(url, token="fake", headers={"traceparent": f"00-{expected}-00f067aa0ba902b7-01"}, params={
            "name": "get_data_sources", "arguments": {"query": f"concurrent-trace-{index}"},
        })
        assert response.headers["x-trace-id"] == expected
        outbound = next(item[2] for item in reversed(requests) if item[0].get("query") == f"concurrent-trace-{index}")
        assert outbound["traceparent"].split("-")[1] == expected
    await asyncio.gather(*(request(index) for index in range(10)))


@pytest.mark.asyncio
async def test_exported_message_span_has_http_link_and_no_native_duplicate(live_mcp):
    url, _, requests = live_mcp
    remote_trace = "6bf92f3577b34da6a3ce929d0e0e4736"
    http_trace = "7bf92f3577b34da6a3ce929d0e0e4736"
    response, _ = await wire_call(url, token="fake", headers={
        "traceparent": f"00-{http_trace}-00f067aa0ba902b7-01",
    }, params={"name": "get_data_sources", "arguments": {}, "_meta": {
        "traceparent": f"00-{remote_trace}-11f067aa0ba902b7-01",
    }})
    assert response.headers["x-trace-id"] == http_trace
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        spans = [(scope, span) for scope, span in requests.spans if span.trace_id.hex() == remote_trace]
        if any(scope == "codealive-mcp.tools" for scope, span in spans):
            break
        await asyncio.sleep(0.02)
    else:
        pytest.fail("Local OTLP collector did not receive the MCP span")
    server_spans = [span for _, span in spans if span.kind == 2]  # SERVER
    assert len(server_spans) == 1
    span = server_spans[0]
    assert span.parent_span_id.hex() == "11f067aa0ba902b7"
    assert span.name == "tools/call get_data_sources"
    assert len(span.links) == 1
    assert span.links[0].trace_id.hex() == http_trace
    assert all(scope != "fastmcp" for scope, _ in spans)


@pytest.mark.asyncio
async def test_stdio_message_context_reaches_backend(live_mcp):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _, env, requests = live_mcp
    expected = "8bf92f3577b34da6a3ce929d0e0e4736"
    parameters = StdioServerParameters(
        command=sys.executable, args=[str(SERVER)],
        env={**env, "CODEALIVE_API_KEY": "fake-stdio-trace"},
    )
    async with asyncio.timeout(15):
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_data_sources", {"query": "stdio-trace"}, meta={
                    "traceparent": f"00-{expected}-00f067aa0ba902b7-01",
                })
                assert result.is_error is False
    outbound = next(item[2] for item in reversed(requests) if item[0].get("query") == "stdio-trace")
    assert outbound["traceparent"].split("-")[1] == expected


def test_rejected_host_still_gets_http_trace_id(live_mcp):
    url, _, _ = live_mcp
    expected = "9bf92f3577b34da6a3ce929d0e0e4736"
    response = httpx.post(url, headers={"Host": "untrusted.example", "traceparent": f"00-{expected}-00f067aa0ba902b7-01"})
    assert response.status_code == 421
    assert response.headers["x-trace-id"] == expected
