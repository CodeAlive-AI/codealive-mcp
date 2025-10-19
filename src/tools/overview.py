"""Repository overview tool for CodeAlive MCP server."""

from typing import Optional
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import (
    handle_api_error,
    normalize_data_source_names,
    format_data_source_names,
)


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
    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        api_key = get_api_key_from_context(ctx)

        # Normalize data_sources (handles Claude Desktop serialization issues)
        data_source_names = normalize_data_source_names(data_sources)

        # Build request params
        params = {}
        if data_source_names and len(data_source_names) > 0:
            formatted_names = format_data_source_names(data_source_names)
            params = formatted_names

        # Prepare headers
        headers = {"Authorization": f"Bearer {api_key}"}

        # Log the request
        endpoint = "/api/overview"
        full_url = urljoin(context.base_url, endpoint)
        request_id = log_api_request("GET", full_url, headers, params=params)

        # Make API request
        response = await context.client.get(endpoint, headers=headers, params=params)

        # Log the response
        log_api_response(response, request_id)

        response.raise_for_status()

        # Parse JSON response
        overview_data = response.json()

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

    except (httpx.HTTPStatusError, Exception) as e:
        return await handle_api_error(ctx, e, "get repository overview")
