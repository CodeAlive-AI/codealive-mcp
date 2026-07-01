"""Tool API v3 artifact fetch."""

from typing import Optional, Union

from fastmcp import Context
from fastmcp.exceptions import ToolError

from .tool_api import call_tool_api, normalize_optional_list


async def fetch_artifacts(
    ctx: Context,
    identifiers: Union[str, list[str]],
    data_source: Optional[str] = None,
) -> str:
    """Fetch full artifact content for identifiers returned by search tools."""
    normalized = normalize_optional_list(identifiers)
    if not normalized:
        raise ToolError("[fetch_artifacts] identifiers is required.")
    if len(normalized) > 50:
        raise ToolError("[fetch_artifacts] Maximum 50 identifiers per request.")

    return await call_tool_api(ctx, "fetch_artifacts", {
        "identifiers": normalized,
        "data_source": data_source,
    }, action_label="fetch artifacts")
