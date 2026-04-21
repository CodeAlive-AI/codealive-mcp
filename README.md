# CodeAlive MCP: Deepest Context Engine for your projects (especially for large codebases)

<!-- MCP Server Name: io.github.codealive-ai.codealive-mcp -->

[![CodeAlive Logo](https://app.codealive.ai/images/logos/dark-logo.svg)](https://www.codealive.ai/)

**Connect your AI assistant to CodeAlive's powerful code understanding platform in seconds!**

This MCP (Model Context Protocol) server enables AI clients like Claude Code, Cursor, Claude Desktop, Continue, VS Code (GitHub Copilot), Cline, Codex, OpenCode, Qwen Code, Gemini CLI, Roo Code, Goose, Kilo Code, Windsurf, Kiro, Qoder, n8n, and Amazon Q Developer to access CodeAlive's advanced semantic code search and codebase interaction features.

## What is CodeAlive?

The most accurate and comprehensive Context Engine as a service, optimized for large codebases, powered by advanced GraphRAG and accessible via MCP. It enriches the context for AI agents like Cursor, Claude Code, Codex, etc., making them 35% more efficient and up to 84% faster.

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
4. **`fetch_artifacts`** - Load the full source for relevant search hits
5. **`get_artifact_relationships`** - Expand call graph, inheritance, and reference relationships for one artifact
6. **`chat`** - Slower synthesized codebase Q&A, typically only after search
7. **`codebase_search`** - Deprecated legacy semantic search alias kept for backward compatibility
8. **`codebase_consultant`** - Deprecated alias for `chat`

## 🎯 Usage Examples

After setup, try these commands with your AI assistant:

- *"Show me all available repositories"* → Uses `get_data_sources`
- *"Find authentication code in the user service"* → Uses `semantic_search`
- *"Find the exact regex that matches JWT tokens"* → Uses `grep_search`
- *"Explain how the payment flow works in this codebase"* → Usually starts with `semantic_search`/`grep_search`, then optionally uses `chat`

`semantic_search` and `grep_search` should be the default tools for most agents. `chat` is a slower synthesis fallback, can take up to 30 seconds, and is usually unnecessary when an agent can run a multi-step workflow with search, fetch, relationships, and local file reads. If your agent supports subagents, the highest-confidence path is to delegate a focused subagent that orchestrates `semantic_search` and `grep_search` first.

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

### Step 2: Choose Your AI Client

Select your preferred AI client below for instant setup:

## 🚀 Quick Start (Agentic Installation)

You may ask your AI agent to install the CodeAlive MCP server for you.

1. Copy-Paste the following prompt into your AI agent (remember to insert your API key):
```
Here is CodeAlive API key: PASTE_YOUR_API_KEY_HERE

Add the CodeAlive MCP server by following the installation guide from the README at https://raw.githubusercontent.com/CodeAlive-AI/codealive-mcp/main/README.md

Find the section "AI Client Integrations" and locate your client (Claude Code, Cursor, Gemini CLI, etc.). Each client has specific setup instructions:
- For Gemini CLI: Use the one-command setup with `gemini mcp add`
- For Claude Code: Use `claude mcp add` with the --transport http flag
- For other clients: Follow the configuration snippets provided

Prefer the Remote HTTP option when available. If API key is not provided above, help me issue a CodeAlive API key first.
```
Then allow execution.

2. Restart your AI agent.

## 🤖 AI Client Integrations

<details>
<summary><b>Claude Code</b></summary>

**Option 1: Remote HTTP (Recommended)**

```bash
claude mcp add --transport http codealive https://mcp.codealive.ai/api --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

**Option 2: Docker (STDIO)**

```bash
claude mcp add codealive-docker /usr/bin/docker run --rm -i -e CODEALIVE_API_KEY=YOUR_API_KEY_HERE ghcr.io/codealive-ai/codealive-mcp:main
```

Replace `YOUR_API_KEY_HERE` with your actual API key.

</details>

<details>
<summary><b>Cursor</b></summary>

**Option 1: Remote HTTP (Recommended)**

1. Open Cursor → Settings (`Cmd+,` or `Ctrl+,`)
2. Navigate to **"MCP"** in the left panel
3. Click **"Add new MCP server"**
4. Paste this configuration:

```json
{
  "mcpServers": {
    "codealive": {
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

5. Save and restart Cursor

**Option 2: Docker (STDIO)**

```json
{
  "mcpServers": {
    "codealive": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Codex</b></summary>

OpenAI Codex CLI supports MCP via `~/.codex/config.toml`.

**`~/.codex/config.toml` (Docker stdio – recommended)**
```toml
[mcp_servers.codealive]
command = "docker"
args = ["run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"]
```

**Experimental: Streamable HTTP (requires `[features].rmcp_client = true`)**

> **Note:** Streamable HTTP support requires `rmcp_client = true` under a `[features]` section in your Codex configuration.

```toml
[mcp_servers.codealive]
url = "https://mcp.codealive.ai/api"
headers = { Authorization = "Bearer YOUR_API_KEY_HERE" }
```

</details>

<details>
<summary><b>Gemini CLI</b></summary>

**One command setup (complete):**

```bash
gemini mcp add --transport http secure-http https://mcp.codealive.ai/api --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

Replace `YOUR_API_KEY_HERE` with your actual API key. That's it - no config files needed! 🎉

</details>

<details>
<summary><b>Continue</b></summary>

**Option 1: Remote HTTP (Recommended)**

1. Create/edit `.continue/config.yaml` in your project or `~/.continue/config.yaml`
2. Add this configuration:

```yaml
mcpServers:
  - name: CodeAlive
    type: streamable-http
    url: https://mcp.codealive.ai/api
    requestOptions:
      headers:
        Authorization: "Bearer YOUR_API_KEY_HERE"
```

3. Restart VS Code

**Option 2: Docker (STDIO)**

```yaml
mcpServers:
  - name: CodeAlive
    type: stdio
    command: docker
    args:
      - run
      - --rm
      - -i
      - -e
      - CODEALIVE_API_KEY=YOUR_API_KEY_HERE
      - ghcr.io/codealive-ai/codealive-mcp:main
```

</details>

<details>
<summary><b>Visual Studio Code with GitHub Copilot</b></summary>

**Option 1: Remote HTTP (Recommended)**

> **Note:** VS Code supports both Streamable HTTP and SSE transports, with automatic fallback to SSE if Streamable HTTP fails.

1. Open Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`)
2. Run **"MCP: Add Server"**
3. Choose **"HTTP"** server type
4. Enter this configuration:

```json
{
  "servers": {
    "codealive": {
      "type": "http",
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

5. Restart VS Code

**Option 2: Docker (STDIO)**

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "codealive": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Claude Desktop</b></summary>

**Option 1: Extension bundle `.mcpb` (Recommended)**

The `.mcpb` bundle gives you one-click install, secure token storage, and self-hosted `baseUrl` configuration — no Docker or CLI required.

1. Download `codealive-mcp.mcpb` from the [latest GitHub Release](https://github.com/CodeAlive-AI/codealive-mcp/releases/latest)
2. In Claude Desktop, open **Settings → Extensions → Install Extension...**
3. Select the downloaded `.mcpb` file and configure:
   - **CodeAlive API Key**: your bearer token
   - **CodeAlive Base URL**: defaults to `https://app.codealive.ai`; for self-hosted, use your deployment origin (e.g. `https://codealive.yourcompany.com`)
   - **Ignore TLS Errors**: only for dev/self-signed environments

**Option 2: Docker (STDIO)**

1. Edit your config file:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add this configuration:

```json
{
  "mcpServers": {
    "codealive": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

3. Restart Claude Desktop

</details>

<details>
<summary><b>Cline</b></summary>

**Option 1: Remote HTTP (Recommended)**

1. Open Cline extension in VS Code
2. Click the MCP Servers icon to configure
3. Add this configuration to your MCP settings:

```json
{
  "mcpServers": {
    "codealive": {
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

4. Save and restart VS Code

**Option 2: Docker (STDIO)**

```json
{
  "mcpServers": {
    "codealive": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>OpenCode</b></summary>

Add CodeAlive as a **remote** MCP server in your `opencode.json`.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "codealive": {
      "type": "remote",
      "url": "https://mcp.codealive.ai/api",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Qwen Code</b></summary>

Qwen Code supports MCP via `mcpServers` in its `settings.json` and multiple transports (stdio/SSE/streamable-http). Use **streamable-http** when available; otherwise use Docker (stdio).

**`~/.qwen/settings.json` (Streamable HTTP)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "streamable-http",
      "url": "https://mcp.codealive.ai/api",
      "requestOptions": {
        "headers": {
          "Authorization": "Bearer YOUR_API_KEY_HERE"
        }
      }
    }
  }
}
```

**Fallback: Docker (stdio)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "--rm", "-i",
               "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
               "ghcr.io/codealive-ai/codealive-mcp:main"]
    }
  }
}
```

</details>

<details>
<summary><b>Roo Code</b></summary>

Roo Code reads a JSON settings file similar to Cline.

**Global config:** `mcp_settings.json` (Roo) or `cline_mcp_settings.json` (Cline-style)

**Option A — Remote HTTP**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "streamable-http",
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**Option B — Docker (STDIO)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

> **Tip:** If your Roo build doesn't honor HTTP headers, use the Docker/STDIO option.

</details>

<details>
<summary><b>Goose</b></summary>

**UI path:** Settings → MCP Servers → Add → choose Streamable HTTP

**Streamable HTTP configuration:**
- **Name:** `codealive`
- **Endpoint URL:** `https://mcp.codealive.ai/api`
- **Headers:** `Authorization: Bearer YOUR_API_KEY_HERE`

**Docker (STDIO) alternative:**

Add a STDIO extension with:
- **Command:** `docker`
- **Args:** `run --rm -i -e CODEALIVE_API_KEY=YOUR_API_KEY_HERE ghcr.io/codealive-ai/codealive-mcp:main`

</details>

<details>
<summary><b>Kilo Code</b></summary>

**UI path:** Manage → Integrations → Model Context Protocol (MCP) → Add Server

**HTTP**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "streamable-http",
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**STDIO (Docker)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Windsurf (Codeium)</b></summary>

**File:** `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "codealive": {
      "type": "streamable-http",
      "serverUrl": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Kiro</b></summary>

> **Note:** Kiro does not yet support remote MCP servers natively. Use the `mcp-remote` workaround to connect to remote HTTP servers.

**Prerequisites:**
```bash
npm install -g mcp-remote
```

**UI path:** Settings → MCP → Add Server

**Global file:** `~/.kiro/settings/mcp.json`
**Workspace file:** `.kiro/settings/mcp.json`

**Remote HTTP (via mcp-remote workaround)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://mcp.codealive.ai/api",
        "--header",
        "Authorization: Bearer ${CODEALIVE_API_KEY}"
      ],
      "env": {
        "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**Docker (STDIO)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Qoder</b></summary>

**UI path:** User icon → Qoder Settings → MCP → My Servers → + Add (Agent mode)

**SSE (remote HTTP)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "sse",
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**STDIO (Docker)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Amazon Q Developer (CLI & IDE)</b></summary>

**Q Developer CLI**

**Config file:** `~/.aws/amazonq/mcp.json` or workspace `.amazonq/mcp.json`

**HTTP server**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "http",
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**STDIO (Docker)**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

**Q Developer IDE (VS Code / JetBrains)**

**Global:** `~/.aws/amazonq/agents/default.json`
**Local (workspace):** `.aws/amazonq/agents/default.json`

**Minimal entry (HTTP):**
```json
{
  "mcpServers": {
    "codealive": {
      "type": "http",
      "url": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      },
      "timeout": 310000
    }
  }
}
```

Use the IDE UI: Q panel → Chat → tools icon → Add MCP Server → choose http or stdio.

</details>

<details>
<summary><b>JetBrains AI Assistant</b></summary>

> **Note:** JetBrains AI Assistant requires the `mcp-remote` workaround for connecting to remote HTTP MCP servers.

**Prerequisites:**
```bash
npm install -g mcp-remote
```

**Config file:** Settings/Preferences → AI Assistant → Model Context Protocol → Configure

Add this configuration:

```json
{
  "mcpServers": {
    "codealive": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://mcp.codealive.ai/api",
        "--header",
        "Authorization: Bearer ${CODEALIVE_API_KEY}"
      ],
      "env": {
        "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

**For self-hosted deployments**, replace the URL:
```json
{
  "mcpServers": {
    "codealive": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://your-server:8000/api",
        "--header",
        "Authorization: Bearer ${CODEALIVE_API_KEY}"
      ],
      "env": {
        "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

See [JetBrains MCP Documentation](https://www.jetbrains.com/help/ai-assistant/mcp.html#workaround-for-remote-servers) for more details.

</details>

<details>
<summary><b>n8n</b></summary>

**Using AI Agent Node with MCP Tools**

1. Add an **AI Agent** node to your workflow
2. Configure the agent with MCP tools:
   ```
   Server URL: https://mcp.codealive.ai/api
   Authorization Header: Bearer YOUR_API_KEY_HERE
   ```

3. The server automatically handles n8n's extra parameters (sessionId, action, chatInput, toolCallId)
4. Use the available tools:
   - `get_data_sources` - List available repositories
   - `semantic_search` - Search code semantically
   - `grep_search` - Search by exact text or regex
   - `get_artifact_relationships` - Expand relationships for one artifact
   - `chat` - Slower synthesized codebase Q&A, usually after search
   - `codebase_search` - Legacy semantic search alias
   - `codebase_consultant` - Deprecated alias for `chat`

**Example Workflow:**
```
Trigger → AI Agent (with CodeAlive MCP tools) → Process Response
```

**Note:** n8n middleware is built-in, so no special configuration is needed. The server will automatically strip n8n's extra parameters before processing tool calls.

</details>

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

Once installed locally, configure your AI client to use the local server:

#### Claude Code (Local)
```bash
claude mcp add codealive-local /path/to/codealive-mcp/.venv/bin/python /path/to/codealive-mcp/src/codealive_mcp_server.py --env CODEALIVE_API_KEY=YOUR_API_KEY_HERE
```

#### Other Clients (Local)
Replace the Docker `command` and `args` with:
```json
{
  "command": "/path/to/codealive-mcp/.venv/bin/python",
  "args": ["/path/to/codealive-mcp/src/codealive_mcp_server.py"],
  "env": {
    "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
  }
}
```

### Running HTTP Server Locally

```bash
# Start local HTTP server
export CODEALIVE_API_KEY="your_api_key_here"
python src/codealive_mcp_server.py --transport http --host localhost --port 8000

# Test health endpoint
curl http://localhost:8000/health
```

### Testing Your Local Installation

After making changes, quickly verify everything works:

```bash
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
```

The smoke test verifies:
- Server starts and connects correctly
- All tools are registered
- Each tool responds appropriately
- Parameter validation works
- Runs in ~5 seconds

### Smithery Installation

Auto-install for Claude Desktop via [Smithery](https://smithery.ai/server/@CodeAlive-AI/codealive-mcp):

```bash
npx -y @smithery/cli install @CodeAlive-AI/codealive-mcp --client claude
```

---

## 🌐 Community Plugins

### Gemini CLI — CodeAlive Extension

**Repo:** https://github.com/akolotov/gemini-cli-codealive-extension

Gemini CLI extension that wires CodeAlive into your terminal with prebuilt slash commands and MCP config. It includes:
- `GEMINI.md` guidance so Gemini knows how to use CodeAlive tools effectively
- Slash commands: `/codealive:chat`, `/codealive:find`, `/codealive:search`
- Easy setup via Gemini CLI's extension system

**Install**
```bash
gemini extensions install https://github.com/akolotov/gemini-cli-codealive-extension
```

**Configure**
```bash
# Option 1: .env next to where you run `gemini`
CODEALIVE_API_KEY="your_codealive_api_key_here"

# Option 2: environment variable
export CODEALIVE_API_KEY="your_codealive_api_key_here"
gemini
```

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
   - Clients must provide their API key via `Authorization: Bearer YOUR_KEY` header

See `docker-compose.example.yml` for the complete configuration template.

### Connecting AI Clients to Your Deployed Instance

Once deployed, configure your AI clients to use your HTTP endpoint:

**Claude Code:**
```bash
claude mcp add --transport http codealive http://your-server:8000/api --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

**VS Code:**
```bash
code --add-mcp "{\"name\":\"codealive\",\"type\":\"http\",\"url\":\"http://your-server:8000/api\",\"headers\":{\"Authorization\":\"Bearer YOUR_API_KEY_HERE\"}}"
```

**Cursor / Other Clients:**
```json
{
  "mcpServers": {
    "codealive": {
      "url": "http://your-server:8000/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

Replace `your-server:8000` with your actual deployment URL and port.

---

## 🪟 Windows & WSL

<details>
<summary><b>Overview</b></summary>

Claude Code on Windows runs inside WSL (Windows Subsystem for Linux). Claude Desktop runs natively on Windows. This creates specific challenges when configuring MCP servers — especially around binary paths, environment variables, and networking.

**The simplest solution for both Claude Code and Claude Desktop on Windows is Remote HTTP** — it avoids all subprocess spawning and path issues entirely.

</details>

<details>
<summary><b>Claude Code in WSL</b></summary>

When Claude Code runs inside WSL, it operates as a normal Linux environment. Use the same commands as on Linux/macOS:

**Remote HTTP (Recommended — avoids all WSL issues):**
```bash
claude mcp add --transport http codealive https://mcp.codealive.ai/api --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

**Docker STDIO (if Docker Desktop WSL integration is enabled):**
```bash
claude mcp add codealive-docker /usr/bin/docker run --rm -i -e CODEALIVE_API_KEY=YOUR_API_KEY_HERE ghcr.io/codealive-ai/codealive-mcp:main
```

> **Note:** If `docker` is not found, ensure Docker Desktop has WSL integration enabled for your distro, or use the full path `/usr/bin/docker`.

</details>

<details>
<summary><b>Claude Desktop on Windows (Docker STDIO)</b></summary>

Claude Desktop on Windows **cannot** connect to MCP servers running inside WSL directly. Use one of these approaches:

**Option 1: Docker Desktop (Recommended)**

If Docker Desktop is installed on Windows, `docker.exe` is in the Windows PATH:

```json
{
  "mcpServers": {
    "codealive": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

**Option 2: wsl.exe Proxy**

If Docker is only available inside WSL, use `wsl.exe` as a bridge:

```json
{
  "mcpServers": {
    "codealive": {
      "command": "wsl.exe",
      "args": [
        "--", "docker", "run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:main"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Self-Hosted MCP Server in WSL2</b></summary>

If you run the MCP HTTP server inside WSL2 and connect from Windows-side clients:

**WSL2 NAT networking issue:** By default, `localhost` inside WSL2 is not reachable from Windows. Two workarounds:

1. **Enable mirrored networking** (Windows 11 22H2+) — add to `%USERPROFILE%\.wslconfig`:
   ```ini
   [wsl2]
   networkingMode=mirrored
   ```
   Then restart WSL: `wsl --shutdown`. After this, `localhost` is shared between Windows and WSL2.

2. **Use WSL2 VM IP** — run `hostname -I` inside WSL to get the IP, then connect to `http://<WSL_IP>:8000/api` instead of `http://localhost:8000/api`.

</details>

<details>
<summary><b>Common WSL Pitfalls</b></summary>

| Problem | Cause | Fix |
|---------|-------|-----|
| `docker: command not found` | Docker not in WSL PATH | Enable Docker Desktop WSL integration for your distro, or use full path `/usr/bin/docker` |
| `ENOENT` / `spawn error` for `npx` or `python` | Binary not in non-interactive shell PATH | Use absolute path (e.g., `/home/user/.nvm/versions/node/v20/bin/npx`) |
| Environment variables missing | WSL non-login shell doesn't source `.bashrc` | Add vars explicitly in MCP config `env` block |
| `Connection refused` to self-hosted server | WSL2 NAT isolates localhost | Enable mirrored networking or use WSL2 VM IP |
| Claude Desktop can't reach WSL MCP server | Claude Desktop doesn't support WSL subprocess spawning | Use Remote HTTP, Docker Desktop, or `wsl.exe` proxy |

</details>

---

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
