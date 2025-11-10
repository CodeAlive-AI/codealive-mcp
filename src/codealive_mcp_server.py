"""
CodeAlive MCP Server - Main entry point.

A Model Context Protocol server for semantic code search and analysis using CodeAlive API.
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Load environment variables
project_dir = Path(__file__).parent.parent
dotenv_path = project_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import core components
from core import codealive_lifespan, setup_debug_logging
from middleware import N8NRemoveParametersMiddleware
from tools import codebase_consultant, get_data_sources, codebase_search

# Initialize FastMCP server with lifespan and enhanced system instructions
mcp = FastMCP(
    name="CodeAlive MCP Server",
    instructions="""
    This server provides access to the CodeAlive API for AI-powered code assistance and code understanding.

    CodeAlive enables you to:
    - Analyze code repositories and workspaces
    - Search through code using natural language
    - Understand code structure, dependencies, and patterns
    - Answer questions about code implementation details
    - Integrate with local git repositories for seamless code exploration

    When working with a codebase:
    1. First use `get_data_sources` to identify available repositories and workspaces
    2. Then use `codebase_search` to find relevant files and code snippets
    3. Finally, use `chat_completions` for in-depth analysis of the code

    For effective code exploration:
    - Start with broad queries to understand the overall structure
    - Use specific function/class names when looking for particular implementations
    - Combine natural language with code patterns in your queries
    - Always use "auto" search mode by default; it intelligently selects the appropriate search depth
    - IMPORTANT: Only use "deep" search mode for very complex conceptual queries as it's resource-intensive
    - Remember that context from previous messages is maintained in the same conversation

    CRITICAL - include_content parameter usage:
    You MUST intelligently determine if searching CURRENT or EXTERNAL repositories:

    - CURRENT repository (user's working directory): include_content=false
      * You have file access → Get paths from search, then use Read tool for latest content
    - EXTERNAL repositories (not in working directory): include_content=true
      * No file access → Must include content in search results

    Use these heuristics to identify CURRENT vs EXTERNAL (combine multiple signals):
    1. Repository/directory name matching (e.g., working in "my-app", repo named "my-app")
    2. Description matching observed codebase (tech stack, architecture, features)
    3. User's language ("this repo", "our code" = CURRENT; "the X service" = EXTERNAL)
    4. URL matching with git remote (when available)
    5. Working context (files you've been reading/editing match this repo)

    When uncertain, use context: Is user asking about their current work or a different service?

    Flexible data source usage:
    - You can use a workspace name as a single data source to search or chat across all its repositories at once
    - Alternatively, you can use specific repository names for more targeted searches
    - For complex queries, you can combine multiple repository names from different workspaces
    - Choose between workspace-level or repository-level access based on the scope of the query

    Repository integration:
    - CodeAlive can connect to repositories you've indexed in the system
    - If a user is working within a git repository that matches a CodeAlive-indexed repository (by URL),
      you can suggest using CodeAlive's search and chat to understand the codebase
    - Data sources include repository URLs to help match with local git repositories

    When analyzing search results:
    - Pay attention to file paths to understand the project structure
    - Look for patterns across multiple matching files
    - Consider the relationships between different code components
    """,
    lifespan=codealive_lifespan
)

# Register middleware to handle n8n extra parameters
# This must be registered BEFORE tools to intercept tool calls
mcp.add_middleware(N8NRemoveParametersMiddleware())


# Add health check endpoint for AWS ALB
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for load balancer."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "service": "codealive-mcp-server"
    })


# Register tools
mcp.tool()(codebase_consultant)
mcp.tool()(get_data_sources)
mcp.tool()(codebase_search)


def main():
    """Main entry point for the server."""
    parser = argparse.ArgumentParser(description="CodeAlive MCP Server")
    parser.add_argument("--api-key", help="CodeAlive API Key")
    parser.add_argument("--base-url", help="CodeAlive Base URL")
    parser.add_argument("--transport", help="Transport type (stdio or http)", default="stdio")
    parser.add_argument("--host", help="Host for HTTP transport", default="0.0.0.0")
    parser.add_argument("--port", help="Port for HTTP transport", type=int, default=8000)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for verbose logging")
    parser.add_argument("--ignore-ssl", action="store_true", help="Ignore SSL certificate validation")

    args = parser.parse_args()

    # Command line arguments take precedence over .env file/environment variables
    if args.api_key:
        os.environ["CODEALIVE_API_KEY"] = args.api_key

    if args.base_url:
        os.environ["CODEALIVE_BASE_URL"] = args.base_url
        print(f"Using base URL from command line: {args.base_url}")

    # Disable SSL verification if explicitly requested or in debug mode
    if args.ignore_ssl or args.debug:
        os.environ["CODEALIVE_IGNORE_SSL"] = "true"
        if args.ignore_ssl:
            print("SSL certificate validation disabled by --ignore-ssl flag")
        elif args.debug:
            print("SSL certificate validation disabled in debug mode")

    # Debug environment if requested
    if args.debug:
        os.environ["DEBUG_MODE"] = "true"
        setup_debug_logging()
        print("\nDEBUG MODE ENABLED")
        print("Environment:")
        print(f"  - Current working dir: {os.getcwd()}")
        print(f"  - Script location: {__file__}")
        print(f"  - Dotenv path: {dotenv_path}")
        print(f"  - Dotenv file exists: {os.path.exists(dotenv_path)}")

    # Set transport mode for validation
    os.environ["TRANSPORT_MODE"] = args.transport

    api_key = os.environ.get("CODEALIVE_API_KEY", "")
    base_url = os.environ.get("CODEALIVE_BASE_URL", "")

    if args.transport == "stdio":
        # STDIO mode: require API key in environment
        if not api_key:
            print("ERROR: STDIO mode requires CODEALIVE_API_KEY environment variable.")
            print("Please set this in your .env file or environment.")
            sys.exit(1)
        print(f"STDIO mode: Using API key from environment (ends with: ...{api_key[-4:] if len(api_key) > 4 else '****'})")
    else:
        # HTTP mode: API keys should be provided via Authorization headers
        if api_key:
            print("WARNING: HTTP mode detected CODEALIVE_API_KEY in environment.")
            print("In production, API keys should be provided via Authorization: Bearer headers.")
            print("Environment variable will be ignored in HTTP mode.")
        print("HTTP mode: API keys will be extracted from Authorization: Bearer headers")

    if not base_url:
        print("WARNING: CODEALIVE_BASE_URL environment variable is not set, using default.")
        print("CodeAlive will connect to the production API at https://app.codealive.ai")

    # Run the server with the selected transport
    if args.transport == "http":
        # Use /api path to avoid conflicts with health endpoint
        mcp.run(transport="http", host=args.host, port=args.port, path="/api", stateless_http=True)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
