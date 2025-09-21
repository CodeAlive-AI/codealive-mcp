"""Error handling utilities for CodeAlive MCP server."""

from typing import Optional
import httpx
from fastmcp import Context


async def handle_api_error(
    ctx: Context,
    error: Exception,
    operation: str = "API operation"
) -> str:
    """
    Handle API errors consistently across all tools.

    Args:
        ctx: FastMCP context for logging
        error: The exception that occurred
        operation: Description of the operation that failed

    Returns:
        User-friendly error message string
    """
    if isinstance(error, httpx.HTTPStatusError):
        error_code = error.response.status_code
        error_detail = error.response.text

        # Map status codes to user-friendly messages
        error_messages = {
            401: "Authentication error (401): Invalid API key or insufficient permissions",
            403: "Authorization error (403): You don't have permission to access this resource",
            404: "Not found error (404): The requested resource could not be found",
            429: "Rate limit exceeded (429): Too many requests, please try again later",
            500: f"Server error (500): The CodeAlive service encountered an issue",
            502: "Bad gateway (502): The CodeAlive service is temporarily unavailable",
            503: "Service unavailable (503): The CodeAlive service is under maintenance",
        }

        if error_code in error_messages:
            error_msg = error_messages[error_code]
        elif error_code >= 500:
            error_msg = f"Server error ({error_code}): The CodeAlive service encountered an issue"
        else:
            error_msg = f"HTTP error: {error_code} - {error_detail[:200]}"  # Limit detail length

        await ctx.error(error_msg)
        return f"Error: {error_msg}"
    else:
        error_msg = f"Error during {operation}: {str(error)}"
        await ctx.error(error_msg)
        return f"Error: {error_msg}. Please check your input parameters and try again."


def format_data_source_ids(data_sources: Optional[list]) -> list:
    """
    Convert various data source formats to the API's expected format.

    Handles:
    - Simple string IDs: ["id1", "id2"]
    - Dict format: [{"id": "id1"}, {"type": "repository", "id": "id2"}]
    - Mixed formats
    - None/empty values

    Args:
        data_sources: List of data sources in various formats

    Returns:
        List of dicts with 'id' field: [{"id": "id1"}, {"id": "id2"}]
    """
    if not data_sources:
        return []

    formatted = []
    for ds in data_sources:
        if isinstance(ds, str) and ds:
            # Simple string ID
            formatted.append({"id": ds})
        elif isinstance(ds, dict) and ds.get("id"):
            # Already has id field - extract just the id
            formatted.append({"id": ds["id"]})
        # Skip None/empty values

    return formatted