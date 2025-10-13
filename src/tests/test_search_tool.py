"""Test suite for search tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context
from tools.search import codebase_search


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_codebase_search_returns_xml_string(mock_get_api_key):
    """Test that codebase_search returns an XML string directly."""
    # Mock the API key function
    mock_get_api_key.return_value = "test_key"

    # Create mock context
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    # Create mock response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "kind": "Symbol",
                "identifier": "owner/repo::path/auth.py::authenticate_user",
                "location": {
                    "path": "path/auth.py",
                    "range": {"start": {"line": 10}, "end": {"line": 25}}
                }
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    # Create mock client
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Create mock context with proper structure
    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    # Call codebase_search
    result = await codebase_search(
        ctx=ctx,
        query="authenticate_user",
        data_source_ids=["test_id"],
        mode="auto",
        include_content=False
    )

    # Verify result is a string (XML)
    assert isinstance(result, str), "codebase_search should return an XML string"

    # Verify it contains expected XML structure
    assert "<results>" in result, "Should contain results tag"
    assert "<search_result" in result, "Should contain search_result tag"


@pytest.mark.asyncio
async def test_codebase_search_empty_query_returns_error_string():
    """Test that empty query returns an error string (not dict)."""
    # Create mock context
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    # Create mock context with proper structure
    mock_codealive_context = MagicMock()
    mock_codealive_context.base_url = "https://app.codealive.ai"
    ctx.request_context.lifespan_context = mock_codealive_context

    # Call with empty query
    result = await codebase_search(
        ctx=ctx,
        query="",
        data_source_ids=["test_id"],
        mode="auto",
        include_content=False
    )

    # Verify result is a string (not a dict)
    assert isinstance(result, str), "Error should be returned as a string"
    assert "<error>" in result, "Error string should contain <error> tag"
    assert "Query cannot be empty" in result, "Should contain error message"


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_codebase_search_api_error_returns_error_string(mock_get_api_key):
    """Test that API errors return an error string (not dict)."""
    import httpx

    # Mock the API key function
    mock_get_api_key.return_value = "test_key"

    # Create mock context
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    # Create mock response that raises 404
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

    # Create mock client that returns the error response
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    # Create mock context with proper structure
    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    # Call codebase_search
    result = await codebase_search(
        ctx=ctx,
        query="test query",
        data_source_ids=["invalid_id"],
        mode="auto",
        include_content=False
    )

    # Verify result is a string (not a dict)
    assert isinstance(result, str), "Error should be returned as a string"
    assert "<error>" in result, "Error string should contain <error> tag"
    assert "404" in result, "Should contain error details"