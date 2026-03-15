"""Response transformation utilities to convert API responses to XML format."""

from typing import Dict, Any, List, Optional
from collections import OrderedDict
import html


def transform_search_response_to_xml(
    search_results: Dict[str, Any],
) -> str:
    """
    Transform search API response to XML format for better LLM processing.

    XML format is more structured and often better for LLMs to parse.
    Token reduction: ~60-90% compared to raw JSON responses.

    Args:
        search_results: Raw search API response from CodeAlive

    Returns:
        Transformed XML response string with search results
    """
    if not isinstance(search_results, dict) or "results" not in search_results:
        return "<results></results>"

    results = search_results.get("results", [])
    if not results:
        return "<results></results>"

    # Process and group results
    file_groups = _group_results_by_file(results)

    # Build XML output (always without content)
    return _build_xml_without_content(file_groups)


def _group_results_by_file(results: List[Dict]) -> OrderedDict:
    """
    Group search results by file path while preserving order.

    Args:
        results: List of search result dictionaries

    Returns:
        OrderedDict mapping file paths to their results
    """
    file_groups = OrderedDict()

    for result in results:
        kind = result.get("kind", "")

        # Skip folders - they don't provide value
        if kind == "Folder":
            continue

        # Extract path
        path = _extract_path_from_result(result)
        if not path:
            continue

        # Build result info
        result_info = _build_result_info(result)

        # Preserve order by creating list if path not seen before
        if path not in file_groups:
            file_groups[path] = []
        file_groups[path].append(result_info)

    return file_groups


def _extract_path_from_result(result: Dict) -> Optional[str]:
    """Extract file path from a search result."""
    if result.get("location", {}).get("path"):
        return result["location"]["path"]
    elif result.get("identifier"):
        # Extract path from identifier (format: "{owner/repo}::{path}::{symbol_or_chunk}")
        parts = result["identifier"].split("::")
        if len(parts) >= 2:
            return parts[1]
    return None


def _build_result_info(result: Dict) -> Dict:
    """Build a structured info dict from a search result."""
    result_info = {
        "kind": result.get("kind", "")
    }

    # Add line numbers for symbols
    if result.get("location", {}).get("range"):
        start = result["location"]["range"].get("start", {})
        end = result["location"]["range"].get("end", {})
        if start.get("line") is not None and end.get("line") is not None:
            result_info["start_line"] = start["line"]
            result_info["end_line"] = end["line"]

    # Add description if present
    if result.get("description"):
        result_info["description"] = result["description"]

    # Add snippet if present (fallback content when description is missing)
    if result.get("snippet"):
        result_info["snippet"] = result["snippet"]

    # Add contentByteSize if present
    if result.get("contentByteSize") is not None:
        result_info["contentByteSize"] = result["contentByteSize"]

    # Add identifier if present
    if result.get("identifier"):
        result_info["identifier"] = result["identifier"]

    return result_info


def _build_xml_without_content(file_groups: OrderedDict) -> str:
    """Build XML representation without file content."""
    xml_parts = ["<results>"]

    for path, results in file_groups.items():
        for result in results:
            attrs = _build_xml_attributes(path, result)
            description = result.get("description")
            snippet = result.get("snippet")
            if description:
                xml_parts.append(f'  <search_result {" ".join(attrs)}>')
                xml_parts.append(f'    <description>{html.escape(description)}</description>')
                xml_parts.append(f'  </search_result>')
            elif snippet:
                xml_parts.append(f'  <search_result {" ".join(attrs)}>')
                xml_parts.append(f'    <content truncated="true">{html.escape(snippet)}</content>')
                xml_parts.append(f'  </search_result>')
            else:
                xml_parts.append(f'  <search_result {" ".join(attrs)} />')

    xml_parts.append("</results>")
    return "\n".join(xml_parts)


def _build_xml_attributes(path: str, result: Dict) -> List[str]:
    """Build XML attribute strings for a search result."""
    attrs = [f'path="{html.escape(path)}"']

    if result.get("start_line") is not None:
        attrs.append(f'startLine="{result["start_line"]}"')
    if result.get("end_line") is not None:
        attrs.append(f'endLine="{result["end_line"]}"')
    if result.get("kind"):
        attrs.append(f'kind="{html.escape(result["kind"])}"')
    if result.get("identifier"):
        attrs.append(f'identifier="{html.escape(result["identifier"])}"')
    if result.get("contentByteSize") is not None:
        attrs.append(f'contentByteSize="{result["contentByteSize"]}"')

    return attrs
