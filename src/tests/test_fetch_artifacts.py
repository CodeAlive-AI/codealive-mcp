"""Test suite for fetch_artifacts tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context
from tools.fetch_artifacts import fetch_artifacts


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_returns_xml(mock_get_api_key):
    """Test that fetch_artifacts returns properly formatted XML."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "artifacts": [
            {
                "identifier": "owner/repo::src/auth.py::login",
                "content": "def login(user, pwd):\n    return True",
                "contentByteSize": 38
            },
            {
                "identifier": "owner/repo::src/missing.py::func",
                "content": None,
                "contentByteSize": None
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await fetch_artifacts(
        ctx=ctx,
        identifiers=["owner/repo::src/auth.py::login", "owner/repo::src/missing.py::func"],
    )

    assert isinstance(result, str)
    assert "<artifacts>" in result
    assert "</artifacts>" in result
    # Found artifact has content
    assert "def login(user, pwd):" in result
    assert 'contentByteSize="38"' in result
    assert 'identifier="owner/repo::src/auth.py::login"' in result
    # Not-found artifact is skipped (not in output)
    assert "missing.py" not in result


@pytest.mark.asyncio
async def test_fetch_artifacts_empty_identifiers():
    """Test that empty identifiers list returns an error."""
    ctx = MagicMock(spec=Context)

    result = await fetch_artifacts(ctx=ctx, identifiers=[])

    assert "<error>" in result
    assert "At least one identifier" in result


@pytest.mark.asyncio
async def test_fetch_artifacts_exceeds_max_identifiers():
    """Test that more than 20 identifiers returns an error."""
    ctx = MagicMock(spec=Context)

    identifiers = [f"owner/repo::file{i}.py::func{i}" for i in range(21)]

    result = await fetch_artifacts(ctx=ctx, identifiers=identifiers)

    assert "<error>" in result
    assert "Maximum 20" in result


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_posts_correct_body(mock_get_api_key):
    """Test that fetch_artifacts sends the correct POST body."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"artifacts": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    await fetch_artifacts(
        ctx=ctx,
        identifiers=["id1", "id2"],
    )

    call_args = mock_client.post.call_args
    assert call_args.args[0] == "/api/search/artifacts"
    body = call_args.kwargs["json"]
    assert body["identifiers"] == ["id1", "id2"]
    assert "names" not in body


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_api_error(mock_get_api_key):
    """Test that API errors are handled gracefully."""
    import httpx

    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"

    def raise_500():
        raise httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response
        )

    mock_response.raise_for_status = raise_500

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await fetch_artifacts(
        ctx=ctx,
        identifiers=["some-id"],
    )

    assert isinstance(result, str)
    assert "<error>" in result


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_escapes_xml(mock_get_api_key):
    """Test that content with XML special characters is properly escaped."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "artifacts": [
            {
                "identifier": "owner/repo::file.py::func",
                "content": 'if x < 10 && y > 5:\n    return "<ok>"',
                "contentByteSize": 40
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await fetch_artifacts(
        ctx=ctx,
        identifiers=["owner/repo::file.py::func"],
    )

    assert "&lt;" in result
    assert "&amp;" in result
    assert "<artifacts>" in result
    assert "</artifacts>" in result
