"""Artifact relationships tool implementation."""

from typing import Any, Dict, List, Literal, Optional
from urllib.parse import urljoin

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError
from loguru import logger

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
    data_source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieve relationship groups for a single artifact by profile.

    Use this tool to expand the relationship graph around one known artifact:
    call graph edges, inheritance hierarchy, or references.

    Important usage rules:
        - This is a graph expansion tool, not a search tool. The `identifier`
          must be an exact artifact identifier returned by `semantic_search`,
          `grep_search`, legacy `codebase_search`, or `fetch_artifacts`.
        - Do not pass a repository name, file path, class name, method name, or
          guessed symbol name unless it is the full identifier from a prior
          tool result.
        - If `found=false` or the backend returns a not-found/inaccessible
          error, get a fresh identifier with `semantic_search`, `grep_search`,
          `codebase_search`, or `fetch_artifacts` before retrying. Repeating
          the same guessed identifier usually repeats the same failure.
        - Relationships are primarily available for symbol artifacts such as
          functions, methods, classes, and interfaces. Plain files and prose
          documents can legitimately have no relationship graph.
        - The response contains relationship metadata and short summaries, not
          full source code. Use `fetch_artifacts` on returned identifiers when
          exact source content is needed.
        - Choose `profile` by artifact shape: `callsOnly` for function/method
          callers and callees; `inheritanceOnly` for hierarchy; `allRelevant`
          for calls plus inheritance only (it excludes references);
          `referencesOnly` for where-used checks on types, containers, fields,
          commands, events, interfaces, and other non-call usage.
        - Mediated or dynamic frameworks such as command buses, event buses,
          dependency injection, reflection, route binding, subscriptions,
          schedulers, or generated dispatch may not expose a direct call edge.
          When graph context is missing or insufficient, use targeted
          `grep_search` for construction, registration, dispatch, route,
          subscription, or scheduler text surfaced by source you've already read.
        - If any relationship group has `truncated=true`, increase
          `max_count_per_type` up to 1000 or narrow the investigation with a
          more specific `profile`.

    Args:
        identifier: Fully qualified artifact identifier from search or fetch results.
        profile: Relationship profile to expand. One of:
                 - "callsOnly" (default): outgoing and incoming calls
                 - "inheritanceOnly": ancestors, descendants, implementations, and derived types
                 - "allRelevant": calls + inheritance only; references are excluded
                 - "referencesOnly": where-used LSP references for non-call usage
        max_count_per_type: Maximum related artifacts per relationship type (1–1000, default 50).
        data_source: Optional data-source Name or Id used to disambiguate an identifier that
                     exists in more than one data source. Copy the `dataSource.name` or
                     `dataSource.id` from a search result. Omit it for normal lookups; if the
                     source identifier is ambiguous and you omit it, the backend returns a 409
                     listing the candidate data sources.

    Returns:
        A dict with grouped relationships:
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
    tool_arguments = {
        "identifier": identifier,
        "profile": profile,
        "max_count_per_type": max_count_per_type,
        "data_source": data_source,
    }

    # Normalize the optional selector: treat empty/whitespace-only as "no selector"
    # so we don't send a junk dataSource to the backend or echo it in the not-found hint.
    # (tool_arguments above intentionally keeps the raw value for exact-invocation logging.)
    if data_source is not None:
        data_source = data_source.strip() or None

    if not identifier:
        logger.bind(tool=_TOOL_NAME, tool_arguments=tool_arguments).warning(
            "Tool validation failed: artifact identifier is required"
        )
        raise ToolError(f"[{_TOOL_NAME}] Artifact identifier is required.")

    if not (1 <= max_count_per_type <= 1000):
        logger.bind(tool=_TOOL_NAME, tool_arguments=tool_arguments).warning(
            "Tool validation failed: max_count_per_type is out of range"
        )
        raise ToolError(f"[{_TOOL_NAME}] max_count_per_type must be between 1 and 1000.")

    # Literal type handles most validation via Pydantic, but direct callers
    # (e.g. unit tests) can still pass invalid values — keep as fallback.
    api_profile = PROFILE_MAP.get(profile)
    if api_profile is None:
        supported = ", ".join(PROFILE_MAP.keys())
        logger.bind(tool=_TOOL_NAME, tool_arguments=tool_arguments).warning(
            "Tool validation failed: unsupported relationship profile"
        )
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
        if data_source:
            body["dataSource"] = data_source

        await ctx.debug(f"Fetching {profile} relationships for artifact")

        full_url = urljoin(context.base_url, "/api/search/artifact-relationships")
        request_id = log_api_request("POST", full_url, headers, body=body)

        response = await context.client.post(
            "/api/search/artifact-relationships", json=body, headers=headers
        )

        log_api_response(response, request_id)
        response.raise_for_status()

        return _build_relationships_dict(response.json(), data_source=data_source)

    except (httpx.HTTPStatusError, Exception) as e:
        logger.bind(
            tool=_TOOL_NAME,
            tool_arguments=tool_arguments,
            error_type=type(e).__name__,
            error=str(e),
        ).warning("Tool call failed while fetching artifact relationships")
        await handle_api_error(
            ctx, e, "get artifact relationships", method=_TOOL_NAME,
            recovery_hints={
                404: (
                    "(1) verify the identifier came from a recent semantic_search, grep_search, codebase_search, or fetch_artifacts result, "
                    "(2) call semantic_search or grep_search again to get a fresh identifier — the index may have changed, "
                    "(3) check that the artifact is a function/class (relationships are not available for non-symbol artifacts)"
                ),
                409: (
                    "(1) the identifier exists in more than one data source — see the candidate data sources in the Detail above; each one will resolve, "
                    "(2) retry get_artifact_relationships with data_source set to one candidate's Name or Id; if that data source isn't the one you want, retry with the next candidate, "
                    "(3) do NOT invent relation results — pick from the listed data sources"
                ),
            },
        )


