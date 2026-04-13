"""Test suite for error handling utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx
from fastmcp.exceptions import ToolError
from utils.errors import handle_api_error, format_data_source_names


def _make_http_error(status_code: int, text: str = "") -> httpx.HTTPStatusError:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return httpx.HTTPStatusError("", request=None, response=response)


# ---------------------------------------------------------------------------
# Status code mapping — handle_api_error now raises ToolError (isError: true)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_401_error():
    """401 errors must be tagged non-retryable and surface API key recovery steps."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="Authentication error \\(401\\)"):
        await handle_api_error(ctx, _make_http_error(401, "Invalid token"), "test operation")

    ctx.error.assert_called_once()
    error_msg = ctx.error.call_args[0][0]
    assert "Invalid API key" in error_msg
    assert "Retry: no" in error_msg
    assert "Try:" in error_msg
    assert "CODEALIVE_API_KEY" in error_msg


@pytest.mark.asyncio
async def test_handle_404_error():
    """404 errors must be non-retryable and point at get_data_sources."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="Not found error \\(404\\)"):
        await handle_api_error(ctx, _make_http_error(404, "Resource not found"), "search")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: no" in error_msg
    assert "get_data_sources" in error_msg


@pytest.mark.asyncio
async def test_handle_429_rate_limit():
    """429 errors must be retryable with a concrete wait window."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="Rate limit exceeded \\(429\\)"):
        await handle_api_error(ctx, _make_http_error(429, "Rate limit exceeded"), "api call")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: yes" in error_msg
    assert "30" in error_msg


@pytest.mark.asyncio
async def test_handle_500_server_error():
    """500 errors must be retryable and include the issues URL for persistent failures."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="Server error \\(500\\)"):
        await handle_api_error(ctx, _make_http_error(500, "Internal server error"), "operation")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: yes" in error_msg
    assert "github.com/CodeAlive-AI/codealive-mcp/issues" in error_msg


@pytest.mark.asyncio
async def test_handle_422_data_source_not_ready():
    """422 errors must point at get_data_sources(alive_only=false)."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="422"):
        await handle_api_error(ctx, _make_http_error(422, "still indexing"), "search")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: yes" in error_msg
    assert "alive_only=false" in error_msg


@pytest.mark.asyncio
async def test_handle_502_bad_gateway():
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="502"):
        await handle_api_error(ctx, _make_http_error(502), "search")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: yes" in error_msg
    assert "10" in error_msg


@pytest.mark.asyncio
async def test_handle_503_service_unavailable():
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="503"):
        await handle_api_error(ctx, _make_http_error(503), "search")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: yes" in error_msg


@pytest.mark.asyncio
async def test_handle_generic_exception():
    """Non-HTTP exceptions still produce a structured Retry/Try message."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    error = ValueError("Invalid input")
    with pytest.raises(ToolError, match="Invalid input"):
        await handle_api_error(ctx, error, "parsing")

    error_msg = ctx.error.call_args[0][0]
    assert "Error during parsing" in error_msg
    assert "Retry: no" in error_msg
    assert "Try:" in error_msg


@pytest.mark.asyncio
async def test_handle_unknown_http_error():
    """Unknown 4xx codes carry the raw detail (truncated) and a 'do not retry' marker."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    error = _make_http_error(418, "I'm a teapot" * 100)
    with pytest.raises(ToolError, match="418"):
        await handle_api_error(ctx, error, "brewing")

    error_msg = ctx.error.call_args[0][0]
    assert "HTTP error: 418" in error_msg
    assert "Retry: no" in error_msg


@pytest.mark.asyncio
async def test_handle_timeout_error():
    """Timeouts must be tagged retryable with explicit guidance."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError, match="timeout"):
        await handle_api_error(ctx, httpx.ReadTimeout("slow"), "search")

    error_msg = ctx.error.call_args[0][0]
    assert "Retry: yes" in error_msg


# ---------------------------------------------------------------------------
# Per-tool recovery_hints overrides
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_hints_override_default_404():
    """A per-tool 404 hint must replace the generic one."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    custom = "(1) check conversation_id, (2) drop conversation_id and retry"
    with pytest.raises(ToolError) as exc_info:
        await handle_api_error(
            ctx, _make_http_error(404), "chat",
            recovery_hints={404: custom},
        )

    result = str(exc_info.value)
    assert "Not found error (404)" in result
    assert custom in result
    assert "get_data_sources" not in result


@pytest.mark.asyncio
async def test_recovery_hints_only_apply_to_matching_status():
    """A 404 override must NOT change a 401 error."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError) as exc_info:
        await handle_api_error(
            ctx, _make_http_error(401), "chat",
            recovery_hints={404: "this should not appear"},
        )

    result = str(exc_info.value)
    assert "Authentication error (401)" in result
    assert "this should not appear" not in result
    assert "CODEALIVE_API_KEY" in result


@pytest.mark.asyncio
async def test_method_prefix_applied():
    """The [method] prefix must be present in both raised and logged messages."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError) as exc_info:
        await handle_api_error(
            ctx, _make_http_error(401), "chat",
            method="chat",
        )

    assert str(exc_info.value).startswith("[chat] Error:")
    logged = ctx.error.call_args[0][0]
    assert logged.startswith("[chat] ")


# ---------------------------------------------------------------------------
# format_data_source_names — unchanged behaviour
# ---------------------------------------------------------------------------

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
