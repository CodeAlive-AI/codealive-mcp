"""Tool metadata tests for directory-grade MCP compatibility."""

import sys
from pathlib import Path

import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).parent.parent))

from codealive_mcp_server import mcp


@pytest.mark.asyncio
async def test_all_tools_are_marked_read_only_with_titles():
    async with Client(mcp) as client:
        tools = await client.list_tools()

    expected_titles = {
        "chat": "Chat About Codebase",
        "codebase_consultant": "Consult Codebase (Deprecated)",
        "get_data_sources": "List Data Sources",
        "codebase_search": "Search Codebase (Deprecated)",
        "semantic_search": "Semantic Search",
        "grep_search": "Grep Search",
        "fetch_artifacts": "Fetch Artifacts",
        "get_artifact_relationships": "Inspect Artifact Relationships",
    }

    actual = {tool.name: tool for tool in tools}
    assert set(actual.keys()) == set(expected_titles.keys())

    for name, title in expected_titles.items():
        tool = actual[name]
        assert tool.title == title
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