def _build_relationships_dict(data: dict, data_source: Optional[str] = None) -> Dict[str, Any]:
    """Build a dict representation of an artifact relationships response.

    FastMCP serializes the dict via pydantic_core.to_json, which preserves UTF-8 —
    don't reintroduce json.dumps here, it would re-escape non-ASCII identifiers.

    ``data_source`` is the selector the caller passed (if any); when the source is not
    found it shapes the recovery hint so the agent can retry with another data source
    or drop the selector.
    """
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
        groups = [_build_group(group) for group in relationships]
        payload["relationships"] = groups

        counts = _build_counts(data.get("availableRelationshipCounts"))
        if counts is not None:
            payload["availableRelationshipCounts"] = counts
        payload["hint"] = _build_relationship_hint(found, mcp_profile, groups, counts, data_source)
    else:
        payload["hint"] = _build_relationship_hint(found, mcp_profile, [], None, data_source)

    return payload


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


def _build_counts(counts: Any) -> Dict[str, int] | None:
    """Preserve backend relationship counts that guide profile recovery."""
    if not isinstance(counts, dict):
        return None

    return {
        "outgoingCalls": int(counts.get("outgoingCalls") or counts.get("OutgoingCalls") or 0),
        "incomingCalls": int(counts.get("incomingCalls") or counts.get("IncomingCalls") or 0),
        "ancestors": int(counts.get("ancestors") or counts.get("Ancestors") or 0),
        "descendants": int(counts.get("descendants") or counts.get("Descendants") or 0),
        "references": int(counts.get("references") or counts.get("References") or 0),
    }


