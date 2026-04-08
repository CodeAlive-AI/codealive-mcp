"""Test suite for error handling utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx
from utils.errors import handle_api_error, format_data_source_names


def _make_http_error(status_code: int, text: str = "") -> httpx.HTTPStatusError:
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    return httpx.HTTPStatusError("", request=None, response=response)


# ---------------------------------------------------------------------------
# Status code mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_401_error():
    """401 errors must be tagged non-retryable and surface API key recovery steps."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(401, "Invalid token"), "test operation")

    assert "Authentication error (401)" in result
    assert "Invalid API key" in result
    # New: explicit retry decision + actionable hint
    assert "Retry: no" in result
    assert "Try:" in result
    assert "CODEALIVE_API_KEY" in result
    ctx.error.assert_called_once()


@pytest.mark.asyncio
async def test_handle_404_error():
    """404 errors must be non-retryable and point at get_data_sources."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(404, "Resource not found"), "search")

    assert "Not found error (404)" in result
    assert "Retry: no" in result
    assert "get_data_sources" in result
    ctx.error.assert_called_once()


@pytest.mark.asyncio
async def test_handle_429_rate_limit():
    """429 errors must be retryable with a concrete wait window."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(429, "Rate limit exceeded"), "api call")

    assert "Rate limit exceeded (429)" in result
    assert "try again later" in result
    # New: structured retryability marker
    assert "Retry: yes" in result
    assert "30" in result  # mentions a concrete wait window
    ctx.error.assert_called_once()


@pytest.mark.asyncio
async def test_handle_500_server_error():
    """500 errors must be retryable and include the issues URL for persistent failures."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(500, "Internal server error"), "operation")

    assert "Server error (500)" in result
    assert "CodeAlive service encountered an issue" in result
    assert "Retry: yes" in result
    assert "github.com/CodeAlive-AI/codealive-mcp/issues" in result


@pytest.mark.asyncio
async def test_handle_422_data_source_not_ready():
    """422 errors must point at get_data_sources(alive_only=false)."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(422, "still indexing"), "search")

    assert "(422)" in result
    assert "Retry: yes" in result
    assert "alive_only=false" in result


@pytest.mark.asyncio
async def test_handle_502_bad_gateway():
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(502), "search")

    assert "(502)" in result
    assert "Retry: yes" in result
    assert "10" in result  # wait window mentioned


@pytest.mark.asyncio
async def test_handle_503_service_unavailable():
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, _make_http_error(503), "search")

    assert "(503)" in result
    assert "Retry: yes" in result


@pytest.mark.asyncio
async def test_handle_generic_exception():
    """Non-HTTP exceptions still produce a structured Retry/Try message."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    error = ValueError("Invalid input")
    result = await handle_api_error(ctx, error, "parsing")

    assert "Error during parsing" in result
    assert "Invalid input" in result
    assert "Retry: no" in result
    assert "Try:" in result


@pytest.mark.asyncio
async def test_handle_unknown_http_error():
    """Unknown 4xx codes carry the raw detail (truncated) and a 'do not retry' marker."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    error = _make_http_error(418, "I'm a teapot" * 100)
    result = await handle_api_error(ctx, error, "brewing")

    assert "HTTP error: 418" in result
    assert "Retry: no" in result
    # Detail is capped to 200 chars; the rest of the message adds ~120 chars of structured suffix
    assert len(result) < 400


@pytest.mark.asyncio
async def test_handle_timeout_error():
    """Timeouts must be tagged retryable with explicit guidance."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(ctx, httpx.ReadTimeout("slow"), "search")

    assert "timeout" in result.lower()
    assert "Retry: yes" in result


# ---------------------------------------------------------------------------
# Per-tool recovery_hints overrides
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recovery_hints_override_default_404():
    """A per-tool 404 hint must replace the generic one."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    custom = "(1) check conversation_id, (2) drop conversation_id and retry"
    result = await handle_api_error(
        ctx, _make_http_error(404), "chat",
        recovery_hints={404: custom},
    )

    assert "Not found error (404)" in result
    assert custom in result
    # Default 404 hint about get_data_sources is suppressed when overridden
    assert "get_data_sources" not in result


@pytest.mark.asyncio
async def test_recovery_hints_only_apply_to_matching_status():
    """A 404 override must NOT change a 401 error."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(
        ctx, _make_http_error(401), "chat",
        recovery_hints={404: "this should not appear"},
    )

    assert "Authentication error (401)" in result
    assert "this should not appear" not in result
    # Default 401 hint is preserved
    assert "CODEALIVE_API_KEY" in result


@pytest.mark.asyncio
async def test_method_prefix_applied():
    """The [method] prefix must be present in both returned and logged messages."""
    ctx = MagicMock()
    ctx.error = AsyncMock()

    result = await handle_api_error(
        ctx, _make_http_error(401), "chat",
        method="chat",
    )

    assert result.startswith("[chat] Error:")
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
