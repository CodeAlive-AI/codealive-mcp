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
    chat,
    codebase_consultant,
    codebase_search,
    fetch_artifacts,
    grep_search,
    get_artifact_relationships,
    get_data_sources,
    semantic_search,
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
    mcp.tool()(semantic_search)
    mcp.tool()(grep_search)
    mcp.tool()(fetch_artifacts)
    mcp.tool()(chat)
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
        assert result.is_error
        assert "500" in text or "Server error" in text


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
        data = json.loads(text)
        # Compact JSON: round-trips byte-for-byte through the compact serializer
        assert text == json.dumps(data, separators=(",", ":"))
        assert data["results"][0]["path"] == "src/auth.py"
        assert "AuthService" in data["results"][0]["identifier"]
        # Hint must always be present and instruct the agent to fetch real content
        assert "fetch_artifacts" in data["hint"]

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_search", {"query": ""},
                raise_on_error=False,
            )

        text = _text(result)
        assert result.is_error
        assert "empty" in text.lower() or "Query cannot be empty" in text

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
        data = json.loads(text)
        assert data["results"] == []
        assert "fetch_artifacts" in data["hint"]

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
        assert result.is_error
        assert "404" in text or "not found" in text.lower()


# ---------------------------------------------------------------------------
# semantic_search
# ---------------------------------------------------------------------------

class TestSemanticSearchE2E:
    @pytest.mark.asyncio
    async def test_success_hits_canonical_endpoint(self):
        def handler(req):
            assert req.url.params.get("Query") == "auth service"
            assert req.url.params.get("MaxResults") == "7"
            assert req.url.params.get_list("Names") == ["backend"]
            assert req.url.params.get_list("Paths") == ["src/auth.py"]
            assert req.url.params.get_list("Extensions") == [".py"]
            assert req.headers["X-CodeAlive-Tool"] == "semantic_search"
            return httpx.Response(
                200,
                json={
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
                },
            )

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "semantic_search",
                {
                    "query": "auth service",
                    "data_sources": ["backend"],
                    "paths": ["src/auth.py"],
                    "extensions": [".py"],
                    "max_results": 7,
                },
            )

        data = json.loads(_text(result))
        assert data["results"][0]["path"] == "src/auth.py"
        assert "fetch_artifacts" in data["hint"]

    @pytest.mark.asyncio
    async def test_max_results_forwarded(self):
        def handler(req):
            assert req.url.params.get("MaxResults") == "3"
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 3},
            )

    @pytest.mark.asyncio
    async def test_max_results_not_sent_when_omitted(self):
        def handler(req):
            assert "MaxResults" not in dict(req.url.params)
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"]},
            )

    @pytest.mark.asyncio
    async def test_max_results_boundary_0_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 0},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_results" in _text(result)

    @pytest.mark.asyncio
    async def test_max_results_boundary_501_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 501},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_results" in _text(result)

    @pytest.mark.asyncio
    async def test_max_results_boundary_500_accepted(self):
        def handler(req):
            assert req.url.params.get("MaxResults") == "500"
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 500},
            )

    @pytest.mark.asyncio
    async def test_max_results_boundary_1_accepted(self):
        def handler(req):
            assert req.url.params.get("MaxResults") == "1"
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 1},
            )

    @pytest.mark.asyncio
    async def test_extensions_forwarded(self):
        def handler(req):
            assert req.url.params.get_list("Extensions") == [".cs", ".py"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "extensions": [".cs", ".py"]},
            )

    @pytest.mark.asyncio
    async def test_paths_forwarded(self):
        def handler(req):
            assert req.url.params.get_list("Paths") == ["src/services", "src/domain"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "paths": ["src/services", "src/domain"]},
            )

    @pytest.mark.asyncio
    async def test_multiple_data_sources_forwarded(self):
        def handler(req):
            assert req.url.params.get_list("Names") == ["repo-a", "repo-b"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo-a", "repo-b"]},
            )

    @pytest.mark.asyncio
    async def test_all_filters_combined(self):
        def handler(req):
            assert req.url.params.get("Query") == "pattern"
            assert req.url.params.get("MaxResults") == "10"
            assert req.url.params.get_list("Names") == ["backend"]
            assert req.url.params.get_list("Paths") == ["src/domain"]
            assert req.url.params.get_list("Extensions") == [".cs"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {
                    "query": "pattern",
                    "data_sources": ["backend"],
                    "paths": ["src/domain"],
                    "extensions": [".cs"],
                    "max_results": 10,
                },
            )

    @pytest.mark.asyncio
    async def test_empty_data_sources_omits_names(self):
        def handler(req):
            assert "Names" not in dict(req.url.params)
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": []},
            )

    @pytest.mark.asyncio
    async def test_data_sources_as_string_normalized(self):
        def handler(req):
            assert req.url.params.get_list("Names") == ["my-repo"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": "my-repo"},
            )

    @pytest.mark.asyncio
    async def test_404_includes_recovery_hint(self):
        mcp = _server({
            "/api/search/semantic": lambda r: httpx.Response(404, text="not found"),
        })
        async with Client(mcp) as client:
            result = await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["bad-repo"]},
                raise_on_error=False,
            )
        text = _text(result)
        assert result.is_error
        assert "get_data_sources" in text


