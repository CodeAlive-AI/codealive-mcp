"""Search tool implementations."""

import json
from typing import Any, Dict, List, Optional, Sequence, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import (
    handle_api_error,
    normalize_data_source_names,
    transform_grep_response,
    transform_search_response,
)


def _normalize_optional_list(value: Optional[Union[str, List[str]]]) -> List[str]:
    """Normalize optional string-or-list inputs while preserving ordering.

    Handles stringified JSON arrays (e.g. ``'[".cs",".py"]'``) that some MCP
    clients send instead of native arrays.
    """
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if item]
            except (json.JSONDecodeError, TypeError):
                pass
        return [stripped]
    return [item for item in value if item]


def _validate_query(query: str, tool_name: str) -> None:
    """Raise ToolError if query is empty."""
    if not query or not query.strip():
        raise ToolError(
            f"[{tool_name}] Query cannot be empty. Please provide a search term, "
            "pattern, function name, or description of the code you're looking for."
        )


def _validate_max_results(max_results: Optional[int], tool_name: str) -> None:
    """Raise ToolError if max_results is out of range."""
    if max_results is not None and not (1 <= max_results <= 500):
        raise ToolError(f"[{tool_name}] max_results must be between 1 and 500.")


async def _perform_search_request(
    ctx: Context,
    *,
    tool_name: str,
    endpoint: str,
    params: List[tuple[str, str]],
    transform_response,
    action_label: str,
) -> Dict[str, Any]:
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
        # handle_api_error raises ToolError → MCP response gets isError: true
        await handle_api_error(
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
) -> Dict[str, Any]:
    """
    Search indexed code by meaning — the default discovery tool.

    Use this for natural-language exploration when you want relevant artifacts
    by meaning: function names, concepts, architecture patterns, etc.
    For exact string or regex matching, use `grep_search` instead.

    Args:
        query: Natural-language description of what you're looking for.
               Example: "authentication middleware", "database connection pooling",
               "JWT token validation"

        data_sources: Repository or workspace names to search.
                      Omit to use the API key's default data source.
                      Call `get_data_sources` first to discover available names.
                      Example: ["backend", "workspace:payments-team"]

        paths: Restrict results to specific directory paths.
               Example: ["src/services", "src/domain"]

        extensions: Restrict results to specific file extensions.
                    Example: [".cs", ".py", ".ts"]

        max_results: Maximum number of results to return (1–500).
                     Omit for the server default.

    Returns:
        {"results": [...], "hint": "..."}

        Each result contains:
        - path: file path within the repository
        - identifier: fully qualified artifact ID — pass this to `fetch_artifacts`
        - kind: "File", "Symbol", or "Chunk"
        - description: short triage summary (NOT the real source — see hint)
        - startLine/endLine: line range (for symbols)
        - contentByteSize: file size in bytes

        The `hint` field reminds you to load real source code via
        `fetch_artifacts(identifier)` or local `Read(path)` before reasoning
        about the code.

    Examples:
        1. Find authentication code:
           semantic_search(query="authentication middleware",
                           data_sources=["backend"])

        2. Narrow to Python files in a specific directory:
           semantic_search(query="database retry logic",
                           data_sources=["backend"],
                           paths=["src/services"],
                           extensions=[".py"])
    """
    tool_name = "semantic_search"
    _validate_query(query, tool_name)
    _validate_max_results(max_results, tool_name)

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
        transform_response=transform_search_response,
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
) -> Dict[str, Any]:
    """
    Search indexed code by exact text or regex pattern.

    Use this when the literal string or pattern matters: function names, error
    messages, config keys, import paths, TODO comments, etc.
    For meaning-based exploration, use `semantic_search` instead.

    Args:
        query: Exact text or regex pattern to match.
               Literal examples: "ConnectionString", "TODO: fix", "import numpy"
               Regex examples: "def test_.*async", "Status\\.(Alive|Failed)"

        data_sources: Repository or workspace names to search.
                      Omit to use the API key's default data source.
                      Call `get_data_sources` first to discover available names.

        paths: Restrict results to specific directory paths.
               Example: ["src/services"]

        extensions: Restrict results to specific file extensions.
                    Example: [".cs", ".py"]

        max_results: Maximum number of results to return (1–500).

        regex: If True, treat `query` as a regex pattern. Default: False (literal).

    Returns:
        {"results": [...], "hint": "..."}

        Each result contains:
        - path: file path
        - identifier: pass to `fetch_artifacts` for full source
        - matchCount: total matches in this file
        - matches: array of line-level hits, each with:
          - lineNumber, startColumn, endColumn, lineText

        The `hint` reminds you that line previews are evidence only — load
        full source via `fetch_artifacts` or local `Read()` before reasoning.

    Examples:
        1. Find exact string:
           grep_search(query="ConnectionString",
                       data_sources=["backend"])

        2. Regex search for test methods:
           grep_search(query="def test_.*auth",
                       data_sources=["backend"],
                       extensions=[".py"],
                       regex=True)
    """
    tool_name = "grep_search"
    _validate_query(query, tool_name)
    _validate_max_results(max_results, tool_name)

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
        transform_response=transform_grep_response,
        action_label="grep search",
    )


async def codebase_search(
    ctx: Context,
    query: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    mode: str = "auto",
    description_detail: str = "short",
) -> Dict[str, Any]:
    """
    Deprecated legacy semantic search tool.

    Prefer `semantic_search` for new integrations. This compatibility alias keeps the
    previous MCP contract and forwards to the legacy backend endpoint unchanged.
    """
    tool_name = "codebase_search"
    _validate_query(query, tool_name)

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
        return transform_search_response(response.json())
    except (httpx.HTTPStatusError, Exception) as e:
        await handle_api_error(
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
