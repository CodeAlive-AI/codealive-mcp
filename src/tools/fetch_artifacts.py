"""Fetch artifacts tool implementation."""

from typing import List, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import coerce_stringified_list, handle_api_error

# MCP tool/method name surfaced in every error/log message from this module.
_TOOL_NAME = "fetch_artifacts"

# Emitted alongside a <not_found> block so the agent never silently drops a requested
# artifact. Lists the concrete missing identifiers (in the block) and tells the agent to
# re-check those ids and retry the problematic ones. Parallel to search.py's _SEARCH_EMPTY_HINT.
_NOT_FOUND_HINT = (
    "{count} requested identifier(s) returned no accessible artifact and are listed under "
    "<not_found> above. Do NOT silently omit them from your answer. A <not_found> entry means "
    "the identifier did not resolve, or points outside the data sources this key can read — it "
    "is NOT proof the code is absent. Required next steps: (1) re-check those exact identifiers "
    "for typos or staleness; (2) re-run semantic_search or grep_search to obtain fresh, valid "
    "identifiers, then call fetch_artifacts again for those problematic ids; (3) if they still "
    "cannot be retrieved, explicitly tell the user which artifacts could not be fetched — do not "
    "pretend they don't exist."
)


async def fetch_artifacts(
    ctx: Context,
    identifiers: Union[str, List[str]],
    data_source: Optional[str] = None,
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

        data_source: Optional data-source Name or Id used to disambiguate an identifier that
                     exists in more than one data source. Copy the `dataSource.name` or
                     `dataSource.id` from the search result you want. Omit it for normal lookups;
                     if an identifier is ambiguous and you omit it, the backend returns a 409
                     listing the candidate data sources.

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

        Requested identifiers the backend could not resolve (or that are outside your
        access scope) are NOT dropped silently — they are listed in a
        <not_found count="N"> block with each concrete identifier, plus a hint to re-check
        those ids and retry the problematic ones.
        The `<relationships>` element shows the artifact's call graph:
        - **outgoing_calls**: functions this artifact calls (its dependencies)
        - **incoming_calls**: functions that call this artifact (its blast radius)
        Each shows up to 3 related artifacts with summaries. The `count` attribute
        gives the total. Relationships are omitted for non-function artifacts.

    Note:
        - Hard limit: 50 identifiers per request. Recommended: ≤20 to keep
          context size manageable and avoid flooding the conversation with code.
        - Identifiers must come from `semantic_search`, `grep_search`, or legacy `codebase_search` results.
        - Relationships shown here are a **preview** (up to 3 call relationships per direction).
          To retrieve the complete list, or to explore other relationship types
          (inheritance, references), use `get_artifact_relationships`.
    """
    # Coerce stringified JSON arrays sent by some MCP clients (Claude Code
    # deferred tools, LiveKit agents, etc.) into a proper Python list.
    identifiers = coerce_stringified_list(identifiers)

    # Normalize the optional selector: treat empty/whitespace-only as "no selector"
    # so we don't send a junk dataSource to the backend or echo it in the not-found hint.
    if data_source is not None:
        data_source = data_source.strip() or None

    if not identifiers:
        raise ToolError(f"[{_TOOL_NAME}] At least one identifier is required.")

    if len(identifiers) > 50:
        raise ToolError(f"[{_TOOL_NAME}] Maximum 50 identifiers per request. Please reduce the number of identifiers.")

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
        if data_source:
            body["dataSource"] = data_source

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
        return _build_artifacts_xml(artifacts_data, data_source=data_source, requested=identifiers)

    except (httpx.HTTPStatusError, Exception) as e:
        # handle_api_error raises ToolError → MCP response gets isError: true
        await handle_api_error(
            ctx, e, "fetch artifacts", method=_TOOL_NAME,
            recovery_hints={
                404: (
                    "(1) verify the identifiers came from a recent semantic_search, grep_search, or codebase_search call (do not invent them), "
                    "(2) re-run semantic_search or grep_search to get fresh identifiers — the index may have changed, "
                    "(3) for local repos in your working directory, use Read() on the file path instead"
                ),
                409: (
                    "(1) the identifier exists in more than one data source — see the candidate data sources in the Detail above; each one will resolve, "
                    "(2) retry fetch_artifacts with data_source set to one candidate's Name or Id; if that data source isn't the one you want, retry with the next candidate, "
                    "(3) do NOT invent a result — pick from the listed data sources"
                ),
            },
        )


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


def _escape_attr(value: str) -> str:
    """Escape a value for safe inclusion in an XML attribute (identifiers).

    Identifiers are caller-supplied — and in the MCP setting the "caller" is an
    untrusted LLM/user — and they are reflected straight back into the model's context
    (especially in the <not_found> block, which echoes any unmatched requested string via
    the backstop). An un-escaped quote or angle bracket would let a crafted identifier break
    out of the attribute and inject pseudo-XML. Mirrors the C# wrapper's
    XmlToolResultFormatter.EscapeAttr. Source-code *content* is intentionally NOT escaped
    (see <content>); this helper is for attribute values only.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_artifacts_xml(
    data: dict,
    data_source: str | None = None,
    requested: list[str] | None = None,
) -> str:
    """Build XML representation of fetched artifacts.

    Backend DTO: Identifier (string), Found (bool), Content (string?),
    ContentByteSize (long?), Relationships (object?).

    A requested identifier that the backend could not resolve — or that points outside
    the caller's access scope — comes back with ``found: false`` (older backends omit
    the flag and return ``content: null``). Such identifiers are NOT dropped silently:
    they are collected into a ``<not_found count="N">`` block listing each concrete
    identifier, followed by ``_NOT_FOUND_HINT`` telling the agent to re-check the ids and
    retry the problematic ones — otherwise the user silently loses a requested artifact.
    A ``found: true`` artifact with empty content is still rendered as a normal
    ``<artifact>`` (it was located; it just has no extractable body).

    Content is emitted raw (no HTML escaping) and wrapped between newlines so the
    LLM sees the source code exactly as-is.

    When ``data_source`` was supplied and nothing was found, an additional recovery hint
    suggests the identifier may live in a different data source, or the selector is wrong.
    ``requested`` is the original identifier list; it backstops the diff so an id the
    backend never echoed back is still surfaced as not-found.
    """
    xml_parts = ["<artifacts>"]

    has_any_relationships = False
    emitted = 0
    returned_identifiers: set[str] = set()
    not_found: list[str] = []
    artifacts = data.get("artifacts", [])
    for artifact in artifacts:
        identifier = artifact.get("identifier", "")
        if identifier:
            returned_identifiers.add(identifier)

        content = artifact.get("content")
        # Prefer the backend's explicit `found` flag; fall back to content-is-null for
        # older backends that don't emit it yet.
        found = artifact.get("found")
        is_missing = (found is False) if found is not None else (content is None)
        if is_missing:
            if identifier:
                not_found.append(identifier)
            continue

        emitted += 1
        content_byte_size = artifact.get("contentByteSize")

        attrs = [f'identifier="{_escape_attr(identifier)}"']
        if content_byte_size is not None:
            attrs.append(f'contentByteSize="{content_byte_size}"')

        start_line = artifact.get("startLine") or 1
        numbered_content = _add_line_numbers(content or "", start_line)

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

    # Backstop: any requested identifier the backend never echoed back is also missing.
    if requested:
        for identifier in requested:
            if identifier not in returned_identifiers and identifier not in not_found:
                not_found.append(identifier)

    if has_any_relationships:
        xml_parts.append(
            '  <hint>The <relationships> above are a preview (up to 3 calls per '
            'direction). To retrieve the full list, or to explore other relationship '
            'types (inheritance, references), call `get_artifact_relationships` with '
            'an artifact identifier.</hint>'
        )

    if not_found:
        xml_parts.append(f'  <not_found count="{len(not_found)}">')
        for identifier in not_found:
            xml_parts.append(f'    <artifact identifier="{_escape_attr(identifier)}"/>')
        xml_parts.append('  </not_found>')
        xml_parts.append(f'  <hint>{_NOT_FOUND_HINT.format(count=len(not_found))}</hint>')

    if emitted == 0 and data_source:
        xml_parts.append(
            f'  <hint>No artifacts were found in data source "{_escape_attr(data_source)}". The identifier may '
            'belong to a different data source, or the data_source value may be wrong. Try: '
            '(1) re-run fetch_artifacts with data_source set to a different candidate (use the '
            '`dataSource` name or id from your search results, or call get_data_sources), or '
            '(2) omit data_source entirely — if the identifier is ambiguous you then get a 409 '
            'that lists the candidate data sources to choose from.</hint>'
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
                        f'        <call identifier="{_escape_attr(call_id)}" summary="{_escape_attr(summary)}"/>'
                    )
                else:
                    call_elements.append(f'        <call identifier="{_escape_attr(call_id)}"/>')

        parts.append(f'      <{tag} count="{count}">')
        parts.extend(call_elements)
        parts.append(f'      </{tag}>')

    if not parts:
        return None

    return "    <relationships>\n" + "\n".join(parts) + "\n    </relationships>"
