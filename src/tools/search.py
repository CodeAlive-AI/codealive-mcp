"""Search tool implementation."""

from typing import List, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import (
    transform_search_response_to_xml,
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

    **WORKFLOW** (search → review → get content):
      1. Call `codebase_search` → returns XML with paths, descriptions, identifiers
      2. Review descriptions to decide which results matter
      3. Get full content:
         - Local repos (in your working directory): use `Read()` on the file paths
         - External repos (not locally accessible): use `fetch_artifacts` with identifiers

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
        XML with search results. Each result includes path, line numbers, kind, identifier,
        contentByteSize, and description. Use identifiers with `fetch_artifacts` to get
        full content for external repos, or `Read()` for local files.

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
        return f"<error>[{_TOOL_NAME}] Query cannot be empty. Please provide a search term, function name, or description of the code you're looking for.</error>"

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

        # Transform the response to XML format for better LLM processing
        xml_content = transform_search_response_to_xml(search_results)

        # Return XML string directly
        return xml_content

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(
            ctx, e, "code search", method=_TOOL_NAME
        )
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            error_msg = f"[{_TOOL_NAME}] Error: Not found (404): One or more data sources could not be found. Check your data_sources."
        return f"<error>{error_msg}</error>"
