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

### Testing

#### Quick Smoke Test
After making local changes, quickly verify everything works:
```bash
# Using make (recommended)
make smoke-test

# Or directly
python smoke_test.py

# With valid API key for full testing
CODEALIVE_API_KEY=your_key python smoke_test.py
```

The smoke test:
- ✓ Verifies server starts and connects via stdio
- ✓ Checks all tools are registered correctly
- ✓ Tests each tool responds appropriately
- ✓ Validates parameter handling
- ✓ Runs in ~5 seconds

#### Unit Tests
Run comprehensive unit tests with pytest:
```bash
# Using make
make unit-test

# Or directly
pytest src/tests/ -v

# With coverage
pytest src/tests/ -v --cov=src
```

#### All Tests
Run both smoke tests and unit tests:
```bash
make test
```

## Architecture

This is a Model Context Protocol (MCP) server that provides AI clients with access to CodeAlive's semantic code search and analysis capabilities.

### Core Components

- **`codealive_mcp_server.py`**: Main server implementation using FastMCP framework
- **Three main tools**: `codebase_consultant`, `codebase_search`, `get_data_sources`
- **CodeAliveContext**: Manages HTTP client and API credentials
- **Async lifespan management**: Handles client setup/teardown

### Key Architectural Patterns

1. **FastMCP Framework**: Uses modern async Python MCP implementation with lifespan context management
2. **HTTP Client Management**: Single persistent httpx.AsyncClient with proper connection pooling
3. **Streaming Support**: Implements streaming chat completions with proper chunk parsing
4. **Environment Configuration**: Supports both .env files and command-line arguments with precedence
5. **Error Handling**: Comprehensive HTTP status code handling with user-friendly error messages
6. **N8N Middleware**: Strips extra parameters (sessionId, action, chatInput, toolCallId) from n8n tool calls before validation

### Data Flow

1. AI client connects to MCP server via stdio/SSE transport
2. Client calls tools (`get_data_sources` → `codebase_search` → `codebase_consultant`)
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
- n8n (via AI Agent node with MCP tools)
- Any MCP-compatible AI client

Key integration considerations:
- AI clients should use `get_data_sources` first to discover available repositories/workspaces, then use those IDs for targeted search and chat operations
- **n8n Integration**: The server includes middleware to automatically strip n8n's extra parameters (sessionId, action, chatInput, toolCallId) from tool calls, so n8n works out of the box without any special configuration

## Publishing and Releases

### Version Management
When making significant changes, consider incrementing the version in `pyproject.toml`:
```toml
version = "0.3.0"  # Increment for new features, bug fixes, or breaking changes
```

### Automated Publishing
The project uses automated publishing:
- **Trigger**: Push version change to `main` branch
- **Process**: Tests → Build → Docker → MCP Registry → GitHub Release
- **Result**: Available at `io.github.codealive-ai/codealive-mcp` in MCP Registry

### Version Guidelines
- **Patch** (0.2.0 → 0.2.1): Bug fixes, minor improvements
- **Minor** (0.2.0 → 0.3.0): New features, enhancements
- **Major** (0.2.0 → 1.0.0): Breaking changes, major releases

When implementing features or fixes, evaluate if they warrant a version bump for users to benefit from the changes through the MCP Registry.