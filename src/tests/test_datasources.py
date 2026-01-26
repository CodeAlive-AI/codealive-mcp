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

    # Parse the result to verify repositoryIds were removed
    # The result format is: "Available data sources:\n{json}\n\nYou can use..."
    json_start = result.index('[')
    json_end = result.rindex(']') + 1
    data_sources = json.loads(result[json_start:json_end])

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

    # Verify API was called correctly
    mock_client.get.assert_called_once_with(
        "/api/datasources/ready",
        headers={"Authorization": "Bearer test-key"}
    )


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

    # Parse the result
    json_start = result.index('[')
    json_end = result.rindex(']') + 1
    data_sources = json.loads(result[json_start:json_end])

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

    # Parse the result
    json_start = result.index('[')
    json_end = result.rindex(']') + 1
    data_sources = json.loads(result[json_start:json_end])

    # Verify workspace is intact
    workspace = data_sources[0]
    assert workspace["id"] == "workspace-1"
    assert workspace["name"] == "Test Workspace"
    assert "repositoryIds" not in workspace