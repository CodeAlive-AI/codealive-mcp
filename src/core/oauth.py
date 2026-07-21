"""OAuth resource-server validation and downstream token exchange."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.http import HostOriginGuardMiddleware
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from .config import Config, validate_oauth_urls

_OBJECT_ID = re.compile(r"^[0-9a-fA-F]{24}$")
_ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
_TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
_LEGACY_API_KEY = re.compile(r"^ca_[0-9]{10,16}_[A-Za-z0-9_-]{43}$")


def is_jwt_shaped(token: str) -> bool:
    """Distinguish OAuth JWTs from opaque legacy API keys without decoding claims."""
    return token.count(".") == 2


def is_legacy_api_key(token: str) -> bool:
    """Recognize the one historic credential grammar; everything else fails as OAuth."""
    return _LEGACY_API_KEY.fullmatch(token) is not None


def is_oauth_credential(token: str) -> bool:
    return not is_legacy_api_key(token)


def _bearer_auth_parameters(challenge: str) -> list[tuple[str, str]]:
    """Split server-generated Bearer parameters without regex backtracking."""
    value = challenge.strip()
    if not value.lower().startswith("bearer"):
        return []
    value = value[6:].lstrip()
    parameters: list[tuple[str, str]] = []
    start = 0
    quoted = False
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
        elif quoted and character == "\\":
            escaped = True
        elif character == '"':
            quoted = not quoted
        elif character == "," and not quoted:
            segment = value[start:index].strip()
            name, separator, _ = segment.partition("=")
            if separator and name.strip():
                parameters.append((name.strip().lower(), segment))
            start = index + 1

    segment = value[start:].strip()
    name, separator, _ = segment.partition("=")
    if separator and name.strip():
        parameters.append((name.strip().lower(), segment))
    return parameters


class CodeAliveTokenVerifier(TokenVerifier):
    """Accept legacy opaque API keys or strictly validate CodeAlive MCP JWTs."""

    def __init__(self, config: Config):
        super().__init__(required_scopes=["mcp:tools"])
        self._config = config
        self._jwt = JWTVerifier(
            jwks_uri=urljoin(config.oauth_issuer, "connect/jwks"),
            issuer=config.oauth_issuer,
            audience=config.mcp_resource,
            algorithm="RS256",
            required_scopes=None,
        )

    @property
    def scopes_supported(self) -> list[str]:
        return ["mcp:tools"]

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 16_384:
            return None
        if is_legacy_api_key(token):
            # Legacy API keys are opaque and authoritatively validated by the Tool API.
            credential_id = hashlib.sha256(token.encode()).hexdigest()
            return AccessToken(
                token=token,
                client_id="legacy-api-key",
                scopes=["mcp:tools"],
                subject=f"legacy:{credential_id}",
            )

        if not is_jwt_shaped(token):
            return None
        access = await self._jwt.verify_token(token)
        if access is None:
            return None
        claims = access.claims or {}
        audience = claims.get("aud")
        exact_audience = audience == self._config.mcp_resource or audience == [self._config.mcp_resource]
        if not exact_audience:
            return None
        if set(access.scopes or []) != {"mcp:tools"}:
            return None
        required_string_claims = ("sub", "organisation_id", "mcp_connection_id", "client_id")
        if any(not isinstance(claims.get(name), str) or not claims[name] for name in required_string_claims):
            return None
        if access.client_id is not None and access.client_id != claims["client_id"]:
            return None
        if not _OBJECT_ID.fullmatch(claims["sub"]) or not _OBJECT_ID.fullmatch(claims["organisation_id"]) or not _OBJECT_ID.fullmatch(claims["mcp_connection_id"]):
            return None
        # The MCP SDK binds stateful transport sessions to subject/client/issuer.
        # Include the connection in the subject so two grants for the same User/client
        # cannot reuse one another's transport continuity id.
        return AccessToken(
            token=access.token,
            client_id=access.client_id,
            scopes=access.scopes,
            expires_at=access.expires_at,
            claims=claims,
            subject=f"{claims['sub']}:{claims['mcp_connection_id']}",
        )


class OAuthChallengeMiddleware:
    """Add the RFC 9728 challenge attributes required by MCP clients."""

    def __init__(self, app, *, resource_path: str, metadata_url: str):
        self.app = app
        self.resource_path = resource_path
        self.metadata_url = metadata_url

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") != self.resource_path:
            return await self.app(scope, receive, send)

        async def send_with_challenge(message):
            if message.get("type") == "http.response.start" and message.get("status") in {401, 403}:
                status = message["status"]
                headers = []
                existing_challenge = None
                for key, value in message.get("headers", []):
                    if key.lower() == b"www-authenticate":
                        existing_challenge = value.decode("latin-1")
                    else:
                        headers.append((key, value))

                # FastMCP supplies error/error_description for rejected OAuth tokens.
                # Preserve those signals so clients know when to discard credentials,
                # then add the MCP discovery attributes missing from its challenge.
                preserved_attributes: list[str] = []
                if existing_challenge:
                    for name, parameter in _bearer_auth_parameters(
                        existing_challenge
                    ):
                        if name not in {
                            "realm",
                            "resource_metadata",
                            "scope",
                        }:
                            preserved_attributes.append(parameter)

                attributes = [
                    'realm="codealive-mcp"',
                    f'resource_metadata="{self.metadata_url}"',
                    'scope="mcp:tools"',
                    *preserved_attributes,
                ]
                if status == 403 and not any(
                    attribute.lower().startswith("error=")
                    for attribute in preserved_attributes
                ):
                    attributes.append('error="insufficient_scope"')
                challenge = f"Bearer {', '.join(attributes)}"
                headers.append((b"www-authenticate", challenge.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_challenge)


class MetadataAwareHostOriginGuardMiddleware:
    """Keep Host/Origin protection while allowing public metadata discovery."""

    def __init__(
        self,
        app,
        *,
        metadata_path: str,
        allowed_hosts: list[str] | None,
        allowed_origins: list[str] | None,
    ):
        self.metadata_path = metadata_path
        self.guard = HostOriginGuardMiddleware(
            app,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") == "http"
            and scope.get("path") == self.metadata_path
            and scope.get("method") in {"GET", "OPTIONS"}
        ):
            # Metadata is public and contains only configured identifiers. Bypass
            # Origin validation for this path, but retain the upstream Host check
            # so DNS-rebinding protection remains active.
            scope = {
                **scope,
                "headers": [
                    (key, value)
                    for key, value in scope.get("headers", [])
                    if key.lower() != b"origin"
                ],
            }
        await self.guard(scope, receive, send)


class CodeAliveRemoteAuthProvider(RemoteAuthProvider):
    def __init__(self, config: Config, base_url: str, resource_path: str):
        super().__init__(
            token_verifier=CodeAliveTokenVerifier(config),
            authorization_servers=[config.oauth_issuer],
            base_url=base_url,
            resource_base_url=base_url,
            scopes_supported=["mcp:tools"],
            resource_name="CodeAlive MCP",
        )
        self._config = config
        self._resource_path = resource_path
        self._metadata_path = f"/.well-known/oauth-protected-resource{resource_path}"
        self._metadata_url = f"{base_url.rstrip('/')}{self._metadata_path}"

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        self.set_mcp_path(mcp_path)

        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

        async def protected_resource_metadata(request: Request) -> Response:
            if request.method == "OPTIONS":
                return Response(status_code=204, headers=cors_headers)
            return JSONResponse(
                {
                    "resource": self._config.mcp_resource,
                    "authorization_servers": [self._config.oauth_issuer],
                    "scopes_supported": ["mcp:tools"],
                    "bearer_methods_supported": ["header"],
                },
                headers={
                    "Cache-Control": "public, max-age=300",
                    **cors_headers,
                },
            )

        return [
            Route(
                self._metadata_path,
                protected_resource_metadata,
                methods=["GET", "OPTIONS"],
            )
        ]

    def get_middleware(self) -> list:
        return [
            *super().get_middleware(),
            Middleware(
                OAuthChallengeMiddleware,
                resource_path=self._resource_path,
                metadata_url=self._metadata_url,
            ),
        ]


def build_oauth_provider(config: Config) -> RemoteAuthProvider:
    validate_oauth_urls(config.oauth_issuer, config.mcp_resource)
    resource = urlsplit(config.mcp_resource)
    base_url = urlunsplit((resource.scheme, resource.netloc, "", "", ""))
    return CodeAliveRemoteAuthProvider(config, base_url, resource.path)


class ToolTokenExchangeCache:
    """Small in-memory, per-process cache with concurrent exchange coalescing."""

    def __init__(self, maximum_entries: int = 512):
        self._maximum_entries = maximum_entries
        self._entries: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._inflight: dict[str, tuple[asyncio.Task[tuple[str, float]], int]] = {}
        self._generation = 0
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Awaitable[tuple[str, float]]],
    ) -> str:
        now = time.monotonic()
        async with self._lock:
            cached = self._entries.get(key)
            if cached is not None and cached[1] > now:
                self._entries.move_to_end(key)
                return cached[0]
            if cached is not None:
                self._entries.pop(key, None)
            generation = self._generation
            inflight = self._inflight.get(key)
            if inflight is None:
                task = asyncio.create_task(
                    self._run_factory(key, generation, factory)
                )
                self._inflight[key] = (task, generation)
            else:
                task, generation = inflight

        token, _ = await asyncio.shield(task)
        return token

    async def _run_factory(
        self,
        key: str,
        generation: int,
        factory: Callable[[], Awaitable[tuple[str, float]]],
    ) -> tuple[str, float]:
        task = asyncio.current_task()
        try:
            token, cache_until = await factory()
            if cache_until <= time.monotonic():
                return token, cache_until

            async with self._lock:
                if (
                    self._generation == generation
                    and self._inflight.get(key) == (task, generation)
                ):
                    self._entries[key] = (token, cache_until)
                    self._entries.move_to_end(key)
                    while len(self._entries) > self._maximum_entries:
                        self._entries.popitem(last=False)
            return token, cache_until
        finally:
            async with self._lock:
                if self._inflight.get(key) == (task, generation):
                    self._inflight.pop(key, None)

    async def invalidate(self, key: str, rejected_token: str | None = None) -> None:
        """Remove a rejected token without disturbing a newer shared exchange."""
        async with self._lock:
            if rejected_token is not None:
                cached = self._entries.get(key)
                if cached is not None and cached[0] == rejected_token:
                    self._entries.pop(key, None)
                return

            # Administrative invalidation is stronger than a downstream 401: it
            # prevents a pre-invalidation exchange from repopulating the cache.
            self._generation += 1
            self._entries.pop(key, None)
            self._inflight.pop(key, None)


def _tool_token_exchange_cache_key(config: Config, subject_token: str) -> str:
    return hashlib.sha256(
        "\0".join((
            subject_token,
            config.oauth_internal_client_id,
            config.tool_api_resource,
            "mcp:tools",
        )).encode()
    ).hexdigest()


async def invalidate_tool_token_exchange(
    cache: ToolTokenExchangeCache | None,
    config: Config,
    subject_token: str,
    rejected_token: str,
) -> None:
    """Evict the downstream token derived from one inbound MCP token."""
    if cache is not None:
        await cache.invalidate(
            _tool_token_exchange_cache_key(config, subject_token),
            rejected_token,
        )


async def exchange_for_tool_token(
    client: httpx.AsyncClient,
    config: Config,
    subject_token: str,
    cache: ToolTokenExchangeCache | None = None,
) -> str:
    """Exchange an inbound MCP token; the subject token is never sent to Tool API."""
    if not config.oauth_internal_client_secret:
        raise ValueError("OAuth token exchange is not configured")
    async def request_token() -> tuple[str, float]:
        response = await client.post(
            urljoin(config.oauth_issuer, "connect/token"),
            data={
                "grant_type": _TOKEN_EXCHANGE_GRANT,
                "subject_token": subject_token,
                "subject_token_type": _ACCESS_TOKEN_TYPE,
                "requested_token_type": _ACCESS_TOKEN_TYPE,
                "resource": config.tool_api_resource,
                "scope": "mcp:tools",
            },
            auth=(config.oauth_internal_client_id, config.oauth_internal_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(token, str) or not token:
            raise ValueError("OAuth token exchange returned no access token")
        cache_seconds = max(0.0, float(expires_in) - 30.0) if isinstance(expires_in, (int, float)) else 0.0
        return token, time.monotonic() + cache_seconds

    if cache is None:
        token, _ = await request_token()
        return token
    cache_key = _tool_token_exchange_cache_key(config, subject_token)
    return await cache.get_or_create(cache_key, request_token)
