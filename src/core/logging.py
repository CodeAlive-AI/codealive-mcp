"""Logging utilities for CodeAlive MCP server."""

import json
import logging
import uuid
from typing import Optional, Dict, Any, Union, List, Tuple

import httpx

logger = logging.getLogger(__name__)


def setup_debug_logging() -> bool:
    """Setup debug logging if debug mode is enabled."""
    import os

    if os.environ.get("DEBUG_MODE", "").lower() in ["true", "1", "yes"]:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
        return True
    return False


def log_api_request(
    method: str,
    url: str,
    headers: Dict[str, str],
    params: Optional[Union[Dict, List[Tuple]]] = None,
    body: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> str:
    """Log API request details in debug mode.

    Returns:
        Request ID for tracing
    """
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"\n{'='*60}")
        logger.debug(f"[{request_id}] API REQUEST: {method} {url}")

        # Mask authorization header
        safe_headers = {
            k: v if k != 'Authorization' else 'Bearer ***'
            for k, v in headers.items()
        }
        logger.debug(f"Headers: {json.dumps(safe_headers, indent=2)}")

        if params:
            if isinstance(params, dict):
                logger.debug(f"Query Parameters: {json.dumps(params, indent=2)}")
            else:
                # Handle list of tuples
                param_dict = {}
                for key, value in params:
                    if key in param_dict:
                        if not isinstance(param_dict[key], list):
                            param_dict[key] = [param_dict[key]]
                        param_dict[key].append(value)
                    else:
                        param_dict[key] = value
                logger.debug(f"Query Parameters: {json.dumps(param_dict, indent=2)}")

        if body:
            logger.debug(f"Request Body: {json.dumps(body, indent=2)}")

        logger.debug(f"{'='*60}\n")

    return request_id


def log_api_response(response: httpx.Response, request_id: Optional[str] = None) -> None:
    """Log API response details in debug mode without truncation."""
    if logger.isEnabledFor(logging.DEBUG):
        if request_id is None:
            request_id = "unknown"

        logger.debug(f"\n{'='*60}")
        logger.debug(f"[{request_id}] API RESPONSE: {response.status_code} {response.url}")
        logger.debug(f"Response Headers: {json.dumps(dict(response.headers), indent=2)}")

        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                response_body = response.json()
                response_str = json.dumps(response_body, indent=2)
                logger.debug(f"Response Body (Full):\n{response_str}")
            else:
                response_text = response.text
                logger.debug(f"Response Text (Full):\n{response_text}")
        except Exception as e:
            logger.debug(f"Could not parse response: {e}")
            logger.debug(f"Raw response (Full): {response.text}")

        logger.debug(f"{'='*60}\n")