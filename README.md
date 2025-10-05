# CodeAlive MCP: Deep Context for your project (especially for large codebases)

<!-- MCP Server Name: io.github.codealive-ai.codealive-mcp -->

[![CodeAlive Logo](https://app.codealive.ai/images/logos/dark-logo.svg)](https://www.codealive.ai/)

[![smithery badge](https://smithery.ai/badge/@CodeAlive-AI/codealive-mcp)](https://smithery.ai/server/@CodeAlive-AI/codealive-mcp)

**Connect your AI assistant to CodeAlive's powerful code understanding platform in seconds!**

This MCP (Model Context Protocol) server enables AI clients like Claude Code, Cursor, Claude Desktop, Continue, VS Code (GitHub Copilot), and Cline to access CodeAlive's advanced semantic code search and codebase interaction features.

## What is CodeAlive?

The most accurate and comprehensive Context Engine as a service, optimized for large codebases, powered by advanced GraphRAG and accessible via MCP. It enriches the context for AI agents like Cursor, Claude Code, Codex, etc., making them 35% more efficient and up to 84% faster.

It allows AI-Coding Agents toL

*   **Find relevant code faster** with semantic search
*   **Understand the bigger picture** beyond isolated files  
*   **Provide better answers** with full project context
*   **Reduce costs and time** by eliminating guesswork

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
    *   [Claude Code](#claude-code)
    *   [Cursor](#cursor)
    *   [Continue](#continue)
    *   [Visual Studio Code with GitHub Copilot](#visual-studio-code-with-github-copilot)
    *   [Claude Desktop](#claude-desktop)
    *   [Cline](#cline)
*   [Alternative: Docker Setup](#-alternative-docker-setup)
*   [Advanced: Local Development](#-advanced-local-development)
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

### Claude Code

**One command setup:**

```bash
claude mcp add --transport http codealive https://mcp.codealive.ai/api --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

Replace `YOUR_API_KEY_HERE` with your actual API key. That's it! 🎉

### Cursor

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

### Continue

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

### Visual Studio Code with GitHub Copilot

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

### Claude Desktop

> **Note:** Claude Desktop remote MCP requires OAuth authentication. Use Docker option below for Bearer token support.

### Cline

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

---

## 🐳 Alternative: Docker Setup

If you prefer Docker over the remote service, use our Docker image:

### Claude Desktop with Docker

For local development or if you prefer Docker over the remote service:

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

### Cursor with Docker

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

### Continue with Docker

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

### VS Code with Docker

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

### Cline with Docker

1. Open Cline extension in VS Code
2. Click the MCP Servers icon to configure
3. Add this Docker configuration:

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
