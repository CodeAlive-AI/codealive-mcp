"""Response transformation utilities to convert API responses to XML format."""

from typing import Dict, Any, List, Tuple, Optional
from collections import OrderedDict
import html


def transform_search_response_to_xml(
    search_results: Dict[str, Any],
    include_content: bool = False
) -> str:
    """
    Transform search API response to XML format for better LLM processing.

    XML format is more structured and often better for LLMs to parse.
    Token reduction: ~60-90% compared to raw JSON responses.

    Args:
        search_results: Raw search API response from CodeAlive
        include_content: Whether to include full file content in results

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

    # Build XML output
    if include_content:
        return _build_xml_with_content(file_groups)
    else:
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
        result_info = _build_result_info(result, include_content=True)

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
        # Extract path from identifier (format: "owner/repo::path::chunk")
        parts = result["identifier"].split("::")
        if len(parts) >= 2:
            return parts[1]
    return None


def _build_result_info(result: Dict, include_content: bool = False) -> Dict:
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

    # Include content if requested
    if include_content:
        if result.get("content"):
            result_info["content"] = result["content"]
        elif result.get("snippet"):
            result_info["snippet"] = result["snippet"]

    return result_info


def _build_xml_without_content(file_groups: OrderedDict) -> str:
    """Build XML representation without file content."""
    xml_parts = ["<results>"]

    # Create self-closing tags for each result
    for path, results in file_groups.items():
        for result in results:
            attrs = _build_xml_attributes(path, result)
            xml_parts.append(f'  <search_result {" ".join(attrs)} />')

    xml_parts.append("</results>")
    return "\n".join(xml_parts)


def _build_xml_with_content(file_groups: OrderedDict) -> str:
    """Build XML representation including file content."""
    xml_parts = ["<results>"]

    # Group by file and include content
    for path, results in file_groups.items():
        xml_content = _build_file_xml_with_content(path, results)
        if xml_content:
            xml_parts.extend(xml_content)

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

    return attrs


def _build_file_xml_with_content(path: str, results: List[Dict]) -> List[str]:
    """Build XML for a single file including its content."""
    # Collect all content from this file
    content_parts = []
    all_lines = []
    has_content = False

    for result in sorted(results, key=lambda x: x.get("start_line", 0)):
        if result.get("content"):
            content_parts.append(result["content"])
            has_content = True
        elif result.get("snippet"):
            content_parts.append(result["snippet"])
            has_content = True

        if result.get("start_line") is not None:
            all_lines.append(result["start_line"])
        if result.get("end_line") is not None:
            all_lines.append(result["end_line"])

    if not has_content:
        return []

    xml_parts = []

    # Build attributes with line range if available
    if all_lines:
        start_line = min(all_lines)
        end_line = max(all_lines)
        attrs = f'path="{html.escape(path)}" startLine="{start_line}" endLine="{end_line}"'
    else:
        attrs = f'path="{html.escape(path)}"'

    xml_parts.append(f'  <search_result {attrs}>')

    # Add formatted content
    combined_content = "\n".join(content_parts)
    formatted_content = _format_content_with_line_numbers(
        combined_content,
        all_lines[0] if all_lines and results[0].get("start_line") is not None else None
    )
    xml_parts.append(formatted_content)
    xml_parts.append("  </search_result>")

    return xml_parts


def _format_content_with_line_numbers(content: str, start_line: Optional[int]) -> str:
    """Format content with line numbers if available."""
    escaped_content = html.escape(content)

    if start_line is not None and "\n" in content:
        lines = escaped_content.split("\n")
        numbered_lines = []
        current_line = start_line
        for line in lines:
            numbered_lines.append(f"   {current_line}|{line}")
            current_line += 1
        return "\n".join(numbered_lines)
    else:
        # No line numbers - just indent
        lines = escaped_content.split("\n")
        return "\n".join(f"   {line}" for line in lines)