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
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse

# Load environment variables
project_dir = Path(__file__).parent.parent
dotenv_path = project_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import core components
from core import codealive_lifespan, setup_logging, setup_debug_logging, init_tracing, normalize_base_url, _server_ready
import core.client as _client_module  # for /ready flag access
from middleware import N8NRemoveParametersMiddleware, ObservabilityMiddleware
from tools import codebase_consultant, get_data_sources, fetch_artifacts, codebase_search, get_artifact_relationships

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

    When working with a codebase, follow this workflow:
    1. First use `get_data_sources` to identify available repositories and workspaces
    2. Use `codebase_search` to find relevant files — returns paths, descriptions, and identifiers
    3. To get full content:
       - For repos in your working directory: use `Read()` on the local files
       - For external repos: use `fetch_artifacts` with identifiers from search results
    4. Use `codebase_consultant` for in-depth analysis and synthesized answers

    For effective code exploration:
    - Start with broad queries to understand the overall structure
    - Use specific function/class names when looking for particular implementations
    - Combine natural language with code patterns in your queries
    - Always use "auto" search mode by default; it intelligently selects the appropriate search depth
    - IMPORTANT: Only use "deep" search mode for very complex conceptual queries as it's resource-intensive
    - Use `description_detail="full"` in search when you need richer descriptions before fetching content
    - Remember that context from previous messages is maintained in the same conversation

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

# Register middleware — order matters: n8n cleanup runs first, then tracing wraps the clean call
mcp.add_middleware(N8NRemoveParametersMiddleware())
mcp.add_middleware(ObservabilityMiddleware())


# Add health check endpoint for AWS ALB
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for load balancer."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "service": "codealive-mcp-server"
    })


# Readiness endpoint — checks the module-level flag set by codealive_lifespan
@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> JSONResponse:
    """Readiness probe: returns 200 only when the lifespan context is active."""
    if _client_module._server_ready:
        return JSONResponse({
            "status": "ready",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "service": "codealive-mcp-server",
        })
    return JSONResponse(
        {"status": "not_ready", "reason": "lifespan not initialized"},
        status_code=503,
    )


# Register tools
mcp.tool()(codebase_consultant)
mcp.tool()(get_data_sources)
mcp.tool()(codebase_search)
mcp.tool()(fetch_artifacts)
mcp.tool()(get_artifact_relationships)


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

    # Bootstrap logging early (before any log output)
    debug = args.debug
    if debug:
        os.environ["DEBUG_MODE"] = "true"
    setup_logging(debug=debug)

    # Bootstrap OTel tracing
    init_tracing()

    # Command line arguments take precedence over .env file/environment variables
    if args.api_key:
        os.environ["CODEALIVE_API_KEY"] = args.api_key

    if args.base_url:
        normalized_base_url = normalize_base_url(args.base_url)
        os.environ["CODEALIVE_BASE_URL"] = normalized_base_url
        logger.info("Using base URL from command line: {url}", url=normalized_base_url)

    # Disable SSL verification if explicitly requested or in debug mode
    if args.ignore_ssl or debug:
        os.environ["CODEALIVE_IGNORE_SSL"] = "true"
        if args.ignore_ssl:
            logger.warning("SSL certificate validation disabled by --ignore-ssl flag")
        elif debug:
            logger.warning("SSL certificate validation disabled in debug mode")

    if debug:
        logger.debug(
            "Debug environment",
            cwd=os.getcwd(),
            script=__file__,
            dotenv_path=str(dotenv_path),
            dotenv_exists=os.path.exists(dotenv_path),
        )

    # Set transport mode for validation
    os.environ["TRANSPORT_MODE"] = args.transport

    api_key = os.environ.get("CODEALIVE_API_KEY", "")
    base_url = os.environ.get("CODEALIVE_BASE_URL", "")

    if args.transport == "stdio":
        # STDIO mode: require API key in environment
        if not api_key:
            logger.error("STDIO mode requires CODEALIVE_API_KEY environment variable")
            sys.exit(1)
        logger.info(
            "STDIO mode: API key from environment (ends with ...{suffix})",
            suffix=api_key[-4:] if len(api_key) > 4 else "****",
        )
    else:
        # HTTP mode: API keys should be provided via Authorization headers
        if api_key:
            logger.warning(
                "HTTP mode detected CODEALIVE_API_KEY in environment — "
                "it will be ignored; use Authorization: Bearer headers instead"
            )
        logger.info("HTTP mode: API keys extracted from Authorization: Bearer headers")

    if not base_url:
        logger.info(
            "CODEALIVE_BASE_URL not set, using default: https://app.codealive.ai"
        )

    # Run the server with the selected transport
    if args.transport == "http":
        # Use /api path to avoid conflicts with health endpoint
        mcp.run(
            transport="http",
            host=args.host,
            port=args.port,
            path="/api",
            stateless_http=True,
            uvicorn_config={
                "forwarded_allow_ips": "*",
            },
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
