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


def normalize_data_source_names(data_sources) -> list:
    """Normalize data source names from various serialization formats."""
    import json

    if not data_sources:
        return []

    if isinstance(data_sources, str):
        stripped = data_sources.strip()
        if stripped.startswith('['):
            try:
                data_sources = json.loads(stripped)
            except json.JSONDecodeError:
                return [data_sources]
        else:
            return [data_sources]

    if not isinstance(data_sources, list):
        return [str(data_sources)]

    result = []
    for ds in data_sources:
        if isinstance(ds, str):
            result.append(ds)
        elif isinstance(ds, dict):
            if ds.get("name"):
                result.append(ds["name"])
            elif ds.get("id"):
                # Backward compatibility with legacy ID payloads
                result.append(ds["id"])

    return result


def format_data_source_names(data_sources: Optional[list]) -> list:
    """Convert various data source inputs to a simple list of data source names."""
    if not data_sources:
        return []

    formatted: list[str] = []

    for ds in data_sources:
        if isinstance(ds, str):
            name = ds.strip()
            if name:
                formatted.append(name)
        elif isinstance(ds, dict):
            name = ds.get("name") or ds.get("id")
            if isinstance(name, str):
                name = name.strip()
                if name:
                    formatted.append(name)
            elif name is not None:
                formatted.append(str(name))
        elif ds is not None:
            # Fallback: cast other primitive types to string
            formatted.append(str(ds))

    return formatted


# Backward compatibility aliases for legacy imports
normalize_data_source_ids = normalize_data_source_names
format_data_source_ids = format_data_source_names
