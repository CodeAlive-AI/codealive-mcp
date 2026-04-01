"""Artifact relations tool implementation."""

import html
from typing import Optional
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error

# Map MCP profile names to backend enum values
PROFILE_MAP = {
    "callsOnly": "CallsOnly",
    "inheritanceOnly": "InheritanceOnly",
    "allRelevant": "AllRelevant",
    "referencesOnly": "ReferencesOnly",
}

# Backend relation type to MCP-friendly snake_case
RELATION_TYPE_MAP = {
    "OutgoingCalls": "outgoing_calls",
    "IncomingCalls": "incoming_calls",
    "Ancestors": "ancestors",
    "Descendants": "descendants",
    "References": "references",
}


async def get_artifact_relations(
    ctx: Context,
    identifier: str,
    profile: str = "callsOnly",
    max_count_per_type: int = 50,
) -> str:
    """
    Retrieve relation groups for a single artifact by profile.

    Use this tool to explore an artifact's call graph, inheritance hierarchy,
    or references. This is a drill-down tool — use it AFTER `codebase_search`
    or `fetch_artifacts` when you need to understand how an artifact relates
    to others in the codebase.

    Args:
        identifier: Fully qualified artifact identifier from search or fetch results.
        profile: Relation profile to expand. One of:
                 - "callsOnly" (default): outgoing and incoming calls
                 - "inheritanceOnly": ancestors and descendants
                 - "allRelevant": calls + inheritance (4 groups)
                 - "referencesOnly": symbol references
        max_count_per_type: Maximum related artifacts per relation type (1–1000, default 50).

    Returns:
        XML with grouped relations:
        <artifact_relations sourceIdentifier="..." profile="callsOnly" found="true">
          <relation_group type="outgoing_calls" totalCount="57" returnedCount="50" truncated="true">
            <artifact identifier="..." filePath="src/Data/Repo.cs" startLine="88" shortSummary="Stores data"/>
          </relation_group>
          <relation_group type="incoming_calls" totalCount="3" returnedCount="3" truncated="false">
            <artifact identifier="..." filePath="src/Services/Worker.cs" startLine="142"/>
          </relation_group>
        </artifact_relations>

        When the artifact is not found or inaccessible:
        <artifact_relations sourceIdentifier="..." profile="callsOnly" found="false"/>
    """
    if not identifier:
        return "<error>Artifact identifier is required.</error>"

    api_profile = PROFILE_MAP.get(profile)
    if api_profile is None:
        supported = ", ".join(PROFILE_MAP.keys())
        return f'<error>Unsupported profile "{profile}". Use one of: {supported}</error>'

    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)
        headers = {"Authorization": f"Bearer {api_key}"}

        body = {
            "identifier": identifier,
            "profile": api_profile,
            "maxCountPerType": max_count_per_type,
        }

        await ctx.info(f"Fetching {profile} relations for artifact")

        full_url = urljoin(context.base_url, "/api/search/artifact-relations")
        request_id = log_api_request("POST", full_url, headers, body=body)

        response = await context.client.post(
            "/api/search/artifact-relations", json=body, headers=headers
        )

        log_api_response(response, request_id)
        response.raise_for_status()

        return _build_relations_xml(response.json())

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(ctx, e, "get artifact relations")
        return f"<error>{error_msg}</error>"


def _build_relations_xml(data: dict) -> str:
    """Build XML representation of artifact relations response."""
    source_id = html.escape(data.get("sourceIdentifier", ""))
    profile = html.escape(data.get("profile", ""))
    found = data.get("found", False)

    # Map profile back to MCP-friendly name
    mcp_profile = profile
    for mcp_name, api_name in PROFILE_MAP.items():
        if api_name == profile:
            mcp_profile = mcp_name
            break

    if not found:
        return f'<artifact_relations sourceIdentifier="{source_id}" profile="{mcp_profile}" found="false"/>'

    relations = data.get("relations", [])
    if not relations:
        return f'<artifact_relations sourceIdentifier="{source_id}" profile="{mcp_profile}" found="true"/>'

    xml_parts = [
        f'<artifact_relations sourceIdentifier="{source_id}" profile="{mcp_profile}" found="true">'
    ]

    for group in relations:
        relation_type = group.get("relationType", "")
        mcp_type = RELATION_TYPE_MAP.get(relation_type, relation_type.lower())
        total_count = group.get("totalCount", 0)
        returned_count = group.get("returnedCount", 0)
        truncated = str(group.get("truncated", False)).lower()

        xml_parts.append(
            f'  <relation_group type="{html.escape(mcp_type)}" '
            f'totalCount="{total_count}" returnedCount="{returned_count}" '
            f'truncated="{truncated}">'
        )

        for item in group.get("items", []):
            attrs = [f'identifier="{html.escape(item.get("identifier", ""))}"']

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

        xml_parts.append('  </relation_group>')

    xml_parts.append('</artifact_relations>')
    return "\n".join(xml_parts)
