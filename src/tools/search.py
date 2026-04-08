"""Search tool implementations."""

import json
from typing import List, Optional, Sequence, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import (
    handle_api_error,
    normalize_data_source_names,
    transform_grep_response_to_json,
    transform_search_response_to_json,
)


def _normalize_optional_list(value: Optional[Union[str, List[str]]]) -> List[str]:
    """Normalize optional string-or-list inputs while preserving ordering."""
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [item for item in value if item]


def _validate_query(query: str, tool_name: str) -> Optional[str]:
    if query and query.strip():
        return None

    return json.dumps(
        {
            "error": (
                f"[{tool_name}] Query cannot be empty. Please provide a search term, "
                "pattern, function name, or description of the code you're looking for."
            )
        },
        separators=(",", ":"),
    )


def _validate_max_results(max_results: Optional[int], tool_name: str) -> Optional[str]:
    if max_results is None:
        return None
    if 1 <= max_results <= 500:
        return None

    return json.dumps(
        {"error": f"[{tool_name}] max_results must be between 1 and 500."},
        separators=(",", ":"),
    )


async def _perform_search_request(
    ctx: Context,
    *,
    tool_name: str,
    endpoint: str,
    params: List[tuple[str, str]],
    transform_response,
    action_label: str,
) -> str:
    context: CodeAliveContext = ctx.request_context.lifespan_context
    api_key = get_api_key_from_context(ctx)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-CodeAlive-Integration": "mcp",
        "X-CodeAlive-Tool": tool_name,
        "X-CodeAlive-Client": "fastmcp",
    }

    full_url = urljoin(context.base_url, endpoint)
    request_id = log_api_request("GET", full_url, headers, params=params)

    try:
        response = await context.client.get(endpoint, params=params, headers=headers)
        log_api_response(response, request_id)
        response.raise_for_status()
        return transform_response(response.json())
    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(
            ctx,
            e,
            action_label,
            method=tool_name,
            recovery_hints={
                404: (
                    "(1) call get_data_sources to list available data source names, "
                    "(2) check spelling and case of the names you passed in data_sources, "
                    "(3) drop data_sources entirely to fall back to the API key's default"
                ),
            },
        )
        return json.dumps({"error": error_msg}, separators=(",", ":"))


def _build_scope_params(
    *,
    query: str,
    data_sources: Sequence[str],
    paths: Sequence[str],
    extensions: Sequence[str],
    max_results: Optional[int],
) -> List[tuple[str, str]]:
    params: List[tuple[str, str]] = [("Query", query)]

    if max_results is not None:
        params.append(("MaxResults", str(max_results)))

    for data_source in data_sources:
        params.append(("Names", data_source))
    for path in paths:
        params.append(("Paths", path))
    for extension in extensions:
        params.append(("Extensions", extension))

    return params


async def semantic_search(
    ctx: Context,
    query: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    paths: Optional[Union[str, List[str]]] = None,
    extensions: Optional[Union[str, List[str]]] = None,
    max_results: Optional[int] = None,
) -> str:
    """
    Canonical semantic search across indexed repositories and workspaces.

    Use this for natural-language exploration when you want relevant artifacts by meaning.
    For exact or regex matching, use `grep_search` instead.
    """
    tool_name = "semantic_search"
    query_error = _validate_query(query, tool_name)
    if query_error is not None:
        return query_error

    max_results_error = _validate_max_results(max_results, tool_name)
    if max_results_error is not None:
        return max_results_error

    data_source_names = normalize_data_source_names(data_sources)
    normalized_paths = _normalize_optional_list(paths)
    normalized_extensions = _normalize_optional_list(extensions)

    if data_source_names:
        await ctx.info(
            f"Semantic search for '{query}' across {len(data_source_names)} data source(s)"
        )
    else:
        await ctx.info(
            f"Semantic search for '{query}' using the API key's default data source"
        )

    params = _build_scope_params(
        query=query,
        data_sources=data_source_names,
        paths=normalized_paths,
        extensions=normalized_extensions,
        max_results=max_results,
    )

    return await _perform_search_request(
        ctx,
        tool_name=tool_name,
        endpoint="/api/search/semantic",
        params=params,
        transform_response=transform_search_response_to_json,
        action_label="semantic search",
    )


