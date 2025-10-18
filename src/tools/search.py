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

                         CRITICAL RULE - When to include content:
                         - CURRENT repository (user's working directory): include_content=false
                           → You have file access via Read tool - get paths only, then read for latest content
                         - EXTERNAL repositories (not in working directory): include_content=true
                           → You cannot access files - must get content in search results

                         How to identify CURRENT vs EXTERNAL repositories (use ALL available clues):

                         1. **Repository name matching**:
                            - Does the repo name match your current working directory name?
                            - Example: Working in "/Users/bob/my-app" and repo name is "my-app" → likely CURRENT

                         2. **Repository description analysis**:
                            - Does the description match what you've observed in the codebase?
                            - Check tech stack, architecture, features mentioned in description
                            - Example: Description says "Python FastAPI server" and you see FastAPI files → likely CURRENT

                         3. **User's question context**:
                            - Does user say "this repo", "our code", "the current project", "my app"? → CURRENT
                            - Does user reference "the X service", "external repo", "other project"? → EXTERNAL

                         4. **URL matching** (when available):
                            - Compare repo URL from get_data_sources with git remote URL
                            - Note: May not always be available or matchable

                         5. **Working context**:
                            - Have you been reading/editing files that match this repo's structure?
                            - Do file paths in your recent operations align with this repository?

                         **Default heuristic when uncertain**:
                         - If user is asking about code in their working directory → CURRENT (include_content=false)
                         - If user is asking about a different/external service → EXTERNAL (include_content=true)
                         - When truly ambiguous, prefer include_content=false for repos that seem related to current work

    Returns:
        Search results as JSON including source info, file paths, line numbers, and code snippets.

    Examples:
        1. Search CURRENT repository (identified by directory name + context):
           # Working in "/Users/bob/codealive-mcp"
           # User asks: "Where is the search tool implemented in this project?"
           # Repo name from get_data_sources: "codealive-mcp"
           # → Name matches directory, user says "this project" → CURRENT
           codebase_search(
               query="Where is the search tool implemented?",
               data_sources=["codealive-mcp"],
               include_content=false  # Current repo - get paths, use Read tool
           )
           # Then: Read(file_path="/Users/bob/codealive-mcp/src/tools/search.py")

        2. Search CURRENT repository (identified by description matching):
           # Working in Python FastMCP project
           # Description: "Python MCP server using FastMCP framework"
           # You've been reading FastMCP code in this directory → CURRENT
           codebase_search(
               query="How is the lifespan context managed?",
               data_sources=["my-mcp-server"],
               include_content=false  # Description matches observed codebase
           )

        3. Search EXTERNAL repository (different service):
           # Working in "frontend-app"
           # User asks: "How does the payments service handle refunds?"
           # Repo: "payments-service" → Different service → EXTERNAL
           codebase_search(
               query="How are refunds processed?",
               data_sources=["payments-service"],
               include_content=true  # External service - need content
           )

        4. Search EXTERNAL workspace (multiple external repos):
           # User asks about backend services, but you're in frontend repo
           codebase_search(
               query="How do microservices authenticate API calls?",
               data_sources=["backend-workspace"],
               include_content=true  # External workspace
           )

        5. Ambiguous case - use context:
           # User: "Check how authentication works in our API"
           # Working in "api-server" directory
           # Repo name: "company-api" (slightly different but plausible match)
           # Description: "REST API server with authentication"
           # → User says "our API", description matches → Likely CURRENT
           codebase_search(
               query="authentication implementation",
               data_sources=["company-api"],
               include_content=false  # Context suggests current repo
           )

    Note:
        - At least one data source name must be provided
        - All data sources must be in "Alive" state
        - The API key must have access to the specified data sources
        - Prefer natural-language questions; templates are unnecessary.
        - Start with "auto" for best semantic results; escalate to "deep" only if needed.
        - If you know precise symbols (functions/classes), include them to narrow scope.

        CRITICAL: Always call get_data_sources() first to get repository names, descriptions, and URLs.
        Then use the heuristics above to determine include_content for each search.
        The description field is especially valuable for matching repositories to your working context.
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