# ---------------------------------------------------------------------------
# grep_search
# ---------------------------------------------------------------------------

class TestGrepSearchE2E:
    @pytest.mark.asyncio
    async def test_success_hits_canonical_endpoint(self):
        def handler(req):
            assert req.url.params.get("Query") == "auth\\("
            assert req.url.params.get("Regex") == "true"
            assert req.headers["X-CodeAlive-Tool"] == "grep_search"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "identifier": "org/repo::src/auth.py",
                            "kind": "File",
                            "matchCount": 2,
                            "matches": [
                                {
                                    "lineNumber": 15,
                                    "startColumn": 5,
                                    "endColumn": 10,
                                    "lineText": "auth(token)",
                                }
                            ],
                            "location": {
                                "path": "src/auth.py",
                                "range": {"start": {"line": 15}, "end": {"line": 15}},
                            },
                        }
                    ]
                },
            )

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "grep_search",
                {"query": "auth\\(", "data_sources": ["backend"], "regex": True},
            )

        data = json.loads(_text(result))
        assert data["results"][0]["matchCount"] == 2
        assert data["results"][0]["matches"][0]["lineNumber"] == 15
        assert "fetch_artifacts" in data["hint"] or "Read()" in data["hint"]

    @pytest.mark.asyncio
    async def test_regex_false_forwarded(self):
        def handler(req):
            assert req.url.params.get("Regex") == "false"
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "literal string", "data_sources": ["repo"], "regex": False},
            )

    @pytest.mark.asyncio
    async def test_regex_default_is_false(self):
        def handler(req):
            assert req.url.params.get("Regex") == "false"
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "literal string", "data_sources": ["repo"]},
            )

    @pytest.mark.asyncio
    async def test_max_results_forwarded(self):
        def handler(req):
            assert req.url.params.get("MaxResults") == "10"
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 10},
            )

    @pytest.mark.asyncio
    async def test_max_results_boundary_0_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 0},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_results" in _text(result)

    @pytest.mark.asyncio
    async def test_max_results_boundary_501_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["repo"], "max_results": 501},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_results" in _text(result)

    @pytest.mark.asyncio
    async def test_extensions_forwarded(self):
        def handler(req):
            assert req.url.params.get_list("Extensions") == [".ts", ".vue"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["repo"], "extensions": [".ts", ".vue"]},
            )

    @pytest.mark.asyncio
    async def test_paths_forwarded(self):
        def handler(req):
            assert req.url.params.get_list("Paths") == ["src/controllers"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["repo"], "paths": ["src/controllers"]},
            )

    @pytest.mark.asyncio
    async def test_all_filters_combined(self):
        def handler(req):
            assert req.url.params.get("Query") == "Status\\.Alive"
            assert req.url.params.get("Regex") == "true"
            assert req.url.params.get("MaxResults") == "5"
            assert req.url.params.get_list("Names") == ["backend"]
            assert req.url.params.get_list("Paths") == ["src/services"]
            assert req.url.params.get_list("Extensions") == [".cs"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {
                    "query": "Status\\.Alive",
                    "data_sources": ["backend"],
                    "paths": ["src/services"],
                    "extensions": [".cs"],
                    "max_results": 5,
                    "regex": True,
                },
            )

    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "grep_search",
                {"query": "", "data_sources": ["repo"]},
                raise_on_error=False,
            )
        assert result.is_error
        assert "empty" in _text(result).lower() or "Query cannot be empty" in _text(result)

    @pytest.mark.asyncio
    async def test_data_sources_as_string_normalized(self):
        def handler(req):
            assert req.url.params.get_list("Names") == ["my-repo"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": "my-repo"},
            )

    @pytest.mark.asyncio
    async def test_404_includes_recovery_hint(self):
        mcp = _server({
            "/api/search/grep": lambda r: httpx.Response(404, text="not found"),
        })
        async with Client(mcp) as client:
            result = await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["bad-repo"]},
                raise_on_error=False,
            )
        assert result.is_error
        assert "get_data_sources" in _text(result)


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

    @pytest.mark.asyncio
    async def test_stringified_json_identifiers_coerced(self):
        """MCP clients may send identifiers as a JSON-encoded string."""
        def handler(req):
            body = json.loads(req.content)
            assert body["identifiers"] == ["org/repo::src/auth.py::AuthService"]
            return httpx.Response(200, json=self._ARTIFACTS_RESPONSE)

        mcp = _server({"/api/search/artifacts": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_artifacts",
                {"identifiers": '["org/repo::src/auth.py::AuthService"]'},
            )

        xml = _text(result)
        assert "<artifacts>" in xml
        assert "AuthService" in xml

    @pytest.mark.asyncio
    async def test_single_string_identifier_coerced(self):
        """A bare string identifier should be wrapped into a list."""
        def handler(req):
            body = json.loads(req.content)
            assert body["identifiers"] == ["org/repo::src/auth.py"]
            return httpx.Response(200, json=self._ARTIFACTS_RESPONSE)

        mcp = _server({"/api/search/artifacts": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "fetch_artifacts",
                {"identifiers": "org/repo::src/auth.py"},
            )

        xml = _text(result)
        assert "<artifacts>" in xml


# ---------------------------------------------------------------------------
# Stringified parameter coercion for search tools
# ---------------------------------------------------------------------------

class TestSearchStringifiedParamsE2E:
    """Verify that search tools accept stringified JSON arrays for list params."""

    @pytest.mark.asyncio
    async def test_semantic_search_stringified_extensions(self):
        def handler(req):
            assert req.url.params.get_list("Extensions") == [".cs", ".py"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "extensions": '[".cs", ".py"]'},
            )

    @pytest.mark.asyncio
    async def test_semantic_search_stringified_paths(self):
        def handler(req):
            assert req.url.params.get_list("Paths") == ["src/services", "src/domain"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/semantic": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "semantic_search",
                {"query": "test", "data_sources": ["repo"], "paths": '["src/services", "src/domain"]'},
            )

    @pytest.mark.asyncio
    async def test_grep_search_stringified_extensions(self):
        def handler(req):
            assert req.url.params.get_list("Extensions") == [".ts"]
            return httpx.Response(200, json={"results": []})

        mcp = _server({"/api/search/grep": handler})
        async with Client(mcp) as client:
            await client.call_tool(
                "grep_search",
                {"query": "test", "data_sources": ["repo"], "extensions": '[".ts"]'},
            )


# ---------------------------------------------------------------------------
# chat / codebase_consultant (streaming SSE)
# ---------------------------------------------------------------------------

class TestChatE2E:
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
                "chat",
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
                "chat",
                {"question": "And the error handling?", "conversation_id": "conv-existing"},
            )

        text = _text(result)
        assert "Follow-up answer" in text

    @pytest.mark.asyncio
    async def test_empty_question_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "chat", {"question": ""},
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
                "chat",
                {"question": "hello"},
                raise_on_error=False,
            )

        text = _text(result)
        assert "401" in text or "auth" in text.lower()

    @pytest.mark.asyncio
    async def test_legacy_alias_still_works(self):
        body = self._sse_body(["Legacy alias"])

        def handler(req):
            assert req.headers["X-CodeAlive-Tool"] == "codebase_consultant"
            return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

        mcp = _server({"/api/chat/completions": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "codebase_consultant",
                {"question": "How does auth work?", "data_sources": ["backend"]},
            )

        assert "Legacy alias" in _text(result)


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
        """Pydantic rejects invalid Literal values before the function body runs."""
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::x", "profile": "bogus"},
                raise_on_error=False,
            )

        text = _text(result)
        # Pydantic Literal validation fires before the function body, producing
        # a human-readable validation error (not our custom JSON).
        assert "callsOnly" in text
        assert "literal_error" in text or "Input should be" in text

    @pytest.mark.asyncio
    async def test_empty_identifier_returns_error(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": ""},
                raise_on_error=False,
            )

        assert result.is_error
        assert "required" in _text(result).lower()

    @pytest.mark.asyncio
    async def test_max_count_per_type_0_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::x", "max_count_per_type": 0},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_count_per_type" in _text(result)

    @pytest.mark.asyncio
    async def test_max_count_per_type_1001_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::x", "max_count_per_type": 1001},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_count_per_type" in _text(result)

    @pytest.mark.asyncio
    async def test_max_count_per_type_negative_rejected(self):
        mcp = _server({})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::x", "max_count_per_type": -1},
                raise_on_error=False,
            )
        assert result.is_error
        assert "max_count_per_type" in _text(result)

    @pytest.mark.asyncio
    async def test_max_count_per_type_forwarded(self):
        response_data = {
            "sourceIdentifier": "org/repo::src/svc.py::run",
            "profile": "CallsOnly",
            "found": True,
            "relationships": [],
        }

        def handler(req):
            body = json.loads(req.content)
            assert body["maxCountPerType"] == 3
            return httpx.Response(200, json=response_data)

        mcp = _server({"/api/search/artifact-relationships": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::src/svc.py::run", "max_count_per_type": 3},
            )

        data = json.loads(_text(result))
        assert data["found"] is True

    @pytest.mark.asyncio
    async def test_all_relevant_profile(self):
        response_data = {
            "sourceIdentifier": "org/repo::cls",
            "profile": "AllRelevant",
            "found": True,
            "relationships": [
                {"relationType": "OutgoingCalls", "totalCount": 0, "returnedCount": 0, "truncated": False, "items": []},
                {"relationType": "IncomingCalls", "totalCount": 0, "returnedCount": 0, "truncated": False, "items": []},
                {"relationType": "Ancestors", "totalCount": 1, "returnedCount": 1, "truncated": False, "items": [{"identifier": "org/repo::Base"}]},
                {"relationType": "Descendants", "totalCount": 0, "returnedCount": 0, "truncated": False, "items": []},
            ],
        }

        def handler(req):
            body = json.loads(req.content)
            assert body["profile"] == "AllRelevant"
            return httpx.Response(200, json=response_data)

        mcp = _server({"/api/search/artifact-relationships": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::cls", "profile": "allRelevant"},
            )

        data = json.loads(_text(result))
        assert data["profile"] == "allRelevant"
        types = [g["type"] for g in data["relationships"]]
        assert "outgoing_calls" in types
        assert "incoming_calls" in types
        assert "ancestors" in types
        assert "descendants" in types

    @pytest.mark.asyncio
    async def test_references_profile(self):
        response_data = {
            "sourceIdentifier": "org/repo::var",
            "profile": "ReferencesOnly",
            "found": True,
            "relationships": [
                {"relationType": "References", "totalCount": 5, "returnedCount": 5, "truncated": False, "items": [
                    {"identifier": "org/repo::src/a.py::func_a", "filePath": "src/a.py", "startLine": 10}
                ]},
            ],
        }

        def handler(req):
            body = json.loads(req.content)
            assert body["profile"] == "ReferencesOnly"
            return httpx.Response(200, json=response_data)

        mcp = _server({"/api/search/artifact-relationships": handler})
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_artifact_relationships",
                {"identifier": "org/repo::var", "profile": "referencesOnly"},
            )

        data = json.loads(_text(result))
        assert data["profile"] == "referencesOnly"
        assert data["relationships"][0]["type"] == "references"
        assert data["relationships"][0]["totalCount"] == 5

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