async def grep_search(
    ctx: Context,
    query: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    paths: Optional[Union[str, List[str]]] = None,
    extensions: Optional[Union[str, List[str]]] = None,
    max_results: Optional[int] = None,
    regex: bool = False,
) -> str:
    """
    Canonical exact/regex search across indexed repositories and workspaces.

    Use this for literal string lookup or regex matching when the pattern itself matters.
    """
    tool_name = "grep_search"
    query_error = _validate_query(query, tool_name)
    if query_error is not None:
        return query_error

    max_results_error = _validate_max_results(max_results, tool_name)
    if max_results_error is not None:
        return max_results_error

    data_source_names = normalize_data_source_names(data_sources)
    normalized_paths = _normalize_optional_list(paths)
    normalized_extensions = _normalize_optional_list(extensions)

    search_kind = "regex grep" if regex else "literal grep"
    if data_source_names:
        await ctx.info(
            f"{search_kind.capitalize()} for '{query}' across {len(data_source_names)} data source(s)"
        )
    else:
        await ctx.info(
            f"{search_kind.capitalize()} for '{query}' using the API key's default data source"
        )

    params = _build_scope_params(
        query=query,
        data_sources=data_source_names,
        paths=normalized_paths,
        extensions=normalized_extensions,
        max_results=max_results,
    )
    params.append(("Regex", "true" if regex else "false"))

    return await _perform_search_request(
        ctx,
        tool_name=tool_name,
        endpoint="/api/search/grep",
        params=params,
        transform_response=transform_grep_response_to_json,
        action_label="grep search",
    )


async def codebase_search(
    ctx: Context,
    query: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    mode: str = "auto",
    description_detail: str = "short",
) -> str:
    """
    Deprecated legacy semantic search tool.

    Prefer `semantic_search` for new integrations. This compatibility alias keeps the
    previous MCP contract and forwards to the legacy backend endpoint unchanged.
    """
    tool_name = "codebase_search"
    query_error = _validate_query(query, tool_name)
    if query_error is not None:
        return query_error

    context: CodeAliveContext = ctx.request_context.lifespan_context
    data_source_names = normalize_data_source_names(data_sources)

    normalized_mode = mode.lower() if mode else "auto"
    if normalized_mode not in ["auto", "fast", "deep"]:
        await ctx.warning(
            f"[{tool_name}] Invalid search mode: {mode}. "
            "Valid modes are 'auto', 'fast', and 'deep'. Using 'auto' instead."
        )
        normalized_mode = "auto"

    detail_map = {"short": "Short", "full": "Full"}
    normalized_detail = detail_map.get((description_detail or "short").lower(), "Short")

    if data_source_names:
        await ctx.info(
            f"Legacy codebase_search for '{query}' across {len(data_source_names)} data source(s)"
        )
    else:
        await ctx.info(
            f"Legacy codebase_search for '{query}' using the API key's default data source"
        )

    params = [
        ("Query", query),
        ("Mode", normalized_mode),
        ("IncludeContent", "false"),
        ("DescriptionDetail", normalized_detail),
    ]
    for data_source in data_source_names:
        params.append(("Names", data_source))

    api_key = get_api_key_from_context(ctx)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-CodeAlive-Integration": "mcp",
        "X-CodeAlive-Tool": tool_name,
        "X-CodeAlive-Client": "fastmcp",
    }

    full_url = urljoin(context.base_url, "/api/search")
    request_id = log_api_request("GET", full_url, headers, params=params)

    try:
        response = await context.client.get("/api/search", params=params, headers=headers)
        log_api_response(response, request_id)
        response.raise_for_status()
        return transform_search_response_to_json(response.json())
    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(
            ctx,
            e,
            "code search",
            method=tool_name,
            recovery_hints={
                404: (
                    "(1) call get_data_sources to list available data source names, "
                    "(2) check spelling and case of the names you passed in data_sources, "
                    "(3) drop data_sources entirely to fall back to the API key's default"
                ),
            },
        )
        return json.dumps({"error": error_msg}, separators=(",", ":"))
