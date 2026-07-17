"""MCP Tool API v3 contract tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult

from core.config import Config
from tools.artifact_query import get_artifact_query_schema, query_artifact_metadata
from tools.artifact_relationships import get_artifact_relationships
from tools.chat import chat
from tools.datasources import get_data_sources
from tools.fetch_artifacts import fetch_artifacts
from tools.repository import get_file_tree, get_repository_ontology, read_file
from tools.search import grep_search, semantic_search
from tools.tool_api import call_tool_api

LEGACY_API_KEY = "ca_1720000000000_0123456789abcdef0123456789abcdef0123456789a"


def _context_with_response(
    rendered: str = "<result>ok</result>",
    obj: dict | None = None,
):
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.json.return_value = {
        "rendered": rendered,
        "obj": obj if obj is not None else {"ok": True},
    }
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
                profile="all_relevant",
                max_count_per_type=25,
                data_source="backend",
            ),
            "/api/tools/get_artifact_relationships",
            {
                "identifier": "repo::src/Foo.cs::Foo",
                "profile": "all_relevant",
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
    mock_get_api_key.return_value = LEGACY_API_KEY
    ctx, client = _context_with_response("<agentic>done</agentic>")

    result = await tool_call(ctx)

    assert result == "<agentic>done</agentic>"
    call_args = client.post.call_args
    assert call_args.args[0] == expected_path
    assert call_args.kwargs["json"] == {**expected_payload, "output_format": "agentic"}
    assert call_args.kwargs["headers"]["Authorization"] == f"Bearer {LEGACY_API_KEY}"
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


@pytest.mark.asyncio
@patch("tools.tool_api.get_api_key_from_context")
async def test_repairable_backend_error_sets_native_mcp_error(mock_get_api_key):
    mock_get_api_key.return_value = LEGACY_API_KEY
    error = {
        "code": "invalid_tool_arguments",
        "message": "question is required",
        "retry": "yes - repair the tool arguments and call the tool again",
        "try": "Provide question and retry.",
    }
    ctx, _ = _context_with_response(
        rendered="<tool_error><code>invalid_tool_arguments</code></tool_error>",
        obj={"error": error},
    )

    result = await semantic_search(ctx, question="missing upstream validation")

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    assert len(result.content) == 1
    assert result.content[0].text == "<tool_error><code>invalid_tool_arguments</code></tool_error>"
    assert result.structured_content == {"error": error}


@pytest.mark.asyncio
@patch("tools.tool_api.invalidate_tool_token_exchange", new_callable=AsyncMock)
@patch("tools.tool_api.exchange_for_tool_token", new_callable=AsyncMock)
@patch("tools.tool_api.get_api_key_from_context")
async def test_oauth_tool_call_evicts_rejected_exchange_and_retries_once(
    mock_get_api_key,
    mock_exchange,
    mock_invalidate,
):
    mock_get_api_key.return_value = "header.payload.signature"
    mock_exchange.side_effect = ["stale-tool-token", "fresh-tool-token"]
    ctx, client = _context_with_response("done")
    context = ctx.request_context.lifespan_context
    context.config = MagicMock()
    context.tool_token_cache = MagicMock()

    unauthorized = MagicMock(status_code=401)
    success = MagicMock(status_code=200)
    success.json.return_value = {"rendered": "done", "obj": {"ok": True}}
    success.raise_for_status = MagicMock()
    client.post.side_effect = [unauthorized, success]

    result = await call_tool_api(ctx, "semantic_search", {"question": "why"})

    assert result == "done"
    assert client.post.call_count == 2
    assert client.post.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer stale-tool-token"
    assert client.post.call_args_list[1].kwargs["headers"]["Authorization"] == "Bearer fresh-tool-token"
    mock_invalidate.assert_awaited_once_with(
        context.tool_token_cache,
        context.config,
        "header.payload.signature",
    )


@pytest.mark.asyncio
@patch("tools.tool_api.exchange_for_tool_token", new_callable=AsyncMock)
@patch("tools.tool_api.get_api_key_from_context")
async def test_oauth_shaped_credential_is_not_exchanged_when_feature_is_disabled(
    mock_get_api_key,
    mock_exchange,
):
    credential = "header.payload.signature"
    mock_get_api_key.return_value = credential
    ctx, client = _context_with_response("done")
    context = ctx.request_context.lifespan_context
    context.config = Config(oauth_enabled=False)

    result = await call_tool_api(ctx, "semantic_search", {"question": "why"})

    assert result == "done"
    assert client.post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {credential}"
    mock_exchange.assert_not_awaited()
