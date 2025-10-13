"""Search tool implementation."""

from typing import List, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import transform_search_response_to_xml, handle_api_error, normalize_data_source_ids


async def codebase_search(
    ctx: Context,
    query: str,
    data_source_ids: Optional[Union[str, List[str]]] = None,
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

        data_source_ids: List of data source IDs to search in (required).
                         Can be workspace IDs (search all repositories in the workspace)
                         or individual repository IDs for targeted searches.
                         Example: ["67f664fd4c2a00698a52bb6f", "5e8f9a2c1d3b7e4a6c9d0f8e"]

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
           codebase_search(query="What is the auth flow?", data_source_ids=["repo123"])

        2. Intent query:
           codebase_search(query="Where is user registration logic?", data_source_ids=["repo123"])

        3. Workspace-wide question:
           codebase_search(query="How do microservices talk to the billing API?", data_source_ids=["workspace456"])

        4. Mixed query with a known identifier:
           codebase_search(query="Where do we validate JWTs (AuthService)?", data_source_ids=["repo123"])

        5. Concise results without full file contents:
           codebase_search(query="Where is password reset handled?", data_source_ids=["repo123"], include_content=false)

    Note:
        - At least one data_source_id must be provided
        - All data sources must be in "Alive" state
        - The API key must have access to the specified data sources
        - Prefer natural-language questions; templates are unnecessary.
        - Start with "auto" for best semantic results; escalate to "deep" only if needed.
        - If you know precise symbols (functions/classes), include them to narrow scope.
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    # Normalize data source IDs (handles Claude Desktop serialization issues)
    data_source_ids = normalize_data_source_ids(data_source_ids)

    # Validate inputs
    if not query or not query.strip():
        return "<error>Query cannot be empty. Please provide a search term, function name, or description of the code you're looking for.</error>"

    if not data_source_ids or len(data_source_ids) == 0:
        await ctx.info("No data source IDs provided. If the API key has exactly one assigned data source, that will be used as default.")

    try:
        normalized_mode = mode.lower() if mode else "auto"

        # Map input mode to backend's expected enum values
        if normalized_mode not in ["auto", "fast", "deep"]:
            await ctx.warning(f"Invalid search mode: {mode}. Valid modes are 'auto', 'fast', and 'deep'. Using 'auto' instead.")
            normalized_mode = "auto"

        # Log the search attempt
        if data_source_ids and len(data_source_ids) > 0:
            await ctx.info(f"Searching for '{query}' in {len(data_source_ids)} data source(s) using {normalized_mode} mode")
        else:
            await ctx.info(f"Searching for '{query}' using API key's default data source with {normalized_mode} mode")

        # Prepare query parameters as a list of tuples to support multiple values for DataSourceIds
        params = [
            ("Query", query),
            ("Mode", normalized_mode),
            ("IncludeContent", "true" if include_content else "false")
        ]

        if data_source_ids and len(data_source_ids) > 0:
            # Add each data source ID as a separate query parameter
            for ds_id in data_source_ids:
                if ds_id:  # Skip None or empty values
                    params.append(("DataSourceIds", ds_id))
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
            error_msg = f"Error: Not found (404): One or more data sources could not be found. Check your data_source_ids."
        return f"<error>{error_msg}</error>"