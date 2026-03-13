"""Test suite for search tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context
from tools.search import codebase_search


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_codebase_search_returns_xml_string(mock_get_api_key):
    """Test that codebase_search returns an XML string directly."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "kind": "Symbol",
                "identifier": "owner/repo::path/auth.py::authenticate_user",
                "location": {
                    "path": "path/auth.py",
                    "range": {"start": {"line": 10}, "end": {"line": 25}}
                },
                "description": "Authenticates a user with credentials"
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await codebase_search(
        ctx=ctx,
        query="authenticate_user",
        data_sources=["test-name"],
        mode="auto"
    )

    assert isinstance(result, str)
    assert "<results>" in result
    assert "<search_result" in result

    call_args = mock_client.get.call_args
    params = call_args.kwargs["params"]
    assert ("Names", "test-name") in params


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_codebase_search_always_sends_include_content_false(mock_get_api_key):
    """Test that IncludeContent is always 'false' regardless of input."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    await codebase_search(
        ctx=ctx,
        query="test",
        data_sources=["test-name"],
    )

    call_args = mock_client.get.call_args
    params = call_args.kwargs["params"]
    assert ("IncludeContent", "false") in params


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_codebase_search_description_detail_mapping(mock_get_api_key):
    """Test that description_detail maps correctly to DescriptionDetail API param."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    # Test "short" mapping
    await codebase_search(
        ctx=ctx,
        query="test",
        data_sources=["test-name"],
        description_detail="short",
    )
    params = mock_client.get.call_args.kwargs["params"]
    assert ("DescriptionDetail", "Short") in params

    # Test "full" mapping
    await codebase_search(
        ctx=ctx,
        query="test",
        data_sources=["test-name"],
        description_detail="full",
    )
    params = mock_client.get.call_args.kwargs["params"]
    assert ("DescriptionDetail", "Full") in params

    # Test default (invalid value falls back to "Short")
    await codebase_search(
        ctx=ctx,
        query="test",
        data_sources=["test-name"],
        description_detail="invalid",
    )
    params = mock_client.get.call_args.kwargs["params"]
    assert ("DescriptionDetail", "Short") in params


@pytest.mark.asyncio
async def test_codebase_search_empty_query_returns_error_string():
    """Test that empty query returns an error string (not dict)."""
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_codealive_context = MagicMock()
    mock_codealive_context.base_url = "https://app.codealive.ai"
    ctx.request_context.lifespan_context = mock_codealive_context

    result = await codebase_search(
        ctx=ctx,
        query="",
        data_sources=["test-name"],
        mode="auto"
    )

    assert isinstance(result, str)
    assert "<error>" in result
    assert "Query cannot be empty" in result


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_codebase_search_api_error_returns_error_string(mock_get_api_key):
    """Test that API errors return an error string (not dict)."""
    import httpx

    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    def raise_404():
        raise httpx.HTTPStatusError(
            "Not found",
            request=MagicMock(),
            response=mock_response
        )

    mock_response.raise_for_status = raise_404

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await codebase_search(
        ctx=ctx,
        query="test query",
        data_sources=["invalid-name"],
        mode="auto"
    )

    assert isinstance(result, str)
    assert "<error>" in result
    assert "404" in result
