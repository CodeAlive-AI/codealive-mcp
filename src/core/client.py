"""API client management for CodeAlive MCP server."""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_http_headers
from loguru import logger

from .config import Config, REQUEST_TIMEOUT_SECONDS


@dataclass
class CodeAliveContext:
    """Context for CodeAlive API access."""
    client: httpx.AsyncClient
    api_key: str
    base_url: str


# Module-level readiness state for the /ready endpoint.
# Set to True once the lifespan context (httpx client) is initialized,
# reset to False on shutdown.
_server_ready: bool = False


def get_api_key_from_context(ctx: Context) -> str:
    """Extract API key based on transport mode."""
    try:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")

        if auth_header and auth_header.startswith("Bearer "):
            # HTTP mode with Bearer token
            return auth_header[7:]
        elif headers:
            # HTTP mode but no/invalid Authorization header
            raise ValueError("HTTP mode: Authorization: Bearer <api-key> header required")
        else:
            # STDIO mode - no HTTP headers available
            api_key = os.environ.get("CODEALIVE_API_KEY", "")
            if not api_key:
                raise ValueError("STDIO mode: CODEALIVE_API_KEY environment variable required")
            return api_key
    except Exception:
        # Fallback to STDIO mode if header access fails
        api_key = os.environ.get("CODEALIVE_API_KEY", "")
        if not api_key:
            raise ValueError("STDIO mode: CODEALIVE_API_KEY environment variable required")
        return api_key


@asynccontextmanager
async def codealive_lifespan(server: FastMCP) -> AsyncIterator[CodeAliveContext]:
    """Manage CodeAlive API client lifecycle."""
    config = Config.from_environment()

    logger.info(
        "CodeAlive MCP Server starting in {mode} mode",
        mode=config.transport_mode.upper(),
        base_url=config.base_url,
        ssl_verification=config.verify_ssl,
    )

    # Create client with explicit connection pool limits
    pool_limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)

    if config.transport_mode == "stdio":
        # STDIO mode: create client with fixed API key
        client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=config.verify_ssl,
            limits=pool_limits,
        )
    else:
        # HTTP mode: create base client without authentication headers
        client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=config.verify_ssl,
            limits=pool_limits,
        )

    global _server_ready
    try:
        _server_ready = True
        yield CodeAliveContext(
            client=client,
            api_key="",  # Will be set per-request in HTTP mode
            base_url=config.base_url
        )
    finally:
        _server_ready = False
        await client.aclose()