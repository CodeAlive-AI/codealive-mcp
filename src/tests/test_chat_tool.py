"""Test suite for codebase consultant tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from fastmcp import Context
from tools.chat import codebase_consultant


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_consultant_with_simple_names(mock_get_api_key):
    """Test codebase consultant with simple string names."""
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
    result = await codebase_consultant(
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


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_consultant_preserves_string_names(mock_get_api_key):
    """Test codebase consultant preserves string names."""
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
async def test_consultant_with_conversation_id(mock_get_api_key):
    """Test codebase consultant with existing conversation ID."""
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

    result = await codebase_consultant(
        ctx=ctx,
        question="Follow up",
        conversation_id="conv_123"
    )

    call_args = mock_client.post.call_args
    request_data = call_args.kwargs["json"]

    # Should include conversation ID
    assert request_data["conversationId"] == "conv_123"
    # Should not have explicit names when continuing conversation
    assert "names" not in request_data

    assert result == "Continued"


@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
async def test_consultant_empty_question_validation(mock_get_api_key):
    """Test validation of empty question."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.request_context.lifespan_context = MagicMock()

    # Test with empty question
    result = await codebase_consultant(ctx=ctx, question="")
    assert "Error: No question provided" in result

    # Test with whitespace only
    result = await codebase_consultant(ctx=ctx, question="   ")
    assert "Error: No question provided" in result




@pytest.mark.asyncio
@patch('tools.chat.get_api_key_from_context')
@patch('tools.chat.handle_api_error')
async def test_consultant_error_handling(mock_handle_error, mock_get_api_key):
    """Test error handling in codebase consultant."""
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

    result = await codebase_consultant(
        ctx=ctx,
        question="Test",
        data_sources=["repo123"]
    )

    assert result == "Error: Authentication failed"
    mock_handle_error.assert_called_once()