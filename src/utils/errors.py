"""Error handling utilities for CodeAlive MCP server.

Errors emitted to the model follow a structured shape so the LLM can decide
**whether to retry** and **what to try next**:

    [<tool>] Error: <label>. Retry: yes|no [(<window>)]. Try: (1) ... (2) ...

The ``Retry:`` marker is critical — without it the model can loop on permanent
errors like 401/404, burning tokens and frustrating the user. The ``Try: ...``
hint gives the model a concrete next action instead of hallucinating one.

Per-tool callers can override the default ``Try:`` text via ``recovery_hints``
when a generic hint isn't actionable enough — e.g. a 404 from ``semantic_search``
should suggest ``get_data_sources``, while a 404 from artifact tools should
suggest reusing identifiers returned by v3 search/fetch/read tools.
"""

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError

from core.config import REQUEST_TIMEOUT_SECONDS


def _parse_problem_details(body: str) -> Optional[dict[str, Any]]:
    """Parse a CodeAlive RFC 9457 / legacy error body, return None on mismatch."""
    if not body:
        return None
    try:
        d = json.loads(body)
    except (ValueError, TypeError):
        return None
    return d if isinstance(d, dict) else None


def _summarise_field_errors(d: dict[str, Any]) -> Optional[str]:
    """Render a one-line ``field: msg; field: msg`` summary from RFC 9457
    ``errors`` (a dict-of-lists) or the legacy flat ``validationErrors`` list."""
    errors = d.get("errors")
    if isinstance(errors, dict):
        rendered = [
            f"{field}: {msg}"
            for field, msgs in errors.items()
            for msg in (msgs or [])
        ]
        if rendered:
            return "; ".join(rendered)
    legacy = d.get("validationErrors")
    if isinstance(legacy, list) and legacy:
        return "; ".join(str(x) for x in legacy)
    return None

# GitHub Issues URL is verified in README.md and manifest.json — safe to embed.
_ISSUES_URL = "https://github.com/CodeAlive-AI/codealive-mcp/issues"


def _method_prefix(method: Optional[str]) -> str:
    """Build a `[method] ` prefix for log/error messages, empty if no method given."""
    return f"[{method}] " if method else ""


def format_validation_error(method: str, message: str) -> str:
    """Format a validation error message with the MCP tool/method name prefix.

    Use this for early-return validation errors that don't pass through
    `handle_api_error` so the originating tool is still visible in the message.
    """
    return f"{_method_prefix(method)}Error: {message}"


# ---------------------------------------------------------------------------
# Status-code templates
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _ErrorTemplate:
    """Template for an HTTP-status-mapped error message.

    Attributes:
        label:        Human-readable status description prefixed by the code,
                      e.g. ``"Authentication error (401): Invalid API key..."``.
        retryable:    Whether the LLM should ever retry this on its own.
        retry_window: Short, concrete wait hint (only meaningful when retryable),
                      e.g. ``"wait 30–60s and retry"``.
        default_hint: Generic ``Try: ...`` text used when no per-tool override
                      is provided via ``recovery_hints``.
    """
    label: str
    retryable: bool
    retry_window: Optional[str]
    default_hint: str


