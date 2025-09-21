"""Test suite for chat completions tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastmcp import Context
from tools.chat import chat_completions


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_with_simple_ids(mock_get_api_key):
    """Test chat completions with simple string IDs."""
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

    # Test with simple string IDs
    result = await chat_completions(
        ctx=ctx,
        messages=[{"role": "user", "content": "Test question"}],
        data_sources=["repo123", "repo456"]
    )

    # Verify the API was called with correct format
    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should convert simple IDs to {"id": "..."} format
    assert request_data["dataSources"] == [
        {"id": "repo123"},
        {"id": "repo456"}
    ]

    assert result == "Hello world"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_with_dict_ids(mock_get_api_key):
    """Test chat completions with dictionary format IDs."""
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

    # Test with dict format (backward compatibility)
    result = await chat_completions(
        ctx=ctx,
        messages=[{"role": "user", "content": "Test"}],
        data_sources=[
            {"type": "repository", "id": "repo123"},
            {"id": "repo456"}
        ]
    )

    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should extract just the ID
    assert request_data["dataSources"] == [
        {"id": "repo123"},
        {"id": "repo456"}
    ]

    assert result == "Response"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_with_conversation_id(mock_get_api_key):
    """Test chat completions with existing conversation ID."""
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

    result = await chat_completions(
        ctx=ctx,
        messages=[{"role": "user", "content": "Follow up"}],
        conversation_id="conv_123"
    )

    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should include conversation ID
    assert request_data["conversationId"] == "conv_123"
    # Should not have data sources when continuing conversation
    assert "dataSources" not in request_data

    assert result == "Continued"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_empty_messages_validation(mock_get_api_key):
    """Test validation of empty messages."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.request_context.lifespan_context = MagicMock()

    # Test with no messages
    result = await chat_completions(ctx=ctx, messages=None)
    assert "Error: No messages provided" in result

    # Test with empty list
    result = await chat_completions(ctx=ctx, messages=[])
    assert "Error: No messages provided" in result


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_chat_invalid_message_format(mock_get_api_key):
    """Test validation of message format."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.request_context.lifespan_context = MagicMock()

    # Test with missing role
    result = await chat_completions(
        ctx=ctx,
        messages=[{"content": "Test"}]
    )
    assert "Error: Each message must have 'role' and 'content'" in result

    # Test with missing content
    result = await chat_completions(
        ctx=ctx,
        messages=[{"role": "user"}]
    )
    assert "Error: Each message must have 'role' and 'content'" in result


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
@patch('tools.chat.handle_api_error')
async def test_chat_error_handling(mock_handle_error, mock_get_api_key):
    """Test error handling in chat completions."""
    mock_get_api_key.return_value = "test_key"
    mock_handle_error.return_value = "Error: Authentication failed"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()

    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Network error")

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context

    result = await chat_completions(
        ctx=ctx,
        messages=[{"role": "user", "content": "Test"}],
        data_sources=["repo123"]
    )

    assert result == "Error: Authentication failed"
    mock_handle_error.assert_called_once()