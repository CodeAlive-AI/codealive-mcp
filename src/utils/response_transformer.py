"""Response transformation utilities to convert API responses to compact JSON."""

import json
from typing import Dict, Any, List, Optional


def transform_search_response_to_json(
    search_results: Dict[str, Any],
) -> str:
    """
    Transform search API response to a compact JSON string for LLM consumption.

    Args:
        search_results: Raw search API response from CodeAlive

    Returns:
        Compact JSON string with the search results.
    """
    if not isinstance(search_results, dict) or "results" not in search_results:
        return '{"results":[]}'

    results = search_results.get("results", [])
    if not results:
        return '{"results":[]}'

    formatted_results: List[Dict[str, Any]] = []
    for result in results:
        kind = result.get("kind", "")

        # Skip folders - they don't provide value
        if kind == "Folder":
            continue

        path = _extract_path_from_result(result)
        if not path:
            continue

        formatted_results.append(_build_result_dict(path, result))

    return json.dumps({"results": formatted_results}, separators=(",", ":"))


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


def _build_result_dict(path: str, result: Dict) -> Dict[str, Any]:
    """Build a JSON-serializable dict from a search result."""
    info: Dict[str, Any] = {"path": path}

    # Add line numbers for symbols
    range_obj = result.get("location", {}).get("range") if result.get("location") else None
    if range_obj:
        start = range_obj.get("start", {}) or {}
        end = range_obj.get("end", {}) or {}
        if start.get("line") is not None:
            info["startLine"] = start["line"]
        if end.get("line") is not None:
            info["endLine"] = end["line"]

    if result.get("kind"):
        info["kind"] = result["kind"]

    if result.get("identifier"):
        info["identifier"] = result["identifier"]

    if result.get("contentByteSize") is not None:
        info["contentByteSize"] = result["contentByteSize"]

    if result.get("description"):
        info["description"] = result["description"]
    elif result.get("snippet"):
        # Snippet acts as a fallback when no description is available
        info["snippet"] = result["snippet"]

    return info
