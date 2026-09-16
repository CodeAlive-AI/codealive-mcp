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
    requests = []

    class Backend(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
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
    env = {**isolated_environment(), "CODEALIVE_BASE_URL": f"http://127.0.0.1:{backend.server_port}"}
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
        [uv, "run", "--no-project", "--isolated", "--with", "mcp==1.28.1", "--exclude-newer", "7 days", "python", "-c", script, url, sys.executable, str(SERVER)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
