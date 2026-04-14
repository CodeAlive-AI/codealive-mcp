#!/usr/bin/env python3
"""
CodeAlive Relationships - Drill into an artifact's relationship graph

Returns the call graph (incoming/outgoing calls), inheritance hierarchy
(ancestors/descendants), or symbol references for a single artifact.

Use this AFTER `search.py` or `fetch.py` when you have an artifact identifier
and want to understand how it relates to the rest of the codebase. The fetch
script returns a small "preview" of relationships (up to 3 calls per direction);
this script gives you the full list and lets you switch profiles.

Usage:
    python relationships.py <identifier> [--profile PROFILE] [--max-count N]

Profiles:
    callsOnly         (default) outgoing + incoming calls
    inheritanceOnly   ancestors + descendants
    allRelevant       calls + inheritance (4 groups)
    referencesOnly    symbol references

Examples:
    # Default: full call graph for a function (up to 50 calls per direction)
    python relationships.py "my-org/backend::src/auth.py::AuthService.login()"

    # Inheritance hierarchy for a class
    python relationships.py "my-org/backend::src/models.py::User" --profile inheritanceOnly

    # Everything in one shot, raise the cap
    python relationships.py "my-org/backend::src/svc.py::Service" --profile allRelevant --max-count 200

    # Only symbol references
    python relationships.py "my-org/backend::src/utils.py::format_date" --profile referencesOnly
"""

import sys
import json
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from api_client import CodeAliveClient


# Backend relationship type → MCP-friendly snake_case label
RELATIONSHIP_TYPE_LABELS = {
    "OutgoingCalls": "outgoing_calls",
    "IncomingCalls": "incoming_calls",
    "Ancestors": "ancestors",
    "Descendants": "descendants",
    "References": "references",
}

# Backend profile enum → CLI profile name (kept in sync with api_client.PROFILE_MAP)
PROFILE_LABELS = {
    "CallsOnly": "callsOnly",
    "InheritanceOnly": "inheritanceOnly",
    "AllRelevant": "allRelevant",
    "ReferencesOnly": "referencesOnly",
}


def format_relationships(data: dict) -> str:
    """Format an artifact-relationships response for display."""
    source_id = data.get("sourceIdentifier") or "<unknown>"
    raw_profile = data.get("profile") or ""
    profile = PROFILE_LABELS.get(raw_profile, raw_profile)
    found = bool(data.get("found"))

    if not found:
        return (
            f"Artifact not found or inaccessible: {source_id}\n"
            f"(profile={profile})"
        )

    relationships = data.get("relationships") or []

    output = []
    output.append(f"\n{'='*60}")
    output.append(f"🔗 {source_id}")
    output.append(f"   profile: {profile}")
    output.append(f"{'='*60}")

    if not relationships:
        output.append("\n  (no relationships)")
        output.append("")
        return "\n".join(output)

    for group in relationships:
        rel_type = group.get("relationType", "")
        label = RELATIONSHIP_TYPE_LABELS.get(rel_type, rel_type or "?")
        total = group.get("totalCount") or 0
        returned = group.get("returnedCount") or 0
        truncated = bool(group.get("truncated"))

        suffix = ""
        if truncated and total != returned:
            suffix = f" (showing {returned}/{total} — increase --max-count to see more)"
        elif total != returned:
            suffix = f" ({returned}/{total})"
        else:
            suffix = f" ({total})"

        output.append(f"\n▶ {label}{suffix}")

        items = group.get("items") or []
        if not items:
            output.append("    (none)")
            continue

        for item in items:
            ident = item.get("identifier", "")
            file_path = item.get("filePath")
            start_line = item.get("startLine")
            short_summary = item.get("shortSummary")

            loc = ""
            if file_path:
                loc = file_path
                if start_line:
                    loc = f"{file_path}:{start_line}"

            output.append(f"  • {ident}")
            if loc:
                output.append(f"      📍 {loc}")
            if short_summary:
                output.append(f"      📝 {short_summary}")

    output.append("")
    return "\n".join(output)


def main():
    """CLI interface for fetching artifact relationships."""
    if len(sys.argv) < 2 or sys.argv[1] == "--help":
        print(__doc__)
        if len(sys.argv) < 2:
            sys.exit(1)
        sys.exit(0)

    identifier = sys.argv[1]
    profile = "callsOnly"
    max_count = 50

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--profile" and i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
            i += 2
        elif arg == "--max-count" and i + 1 < len(sys.argv):
            try:
                max_count = int(sys.argv[i + 1])
            except ValueError:
                print(f"Error: --max-count expects an integer, got '{sys.argv[i + 1]}'", file=sys.stderr)
                sys.exit(1)
            i += 2
        elif arg == "--json":
            # Handled below — we strip it before calling format_relationships
            i += 1
        else:
            print(f"Error: unknown argument '{arg}'", file=sys.stderr)
            print("Run with --help for usage.", file=sys.stderr)
            sys.exit(1)

    as_json = "--json" in sys.argv

    try:
        client = CodeAliveClient()

        print(f"🔗 Fetching {profile} relationships for: {identifier}", file=sys.stderr)
        print(f"⚙️  max-count={max_count}", file=sys.stderr)
        print(file=sys.stderr)

        result = client.get_artifact_relationships(
            identifier=identifier,
            profile=profile,
            max_count_per_type=max_count,
        )

        if as_json:
            print(json.dumps(result, indent=2))
        else:
            print(format_relationships(result))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
