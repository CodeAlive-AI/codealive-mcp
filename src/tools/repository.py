"""Tool API v3 repository context tools."""

from typing import Annotated, Optional

from fastmcp import Context
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api, require_text


async def get_repository_ontology(
    ctx: Context,
    data_source: Annotated[
        Optional[str],
        Field(description="One repository name or id returned by get_data_sources."),
    ] = None,
) -> ToolApiResult:
    """Return ontology and orientation context for exactly one repository."""
    return await call_tool_api(ctx, "get_repository_ontology", {
        "data_source": data_source,
    }, action_label="get repository ontology")


async def get_file_tree(
    ctx: Context,
    data_source: Annotated[
        Optional[str],
        Field(description="One repository name or id returned by get_data_sources."),
    ] = None,
    path: Annotated[Optional[str], Field(description="Repository-relative directory path; omit for root.")] = None,
    max_depth: Annotated[Optional[int], Field(ge=1, le=8, description="Tree traversal depth (1-8).")] = None,
    max_nodes: Annotated[Optional[int], Field(ge=1, le=300, description="Maximum tree nodes (1-300).")] = None,
    output_depth: Annotated[Optional[int], Field(description="Optional render-only depth cap.")] = None,
) -> ToolApiResult:
    """Return a bounded file tree for exactly one repository."""
    return await call_tool_api(ctx, "get_file_tree", {
        "data_source": data_source,
        "path": path,
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "output_depth": output_depth,
    }, action_label="get file tree")


async def read_file(
    ctx: Context,
    path: Annotated[str, Field(min_length=1, description="Safe repository-relative file path.")],
    data_source: Annotated[
        Optional[str],
        Field(description="One repository name or id returned by get_data_sources."),
    ] = None,
    start_line: Annotated[Optional[int], Field(ge=1, description="Optional one-based start line.")] = None,
    end_line: Annotated[
        Optional[int],
        Field(ge=1, description="Optional one-based end line; at most 1000 lines per call."),
    ] = None,
) -> ToolApiResult:
    """Read a safe repository-relative file path from exactly one repository."""
    require_text(path, "read_file", "path")
    return await call_tool_api(ctx, "read_file", {
        "data_source": data_source,
        "path": path,
        "start_line": start_line,
        "end_line": end_line,
    }, action_label="read file")
