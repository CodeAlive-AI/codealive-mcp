"""Response transformation utilities to convert API responses to compact JSON."""

import json
from typing import Dict, Any, List, Optional


# Hint embedded in every search response. Tells the agent that
# `description` is only a pointer for triage and that the source of truth
# is the full content returned by `fetch_artifacts` (or a local `Read()`
# for repos in the working directory).
_SEARCH_HINT = (
    "`description` is only a triage hint to help you decide which artifacts "
    "deserve a closer look — DO NOT base your understanding of the code on it. "
    "For every artifact you consider relevant you MUST load the real source "
    "via `fetch_artifacts` (using the `identifier`) for external repos, or "
    "`Read()` on the file path for repos in the local working directory. "
    "Treat only the `content` returned by `fetch_artifacts` (or `Read()`) as "
    "ground truth."
)

_GREP_HINT = (
    "Line previews in `matches` are only search evidence. Before reasoning about "
    "behavior, load the full source via `fetch_artifacts` for external repos or "
    "`Read()` on the local path. Treat only the full source as ground truth."
)


def transform_search_response_to_json(
    search_results: Dict[str, Any],
) -> str:
    """
    Transform search API response to a compact JSON string for LLM consumption.

    Args:
        search_results: Raw search API response from CodeAlive

    Returns:
        Compact JSON string with the search results and an embedded hint
        instructing the agent to fetch real content via ``fetch_artifacts``.
    """
    if not isinstance(search_results, dict) or "results" not in search_results:
        return json.dumps(
            {"results": [], "hint": _SEARCH_HINT}, separators=(",", ":")
        )

    results = search_results.get("results", [])

    formatted_results = _format_results(results or [])

    return json.dumps(
        {"results": formatted_results, "hint": _SEARCH_HINT},
        separators=(",", ":"),
    )


def transform_grep_response_to_json(grep_results: Dict[str, Any]) -> str:
    """Transform canonical grep response to compact JSON for LLM consumption."""
    if not isinstance(grep_results, dict) or "results" not in grep_results:
        return json.dumps(
            {"results": [], "hint": _GREP_HINT}, separators=(",", ":")
        )

    formatted_results: List[Dict[str, Any]] = []
    for result in grep_results.get("results", []) or []:
        kind = result.get("kind", "")
        if kind == "Folder":
            continue

        path = _extract_path_from_result(result)
        if not path:
            continue

        item = _build_result_dict(path, result)
        if result.get("matchCount") is not None:
            item["matchCount"] = result["matchCount"]
        if result.get("matches"):
            item["matches"] = [
                {
                    "lineNumber": match.get("lineNumber"),
                    "startColumn": match.get("startColumn"),
                    "endColumn": match.get("endColumn"),
                    "lineText": match.get("lineText"),
                }
                for match in result["matches"]
            ]
        formatted_results.append(item)

    return json.dumps(
        {"results": formatted_results, "hint": _GREP_HINT},
        separators=(",", ":"),
    )


def _format_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted_results: List[Dict[str, Any]] = []
    for result in results:
        kind = result.get("kind", "")

        if kind == "Folder":
            continue

        path = _extract_path_from_result(result)
        if not path:
            continue

        formatted_results.append(_build_result_dict(path, result))

    return formatted_results


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
