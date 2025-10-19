"""Data sources tool implementation."""

import json
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error


async def get_data_sources(ctx: Context, alive_only: bool = True) -> str:
    """
    **CALL THIS FIRST**: Gets all available data sources (repositories and workspaces) for the user's account.

    This tool MUST be called BEFORE using `codebase_search` or `codebase_consultant` to discover
    available data source names, UNLESS the user has explicitly provided data source names.

    A data source is a code repository or workspace that has been indexed by CodeAlive
    and can be used for code search and chat completions.

    Args:
        alive_only: If True (default), returns only data sources in "Alive" state ready for use with chat.
                    If False, returns all data sources regardless of processing state.

    Returns:
        A formatted list of available data sources with the following information for each:
        - id: Unique identifier for the data source
        - name: Human-readable name - CRITICAL for matching with current working directory name
        - description: Summary of codebase contents - CRITICAL for identifying if this matches your
          current working codebase (compare tech stack, architecture, features you've observed)
        - type: The type of data source ("Repository" or "Workspace")
        - url: Repository URL (for Repository type only) - useful for matching with git remote
        - state: The processing state of the data source (if alive_only=false)

        Use name + description + url together to determine if a repository is the CURRENT one
        you're working in versus an EXTERNAL repository.

    Examples:
        1. Get only ready-to-use data sources:
           get_data_sources()

        2. Get all data sources including those still processing:
           get_data_sources(alive_only=false)

    Note:
        Data sources in "Alive" state are fully processed and ready for search and chat.
        Other states include "New" (just added), "Processing" (being indexed),
        "Failed" (indexing failed), etc.

        CRITICAL - Use ALL available information to identify CURRENT vs EXTERNAL repositories:

        Heuristic signals to combine (in order of reliability):
        1. **Name matching**: Does repo name match your current working directory name?
           Example: In "/Users/bob/my-app" and repo name is "my-app" → CURRENT

        2. **Description matching**: Does description match what you've observed in the codebase?
           - Tech stack (Python, JavaScript, FastAPI, React, etc.)
           - Architecture patterns (microservices, monolith, MCP server, etc.)
           - Key features mentioned
           Example: Description says "FastAPI MCP server" and you see FastAPI + MCP code → CURRENT

        3. **User context**: What is the user asking about?
           - "this repo", "our code", "my project" → CURRENT
           - "the payments service", "external API" → EXTERNAL

        4. **URL matching** (when available): Compare with git remote URL
           Note: May have format differences (SSH vs HTTPS), but hostname + path should match

        5. **Working history**: Have you been reading/editing files that align with this repo?

        **Decision rule**:
        - CURRENT repo → include_content=false in codebase_search (use Read tool for files)
        - EXTERNAL repo → include_content=true in codebase_search (no file access)

        Use the returned data source names with the codebase_search and codebase_consultant functions.
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)

        # Determine the endpoint based on alive_only flag
        endpoint = "/api/datasources/alive" if alive_only else "/api/datasources/all"

        headers = {"Authorization": f"Bearer {api_key}"}

        # Log the request
        full_url = urljoin(context.base_url, endpoint)
        request_id = log_api_request("GET", full_url, headers)

        # Make API request
        response = await context.client.get(endpoint, headers=headers)

        # Log the response
        log_api_response(response, request_id)

        response.raise_for_status()

        # Parse and format the response
        data_sources = response.json()

        # If no data sources found, return a helpful message
        if not data_sources or len(data_sources) == 0:
            return "No data sources found. Please add a repository or workspace to CodeAlive before using this API."

        # Remove repositoryIds from workspace data sources
        for data_source in data_sources:
            if data_source.get("type") == "Workspace" and "repositoryIds" in data_source:
                del data_source["repositoryIds"]

        # Format the response as a readable string
        formatted_data = json.dumps(data_sources, indent=2)
        result = f"Available data sources:\n{formatted_data}"

        # Add usage hint
        result += "\n\nYou can use these data source names with the codebase_search and codebase_consultant functions."

        return result

    except (httpx.HTTPStatusError, Exception) as e:
        return await handle_api_error(ctx, e, "retrieving data sources")