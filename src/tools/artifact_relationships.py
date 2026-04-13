"""Artifact relationships tool implementation."""

import json
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urljoin

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error

# MCP tool/method name surfaced in every error/log message from this module.
_TOOL_NAME = "get_artifact_relationships"

# Map MCP profile names to backend enum values
PROFILE_MAP = {
    "callsOnly": "CallsOnly",
    "inheritanceOnly": "InheritanceOnly",
    "allRelevant": "AllRelevant",
    "referencesOnly": "ReferencesOnly",
}

# Backend relationship type to MCP-friendly snake_case
RELATIONSHIP_TYPE_MAP = {
    "OutgoingCalls": "outgoing_calls",
    "IncomingCalls": "incoming_calls",
    "Ancestors": "ancestors",
    "Descendants": "descendants",
    "References": "references",
}


async def get_artifact_relationships(
    ctx: Context,
    identifier: str,
    profile: Literal["callsOnly", "inheritanceOnly", "allRelevant", "referencesOnly"] = "callsOnly",
    max_count_per_type: int = 50,
) -> str:
    """
    Retrieve relationship groups for a single artifact by profile.

    Use this tool to explore an artifact's call graph, inheritance hierarchy,
    or references. This is a drill-down tool — use it AFTER `semantic_search`,
    `grep_search`, legacy `codebase_search`, or `fetch_artifacts` when you need
    to understand how an artifact relates to others in the codebase.

    Args:
        identifier: Fully qualified artifact identifier from search or fetch results.
        profile: Relationship profile to expand. One of:
                 - "callsOnly" (default): outgoing and incoming calls
                 - "inheritanceOnly": ancestors and descendants
                 - "allRelevant": calls + inheritance (4 groups)
                 - "referencesOnly": symbol references
        max_count_per_type: Maximum related artifacts per relationship type (1–1000, default 50).

    Returns:
        Compact JSON with grouped relationships:
            {"sourceIdentifier":"...","profile":"callsOnly","found":true,
             "relationships":[
               {"type":"outgoing_calls","totalCount":57,"returnedCount":50,"truncated":true,
                "items":[{"identifier":"...","filePath":"src/Data/Repo.cs","startLine":88,
                          "shortSummary":"Stores data"}]},
               {"type":"incoming_calls","totalCount":3,"returnedCount":3,"truncated":false,
                "items":[{"identifier":"...","filePath":"src/Services/Worker.cs","startLine":142}]}
             ]}

        When the artifact is not found or inaccessible:
            {"sourceIdentifier":"...","profile":"callsOnly","found":false}
    """
    if not identifier:
        raise ToolError(f"[{_TOOL_NAME}] Artifact identifier is required.")

    if not (1 <= max_count_per_type <= 1000):
        raise ToolError(f"[{_TOOL_NAME}] max_count_per_type must be between 1 and 1000.")

    # Literal type handles most validation via Pydantic, but direct callers
    # (e.g. unit tests) can still pass invalid values — keep as fallback.
    api_profile = PROFILE_MAP.get(profile)
    if api_profile is None:
        supported = ", ".join(PROFILE_MAP.keys())
        raise ToolError(f'[{_TOOL_NAME}] Unsupported profile "{profile}". Use one of: {supported}')

    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-CodeAlive-Integration": "mcp",
            "X-CodeAlive-Tool": "get_artifact_relationships",
            "X-CodeAlive-Client": "fastmcp",
        }

        body = {
            "identifier": identifier,
            "profile": api_profile,
            "maxCountPerType": max_count_per_type,
        }

        await ctx.info(f"Fetching {profile} relationships for artifact")

        full_url = urljoin(context.base_url, "/api/search/artifact-relationships")
        request_id = log_api_request("POST", full_url, headers, body=body)

        response = await context.client.post(
            "/api/search/artifact-relationships", json=body, headers=headers
        )

        log_api_response(response, request_id)
        response.raise_for_status()

        return _build_relationships_json(response.json())

    except (httpx.HTTPStatusError, Exception) as e:
        await handle_api_error(
            ctx, e, "get artifact relationships", method=_TOOL_NAME,
            recovery_hints={
                404: (
                    "(1) verify the identifier came from a recent semantic_search, grep_search, codebase_search, or fetch_artifacts result, "
                    "(2) call semantic_search or grep_search again to get a fresh identifier — the index may have changed, "
                    "(3) check that the artifact is a function/class (relationships are not available for non-symbol artifacts)"
                ),
            },
        )


def _build_relationships_json(data: dict) -> str:
    """Build a compact JSON representation of an artifact relationships response."""
    raw_source_id = data.get("sourceIdentifier") or ""
    raw_profile = data.get("profile") or ""
    found = bool(data.get("found", False))

    # Map profile back to MCP-friendly name
    mcp_profile = raw_profile
    for mcp_name, api_name in PROFILE_MAP.items():
        if api_name == raw_profile:
            mcp_profile = mcp_name
            break

    payload: Dict[str, Any] = {
        "sourceIdentifier": raw_source_id,
        "profile": mcp_profile,
        "found": found,
    }

    if found:
        relationships = data.get("relationships") or []
        payload["relationships"] = [_build_group(group) for group in relationships]

    return json.dumps(payload, separators=(",", ":"))


def _build_group(group: dict) -> Dict[str, Any]:
    """Build the JSON representation of a single relationship group."""
    relationship_type = group.get("relationType", "")
    mcp_type = RELATIONSHIP_TYPE_MAP.get(relationship_type, relationship_type.lower())

    items: List[Dict[str, Any]] = []
    for item in group.get("items", []) or []:
        item_dict: Dict[str, Any] = {"identifier": item.get("identifier") or ""}

        file_path = item.get("filePath")
        if file_path is not None:
            item_dict["filePath"] = file_path

        start_line = item.get("startLine")
        if start_line is not None:
            item_dict["startLine"] = start_line

        short_summary = item.get("shortSummary")
        if short_summary is not None:
            item_dict["shortSummary"] = short_summary

        items.append(item_dict)

    return {
        "type": mcp_type,
        "totalCount": group.get("totalCount") or 0,
        "returnedCount": group.get("returnedCount") or 0,
        "truncated": bool(group.get("truncated")),
        "items": items,
    }
