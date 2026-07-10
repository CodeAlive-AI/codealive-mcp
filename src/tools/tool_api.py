"""Shared v3 Tool API caller for MCP tools."""

import json
from typing import Any, Iterable, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error

ToolApiResult = str | ToolResult


def normalize_optional_list(value: Optional[Union[str, list[str]]]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if str(item).strip()]
            except (json.JSONDecodeError, TypeError):
                pass
        return [stripped]
    return [str(item) for item in value if str(item).strip()]


def require_text(value: str, tool_name: str, field: str) -> None:
    if not value or not value.strip():
        raise ToolError(f"[{tool_name}] {field} is required.")


def omit_empty(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != [] and value != ""
    }


async def call_tool_api(
    ctx: Context,
    tool_name: str,
    payload: dict[str, Any],
    *,
    action_label: Optional[str] = None,
) -> ToolApiResult:
    context: CodeAliveContext = ctx.request_context.lifespan_context
    api_key = get_api_key_from_context(ctx)
    body = {**omit_empty(payload), "output_format": "agentic"}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-CodeAlive-Integration": "mcp",
        "X-CodeAlive-Tool": tool_name,
        "X-CodeAlive-Client": "fastmcp-v3",
    }

    endpoint = f"/api/tools/{tool_name}"
    full_url = urljoin(context.base_url, endpoint)
    request_id = log_api_request("POST", full_url, headers, body=body)

    try:
        response = await context.client.post(endpoint, json=body, headers=headers)
        log_api_response(response, request_id)
        response.raise_for_status()
        data = response.json()
        obj = data.get("obj")
        rendered = data.get("rendered")
        if isinstance(obj, dict) and isinstance(obj.get("error"), dict):
            content = rendered if isinstance(rendered, str) else json.dumps(
                obj,
                ensure_ascii=False,
                indent=2,
            )
            return ToolResult(
                content=content,
                structured_content=obj,
                is_error=True,
            )
        if isinstance(rendered, str):
            return rendered
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception as exc:
        await handle_api_error(
            ctx,
            exc,
            action_label or tool_name,
            method=tool_name,
            recovery_hints={
                404: (
                    "(1) verify the tool name is a Tool API v3 tool, "
                    "(2) call get_data_sources to choose visible data sources, "
                    "(3) retry with canonical snake_case arguments"
                ),
            },
        )
        raise AssertionError("handle_api_error always raises")
