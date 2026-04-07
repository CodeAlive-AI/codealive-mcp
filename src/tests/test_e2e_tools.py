"""End-to-end tests for MCP tools using FastMCP's built-in Client.

Each test builds a FastMCP server with the real tool functions, a custom
lifespan backed by httpx.MockTransport, and exercises the tool through
the in-memory MCP transport — covering argument validation, HTTP
call dispatch, response parsing, and XML/text formatting in a single pass.
"""

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx
import pytest
from fastmcp import Client, FastMCP

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import CodeAliveContext
from tools import (
    codebase_consultant,
    codebase_search,
    fetch_artifacts,
    get_artifact_relationships,
    get_data_sources,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_transport(routes: dict) -> httpx.MockTransport:
    """httpx MockTransport dispatching by URL path.

    ``routes`` maps a URL path (e.g. "/api/search") to a callable
    ``(httpx.Request) -> httpx.Response``.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        for path, responder in routes.items():
            if request.url.path == path:
                return responder(request)
        return httpx.Response(404, json={"error": f"no mock for {request.url.path}"})
    return httpx.MockTransport(handler)


def _server(routes: dict) -> FastMCP:
    """Build a FastMCP instance wired to mock HTTP routes."""

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[CodeAliveContext]:
        transport = _mock_transport(routes)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://test.codealive.ai"
        ) as client:
            yield CodeAliveContext(
                client=client,
                api_key="",
                base_url="https://test.codealive.ai",
            )

    mcp = FastMCP("E2E Test Server", lifespan=lifespan)
    mcp.tool()(get_data_sources)
    mcp.tool()(codebase_search)
    mcp.tool()(fetch_artifacts)
    mcp.tool()(codebase_consultant)
    mcp.tool()(get_artifact_relationships)
    return mcp


def _text(result) -> str:
    """Extract first text block from a CallToolResult."""
    return result.content[0].text


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _api_key_env(monkeypatch):
    """Provide CODEALIVE_API_KEY so get_api_key_from_context falls back to it."""
    monkeypatch.setenv("CODEALIVE_API_KEY", "test-e2e-key")


# ---------------------------------------------------------------------------
# get_data_sources
# ---------------------------------------------------------------------------

class TestGetDataSourcesE2E:
    @pytest.mark.asyncio
    async def test_returns_compact_json(self):
        payload = [
            {"id": "r1", "name": "backend", "type": "Repository", "url": "https://github.com/org/backend"},
            {"id": "w1", "name": "platform", "type": "Workspace", "repositoryIds": ["r1", "r2"]},
        ]

        def handler(req):
            assert req.headers["authorization"] == "Bearer test-e2e-key"
            return httpx.Response(200, json=payload)

        mcp = _server({"/api/datasources/ready": handler})
        async with Client(mcp) as client:
            result = await client.call_tool("get_data_sources", {})

        text = _text(result)
        # Compact JSON: no spaces after separators
        assert ", " not in text and ": " not in text
        data = json.loads(text)
        names = [ds["name"] for ds in data]
        assert "backend" in names
        assert "platform" in names
        # repositoryIds must be stripped from workspaces
        for ds in data:
            assert "repositoryIds" not in ds

    @pytest.mark.asyncio
    async def test_empty_list_returns_message(self):
        mcp = _server({"/api/datasources/ready": lambda r: httpx.Response(200, json=[])})
        async with Client(mcp) as client:
            result = await client.call_tool("get_data_sources", {})

        text = _text(result)
        data = json.loads(text)
        assert data["dataSources"] == []
        assert "No data sources found" in data["message"]

    @pytest.mark.asyncio
    async def test_alive_only_false_hits_all_endpoint(self):
        hit = []

        def handler_all(req):
            hit.append("all")
            return httpx.Response(200, json=[{"id": "1", "name": "r", "type": "Repository"}])

        mcp = _server({
            "/api/datasources/all": handler_all,
            "/api/datasources/ready": lambda r: httpx.Response(200, json=[]),
        })
        async with Client(mcp) as client:
            await client.call_tool("get_data_sources", {"alive_only": False})

        assert "all" in hit

    @pytest.mark.asyncio
    async def test_backend_500_returns_error(self):
        mcp = _server({
            "/api/datasources/ready": lambda r: httpx.Response(500, text="boom"),
        })
        async with Client(mcp) as client:
            result = await client.call_tool("get_data_sources", {}, raise_on_error=False)

        text = _text(result)
        data = json.loads(text)
        assert "error" in data
        assert "500" in data["error"] or "Server error" in data["error"]


# ---------------------------------------------------------------------------
# codebase_search
# ---------------------------------------------------------------------------

class TestCodebaseSearchE2E:
    _SEARCH_RESPONSE = {
        "results": [
            {
                "identifier": "org/repo::src/auth.py::AuthService",
                "kind": "Class",
                "description": "Handles authentication",
                "contentByteSize": 4200,
                "location": {
                    "path": "src/auth.py",
                    "range": {"start": {"line": 10}, "end": {"line": 85}},
                },
            }
        ]
    }

    @pytest.mark.asyncio
    async def test_success_returns_compact_json(self):
        def handler(req):
            assert req.url.params.get("Query") == "auth service"
            assert req.url.params.get("Mode") == "auto"
            assert "X-CodeAlive-Tool" in req.headers
            return httpx.Response(200, json=self._SEARCH_RESPONSE)

        mcp = _server({"/api/search": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_search",
                {"query": "auth service", "data_sources": ["backend"]},
            )

        text = _text(result)
        # Compact JSON: no spaces after separators
        assert ", " not in text and ": " not in text
        data = json.loads(text)
        assert data["results"][0]["path"] == "src/auth.py"
        assert "AuthService" in data["results"][0]["identifier"]

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_search", {"query": ""},
                raise_on_error=False,
            )

        text = _text(result)
        data = json.loads(text)
        assert "error" in data
        assert "empty" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_json(self):
        mcp = _server({
            "/api/search": lambda r: httpx.Response(200, json={"results": []}),
        })
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_search", {"query": "nonexistent"},
            )

        text = _text(result)
        assert text == '{"results":[]}'

    @pytest.mark.asyncio
    async def test_deep_mode_forwarded(self):
        received_mode = []

        def handler(req):
            received_mode.append(req.url.params.get("Mode"))
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "codebase_search", {"query": "x", "mode": "deep"},
            )

        assert received_mode == ["deep"]

    @pytest.mark.asyncio
    async def test_404_returns_not_found_error(self):
        mcp = _server({
            "/api/search": lambda r: httpx.Response(404, text="not found"),
        })
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_search", {"query": "x"},
                raise_on_error=False,
            )

        text = _text(result)
        data = json.loads(text)
        assert "error" in data
        assert "404" in data["error"] or "not found" in data["error"].lower()


# ---------------------------------------------------------------------------
# fetch_artifacts
# ---------------------------------------------------------------------------

class TestFetchArtifactsE2E:
    _ARTIFACTS_RESPONSE = {
        "artifacts": [
            {
                "identifier": "org/repo::src/auth.py::AuthService",
                "content": "class AuthService:\n    pass\n",
                "contentByteSize": 28,
                "startLine": 10,
            }
        ]
    }

    @pytest.mark.asyncio
    async def test_success_returns_xml_with_content(self):
        def handler(req):
            body = json.loads(req.content)
            assert body["identifiers"] == ["org/repo::src/auth.py::AuthService"]
            return httpx.Response(200, json=self._ARTIFACTS_RESPONSE)

        mcp = _server({"/api/search/artifacts": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_artifacts",
                {"identifiers": ["org/repo::src/auth.py::AuthService"]},
            )

        xml = _text(result)
        assert "<artifacts>" in xml
        assert "AuthService" in xml
        assert "class AuthService" in xml
        # Content body sits between newlines inside <content>
        assert "<content>\n" in xml
        assert "\n    </content>" in xml

    @pytest.mark.asyncio
    async def test_empty_identifiers_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_artifacts", {"identifiers": []},
                raise_on_error=False,
            )

        assert "required" in _text(result).lower() or "error" in _text(result).lower()

    @pytest.mark.asyncio
    async def test_over_20_identifiers_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_artifacts",
                {"identifiers": [f"id-{i}" for i in range(21)]},
                raise_on_error=False,
            )

        assert "20" in _text(result) or "Maximum" in _text(result)

    @pytest.mark.asyncio
    async def test_artifact_with_relationships(self):
        payload = {
            "artifacts": [
                {
                    "identifier": "org/repo::src/svc.py::run",
                    "content": "def run(): pass",
                    "contentByteSize": 15,
                    "startLine": 1,
                    "relationships": {
                        "outgoingCallsCount": 2,
                        "outgoingCalls": [
                            {"identifier": "org/repo::src/db.py::connect", "summary": "Opens DB"}
                        ],
                        "incomingCallsCount": 1,
                        "incomingCalls": [
                            {"identifier": "org/repo::src/main.py::main"}
                        ],
                    },
                }
            ]
        }
        mcp = _server({"/api/search/artifacts": lambda r: httpx.Response(200, json=payload)})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_artifacts", {"identifiers": ["org/repo::src/svc.py::run"]},
            )

        xml = _text(result)
        assert "<outgoing_calls" in xml
        assert "<incoming_calls" in xml
        assert "Opens DB" in xml
        assert "get_artifact_relationships" in xml  # hint about full relationships


# ---------------------------------------------------------------------------
# codebase_consultant (streaming SSE)
# ---------------------------------------------------------------------------

class TestCodebaseConsultantE2E:
    @staticmethod
    def _sse_body(chunks: list[str], conv_id: str = "conv-42", msg_id: str = "msg-1") -> str:
        """Build an SSE response body with metadata + content chunks + DONE."""
        lines = [
            "event: message",
            f'data: {{"event":"metadata","conversationId":"{conv_id}","messageId":"{msg_id}"}}',
            "",
        ]
        for chunk in chunks:
            payload = json.dumps({"choices": [{"delta": {"content": chunk}}]})
            lines.append(f"data: {payload}")
            lines.append("")
        lines.append("data: [DONE]")
        lines.append("")
        return "\n".join(lines)

    @pytest.mark.asyncio
    async def test_streaming_success(self):
        body = self._sse_body(["Hello ", "world!"])

        def handler(req):
            data = json.loads(req.content)
            assert data["stream"] is True
            assert data["messages"][0]["content"] == "How does auth work?"
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

        mcp = _server({"/api/chat/completions": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_consultant",
                {"question": "How does auth work?", "data_sources": ["backend"]},
            )

        text = _text(result)
        assert "Hello world!" in text
        # New conversation gets ID appended
        assert "conv-42" in text

    @pytest.mark.asyncio
    async def test_continuing_conversation(self):
        body = self._sse_body(["Follow-up answer"], conv_id="conv-existing")

        def handler(req):
            data = json.loads(req.content)
            assert data["conversationId"] == "conv-existing"
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

        mcp = _server({"/api/chat/completions": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_consultant",
                {"question": "And the error handling?", "conversation_id": "conv-existing"},
            )

        text = _text(result)
        assert "Follow-up answer" in text

    @pytest.mark.asyncio
    async def test_empty_question_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_consultant", {"question": ""},
                raise_on_error=False,
            )

        text = _text(result)
        assert "error" in text.lower() or "question" in text.lower()

    @pytest.mark.asyncio
    async def test_backend_error_handled(self):
        mcp = _server({
            "/api/chat/completions": lambda r: httpx.Response(401, text="unauthorized"),
        })
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_consultant",
                {"question": "hello"},
                raise_on_error=False,
            )

        text = _text(result)
        assert "401" in text or "auth" in text.lower()


# ---------------------------------------------------------------------------
# get_artifact_relationships
# ---------------------------------------------------------------------------

class TestGetArtifactRelationshipsE2E:
    _RELATIONSHIPS_RESPONSE = {
        "sourceIdentifier": "org/repo::src/svc.py::Service",
        "profile": "CallsOnly",
        "found": True,
        "relationships": [
            {
                "relationType": "OutgoingCalls",
                "totalCount": 3,
                "returnedCount": 3,
                "truncated": False,
                "items": [
                    {"identifier": "org/repo::src/db.py::query", "filePath": "src/db.py", "startLine": 42},
                    {"identifier": "org/repo::src/cache.py::get", "filePath": "src/cache.py", "startLine": 10,
                     "shortSummary": "Cache lookup"},
                ],
            },
            {
                "relationType": "IncomingCalls",
                "totalCount": 1,
                "returnedCount": 1,
                "truncated": False,
                "items": [
                    {"identifier": "org/repo::src/main.py::run", "filePath": "src/main.py", "startLine": 5},
                ],
            },
        ],
    }

    @pytest.mark.asyncio
    async def test_success_returns_compact_json(self):
        def handler(req):
            body = json.loads(req.content)
            assert body["identifier"] == "org/repo::src/svc.py::Service"
            assert body["profile"] == "CallsOnly"
            return httpx.Response(200, json=self._RELATIONSHIPS_RESPONSE)

        mcp = _server({"/api/search/artifact-relationships": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::src/svc.py::Service", "profile": "callsOnly"},
            )

        text = _text(result)
        assert ", " not in text and ": " not in text
        data = json.loads(text)
        assert data["found"] is True
        types = [g["type"] for g in data["relationships"]]
        assert "outgoing_calls" in types
        assert "incoming_calls" in types
        outgoing_items = data["relationships"][0]["items"]
        assert any(item.get("shortSummary") == "Cache lookup" for item in outgoing_items)
        assert any(item.get("filePath") == "src/db.py" for item in outgoing_items)

    @pytest.mark.asyncio
    async def test_not_found(self):
        response_data = {
            "sourceIdentifier": "org/repo::missing",
            "profile": "CallsOnly",
            "found": False,
        }
        mcp = _server({
            "/api/search/artifact-relationships": lambda r: httpx.Response(200, json=response_data),
        })
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::missing"},
            )

        data = json.loads(_text(result))
        assert data["found"] is False
        assert "relationships" not in data

    @pytest.mark.asyncio
    async def test_invalid_profile_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::x", "profile": "bogus"},
                raise_on_error=False,
            )

        text = _text(result)
        data = json.loads(text)
        assert "error" in data
        assert "Unsupported profile" in data["error"]

    @pytest.mark.asyncio
    async def test_empty_identifier_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": ""},
                raise_on_error=False,
            )

        data = json.loads(_text(result))
        assert "error" in data
        assert "required" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_inheritance_profile_maps_correctly(self):
        response_data = {
            "sourceIdentifier": "org/repo::cls",
            "profile": "InheritanceOnly",
            "found": True,
            "relationships": [
                {
                    "relationType": "Ancestors",
                    "totalCount": 1,
                    "returnedCount": 1,
                    "truncated": False,
                    "items": [{"identifier": "org/repo::Base", "filePath": "base.py", "startLine": 1}],
                }
            ],
        }

        def handler(req):
            body = json.loads(req.content)
            assert body["profile"] == "InheritanceOnly"
            return httpx.Response(200, json=response_data)

        mcp = _server({"/api/search/artifact-relationships": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::cls", "profile": "inheritanceOnly"},
            )

        data = json.loads(_text(result))
        assert data["profile"] == "inheritanceOnly"
        assert data["relationships"][0]["type"] == "ancestors"