_ERROR_TEMPLATES: dict[int, _ErrorTemplate] = {
    400: _ErrorTemplate(
        label="Bad request (400): The CodeAlive service rejected the request",
        retryable=False,
        retry_window=None,
        default_hint=(
            "(1) inspect the field-level errors below and fix the offending parameter, "
            "(2) verify that the request uses canonical Tool API v3 snake_case fields, "
            "(3) if no field errors are surfaced, re-read the tool docstring and verify "
            "the request shape matches"
        ),
    ),
    401: _ErrorTemplate(
        label="Authentication error (401): Invalid API key or insufficient permissions",
        retryable=False,
        retry_window=None,
        default_hint=(
            "(1) verify the CODEALIVE_API_KEY environment variable is set and not empty, "
            "(2) confirm the key has not expired or been revoked, "
            "(3) regenerate the key in your CodeAlive account settings"
        ),
    ),
    403: _ErrorTemplate(
        label="Authorization error (403): You don't have permission to access this resource",
        retryable=False,
        retry_window=None,
        default_hint=(
            "(1) verify the API key has access to the requested data source, "
            "(2) ask the CodeAlive workspace admin to grant access, "
            "(3) call get_data_sources to see what this key can read"
        ),
    ),
    404: _ErrorTemplate(
        label="Not found error (404): The requested resource could not be found",
        retryable=False,
        retry_window=None,
        default_hint=(
            "(1) call get_data_sources to see available data source names, "
            "(2) check spelling and case, "
            "(3) verify any identifiers were returned by a recent semantic_search, grep_search, read_file, or fetch_artifacts"
        ),
    ),
    409: _ErrorTemplate(
        label="Ambiguous data source (409): the identifier matches more than one data source",
        retryable=True,
        retry_window="retry once with data_source set",
        default_hint=(
            "(1) read the candidate data sources in the Detail below — every one will resolve, "
            "(2) retry with data_source set to one candidate's Name or Id; if that data source isn't "
            "the one you want, retry with the next candidate, "
            "(3) do not invent a result"
        ),
    ),
    422: _ErrorTemplate(
        label="Data source not ready (422): The requested data source is still being indexed",
        retryable=True,
        retry_window="wait 1–5 minutes and retry",
        default_hint=(
            "(1) wait for indexing to complete before retrying, "
            "(2) call get_data_sources(ready_only=false) to check the processing state, "
            "(3) try a different data source if available"
        ),
    ),
    429: _ErrorTemplate(
        label="Rate limit exceeded (429): Too many requests, please try again later",
        retryable=True,
        retry_window="wait 30–60s and retry",
        default_hint=(
            "(1) wait at least 30 seconds before retrying, "
            "(2) reduce request frequency if this happens repeatedly, "
            "(3) batch related questions into a single chat call"
        ),
    ),
    500: _ErrorTemplate(
        label="Server error (500): The CodeAlive service encountered an issue",
        retryable=True,
        retry_window="retry once after a few seconds",
        default_hint=(
            "(1) retry the call once, "
            f"(2) if it still fails, the problem is on CodeAlive's side — report it at {_ISSUES_URL} with the request details"
        ),
    ),
    502: _ErrorTemplate(
        label="Bad gateway (502): The CodeAlive service is temporarily unreachable",
        retryable=True,
        retry_window="retry in 10–30s",
        default_hint=(
            "(1) wait 10–30 seconds and retry, "
            "(2) if the error persists for more than a few minutes, the upstream service is down — stop retrying"
        ),
    ),
    503: _ErrorTemplate(
        label="Service unavailable (503): The CodeAlive service is under maintenance",
        retryable=True,
        retry_window="retry in 30–60s",
        default_hint=(
            "(1) wait 30–60 seconds and retry, "
            f"(2) if persistent, report at {_ISSUES_URL}"
        ),
    ),
}


