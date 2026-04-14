#!/usr/bin/env python3
"""
CodeAlive Fetch - Retrieve full content for code artifacts

Usage:
    python fetch.py <identifier1> [identifier2...]

Examples:
    # Fetch a single artifact (symbol)
    python fetch.py "my-org/backend::src/services/auth.py::AuthService.validate_token(token: str)"

    # Fetch a file
    python fetch.py "my-org/backend::src/services/auth.py"

    # Fetch multiple artifacts
    python fetch.py "my-org/backend::src/auth.py::login" "my-org/backend::src/utils.py::helper"

Identifiers come from semantic/grep search results (the `identifier` field).
The format is: {owner/repo}::{path}::{symbol} (for symbols/chunks)
               {owner/repo}::{path} (for files)

Maximum 20 identifiers per request.
"""

import sys
import json
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from api_client import CodeAliveClient


def _add_line_numbers(content: str, start_line: int = 1) -> str:
    """Add line numbers to content for easier navigation."""
    if not content:
        return content
    lines = content.split("\n")
    width = len(str(start_line + len(lines) - 1))
    numbered = [f"{start_line + i:>{width}} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)


def _has_any_calls(relationships: dict) -> bool:
    """True if a relationships preview has at least one outgoing/incoming call."""
    for key in ("outgoingCallsCount", "incomingCallsCount"):
        count = relationships.get(key)
        if count and count > 0:
            return True
    return False


def _format_relationships_preview(relationships: dict) -> list:
    """Format the inline preview of call relationships returned with each artifact.

    Returns a list of output lines (possibly empty).
    """
    lines: list = []

    for direction, key, label in (
        ("outgoing", "outgoingCalls", "↗ outgoing_calls"),
        ("incoming", "incomingCalls", "↙ incoming_calls"),
    ):
        count = relationships.get(f"{key}Count")
        if count is None:
            continue
        calls = relationships.get(key) or []

        lines.append(f"  {label} ({count}):")
        if not calls:
            lines.append("    (none in preview)")
            continue
        for call in calls:
            ident = call.get("identifier", "")
            summary = call.get("summary")
            if summary:
                lines.append(f"    • {ident}")
                lines.append(f"        📝 {summary}")
            else:
                lines.append(f"    • {ident}")

    return lines


def format_artifacts(data: dict) -> str:
    """Format fetched artifacts for display."""
    artifacts = data.get("artifacts", [])
    if not artifacts:
        return "No artifacts returned."

    output = []
    count = 0
    has_any_relationships = False

    for artifact in artifacts:
        content = artifact.get("content")
        if content is None:
            continue

        count += 1
        identifier = artifact.get("identifier", "unknown")
        content_byte_size = artifact.get("contentByteSize")

        size_str = f" ({content_byte_size} bytes)" if content_byte_size else ""
        output.append(f"\n{'='*60}")
        output.append(f"📄 {identifier}{size_str}")
        output.append(f"{'='*60}")
        start_line = artifact.get("startLine") or 1
        output.append(_add_line_numbers(content, start_line))

        relationships = artifact.get("relationships")
        if relationships is not None:
            preview_lines = _format_relationships_preview(relationships)
            if preview_lines:
                output.append("\n--- relationships (preview) ---")
                output.extend(preview_lines)
                if _has_any_calls(relationships):
                    has_any_relationships = True

    if not output:
        return "No artifacts found."

    output.append(f"\n({count} artifact(s))")

    if has_any_relationships:
        output.append(
            "\n💡 Hint: the relationships shown above are a preview (up to 3 calls "
            "per direction).\n"
            "   To see the full call graph, inheritance, or references for an "
            "artifact, run:\n"
            "     python relationships.py <identifier> "
            "[--profile callsOnly|inheritanceOnly|allRelevant|referencesOnly]"
        )

    return "\n".join(output)


def main():
    """CLI interface for fetching artifacts."""
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print(__doc__)
        if len(sys.argv) < 2:
            sys.exit(1)
        sys.exit(0)

    identifiers = sys.argv[1:]

    if len(identifiers) > 20:
        print("Error: Maximum 20 identifiers per request.", file=sys.stderr)
        sys.exit(1)

    try:
        client = CodeAliveClient()

        print(f"📥 Fetching {len(identifiers)} artifact(s)", file=sys.stderr)
        print(file=sys.stderr)

        result = client.fetch_artifacts(identifiers=identifiers)

        print(format_artifacts(result))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
