#!/usr/bin/env python3
"""
CodeAlive Grep Search — exact text or regex search across indexed repositories.

Finds code containing a specific string or pattern. Use when you know the
exact identifier, error message, config key, or regex to match.
For concept-based discovery, use search.py instead.

Usage:
    python grep.py "AuthService" my-repo
    python grep.py "auth\\(" my-repo --regex --max-results 25
    python grep.py "TODO" workspace:backend-team --path src --ext .py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from api_client import CodeAliveClient


def format_grep_results(results: dict) -> str:
    items = results.get("results", []) if isinstance(results, dict) else []
    if not items:
        return (
            "No grep matches found. This does NOT mean the code doesn't exist.\n"
            "Try: (1) check case — grep is case-sensitive by default; "
            "(2) use search.py for concept-based discovery if unsure of exact naming; "
            "(3) check that the data source is correct (run datasources.py); "
            "(4) remove --path/--ext filters if used."
        )

    output = []
    for idx, result in enumerate(items, 1):
        location = result.get("location", {})
        file_path = location.get("path") or result.get("path")
        matches = result.get("matches", [])

        output.append(f"\n--- Result #{idx} [{result.get('kind', 'Artifact')}] ---")
        if file_path:
            output.append(f"  File: {file_path}")
        if result.get("identifier"):
            output.append(f"  Identifier: {result['identifier']}")
        if result.get("matchCount") is not None:
            output.append(f"  Match count: {result['matchCount']}")

        for match in matches:
            output.append(
                "  "
                f"{match.get('lineNumber', '?')}:{match.get('startColumn', '?')}-"
                f"{match.get('endColumn', '?')}  {match.get('lineText', '')}"
            )

    output.append(
        "\nHint: match previews are search evidence only. Fetch the full source "
        "with `python fetch.py <identifier>` or read the local file before reasoning about behavior."
    )
    return "\n".join(output)


def main():
    if len(sys.argv) < 3:
        print("Error: Missing required arguments.", file=sys.stderr)
        print(
            "Usage: python grep.py <query> <data_source> [data_source2...] "
            "[--regex] [--max-results N] [--path PATH] [--ext EXT]",
            file=sys.stderr,
        )
        sys.exit(1)

    query = sys.argv[1]
    data_sources = []
    paths = []
    extensions = []
    max_results = None
    regex = False

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--regex":
            regex = True
            i += 1
        elif arg == "--max-results" and i + 1 < len(sys.argv):
            max_results = int(sys.argv[i + 1])
            i += 2
        elif arg == "--path" and i + 1 < len(sys.argv):
            paths.append(sys.argv[i + 1])
            i += 2
        elif arg == "--ext" and i + 1 < len(sys.argv):
            extensions.append(sys.argv[i + 1])
            i += 2
        elif arg == "--help":
            print(__doc__)
            sys.exit(0)
        else:
            data_sources.append(arg)
            i += 1

    if not data_sources:
        print(
            "Error: At least one data source is required. Run datasources.py to see available sources.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        client = CodeAliveClient()
        results = client.grep_search(
            query=query,
            data_sources=data_sources,
            paths=paths or None,
            extensions=extensions or None,
            max_results=max_results,
            regex=regex,
        )
        print(format_grep_results(results))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
