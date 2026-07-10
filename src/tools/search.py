"""Tool API v3 search tools."""

from typing import Annotated, Optional, Union

from fastmcp import Context
from fastmcp.exceptions import ToolError
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api, normalize_optional_list, require_text


def _validate_max_results(max_results: Optional[int], tool_name: str) -> None:
    if max_results is not None and not (1 <= max_results <= 500):
        raise ToolError(f"[{tool_name}] max_results must be between 1 and 500.")


async def semantic_search(
    ctx: Context,
    question: Annotated[
        str,
        Field(min_length=1, description="Natural-language question about indexed code."),
    ],
    data_sources: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository or workspace names returned by get_data_sources."),
    ] = None,
    paths: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository-relative path prefixes to include."),
    ] = None,
    extensions: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="File extensions to include, such as cs, ts, or py."),
    ] = None,
    max_results: Annotated[
        Optional[int],
        Field(ge=1, le=500, description="Maximum number of results (1-500)."),
    ] = None,
    exclude_markdown: bool = False,
) -> ToolApiResult:
    """Search indexed code by meaning using Tool API v3.

    `question` must be a natural-language English sentence. Use `data_sources`
    names returned by `get_data_sources`; use `id` only for automation or
    disambiguation. Returns backend-rendered agentic output directly.
    """
    tool_name = "semantic_search"
    require_text(question, tool_name, "question")
    _validate_max_results(max_results, tool_name)
    return await call_tool_api(ctx, tool_name, {
        "question": question,
        "data_sources": normalize_optional_list(data_sources),
        "paths": normalize_optional_list(paths),
        "extensions": normalize_optional_list(extensions),
        "max_results": max_results,
        "exclude_markdown": exclude_markdown,
    }, action_label="semantic search")


async def grep_search(
    ctx: Context,
    query: Annotated[
        str,
        Field(min_length=1, description="Exact literal text or regular expression to find."),
    ],
    data_sources: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository or workspace names returned by get_data_sources."),
    ] = None,
    paths: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository-relative path prefixes to include."),
    ] = None,
    extensions: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="File extensions to include, such as cs, ts, or py."),
    ] = None,
    max_results: Annotated[
        Optional[int],
        Field(ge=1, le=500, description="Maximum number of results (1-500)."),
    ] = None,
    exclude_markdown: bool = False,
    regex: bool = False,
) -> ToolApiResult:
    """Search indexed code by exact literal text or regex using Tool API v3."""
    tool_name = "grep_search"
    require_text(query, tool_name, "query")
    _validate_max_results(max_results, tool_name)
    return await call_tool_api(ctx, tool_name, {
        "query": query,
        "data_sources": normalize_optional_list(data_sources),
        "paths": normalize_optional_list(paths),
        "extensions": normalize_optional_list(extensions),
        "max_results": max_results,
        "exclude_markdown": exclude_markdown,
        "regex": regex,
    }, action_label="grep search")
