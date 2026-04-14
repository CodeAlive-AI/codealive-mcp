#!/usr/bin/env python3
"""
CodeAlive Data Sources - List available repositories and workspaces

Shows all indexed codebases available for search and consultation.
Includes current project repos, dependencies, libraries, and organizational codebases.

Usage:
    python datasources.py              # Show ready-to-use data sources
    python datasources.py --all        # Show all data sources (including processing)
    python datasources.py --json       # Output as JSON

Examples:
    # List ready data sources
    python datasources.py

    # List all data sources (including those being processed)
    python datasources.py --all

    # Get JSON output for parsing
    python datasources.py --json
"""

import sys
import json
from pathlib import Path

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from api_client import CodeAliveClient


def format_datasources(datasources: list, as_json: bool = False) -> str:
    """Format data sources for display."""
    if as_json:
        return json.dumps(datasources, indent=2)

    if not datasources:
        return "No data sources found.\nAdd repositories at https://app.codealive.ai"

    output = []
    output.append(f"\n📚 Available Data Sources ({len(datasources)} total)\n")
    output.append("="*80)

    # Group by type
    repos = [ds for ds in datasources if ds.get("type") == "Repository"]
    workspaces = [ds for ds in datasources if ds.get("type") == "Workspace"]

    if workspaces:
        output.append("\n🗂️  WORKSPACES (search across multiple repos)")
        output.append("-"*80)
        for ws in workspaces:
            name = ws.get("name", "Unknown")
            desc = ws.get("description", "No description")
            state = ws.get("state", "")

            status = f" [{state}]" if state and state != "Alive" else ""
            output.append(f"\n  📁 {name}{status}")
            output.append(f"     {desc}")

    if repos:
        output.append("\n\n📦 REPOSITORIES")
        output.append("-"*80)
        for repo in repos:
            name = repo.get("name", "Unknown")
            desc = repo.get("description", "No description")
            url = repo.get("url", "")
            state = repo.get("state", "")

            status = f" [{state}]" if state and state != "Alive" else ""
            output.append(f"\n  📄 {name}{status}")
            output.append(f"     {desc}")
            if url:
                output.append(f"     🔗 {url}")

    output.append("\n" + "="*80)
    output.append("\n💡 Usage:")
    output.append("   • Use names with search.py and chat.py")
    output.append("   • Workspaces search ALL repos in the workspace")
    output.append("   • Combine multiple data sources for broader search")
    output.append("\n📖 Examples:")
    output.append("   python search.py 'auth logic' my-backend")
    output.append("   python chat.py 'How does caching work?' workspace:platform-team")

    return "\n".join(output)


def main():
    """CLI interface for listing data sources."""
    alive_only = True
    as_json = False

    for arg in sys.argv[1:]:
        if arg == "--all":
            alive_only = False
        elif arg == "--json":
            as_json = True
        elif arg == "--help":
            print(__doc__)
            sys.exit(0)

    try:
        client = CodeAliveClient()
        datasources = client.get_datasources(alive_only=alive_only)
        print(format_datasources(datasources, as_json))

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
