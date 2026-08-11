"""Advertise the review-profile catalog without changing public MCP tools.

Uses FastMCP's on_list_tools hook. Authorization still belongs to Web Server.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import Tool
from mcp import types as mt

from core.config import Config
from core.review_catalog import advertised_tool_names


class ReviewToolCatalogMiddleware(Middleware):
    """Filter tools/list to the credential class's deterministic catalog."""

    def __init__(self, config: Config | None = None):
        self._config = config

    def _config_now(self) -> Config:
        return self._config or Config.from_environment()

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        tools = await call_next(context)
        config = self._config_now()
        allowed = advertised_tool_names(
            get_access_token(),
            tool_api_resource=config.tool_api_resource,
        )
        by_name = {tool.name: tool for tool in tools}
        return [by_name[name] for name in allowed if name in by_name]
