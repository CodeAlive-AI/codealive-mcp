# CodeAlive MCP: Deepest Context Engine for your projects (especially for large codebases)

<!-- MCP Server Name: io.github.codealive-ai.codealive-mcp -->

[![CodeAlive Logo](https://app.codealive.ai/images/logos/dark-logo.svg)](https://www.codealive.ai/)

**Connect your AI assistant to CodeAlive's powerful code understanding platform in seconds!**

This MCP (Model Context Protocol) server enables AI clients like Claude Code, Cursor, Claude Desktop, Continue, VS Code (GitHub Copilot), Cline, Codex, OpenCode, SourceCraft Code Assistant, SourceCraft CLI, Zed, KodaCode, GigaCode, Qwen Code, Gemini CLI, Roo Code, Goose, Kilo Code, Windsurf, Kiro, Qoder, n8n, and Amazon Q Developer to access CodeAlive's advanced semantic code search and codebase interaction features.

## What is CodeAlive?

CodeAlive is a Context Engine for large codebases, powered by graph-based retrieval and exposed through MCP. It gives AI agents like Cursor, Claude Code, Codex, and other MCP-compatible tools precise repository context instead of forcing them to read files blindly. In our RepoQA benchmark, CodeAlive + Qwen3.6 deep reached frontier-agent quality at ~25x lower model cost, and semantic search reduced captured tokens by 45%.

It's like Context7, but for your (large) codebases.

It allows AI-Coding Agents to:

*   **Find relevant code faster** with semantic search
*   **Understand the bigger picture** beyond isolated files  
*   **Provide better answers** with full project context
*   **Reduce costs and time** by removing guesswork

## 🛠 Available Tools

Once connected, you'll have access to these powerful tools:

1. **`get_data_sources`** - List your indexed repositories and workspaces
2. **`semantic_search`** - Canonical semantic search across indexed artifacts
3. **`grep_search`** - Exact literal or regex text search inside file content, plus literal file-name/path matching (returns files like `Form.xml` even when their content never mentions the name), with line-level previews for content matches
4. **`get_repository_ontology`** - Get repository-level orientation for one selected repository
5. **`get_file_tree`** - Inspect a bounded file tree for one repository
6. **`read_file`** - Read a repository-relative file path, optionally with a line range
7. **`fetch_artifacts`** - Load the full source for relevant search hits (missing or inaccessible identifiers are reported back, not silently dropped)
8. **`get_artifact_relationships`** - Expand call graph, inheritance, and reference relationships for one artifact
9. **`get_artifact_query_schema`** - Inspect supported ArtifactQuery entities, fields, and examples
10. **`query_artifact_metadata`** - Run read-only metadata analytics across selected repositories
11. **`chat`** - Stateless, slower synthesized codebase Q&A; call only when explicitly requested

## 🎯 Usage Examples

After setup, try these commands with your AI assistant:

- *"Show me all available repositories"* → Uses `get_data_sources`
- *"Find authentication code in the user service"* → Uses `semantic_search`
- *"Find the exact regex that matches JWT tokens"* → Uses `grep_search`
- *"Explain how the payment flow works in this codebase"* → Usually starts with `semantic_search`/`grep_search`, then optionally uses `chat`

`semantic_search` and `grep_search` should be the default tools for most agents. `chat` is a slower stateless synthesis fallback that can take substantially longer than retrieval, and is usually unnecessary when an agent can run a multi-step workflow with ontology, search, fetch/read, relationships, ArtifactQuery, and local file reads. If your agent supports subagents, the highest-confidence path is to delegate a focused subagent that orchestrates `semantic_search` and `grep_search` first.

## 📚 Agent Skill

For an even better experience, install the [CodeAlive Agent Skill](https://github.com/CodeAlive-AI/codealive-skills) alongside the MCP server. The MCP server gives your agent access to CodeAlive's tools; the skill teaches it the best workflows and query patterns to use them effectively.

**For most agents** (Cursor, Copilot, Gemini CLI, Codex, and [30+ others](https://agentskills.io/)) — install the skill:

```bash
npx skills add CodeAlive-AI/codealive-skills@codealive-context-engine
```

**For Claude Code** — install the plugin (recommended), which includes the skill plus Claude-specific enhancements:

```
/plugin marketplace add CodeAlive-AI/codealive-skills
/plugin install codealive@codealive-marketplace
```

## Table of Contents

*   [Agent Skill](#-agent-skill)
*   [Quick Start (Remote)](#-quick-start-remote)
*   [AI Client Integrations](#-ai-client-integrations)
*   [Advanced: Local Development](#-advanced-local-development)
*   [Community Plugins](#-community-plugins)
*   [HTTP Deployment (Self-Hosted & Cloud)](#-http-deployment-self-hosted--cloud)
*   [Windows & WSL](#-windows--wsl)
*   [Available Tools](#-available-tools)
*   [Usage Examples](#-usage-examples)
*   [Troubleshooting](#-troubleshooting)
*   [Publishing to MCP Registry](#-publishing-to-mcp-registry)
*   [License](#-license)

## 🚀 Quick Start (Remote)

**The fastest way to get started** - no installation required! Our remote MCP server at `https://mcp.codealive.ai/api` provides instant access to CodeAlive's capabilities.

### Step 1: Get Your API Key

1. Sign up at [https://app.codealive.ai/](https://app.codealive.ai/)
2. Navigate to **MCP & API**
3. Click **"+ Create API Key"**
4. Copy your API key immediately - you won't see it again!

### Step 2: Open Your Client Guide

Choose your client in the [MCP integration guides](https://docs.codealive.ai/integrations/mcp) and follow the current setup instructions there.

## 🚀 Quick Start (Agentic Installation)

You may ask your AI agent to install the CodeAlive MCP server for you.

1. Copy-paste the following prompt into your AI agent. Do not include your API key in the prompt:
```
Add the CodeAlive MCP server by following the guide for my client at https://docs.codealive.ai/integrations/mcp

Prefer the Remote HTTP option when available. Do not ask me to paste an API key into chat. When the key is needed, ask me to create a CodeAlive API key and copy it to my clipboard. After I confirm, insert it directly from the clipboard into the required secure configuration without displaying, echoing, logging, or exposing it in command arguments, command output, or model context. If you cannot safely use the clipboard without exposing the value, tell me exactly where to paste it myself.
```
Then allow execution.

2. Restart your AI agent.

## 🤖 AI Client Integrations

Client-specific configuration is maintained in the CodeAlive documentation so file paths, transports, and authentication guidance stay current.

**Start here:** [MCP integration guides](https://docs.codealive.ai/integrations/mcp)

| Client | Setup guide |
|---|---|
| Claude Code | [Claude Code](https://docs.codealive.ai/integrations/mcp/claude-code) |
| Claude Desktop | [Claude Desktop](https://docs.codealive.ai/integrations/mcp/claude-desktop) |
| Cursor | [Cursor](https://docs.codealive.ai/integrations/mcp/cursor) |
| Visual Studio Code | [VS Code](https://docs.codealive.ai/integrations/mcp/vscode) |
| Windsurf | [Windsurf](https://docs.codealive.ai/integrations/mcp/windsurf) |
| Cline | [Cline](https://docs.codealive.ai/integrations/mcp/cline) |
| Continue | [Continue](https://docs.codealive.ai/integrations/mcp/continue) |
| Codex | [Codex](https://docs.codealive.ai/integrations/mcp/codex) |
| Gemini CLI | [Gemini CLI](https://docs.codealive.ai/integrations/mcp/gemini-cli) |
| Amazon Q Developer | [Amazon Q](https://docs.codealive.ai/integrations/mcp/amazon-q) |
| OpenCode | [OpenCode](https://docs.codealive.ai/integrations/mcp/opencode) |
| SourceCraft Code Assistant and SourceCraft CLI | [SourceCraft](https://docs.codealive.ai/integrations/mcp/sourcecraft) |
| Zed | [Zed](https://docs.codealive.ai/integrations/mcp/zed) |
| ChatGPT | [ChatGPT](https://docs.codealive.ai/integrations/mcp/chatgpt) |
| OpenClaw | [OpenClaw](https://docs.codealive.ai/integrations/mcp/openclaw) |
| KodaCode, GigaCode, Roo Code, Goose, Kilo Code, Qwen Code, Kiro, Qoder, JetBrains AI Assistant, n8n, and more | [Other agents](https://docs.codealive.ai/integrations/mcp/other-agents) |

For an unlisted client, use these generic connection details and adapt them to the client's MCP configuration format:

- **Endpoint:** `https://mcp.codealive.ai/api`
- **Transport:** Streamable HTTP
- **Authentication header:** `Authorization: Bearer YOUR_API_KEY_HERE`

For a private deployment, replace the endpoint with your server's `/api` URL. See [Self-Hosting](https://docs.codealive.ai/integrations/mcp/self-hosting) for deployment guidance.

> **Connecting the server is half the setup.** Coding agents may continue using their built-in search unless project instructions tell them to prefer CodeAlive. Ready-made rules for `AGENTS.md`, `CLAUDE.md`, and client-specific instruction files are in [Instructing Coding Agents](https://docs.codealive.ai/guides/instructing-agents).

---
## 🔧 Advanced: Local Development

**For developers who want to customize or contribute to the MCP server.**

### Prerequisites

*   Python 3.11+
*   [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/CodeAlive-AI/codealive-mcp.git
cd codealive-mcp

# Setup with uv (recommended)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e .

# Or setup with pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate  
pip install -e .
```

### Local Server Configuration

After installing the server locally, point your MCP client at `.venv/bin/python` with `src/codealive_mcp_server.py` as the first argument and provide `CODEALIVE_API_KEY` in the process environment. Client-specific configuration belongs in the [MCP integration guides](https://docs.codealive.ai/integrations/mcp).

### Running HTTP Server Locally

```bash
# Start local HTTP server
export CODEALIVE_API_KEY="your_api_key_here"
python src/codealive_mcp_server.py --transport http --host localhost --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

HTTP transport validates `Host` and browser `Origin` headers. Loopback hosts
(`localhost`, `127.0.0.1`, `::1`) work without extra configuration. For a
shared hostname, configure an exact allowlist:

```bash
export CODEALIVE_MCP_ALLOWED_HOSTS="mcp.codealive.yourcompany.com"
# Only for browser callers; ordinary MCP clients do not send Origin.
export CODEALIVE_MCP_ALLOWED_ORIGINS="https://mcp.codealive.yourcompany.com"
python src/codealive_mcp_server.py --transport http --host 0.0.0.0 --port 8000
```

The equivalent repeatable CLI options are `--allowed-host` and
`--allowed-origin`. Do not use `*` for an Internet-facing server.

### Testing Your Local Installation

After making changes, quickly verify everything works:

```bash
# Match pyproject.toml exactly; older uv versions reject the locked setup.
uv --version  # expected: uv 0.11.28
uv sync --locked --extra test

# Install the repository pre-push dependency audit once per clone
./scripts/setup-hooks.sh

# Quick smoke test (recommended)
make smoke-test

# Or run directly
python smoke_test.py

# With your API key for full testing
CODEALIVE_API_KEY=your_key python smoke_test.py

# Run unit tests
make unit-test

# Run all tests
make test

# Equivalent direct locked test run
uv run pytest src/tests/ -q
```

The smoke test verifies:
- Server starts and connects correctly
- All tools are registered
- Each tool responds appropriately
- Parameter validation works
- Runs in ~5 seconds

---

## 🌐 Community Plugins

- [Gemini CLI — CodeAlive Extension](https://github.com/akolotov/gemini-cli-codealive-extension)
- [Gemini CLI setup guide](https://docs.codealive.ai/integrations/mcp/gemini-cli)

---

## 🚢 HTTP Deployment (Self-Hosted & Cloud)

**Deploy the MCP server as an HTTP service for team-wide access or integration with self-hosted CodeAlive instances.**

### Deployment Options

The CodeAlive MCP server can be deployed as an HTTP service using Docker. This allows multiple AI clients to connect to a single shared instance, and enables integration with self-hosted CodeAlive deployments.

### Docker Compose (Recommended)

Create a `docker-compose.yml` file based on our example:

```bash
# Download the example
curl -O https://raw.githubusercontent.com/CodeAlive-AI/codealive-mcp/main/docker-compose.example.yml
mv docker-compose.example.yml docker-compose.yml

# Edit configuration (see below)
nano docker-compose.yml

# Start the service
docker compose up -d

# Check health
curl http://localhost:8000/health
```

**Configuration Options:**

1. **For CodeAlive Cloud (default):**
   - Remove `CODEALIVE_BASE_URL` environment variable (uses default `https://app.codealive.ai`)
   - Clients must provide their API key via `Authorization: Bearer YOUR_KEY` header

2. **For Self-Hosted CodeAlive:**
   - Set `CODEALIVE_BASE_URL` to your CodeAlive instance URL (e.g., `https://codealive.yourcompany.com`)
   - Set `CODEALIVE_MCP_ALLOWED_HOSTS` to the exact hostname clients use for this MCP server
   - Clients must provide their API key via `Authorization: Bearer YOUR_KEY` header

See `docker-compose.example.yml` for the complete configuration template.

### OAuth 2.1 deployment profile

Remote HTTP deployments can enable browser authorization while keeping legacy API-key clients
working during rollout. OAuth mode publishes MCP Protected Resource Metadata, validates exact
issuer/resource-bound JWTs, and exchanges them for a separate short-lived Tool API token. The
incoming MCP bearer token is never forwarded downstream.

| Environment variable | Purpose |
|---|---|
| `CODEALIVE_MCP_OAUTH_ENABLED=true` | Enables OAuth validation and MCP authorization discovery for HTTP transport |
| `CODEALIVE_OAUTH_ISSUER` | Exact OpenIddict issuer, with a trailing slash |
| `CODEALIVE_MCP_RESOURCE` | Exact public MCP resource URL; its path is also the HTTP MCP path |
| `CODEALIVE_TOOL_API_RESOURCE` | Downstream audience; defaults to `urn:codealive:tool-api` |
| `CODEALIVE_OAUTH_INTERNAL_CLIENT_ID` | Confidential resource-server client used only for token exchange |
| `CODEALIVE_OAUTH_INTERNAL_CLIENT_SECRET` | Required secret for that internal client; startup fails closed when it is missing |

The authorization server and MCP service values must match exactly. In CodeAlive Web.Server the
corresponding settings live under `McpOAuth` (`Enabled`, `Issuer`, `Resource`,
`ToolApiResource`, `InternalClientId`, and `InternalClientSecret`). Persist the Web.Server Data
Protection key ring and OpenIddict signing/encryption certificates across replicas and restarts.
Enable the Web.Server and MCP flags in the same rollout; a half-enabled deployment is not a valid
steady state. API-key credentials retain their explicit legacy grammar and are never used as a
fallback after OAuth validation fails.

### Connecting MCP Clients to Your Deployed Instance

Use the same generic connection details as CodeAlive Cloud, replacing the endpoint with your deployment's `/api` URL:

- **Endpoint:** `https://your-server.example.com/api`
- **Transport:** Streamable HTTP
- **Authentication header:** `Authorization: Bearer YOUR_API_KEY_HERE`

For the exact configuration format, open the relevant [client integration guide](https://docs.codealive.ai/integrations/mcp).

## 🪟 Windows & WSL

Use the client-specific documentation for Windows and WSL setup:

- [Claude Code](https://docs.codealive.ai/integrations/mcp/claude-code)
- [Claude Desktop](https://docs.codealive.ai/integrations/mcp/claude-desktop)
- [All MCP integration guides](https://docs.codealive.ai/integrations/mcp)
- [Troubleshooting](https://docs.codealive.ai/troubleshooting)

For self-hosted servers running in WSL2, Windows clients must be able to reach the server's `/api` endpoint. Use mirrored networking on supported Windows 11 versions or connect through the WSL2 VM address.

## 🐞 Troubleshooting

### Quick Diagnostics

1. **Test the hosted service:**
   ```bash
   curl https://mcp.codealive.ai/health
   ```

2. **Check your API key:**
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" https://app.codealive.ai/api/v1/data_sources
   ```

3. **Enable debug logging:** Add `--debug` to local server args

### Common Issues

- **"Connection refused"** → Check internet connection
- **"401 Unauthorized"** → Verify your API key  
- **"No repositories found"** → Check API key permissions in CodeAlive dashboard
- **Client-specific logs** → See your AI client's documentation for MCP logs

### Windows / WSL Issues

- **`docker: command not found` in WSL** → Enable Docker Desktop WSL integration for your distro (Settings → Resources → WSL integration), or use the full path `/usr/bin/docker`
- **`ENOENT` or `spawn error` for `npx`/`python`** → Non-interactive WSL shells don't inherit `nvm`/`pyenv` paths. Use absolute paths in MCP configs
- **`Connection refused` to self-hosted server in WSL2** → WSL2 uses NAT networking; `localhost` differs between Windows and WSL2. Enable mirrored networking in `.wslconfig` or use the WSL2 VM IP (`hostname -I`)
- **Claude Desktop can't connect to WSL MCP server** → Claude Desktop doesn't support WSL subprocess spawning. Use Remote HTTP (`https://mcp.codealive.ai/api`), Docker Desktop, or the `wsl.exe` proxy pattern (see [Windows & WSL section](#-windows--wsl))

### Getting Help

- 📧 Email: support@codealive.ai
- 🐛 Issues: [GitHub Issues](https://github.com/CodeAlive-AI/codealive-mcp/issues)

---

## 📦 Publishing to MCP Registry

For maintainers: see [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on publishing new versions to the MCP Registry.

---

## Privacy Policy

CodeAlive processes the repositories and queries you send through this extension in order to provide semantic search and codebase analysis. For complete privacy details, see [CodeAlive Privacy Policy](https://www.codealive.ai/privacy/).

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Ready to supercharge your AI assistant with deep code understanding?**  
[Get started now →](https://app.codealive.ai/)
