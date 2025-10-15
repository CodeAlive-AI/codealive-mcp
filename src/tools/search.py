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


async def codebase_search(
    ctx: Context,
    query: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    mode: str = "auto",
    include_content: bool = False
) -> str:
    """
    Use `codebase_search` tool to search for code in the codebase.

    Semantic search (`codebase_search`) is your MAIN exploration tool for understanding the
    indexed codebase (typically main/master branch or the specific branch shown in data sources).

    ALWAYS prefer using `codebase_search` over grep/find for initial code exploration because:
    - It's much faster and more efficient for discovering relevant code
    - It understands semantic meaning, not just text patterns
    - It searches the indexed repository state with full context

    IMPORTANT: This searches the INDEXED version of repositories (check branch in get_data_sources),
    NOT the current local files. Use grep when you specifically need to:
    - Search uncommitted local changes
    - Verify recent modifications
    - Check files on a different branch than the indexed one

    This tool excels at natural-language questions and intent-driven queries like:
      • "What is the authentication flow?"
      • "Where is the user registration logic implemented?"
      • "How do services communicate with the billing API?"
      • "Where is rate limiting handled?"
      • "Show me how we validate JWTs."

    You can include function/class names for more targeted results.

    Args:
        query: A natural-language description of what you're looking for.
               Prefer questions/phrases over template strings.
               Examples: "What initializes the database connection?",
                         "Where do we parse OAuth callbacks?",
                         "user registration controller"

        data_sources: List of data source names to search in (required).
                      Can be workspace names (search all repositories in the workspace)
                      or individual repository names for targeted searches.
                      Example: ["enterprise-platform", "payments-team"]

        mode: Search mode (case-insensitive):
              - "auto": (Default, recommended) Adaptive semantic search.
              - "fast": Lightweight/lexical pass; quickest for obvious matches.
              - "deep": Exhaustive semantic exploration; use sparingly for hard,
                        cross-cutting questions.

        include_content: Whether to include full file content in results (default: false).
                         Agents should proactively request content when needed by setting this to true.
                         Note: File content may be outdated compared to current local state.

    Returns:
        Search results as JSON including source info, file paths, line numbers, and code snippets.

    Examples:
        1. Natural-language question (recommended):
           codebase_search(query="What is the auth flow?", data_sources=["repo123"])

        2. Intent query:
           codebase_search(query="Where is user registration logic?", data_sources=["repo123"])

        3. Workspace-wide question:
           codebase_search(query="How do microservices talk to the billing API?", data_sources=["backend-team"])

        4. Mixed query with a known identifier:
           codebase_search(query="Where do we validate JWTs (AuthService)?", data_sources=["repo123"])

        5. Concise results without full file contents:
           codebase_search(query="Where is password reset handled?", data_sources=["repo123"], include_content=false)

    Note:
        - At least one data source name must be provided
        - All data sources must be in "Alive" state
        - The API key must have access to the specified data sources
        - Prefer natural-language questions; templates are unnecessary.
        - Start with "auto" for best semantic results; escalate to "deep" only if needed.
        - If you know precise symbols (functions/classes), include them to narrow scope.
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    # Normalize data source names (handles Claude Desktop serialization issues)
    data_source_names = normalize_data_source_names(data_sources)

    # Validate inputs
    if not query or not query.strip():
        return "<error>Query cannot be empty. Please provide a search term, function name, or description of the code you're looking for.</error>"

    if not data_source_names or len(data_source_names) == 0:
        await ctx.info("No data source names provided. If the API key has exactly one assigned data source, that will be used as default.")

    try:
        normalized_mode = mode.lower() if mode else "auto"

        # Map input mode to backend's expected enum values
        if normalized_mode not in ["auto", "fast", "deep"]:
            await ctx.warning(f"Invalid search mode: {mode}. Valid modes are 'auto', 'fast', and 'deep'. Using 'auto' instead.")
            normalized_mode = "auto"

        # Log the search attempt
        if data_source_names and len(data_source_names) > 0:
            await ctx.info(f"Searching for '{query}' in {len(data_source_names)} data source(s) using {normalized_mode} mode")
        else:
            await ctx.info(f"Searching for '{query}' using API key's default data source with {normalized_mode} mode")

        # Prepare query parameters as a list of tuples to support multiple values for Names
        params = [
            ("Query", query),
            ("Mode", normalized_mode),
            ("IncludeContent", "true" if include_content else "false")
        ]

        if data_source_names and len(data_source_names) > 0:
            # Add each data source name as a separate query parameter
            for ds_name in data_source_names:
                if ds_name:  # Skip None or empty values
                    params.append(("Names", ds_name))
        else:
            await ctx.info("Using API key's default data source (if available)")

        api_key = get_api_key_from_context(ctx)

        headers = {"Authorization": f"Bearer {api_key}"}

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
        xml_content = transform_search_response_to_xml(search_results, include_content)

        # Return XML string directly
        return xml_content

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(ctx, e, "code search")
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            error_msg = f"Error: Not found (404): One or more data sources could not be found. Check your data_sources."
        return f"<error>{error_msg}</error>"