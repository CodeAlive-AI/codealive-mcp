"""Test suite for search tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context
from tools.search import search_code


@pytest.mark.asyncio
@patch('tools.search.get_api_key_from_context')
async def test_search_code_returns_dict(mock_get_api_key):
    """Test that search_code returns a dictionary with structured_content."""
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

    # Call search_code
    result = await search_code(
        ctx=ctx,
        query="authenticate_user",
        data_source_ids=["test_id"],
        mode="auto",
        include_content=False
    )

    # Verify result is a dictionary
    assert isinstance(result, dict), "search_code should return a dictionary"

    # Verify it has structured_content field
    assert "structured_content" in result, "Result should have structured_content field"

    # Verify the structured_content is a string (XML)
    assert isinstance(result["structured_content"], str), "structured_content should be a string"

    # Verify it contains expected XML structure
    assert "<results>" in result["structured_content"], "Should contain results tag"
    assert "<search_result" in result["structured_content"], "Should contain search_result tag"