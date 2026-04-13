"""Test suite for semantic, grep, and legacy search tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Context
from fastmcp.exceptions import ToolError

from tools.search import codebase_search, grep_search, semantic_search


def _build_context(mock_response):
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}
    return ctx, mock_client


@pytest.mark.asyncio
@patch("tools.search.get_api_key_from_context")
async def test_semantic_search_returns_compact_json(mock_get_api_key):
    mock_get_api_key.return_value = "test_key"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "kind": "Symbol",
                "identifier": "owner/repo::path/auth.py::authenticate_user",
                "location": {
                    "path": "path/auth.py",
                    "range": {"start": {"line": 10}, "end": {"line": 25}},
                },
                "description": "Authenticates a user with credentials",
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    ctx, mock_client = _build_context(mock_response)

    result = await semantic_search(
        ctx=ctx,
        query="authenticate_user",
        data_sources=["test-name"],
        paths=["src/auth.py"],
        extensions=[".py"],
        max_results=7,
    )

    data = json.loads(result)
    assert data["results"][0]["path"] == "path/auth.py"
    assert data["results"][0]["identifier"] == "owner/repo::path/auth.py::authenticate_user"

    call_args = mock_client.get.call_args
    assert call_args.args[0] == "/api/search/semantic"
    params = call_args.kwargs["params"]
    assert ("Query", "authenticate_user") in params
    assert ("Names", "test-name") in params
    assert ("Paths", "src/auth.py") in params
    assert ("Extensions", ".py") in params
    assert ("MaxResults", "7") in params
    assert call_args.kwargs["headers"]["X-CodeAlive-Tool"] == "semantic_search"


@pytest.mark.asyncio
@patch("tools.search.get_api_key_from_context")
async def test_grep_search_returns_matches(mock_get_api_key):
    mock_get_api_key.return_value = "test_key"

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "kind": "File",
                "identifier": "owner/repo::path/auth.py",
                "location": {
                    "path": "path/auth.py",
                    "range": {"start": {"line": 15}},
                },
                "matchCount": 2,
                "matches": [
                    {
                        "lineNumber": 15,
                        "startColumn": 5,
                        "endColumn": 12,
                        "lineText": "token = auth()",
                    }
                ],
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    ctx, mock_client = _build_context(mock_response)

    result = await grep_search(
        ctx=ctx,
        query="auth\\(",
        data_sources=["test-name"],
        regex=True,
    )

    data = json.loads(result)
    assert data["results"][0]["matchCount"] == 2
    assert data["results"][0]["matches"][0]["lineNumber"] == 15

    call_args = mock_client.get.call_args
    assert call_args.args[0] == "/api/search/grep"
    params = call_args.kwargs["params"]
    assert ("Regex", "true") in params
    assert call_args.kwargs["headers"]["X-CodeAlive-Tool"] == "grep_search"


@pytest.mark.asyncio
@patch("tools.search.get_api_key_from_context")
async def test_codebase_search_keeps_legacy_params(mock_get_api_key):
    mock_get_api_key.return_value = "test_key"

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()

    ctx, mock_client = _build_context(mock_response)

    await codebase_search(
        ctx=ctx,
        query="test",
        data_sources=["test-name"],
        mode="deep",
        description_detail="full",
    )

    call_args = mock_client.get.call_args
    assert call_args.args[0] == "/api/search"
    params = call_args.kwargs["params"]
    assert ("Mode", "deep") in params
    assert ("DescriptionDetail", "Full") in params
    assert ("IncludeContent", "false") in params
    assert call_args.kwargs["headers"]["X-CodeAlive-Tool"] == "codebase_search"


@pytest.mark.asyncio
async def test_semantic_search_empty_query_raises_tool_error():
    ctx = MagicMock(spec=Context)

    with pytest.raises(ToolError, match="Query cannot be empty"):
        await semantic_search(ctx=ctx, query="")


@pytest.mark.asyncio
async def test_grep_search_invalid_max_results_raises_tool_error():
    ctx = MagicMock(spec=Context)

    with pytest.raises(ToolError, match="max_results"):
        await grep_search(ctx=ctx, query="foo", max_results=501)


@pytest.mark.asyncio
@patch("tools.search.get_api_key_from_context")
async def test_codebase_search_api_error_raises_tool_error(mock_get_api_key):
    import httpx

    mock_get_api_key.return_value = "test_key"

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    def raise_404():
        raise httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=mock_response,
        )

    mock_response.raise_for_status = raise_404
    ctx, mock_client = _build_context(mock_response)
    mock_client.get.return_value = mock_response

    with pytest.raises(ToolError, match="404"):
        await codebase_search(
            ctx=ctx,
            query="test query",
            data_sources=["invalid-name"],
        )
