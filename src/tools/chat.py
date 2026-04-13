"""Chat completions tool implementation.

The canonical MCP tool name is ``chat``. ``codebase_consultant`` remains as a
deprecated alias for backward compatibility.
"""

import json
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import Context
from fastmcp.exceptions import ToolError

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error, format_validation_error, format_data_source_names, normalize_data_source_names

_PRIMARY_TOOL_NAME = "chat"
_LEGACY_TOOL_NAME = "codebase_consultant"


async def chat(
    ctx: Context,
    question: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    conversation_id: Optional[str] = None,
) -> str:
    """
    Ask CodeAlive for a synthesized answer about the indexed codebase.

    **IMPORTANT: Do NOT call this tool unless the user explicitly asks for it**
    (e.g. "use chat", "ask CodeAlive", "use codebase_consultant").
    For all other tasks — finding code, understanding architecture, debugging —
    use `semantic_search`, `grep_search`, `fetch_artifacts`, and
    `get_artifact_relationships` instead. These tools are faster, return
    primary evidence, and give you full control over the workflow.

    `chat` is a slow synthesis fallback (up to 30 seconds) with lower evidence
    fidelity. It exists for cases where the user wants a single opinionated
    answer from CodeAlive rather than raw search results.

    **PREREQUISITE**: You MUST call `get_data_sources` FIRST to discover available data source names,
    UNLESS the user has explicitly provided specific data source names OR you are continuing an
    existing conversation with a `conversation_id`.

    When invoked by the user, this tool can produce synthesized answers about
    architecture, design decisions, code walkthroughs, debugging, etc.
    These topics do NOT by themselves justify calling the tool — only an
    explicit user request does.

    Args:
        question: What you want to know about the codebase
                  Example: "How does the authentication system work?"

        data_sources: Repository or workspace names to analyze. These names are
                      resolved to IDs on the server side.
                      Example: ["enterprise-platform", "workspace:payments-team"]

        conversation_id: Continue a previous consultation session
                         Example: "conv_6789f123a456b789c123d456"

    Returns:
        Synthesized analysis and explanation addressing your question.

    Examples:
        1. Ask about architecture:
           chat(
             question="What's the best way to add caching to our API?",
             data_sources=["repo123"]
           )

        2. Understand implementation:
           chat(
             question="How do the microservices communicate?",
             data_sources=["platform", "payments"]
           )

        3. Continue a consultation:
           chat(
             question="What about error handling in that flow?",
             conversation_id="conv_6789f123a456b789c123d456"
           )

    Note:
        - `chat` is disabled by default; see top of docstring for the single
          condition that permits calling it.
        - Either conversation_id OR data_sources is typically provided
        - When creating a new conversation, data_sources is optional if your API key has exactly one assigned data source
        - When continuing a conversation, conversation_id is required to maintain context
        - The tool maintains full conversation history for follow-up questions
        - Choose workspace names for broad architectural questions or repository names for specific implementation details
    """
    return await _chat_impl(
        ctx,
        question=question,
        data_sources=data_sources,
        conversation_id=conversation_id,
        method_name=_PRIMARY_TOOL_NAME,
    )


async def codebase_consultant(
    ctx: Context,
    question: str,
    data_sources: Optional[Union[str, List[str]]] = None,
    conversation_id: Optional[str] = None,
) -> str:
    """Deprecated alias for `chat`.

    Keep this for backward compatibility with older prompts and MCP clients.
    New integrations should prefer the canonical `chat` tool name.

    **Same invocation policy as `chat`**: do NOT call unless the user explicitly
    named the tool (e.g. "use codebase_consultant", "ask CodeAlive", "use chat").
    For all other tasks use `semantic_search`, `grep_search`, `fetch_artifacts`,
    and `get_artifact_relationships`.
    """
    return await _chat_impl(
        ctx,
        question=question,
        data_sources=data_sources,
        conversation_id=conversation_id,
        method_name=_LEGACY_TOOL_NAME,
    )


