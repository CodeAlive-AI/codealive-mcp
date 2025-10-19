"""Repository overview tool for CodeAlive MCP server."""

from typing import Optional
from xml.etree import ElementTree as ET

from mcp.server.fastmcp import Context

from core.config import get_api_key_from_context
from core.logging import log_api_request, log_api_response, logger
from utils.errors import (
    handle_api_error,
    normalize_data_source_names,
    format_data_source_names,
)
import httpx


async def get_repo_overview(
    ctx: Context,
    data_sources: Optional[list[str]] = None
) -> str:
    """Get high-level overview of repositories including purpose, responsibilities, ubiquitous language, and domain descriptions.

    This tool retrieves domain-focused information about repositories to help users understand
    the business context and vocabulary of codebases. It returns structured information including:
    - Purpose: What the repository is for
    - Responsibilities: What it does
    - Ubiquitous Language: Domain-specific terminology and concepts
    - Domain(s): Business domains covered with their vocabulary

    Args:
        ctx: FastMCP context containing API client and configuration
        data_sources: Optional list of repository/workspace names. If not provided, returns
                     overviews for all available data sources

    Returns:
        XML formatted string containing repository overviews in markdown format

    Example:
        # Get overview for specific repositories
        result = await get_repo_overview(ctx, ["my-backend-api", "frontend-app"])

        # Get overviews for all repositories
        result = await get_repo_overview(ctx)

        # Example output structure:
        # <repository_overviews>
        #   <repository name="my-backend-api">
        #     <overview>
        #       # Purpose
        #       Backend API for e-commerce platform
        #
        #       ## Responsibilities
        #       - Handle user authentication
        #       - Process orders and payments
        #
        #       ## Ubiquitous Language
        #       - Order: A customer purchase request
        #       - Cart: Collection of items before checkout
        #
        #       ## Domains
        #       ### E-commerce
        #       - Product catalog management
        #       - Order processing
        #     </overview>
        #   </repository>
        # </repository_overviews>
    """
    try:
        # Get context and API key
        context = ctx.request_context.lifespan_context
        api_key = get_api_key_from_context(ctx)

        # Normalize and format data_sources if provided
        data_sources = normalize_data_source_names(data_sources)

        # Build request URL and params
        url = f"{context.base_url}/api/overview"
        params = {}

        if data_sources:
            formatted_names = format_data_source_names(data_sources)
            params = formatted_names

        # Log and execute GET request
        log_api_request(logger, "GET", url, params)

        headers = {"Authorization": f"Bearer {api_key}"}
        response = await context.client.get(url, headers=headers, params=params)
        response.raise_for_status()

        # Parse JSON response
        overview_data = response.json()
        log_api_response(logger, response.status_code, overview_data)

        # Transform to XML format
        root = ET.Element("repository_overviews")

        for repo in overview_data:
            repo_element = ET.SubElement(root, "repository")
            repo_element.set("name", repo.get("name", "unknown"))

            overview_element = ET.SubElement(repo_element, "overview")
            overview_element.text = repo.get("overview", "")

        # Convert to string with proper formatting
        xml_string = ET.tostring(root, encoding="unicode", method="xml")

        return xml_string

    except httpx.HTTPError as e:
        return handle_api_error(ctx, e, "get repository overview")
    except Exception as e:
        return handle_api_error(ctx, e, "get repository overview")
