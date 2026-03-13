"""Fetch artifacts tool implementation."""

from typing import List
from urllib.parse import urljoin

import html
import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error


async def fetch_artifacts(
    ctx: Context,
    identifiers: List[str],
) -> str:
    """
    Retrieve the full content of code artifacts by their identifiers.

    Use this tool AFTER `codebase_search` to get the complete source code for results
    you need to inspect. The `identifier` values come from the search results.

    This is the recommended way to retrieve content for **external repositories** that
    you cannot access via local file reads. For repositories in your working directory,
    prefer using `Read()` on the local files instead.

    Args:
        identifiers: List of artifact identifiers from search results (max 20).
                     These are the `identifier` attribute values from `codebase_search` XML results.

                     Identifier format examples:
                       Symbol:  "my-org/backend::src/services/auth.py::AuthService.validate_token(token: str)"
                       File:    "my-org/backend::src/services/auth.py"
                       Chunk:   "my-org/backend::README.md::0042"

    Returns:
        XML with full content for each found artifact:
        <artifacts>
          <artifact identifier="..." contentByteSize="...">content here</artifact>
        </artifacts>
        Only artifacts with content are included in the response.

    Note:
        - Maximum 20 identifiers per request to avoid excessive payloads.
        - Identifiers must come from `codebase_search` results.
    """
    if not identifiers:
        return "<error>At least one identifier is required.</error>"

    if len(identifiers) > 20:
        return "<error>Maximum 20 identifiers per request. Please reduce the number of identifiers.</error>"

    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)
        headers = {"Authorization": f"Bearer {api_key}"}

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
        error_msg = await handle_api_error(ctx, e, "fetch artifacts")
        return f"<error>{error_msg}</error>"


def _build_artifacts_xml(data: dict) -> str:
    """Build XML representation of fetched artifacts.

    Backend DTO: Identifier (string), Content (string?), ContentByteSize (long?).
    Content is null when artifact is not found or has no content.
    Only artifacts with content are included in output.
    """
    xml_parts = ["<artifacts>"]

    artifacts = data.get("artifacts", [])
    for artifact in artifacts:
        content = artifact.get("content")
        if content is None:
            continue

        identifier = html.escape(artifact.get("identifier", ""))
        content_byte_size = artifact.get("contentByteSize")

        attrs = [f'identifier="{identifier}"']
        if content_byte_size is not None:
            attrs.append(f'contentByteSize="{content_byte_size}"')
        escaped_content = html.escape(content)
        xml_parts.append(f'  <artifact {" ".join(attrs)}>{escaped_content}</artifact>')

    xml_parts.append("</artifacts>")
    return "\n".join(xml_parts)
