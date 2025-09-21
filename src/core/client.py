"""API client management for CodeAlive MCP server."""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_http_headers

from .config import Config


@dataclass
class CodeAliveContext:
    """Context for CodeAlive API access."""
    client: httpx.AsyncClient
    api_key: str
    base_url: str


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

    print(f"CodeAlive MCP Server starting in {config.transport_mode.upper()} mode:")
    if config.transport_mode == "stdio":
        print(f"  - API Key: {'*' * 5}{config.api_key[-5:] if config.api_key else 'Not set'}")
    else:
        print(f"  - API Keys: Extracted from Authorization headers per request")
    print(f"  - Base URL: {config.base_url}")
    print(f"  - SSL Verification: {'Enabled' if config.verify_ssl else 'Disabled'}")

    # Create client
    if config.transport_mode == "stdio":
        # STDIO mode: create client with fixed API key
        client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
            verify=config.verify_ssl,
        )
    else:
        # HTTP mode: create base client without authentication headers
        client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Content-Type": "application/json",
            },
            timeout=60.0,
            verify=config.verify_ssl,
        )

    try:
        yield CodeAliveContext(
            client=client,
            api_key="",  # Will be set per-request in HTTP mode
            base_url=config.base_url
        )
    finally:
        await client.aclose()