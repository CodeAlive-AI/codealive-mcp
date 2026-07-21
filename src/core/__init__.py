"""Core components for CodeAlive MCP server."""

from .client import CodeAliveContext, get_api_key_from_context, codealive_lifespan, _server_ready
from .oauth import (
    MetadataAwareHostOriginGuardMiddleware,
    ToolTokenExchangeCache,
    build_oauth_provider,
    exchange_for_tool_token,
    invalidate_tool_token_exchange,
    is_oauth_credential,
    is_jwt_shaped,
)
from .config import Config, REQUEST_TIMEOUT_SECONDS, normalize_base_url
from .logging import setup_logging, setup_debug_logging, log_api_request, log_api_response
from .observability import init_tracing

__all__ = [
    'CodeAliveContext',
    'MetadataAwareHostOriginGuardMiddleware',
    'get_api_key_from_context',
    'build_oauth_provider',
    'exchange_for_tool_token',
    'invalidate_tool_token_exchange',
    'is_oauth_credential',
    'ToolTokenExchangeCache',
    'is_jwt_shaped',
    'codealive_lifespan',
    'Config',
    'REQUEST_TIMEOUT_SECONDS',
    'normalize_base_url',
    'setup_logging',
    'setup_debug_logging',
    'log_api_request',
    'log_api_response',
    'init_tracing',
]
