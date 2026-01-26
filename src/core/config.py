"""Configuration management for CodeAlive MCP server."""

import os
from dataclasses import dataclass
from typing import Optional

# Request timeout in seconds (5 minutes)
REQUEST_TIMEOUT_SECONDS = 300.0


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
            base_url=os.environ.get("CODEALIVE_BASE_URL", "https://app.codealive.ai"),
            transport_mode=os.environ.get("TRANSPORT_MODE", "stdio"),
            verify_ssl=not os.environ.get("CODEALIVE_IGNORE_SSL", "").lower() in ["true", "1", "yes"],
            debug_mode=os.environ.get("DEBUG_MODE", "").lower() in ["true", "1", "yes"],
        )