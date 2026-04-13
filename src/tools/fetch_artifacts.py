"""Fetch artifacts tool implementation."""

from typing import List, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import coerce_stringified_list, handle_api_error

# MCP tool/method name surfaced in every error/log message from this module.
_TOOL_NAME = "fetch_artifacts"


async def fetch_artifacts(
    ctx: Context,
    identifiers: Union[str, List[str]],
) -> str:
    """
    Retrieve the full content of code artifacts by their identifiers.

    Use this tool AFTER `semantic_search`, `grep_search`, or legacy `codebase_search`
    to get the complete source code for results you need to inspect. The `identifier`
    values come from the search results.

    This is the recommended way to retrieve content for **external repositories** that
    you cannot access via local file reads. For repositories in your working directory,
    prefer using `Read()` on the local files instead.

    Args:
        identifiers: List of artifact identifiers from search results (max 20).
                     These are the `identifier` attribute values from `semantic_search`,
                     `grep_search`, or legacy `codebase_search` results.

                     Identifier format examples:
                       Symbol:  "my-org/backend::src/services/auth.py::AuthService.validate_token(token: str)"
                       File:    "my-org/backend::src/services/auth.py"
                       Chunk:   "my-org/backend::README.md::0042"

    Returns:
        XML with full content and call relationships for each found artifact:
        <artifacts>
          <artifact identifier="..." contentByteSize="...">
            <content>numbered source code</content>
            <relationships>
              <outgoing_calls count="12">
                <call identifier="org/repo::path::Symbol" summary="Does X..."/>
              </outgoing_calls>
              <incoming_calls count="3">
                <call identifier="org/repo::path::Caller" summary="Calls this to..."/>
              </incoming_calls>
            </relationships>
          </artifact>
        </artifacts>

        Only artifacts with content are included in the response.
        The `<relationships>` element shows the artifact's call graph:
        - **outgoing_calls**: functions this artifact calls (its dependencies)
        - **incoming_calls**: functions that call this artifact (its blast radius)
        Each shows up to 3 related artifacts with summaries. The `count` attribute
        gives the total. Relationships are omitted for non-function artifacts.

    Note:
        - Maximum 20 identifiers per request to avoid excessive payloads.
        - Identifiers must come from `semantic_search`, `grep_search`, or legacy `codebase_search` results.
        - Relationships shown here are a **preview** (up to 3 call relationships per direction).
          To retrieve the complete list, or to explore other relationship types
          (inheritance, references), use `get_artifact_relationships`.
    """
    # Coerce stringified JSON arrays sent by some MCP clients (Claude Code
    # deferred tools, LiveKit agents, etc.) into a proper Python list.
    identifiers = coerce_stringified_list(identifiers)

    if not identifiers:
        return f"<error>[{_TOOL_NAME}] At least one identifier is required.</error>"

    if len(identifiers) > 20:
        return f"<error>[{_TOOL_NAME}] Maximum 20 identifiers per request. Please reduce the number of identifiers.</error>"

    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-CodeAlive-Integration": "mcp",
            "X-CodeAlive-Tool": "fetch_artifacts",
            "X-CodeAlive-Client": "fastmcp",
        }

        body = {"identifiers": identifiers}

        await ctx.info(f"Fetching {len(identifiers)} artifact(s)")

        # Log the request
        full_url = urljoin(context.base_url, "/api/search/artifacts")
        request_id = log_api_request("POST", full_url, headers, body=body)

        # Make API request
        response = await context.client.post(
            "/api/search/artifacts", json=body, headers=headers
        )

        # Log the response
        log_api_response(response, request_id)

        response.raise_for_status()

        artifacts_data = response.json()

        # Build XML output
        return _build_artifacts_xml(artifacts_data)

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(
            ctx, e, "fetch artifacts", method=_TOOL_NAME,
            recovery_hints={
                404: (
                    "(1) verify the identifiers came from a recent semantic_search, grep_search, or codebase_search call (do not invent them), "
                    "(2) re-run semantic_search or grep_search to get fresh identifiers — the index may have changed, "
                    "(3) for local repos in your working directory, use Read() on the file path instead"
                ),
            },
        )
        return f"<error>{error_msg}</error>"


