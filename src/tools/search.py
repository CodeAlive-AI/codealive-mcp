"""Search tool implementation."""

from typing import List, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context

import json

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import (
    transform_search_response_to_json,
    handle_api_error,
    normalize_data_source_names,
)

# MCP tool/method name surfaced in every error/log message from this module.
_TOOL_NAME = "codebase_search"


async def codebase_search(
    ctx: Context,
    query: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    mode: str = "auto",
    description_detail: str = "short",
) -> str:
    """
    Semantic code search across indexed repositories. Returns file paths, descriptions, and identifiers.

    **PREREQUISITE**: Call `get_data_sources` FIRST to discover data source names,
    UNLESS the user has explicitly provided specific names (e.g., "search in my-repo").

    **WORKFLOW** (search → triage → load real content):
      1. Call `codebase_search` → returns compact JSON with paths, descriptions, identifiers
      2. Use `description` ONLY to triage which results look relevant — it is a
         pointer, NOT the source of truth. Do not draw conclusions from it.
      3. For every artifact that looks relevant, load the real source:
         - Local repos (in your working directory): use `Read()` on the file paths
         - External repos (not locally accessible): use `fetch_artifacts` with identifiers
         Base your understanding only on the `content` returned by step 3.

    **WHEN TO USE vs local tools:**
      USE `codebase_search`: natural-language questions, semantic exploration, cross-repo patterns
      USE grep/find: uncommitted local changes, exact keyword match, non-indexed branches

    Args:
        query: Natural-language description of what you're looking for.
               Examples: "What initializes the database connection?",
                         "Where do we parse OAuth callbacks?",
                         "user registration controller"

        data_sources: Data source names to search (from `get_data_sources`).
                      Can be workspace names or individual repository names.
                      Example: ["enterprise-platform", "payments-team"]

        mode: Search mode (case-insensitive):
              - "auto": (Default, recommended) Adaptive semantic search.
              - "fast": Lightweight lexical pass; for known terms/exact names.
              - "deep": Exhaustive semantic exploration; use sparingly for hard,
                        cross-cutting questions.

        description_detail: Detail level for result descriptions (default: "short").
                            - "short": Brief summary of each result.
                            - "full": Richer description — use when deciding which results to fetch.

    Returns:
        Compact JSON with search results plus a `hint` field reminding the agent to
        load real content via `fetch_artifacts`/`Read()` before drawing conclusions.
        Each result includes path, line numbers, kind, identifier, contentByteSize,
        and description. **`description` is a triage pointer only — never the source
        of truth.** Use identifiers with `fetch_artifacts` to get full content for
        external repos, or `Read()` for local files.

        Shape:
            {"results":[{"path":"...","startLine":...,"endLine":...,"kind":"...",
                         "identifier":"...","contentByteSize":...,"description":"..."}],
             "hint":"..."}

    Note:
        - Searches the INDEXED version of repositories, NOT local files
        - Start with "auto" mode; escalate to "deep" only if needed
        - Always call get_data_sources() first to get available repository names
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    # Normalize data source names (handles Claude Desktop serialization issues)
    data_source_names = normalize_data_source_names(data_sources)

    # Validate inputs
    if not query or not query.strip():
        return json.dumps(
            {
                "error": f"[{_TOOL_NAME}] Query cannot be empty. Please provide a search term, function name, or description of the code you're looking for."
            },
            separators=(",", ":"),
        )

    if not data_source_names or len(data_source_names) == 0:
        await ctx.info("No data source names provided. If the API key has exactly one assigned data source, that will be used as default.")

    try:
        normalized_mode = mode.lower() if mode else "auto"

        # Map input mode to backend's expected enum values
        if normalized_mode not in ["auto", "fast", "deep"]:
            await ctx.warning(f"[{_TOOL_NAME}] Invalid search mode: {mode}. Valid modes are 'auto', 'fast', and 'deep'. Using 'auto' instead.")
            normalized_mode = "auto"

        # Log the search attempt
        if data_source_names and len(data_source_names) > 0:
            await ctx.info(f"Searching for '{query}' in {len(data_source_names)} data source(s) using {normalized_mode} mode")
        else:
            await ctx.info(f"Searching for '{query}' using API key's default data source with {normalized_mode} mode")

        # Map description_detail to API enum values
        detail_map = {"short": "Short", "full": "Full"}
        normalized_detail = detail_map.get(
            (description_detail or "short").lower(), "Short"
        )

        # Prepare query parameters as a list of tuples to support multiple values for Names
        params = [
            ("Query", query),
            ("Mode", normalized_mode),
            ("IncludeContent", "false"),
            ("DescriptionDetail", normalized_detail),
        ]

        if data_source_names and len(data_source_names) > 0:
            # Add each data source name as a separate query parameter
            for ds_name in data_source_names:
                if ds_name:  # Skip None or empty values
                    params.append(("Names", ds_name))
        else:
            await ctx.info("Using API key's default data source (if available)")

        api_key = get_api_key_from_context(ctx)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-CodeAlive-Integration": "mcp",
            "X-CodeAlive-Tool": "codebase_search",
            "X-CodeAlive-Client": "fastmcp",
        }

        # Log the request
        full_url = urljoin(context.base_url, "/api/search")
        request_id = log_api_request("GET", full_url, headers, params=params)

        # Make API request
        response = await context.client.get("/api/search", params=params, headers=headers)

        # Log the response
        log_api_response(response, request_id)

        response.raise_for_status()

        search_results = response.json()

        # Return compact JSON string directly
        return transform_search_response_to_json(search_results)

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(
            ctx, e, "code search", method=_TOOL_NAME,
            recovery_hints={
                404: (
                    "(1) call get_data_sources to list available data source names, "
                    "(2) check spelling and case of the names you passed in data_sources, "
                    "(3) drop data_sources entirely to fall back to the API key's default"
                ),
            },
        )
        return json.dumps({"error": error_msg}, separators=(",", ":"))
