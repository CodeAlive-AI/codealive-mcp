"""Structured logging with loguru for CodeAlive MCP server.

All log output goes to stderr (safe for stdio MCP transport).
When ``serialize=True`` loguru emits one JSON object per line,
with OTel trace context automatically injected via a patcher.
"""

import logging
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from loguru import logger
from opentelemetry import trace as otel_trace

# ---------------------------------------------------------------------------
# PII masking
# ---------------------------------------------------------------------------

# Request-body keys that may contain user content
_PII_FIELDS = frozenset({"query", "question", "messages", "message"})
_PII_MAX_LEN = 80
_RESPONSE_BODY_MAX_LEN = 500


def _mask_pii(value: str, max_len: int = _PII_MAX_LEN) -> str:
    if len(value) <= max_len:
        return value
    return value[:max_len] + f"...[{len(value)} chars]"


def _sanitize_body(body: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow copy with PII fields truncated."""
    sanitized: Dict[str, Any] = {}
    for k, v in body.items():
        if k in _PII_FIELDS:
            if isinstance(v, str):
                sanitized[k] = _mask_pii(v)
            elif isinstance(v, list):
                sanitized[k] = f"[{len(v)} items]"
            else:
                sanitized[k] = "<masked>"
        else:
            sanitized[k] = v
    return sanitized


# ---------------------------------------------------------------------------
# OTel context injection
# ---------------------------------------------------------------------------

def _otel_patcher(record: dict) -> None:
    """Inject current OTel trace_id / span_id into every log record."""
    try:
        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            record["extra"]["trace_id"] = format(ctx.trace_id, "032x")
            record["extra"]["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# stdlib logging intercept (captures logs from libraries using stdlib)
# ---------------------------------------------------------------------------

class _InterceptHandler(logging.Handler):
    """Route stdlib ``logging`` through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(1), 1
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# ---------------------------------------------------------------------------
# Minimum-level check
# ---------------------------------------------------------------------------

_current_level: str = "INFO"


def _is_debug_enabled() -> bool:
    """Fast check whether DEBUG-level logs are active."""
    return _current_level == "DEBUG"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logging(debug: bool = False) -> None:
    """Configure loguru for structured JSON logging to stderr.

    Also installs an intercept handler so that stdlib ``logging`` messages
    (e.g. from uvicorn, httpx, n8n middleware) are routed through loguru.
    """
    global _current_level
    logger.remove()

    _current_level = "DEBUG" if debug else "INFO"

    logger.configure(patcher=_otel_patcher)

    logger.add(
        sys.stderr,
        level=_current_level,
        serialize=True,
    )

    # Intercept stdlib logging
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    logger.info("Logging initialized at {level} level", level=_current_level)


def setup_debug_logging() -> bool:
    """Backward-compatible helper: enable debug logging if ``DEBUG_MODE`` env is set."""
    import os

    if os.environ.get("DEBUG_MODE", "").lower() in ["true", "1", "yes"]:
        setup_logging(debug=True)
        return True
    return False


def log_api_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    params: Optional[Union[Dict, List[Tuple]]] = None,
    body: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> str:
    """Log an outgoing API request at DEBUG level with PII masking.

    Returns the ``request_id`` for correlation with the response log.
    """
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]

    if not _is_debug_enabled():
        return request_id

    safe_headers = {
        k: ("Bearer ***" if k.lower() == "authorization" else v)
        for k, v in headers.items()
    }

    extra: Dict[str, Any] = {
        "event": "api_request",
        "request_id": request_id,
        "http_method": method,
        "url": url,
        "headers": safe_headers,
    }

    if params:
        if isinstance(params, dict):
            extra["params"] = params
        else:
            param_dict: Dict[str, Any] = {}
            for key, value in params:
                if key in param_dict:
                    if not isinstance(param_dict[key], list):
                        param_dict[key] = [param_dict[key]]
                    param_dict[key].append(value)
                else:
                    param_dict[key] = value
            extra["params"] = param_dict

    if body:
        extra["body"] = _sanitize_body(body)

    logger.bind(**extra).debug("API request: {method} {url}", method=method, url=url)

    return request_id


def log_api_response(
    response: httpx.Response,
    request_id: Optional[str] = None,
) -> None:
    """Log an API response at DEBUG level with body truncation.

    IMPORTANT: This function reads ``response.text`` which consumes the
    response body.  It is guarded by a level check so that streaming
    responses (e.g. chat completions) are not accidentally consumed at
    INFO level.
    """
    if not _is_debug_enabled():
        return

    if request_id is None:
        request_id = "unknown"

    extra: Dict[str, Any] = {
        "event": "api_response",
        "request_id": request_id,
        "status_code": response.status_code,
        "url": str(response.url),
    }

    try:
        body_text = response.text
        if len(body_text) > _RESPONSE_BODY_MAX_LEN:
            extra["response_body"] = (
                body_text[:_RESPONSE_BODY_MAX_LEN]
                + f"...[{len(body_text)} chars total]"
            )
        else:
            extra["response_body"] = body_text
    except Exception:
        extra["response_body"] = "<unreadable>"

    logger.bind(**extra).debug(
        "API response: {status_code} {url}",
        status_code=response.status_code,
        url=str(response.url),
    )
