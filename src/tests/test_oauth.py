"""OAuth 2.1 resource-server and token-exchange contracts."""

import asyncio

from unittest.mock import AsyncMock

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken
from starlette.middleware import Middleware
from starlette.responses import Response

from core.config import Config
from core.oauth import (
    CodeAliveTokenVerifier,
    MetadataAwareHostOriginGuardMiddleware,
    OAuthChallengeMiddleware,
    ToolTokenExchangeCache,
    build_oauth_provider,
    exchange_for_tool_token,
)


def _config(**changes) -> Config:
    values = {
        "oauth_issuer": "https://auth.codealive.ai/",
        "mcp_resource": "https://mcp.codealive.ai/api",
        "tool_api_resource": "urn:codealive:tool-api",
        "oauth_internal_client_id": "codealive-mcp",
        "oauth_internal_client_secret": "test-secret",
    }
    values.update(changes)
    return Config(**values)


@pytest.mark.parametrize("issuer", [
    "http://auth.codealive.ai",
    "https://user@auth.codealive.ai",
    "https://auth.codealive.ai/tenant",
    "https://auth.codealive.ai",
])
def test_oauth_provider_rejects_noncanonical_issuer(issuer):
    with pytest.raises(ValueError, match="OAUTH_ISSUER"):
        build_oauth_provider(_config(oauth_issuer=issuer))


@pytest.mark.parametrize("resource", [
    "http://mcp.codealive.ai/api",
    "https://user@mcp.codealive.ai/api",
    "https://mcp.codealive.ai",
    "https://mcp.codealive.ai/api?tenant=x",
    "https://mcp.codealive.ai/api/",
])
def test_oauth_provider_rejects_noncanonical_resource(resource):
    with pytest.raises(ValueError, match="MCP_RESOURCE"):
        build_oauth_provider(_config(mcp_resource=resource))


def test_oauth_provider_allows_loopback_http_resource_for_local_development():
    provider = build_oauth_provider(_config(mcp_resource="http://127.0.0.1:8000/api"))
    assert provider is not None


def test_oauth_enabled_rejects_same_mcp_and_tool_api_resource():
    with pytest.raises(ValueError, match="must be distinct"):
        _config(
            oauth_enabled=True,
            tool_api_resource="https://MCP.codealive.ai/api",
        )


@pytest.mark.parametrize("tool_resource", ["", "relative/resource", " urn:codealive:tool-api"])
def test_oauth_enabled_rejects_non_absolute_tool_api_resource(tool_resource):
    with pytest.raises(ValueError, match="TOOL_API_RESOURCE"):
        _config(oauth_enabled=True, tool_api_resource=tool_resource)


@pytest.mark.parametrize("client_id", ["", "   "])
def test_oauth_enabled_rejects_empty_internal_client_id(client_id):
    with pytest.raises(ValueError, match="INTERNAL_CLIENT_ID"):
        _config(oauth_enabled=True, oauth_internal_client_id=client_id)


def test_oauth_environment_does_not_silently_rewrite_tool_api_audience(monkeypatch):
    monkeypatch.setenv("CODEALIVE_MCP_OAUTH_ENABLED", "true")
    monkeypatch.setenv("CODEALIVE_TOOL_API_RESOURCE", "https://tools.example/api/")

    config = Config.from_environment()

    assert config.tool_api_resource == "https://tools.example/api/"


@pytest.mark.asyncio
async def test_protected_resource_metadata_and_challenge_are_exact():
    mcp = FastMCP("OAuth test", auth=build_oauth_provider(_config()))
    app = mcp.http_app(path="/api", stateless_http=True)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://mcp.codealive.ai",
        ) as client:
            metadata = await client.get("/.well-known/oauth-protected-resource/api")
            unauthorized = await client.post("/api", json={})

    assert metadata.status_code == 200
    assert metadata.headers["cache-control"] == "public, max-age=300"
    assert metadata.headers["access-control-allow-origin"] == "*"
    assert metadata.json() == {
        "resource": "https://mcp.codealive.ai/api",
        "authorization_servers": ["https://auth.codealive.ai/"],
        "scopes_supported": ["mcp:tools"],
        "bearer_methods_supported": ["header"],
    }
    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"] == (
        'Bearer realm="codealive-mcp", '
        'resource_metadata="https://mcp.codealive.ai/.well-known/oauth-protected-resource/api", '
        'scope="mcp:tools"'
    )


