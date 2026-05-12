"""Test suite for chat tool and legacy consultant alias."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastmcp import Context
from fastmcp.exceptions import ToolError
from tools.chat import chat, codebase_consultant


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_with_simple_names(mock_get_api_key):
    """Test chat with simple string names."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    # Mock streaming response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    # Simulate SSE streaming response
    async def mock_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"Hello"}}]}'
        yield 'data: {"choices":[{"delta":{"content":" world"}}]}'
        yield 'data: [DONE]'

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    # Test with simple string names
    result = await chat(
        ctx=ctx,
        question="Test question",
        data_sources=["repo123", "repo456"]
    )

    # Verify the API was called with correct format
    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should convert simple names to the backend names array
    assert request_data["names"] == [
        "repo123",
        "repo456"
    ]

    assert result == "Hello world"
    assert call_args.kwargs["headers"]["Accept"] == "text/event-stream, application/problem+json"
    assert call_args.kwargs["headers"]["X-CodeAlive-Tool"] == "chat"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_consultant_alias_preserves_string_names(mock_get_api_key):
    """Test deprecated consultant alias preserves behavior."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"Response"}}]}'
        yield 'data: [DONE]'

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    # Test with string names
    result = await codebase_consultant(
        ctx=ctx,
        question="Test",
        data_sources=["repo123", "repo456"]
    )

    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should extract just the normalized names
    assert request_data["names"] == [
        "repo123",
        "repo456"
    ]

    assert result == "Response"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_with_conversation_id(mock_get_api_key):
    """Test chat with existing conversation ID."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices":[{"delta":{"content":"Continued"}}]}'
        yield 'data: [DONE]'

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    result = await chat(
        ctx=ctx,
        question="Follow up",
        conversation_id="69fceb3e7b2a6a7efdd18180"
    )

    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should include conversation ID
    assert request_data["conversationId"] == "69fceb3e7b2a6a7efdd18180"
    # Should not have explicit names when continuing conversation
    assert "names" not in request_data
    assert result == "Continued"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_rejects_non_objectid_conversation_id(mock_get_api_key):
    """Invalid continuation IDs fail locally with an actionable ToolError."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    with pytest.raises(ToolError) as exc:
        await chat(
            ctx=ctx,
            question="Follow up",
            conversation_id="conv_123",
        )

    msg = str(exc.value)
    assert "24-character hex Mongo ObjectId" in msg
    assert "Retry: no" in msg


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_named_sse_error_raises_tool_error(mock_get_api_key):
    """RFC 9457 `event: error` frames must not collapse to an empty answer."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'event: error'
        yield 'data: {"title":"Bad request","status":400,"detail":"Message content violates our content policy","requestId":"req-1"}'
        yield ''

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    with pytest.raises(ToolError) as exc:
        await chat(ctx=ctx, question="Test question", data_sources=["repo123"])

    msg = str(exc.value)
    assert "Message content violates our content policy" in msg
    assert "Code: 400" in msg
    assert "Retry: no" in msg
    assert "requestId=req-1" in msg


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_named_sse_rate_limit_error_is_retryable(mock_get_api_key):
    """429 ProblemDetails frames should tell agents to back off, not fix input."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'event: error'
        yield 'data: {"title":"Plan limit","status":429,"detail":"Chat completion rate limit exceeded","requestId":"req-429"}'
        yield ''

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    with pytest.raises(ToolError) as exc:
        await chat(ctx=ctx, question="Test question", data_sources=["repo123"])

    msg = str(exc.value)
    assert "Chat completion rate limit exceeded" in msg
    assert "Retry: yes" in msg
    assert "back off" in msg
    assert "requestId=req-429" in msg


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_empty_question_validation(mock_get_api_key):
    """Test validation of empty question."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.request_context.lifespan_context = MagicMock()

    # Test with empty question
    with pytest.raises(ToolError, match="No question provided"):
        await chat(ctx=ctx, question="")

    # Test with whitespace only
    with pytest.raises(ToolError, match="No question provided"):
        await chat(ctx=ctx, question="   ")




@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
@patch('tools.chat.handle_api_error')
async def test_chat_error_handling(mock_handle_error, mock_get_api_key):
    """Test error handling in chat — handle_api_error raises ToolError."""
    mock_get_api_key.return_value = "test_key"
    mock_handle_error.side_effect = ToolError("Error: Authentication failed")

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()

    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Network error")

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    with pytest.raises(ToolError, match="Authentication failed"):
        await chat(
            ctx=ctx,
            question="Test",
            data_sources=["repo123"]
        )

    mock_handle_error.assert_called_once()
