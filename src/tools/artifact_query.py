"""Tool API v3 ArtifactQuery tools."""

from typing import Annotated, Optional, Union

from fastmcp import Context
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api, normalize_optional_list, require_text


async def get_artifact_query_schema(
    ctx: Context,
    entity: Annotated[
        Optional[str],
        Field(description="Optional ArtifactQuery entity such as files or symbols."),
    ] = None,
    include_examples: bool = True,
) -> ToolApiResult:
    """Return the ArtifactQuery v1 schema, fields, operators, and examples."""
    return await call_tool_api(ctx, "get_artifact_query_schema", {
        "entity": entity,
        "include_examples": include_examples,
    }, action_label="get artifact query schema")


async def query_artifact_metadata(
    ctx: Context,
    statement: Annotated[str, Field(min_length=1, description="One bounded ArtifactQuery statement.")],
    data_sources: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository or workspace names returned by get_data_sources."),
    ] = None,
) -> ToolApiResult:
    """Execute one bounded ArtifactQuery metadata statement."""
    require_text(statement, "query_artifact_metadata", "statement")
    return await call_tool_api(ctx, "query_artifact_metadata", {
        "statement": statement,
        "data_sources": normalize_optional_list(data_sources),
    }, action_label="query artifact metadata")
