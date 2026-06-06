"""Tests for data sources tool."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Context

from tools.datasources import get_data_sources


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_removes_repository_ids_from_workspaces(mock_get_api_key):
    """Test that repositoryIds are removed from workspace data sources."""
    mock_get_api_key.return_value = "test-key"

    # Mock context
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.info = AsyncMock()
    mock_ctx.warning = AsyncMock()
    mock_ctx.error = AsyncMock()

    mock_lifespan_context = MagicMock()
    mock_lifespan_context.base_url = "https://api.example.com"

    # Mock client with response containing workspaces with repositoryIds
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "repo-1",
            "name": "Test Repository",
            "type": "Repository",
            "url": "https://github.com/example/repo",
            "state": "Alive"
        },
        {
            "id": "workspace-1",
            "name": "Test Workspace",
            "type": "Workspace",
            "repositoryIds": ["repo-1", "repo-2", "repo-3"],
            "state": "Alive"
        }
    ]
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_lifespan_context.client = mock_client

    mock_ctx.request_context.lifespan_context = mock_lifespan_context

    # Call the function
    result = await get_data_sources(mock_ctx, alive_only=True)

    # Result is a compact JSON array
    data_sources = json.loads(result)

    # Verify repository still has all fields
    repo = next(ds for ds in data_sources if ds["type"] == "Repository")
    assert repo["id"] == "repo-1"
    assert repo["name"] == "Test Repository"
    assert repo["url"] == "https://github.com/example/repo"
    assert "repositoryIds" not in repo

    # Verify workspace has repositoryIds removed
    workspace = next(ds for ds in data_sources if ds["type"] == "Workspace")
    assert workspace["id"] == "workspace-1"
    assert workspace["name"] == "Test Workspace"
    assert "repositoryIds" not in workspace, "repositoryIds should be removed from workspace"

    # Verify API was called correctly. Headers include CodeAlive integration
    # markers added on every request, so assert on the relevant subset.
    mock_client.get.assert_called_once()
    call_args = mock_client.get.call_args
    assert call_args.args[0] == "/api/datasources/ready"
    headers = call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["X-CodeAlive-Tool"] == "get_data_sources"
    assert headers["X-CodeAlive-Integration"] == "mcp"


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_preserves_other_workspace_fields(mock_get_api_key):
    """Test that other workspace fields are preserved when removing repositoryIds."""
    mock_get_api_key.return_value = "test-key"

    # Mock context
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.info = AsyncMock()
    mock_ctx.warning = AsyncMock()
    mock_ctx.error = AsyncMock()

    mock_lifespan_context = MagicMock()
    mock_lifespan_context.base_url = "https://api.example.com"

    # Mock client with workspace containing various fields
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "workspace-1",
            "name": "Test Workspace",
            "type": "Workspace",
            "state": "Alive",
            "repositoryIds": ["repo-1", "repo-2"],
            "customField": "custom-value",
            "createdAt": "2025-01-01T00:00:00Z"
        }
    ]
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_lifespan_context.client = mock_client

    mock_ctx.request_context.lifespan_context = mock_lifespan_context

    # Call the function
    result = await get_data_sources(mock_ctx, alive_only=True)

    # Result is compact JSON array
    data_sources = json.loads(result)

    workspace = data_sources[0]

    # Verify repositoryIds removed but other fields preserved
    assert "repositoryIds" not in workspace
    assert workspace["id"] == "workspace-1"
    assert workspace["name"] == "Test Workspace"
    assert workspace["type"] == "Workspace"
    assert workspace["state"] == "Alive"
    assert workspace["customField"] == "custom-value"
    assert workspace["createdAt"] == "2025-01-01T00:00:00Z"


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_handles_missing_repository_ids(mock_get_api_key):
    """Test that function handles workspaces without repositoryIds field."""
    mock_get_api_key.return_value = "test-key"

    # Mock context
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.info = AsyncMock()
    mock_ctx.warning = AsyncMock()
    mock_ctx.error = AsyncMock()

    mock_lifespan_context = MagicMock()
    mock_lifespan_context.base_url = "https://api.example.com"

    # Mock client with workspace without repositoryIds
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "id": "workspace-1",
            "name": "Test Workspace",
            "type": "Workspace",
            "state": "Alive"
        }
    ]
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_lifespan_context.client = mock_client

    mock_ctx.request_context.lifespan_context = mock_lifespan_context

    # Call the function - should not raise an error
    result = await get_data_sources(mock_ctx, alive_only=True)

    # Result is compact JSON array
    data_sources = json.loads(result)

    # Verify workspace is intact
    workspace = data_sources[0]
    assert workspace["id"] == "workspace-1"
    assert workspace["name"] == "Test Workspace"
    assert "repositoryIds" not in workspace


def _ctx_with_response(json_return, headers=None):
    """Builds a mocked Context whose client.get returns a response with the given JSON body."""
    mock_ctx = MagicMock(spec=Context)
    mock_ctx.info = AsyncMock()
    mock_ctx.warning = AsyncMock()
    mock_ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = json_return
    mock_response.headers = headers or {}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_lifespan_context = MagicMock()
    mock_lifespan_context.base_url = "https://api.example.com"
    mock_lifespan_context.client = mock_client
    mock_ctx.request_context.lifespan_context = mock_lifespan_context
    return mock_ctx, mock_client


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_with_query_passes_query_param(mock_get_api_key):
    """When a query is supplied, it is forwarded to the listing endpoint as the `query` param."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, mock_client = _ctx_with_response([
        {"id": "repo-1", "name": "Repo", "type": "Repository", "relevanceReason": "handles OAuth"},
    ])

    await get_data_sources(mock_ctx, alive_only=True, query="add OAuth to checkout")

    call_args = mock_client.get.call_args
    assert call_args.args[0] == "/api/datasources/ready"
    assert call_args.kwargs["params"] == {"query": "add OAuth to checkout"}


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_without_query_sends_no_query_param(mock_get_api_key):
    """Without a query, no `query` param is sent (legacy behavior unchanged)."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, mock_client = _ctx_with_response([
        {"id": "repo-1", "name": "Repo", "type": "Repository"},
    ])

    await get_data_sources(mock_ctx, alive_only=True)

    call_args = mock_client.get.call_args
    assert call_args.kwargs.get("params") is None


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_surfaces_relevance_reason(mock_get_api_key):
    """relevanceReason is preserved per item for the client (wrapped shape when query is set)."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response([
        {"id": "repo-1", "name": "Repo", "type": "Repository", "relevanceReason": "implements the checkout flow"},
    ])

    result = await get_data_sources(mock_ctx, alive_only=True, query="checkout")

    payload = json.loads(result)
    assert payload["dataSources"][0]["relevanceReason"] == "implements the checkout flow"


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_filtered_hint_reports_total_and_omitted(mock_get_api_key):
    """Filtered success surfaces how many sources exist beyond the shown subset and how to get them."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response(
        [{"id": "repo-1", "name": "Repo", "type": "Repository", "relevanceReason": "checkout flow"}],
        headers={"X-CodeAlive-Total-Data-Sources": "25"},
    )

    result = await get_data_sources(mock_ctx, alive_only=True, query="checkout")

    payload = json.loads(result)
    assert len(payload["dataSources"]) == 1
    assert "1 of 25" in payload["message"]
    assert "omitted" in payload["message"].lower()
    assert "without a query" in payload["message"].lower()


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_filtered_hint_without_total_header(mock_get_api_key):
    """Filtered success without the total header still hints that sources were omitted."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response(
        [{"id": "repo-1", "name": "Repo", "type": "Repository", "relevanceReason": "checkout flow"}],
    )

    result = await get_data_sources(mock_ctx, alive_only=True, query="checkout")

    payload = json.loads(result)
    assert "omitted" in payload["message"].lower()
    assert "without a query" in payload["message"].lower()


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_all_relevant_hint_reports_no_omission(mock_get_api_key):
    """When every available source is relevant, the hint says so instead of claiming omissions."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response(
        [{"id": "repo-1", "name": "Repo", "type": "Repository", "relevanceReason": "checkout flow"}],
        headers={"X-CodeAlive-Total-Data-Sources": "1"},
    )

    result = await get_data_sources(mock_ctx, alive_only=True, query="checkout")

    payload = json.loads(result)
    assert "all 1" in payload["message"].lower()
    assert "omitted" not in payload["message"].lower()


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_failopen_hint_when_no_reasons_present(mock_get_api_key):
    """Query supplied but no item carries relevanceReason → the filter did not run (fail-open,
    disabled, or an older backend); the hint must say the FULL list is returned."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response([
        {"id": "repo-1", "name": "Repo", "type": "Repository"},
        {"id": "repo-2", "name": "Other", "type": "Repository"},
    ])

    result = await get_data_sources(mock_ctx, alive_only=True, query="checkout")

    payload = json.loads(result)
    assert len(payload["dataSources"]) == 2
    assert "unavailable" in payload["message"].lower()
    assert "full" in payload["message"].lower()


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_empty_with_query_returns_no_relevant_message(mock_get_api_key):
    """Empty result WITH a query returns a 'no relevant' message, not 'add a repository'."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response([])

    result = await get_data_sources(mock_ctx, alive_only=True, query="something unrelated")

    payload = json.loads(result)
    assert payload["dataSources"] == []
    assert "relevant" in payload["message"].lower()
    assert "add a repository" not in payload["message"].lower()


@pytest.mark.asyncio
@patch('tools.datasources.get_api_key_from_context')
async def test_get_data_sources_empty_without_query_keeps_add_repository_message(mock_get_api_key):
    """Empty result WITHOUT a query keeps the existing 'add a repository' message."""
    mock_get_api_key.return_value = "test-key"
    mock_ctx, _ = _ctx_with_response([])

    result = await get_data_sources(mock_ctx, alive_only=True)

    payload = json.loads(result)
    assert payload["dataSources"] == []
    assert "add a repository" in payload["message"].lower()