"""
CodeAlive MCP Server - Main entry point.

A Model Context Protocol server for semantic code search and analysis using CodeAlive API.
"""

import argparse
import datetime
import os
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastmcp import FastMCP
from loguru import logger
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Load environment variables
project_dir = Path(__file__).parent.parent
dotenv_path = project_dir / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import core components
from core import Config, MetadataAwareHostOriginGuardMiddleware, build_oauth_provider, codealive_lifespan, setup_logging, setup_debug_logging, init_tracing, normalize_base_url, _server_ready
import core.client as _client_module  # for /ready flag access
from middleware import N8NRemoveParametersMiddleware, ObservabilityMiddleware
from tools import (
    get_data_sources,
    semantic_search,
    grep_search,
    get_repository_ontology,
    get_file_tree,
    read_file,
    fetch_artifacts,
    get_artifact_relationships,
    get_artifact_query_schema,
    query_artifact_metadata,
    chat,
)


def _package_version() -> str:
    try:
        return version("codealive-mcp")
    except PackageNotFoundError:
        return "unknown"


# Initialize FastMCP server with lifespan and enhanced system instructions
mcp = FastMCP(
    name="CodeAlive MCP Server",
    version=_package_version(),
    instructions="""
    Use CodeAlive to inspect indexed repositories and workspaces.

    Default workflow: DISCOVER → SEARCH → READ → EXPAND.
    1. Call get_data_sources to identify visible data sources.
    2. Use get_repository_ontology for one-repository orientation.
    3. Use semantic_search for meaning and grep_search for literal or regex matches.
    4. Read evidence with read_file or fetch_artifacts using returned identifiers.
    5. Expand known identifiers with get_artifact_relationships. Use ArtifactQuery tools for metadata analytics.

    Call chat only when the user explicitly requests that tool. Chat is stateless; include prior findings,
    identifiers, assumptions, scope, and constraints in every question. Deprecated MCP aliases are absent.
    """,
    lifespan=codealive_lifespan
)

# Register middleware — order matters: n8n cleanup runs first, then tracing wraps the clean call
mcp.add_middleware(N8NRemoveParametersMiddleware())
mcp.add_middleware(ObservabilityMiddleware())


def _runtime_metadata() -> dict[str, str]:
    return {
        "version": _package_version(),
        "sourceRevision": os.getenv("CODEALIVE_MCP_SOURCE_REVISION", "unknown"),
    }


# Add health check endpoint for AWS ALB
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for load balancer."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "service": "codealive-mcp-server",
        **_runtime_metadata(),
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


# Register tools with metadata suitable for Claude Desktop and MCP directories.
_READ_ONLY_TOOL = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}

mcp.tool(
    title="List Data Sources",
    annotations=_READ_ONLY_TOOL,
)(get_data_sources)
mcp.tool(
    title="Semantic Search",
    annotations=_READ_ONLY_TOOL,
)(semantic_search)
mcp.tool(
    title="Grep Search",
    annotations=_READ_ONLY_TOOL,
)(grep_search)
mcp.tool(
    title="Get Repository Ontology",
    annotations=_READ_ONLY_TOOL,
)(get_repository_ontology)
mcp.tool(
    title="Get File Tree",
    annotations=_READ_ONLY_TOOL,
)(get_file_tree)
mcp.tool(
    title="Read File",
    annotations=_READ_ONLY_TOOL,
)(read_file)
mcp.tool(
    title="Fetch Artifacts",
    annotations=_READ_ONLY_TOOL,
)(fetch_artifacts)
mcp.tool(
    title="Inspect Artifact Relationships",
    annotations=_READ_ONLY_TOOL,
)(get_artifact_relationships)
mcp.tool(
    title="Get ArtifactQuery Schema",
    annotations=_READ_ONLY_TOOL,
)(get_artifact_query_schema)
mcp.tool(
    title="Query Artifact Metadata",
    annotations=_READ_ONLY_TOOL,
)(query_artifact_metadata)
mcp.tool(
    title="Chat About Codebase",
    annotations=_READ_ONLY_TOOL,
)(chat)


def main():
    """Main entry point for the server."""
    parser = argparse.ArgumentParser(description="CodeAlive MCP Server")
    parser.add_argument("--api-key", help="CodeAlive API Key")
    parser.add_argument("--base-url", help="CodeAlive Base URL")
    parser.add_argument("--transport", help="Transport type (stdio or http)", default="stdio")
    parser.add_argument("--host", help="Host for HTTP transport", default="127.0.0.1")
    parser.add_argument("--port", help="Port for HTTP transport", type=int, default=8000)
    parser.add_argument(
        "--allowed-host",
        action="append",
        help="Host accepted by HTTP transport protection; repeat for multiple hosts",
    )
    parser.add_argument(
        "--allowed-origin",
        action="append",
        help="Origin accepted by HTTP transport protection; repeat for multiple origins",
    )
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

    # Debug logging must not weaken transport security. TLS verification is disabled only
    # through the explicit opt-in flag used for local self-signed development endpoints.
    if args.ignore_ssl:
        os.environ["CODEALIVE_IGNORE_SSL"] = "true"
        logger.warning("SSL certificate validation disabled by --ignore-ssl flag")

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

        oauth_config = Config.from_environment()
        if oauth_config.oauth_enabled:
            if not oauth_config.oauth_internal_client_secret:
                logger.error(
                    "OAuth mode requires CODEALIVE_OAUTH_INTERNAL_CLIENT_SECRET for downstream token exchange"
                )
                sys.exit(1)
            mcp.auth = build_oauth_provider(oauth_config)

    if not base_url:
        logger.info(
            "CODEALIVE_BASE_URL not set, using default: https://app.codealive.ai"
        )

    # Run the server with the selected transport
    if args.transport == "http":
        oauth_config = Config.from_environment()
        mcp_path = urlsplit(oauth_config.mcp_resource).path or "/api"
        allowed_hosts = args.allowed_host or [
            value.strip()
            for value in os.getenv("CODEALIVE_MCP_ALLOWED_HOSTS", "").split(",")
            if value.strip()
        ]
        allowed_origins = args.allowed_origin or [
            value.strip()
            for value in os.getenv("CODEALIVE_MCP_ALLOWED_ORIGINS", "").split(",")
            if value.strip()
        ]
        transport_middleware = None
        host_origin_protection = True
        if oauth_config.oauth_enabled:
            metadata_path = f"/.well-known/oauth-protected-resource{mcp_path}"
            transport_middleware = [
                Middleware(
                    MetadataAwareHostOriginGuardMiddleware,
                    metadata_path=metadata_path,
                    allowed_hosts=allowed_hosts or None,
                    allowed_origins=allowed_origins or None,
                )
            ]
            host_origin_protection = False
        # Use /api path to avoid conflicts with health endpoint
        mcp.run(
            transport="http",
            host=args.host,
            port=args.port,
            path=mcp_path,
            stateless_http=True,
            middleware=transport_middleware,
            host_origin_protection=host_origin_protection,
            allowed_hosts=allowed_hosts or None,
            allowed_origins=allowed_origins or None,
            uvicorn_config={
                "forwarded_allow_ips": "*",
            },
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
