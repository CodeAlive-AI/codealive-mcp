"""MCP Tool API v3 contract tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Context
from fastmcp.exceptions import ToolError

from tools.artifact_query import get_artifact_query_schema, query_artifact_metadata
from tools.artifact_relationships import get_artifact_relationships
from tools.chat import chat
from tools.datasources import get_data_sources
from tools.fetch_artifacts import fetch_artifacts
from tools.repository import get_file_tree, get_repository_ontology, read_file
from tools.search import grep_search, semantic_search


def _context_with_response(rendered: str = "<result>ok</result>"):
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.json.return_value = {"rendered": rendered, "obj": {"ok": True}}
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post.return_value = response

    codealive_context = MagicMock()
    codealive_context.client = client
    codealive_context.base_url = "https://app.codealive.ai/api/"

    ctx.request_context.lifespan_context = codealive_context
    return ctx, client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_call", "expected_path", "expected_payload"),
    [
        (
            lambda ctx: get_data_sources(ctx, query="checkout", ready_only=False),
            "/api/tools/get_data_sources",
            {"query": "checkout", "ready_only": False},
        ),
        (
            lambda ctx: semantic_search(
                ctx,
                question="How does checkout authorization work?",
                data_sources=["backend"],
                paths=["src"],
                extensions=".cs",
                max_results=7,
                exclude_markdown=True,
            ),
            "/api/tools/semantic_search",
            {
                "question": "How does checkout authorization work?",
                "data_sources": ["backend"],
                "paths": ["src"],
                "extensions": [".cs"],
                "max_results": 7,
                "exclude_markdown": True,
            },
        ),
        (
            lambda ctx: grep_search(ctx, query="Authorize", data_sources="backend", regex=True),
            "/api/tools/grep_search",
            {
                "query": "Authorize",
                "data_sources": ["backend"],
                "exclude_markdown": False,
                "regex": True,
            },
        ),
        (
            lambda ctx: get_repository_ontology(ctx, data_source="backend"),
            "/api/tools/get_repository_ontology",
            {"data_source": "backend"},
        ),
        (
            lambda ctx: get_file_tree(ctx, data_source="backend", path="src", max_depth=2),
            "/api/tools/get_file_tree",
            {"data_source": "backend", "path": "src", "max_depth": 2},
        ),
        (
            lambda ctx: read_file(ctx, path="README.md", data_source="backend", start_line=1, end_line=20),
            "/api/tools/read_file",
            {"data_source": "backend", "path": "README.md", "start_line": 1, "end_line": 20},
        ),
        (
            lambda ctx: fetch_artifacts(ctx, identifiers=["repo::src/Foo.cs::Foo"], data_source="backend"),
            "/api/tools/fetch_artifacts",
            {"identifiers": ["repo::src/Foo.cs::Foo"], "data_source": "backend"},
        ),
        (
            lambda ctx: get_artifact_relationships(
                ctx,
                identifier="repo::src/Foo.cs::Foo",
                profile="AllRelevant",
                max_count_per_type=25,
                data_source="backend",
            ),
            "/api/tools/get_artifact_relationships",
            {
                "identifier": "repo::src/Foo.cs::Foo",
                "profile": "AllRelevant",
                "max_count_per_type": 25,
                "data_source": "backend",
            },
        ),
        (
            lambda ctx: get_artifact_query_schema(ctx, entity="files", include_examples=False),
            "/api/tools/get_artifact_query_schema",
            {"entity": "files", "include_examples": False},
        ),
        (
            lambda ctx: query_artifact_metadata(ctx, statement="SELECT path FROM files LIMIT 5", data_sources=["backend"]),
            "/api/tools/query_artifact_metadata",
            {"statement": "SELECT path FROM files LIMIT 5", "data_sources": ["backend"]},
        ),
        (
            lambda ctx: chat(ctx, question="Summarize repository startup flow.", data_sources=["backend"]),
            "/api/tools/chat",
            {"question": "Summarize repository startup flow.", "data_sources": ["backend"]},
        ),
    ],
)
@patch("tools.tool_api.get_api_key_from_context")
async def test_mcp_tools_post_canonical_v3_payloads(mock_get_api_key, tool_call, expected_path, expected_payload):
    mock_get_api_key.return_value = "test_key"
    ctx, client = _context_with_response("<agentic>done</agentic>")

    result = await tool_call(ctx)

    assert result == "<agentic>done</agentic>"
    call_args = client.post.call_args
    assert call_args.args[0] == expected_path
    assert call_args.kwargs["json"] == {**expected_payload, "output_format": "agentic"}
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer test_key"
    assert call_args.kwargs["headers"]["X-CodeAlive-Integration"] == "mcp"
    assert call_args.kwargs["headers"]["X-CodeAlive-Tool"] == expected_path.rsplit("/", 1)[1]
    assert call_args.kwargs["headers"]["X-CodeAlive-Client"] == "fastmcp-v3"


@pytest.mark.asyncio
async def test_required_arguments_fail_before_network_call():
    ctx, client = _context_with_response()

    with pytest.raises(ToolError, match="question is required"):
        await semantic_search(ctx, question="")

    with pytest.raises(ToolError, match="path is required"):
        await read_file(ctx, path="")

    with pytest.raises(ToolError, match="identifiers is required"):
        await fetch_artifacts(ctx, identifiers=[])

    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_local_bounds_validation_fail_before_network_call():
    ctx, client = _context_with_response()

    with pytest.raises(ToolError, match="max_results"):
        await grep_search(ctx, query="Foo", max_results=501)

    with pytest.raises(ToolError, match="max_count_per_type"):
        await get_artifact_relationships(ctx, identifier="repo::Foo", max_count_per_type=0)

    client.post.assert_not_called()
