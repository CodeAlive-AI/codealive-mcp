#!/usr/bin/env python3
"""Live MCP smoke tests against a real CodeAlive Backend Tool API v3.

The MCP surface deliberately returns backend-rendered agentic text, so this
script validates protocol error state and rendered content instead of parsing
tool results as JSON.

Required environment:
    CODEALIVE_API_KEY

Examples:
    python integration_test.py --target CodeAlive-AI/backend
    python integration_test.py --target CodeAlive-AI/backend \
        --artifact-identifier 'CodeAlive-AI/backend::README.md' --include-chat
"""

__test__ = False  # Executable live smoke script, not a pytest module.

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = {
    "get_data_sources",
    "semantic_search",
    "grep_search",
    "get_repository_ontology",
    "get_file_tree",
    "read_file",
    "fetch_artifacts",
    "get_artifact_relationships",
    "get_artifact_query_schema",
    "query_artifact_metadata",
    "chat",
}


class SmokeResults:
    def __init__(self) -> None:
        self._results: list[tuple[str, bool, str]] = []

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        self._results.append((name, passed, detail))
        status = "PASS" if passed else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"{status:4} {name}{suffix}")

    def skip(self, name: str, detail: str) -> None:
        print(f"SKIP {name} — {detail}")

    def exit_code(self) -> int:
        failed = [result for result in self._results if not result[1]]
        print(f"\n{len(self._results) - len(failed)} passed, {len(failed)} failed")
        return 1 if failed else 0


def rendered_text(result: Any) -> str:
    if not result.content:
        return ""
    return getattr(result.content[0], "text", "")


async def expect_rendered_success(
    session: ClientSession,
    results: SmokeResults,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    result = await session.call_tool(tool_name, arguments)
    text = rendered_text(result)
    results.record(
        tool_name,
        not result.isError and bool(text.strip()),
        f"isError={result.isError}, chars={len(text)}",
    )
    return text


async def run_smoke(
    target: str,
    file_path: str,
    grep_query: str,
    artifact_identifier: str | None,
    include_chat: bool,
) -> int:
    api_key = os.environ.get("CODEALIVE_API_KEY", "")
    if not api_key:
        print("CODEALIVE_API_KEY is required", file=sys.stderr)
        return 2

    results = SmokeResults()
    server_script = Path(__file__).parent / "src" / "codealive_mcp_server.py"
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script)],
        env={**os.environ, "CODEALIVE_API_KEY": api_key},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed_tools = {tool.name for tool in (await session.list_tools()).tools}
            results.record(
                "tools/list contract",
                listed_tools == EXPECTED_TOOLS,
                f"listed={len(listed_tools)}",
            )

            await expect_rendered_success(
                session,
                results,
                "get_data_sources",
                {"ready_only": True},
            )
            await expect_rendered_success(
                session,
                results,
                "semantic_search",
                {
                    "question": "How is application startup configured?",
                    "data_sources": [target],
                    "max_results": 3,
                },
            )
            await expect_rendered_success(
                session,
                results,
                "grep_search",
                {
                    "query": grep_query,
                    "data_sources": [target],
                    "max_results": 3,
                    "regex": False,
                },
            )
            await expect_rendered_success(
                session,
                results,
                "get_repository_ontology",
                {"data_source": target},
            )
            await expect_rendered_success(
                session,
                results,
                "get_file_tree",
                {"data_source": target, "max_depth": 1, "max_nodes": 30},
            )
            await expect_rendered_success(
                session,
                results,
                "read_file",
                {"data_source": target, "path": file_path, "start_line": 1, "end_line": 20},
            )

            if artifact_identifier:
                await expect_rendered_success(
                    session,
                    results,
                    "fetch_artifacts",
                    {"identifiers": [artifact_identifier], "data_source": target},
                )
                await expect_rendered_success(
                    session,
                    results,
                    "get_artifact_relationships",
                    {
                        "identifier": artifact_identifier,
                        "profile": "all_relevant",
                        "max_count_per_type": 10,
                        "data_source": target,
                    },
                )
            else:
                results.skip(
                    "artifact tools",
                    "pass --artifact-identifier from a search result to exercise both tools",
                )

            await expect_rendered_success(
                session,
                results,
                "get_artifact_query_schema",
                {"entity": "files", "include_examples": False},
            )
            await expect_rendered_success(
                session,
                results,
                "query_artifact_metadata",
                {
                    "statement": "SELECT path FROM files LIMIT 1",
                    "data_sources": [target],
                },
            )

            if include_chat:
                await expect_rendered_success(
                    session,
                    results,
                    "chat",
                    {
                        "question": "Summarize the repository startup flow. Prior context: none.",
                        "data_sources": [target],
                    },
                )
            else:
                results.skip("chat", "pass --include-chat to run the billable, potentially long call")

            repairable = await session.call_tool(
                "read_file",
                {"data_source": target, "path": "../outside-repository"},
            )
            repairable_text = rendered_text(repairable)
            results.record(
                "repairable error semantics",
                repairable.isError and "<tool_error>" in repairable_text,
                f"isError={repairable.isError}, chars={len(repairable_text)}",
            )

    return results.exit_code()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test MCP against a live Tool API v3 backend")
    parser.add_argument(
        "--target",
        default=os.environ.get("CODEALIVE_TEST_DATA_SOURCE"),
        required=os.environ.get("CODEALIVE_TEST_DATA_SOURCE") is None,
        help="Repository name returned by get_data_sources",
    )
    parser.add_argument("--file-path", default="README.md")
    parser.add_argument("--grep-query", default="class")
    parser.add_argument("--artifact-identifier")
    parser.add_argument("--include-chat", action="store_true")
    arguments = parser.parse_args()

    return asyncio.run(
        run_smoke(
            target=arguments.target,
            file_path=arguments.file_path,
            grep_query=arguments.grep_query,
            artifact_identifier=arguments.artifact_identifier,
            include_chat=arguments.include_chat,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