@pytest.mark.asyncio
async def test_protected_resource_metadata_supports_cors_preflight():
    mcp = FastMCP("OAuth test", auth=build_oauth_provider(_config()))
    app = mcp.http_app(
        path="/api",
        stateless_http=True,
        host_origin_protection=False,
        middleware=[
            Middleware(
                MetadataAwareHostOriginGuardMiddleware,
                metadata_path="/.well-known/oauth-protected-resource/api",
                allowed_hosts=["mcp.codealive.ai"],
                allowed_origins=["https://mcp.codealive.ai"],
            )
        ],
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://mcp.codealive.ai",
        ) as client:
            response = await client.options(
                "/.well-known/oauth-protected-resource/api",
                headers={
                    "Origin": "https://inspector.example",
                    "Access-Control-Request-Method": "GET",
                },
            )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert "GET" in response.headers["access-control-allow-methods"]


@pytest.mark.asyncio
async def test_metadata_cors_exception_does_not_weaken_mcp_origin_or_host_guard():
    mcp = FastMCP("OAuth test", auth=build_oauth_provider(_config()))
    app = mcp.http_app(
        path="/api",
        stateless_http=True,
        host_origin_protection=False,
        middleware=[
            Middleware(
                MetadataAwareHostOriginGuardMiddleware,
                metadata_path="/.well-known/oauth-protected-resource/api",
                allowed_hosts=["mcp.codealive.ai"],
                allowed_origins=["https://mcp.codealive.ai"],
            )
        ],
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="https://mcp.codealive.ai",
        ) as client:
            rejected_origin = await client.post(
                "/api",
                headers={"Origin": "https://attacker.example"},
                json={},
            )
            rejected_host = await client.get(
                "/.well-known/oauth-protected-resource/api",
                headers={
                    "Host": "attacker.example",
                    "Origin": "https://inspector.example",
                },
            )

    assert rejected_origin.status_code == 403
    assert rejected_host.status_code == 421


