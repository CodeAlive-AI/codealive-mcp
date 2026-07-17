"""Configuration management for CodeAlive MCP server."""

import os
import ipaddress
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

# Request timeout in seconds (5 minutes)
REQUEST_TIMEOUT_SECONDS = 300.0


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_oauth_urls(issuer_value: str, resource_value: str) -> None:
    issuer = urlsplit(issuer_value)
    if (
        issuer.scheme != "https"
        or not issuer.netloc
        or issuer.username is not None
        or issuer.password is not None
        or issuer.path not in {"", "/"}
        or issuer.query
        or issuer.fragment
        or not issuer_value.endswith("/")
        or (issuer.hostname or "").endswith(".")
    ):
        raise ValueError("CODEALIVE_OAUTH_ISSUER must be a canonical HTTPS origin")

    resource = urlsplit(resource_value)
    secure = resource.scheme == "https" or (
        resource.scheme == "http" and _is_loopback_host(resource.hostname)
    )
    if (
        not secure
        or not resource.netloc
        or resource.username is not None
        or resource.password is not None
        or resource.path in {"", "/"}
        or resource.query
        or resource.fragment
        or resource_value.endswith("/")
        or (resource.hostname or "").endswith(".")
    ):
        raise ValueError("CODEALIVE_MCP_RESOURCE must be a canonical HTTPS URL with a path")


def _same_resource_identifier(left_value: str, right_value: str) -> bool:
    left = urlsplit(left_value)
    right = urlsplit(right_value)
    if left.scheme.lower() != right.scheme.lower():
        return False
    if left.netloc or right.netloc:
        left_port = left.port or (443 if left.scheme.lower() == "https" else 80 if left.scheme.lower() == "http" else None)
        right_port = right.port or (443 if right.scheme.lower() == "https" else 80 if right.scheme.lower() == "http" else None)
        return (
            left.hostname == right.hostname
            and left_port == right_port
            and left.username == right.username
            and left.password == right.password
            and left.path == right.path
            and left.query == right.query
            and left.fragment == right.fragment
        )
    return left.path == right.path and left.query == right.query and left.fragment == right.fragment


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
    oauth_enabled: bool = False
    oauth_issuer: str = "https://auth.codealive.ai/"
    mcp_resource: str = "https://mcp.codealive.ai/api"
    tool_api_resource: str = "urn:codealive:tool-api"
    oauth_internal_client_id: str = "codealive-mcp"
    oauth_internal_client_secret: Optional[str] = None

    def __post_init__(self) -> None:
        if self.oauth_enabled:
            validate_oauth_urls(self.oauth_issuer, self.mcp_resource)
            if _same_resource_identifier(self.mcp_resource, self.tool_api_resource):
                raise ValueError(
                    "CODEALIVE_MCP_RESOURCE and CODEALIVE_TOOL_API_RESOURCE must be distinct"
                )

    @classmethod
    def from_environment(cls) -> "Config":
        """Create config from environment variables."""
        return cls(
            api_key=os.environ.get("CODEALIVE_API_KEY"),
            base_url=normalize_base_url(os.environ.get("CODEALIVE_BASE_URL", "https://app.codealive.ai")),
            transport_mode=os.environ.get("TRANSPORT_MODE", "stdio"),
            verify_ssl=not os.environ.get("CODEALIVE_IGNORE_SSL", "").lower() in ["true", "1", "yes"],
            debug_mode=os.environ.get("DEBUG_MODE", "").lower() in ["true", "1", "yes"],
            oauth_enabled=os.environ.get("CODEALIVE_MCP_OAUTH_ENABLED", "false").lower() in ["true", "1", "yes"],
            oauth_issuer=os.environ.get("CODEALIVE_OAUTH_ISSUER", "https://auth.codealive.ai/"),
            mcp_resource=os.environ.get("CODEALIVE_MCP_RESOURCE", "https://mcp.codealive.ai/api"),
            tool_api_resource=os.environ.get("CODEALIVE_TOOL_API_RESOURCE", "urn:codealive:tool-api").rstrip("/"),
            oauth_internal_client_id=os.environ.get("CODEALIVE_OAUTH_INTERNAL_CLIENT_ID", "codealive-mcp"),
            oauth_internal_client_secret=os.environ.get("CODEALIVE_OAUTH_INTERNAL_CLIENT_SECRET"),
        )
