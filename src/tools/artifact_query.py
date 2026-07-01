"""Tool API v3 ArtifactQuery tools."""

from typing import Optional, Union

from fastmcp import Context

from .tool_api import call_tool_api, normalize_optional_list, require_text


async def get_artifact_query_schema(
    ctx: Context,
    entity: Optional[str] = None,
    include_examples: bool = True,
) -> str:
    """Return the ArtifactQuery v1 schema, fields, operators, and examples."""
    return await call_tool_api(ctx, "get_artifact_query_schema", {
        "entity": entity,
        "include_examples": include_examples,
    }, action_label="get artifact query schema")


async def query_artifact_metadata(
    ctx: Context,
    statement: str,
    data_sources: Optional[Union[str, list[str]]] = None,
) -> str:
    """Execute one bounded ArtifactQuery metadata statement."""
    require_text(statement, "query_artifact_metadata", "statement")
    return await call_tool_api(ctx, "query_artifact_metadata", {
        "statement": statement,
        "data_sources": normalize_optional_list(data_sources),
    }, action_label="query artifact metadata")
