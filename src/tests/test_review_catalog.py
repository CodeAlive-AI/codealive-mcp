"""Review-profile catalog advertising and ask_codebase forwarding."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client, Context
from fastmcp.server.auth import AccessToken

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.review_catalog import (
    PUBLIC_TOOL_NAMES,
    REVIEWER_TOOL_NAMES,
    SYNTHESIZER_TOOL_NAMES,
    advertised_tool_names,
    is_verified_review_capability,
)
from tools.chat import ask_codebase
from tools.tool_api import call_tool_api

LEGACY_API_KEY = "ca_1720000000000_0123456789abcdef0123456789abcdef0123456789a"


def _context_with_response(rendered: str = "<result>ok</result>", obj: dict | None = None):
    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    response = MagicMock()
    response.json.return_value = {
        "rendered": rendered,
        "obj": obj if obj is not None else {"ok": True},
    }
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.post.return_value = response

    codealive_context = MagicMock()
    codealive_context.client = client
    codealive_context.base_url = "https://app.codealive.ai/api/"
    codealive_context.config = Config(oauth_enabled=False)
    codealive_context.tool_token_cache = None

    ctx.request_context.lifespan_context = codealive_context
    return ctx, client


def _review_access(profile: str = "reviewer-tools:v1") -> AccessToken:
    return AccessToken(
        token="header.payload.signature",
        client_id="codealive-agents-server",
        scopes=[],
        claims={
            "aud": "urn:codealive:tool-api",
            "sub": "codealive-agents-server",
            "review_id": "0123456789abcdef01234567",
            "organisation_id": "1123456789abcdef01234567",
            "review_tool_profile": profile,
            "primary_data_source_id": "2123456789abcdef01234567",
        },
        subject="0123456789abcdef01234567:reviewer-tools:v1",
    )


def test_public_catalog_hides_ask_codebase_and_keeps_chat():
    names = advertised_tool_names(None, tool_api_resource="urn:codealive:tool-api")
    assert names == PUBLIC_TOOL_NAMES
    assert "ask_codebase" not in names
    assert names[-1] == "chat"


def test_reviewer_catalog_is_exact_v1_without_chat_or_ontology():
    names = advertised_tool_names(
        _review_access(),
        tool_api_resource="urn:codealive:tool-api",
    )
    assert names == REVIEWER_TOOL_NAMES
    assert names[0] == "ask_codebase"
    assert "chat" not in names
    assert "get_repository_ontology" not in names


def test_synthesizer_catalog_adds_ontology_only():
    names = advertised_tool_names(
        _review_access("synthesizer-tools:v1"),
        tool_api_resource="urn:codealive:tool-api",
    )
    assert names == SYNTHESIZER_TOOL_NAMES
    assert names[-1] == "get_repository_ontology"
    assert "chat" not in names


def test_unknown_review_profile_advertises_empty_catalog():
    access = _review_access("reviewer-tools:v2")
    names = advertised_tool_names(access, tool_api_resource="urn:codealive:tool-api")
    assert names == ()


def test_missing_review_profile_advertises_empty_catalog():
    access = _review_access()
    claims = dict(access.claims or {})
    claims.pop("review_tool_profile", None)
    access = AccessToken(
        token=access.token,
        client_id=access.client_id,
        scopes=access.scopes,
        claims=claims,
        subject=access.subject,
    )
    names = advertised_tool_names(access, tool_api_resource="urn:codealive:tool-api")
    assert names == ()
    assert is_verified_review_capability(access, "urn:codealive:tool-api") is True


def test_unverified_access_is_not_a_review_capability():
    assert is_verified_review_capability(None, "urn:codealive:tool-api") is False
    mcp_user = AccessToken(
        token="header.payload.signature",
        client_id="client",
        scopes=["mcp:tools"],
        claims={"aud": "https://mcp.codealive.ai/api"},
    )
    assert is_verified_review_capability(mcp_user, "urn:codealive:tool-api") is False


@pytest.mark.asyncio
async def test_public_list_tools_does_not_advertise_ask_codebase():
    from codealive_mcp_server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert [tool.name for tool in tools] == list(PUBLIC_TOOL_NAMES)
    assert "ask_codebase" not in {tool.name for tool in tools}


@pytest.mark.asyncio
@patch("middleware.review_catalog.get_access_token", return_value=_review_access())
async def test_reviewer_list_tools_is_the_closed_v1_catalog(_mock_access):
    from codealive_mcp_server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert [tool.name for tool in tools] == list(REVIEWER_TOOL_NAMES)


@pytest.mark.asyncio
@patch(
    "middleware.review_catalog.get_access_token",
    return_value=_review_access("reviewer-tools:v2"),
)
async def test_unknown_review_profile_list_tools_is_empty(_mock_access):
    from codealive_mcp_server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert tools == []


@pytest.mark.asyncio
@patch("tools.tool_api.get_access_token", return_value=_review_access())
@patch("tools.tool_api.exchange_for_tool_token", new_callable=AsyncMock)
@patch("tools.tool_api.get_api_key_from_context")
async def test_review_capability_is_forwarded_unchanged(
    mock_get_api_key,
    mock_exchange,
    _mock_access,
):
    capability = "eyJreview.aaa.bbb"
    mock_get_api_key.return_value = capability
    ctx, client = _context_with_response("indexed answer")
    ctx.request_context.lifespan_context.config = Config(
        oauth_enabled=True,
        oauth_issuer="https://auth.codealive.ai/",
        mcp_resource="https://mcp.codealive.ai/api",
        tool_api_resource="urn:codealive:tool-api",
        oauth_internal_client_id="codealive-mcp",
        oauth_internal_client_secret="test-secret",
    )

    result = await ask_codebase(ctx, question="How does startup work?")

    assert result == "indexed answer"
    mock_exchange.assert_not_awaited()
    posted = client.post.call_args
    assert posted.args[0] == "/api/tools/ask_codebase"
    assert posted.kwargs["headers"]["Authorization"] == f"Bearer {capability}"
    assert posted.kwargs["headers"]["X-CodeAlive-Tool"] == "ask_codebase"
    assert "eyJreview" not in repr(posted.kwargs["headers"]).replace(capability, "")


@pytest.mark.asyncio
@patch("tools.tool_api.get_access_token", return_value=None)
@patch("tools.tool_api.exchange_for_tool_token", new_callable=AsyncMock)
@patch("tools.tool_api.get_api_key_from_context")
async def test_ordinary_mcp_oauth_still_exchanges(
    mock_get_api_key,
    mock_exchange,
    _mock_access,
):
    mock_get_api_key.return_value = "header.payload.signature"
    mock_exchange.return_value = "tool-token"
    ctx, client = _context_with_response("done")
    ctx.request_context.lifespan_context.config = Config(
        oauth_enabled=True,
        oauth_issuer="https://auth.codealive.ai/",
        mcp_resource="https://mcp.codealive.ai/api",
        tool_api_resource="urn:codealive:tool-api",
        oauth_internal_client_id="codealive-mcp",
        oauth_internal_client_secret="test-secret",
    )
    ctx.request_context.lifespan_context.tool_token_cache = MagicMock()

    result = await call_tool_api(ctx, "chat", {"question": "hello"})

    assert result == "done"
    mock_exchange.assert_awaited_once()
    assert client.post.call_args.kwargs["headers"]["Authorization"] == "Bearer tool-token"


@pytest.mark.asyncio
@patch("tools.tool_api.get_api_key_from_context")
async def test_api_key_ask_codebase_forwards_without_exchange(mock_get_api_key):
    mock_get_api_key.return_value = LEGACY_API_KEY
    ctx, client = _context_with_response("ok")

    result = await ask_codebase(ctx, question="What owns checkout?")

    assert result == "ok"
    assert client.post.call_args.args[0] == "/api/tools/ask_codebase"
    assert client.post.call_args.kwargs["headers"]["Authorization"] == f"Bearer {LEGACY_API_KEY}"
    assert client.post.call_args.kwargs["json"]["question"] == "What owns checkout?"
