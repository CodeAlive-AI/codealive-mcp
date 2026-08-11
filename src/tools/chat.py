"""Tool API v3 stateless chat."""

from typing import Annotated, Optional, Union

from fastmcp import Context
from pydantic import Field

from .tool_api import ToolApiResult, call_tool_api, normalize_optional_list, require_text


async def chat(
    ctx: Context,
    question: Annotated[
        str,
        Field(
            min_length=1,
            description="Self-contained stateless question including relevant prior context.",
        ),
    ],
    data_sources: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository or workspace names returned by get_data_sources."),
    ] = None,
) -> ToolApiResult:
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


async def ask_codebase(
    ctx: Context,
    question: Annotated[
        str,
        Field(
            min_length=1,
            description="Self-contained stateless question including relevant prior context.",
        ),
    ],
    data_sources: Annotated[
        Optional[Union[str, list[str]]],
        Field(description="Repository or workspace names returned by get_data_sources."),
    ] = None,
) -> ToolApiResult:
    """Preferred broad-question research tool through Tool API v3.

    Start here for architecture, behavior, ownership, dependencies,
    conventions, and blast-radius questions. Exact lookups — a known file or
    range, a literal occurrence, or metadata for a known artifact — may use
    the corresponding direct tool instead. Include prior findings,
    identifiers, assumptions, scope, and constraints in each `question`.
    """
    require_text(question, "ask_codebase", "question")
    return await call_tool_api(ctx, "ask_codebase", {
        "question": question,
        "data_sources": normalize_optional_list(data_sources),
    }, action_label="ask_codebase")
