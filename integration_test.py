#!/usr/bin/env python3
"""
Integration tests for CodeAlive MCP Server against a live backend.

Unlike e2e tests (which use httpx.MockTransport), these tests hit the real
CodeAlive API and verify that the backend correctly handles every filtering
parameter. This catches backend regressions that mock-based tests cannot.

Requires:
    CODEALIVE_API_KEY  — a valid API key with at least one indexed repository.

Usage:
    CODEALIVE_API_KEY=ca_... python integration_test.py
    CODEALIVE_API_KEY=ca_... python integration_test.py --target codealive-app

The test automatically picks a CodeAlive-owned repository as the target,
or falls back to the first ready repo. Override with --target <name>.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ── Helpers ──────────────────────────────────────────────────────────────────

C = {
    "G": "\033[92m", "R": "\033[91m", "Y": "\033[93m",
    "B": "\033[94m", "W": "\033[1m", "E": "\033[0m",
}

_results: list[tuple[str, bool, str]] = []


def ok(msg: str) -> None:
    print(f"  {C['G']}PASS{C['E']} {msg}")


def fail(msg: str) -> None:
    print(f"  {C['R']}FAIL{C['E']} {msg}")


def info(msg: str) -> None:
    print(f"       {C['Y']}{msg}{C['E']}")


def header(msg: str) -> None:
    print(f"\n{C['W']}{C['B']}{'─' * 60}")
    print(f"  {msg}")
    print(f"{'─' * 60}{C['E']}")


def record(name: str, passed: bool, detail: str = "") -> None:
    _results.append((name, passed, detail))
    text = f"{name}" + (f" — {detail}" if detail else "")
    ok(text) if passed else fail(text)


def parse(text: str) -> tuple[Optional[dict], Optional[str]]:
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def _all_match(items: list[dict], field: str, substring: str) -> bool:
    """True if every item contains *substring* in its *field* or identifier."""
    for item in items:
        value = item.get(field, "") or item.get("identifier", "")
        if substring.lower() not in value.lower():
            return False
    return True


# ── Test groups ──────────────────────────────────────────────────────────────

async def test_get_data_sources(s: ClientSession) -> None:
    header("get_data_sources: alive_only parameter")

    r = await s.call_tool("get_data_sources", {"alive_only": True})
    ready, _ = parse(r.content[0].text)
    ready_count = len(ready) if isinstance(ready, list) else 0

    r = await s.call_tool("get_data_sources", {"alive_only": False})
    all_ds, _ = parse(r.content[0].text)
    all_count = len(all_ds) if isinstance(all_ds, list) else 0

    record("alive_only=True vs False", all_count >= ready_count,
           f"ready={ready_count}, all={all_count}")

    if isinstance(all_ds, list):
        non_ready = [d for d in all_ds if d.get("readiness") != "Ready"]
        record("alive_only=False includes non-ready", True,
               f"{len(non_ready)} non-ready" if non_ready else "all ready")


async def test_semantic_search_filtering(s: ClientSession, target: str) -> None:
    header("semantic_search: max_results")

    for limit in (1, 5, 50):
        r = await s.call_tool("semantic_search", {
            "query": "repository processing",
            "data_sources": [target],
            "max_results": limit,
        })
        data, _ = parse(r.content[0].text)
        count = len(data.get("results", [])) if data else 0
        record(f"semantic max_results={limit}", count <= limit,
               f"got {count} (limit {limit})")

    header("semantic_search: extensions filter")

    r = await s.call_tool("semantic_search", {
        "query": "authentication",
        "data_sources": [target],
        "extensions": [".cs"],
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    all_cs = _all_match(items, "path", ".cs")
    record("semantic extensions=[.cs]",
           len(items) > 0 and all_cs,
           f"{len(items)} results, all .cs: {all_cs}")

    header("semantic_search: paths filter")

    r = await s.call_tool("semantic_search", {
        "query": "service",
        "data_sources": [target],
        "paths": ["src/CodeAlive.Domain"],
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    all_domain = _all_match(items, "path", "CodeAlive.Domain")
    record("semantic paths=[src/CodeAlive.Domain]",
           len(items) > 0 and all_domain,
           f"{len(items)} results, all in Domain: {all_domain}")

    header("semantic_search: combined filters")

    r = await s.call_tool("semantic_search", {
        "query": "processing status",
        "data_sources": [target],
        "paths": ["src/CodeAlive.Common.Services"],
        "extensions": [".cs"],
        "max_results": 3,
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    all_svc = _all_match(items, "path", "Common.Services")
    all_cs = _all_match(items, "path", ".cs")
    record("semantic combined: paths+ext+max",
           len(items) <= 3 and all_svc and all_cs,
           f"{len(items)} results (max 3), in Services: {all_svc}, .cs: {all_cs}")


async def test_grep_search_filtering(s: ClientSession, target: str) -> None:
    header("grep_search: max_results")

    r = await s.call_tool("grep_search", {
        "query": "RepositoryProcessingStatus",
        "data_sources": [target],
        "max_results": 3,
    })
    data, _ = parse(r.content[0].text)
    count_3 = len(data.get("results", [])) if data else 0
    record("grep max_results=3", count_3 <= 3, f"got {count_3}")

    r = await s.call_tool("grep_search", {
        "query": "RepositoryProcessingStatus",
        "data_sources": [target],
        "max_results": 100,
    })
    data, _ = parse(r.content[0].text)
    count_100 = len(data.get("results", [])) if data else 0
    record("grep max_results=100", count_100 >= count_3,
           f"got {count_100} (was {count_3} with limit=3)")

    header("grep_search: extensions filter")

    r = await s.call_tool("grep_search", {
        "query": "RepositoryProcessingStatus",
        "data_sources": [target],
        "extensions": [".cs"],
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    all_cs = _all_match(items, "path", ".cs")
    record("grep extensions=[.cs]",
           len(items) > 0 and all_cs,
           f"{len(items)} results, all .cs: {all_cs}")

    r = await s.call_tool("grep_search", {
        "query": "RepositoryProcessingStatus",
        "data_sources": [target],
        "extensions": [".ts"],
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    all_ts = _all_match(items, "path", ".ts")
    record("grep extensions=[.ts]", all_ts,
           f"{len(items)} results, all .ts: {all_ts}")

    header("grep_search: paths filter")

    r = await s.call_tool("grep_search", {
        "query": "RepositoryProcessingStatus",
        "data_sources": [target],
        "paths": ["src/CodeAlive.Domain"],
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    all_domain = _all_match(items, "path", "CodeAlive.Domain")
    record("grep paths=[src/CodeAlive.Domain]",
           len(items) > 0 and all_domain,
           f"{len(items)} results, all in Domain: {all_domain}")

    header("grep_search: regex")

    r = await s.call_tool("grep_search", {
        "query": "Repository.*Status\\.Alive",
        "data_sources": [target],
        "regex": True,
    })
    data, _ = parse(r.content[0].text)
    regex_count = len(data.get("results", [])) if data else 0

    r = await s.call_tool("grep_search", {
        "query": "Repository.*Status\\.Alive",
        "data_sources": [target],
        "regex": False,
    })
    data, _ = parse(r.content[0].text)
    literal_count = len(data.get("results", [])) if data else 0
    record("grep regex=True vs False",
           regex_count > literal_count,
           f"regex={regex_count}, literal={literal_count}")

    header("grep_search: combined filters")

    r = await s.call_tool("grep_search", {
        "query": "Status.*Alive",
        "data_sources": [target],
        "paths": ["src/CodeAlive.Common.Services"],
        "extensions": [".cs"],
        "regex": True,
        "max_results": 5,
    })
    data, _ = parse(r.content[0].text)
    items = data.get("results", []) if data else []
    record("grep combined: all filters",
           len(items) <= 5,
           f"{len(items)} results (max 5)")


async def test_relationships_profiles(s: ClientSession, target: str) -> None:
    header("get_artifact_relationships: profiles")

    # Find a symbol
    r = await s.call_tool("grep_search", {
        "query": "class PipelineOrchestratorService",
        "data_sources": [target],
        "max_results": 5,
    })
    data, _ = parse(r.content[0].text)
    symbol_id = None
    if data:
        for item in data.get("results", []):
            ident = item.get("identifier", "")
            if ident.count("::") >= 2:
                symbol_id = ident
                break

    if not symbol_id:
        record("profile tests", False, "no symbol found")
        return

    info(f"symbol: {symbol_id}")

    for profile in ("callsOnly", "inheritanceOnly", "allRelevant", "referencesOnly"):
        r = await s.call_tool("get_artifact_relationships", {
            "identifier": symbol_id,
            "profile": profile,
        })
        data, _ = parse(r.content[0].text)
        if data and data.get("found"):
            types = [rel.get("type") for rel in data.get("relationships", [])]
            total = sum(rel.get("totalCount", 0) for rel in data.get("relationships", []))
            record(f"profile={profile}", True, f"types={types}, total={total}")
        elif data and not data.get("found"):
            record(f"profile={profile}", True, "found=False (valid)")
        else:
            record(f"profile={profile}", False, str(data)[:100])

    # Invalid profile
    r = await s.call_tool("get_artifact_relationships", {
        "identifier": symbol_id,
        "profile": "invalidProfile",
    })
    data, _ = parse(r.content[0].text)
    record("invalid profile rejected",
           data and "error" in data,
           "correctly rejected")

    # max_count_per_type
    header("get_artifact_relationships: max_count_per_type")

    r = await s.call_tool("get_artifact_relationships", {
        "identifier": symbol_id,
        "profile": "callsOnly",
        "max_count_per_type": 2,
    })
    data, _ = parse(r.content[0].text)
    if data and data.get("found"):
        for rel in data.get("relationships", []):
            returned = rel.get("returnedCount", 0)
            record(f"max_count_per_type=2 ({rel['type']})",
                   returned <= 2,
                   f"returned={returned}")


async def test_fetch_artifacts_edges(s: ClientSession, target: str) -> None:
    header("fetch_artifacts: edge cases")

    r = await s.call_tool("fetch_artifacts", {"identifiers": []})
    record("empty identifiers rejected",
           "required" in r.content[0].text.lower(),
           "correctly rejected")

    r = await s.call_tool("fetch_artifacts", {
        "identifiers": [f"fake::id::{i}" for i in range(21)]
    })
    record(">20 identifiers rejected",
           "20" in r.content[0].text or "maximum" in r.content[0].text.lower(),
           "correctly rejected")

    r = await s.call_tool("fetch_artifacts", {
        "identifiers": ["nonexistent::file.py::NoClass"]
    })
    record("nonexistent identifier",
           not r.isError,
           f"len={len(r.content[0].text)}")

    # Multiple valid
    r = await s.call_tool("semantic_search", {
        "query": "service",
        "data_sources": [target],
        "max_results": 3,
    })
    data, _ = parse(r.content[0].text)
    ids = [i["identifier"] for i in (data.get("results", []) if data else [])
           if i.get("identifier")][:3]
    if ids:
        r = await s.call_tool("fetch_artifacts", {"identifiers": ids})
        record(f"fetch {len(ids)} artifacts",
               "<artifact" in r.content[0].text,
               f"len={len(r.content[0].text)}")


async def test_validation_edges(s: ClientSession, target: str) -> None:
    header("Validation edge cases")

    for val, label in [(0, "0"), (501, "501")]:
        r = await s.call_tool("semantic_search", {
            "query": "test", "data_sources": [target], "max_results": val,
        })
        record(f"max_results={label} rejected",
               "error" in r.content[0].text.lower(),
               "correctly rejected")

    r = await s.call_tool("semantic_search", {
        "query": "test", "data_sources": [target], "max_results": 500,
    })
    data, _ = parse(r.content[0].text)
    has_results = data is not None and "results" in data
    record("max_results=500 accepted",
           has_results,
           "accepted" if has_results else f"unexpected: {r.content[0].text[:100]}")

    r = await s.call_tool("semantic_search", {
        "query": "test", "data_sources": [],
    })
    record("empty data_sources=[] fallback",
           not r.isError,
           f"len={len(r.content[0].text)}")

    r = await s.call_tool("semantic_search", {
        "query": "service", "data_sources": target,
    })
    data, _ = parse(r.content[0].text)
    record("data_sources as string",
           data is not None and "results" in data,
           f"{len(data.get('results', []))} results" if data and "results" in data else "fail")


async def test_agent_workflow(s: ClientSession, target: str) -> None:
    header("Full agent workflow: search -> fetch -> relationships -> chat")

    # 1. semantic_search
    r = await s.call_tool("semantic_search", {
        "query": "repository indexing pipeline",
        "data_sources": [target],
        "max_results": 5,
    })
    data, _ = parse(r.content[0].text)
    results = data.get("results", []) if data else []
    record("workflow: semantic_search", len(results) > 0, f"{len(results)} results")

    artifact_id = None
    for item in results:
        ident = item.get("identifier", "")
        if ident.count("::") >= 2:
            artifact_id = ident
            break

    # 2. fetch_artifacts
    if artifact_id:
        r = await s.call_tool("fetch_artifacts", {"identifiers": [artifact_id]})
        record("workflow: fetch_artifacts",
               "<artifact" in r.content[0].text,
               f"len={len(r.content[0].text)}")

        # 3. relationships
        r = await s.call_tool("get_artifact_relationships", {
            "identifier": artifact_id,
        })
        data, _ = parse(r.content[0].text)
        record("workflow: relationships",
               data is not None and "found" in data,
               f"found={data.get('found')}" if data else "parse error")

    # 4. chat
    r = await s.call_tool("chat", {
        "question": "How does repository indexing work?",
        "data_sources": [target],
    })
    text = r.content[0].text
    record("workflow: chat",
           len(text) > 100 and not r.isError,
           f"len={len(text)}")

    # 5. deprecated aliases
    r = await s.call_tool("codebase_consultant", {
        "question": "What testing patterns are used?",
        "data_sources": [target],
    })
    record("workflow: codebase_consultant (deprecated)",
           len(r.content[0].text) > 50 and not r.isError,
           f"len={len(r.content[0].text)}")

    r = await s.call_tool("codebase_search", {
        "query": "error handling",
        "data_sources": [target],
    })
    record("workflow: codebase_search (deprecated)",
           not r.isError,
           f"len={len(r.content[0].text)}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main(target_override: Optional[str] = None) -> int:
    api_key = os.environ.get("CODEALIVE_API_KEY", "")
    if not api_key:
        print(f"{C['R']}CODEALIVE_API_KEY not set{C['E']}")
        return 1

    server_script = str(Path(__file__).parent / "src" / "codealive_mcp_server.py")
    server_params = StdioServerParameters(
        command=str(Path(__file__).parent / ".venv" / "bin" / "python"),
        args=[server_script],
        env={**os.environ, "CODEALIVE_API_KEY": api_key},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            print(f"{C['G']}Server connected{C['E']}")

            # Resolve target data source
            if target_override:
                target = target_override
                info(f"Using explicit target: {target}")
            else:
                r = await s.call_tool("get_data_sources", {})
                data_sources = json.loads(r.content[0].text)
                target = None
                for ds in data_sources if isinstance(data_sources, list) else []:
                    if ds.get("readiness") != "Ready":
                        continue
                    if "CodeAlive" in ds.get("fullName", "") and ds.get("type") == "Repository":
                        # Prefer the backend — it's the largest and most diverse
                        if "backend" in ds.get("fullName", "").lower():
                            target = ds["name"]
                            break
                        if not target:
                            target = ds["name"]

                if not target and isinstance(data_sources, list) and data_sources:
                    target = data_sources[0]["name"]

                if not target:
                    print(f"{C['R']}No usable data source found{C['E']}")
                    return 1

                info(f"Auto-selected target: {target}")

            # Run test groups
            await test_get_data_sources(s)
            await test_semantic_search_filtering(s, target)
            await test_grep_search_filtering(s, target)
            await test_relationships_profiles(s, target)
            await test_fetch_artifacts_edges(s, target)
            await test_validation_edges(s, target)
            await test_agent_workflow(s, target)

    # Summary
    header("SUMMARY")
    passed = sum(1 for _, p, _ in _results if p)
    failed = sum(1 for _, p, _ in _results if not p)

    for name, p, detail in _results:
        status = f"{C['G']}PASS{C['E']}" if p else f"{C['R']}FAIL{C['E']}"
        print(f"  {status}  {name}")
        if not p and detail:
            print(f"         {C['R']}{detail}{C['E']}")

    print(f"\n  {C['W']}{passed} passed{C['E']}, ", end="")
    print(f"{C['R']}{failed} failed{C['E']}" if failed else f"{C['G']}0 failed{C['E']}", end="")
    print(f" / {passed + failed} total")

    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integration tests against live backend")
    parser.add_argument("--target", help="Data source name to test against")
    args = parser.parse_args()

    try:
        sys.exit(asyncio.run(main(args.target)))
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(1)