def _add_line_numbers(content: str, start_line: int = 1) -> str:
    """Add line numbers to content for easier navigation.

    Returns content with each line prefixed by its line number,
    right-aligned and separated by ' | '.

    Args:
        content: The text content to number.
        start_line: 1-based line number for the first line (default 1).
    """
    if not content:
        return content

    lines = content.split("\n")
    width = len(str(start_line + len(lines) - 1))
    numbered = [f"{start_line + i:>{width}} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)


def _build_artifacts_xml(data: dict) -> str:
    """Build XML representation of fetched artifacts.

    Backend DTO: Identifier (string), Content (string?), ContentByteSize (long?),
    Relationships (object?).
    Content is null when artifact is not found or has no content.
    Only artifacts with content are included in output.

    Content is emitted raw (no HTML escaping) and wrapped between newlines so the
    LLM sees the source code exactly as-is.
    """
    xml_parts = ["<artifacts>"]

    has_any_relationships = False
    artifacts = data.get("artifacts", [])
    for artifact in artifacts:
        content = artifact.get("content")
        if content is None:
            continue

        identifier = artifact.get("identifier", "")
        content_byte_size = artifact.get("contentByteSize")

        attrs = [f'identifier="{identifier}"']
        if content_byte_size is not None:
            attrs.append(f'contentByteSize="{content_byte_size}"')

        start_line = artifact.get("startLine") or 1
        numbered_content = _add_line_numbers(content, start_line)

        xml_parts.append(f'  <artifact {" ".join(attrs)}>')
        xml_parts.append('    <content>')
        xml_parts.append(numbered_content)
        xml_parts.append('    </content>')

        relationships = artifact.get("relationships")
        if relationships is not None:
            relationships_xml = _build_relationships_xml(relationships)
            if relationships_xml:
                xml_parts.append(relationships_xml)
                if _has_any_calls(relationships):
                    has_any_relationships = True

        xml_parts.append('  </artifact>')

    if has_any_relationships:
        xml_parts.append(
            '  <hint>The <relationships> above are a preview (up to 3 calls per '
            'direction). To retrieve the full list, or to explore other relationship '
            'types (inheritance, references), call `get_artifact_relationships` with '
            'an artifact identifier.</hint>'
        )

    xml_parts.append("</artifacts>")
    return "\n".join(xml_parts)


def _has_any_calls(relationships: dict) -> bool:
    """Return True if relationships contain at least one outgoing or incoming call."""
    for rel_type in ("outgoingCalls", "incomingCalls"):
        count = relationships.get(f"{rel_type}Count")
        if count and count > 0:
            return True
    return False


def _build_relationships_xml(relationships: dict) -> str | None:
    """Build XML for artifact call relationships.

    Returns None if no relationship types are present.
    Identifiers and summaries are emitted raw (no HTML escaping).
    """
    parts = []

    for rel_type in ("outgoingCalls", "incomingCalls"):
        tag = "outgoing_calls" if rel_type == "outgoingCalls" else "incoming_calls"
        count = relationships.get(f"{rel_type}Count")
        calls = relationships.get(rel_type)

        if count is None:
            continue

        call_elements = []
        if calls:
            for call in calls:
                call_id = call.get("identifier") or ""
                summary = call.get("summary")
                if summary is not None:
                    call_elements.append(
                        f'        <call identifier="{call_id}" summary="{summary}"/>'
                    )
                else:
                    call_elements.append(f'        <call identifier="{call_id}"/>')

        parts.append(f'      <{tag} count="{count}">')
        parts.extend(call_elements)
        parts.append(f'      </{tag}>')

    if not parts:
        return None

    return "    <relationships>\n" + "\n".join(parts) + "\n    </relationships>"
