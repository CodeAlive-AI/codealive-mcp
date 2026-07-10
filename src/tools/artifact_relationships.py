"""Tool API v3 artifact relationship expansion."""

from typing import Annotated, Literal, Optional

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api, require_text


async def get_artifact_relationships(
    ctx: Context,
    identifier: Annotated[
        str,
        Field(
            min_length=1,
            description="Exact artifact identifier returned by a prior CodeAlive tool.",
        ),
    ],
    profile: Literal["calls_only", "inheritance_only", "all_relevant", "references_only"] = "calls_only",
    max_count_per_type: Annotated[
        int,
        Field(ge=1, le=1000, description="Maximum relationships per type (1-1000)."),
    ] = 50,
    data_source: Annotated[
        Optional[str],
        Field(description="Optional repository name or id used to disambiguate the identifier."),
    ] = None,
) -> ToolApiResult:
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