def _build_relationship_hint(
    found: bool,
    profile: str,
    groups: List[Dict[str, Any]],
    counts: Dict[str, int] | None,
    data_source: Optional[str] = None,
) -> str:
    """Give model-facing next-step guidance for graph traversal results."""
    if not found:
        if data_source:
            return (
                f'No relationship data was found for this identifier in data source "{data_source}". '
                "The identifier may belong to a different data source, or the data_source value may be "
                "wrong. Try: re-run with data_source set to a different candidate (use the `dataSource` "
                "name or id from your search results, or call get_data_sources), or omit data_source "
                "entirely — if the identifier is ambiguous you then get a 409 listing the candidate data "
                "sources. Otherwise re-run semantic_search or grep_search to get a fresh identifier."
            )
        return (
            "No relationship data was found for this identifier. Verify that the identifier came from "
            "a recent search/fetch result and points to a symbol-level artifact; otherwise re-run "
            "semantic_search or grep_search to get a fresh identifier."
        )

    if any(group["truncated"] for group in groups):
        return (
            "Some relationship groups are truncated. If the user asked for all usages or full graph "
            "scope, call get_artifact_relationships again with a higher max_count_per_type, then "
            "fetch promising related artifacts before making broad claims."
        )

    if all(group["totalCount"] == 0 for group in groups):
        return _build_empty_profile_hint(profile, counts)

    return (
        "Fetch promising related artifacts before making claims about behavior, concrete applications, "
        "or how broadly this mechanism is used."
    )


def _build_empty_profile_hint(profile: str, counts: Dict[str, int] | None) -> str:
    has_calls = (counts or {}).get("outgoingCalls", 0) > 0 or (counts or {}).get("incomingCalls", 0) > 0
    has_inheritance = (counts or {}).get("ancestors", 0) > 0 or (counts or {}).get("descendants", 0) > 0
    has_references = (counts or {}).get("references", 0) > 0

    if profile == "referencesOnly" and has_calls and has_inheritance:
        return (
            "No references were found for this profile, but call and inheritance relationships exist. "
            "Use callsOnly for function/method callers or callees, or inheritanceOnly for base classes, "
            "interfaces, overrides, implementations, or derived types."
        )
    if profile == "referencesOnly" and has_calls:
        return (
            "No references were found for this profile, but call relationships exist. Use callsOnly "
            "for function/method callers or callees. Use referencesOnly for where-used checks on "
            "types, containers, fields, commands, events, interfaces, and other non-call usage."
        )
    if profile == "referencesOnly" and has_inheritance:
        return (
            "No references were found for this profile, but inheritance relationships exist. Use "
            "inheritanceOnly for base classes, interfaces, overrides, implementations, or derived types."
        )
    if profile == "callsOnly" and has_references and has_inheritance:
        return (
            "No call relationships were found for this profile, but references and inheritance "
            "relationships exist. Try referencesOnly for where-used checks or inheritanceOnly for hierarchy."
        )
    if profile == "callsOnly" and has_references:
        return (
            "No call relationships were found for this profile, but references exist. Use referencesOnly "
            "for where-used checks on types, containers, fields, commands, events, interfaces, or mediated dispatch symbols."
        )
    if profile == "callsOnly" and has_inheritance:
        return (
            "No call relationships were found for this profile, but inheritance relationships exist. "
            "Use inheritanceOnly for base classes, interfaces, overrides, implementations, or derived types."
        )
    if profile == "allRelevant" and has_references:
        return (
            "No calls or inheritance relationships were found for allRelevant. allRelevant excludes "
            "references by design; use referencesOnly for where-used checks."
        )
    if profile == "inheritanceOnly" and has_calls and has_references:
        return (
            "No inheritance relationships were found for this profile. Use callsOnly for function "
            "callers/callees, or referencesOnly for where-used checks on types, commands, events, fields, containers, or interfaces."
        )
    if profile == "inheritanceOnly" and has_calls:
        return (
            "No inheritance relationships were found for this profile, but call relationships exist. "
            "Use callsOnly for function/method callers or callees."
        )
    if profile == "inheritanceOnly" and has_references:
        return (
            "No inheritance relationships were found for this profile, but references exist. Use "
            "referencesOnly for where-used checks on types, containers, fields, commands, events, interfaces, or mediated dispatch symbols."
        )

    return (
        "No relationships were found for this profile. Empty profile results do not mean the artifact "
        "has no graph data. Use callsOnly for function/method callers and callees, inheritanceOnly for "
        "hierarchy, allRelevant for calls plus inheritance, and referencesOnly for where-used checks on "
        "types, containers, fields, commands, events, interfaces, and other non-call usage."
    )
