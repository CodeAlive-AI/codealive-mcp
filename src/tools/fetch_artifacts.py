"""Tool API v3 artifact fetch."""

from typing import Annotated, Optional, Union

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api, normalize_optional_list


async def fetch_artifacts(
    ctx: Context,
    identifiers: Annotated[
        Union[
            str,
            Annotated[list[str], Field(min_length=1, max_length=50)],
        ],
        Field(description="Artifact identifiers returned by search, read, or relationship tools."),
    ],
    data_source: Annotated[
        Optional[str],
        Field(description="Optional repository name or id used to disambiguate identifiers."),
    ] = None,
) -> ToolApiResult:
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
