"""Artifact relationships tool implementation."""

import html
from typing import Optional
from urllib.parse import urljoin

import httpx
from fastmcp import Context

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
    profile: str = "callsOnly",
    max_count_per_type: int = 50,
) -> str:
    """
    Retrieve relationship groups for a single artifact by profile.

    Use this tool to explore an artifact's call graph, inheritance hierarchy,
    or references. This is a drill-down tool — use it AFTER `codebase_search`
    or `fetch_artifacts` when you need to understand how an artifact relates
    to others in the codebase.

    Args:
        identifier: Fully qualified artifact identifier from search or fetch results.
        profile: Relationship profile to expand. One of:
                 - "callsOnly" (default): outgoing and incoming calls
                 - "inheritanceOnly": ancestors and descendants
                 - "allRelevant": calls + inheritance (4 groups)
                 - "referencesOnly": symbol references
        max_count_per_type: Maximum related artifacts per relationship type (1–1000, default 50).

    Returns:
        XML with grouped relationships:
        <artifact_relationships sourceIdentifier="..." profile="callsOnly" found="true">
          <relationship_group type="outgoing_calls" totalCount="57" returnedCount="50" truncated="true">
            <artifact identifier="..." filePath="src/Data/Repo.cs" startLine="88" shortSummary="Stores data"/>
          </relationship_group>
          <relationship_group type="incoming_calls" totalCount="3" returnedCount="3" truncated="false">
            <artifact identifier="..." filePath="src/Services/Worker.cs" startLine="142"/>
          </relationship_group>
        </artifact_relationships>

        When the artifact is not found or inaccessible:
        <artifact_relationships sourceIdentifier="..." profile="callsOnly" found="false"/>
    """
    if not identifier:
        return f"<error>[{_TOOL_NAME}] Artifact identifier is required.</error>"

    api_profile = PROFILE_MAP.get(profile)
    if api_profile is None:
        supported = ", ".join(PROFILE_MAP.keys())
        return f'<error>[{_TOOL_NAME}] Unsupported profile "{profile}". Use one of: {supported}</error>'

    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)
        headers = {"Authorization": f"Bearer {api_key}"}

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

        return _build_relationships_xml(response.json())

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(
            ctx, e, "get artifact relationships", method=_TOOL_NAME
        )
        return f"<error>{error_msg}</error>"


def _build_relationships_xml(data: dict) -> str:
    """Build XML representation of artifact relationships response."""
    raw_source_id = data.get("sourceIdentifier") or ""
    raw_profile = data.get("profile") or ""
    found = data.get("found", False)

    # Map profile back to MCP-friendly name
    mcp_profile = raw_profile
    for mcp_name, api_name in PROFILE_MAP.items():
        if api_name == raw_profile:
            mcp_profile = mcp_name
            break

    source_id_attr = html.escape(raw_source_id)
    profile_attr = html.escape(mcp_profile)

    if not found:
        return f'<artifact_relationships sourceIdentifier="{source_id_attr}" profile="{profile_attr}" found="false"/>'

    relationships = data.get("relationships") or []
    if not relationships:
        return f'<artifact_relationships sourceIdentifier="{source_id_attr}" profile="{profile_attr}" found="true"/>'

    xml_parts = [
        f'<artifact_relationships sourceIdentifier="{source_id_attr}" profile="{profile_attr}" found="true">'
    ]

    for group in relationships:
        relationship_type = group.get("relationType", "")
        mcp_type = RELATIONSHIP_TYPE_MAP.get(relationship_type, relationship_type.lower())
        total_count = group.get("totalCount") or 0
        returned_count = group.get("returnedCount") or 0
        truncated = str(bool(group.get("truncated"))).lower()

        xml_parts.append(
            f'  <relationship_group type="{html.escape(mcp_type)}" '
            f'totalCount="{total_count}" returnedCount="{returned_count}" '
            f'truncated="{truncated}">'
        )

        for item in group.get("items", []):
            attrs = [f'identifier="{html.escape(item.get("identifier") or "")}"']

            file_path = item.get("filePath")
            if file_path is not None:
                attrs.append(f'filePath="{html.escape(file_path)}"')

            start_line = item.get("startLine")
            if start_line is not None:
                attrs.append(f'startLine="{start_line}"')

            short_summary = item.get("shortSummary")
            if short_summary is not None:
                attrs.append(f'shortSummary="{html.escape(short_summary)}"')

            xml_parts.append(f'    <artifact {" ".join(attrs)}/>')

        xml_parts.append('  </relationship_group>')

    xml_parts.append('</artifact_relationships>')
    return "\n".join(xml_parts)
