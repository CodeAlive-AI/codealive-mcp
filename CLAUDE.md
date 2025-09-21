# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation and Setup
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Running the MCP Server
```bash
# Basic run with stdio transport
python src/codealive_mcp_server.py

# With debug mode enabled
python src/codealive_mcp_server.py --debug

# With SSE transport
python src/codealive_mcp_server.py --transport sse --host 0.0.0.0 --port 8000

# With custom API key and base URL
python src/codealive_mcp_server.py --api-key YOUR_KEY --base-url https://custom.url
```

### Docker Usage
```bash
# Build Docker image
docker build -t codealive-mcp .

# Run with Docker
docker run --rm -i -e CODEALIVE_API_KEY=your_key_here codealive-mcp
```

## Architecture

This is a Model Context Protocol (MCP) server that provides AI clients with access to CodeAlive's semantic code search and analysis capabilities.

### Core Components

- **`codealive_mcp_server.py`**: Main server implementation using FastMCP framework
- **Three main tools**: `chat_completions`, `codebase_search`, `get_data_sources`
- **CodeAliveContext**: Manages HTTP client and API credentials
- **Async lifespan management**: Handles client setup/teardown

### Key Architectural Patterns

1. **FastMCP Framework**: Uses modern async Python MCP implementation with lifespan context management
2. **HTTP Client Management**: Single persistent httpx.AsyncClient with proper connection pooling
3. **Streaming Support**: Implements streaming chat completions with proper chunk parsing
4. **Environment Configuration**: Supports both .env files and command-line arguments with precedence
5. **Error Handling**: Comprehensive HTTP status code handling with user-friendly error messages

### Data Flow

1. AI client connects to MCP server via stdio/SSE transport
2. Client calls tools (`get_data_sources` → `codebase_search` → `chat_completions`)
3. MCP server translates tool calls to CodeAlive API requests
4. CodeAlive API returns semantic search results or chat completions
5. Server formats and returns results to AI client

### Environment Variables

- `CODEALIVE_API_KEY`: Required API key for CodeAlive service
- `CODEALIVE_BASE_URL`: API base URL (defaults to https://app.codealive.ai)
- `CODEALIVE_IGNORE_SSL`: Set to disable SSL verification (debug mode)

### Data Source Types

- **Repository**: Individual code repositories with URL and repository ID
- **Workspace**: Collections of repositories accessible via workspace ID
- Tool calls can target specific repositories or entire workspaces for broader context

### Integration Patterns

The server is designed to integrate with:
- Claude Desktop/Code (via settings.json configuration)
- Cursor (via MCP settings panel)
- VS Code with GitHub Copilot (via settings.json)
- Continue (via config.yaml)
- Any MCP-compatible AI client

Key integration consideration: AI clients should use `get_data_sources` first to discover available repositories/workspaces, then use those IDs for targeted search and chat operations.