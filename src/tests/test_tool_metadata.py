"""Tool metadata tests for directory-grade MCP compatibility."""

import sys
from pathlib import Path

import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).parent.parent))

from codealive_mcp_server import _package_version, mcp


@pytest.mark.asyncio
async def test_all_tools_are_marked_read_only_with_titles():
    async with Client(mcp) as client:
        tools = await client.list_tools()

    expected_titles = {
        "chat": "Chat About Codebase",
        "get_data_sources": "List Data Sources",
        "semantic_search": "Semantic Search",
        "grep_search": "Grep Search",
        "get_repository_ontology": "Get Repository Ontology",
        "get_file_tree": "Get File Tree",
        "read_file": "Read File",
        "fetch_artifacts": "Fetch Artifacts",
        "get_artifact_relationships": "Inspect Artifact Relationships",
        "get_artifact_query_schema": "Get ArtifactQuery Schema",
        "query_artifact_metadata": "Query Artifact Metadata",
    }

    actual = {tool.name: tool for tool in tools}
    assert set(actual.keys()) == set(expected_titles.keys())

    for name, title in expected_titles.items():
        tool = actual[name]
        assert tool.title == title
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.annotations.idempotentHint is True
        assert tool.annotations.openWorldHint is True

    relationships_description = actual["get_artifact_relationships"].description
    assert relationships_description is not None
    assert "exact artifact identifier" in relationships_description
    assert "not a search tool" in relationships_description
    assert "fetch_artifacts" in relationships_description

    semantic_schema = actual["semantic_search"].inputSchema["properties"]
    assert semantic_schema["question"]["minLength"] == 1
    max_results_schema = semantic_schema["max_results"]["anyOf"][0]
    assert max_results_schema["minimum"] == 1
    assert max_results_schema["maximum"] == 500

    tree_schema = actual["get_file_tree"].inputSchema["properties"]
    assert tree_schema["max_depth"]["anyOf"][0]["maximum"] == 8
    assert tree_schema["max_nodes"]["anyOf"][0]["maximum"] == 300

    fetch_schema = actual["fetch_artifacts"].inputSchema["properties"]["identifiers"]
    identifier_array_schema = next(branch for branch in fetch_schema["anyOf"] if branch.get("type") == "array")
    assert identifier_array_schema["minItems"] == 1
    assert identifier_array_schema["maxItems"] == 50

    relationship_schema = actual["get_artifact_relationships"].inputSchema["properties"]
    assert relationship_schema["profile"]["enum"] == [
        "calls_only",
        "inheritance_only",
        "all_relevant",
        "references_only",
    ]
    assert relationship_schema["max_count_per_type"]["maximum"] == 1000


def test_server_advertises_codealive_version_and_compact_instructions():
    assert mcp.version == _package_version()
    assert mcp.instructions is not None
    assert len(mcp.instructions.split()) <= 150
    assert "DISCOVER → SEARCH → READ → EXPAND" in mcp.instructions
    assert "chat only when the user explicitly requests" in mcp.instructions.lower()
