"""Test suite for error handling utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx
from utils.errors import handle_api_error, format_data_source_names


@pytest.mark.asyncio
async def test_handle_401_error():
    """Test handling of 401 authentication errors."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    # Create mock 401 response
    response = MagicMock()
    response.status_code = 401
    response.text = "Invalid token"

    error = httpx.HTTPStatusError("", request=None, response=response)
    result = await handle_api_error(ctx, error, "test operation")

    assert "Authentication error (401)" in result
    assert "Invalid API key" in result
    ctx.error.assert_called_once()


@pytest.mark.asyncio
async def test_handle_404_error():
    """Test handling of 404 not found errors."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.status_code = 404
    response.text = "Resource not found"

    error = httpx.HTTPStatusError("", request=None, response=response)
    result = await handle_api_error(ctx, error, "search")

    assert "Not found error (404)" in result
    ctx.error.assert_called_once()


@pytest.mark.asyncio
async def test_handle_429_rate_limit():
    """Test handling of 429 rate limit errors."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.status_code = 429
    response.text = "Rate limit exceeded"

    error = httpx.HTTPStatusError("", request=None, response=response)
    result = await handle_api_error(ctx, error, "api call")

    assert "Rate limit exceeded (429)" in result
    assert "try again later" in result
    ctx.error.assert_called_once()


@pytest.mark.asyncio
async def test_handle_500_server_error():
    """Test handling of 500 server errors."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.status_code = 500
    response.text = "Internal server error"

    error = httpx.HTTPStatusError("", request=None, response=response)
    result = await handle_api_error(ctx, error, "operation")

    assert "Server error (500)" in result
    assert "CodeAlive service encountered an issue" in result


@pytest.mark.asyncio
async def test_handle_generic_exception():
    """Test handling of non-HTTP exceptions."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    error = ValueError("Invalid input")
    result = await handle_api_error(ctx, error, "parsing")

    assert "Error during parsing" in result
    assert "Invalid input" in result
    assert "check your input parameters" in result


@pytest.mark.asyncio
async def test_handle_unknown_http_error():
    """Test handling of unknown HTTP status codes."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.status_code = 418  # I'm a teapot
    response.text = "I'm a teapot" * 100  # Long error text

    error = httpx.HTTPStatusError("", request=None, response=response)
    result = await handle_api_error(ctx, error, "brewing")

    assert "HTTP error: 418" in result
    # Should truncate long error messages
    assert len(result) < 300


def test_format_data_source_names_strings():
    """Test formatting simple string names."""
    input_data = ["id1", "id2", "id3"]
    result = format_data_source_names(input_data)

    assert result == ["id1", "id2", "id3"]


def test_format_data_source_names_dicts():
    """Test formatting dictionary inputs."""
    input_data = [
        {"id": "id1"},
        {"type": "repository", "id": "id2"},
        {"name": "repo-name"},
        {"id": "id3", "extra": "field"}
    ]
    result = format_data_source_names(input_data)

    assert result == ["id1", "id2", "repo-name", "id3"]


def test_format_data_source_names_mixed():
    """Test formatting mixed format inputs."""
    input_data = [
        "id1",
        {"id": "id2"},
        {"type": "workspace", "id": "id3"},
        "",  # Empty string - should be skipped
        None,  # None - should be skipped
        {"no_id": "field"},  # Missing id - should be skipped
        {"name": "repo-name"},
        "id4"
    ]
    result = format_data_source_names(input_data)

    assert result == ["id1", "id2", "id3", "repo-name", "id4"]


def test_format_data_source_names_empty():
    """Test formatting empty/None inputs."""
    assert format_data_source_names(None) == []
    assert format_data_source_names([]) == []
    assert format_data_source_names([None, "", {}]) == []

