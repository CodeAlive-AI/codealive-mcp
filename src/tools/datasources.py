"""Tool API v3 data-source discovery."""

from typing import Annotated, Optional

from fastmcp import Context
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api


async def get_data_sources(
    ctx: Context,
    query: Annotated[
        Optional[str],
        Field(description="Optional relevance question used to rank visible data sources."),
    ] = None,
    ready_only: bool = True,
) -> ToolApiResult:
    """List visible repositories and workspaces.

    Use the returned `name` value for `data_sources` or `data_source` in other
    v3 tools unless automation needs a stable `id`.
    """
    return await call_tool_api(ctx, "get_data_sources", {
        "query": query,
        "ready_only": ready_only,
    }, action_label="list data sources")
