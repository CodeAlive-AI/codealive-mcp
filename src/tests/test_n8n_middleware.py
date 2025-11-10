"""Test suite for n8n middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from middleware.n8n_middleware import N8NRemoveParametersMiddleware, EXTRA_KEYS


@pytest.mark.asyncio
async def test_strips_n8n_extra_parameters():
    """Test that middleware strips n8n extra parameters."""
    middleware = N8NRemoveParametersMiddleware()

    # Create mock context with n8n extra parameters
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = {
        "query": "test query",
        "data_sources": ["test-repo"],
        "sessionId": "session_123",
        "action": "tool_call",
        "chatInput": "user input",
        "toolCallId": "call_456"
    }

    # Create mock call_next
    call_next = AsyncMock(return_value="result")

    # Call middleware
    result = await middleware.on_call_tool(context, call_next)

    # Verify n8n parameters were stripped
    assert "sessionId" not in context.message.arguments
    assert "action" not in context.message.arguments
    assert "chatInput" not in context.message.arguments
    assert "toolCallId" not in context.message.arguments

    # Verify tool parameters remain
    assert "query" in context.message.arguments
    assert "data_sources" in context.message.arguments
    assert context.message.arguments["query"] == "test query"
    assert context.message.arguments["data_sources"] == ["test-repo"]

    # Verify call_next was called
    call_next.assert_called_once_with(context)

    # Verify result is passed through
    assert result == "result"


@pytest.mark.asyncio
async def test_preserves_all_valid_parameters():
    """Test that middleware preserves all valid tool parameters."""
    middleware = N8NRemoveParametersMiddleware()

    # Create mock context with only valid parameters
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = {
        "query": "search term",
        "data_sources": ["repo1", "repo2"],
        "mode": "auto",
        "include_content": False
    }

    # Create mock call_next
    call_next = AsyncMock(return_value="result")

    # Call middleware
    await middleware.on_call_tool(context, call_next)

    # Verify all valid parameters remain
    assert context.message.arguments == {
        "query": "search term",
        "data_sources": ["repo1", "repo2"],
        "mode": "auto",
        "include_content": False
    }


@pytest.mark.asyncio
async def test_handles_missing_arguments():
    """Test that middleware handles missing arguments gracefully."""
    middleware = N8NRemoveParametersMiddleware()

    # Create mock context without arguments
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = None

    # Create mock call_next
    call_next = AsyncMock(return_value="result")

    # Call middleware - should not raise error
    result = await middleware.on_call_tool(context, call_next)

    # Verify call_next was called
    call_next.assert_called_once_with(context)
    assert result == "result"


@pytest.mark.asyncio
async def test_handles_non_dict_arguments():
    """Test that middleware handles non-dict arguments."""
    middleware = N8NRemoveParametersMiddleware()

    # Create mock context with non-dict arguments
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = "string_arguments"

    # Create mock call_next
    call_next = AsyncMock(return_value="result")

    # Call middleware - should not raise error
    result = await middleware.on_call_tool(context, call_next)

    # Verify arguments unchanged
    assert context.message.arguments == "string_arguments"

    # Verify call_next was called
    call_next.assert_called_once_with(context)
    assert result == "result"


@pytest.mark.asyncio
async def test_strips_partial_n8n_parameters():
    """Test that middleware strips only n8n parameters that are present."""
    middleware = N8NRemoveParametersMiddleware()

    # Create mock context with some n8n parameters
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = {
        "query": "test",
        "sessionId": "session_123",
        "action": "call"
        # Missing chatInput and toolCallId
    }

    # Create mock call_next
    call_next = AsyncMock(return_value="result")

    # Call middleware
    await middleware.on_call_tool(context, call_next)

    # Verify only present n8n parameters were stripped
    assert context.message.arguments == {"query": "test"}


@pytest.mark.asyncio
async def test_does_not_strip_similar_named_parameters():
    """Test that middleware only strips exact n8n parameter names."""
    middleware = N8NRemoveParametersMiddleware()

    # Create mock context with similar but different parameter names
    context = MagicMock()
    context.message = MagicMock()
    context.message.arguments = {
        "query": "test",
        "sessionId": "session_123",  # Should be stripped
        "session_id": "keep_this",    # Should NOT be stripped (different name)
        "myAction": "keep_this_too"   # Should NOT be stripped (different name)
    }

    # Create mock call_next
    call_next = AsyncMock(return_value="result")

    # Call middleware
    await middleware.on_call_tool(context, call_next)

    # Verify only exact n8n parameter names were stripped
    assert "sessionId" not in context.message.arguments
    assert "session_id" in context.message.arguments
    assert "myAction" in context.message.arguments
    assert context.message.arguments["session_id"] == "keep_this"
    assert context.message.arguments["myAction"] == "keep_this_too"


@pytest.mark.asyncio
async def test_all_extra_keys_defined():
    """Test that all expected n8n extra keys are defined."""
    expected_keys = {"sessionId", "action", "chatInput", "toolCallId"}
    assert EXTRA_KEYS == expected_keys, f"EXTRA_KEYS mismatch: expected {expected_keys}, got {EXTRA_KEYS}"
