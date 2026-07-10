"""In-memory MCP protocol tests for the complete public tool surface."""

import sys
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).parent.parent))

from codealive_mcp_server import mcp


@pytest.fixture(autouse=True)
def _stdio_environment(monkeypatch):
    monkeypatch.setenv("TRANSPORT_MODE", "stdio")
    monkeypatch.setenv("CODEALIVE_API_KEY", "test-key")
    monkeypatch.setenv("CODEALIVE_BASE_URL", "https://app.codealive.ai")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("get_data_sources", {}),
        ("semantic_search", {"question": "How does startup work?"}),
        ("grep_search", {"query": "FastMCP"}),
        ("get_repository_ontology", {"data_source": "backend"}),
        ("get_file_tree", {"data_source": "backend"}),
        ("read_file", {"path": "README.md", "data_source": "backend"}),
        ("fetch_artifacts", {"identifiers": ["backend::README.md"]}),
        (
            "get_artifact_relationships",
            {"identifier": "backend::src/Foo.cs::Foo"},
        ),
        ("get_artifact_query_schema", {}),
        ("query_artifact_metadata", {"statement": "SELECT path FROM files LIMIT 1"}),
        ("chat", {"question": "Summarize startup."}),
    ],
)
async def test_each_public_tool_completes_through_mcp_protocol(
    monkeypatch,
    tool_name,
    arguments,
):
    async def post(_client, path, **_kwargs):
        return httpx.Response(
            200,
            json={"rendered": f"<result tool=\"{tool_name}\">ok</result>"},
            request=httpx.Request("POST", f"https://app.codealive.ai{path}"),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)

    async with Client(mcp) as client:
        result = await client.call_tool(tool_name, arguments)

    assert result.is_error is False
    assert result.content[0].text == f"<result tool=\"{tool_name}\">ok</result>"


@pytest.mark.asyncio
async def test_repairable_backend_error_sets_protocol_is_error(monkeypatch):
    async def post(_client, path, **_kwargs):
        return httpx.Response(
            200,
            json={
                "obj": {
                    "error": {
                        "code": "invalid_tool_arguments",
                        "message": "question is required",
                        "retry": "yes - repair the tool arguments and call the tool again",
                        "try": "Provide question and retry.",
                    }
                },
                "rendered": "<tool_error><code>invalid_tool_arguments</code></tool_error>",
            },
            request=httpx.Request("POST", f"https://app.codealive.ai{path}"),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "semantic_search",
            {"question": "valid locally"},
            raise_on_error=False,
        )

    assert result.is_error is True
    assert result.content[0].text.startswith("<tool_error>")
    assert result.structured_content["error"]["code"] == "invalid_tool_arguments"
