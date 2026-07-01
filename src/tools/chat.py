"""Tool API v3 stateless chat."""

from typing import Optional, Union

from fastmcp import Context

from .tool_api import call_tool_api, normalize_optional_list, require_text


async def chat(
    ctx: Context,
    question: str,
    data_sources: Optional[Union[str, list[str]]] = None,
) -> str:
    """Ask stateless CodeAlive chat through Tool API v3.

    Call only when the user explicitly asks for chat/synthesis. Tool API v3
    chat does not preserve public conversation context across calls; include all
    important prior findings, artifact identifiers, assumptions, scope, and
    constraints in each `question`.
    """
    require_text(question, "chat", "question")
    return await call_tool_api(ctx, "chat", {
        "question": question,
        "data_sources": normalize_optional_list(data_sources),
    }, action_label="chat")