@pytest.mark.asyncio
async def test_challenge_preserves_invalid_token_details():
    async def rejected_app(scope, receive, send):
        response = Response(
            status_code=401,
            headers={
                "WWW-Authenticate": (
                    'Bearer error="invalid_token", '
                    'error_description="The access token expired"'
                )
            },
        )
        await response(scope, receive, send)

    app = OAuthChallengeMiddleware(
        rejected_app,
        resource_path="/api",
        metadata_url=(
            "https://mcp.codealive.ai/"
            ".well-known/oauth-protected-resource/api"
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://mcp.codealive.ai",
    ) as client:
        response = await client.post("/api")

    challenge = response.headers["www-authenticate"]
    assert 'error="invalid_token"' in challenge
    assert 'error_description="The access token expired"' in challenge
    assert 'resource_metadata="https://mcp.codealive.ai/' in challenge
    assert 'scope="mcp:tools"' in challenge


@pytest.mark.asyncio
async def test_verifier_rejects_extra_audience_and_missing_binding_claims():
    verifier = CodeAliveTokenVerifier(_config())
    verifier._jwt.verify_token = AsyncMock(return_value=AccessToken(
        token="header.payload.signature",
        client_id="client",
        scopes=["mcp:tools"],
        claims={
            "aud": ["https://mcp.codealive.ai/api", "https://other.example"],
            "sub": "0123456789abcdef01234567",
            "organisation_id": "1123456789abcdef01234567",
            "mcp_connection_id": "2123456789abcdef01234567",
            "client_id": "client",
        },
    ))
    assert await verifier.verify_token("header.payload.signature") is None

    verifier._jwt.verify_token.return_value.claims = {
        "aud": "https://mcp.codealive.ai/api",
        "sub": "0123456789abcdef01234567",
        "organisation_id": "1123456789abcdef01234567",
        "mcp_connection_id": "2123456789abcdef01234567",
        "client_id": "client",
    }
    verified = await verifier.verify_token("header.payload.signature")
    assert verified is not None
    assert verified.subject == "0123456789abcdef01234567:2123456789abcdef01234567"

    verifier._jwt.verify_token.return_value.claims = {"aud": "https://mcp.codealive.ai/api"}
    assert await verifier.verify_token("header.payload.signature") is None


@pytest.mark.asyncio
async def test_opaque_legacy_api_key_remains_supported():
    access = await CodeAliveTokenVerifier(_config()).verify_token(
        "ca_1720000000000_0123456789abcdef0123456789abcdef0123456789a")
    assert access is not None
    assert access.client_id == "legacy-api-key"
    assert access.scopes == ["mcp:tools"]


@pytest.mark.asyncio
async def test_malformed_bearer_never_falls_back_to_legacy_api_key():
    verifier = CodeAliveTokenVerifier(_config())
    verifier._jwt.verify_token = AsyncMock()

    assert await verifier.verify_token("arbitrary-bearer") is None
    assert await verifier.verify_token("header.payload") is None
    verifier._jwt.verify_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_token_exchange_uses_confidential_client_and_exact_resources():
    captured: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"access_token": "tool-token"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        token = await exchange_for_tool_token(client, _config(), "mcp-subject-token")

    assert token == "tool-token"
    assert captured is not None
    assert str(captured.url) == "https://auth.codealive.ai/connect/token"
    body = captured.content.decode()
    assert "subject_token=mcp-subject-token" in body
    assert "resource=urn%3Acodealive%3Atool-api" in body
    assert captured.headers["authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_token_exchange_cache_coalesces_concurrent_calls_without_storing_subject_token():
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return httpx.Response(200, json={"access_token": "tool-token", "expires_in": 300})

    cache = ToolTokenExchangeCache()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        tokens = await asyncio.gather(*[
            exchange_for_tool_token(client, _config(), "mcp-subject-token", cache)
            for _ in range(5)
        ])
        repeated = await exchange_for_tool_token(client, _config(), "mcp-subject-token", cache)

    assert tokens == ["tool-token"] * 5
    assert repeated == "tool-token"
    assert calls == 1
    assert all("mcp-subject-token" not in key for key in cache._entries)


@pytest.mark.asyncio
async def test_token_exchange_cache_invalidation_does_not_restore_stale_inflight_value():
    cache = ToolTokenExchangeCache()
    stale_started = asyncio.Event()
    release_stale = asyncio.Event()

    async def stale_factory():
        stale_started.set()
        await release_stale.wait()
        return "stale-token", float("inf")

    stale = asyncio.create_task(cache.get_or_create("key", stale_factory))
    await stale_started.wait()
    await cache.invalidate("key")
    fresh = await cache.get_or_create(
        "key",
        lambda: asyncio.sleep(0, result=("fresh-token", float("inf"))),
    )
    release_stale.set()

    assert fresh == "fresh-token"
    assert await stale == "stale-token"
    assert await cache.get_or_create("key", stale_factory) == "fresh-token"


@pytest.mark.asyncio
async def test_token_exchange_cache_caller_cancellation_keeps_shared_exchange_alive():
    cache = ToolTokenExchangeCache()
    exchange_started = asyncio.Event()
    release_exchange = asyncio.Event()
    calls = 0

    async def factory():
        nonlocal calls
        calls += 1
        exchange_started.set()
        await release_exchange.wait()
        return "tool-token", float("inf")

    cancelled_caller = asyncio.create_task(cache.get_or_create("key", factory))
    await exchange_started.wait()
    cancelled_caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled_caller

    surviving_caller = asyncio.create_task(cache.get_or_create("key", factory))
    release_exchange.set()

    assert await surviving_caller == "tool-token"
    assert await cache.get_or_create("key", factory) == "tool-token"
    assert calls == 1


@pytest.mark.asyncio
async def test_rejected_cached_token_does_not_cancel_fresh_shared_exchange():
    cache = ToolTokenExchangeCache()
    await cache.get_or_create(
        "key",
        lambda: asyncio.sleep(0, result=("rejected-token", float("inf"))),
    )
    await cache.invalidate("key", "rejected-token")

    fresh_started = asyncio.Event()
    release_fresh = asyncio.Event()
    calls = 0

    async def fresh_factory():
        nonlocal calls
        calls += 1
        fresh_started.set()
        await release_fresh.wait()
        return "fresh-token", float("inf")

    first_retry = asyncio.create_task(cache.get_or_create("key", fresh_factory))
    await fresh_started.wait()
    await cache.invalidate("key", "rejected-token")
    second_retry = asyncio.create_task(cache.get_or_create("key", fresh_factory))
    release_fresh.set()

    assert await first_retry == "fresh-token"
    assert await second_retry == "fresh-token"
    assert calls == 1


def test_oauth_enabled_treats_default_https_port_as_same_resource():
    with pytest.raises(ValueError, match="must be distinct"):
        _config(
            oauth_enabled=True,
            tool_api_resource="https://mcp.codealive.ai:443/api",
        )
