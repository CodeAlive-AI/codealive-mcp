"""Chat completions tool implementation."""

import json
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from fastmcp import Context

from core import CodeAliveContext, get_api_key_from_context, log_api_request, log_api_response
from utils import handle_api_error, format_data_source_ids


async def codebase_consultant(
    ctx: Context,
    question: str,
    data_sources: Optional[List[str]] = None,
    conversation_id: Optional[str] = None
) -> str:
    """
    Consult with an AI expert about your codebase for insights, explanations, and architectural guidance.

    This consultant understands your entire codebase and can help with:
    - Architecture and design decisions
    - Implementation strategies
    - Code explanations and walkthroughs
    - Best practices and optimization advice
    - Debugging and problem-solving

    Args:
        question: What you want to know about the codebase
                 Example: "How does the authentication system work?"

        data_sources: Repository or workspace IDs to analyze
                     Example: ["67f664fd4c2a00698a52bb6f", "5e8f9a2c1d3b7e4a6c9d0f8e"]

        conversation_id: Continue a previous consultation session
                        Example: "conv_6789f123a456b789c123d456"

    Returns:
        Expert analysis and explanation addressing your question.

    Examples:
        1. Ask about architecture:
           codebase_consultant(
             question="What's the best way to add caching to our API?",
             data_sources=["67f664fd4c2a00698a52bb6f"]
           )

        2. Understand implementation:
           codebase_consultant(
             question="How do the microservices communicate?",
             data_sources=["workspace_123", "repo_456"]
           )

        3. Continue a consultation:
           codebase_consultant(
             question="What about error handling in that flow?",
             conversation_id="conv_6789f123a456b789c123d456"
           )

    Note:
        - Either conversation_id OR data_sources is typically provided
        - When creating a new conversation, data_sources is optional if your API key has exactly one assigned data source
        - When continuing a conversation, conversation_id is required to maintain context
        - The consultant maintains full conversation history for follow-up questions
        - Choose workspace IDs for broad architectural questions or repository IDs for specific implementation details
    """
    context: CodeAliveContext = ctx.request_context.lifespan_context

    if not question or not question.strip():
        return "Error: No question provided. Please provide a question to ask the consultant."

    # Validate that either conversation_id or data_sources is provided
    if not conversation_id and (not data_sources or len(data_sources) == 0):
        await ctx.info("No data sources provided. If the API key has exactly one assigned data source, that will be used as default.")

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
        request_data["dataSources"] = format_data_source_ids(data_sources)

    try:
        api_key = get_api_key_from_context(ctx)

        # Log the attempt
        await ctx.info(f"Consulting about: '{question[:100]}...'" if len(question) > 100 else f"Consulting about: '{question}'" +
                       (f" (continuing conversation {conversation_id})" if conversation_id else ""))

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
        conversation_metadata = {}

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

                    # Capture metadata with conversation ID
                    if chunk.get("event") == "metadata" and "conversationId" in chunk:
                        conversation_metadata = chunk
                        await ctx.info(f"Conversation ID: {chunk['conversationId']}")
                        continue

                    # Process content chunks
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        if delta and "content" in delta and delta["content"] is not None:
                            full_response += delta["content"]
                except json.JSONDecodeError:
                    pass

        # Append conversation ID info to the response if we got one and it's a new conversation
        if conversation_metadata.get("conversationId") and not conversation_id:
            conversation_id_note = f"\n\n---\n**Conversation ID:** `{conversation_metadata['conversationId']}`\n*Use this ID in the `conversation_id` parameter to continue this conversation.*"
            full_response += conversation_id_note

        return full_response or "No content returned from the API. Please check that your data sources are accessible and try again."

    except (httpx.HTTPStatusError, Exception) as e:
        error_msg = await handle_api_error(ctx, e, "chat completion")
        if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
            return "Error: Not found (404): The requested resource could not be found. Check your conversation_id or data_source_ids."
        return error_msg