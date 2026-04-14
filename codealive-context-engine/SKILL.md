---
name: codealive-context-engine
description: Semantic code search and AI-powered codebase Q&A across indexed repositories. Use when understanding code beyond local files, exploring dependencies, discovering cross-project patterns, planning features, debugging, or onboarding. Queries like "How does X work?", "Show me Y patterns", "How is library Z used?". The default path is semantic search plus grep search; chat-with-codebase is slower, more expensive, and usually secondary.
---

# CodeAlive Context Engine

Semantic code intelligence across your entire code ecosystem — current project, organizational repos, dependencies, and any indexed codebase.

## Authentication

All scripts require a CodeAlive API key. If any script fails with "API key not configured", help the user set it up:

**Option 1 (recommended):** Run the interactive setup and wait for the user to complete it:
```bash
python setup.py
```

**Option 2 (not recommended — key visible in chat history):** If the user pastes their API key directly in chat, save it via:
```bash
python setup.py --key THE_KEY
```

Do NOT retry the failed script until setup completes successfully.

## Table of Contents

- [Authentication](#authentication)
- [Tools Overview](#tools-overview)
- [When to Use](#when-to-use)
- [Quick Start](#quick-start)
- [Tool Reference](#tool-reference)
- [Data Sources](#data-sources)
- [Configuration](#configuration)

## Tools Overview

| Tool | Script | Speed | Cost | Best For |
|------|--------|-------|------|----------|
| **List Data Sources** | `datasources.py` | Instant | Free | Discovering indexed repos and workspaces |
| **Semantic Search** | `search.py` | Fast | Low | Default discovery — finds code by meaning (concepts, behavior, architecture) |
| **Grep Search** | `grep.py` | Fast | Low | Finds code containing a specific string or regex (identifiers, literals, patterns) |
| **Fetch Artifacts** | `fetch.py` | Fast | Low | Retrieving full content for search results |
| **Artifact Relationships** | `relationships.py` | Fast | Low | Drilling into call graph, inheritance, references for one artifact |
| **Chat with Codebase** | `chat.py` | Slow | High | Synthesized answers, architectural explanations |

**Cost guidance:** `semantic_search` and `grep_search` are the default starting point. Chat with Codebase invokes an LLM on the server side, can take up to 30 seconds, and is significantly more expensive per call — use it only when you need a synthesized, ready-to-use answer rather than raw search results.

**Highest-confidence guidance:** If your agent supports subagents and the task needs maximum reliability or depth, prefer a subagent-driven workflow that combines `search.py`, `grep.py`, `fetch.py`, `relationships.py`, and local file reads. `chat.py` is optional synthesis, not the default path.

**Three-step workflow (search → triage → load real content):**
1. **Search** — find relevant code locations with descriptions and identifiers
2. **Triage** — use `description` ONLY to decide which results are worth a closer
   look. It is a pointer, NOT the source of truth. Do not draw conclusions from it.
3. **Get real content** — for every artifact you decide is relevant:
    - External repos (no local access): `python fetch.py <identifier>`
    - Current working repo: read the file at the shown path with your editor's
      file-read tool
    Treat only that real `content` as ground truth.

**Optional drill-down:** once you know an artifact matters, run
`python relationships.py <identifier>` to expand its call graph, inheritance,
or references.

## When to Use

**Semantic search (default) — you describe behavior or concept:**
- "How is authentication implemented?"
- "Show me error handling patterns across services"
- "How does this library work internally?"
- "Find similar features to guide my implementation"

**Grep search — you know the exact text:**
- "Find all usages of `RepositoryDeleted`"
- "Where is `ConnectionString` configured?"
- "Search for `TODO: fix` across the codebase"
- Error messages, URLs, config keys, import paths, regex patterns

**Use local file tools instead for:**
- Finding specific files by name or pattern
- Exact keyword search in the current directory
- Reading known file paths
- Searching uncommitted changes

## Quick Start

### 1. Discover what's indexed

```bash
python scripts/datasources.py
```

### 2. Search for code (fast, cheap)

```bash
python scripts/search.py "JWT token validation" my-backend
python scripts/search.py "authentication flow" my-repo --path src/auth --ext .py
python scripts/grep.py "AuthService" my-repo
python scripts/grep.py "auth\\(" my-repo --regex
```

### 3. Fetch full content (for external repos)

```bash
python scripts/fetch.py "my-org/backend::src/auth.py::AuthService.login()"
```

### 4. Drill into an artifact's relationships (optional)

```bash
# Full call graph (default)
python scripts/relationships.py "my-org/backend::src/auth.py::AuthService.login()"

# Inheritance hierarchy for a class
python scripts/relationships.py "my-org/backend::src/models.py::User" --profile inheritanceOnly

# Calls + inheritance, raise the per-type cap
python scripts/relationships.py "my-org/backend::src/svc.py::Service" --profile allRelevant --max-count 200
```

### 5. Chat with codebase (slower, optional synthesis)

```bash
python scripts/chat.py "Explain the authentication flow" my-backend
python scripts/chat.py "What about security considerations?" --continue CONV_ID
```

## Tool Reference

### `datasources.py` — List Data Sources

```bash
python scripts/datasources.py              # Ready-to-use sources
python scripts/datasources.py --all        # All (including processing)
python scripts/datasources.py --json       # JSON output
```

### `search.py` — Semantic Code Search (default discovery tool)

The default starting point. Finds code by WHAT it does — concepts, behavior,
architecture — not by exact text. Use when you can describe what you're
looking for but don't know the exact names in the codebase.

```bash
python scripts/search.py <query> <data_sources...> [options]
```

| Option | Description |
|--------|-------------|
| `--max-results N` | Optional cap for the number of returned artifacts |
| `--path PATH` | Repo-relative path or directory scope (repeatable) |
| `--ext EXT` | File extension scope such as `.py` or `.ts` (repeatable) |

**`description` is a triage pointer ONLY** — it tells you which artifacts are
worth a closer look. It is NOT the source of truth and you must NOT draw
conclusions from it. For every result you consider relevant, load the real
source: use `fetch.py <identifier>` for external repos, or your editor's
file-read tool on the path for repos in the current working directory. Treat
only that real `content` as ground truth.

### `grep.py` — Exact Text / Regex Search

Finds code containing a specific string or regex pattern. Use when you know
the exact text to look for: identifiers, error messages, config keys, URLs,
domain events, import paths, TODO comments.

```bash
python scripts/grep.py <query> <data_sources...> [--regex] [--max-results N] [--path PATH] [--ext EXT]
```

| Option | Description |
|--------|-------------|
| `--regex` | Interpret the query as a regex pattern |
| `--max-results N` | Optional cap for the number of returned artifacts |
| `--path PATH` | Repo-relative path or directory scope (repeatable) |
| `--ext EXT` | File extension scope such as `.py` or `.ts` (repeatable) |

Line previews are still search evidence, not source of truth. Use `fetch.py`
or your local file-read tool before drawing conclusions about behavior.

### `fetch.py` — Fetch Artifact Content

Retrieves the full source code content for artifacts found via search. Use this for external repositories you cannot access locally.

```bash
python scripts/fetch.py <identifier1> [identifier2...]
```

| Constraint | Value |
|-----------|-------|
| Max identifiers per request | 20 |
| Identifiers source | `identifier` field from search results |
| Identifier format | `{owner/repo}::{path}::{symbol}` (symbols), `{owner/repo}::{path}` (files) |

For function-like artifacts the response includes a small **relationships
preview** (up to 3 outgoing/incoming calls per direction). To see the full
call graph, inheritance, or references, run `relationships.py` with the
artifact's identifier.

### `relationships.py` — Drill into an Artifact's Relationship Graph

Returns the full call graph (incoming/outgoing calls), inheritance hierarchy
(ancestors/descendants), or symbol references for a single artifact. This is
the drill-down tool — use it AFTER `search.py` or `fetch.py` once you have an
identifier and want to understand how the artifact relates to the rest of the
codebase.

```bash
python scripts/relationships.py <identifier> [--profile PROFILE] [--max-count N]
```

| Option | Description |
|--------|-------------|
| `--profile callsOnly` | Default. Outgoing + incoming calls |
| `--profile inheritanceOnly` | Ancestors + descendants |
| `--profile allRelevant` | Calls + inheritance (4 groups) |
| `--profile referencesOnly` | Symbol references |
| `--max-count N` | Max related artifacts per relationship type (1–1000, default 50) |
| `--json` | Emit the raw JSON response instead of the formatted view |

### `chat.py` — Chat with Codebase

Sends your question to an AI consultant that has full context of the indexed codebase. Returns synthesized, ready-to-use answers. Supports conversation continuity for follow-ups.

**This is more expensive than search** because it runs an LLM inference on the server side. Prefer search when you just need to locate code. Use chat when you need explanations, comparisons, or architectural analysis after search. It can take up to 30 seconds.

```bash
python scripts/chat.py <question> <data_sources...> [options]
```

| Option | Description |
|--------|-------------|
| `--continue <id>` | Continue a previous conversation (saves context and cost) |

**Conversation continuity:** Every response includes a `conversation_id`. Pass it with `--continue` for follow-up questions — this preserves context and is cheaper than starting fresh.

## Data Sources

**Repository** — single codebase, for targeted searches:
```bash
python scripts/search.py "query" my-backend-api
```

**Workspace** — multiple repos, for cross-project patterns:
```bash
python scripts/search.py "query" workspace:backend-team
```

**Multiple repositories:**
```bash
python scripts/search.py "query" repo-a repo-b repo-c
```

## Configuration

### Prerequisites

- Python 3.8+ (no third-party packages required — uses only stdlib)

### API Key Setup

The skill needs a CodeAlive API key. Resolution order:

1. `CODEALIVE_API_KEY` environment variable
2. OS credential store (macOS Keychain / Linux secret-tool / Windows Credential Manager)

**Environment variable (all platforms):**
```bash
export CODEALIVE_API_KEY="your_key_here"
```

**macOS Keychain:**
```bash
security add-generic-password -a "$USER" -s "codealive-api-key" -w "YOUR_API_KEY"
```

**Linux (freedesktop secret-tool):**
```bash
secret-tool store --label="CodeAlive API Key" service codealive-api-key
```

**Windows Credential Manager:**
```cmd
cmdkey /generic:codealive-api-key /user:codealive /pass:"YOUR_API_KEY"
```

**Base URL** (optional, defaults to `https://app.codealive.ai`):
```bash
export CODEALIVE_BASE_URL="https://your-instance.example.com"
```

For self-hosted CodeAlive, use your deployment origin. `https://your-instance.example.com` is preferred, but `https://your-instance.example.com/api` is also accepted and normalized automatically.

Get API keys at: https://app.codealive.ai/settings/api-keys

## Using with CodeAlive MCP Server

This skill works standalone, but delivers the best experience when combined with the [CodeAlive MCP server](https://github.com/CodeAlive-AI/codealive-mcp). The MCP server provides direct tool access via the Model Context Protocol, while this skill provides the workflow knowledge and query patterns to use those tools effectively.

| Component | What it provides |
|-----------|-----------------|
| **This skill** | Query patterns, workflow guidance, cost-aware tool selection |
| **MCP server** | Direct `semantic_search`, `grep_search`, `fetch_artifacts`, `get_artifact_relationships`, `chat`, `get_data_sources` tools plus deprecated aliases |

When both are installed, prefer the MCP server's tools for direct operations and this skill's scripts for guided workflows.

## Detailed Guides

For advanced usage, see reference files:
- **[Query Patterns](references/query-patterns.md)** — effective query writing, anti-patterns, language-specific examples
- **[Workflows](references/workflows.md)** — step-by-step workflows for onboarding, debugging, feature planning, and more
