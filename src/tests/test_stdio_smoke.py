"""STDIO smoke tests for the real MCP server entrypoint."""

import asyncio
import json
import os
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@contextmanager
def _mock_codealive_server():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "tool": self.headers.get("X-CodeAlive-Tool"),
                    "integration": self.headers.get("X-CodeAlive-Integration"),
                    "client": self.headers.get("X-CodeAlive-Client"),
                }
            )
            if self.path == "/api/datasources/ready":
                body = json.dumps(
                    [
                        {
                            "id": "repo-1",
                            "name": "backend",
                            "type": "Repository",
                            "url": "https://github.com/CodeAlive-AI/backend",
                            "state": "Ready",
                        },
                        {
                            "id": "ws-1",
                            "name": "core-workspace",
                            "type": "Workspace",
                            "repositoryIds": ["repo-1"],
                            "state": "Alive",
                        },
                    ]
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], requests
    finally:
        server.shutdown()
        thread.join(timeout=1)


@pytest.mark.asyncio
async def test_stdio_server_lists_tools_and_uses_normalized_ready_endpoint():
    server_script = Path(__file__).resolve().parents[1] / "codealive_mcp_server.py"

    with _mock_codealive_server() as (port, requests):
        env = {
            **os.environ,
            "CODEALIVE_API_KEY": "stdio-smoke-test-key",
            "CODEALIVE_BASE_URL": f"http://127.0.0.1:{port}/api",
        }
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_script)],
            env=env,
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tool_names = sorted(tool.name for tool in tools_result.tools)
                assert tool_names == [
                    "codebase_consultant",
                    "codebase_search",
                    "fetch_artifacts",
                    "get_artifact_relationships",
                    "get_data_sources",
                ]

                result = await session.call_tool("get_data_sources", {})
                assert result.isError is False
                text_content = result.content[0].text
                assert "backend" in text_content
                assert "core-workspace" in text_content
                assert "repositoryIds" not in text_content

        assert requests == [
            {
                "path": "/api/datasources/ready",
                "authorization": "Bearer stdio-smoke-test-key",
                "tool": "get_data_sources",
                "integration": "mcp",
                "client": "fastmcp",
            }
        ]
