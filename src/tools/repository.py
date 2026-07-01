"""Tool API v3 repository context tools."""

from typing import Optional

from fastmcp import Context

from .tool_api import call_tool_api, require_text


async def get_repository_ontology(ctx: Context, data_source: Optional[str] = None) -> str:
    """Return ontology and orientation context for exactly one repository."""
    return await call_tool_api(ctx, "get_repository_ontology", {
        "data_source": data_source,
    }, action_label="get repository ontology")


async def get_file_tree(
    ctx: Context,
    data_source: Optional[str] = None,
    path: Optional[str] = None,
    max_depth: Optional[int] = None,
    max_nodes: Optional[int] = None,
    output_depth: Optional[int] = None,
) -> str:
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
    path: str,
    data_source: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Read a safe repository-relative file path from exactly one repository."""
    require_text(path, "read_file", "path")
    return await call_tool_api(ctx, "read_file", {
        "data_source": data_source,
        "path": path,
        "start_line": start_line,
        "end_line": end_line,
    }, action_label="read file")
