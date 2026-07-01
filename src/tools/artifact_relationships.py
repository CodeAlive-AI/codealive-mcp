"""Tool API v3 artifact relationship expansion."""

from typing import Literal, Optional

from fastmcp import Context
from fastmcp.exceptions import ToolError

from .tool_api import call_tool_api, require_text


async def get_artifact_relationships(
    ctx: Context,
    identifier: str,
    profile: Literal["CallsOnly", "InheritanceOnly", "AllRelevant", "ReferencesOnly"] = "CallsOnly",
    max_count_per_type: int = 50,
    data_source: Optional[str] = None,
) -> str:
    """Expand relationships around one exact artifact identifier.

    This is a graph expansion tool, not a search tool. Use identifiers returned
    by semantic_search, grep_search, fetch_artifacts, read_file, or prior
    relationship results.
    """
    tool_name = "get_artifact_relationships"
    require_text(identifier, tool_name, "identifier")
    if not (1 <= max_count_per_type <= 1000):
        raise ToolError(f"[{tool_name}] max_count_per_type must be between 1 and 1000.")

    return await call_tool_api(ctx, tool_name, {
        "identifier": identifier,
        "profile": profile,
        "max_count_per_type": max_count_per_type,
        "data_source": data_source,
    }, action_label="get artifact relationships")
