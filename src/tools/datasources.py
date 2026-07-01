"""Tool API v3 data-source discovery."""

from typing import Optional

from fastmcp import Context

from .tool_api import call_tool_api


async def get_data_sources(
    ctx: Context,
    query: Optional[str] = None,
    ready_only: bool = True,
) -> str:
    """List visible repositories and workspaces.

    Use the returned `name` value for `data_sources` or `data_source` in other
    v3 tools unless automation needs a stable `id`.
    """
    return await call_tool_api(ctx, "get_data_sources", {
        "query": query,
        "ready_only": ready_only,
    }, action_label="list data sources")
