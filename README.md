# CodeAlive MCP: Deep Context for your project (especially for large codebases)

[![CodeAlive Logo](https://app.codealive.ai/images/logos/dark-logo.svg)](https://www.codealive.ai/)

This MCP (Model Context Protocol) server for the [CodeAlive API](https://www.codealive.ai/) enables AI clients like Claude Desktop, Cursor, Windserf, VS Code (GitHub Copilot), Cline, Roo-Code, and Refact to access CodeAlive's advanced semantic code search and codebase interaction features.

CodeAlive MCP enhances these agents by providing **enriched context** from your project's codebase, enabling more intelligent and efficient interactions.

## What is CodeAlive?

[CodeAlive](https://www.codealive.ai/) is a platform that analyzes your entire codebase, including documentation and dependencies, to understand its structure, patterns, and logic. It creates a detailed internal map of your repositories or workspaces, enabling fast, reliable, and high-quality answers to questions about your solution for any IT professional.

Using this MCP server allows AI agents (like Claude, Copilot, etc.) to leverage CodeAlive's deep code understanding. This helps agents:

*   **Find relevant code faster:** Get precise code snippets related to your questions.
*   **Understand the bigger picture:** Gain context about the entire repository or workspace, not just isolated files.
*   **Reduce costs and time:** Improve agent efficiency by providing accurate context directly, reducing the need for extensive file searching or guesswork.

## Table of Contents

*   [Available Tools](#available-tools)
*   [Getting Started](#getting-started)
    *   [Prerequisites](#prerequisites)
    *   [Getting an API Key](#getting-an-api-key)
    *   [Installation](#installation)
*   [Configuration](#configuration)
    *   [Environment Variables](#environment-variables)
    *   [Command Line Options](#command-line-options)
*   [Integrating with AI Clients](#integrating-with-ai-clients)
    *   [Continue](#continue)
    *   [Claude Code](#claude-code)
    *   [Claude Desktop](#claude-desktop)
    *   [Visual Studio Code with GitHub Copilot](#visual-studio-code-with-github-copilot)
    *   [Cursor](#cursor)
*   [Using Python Directly](#using-python-directly)
    *   [Claude Desktop with Python](#claude-desktop-with-python)
    *   [Cursor with Python](#cursor-with-python)
*   [Troubleshooting](#troubleshooting)
*   [License](#license)

## Available Tools

The MCP server provides the following tools:

1.  **`chat_completions`**: Access the CodeAlive Chat API with codebase context. If your API key is assigned to exactly one datasource, specifying the datasource is optional.
2.  **`get_data_sources`**: List available repositories and workspaces indexed by CodeAlive.
3.  **`search_code`**: Search for code snippets across your datasources using CodeAlive's semantic search. If your API key is assigned to exactly one datasource, specifying the datasource is optional.

## Getting Started

### Prerequisites

*   Python 3.11
*   [uv](https://github.com/astral-sh/uv) (recommended) or pip
*   A CodeAlive account and API Key

### Getting an API Key

1.  Log in to your CodeAlive account at [https://app.codealive.ai/](https://app.codealive.ai/).
2.  Navigate to the **API Keys** section (under Organization).
3.  Click on "**+ Create API Key**".
4.  Give your key a descriptive name (e.g., "My Local MCP Key") and select the appropriate scope (e.g., "All Data Sources" or select specific ones).
5.  Click "**Create**".
6.  **Important:** Copy the generated API key immediately and store it securely. You won't be able to see it again after closing the dialog.

### Installation

#### Installing with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/CodeAlive-AI/codealive-mcp.git
cd codealive-mcp

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
uv pip install -e .
```

#### Installing with pip

```bash
# Clone the repository
git clone https://github.com/CodeAlive-AI/codealive-mcp.git
cd codealive-mcp

# Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
pip install -e .
```

#### Installing via Smithery

To install CodeAlive for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@CodeAlive-AI/codealive-mcp):

```bash
npx -y @smithery/cli install @CodeAlive-AI/codealive-mcp --client claude
```

## Configuration

Configure the server using environment variables or command-line arguments.

### Environment Variables

The following environment variables are supported:

*   `CODEALIVE_API_KEY`: Your CodeAlive API key. (Required unless passed via `--api-key`)

### Command Line Options

*   `--api-key`: Your CodeAlive API key. Overrides the `CODEALIVE_API_KEY` environment variable.
*   `--transport`: Transport type: `"stdio"` (default) or `"sse"`.
*   `--host`: Host address for SSE transport (default: `0.0.0.0`).
*   `--port`: Port for SSE transport (default: `8000`).
*   `--debug`: Enable debug mode with verbose logging to standard output/error.

## Integrating with AI Clients

Below are configuration examples for popular AI clients. Remember to replace placeholders like `/path/to/your/codealive-mcp` and `YOUR_API_KEY_HERE` with your actual values. Using environment variables (`env` block) is generally recommended over putting the API key directly in the configuration file.

### Continue

1.  Configure the MCP server in your project's `.continue/config.yaml` or globally in `~/.continue/config.yaml`:

    ```yaml
    # ~/.continue/config.yaml or ./.continue/config.yaml
    mcpServers:
      - name: CodeAlive
        command: /path/to/your/codealive-mcp/.venv/bin/python # Or use 'uv' if preferred (see Cursor example)
        args:
          - /path/to/your/codealive-mcp/src/codealive_mcp_server.py
          - --debug # Optional: Enable debug logging
        env:
          CODEALIVE_API_KEY: YOUR_API_KEY_HERE
    ```

2.  Restart Continue or reload the configuration.

### Claude Code

#### 1. Locate Your Configuration File

Claude Code reads settings from the following locations:

* **User-wide (global):**

  * **macOS/Linux:** `~/.claude/settings.json`
  * **Windows:** `%USERPROFILE%\.claude\settings.json`
* **Project-level (overrides global):**

  * `<project-root>/.claude/settings.json`
  * **Local (not checked in):** `<project-root>/.claude/settings.local.json`

If the file doesn’t exist, create it.

#### 2. Add Your MCP Server Configuration

Edit your chosen `settings.json` and add (or merge) a top-level `"mcpServers"` block:

```jsonc
{
  // ...existing settings...

  "mcpServers": {
    "codealive": {
      "command": "/path/to/your/codealive-mcp/.venv/bin/python",
      "args": [
        "/path/to/your/codealive-mcp/src/codealive_mcp_server.py",
        "--debug" // Optional: enable debug logging
      ],
      "env": {
        "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

* **`command`**: Path to the executable (Python, Node, etc.) for your MCP server.
* **`args`**: Arguments for launching the server.
* **`env`**: Environment variables (API keys, etc.) needed by your server.

If you already have settings, merge this block without removing other configuration.

#### 3. Restart Claude Code

1. Quit all running Claude Code sessions (terminals or apps).
2. Reopen Claude Code, or start it in your terminal.
3. Check the integration by running `/tools` or verifying that your tools appear in the tool list.

---

**CodeAlive MCP server should now be available in Claude Code!**
For more details, see [Anthropic’s MCP docs](https://docs.anthropic.com/claude/docs/mcp).


### Claude Desktop

1.  Edit your Claude Desktop configuration file:
    *   **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
    *   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json` (usually `C:\Users\YourUsername\AppData\Roaming\Claude\claude_desktop_config.json`)

2.  Add the MCP server configuration:

    ```json
    {
      "mcpServers": {
        "codealive": {
          "command": "/path/to/your/codealive-mcp/.venv/bin/python",
          "args": [
            "/path/to/your/codealive-mcp/src/codealive_mcp_server.py",
            "--debug" // Optional: Enable debug logging
          ],
          "env": {
            "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
          }
        }
      }
    }
    ```
    *(Ensure this merges correctly if the file already has content)*

3.  Restart Claude Desktop completely.

### Visual Studio Code with GitHub Copilot

1.  Open VS Code settings (JSON) using the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`) and selecting "Preferences: Open User Settings (JSON)".

2.  Add the MCP server configuration to your `settings.json`:

    ```json
    {
      // ... other settings ...
      "mcp": {
        "servers": {
          "codealive": {
            "command": "uv",
            "args": [
              "--directory",
              "/path/to/your/codealive-mcp", // Path to the MCP server project root
              "run",
              "python",
              "src/codealive_mcp_server.py",
              "--debug" // Optional: Enable debug logging
            ],
            "env": {
              "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
            }
          }
        }
      }
      // ... other settings ...
    }
    ```
    *(Ensure this merges correctly with existing settings)*

3.  Restart VS Code. Ensure the GitHub Copilot extension is configured to potentially use MCP servers if required by its version/settings.

### Cursor

1.  Open Cursor settings (`Cmd+,` or `Ctrl+,`).
2.  Navigate to the "MCP" section in the left panel.
3.  Click "Add new global MCP server".
4.  Enter the following JSON configuration, updating paths and API key:

    ```json
    {
      "mcpServers": {
        "codealive": {
          "command": "uv",
          "args": [
            "--directory",
            "/path/to/your/codealive-mcp", // Path to the MCP server project root
            "run",
            "python",
            "src/codealive_mcp_server.py",
            "--debug" // Optional: Enable debug logging
          ],
          "env": {
            "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
          }
        }
      }
    }
    ```

5.  Save the configuration.
6.  Restart Cursor completely.

## Using Python Directly

If you prefer not to use `uv`, you can invoke the server script directly using the Python interpreter from your virtual environment. Update the `command` and `args` in the client configurations accordingly.

### Claude Desktop with Python

```json
{
  "mcpServers": {
    "codealive": {
      "command": "/path/to/your/codealive-mcp/.venv/bin/python", // Full path to python in venv
      "args": [
        "/path/to/your/codealive-mcp/src/codealive_mcp_server.py",
        "--debug" // Optional
      ],
      "env": {
        "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Cursor with Python

```json
{
  "mcpServers": {
    "codealive": {
      "command": "/path/to/your/codealive-mcp/.venv/bin/python",
      "args": [
        "/path/to/your/codealive-mcp/src/codealive_mcp_server.py",
        "--debug" // Optional
      ],
      "env": {
        "CODEALIVE_API_KEY": "YOUR_API_KEY_HERE"
      }
    }
  }
}
```

## Troubleshooting

If the MCP server isn't working correctly with your AI client, follow these steps:

1.  **Enable Debug Logging:** Add the `--debug` flag to the `args` in your client's MCP configuration. This will print verbose logs from the MCP server itself to its standard output/error stream. Where this stream goes depends on how the client manages the MCP process.
2.  **Check MCP Server Output:**
    *   Try running the server command directly in your terminal (activate the virtual environment first):
        ```bash
        # Activate venv first!
        export CODEALIVE_API_KEY="YOUR_API_KEY_HERE"
        python src/codealive_mcp_server.py --debug --transport stdio
        ```
    *   Look for any error messages, especially related to API key validation or connection issues.
3.  **Check Client Logs:** Consult the documentation or settings for your specific AI client to find its log files. Look for errors related to starting or communicating with the "codealive" MCP server.
    *   **Claude Desktop:**
        *   Check the main application logs.
        *   Look for MCP-specific logs:
            *   macOS: `~/Library/Logs/Claude/mcp.log` and `~/Library/Logs/Claude/mcp-server-codealive.log`
            *   Windows: `%LOCALAPPDATA%\Claude\Logs\mcp.log` and `%LOCALAPPDATA%\Claude\Logs\mcp-server-codealive.log` (Path is typically `C:\Users\YourUsername\AppData\Local\Claude\Logs`)
    *   **Cursor:**
        *   Use the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) -> `Developer: Toggle Developer Tools` -> Console tab (for browser-level errors).
        *   **Check the Output Panel:** Go to `View` -> `Output` (or click `Output` in the bottom panel). In the dropdown menu on the right side of the Output panel, look for a channel named `CodeAlive`, `MCP`, or related to the server process. This often contains the direct stdout/stderr from the MCP server if `--debug` is enabled.
        *   Use the Command Palette -> `Developer: Open Logs Folder`. Check files within, especially related to the main process or extension host.
        *   Log folder locations:
            *   macOS: `~/Library/Application Support/Cursor/logs/`
            *   Windows: `%APPDATA%\Cursor\logs\` (Typically `C:\Users\YourUsername\AppData\Roaming\Cursor\logs\`)
    *   **VS Code (Continue / Copilot):**
        *   Use the Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`) -> `Developer: Toggle Developer Tools` -> Console tab (for browser-level errors).
        *   **Check the Output Panel:** Go to `View` -> `Output` (or click `Output` in the bottom panel). In the dropdown menu on the right side of the Output panel, look for a channel named `CodeAlive`, `MCP`, `GitHub Copilot`, or `Continue`. The MCP server logs (especially with `--debug`) might be routed here.
        *   Use the Command Palette -> `Developer: Show Logs...` -> Select `Extension Host` from the dropdown. Look for errors related to Copilot or Continue extensions trying to communicate via MCP.
        *   For Continue specific logs: Use Command Palette -> `Continue: Focus on Continue Console View` (requires enabling `Continue: Enable Console` in settings). See [Continue Troubleshooting Docs](https://docs.continue.dev/troubleshooting#check-the-logs).
4.  **Verify Configuration:** Double-check the `command`, `args`, and `env` paths and values in your client's MCP configuration file. Ensure JSON/YAML syntax is correct.
5.  **API Key:** Ensure your `CODEALIVE_API_KEY` is correct.


If problems persist, consider opening an issue on the CodeAlive MCP server repository (if available) with relevant logs and configuration details (masking your API key).

You can also contact our support team at support@codealive.ai for further assistance.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 