def _format_error(template: _ErrorTemplate, hint: str) -> str:
    """Render a template + hint as the user-facing error string."""
    if template.retryable:
        retry_marker = "Retry: yes"
        if template.retry_window:
            retry_marker = f"Retry: yes ({template.retry_window})"
    else:
        retry_marker = "Retry: no — fix the input or credentials, do not loop"
    return f"{template.label}. {retry_marker}. Try: {hint}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def handle_api_error(
    ctx: Context,
    error: Exception,
    operation: str = "API operation",
    *,
    method: Optional[str] = None,
    recovery_hints: Optional[Mapping[int, str]] = None,
) -> None:
    """
    Handle API errors consistently across all tools.

    Logs the error via ``ctx.error()`` and raises ``ToolError`` so the MCP
    response gets ``isError: true``.  The error text is structured so the LLM
    can act on it without hallucinating: it always carries the HTTP code, an
    explicit ``Retry: yes|no`` marker, and a numbered ``Try: ...`` recovery hint.

    Args:
        ctx: FastMCP context for logging.
        error: The exception that occurred.
        operation: Description of the operation that failed (used in timeout
            and generic-exception messages).
        method: Name of the MCP tool/method that triggered the error. When
            provided, every message is prefixed with ``[method]`` so failures
            are easy to attribute.
        recovery_hints: Optional per-tool overrides for the ``Try: ...`` text,
            keyed by HTTP status code. Use this when a generic hint isn't
            enough for a specific tool.

    Raises:
        ToolError: Always raised — sets ``isError: true`` in the MCP response
            so the agent can distinguish errors from data.
    """
    prefix = _method_prefix(method)

    # Handle timeout errors first
    if isinstance(error, httpx.TimeoutException):
        timeout_minutes = int(REQUEST_TIMEOUT_SECONDS // 60)
        error_msg = (
            f"Request timeout during {operation}: The CodeAlive service did not respond "
            f"within {timeout_minutes} minutes. Retry: yes (wait 30s and retry once). "
            "Try: (1) retry the same call after 30 seconds, "
            "(2) reduce the scope of the query (fewer data_sources, shorter question), "
            "(3) if it still times out, the LLM upstream may be overloaded — stop retrying and try again later"
        )
        await ctx.error(f"{prefix}{error_msg}")
        raise ToolError(f"{prefix}Error: {error_msg}")

    if isinstance(error, httpx.HTTPStatusError):
        error_code = error.response.status_code
        error_detail = error.response.text

        # Parse the CodeAlive RFC 9457 / legacy error body once. The summary is
        # appended to whichever branch handles this status code, so the LLM sees
        # field-level errors and the requestId without scanning raw JSON.
        problem = _parse_problem_details(error_detail)
        field_summary = _summarise_field_errors(problem) if problem else None
        request_id = problem.get("requestId") if problem else None
        rfc_detail = problem.get("detail") if problem else None

        def _enrich(msg: str) -> str:
            extras: list[str] = []
            if rfc_detail and rfc_detail not in msg:
                extras.append(f"Detail: {rfc_detail}")
            if field_summary:
                extras.append(f"Fields: {field_summary}")
            if request_id:
                extras.append(f"requestId={request_id}")
            return msg if not extras else f"{msg} ({' | '.join(extras)})"

        template = _ERROR_TEMPLATES.get(error_code)
        if template is not None:
            hint = (recovery_hints or {}).get(error_code, template.default_hint)
            error_msg = _enrich(_format_error(template, hint))
        elif error_code >= 500:
            # Unknown 5xx — treat as retryable server error
            error_msg = _enrich(
                f"Server error ({error_code}): The CodeAlive service encountered an issue. "
                "Retry: yes (retry once after a few seconds). "
                "Try: (1) retry the call once, "
                f"(2) report a persistent error at {_ISSUES_URL}"
            )
        else:
            # Unknown 4xx — keep raw detail (truncated) and a conservative hint
            error_msg = _enrich(
                f"HTTP error: {error_code} - {error_detail[:200]}. "
                "Retry: no — fix the input. "
                "Try: review the parameters you passed and try a different value"
            )

        await ctx.error(f"{prefix}{error_msg}")
        raise ToolError(f"{prefix}Error: {error_msg}")

    error_msg = (
        f"Error during {operation}: {str(error)}. "
        "Retry: no — fix the input. "
        "Try: (1) check the parameters you passed for type errors or typos, "
        "(2) confirm the tool was called with the schema described in its docstring"
    )
    await ctx.error(f"{prefix}{error_msg}")
    raise ToolError(f"{prefix}Error: {error_msg}")


def coerce_stringified_list(value) -> list[str]:
    """Coerce a possibly-stringified JSON array into a Python list of strings.

    MCP clients (Claude Code deferred tools, LiveKit agents, etc.) sometimes
    serialize ``list`` parameters as JSON-encoded strings instead of native
    arrays.  This function accepts both forms so tool validation doesn't
    reject otherwise valid input.

    Accepted inputs:
      - ``list``               → returned as-is (items cast to ``str``)
      - ``'["a","b"]'``        → parsed via ``json.loads``, items cast to ``str``
      - ``"single-value"``     → wrapped as ``["single-value"]``
      - ``None`` / empty       → ``[]``
    """
    import json

    if not value:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except (json.JSONDecodeError, TypeError):
                pass
        return [stripped] if stripped else []

    if isinstance(value, list):
        return [str(item) for item in value if item is not None]

    return [str(value)]


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
