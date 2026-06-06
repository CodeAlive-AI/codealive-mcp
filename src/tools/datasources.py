"""Data sources tool implementation."""

import json
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import (
    CodeAliveContext,
    get_api_key_from_context,
    log_api_request,
    log_api_response,
)
from utils import handle_api_error

# MCP tool/method name surfaced in every error/log message from this module.
_TOOL_NAME = "get_data_sources"

# Pre-filter scoped candidate count, emitted by the backend only on relevance-filtered requests.
_TOTAL_HEADER = "X-CodeAlive-Total-Data-Sources"


def _relevance_message(data_sources: list, response) -> str:
    """Builds the hint accompanying a query'd (relevance-filtered) result.

    The backend guarantees every relevance-selected item carries a non-empty `relevanceReason`,
    so a query'd response where NO item has one means the filter did not run (fail-open on error,
    disabled by config, or an older backend ignoring `query`) and the FULL list was returned —
    the model must be told, instead of mistaking the full dump for a relevant shortlist.
    """
    filtered = any(ds.get("relevanceReason") for ds in data_sources)
    if not filtered:
        return (
            "Relevance filtering was unavailable for this request (it may have failed or be "
            "disabled), so the FULL unfiltered list of data sources is returned."
        )

    shown = len(data_sources)
    total_header = response.headers.get(_TOTAL_HEADER)
    total = int(total_header) if total_header and total_header.isdigit() else None
    if total is not None and total > shown:
        return (
            f"{shown} of {total} available data sources are relevant to this query; the other "
            f"{total - shown} were omitted. Call get_data_sources without a query to get the full list."
        )
    if total is not None:
        return f"All {total} available data sources are relevant to this query."
    return (
        "Only the data sources relevant to this query are shown; non-relevant sources were "
        "omitted. Call get_data_sources without a query to get the full list."
    )


# alive_only refers to ready_only. leaved as is for backward compatibility.
async def get_data_sources(
    ctx: Context, alive_only: bool = True, query: str | None = None
) -> str:
    """
    **CALL THIS FIRST**: Gets all available data sources (repositories and workspaces) for the user's account.

    This tool MUST be called BEFORE using `semantic_search`, `grep_search`, or
    `chat` to discover available data source names, UNLESS the user
    has explicitly provided data source names.

    A data source is a code repository or workspace that has been indexed by CodeAlive
    and can be used for code search and chat completions.

    Args:
        alive_only: If True (default), returns only data sources that are fully processed and ready for use.
                    If False, returns all data sources regardless of processing state.
        query:      Optional. The user's initial intent/task in natural language (e.g. "add OAuth to
                    checkout"). When provided, the backend runs an agentic relevance filter and returns
                    ONLY the data sources relevant to that intent, each with a `relevanceReason`
                    explaining why. This is the user's GOAL — distinct from `searchTerm` (a substring
                    name filter). Omit it to get the full list. Pass it whenever you
                    know what the user is trying to accomplish, to keep the returned list focused.

    Returns:
        Without `query`: a compact JSON array of available data sources.
        With `query`: a JSON object {"dataSources": [...], "message": "..."} where `message` tells
        you whether sources were omitted as non-relevant (and how many of the total), that every
        available source was relevant, or that relevance filtering was unavailable and the FULL
        list is returned. Each data source has the following fields:
        - id: Unique identifier for the data source
        - name: Human-readable name - CRITICAL for matching with current working directory name
        - description: Summary of codebase contents - CRITICAL for identifying if this matches your
          current working codebase (compare tech stack, architecture, features you've observed)
        - type: The type of data source ("Repository" or "Workspace")
        - url: Repository URL (for Repository type only) - useful for matching with git remote
        - state: The processing state of the data source (if alive_only=false)
        - relevanceReason: Why this source is relevant to `query` (present ONLY when `query` was supplied)

        Use name + description + url together to determine if a repository is the CURRENT one
        you're working in versus an EXTERNAL repository.

    Examples:
        1. Get only ready-to-use data sources:
           get_data_sources()

        2. Get all data sources including those still processing:
           get_data_sources(alive_only=false)

    Note:
        Ready data sources are fully processed and available for search and chat.
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

        Use the returned data source names with `semantic_search`, `grep_search`,
        `codebase_search` (legacy), `chat`, and `codebase_consultant` (legacy).
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)

        # Determine the endpoint based on ready_only flag
        endpoint = "/api/datasources/ready" if alive_only else "/api/datasources/all"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-CodeAlive-Integration": "mcp",
            "X-CodeAlive-Tool": "get_data_sources",
            "X-CodeAlive-Client": "fastmcp",
        }

        # Thread the user's intent as the `query` param when present so the backend relevance
        # filter runs. Omitted entirely otherwise, so the request is unchanged for legacy callers
        # (and an older backend that ignores `query` simply returns the full list).
        params = {"query": query} if query else None

        # Log the request
        full_url = urljoin(context.base_url, endpoint)
        request_id = log_api_request("GET", full_url, headers)

        # Make API request
        response = await context.client.get(endpoint, headers=headers, params=params)

        # Log the response
        log_api_response(response, request_id)

        response.raise_for_status()

        # Parse and format the response
        data_sources = response.json()

        # If no data sources found, return an empty JSON array with a hint. With a `query`, an empty
        # result means "nothing relevant to this intent" (sources DO exist) — a distinct message from
        # the no-sources-at-all case, so the model doesn't tell the user to add a repository.
        if not data_sources or len(data_sources) == 0:
            message = (
                "No data sources are relevant to this query. Try a broader query, or call "
                "get_data_sources without a query to see the full list."
                if query
                else "No data sources found. Please add a repository or workspace to CodeAlive before using this API."
            )
            return json.dumps(
                {"dataSources": [], "message": message},
                separators=(",", ":"),
            )

        # Remove repositoryIds from workspace data sources
        for data_source in data_sources:
            if (
                data_source.get("type") == "Workspace"
                and "repositoryIds" in data_source
            ):
                del data_source["repositoryIds"]

        if query:
            return json.dumps(
                {
                    "dataSources": data_sources,
                    "message": _relevance_message(data_sources, response),
                },
                separators=(",", ":"),
            )

        # Return compact JSON (no query → legacy bare array, byte-for-byte unchanged)
        return json.dumps(data_sources, separators=(",", ":"))

    except (httpx.HTTPStatusError, Exception) as e:
        await handle_api_error(
            ctx,
            e,
            "retrieving data sources",
            method=_TOOL_NAME,
            recovery_hints={
                # 422 means *some* sources are still indexing — surface alive_only=false as the next step
                422: (
                    "(1) call get_data_sources(alive_only=false) to see which sources are still being processed, "
                    "(2) wait a few minutes for indexing to complete and retry"
                ),
            },
        )
