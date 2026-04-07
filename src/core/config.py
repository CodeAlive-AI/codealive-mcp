"""Configuration management for CodeAlive MCP server."""

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

# Request timeout in seconds (5 minutes)
REQUEST_TIMEOUT_SECONDS = 300.0


def normalize_base_url(base_url: Optional[str]) -> str:
    """Normalize a CodeAlive base URL to the deployment origin.

    Accepts both deployment origins and URLs that already end with `/api`.
    """
    raw = (base_url or "https://app.codealive.ai").strip()
    if not raw:
        raw = "https://app.codealive.ai"

    if "://" not in raw:
        normalized = raw.rstrip("/")
        if normalized.endswith("/api"):
            normalized = normalized[:-4]
        return normalized

    parts = urlsplit(raw)
    path = parts.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4]

    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment)).rstrip("/")


@dataclass
class Config:
    """Server configuration."""

    api_key: Optional[str] = None
    base_url: str = "https://app.codealive.ai"
    transport_mode: str = "stdio"
    verify_ssl: bool = True
    debug_mode: bool = False

    @classmethod
    def from_environment(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            api_key=os.environ.get("CODEALIVE_API_KEY"),
            base_url=normalize_base_url(os.environ.get("CODEALIVE_BASE_URL", "https://app.codealive.ai")),
            transport_mode=os.environ.get("TRANSPORT_MODE", "stdio"),
            verify_ssl=not os.environ.get("CODEALIVE_IGNORE_SSL", "").lower() in ["true", "1", "yes"],
            debug_mode=os.environ.get("DEBUG_MODE", "").lower() in ["true", "1", "yes"],
        )
