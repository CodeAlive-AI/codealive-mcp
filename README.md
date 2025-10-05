# CodeAlive MCP: Deep Context for your project (especially for large codebases)

<!-- MCP Server Name: io.github.codealive-ai.codealive-mcp -->

[![CodeAlive Logo](https://app.codealive.ai/images/logos/dark-logo.svg)](https://www.codealive.ai/)

**Connect your AI assistant to CodeAlive's powerful code understanding platform in seconds!**

This MCP (Model Context Protocol) server enables AI clients like Claude Code, Cursor, Claude Desktop, Continue, VS Code (GitHub Copilot), Cline, Codex, OpenCode, Qwen Code, Gemini CLI, Roo Code, Goose, Kilo Code, Windsurf, Kiro, Qoder, and Amazon Q Developer to access CodeAlive's advanced semantic code search and codebase interaction features.

## What is CodeAlive?

The most accurate and comprehensive Context Engine as a service, optimized for large codebases, powered by advanced GraphRAG and accessible via MCP. It enriches the context for AI agents like Cursor, Claude Code, Codex, etc., making them 35% more efficient and up to 84% faster.

It's like a Context7, but for your (large) codebases.

It allows AI-Coding Agents to:

*   **Find relevant code faster** with semantic search
*   **Understand the bigger picture** beyond isolated files  
*   **Provide better answers** with full project context
*   **Reduce costs and time** by removing guesswork

## 🛠 Available Tools

Once connected, you'll have access to these powerful tools:

1. **`get_data_sources`** - List your indexed repositories and workspaces
2. **`codebase_search`** - Semantic code search across your indexed codebase (main/master branch)  
3. **`codebase_consultant`** - AI consultant with full project expertise

## 🎯 Usage Examples

After setup, try these commands with your AI assistant:

- *"Show me all available repositories"* → Uses `get_data_sources`
- *"Find authentication code in the user service"* → Uses `codebase_search`
- *"Explain how the payment flow works in this codebase"* → Uses `codebase_consultant`

## Table of Contents

*   [Quick Start (Remote)](#-quick-start-remote)
*   [AI Client Integrations](#-ai-client-integrations)
*   [Advanced: Local Development](#-advanced-local-development)
*   [Community Plugins](#-community-plugins)
*   [Available Tools](#-available-tools)
*   [Usage Examples](#-usage-examples)
*   [Troubleshooting](#-troubleshooting)
*   [License](#-license)

## 🚀 Quick Start (Remote)

**The fastest way to get started** - no installation required! Our remote MCP server at `https://mcp.codealive.ai/api` provides instant access to CodeAlive's capabilities.

### Step 1: Get Your API Key

1. Sign up at [https://app.codealive.ai/](https://app.codealive.ai/)
2. Navigate to **API Keys** (under Organization)
3. Click **"+ Create API Key"**
4. Copy your API key immediately - you won't see it again!

### Step 2: Choose Your AI Client

Select your preferred AI client below for instant setup:

## 🤖 AI Client Integrations

<details>
<summary><b>Claude Code</b></summary>

**Option 1: Remote HTTP (Recommended)**

```bash
claude mcp add --transport http codealive https://mcp.codealive.ai/api --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

**Option 2: Docker (STDIO)**

```bash
claude mcp add codealive-docker /usr/bin/docker run --rm -i -e CODEALIVE_API_KEY=YOUR_API_KEY_HERE ghcr.io/codealive-ai/codealive-mcp:v0.2.0
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Codex</b></summary>

OpenAI Codex CLI supports MCP via `~/.codex/config.toml`. Remote HTTP MCP is still evolving; the most reliable way today is to launch CodeAlive via Docker (stdio).

**`~/.codex/config.toml` (Docker stdio – recommended)**
```toml
[mcp_servers.codealive]
command = "docker"
args = ["run", "--rm", "-i",
        "-e", "CODEALIVE_API_KEY=YOUR_API_KEY_HERE",
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"]
```

> If your Codex version advertises support for remote/HTTP transports, you can try an experimental config (may not work on all versions):
```toml
# Experimental; if supported by your Codex build
[mcp_servers.codealive]
url = "https://mcp.codealive.ai/api"
headers = { Authorization = "Bearer YOUR_API_KEY_HERE" }
```

</details>

<details>
<summary><b>Gemini CLI</b></summary>

Gemini CLI has first-class MCP support via `~/.gemini/settings.json` (or workspace `.gemini/settings.json`). Add CodeAlive as a **streamable-http** server.

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
      - ghcr.io/codealive-ai/codealive-mcp:v0.2.0
```

</details>

<details>
<summary><b>Visual Studio Code with GitHub Copilot</b></summary>

**Option 1: Remote HTTP (Recommended)**

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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
      ]
    }
  }
}
```

</details>

<details>
<summary><b>Claude Desktop</b></summary>

> **Note:** Claude Desktop remote MCP requires OAuth authentication. Use Docker option for Bearer token support.

**Docker (STDIO)**

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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
               "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"]
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
      "type": "http",
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
- **Args:** `run --rm -i -e CODEALIVE_API_KEY=YOUR_API_KEY_HERE ghcr.io/codealive-ai/codealive-mcp:v0.2.0`

</details>

<details>
<summary><b>Kilo Code</b></summary>

**UI path:** Manage → Integrations → Model Context Protocol (MCP) → Add Server

**HTTP**
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
      "type": "http",
      "serverUrl": "https://mcp.codealive.ai/api",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

> **Note:** Product name is Windsurf.

</details>

<details>
<summary><b>Kiro</b></summary>

**UI path:** Settings → MCP → Add Server

**Global file:** `~/.kiro/settings/mcp.json`
**Workspace file:** `.kiro/settings/mcp.json`

**HTTP**
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
        "ghcr.io/codealive-ai/codealive-mcp:v0.2.0"
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
      "timeout": 60000
    }
  }
}
```

Use the IDE UI: Q panel → Chat → tools icon → Add MCP Server → choose http or stdio.

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

### Getting Help

- 📧 Email: support@codealive.ai
- 🐛 Issues: [GitHub Issues](https://github.com/CodeAlive-AI/codealive-mcp/issues)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Ready to supercharge your AI assistant with deep code understanding?**  
[Get started now →](https://app.codealive.ai/)
