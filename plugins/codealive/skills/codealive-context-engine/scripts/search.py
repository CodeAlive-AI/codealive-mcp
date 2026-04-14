#!/usr/bin/env python3
"""
CodeAlive Semantic Search — the default discovery tool.

Finds code by meaning (concepts, behavior, architecture), not by exact text.
Use when you can describe WHAT the code does but don't know exact names.
For exact identifiers, literals, or regex, use grep.py instead.

Usage:
    python search.py "How is authentication handled?" my-repo
    python search.py "JWT token validation" workspace:backend-team --max-results 15
    python search.py "user registration" my-repo --path src/auth --ext .py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from api_client import CodeAliveClient


def _format_byte_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_search_results(results: dict) -> str:
    if not results:
        return "No results found."

    if isinstance(results, list):
        items = results
    elif "results" in results:
        items = results["results"]
    else:
        items = [results]

    if not items:
        return (
            "No results found. This does NOT mean the code doesn't exist.\n"
            "Try: (1) rephrase with synonyms or broader terms; "
            "(2) use grep.py if you know a specific identifier or literal string; "
            "(3) check that the data source is correct (run datasources.py); "
            "(4) remove --path/--ext filters if used."
        )

    output = []
    for idx, result in enumerate(items, 1):
        location = result.get("location", {})
        file_path = location.get("path") or result.get("filePath") or result.get("path")
        range_info = location.get("range", {})
        start_line = range_info.get("start", {}).get("line") or result.get("startLine")
        end_line = range_info.get("end", {}).get("line") or result.get("endLine")

        ds = result.get("dataSource", {})
        source_name = ds.get("name") if isinstance(ds, dict) else ds

        kind = result.get("kind", "")
        identifier = result.get("identifier", "")
        description = result.get("description", "")
        snippet = result.get("snippet", "")
        content_byte_size = result.get("contentByteSize")

        if not file_path and "::" in identifier:
            parts = identifier.split("::")
            if len(parts) >= 2:
                file_path = parts[1]

        loc_str = file_path or ""
        if loc_str and start_line and start_line > 0:
            if end_line and end_line != start_line and end_line > 0:
                loc_str = f"{file_path}:{start_line}-{end_line}"
            else:
                loc_str = f"{file_path}:{start_line}"

        output.append(f"\n--- Result #{idx} [{kind}] ---")
        if loc_str:
            output.append(f"  File: {loc_str}")
        if identifier and kind != "Chunk":
            short_id = identifier.split("::")[-1] if "::" in identifier else identifier
            if short_id != file_path:
                output.append(f"  Symbol: {short_id}")
        if source_name:
            output.append(f"  Source: {source_name}")
        if content_byte_size is not None:
            output.append(f"  Size: {_format_byte_size(content_byte_size)}")
        if description:
            output.append(f"  Description: {description}")
        elif snippet:
            output.append(f"  Snippet: {snippet}")

    output.append(f"\n({len(items)} results)")
    output.append(
        "\nHint: descriptions are triage pointers only. Fetch the full source "
        "for relevant identifiers with `python fetch.py <identifier>` or read "
        "the local file before drawing conclusions."
    )
    return "\n".join(output)


def main():
    if len(sys.argv) < 3:
        print("Error: Missing required arguments.", file=sys.stderr)
        print(
            "Usage: python search.py <query> <data_source> [data_source2...] "
            "[--max-results N] [--path PATH] [--ext EXT]",
            file=sys.stderr,
        )
        sys.exit(1)

    query = sys.argv[1]
    data_sources = []
    paths = []
    extensions = []
    max_results = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--max-results" and i + 1 < len(sys.argv):
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

        print(f"Semantic search: '{query}'", file=sys.stderr)
        print(f"Data sources: {', '.join(data_sources)}", file=sys.stderr)
        if max_results is not None:
            print(f"Max results: {max_results}", file=sys.stderr)
        if paths:
            print(f"Paths: {', '.join(paths)}", file=sys.stderr)
        if extensions:
            print(f"Extensions: {', '.join(extensions)}", file=sys.stderr)
        print(file=sys.stderr)

        results = client.semantic_search(
            query=query,
            data_sources=data_sources,
            paths=paths or None,
            extensions=extensions or None,
            max_results=max_results,
        )

        print(format_search_results(results))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
