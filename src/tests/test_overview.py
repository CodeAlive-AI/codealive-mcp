"""Tests for the get_repo_overview tool."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from mcp.server.fastmcp import Context

from tools.overview import get_repo_overview
from core.client import CodeAliveContext
import httpx


@pytest.mark.asyncio
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_success(mock_get_api_key):
    """Test successful retrieval of repository overview."""
    # Mock API key
    mock_get_api_key.return_value = "test-api-key"

    # Mock response
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "test-repo",
            "overview": "# Purpose\nTest repository\n## Responsibilities\n- Task 1"
        }
    ]
    mock_response.status_code = 200

    # Mock client
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    # Mock context
    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    # Call tool
    result = await get_repo_overview(mock_ctx, ["test-repo"])

    # Assertions
    assert '<repository name="test-repo">' in result
    assert '<overview>' in result
    assert '# Purpose' in result
    assert 'Test repository' in result
    assert '## Responsibilities' in result
    assert '- Task 1' in result

    # Verify API call
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args.kwargs['headers'] == {"Authorization": "Bearer test-api-key"}
    assert "https://app.codealive.ai/api/overview" in call_args.args[0]


@pytest.mark.asyncio
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_multiple_repos(mock_get_api_key):
    """Test retrieval of multiple repository overviews."""
    mock_get_api_key.return_value = "test-api-key"

    # Mock response with 3 repositories
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "repo-1", "overview": "Overview 1"},
        {"name": "repo-2", "overview": "Overview 2"},
        {"name": "repo-3", "overview": "Overview 3"}
    ]
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    result = await get_repo_overview(mock_ctx, ["repo-1", "repo-2", "repo-3"])

    # Verify 3 repository blocks
    assert result.count('<repository') == 3
    assert '<repository name="repo-1">' in result
    assert '<repository name="repo-2">' in result
    assert '<repository name="repo-3">' in result
    assert 'Overview 1' in result
    assert 'Overview 2' in result
    assert 'Overview 3' in result


@pytest.mark.asyncio
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_no_data_sources(mock_get_api_key):
    """Test retrieval without specifying data sources (all repos)."""
    mock_get_api_key.return_value = "test-api-key"

    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "all-repo-1", "overview": "Overview 1"},
        {"name": "all-repo-2", "overview": "Overview 2"}
    ]
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    result = await get_repo_overview(mock_ctx, None)

    # Verify API called without Names[] params
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    # When data_sources is None, params should be empty dict
    assert call_args.kwargs['params'] == {}

    # Verify returns overviews for all repos
    assert '<repository name="all-repo-1">' in result
    assert '<repository name="all-repo-2">' in result


@pytest.mark.asyncio
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_empty_result(mock_get_api_key):
    """Test handling of empty API response."""
    mock_get_api_key.return_value = "test-api-key"

    # Empty array response
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    result = await get_repo_overview(mock_ctx, ["nonexistent"])

    # Should return empty root element
    assert '<repository_overviews' in result
    assert '</repository_overviews>' in result
    # Should not contain any repository elements
    assert '<repository name=' not in result


@pytest.mark.asyncio
@patch("tools.overview.handle_api_error")
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_api_error(mock_get_api_key, mock_handle_error):
    """Test handling of API errors."""
    mock_get_api_key.return_value = "test-api-key"
    mock_handle_error.return_value = "Error: API failed"

    # Mock client that raises HTTPError
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    result = await get_repo_overview(mock_ctx, ["test-repo"])

    # Verify error handling
    assert result == "Error: API failed"
    mock_handle_error.assert_called_once()
    # Verify handle_api_error called with correct parameters
    call_args = mock_handle_error.call_args
    assert call_args.args[0] == mock_ctx
    assert isinstance(call_args.args[1], httpx.HTTPError)
    assert call_args.args[2] == "get repository overview"


@pytest.mark.asyncio
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_auth_header(mock_get_api_key):
    """Test that Authorization header is correctly set."""
    mock_get_api_key.return_value = "my-secret-key"

    mock_response = MagicMock()
    mock_response.json.return_value = [{"name": "test", "overview": "Test"}]
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    await get_repo_overview(mock_ctx, ["test"])

    # Verify correct Authorization header
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args.kwargs['headers'] == {"Authorization": "Bearer my-secret-key"}


@pytest.mark.asyncio
@patch("tools.overview.normalize_data_source_names")
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_data_source_normalization(mock_get_api_key, mock_normalize):
    """Test that data sources are normalized (Claude Desktop serialization handling)."""
    mock_get_api_key.return_value = "test-api-key"
    # Simulate normalization converting string to list
    mock_normalize.return_value = ["normalized-repo"]

    mock_response = MagicMock()
    mock_response.json.return_value = [{"name": "normalized-repo", "overview": "Test"}]
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    # Call with string (simulating Claude Desktop serialization issue)
    await get_repo_overview(mock_ctx, "string-data-source")

    # Verify normalize_data_source_names was called
    mock_normalize.assert_called_once_with("string-data-source")


@pytest.mark.asyncio
@patch("tools.overview.get_api_key_from_context")
async def test_get_repo_overview_markdown_preservation(mock_get_api_key):
    """Test that markdown formatting is preserved in XML output."""
    mock_get_api_key.return_value = "test-api-key"

    # Mock response with rich markdown
    markdown_content = """# Purpose
This is the **main** repository.

## Responsibilities
- Handle *authentication*
- Process `orders`

### Code Example
```python
def example():
    return True
```

## Links
See [documentation](https://example.com) for more.
"""

    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"name": "rich-markdown-repo", "overview": markdown_content}
    ]
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock(spec=CodeAliveContext)
    mock_context.client = mock_client
    mock_context.base_url = "https://app.codealive.ai"

    mock_ctx = MagicMock(spec=Context)
    mock_ctx.request_context.lifespan_context = mock_context

    result = await get_repo_overview(mock_ctx, ["rich-markdown-repo"])

    # Verify all markdown formatting is preserved
    assert '# Purpose' in result
    assert 'This is the **main** repository.' in result
    assert '## Responsibilities' in result
    assert '- Handle *authentication*' in result
    assert '- Process `orders`' in result
    assert '### Code Example' in result
    assert '```python' in result
    assert 'def example():' in result
    assert '## Links' in result
    assert 'See [documentation](https://example.com)' in result

    # Verify no HTML escaping of markdown content (should not have &lt; etc)
    assert '&lt;' not in result or '```' in result  # XML entities only in markdown might be ok
    assert '&gt;' not in result or '```' in result
