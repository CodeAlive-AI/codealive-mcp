"""Chat completions tool implementation."""

import json
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error, format_data_source_ids


async def chat_completions(
    ctx: Context,
    messages: Optional[List[Dict[str, str]]] = None,
    data_sources: Optional[List] = None,  # Accept both strings and dicts for compatibility
    conversation_id: Optional[str] = None
) -> str:
    """
    Streams chat completions from the CodeAlive API for code-aware conversations with knowledge of your codebase.

    Args:
        messages: List of message objects with "role" and "content" fields
                 Example: [
                   {"role": "system", "content": "Analyze the authentication flow"},
                   {"role": "user", "content": "How does the login process work?"}
                 ]

        data_sources: List of data source IDs (repository or workspace IDs).
                     Example: ["67f664fd4c2a00698a52bb6f", "5e8f9a2c1d3b7e4a6c9d0f8e"]
                     Just pass the IDs directly as strings.
        conversation_id: Optional ID to continue a previous conversation
                        Example: "conv_6789f123a456b789c123d456"


    Returns:
        The generated completion text with code understanding from specified repositories/workspaces.
        The response will incorporate knowledge from the specified code repositories.

    Examples:
        1. Start a new conversation with simple ID format (recommended):
           chat_completions(
             messages=[{"role": "user", "content": "Explain the authentication flow in this code"}],
             data_sources=["67f664fd4c2a00698a52bb6f"]
           )

        2. Start a new conversation using multiple data sources:
           chat_completions(
             messages=[{"role": "user", "content": "How do the microservices communicate with each other?"}],
             data_sources=["67f664fd4c2a00698a52bb6f", "5e8f9a2c1d3b7e4a6c9d0f8e"]
           )

        3. Continue an existing conversation:
           chat_completions(
             messages=[{"role": "user", "content": "How is password hashing implemented?"}],
             conversation_id="conv_6789f123a456b789c123d456"
           )


    Note:
        - Either conversation_id OR data_sources is typically provided
        - When creating a new conversation, data_sources is optional if the API key has exactly one assigned data source
        - When continuing a conversation, conversation_id is required
        - The conversation maintains context across multiple messages
        - Messages should be in chronological order with the newest message last
        - Choose between workspace-level access (for broader context) or repository-level access
          (for targeted analysis) based on your query needs
        - If a user is working in a local git repository that matches one of the indexed repositories
          in CodeAlive (by URL), you can leverage this integration for enhanced code understanding
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    if not messages or len(messages) == 0:
        return "Error: No messages provided. Please include at least one message with 'role' and 'content' fields."

    # Validate that either conversation_id or data_sources is provided
    if not conversation_id and (not data_sources or len(data_sources) == 0):
        await ctx.info("No data sources provided. If the API key has exactly one assigned data source, that will be used as default.")

    # Validate that each message has the required fields
    for msg in messages:
        if not msg.get("role") or not msg.get("content"):
            return "Error: Each message must have 'role' and 'content' fields. Valid roles are 'system', 'user', and 'assistant'."

    # Prepare the request payload
    request_data = {
        "messages": messages,
        "stream": True  # Always stream internally for efficiency
    }

    if conversation_id:
        request_data["conversationId"] = conversation_id

    if data_sources:
        request_data["dataSources"] = format_data_source_ids(data_sources)

    try:
        api_key = get_api_key_from_context(ctx)

        # Log the attempt
        await ctx.info(f"Requesting chat completion with {len(messages)} messages" +
                       (f" in conversation {conversation_id}" if conversation_id else " in a new conversation"))

        headers = {"Authorization": f"Bearer {api_key}"}

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
        async for line in response.aiter_lines():
            if not line:
                continue

            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        if delta and "content" in delta and delta["content"] is not None:
                            full_response += delta["content"]
                except json.JSONDecodeError:
                    pass
        return full_response or "No content returned from the API. Please check that your data sources are accessible and try again."

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(ctx, e, "chat completion")
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            return "Error: Not found (404): The requested resource could not be found. Check your conversation_id or data_source_ids."
        return error_msg