async def _chat_impl(
    ctx: Context,
    *,
    question: str,
    data_sources: Optional[Union[str, List[str]]],
    conversation_id: Optional[str],
    method_name: str,
) -> str:
    context: CodeAliveContext = ctx.request_context.lifespan_context

    # Normalize data source names (handles Claude Desktop serialization issues)
    data_sources = normalize_data_source_names(data_sources)

    if not question or not question.strip():
        raise ToolError(format_validation_error(
            method_name,
            "No question provided. Please provide a question to ask the chat tool.",
        ))

    # Validate that either conversation_id or data_sources is provided
    if not conversation_id and (not data_sources or len(data_sources) == 0):
        await ctx.info("No data sources provided. If the API key has exactly one assigned data source, that will be used as default.")
    await ctx.info(
        f"[{method_name}] This synthesized call can take up to 30 seconds. "
        "Prefer semantic_search and grep_search for default discovery."
    )

    # Transform simple question into message format internally
    messages = [{"role": "user", "content": question}]

    # Prepare the request payload
    request_data = {
        "messages": messages,
        "stream": True  # Always stream internally for efficiency
    }

    if conversation_id:
        request_data["conversationId"] = conversation_id

    if data_sources:
        request_data["names"] = format_data_source_names(data_sources)

    try:
        api_key = get_api_key_from_context(ctx)

        # Log the attempt
        await ctx.info(f"Consulting about: '{question[:100]}...'" if len(question) > 100 else f"Consulting about: '{question}'" +
                       (f" (continuing conversation {conversation_id})" if conversation_id else ""))

        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-CodeAlive-Integration": "mcp",
            "X-CodeAlive-Tool": method_name,
            "X-CodeAlive-Client": "fastmcp",
        }

        # Log the request
        full_url = urljoin(context.base_url, "/api/chat/completions")
        request_id = log_api_request("POST", full_url, headers, body=request_data)

        # Make API request
        response = await context.client.post(
            "/api/chat/completions",
            json=request_data,
            headers=headers
        )

        # Log the response
        log_api_response(response, request_id)

        response.raise_for_status()

        # Process streaming response - we always stream internally for efficiency
        full_response = ""
        conversation_metadata = {}

        try:
            async for line in response.aiter_lines():
                if not line:
                    continue

                # Handle metadata events
                if line.startswith("event: message"):
                    continue

                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)

                        # Capture metadata with conversation ID and message ID
                        if chunk.get("event") == "metadata":
                            conv_id = chunk.get("conversationId")
                            msg_id = chunk.get("messageId")
                            if conv_id or msg_id:
                                conversation_metadata = chunk
                                await ctx.info(f"Conversation ID: {conv_id}, Message ID: {msg_id}")
                            continue

                        # Process content chunks
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if delta and "content" in delta and delta["content"] is not None:
                                full_response += delta["content"]
                    except json.JSONDecodeError:
                        pass
        except Exception as streaming_error:
            # Include conversation and message IDs in streaming error response
            error_context = _format_metadata_context(conversation_metadata)
            error_msg = (
                f"[{method_name}] Error during streaming: {str(streaming_error)}"
            )
            await ctx.error(error_msg)
            raise ToolError(f"{error_msg} {error_context}")

        # Append conversation ID info to the response if we got one and it's a new conversation
        if conversation_metadata.get("conversationId") and not conversation_id:
            conversation_id_note = f"\n\n---\n**Conversation ID:** `{conversation_metadata['conversationId']}`\n*Use this ID in the `conversation_id` parameter to continue this conversation.*"
            full_response += conversation_id_note

        return full_response or "No content returned from the API. Please check that your data sources are accessible and try again."

    except (httpx.HTTPStatusError, Exception) as e:
        await handle_api_error(
            ctx, e, "chat completion", method=method_name,
            recovery_hints={
                404: (
                    "(1) if continuing a conversation, verify conversation_id matches one returned by an earlier call, "
                    "(2) if starting a new conversation, call get_data_sources to list valid data source names, "
                    "(3) drop conversation_id and data_sources to fall back to the API key's default"
                ),
            },
        )


def _format_metadata_context(metadata: Dict) -> str:
    """Format conversation metadata for error messages."""
    if not metadata:
        return ""

    parts = []
    if metadata.get("conversationId"):
        parts.append(f"Conversation ID: {metadata['conversationId']}")
    if metadata.get("messageId"):
        parts.append(f"Message ID: {metadata['messageId']}")

    if parts:
        return f"\n\n---\n**Debug Info:**\n" + "\n".join(f"- {p}" for p in parts)
    return ""
