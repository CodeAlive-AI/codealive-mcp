"""
N8N middleware to strip extra parameters from tool calls.

n8n sends extra parameters (sessionId, action, chatInput, toolCallId) that aren't part
of the tool schema. This middleware strips them before FastMCP validates the function signature.
"""

import logging
from typing import TYPE_CHECKING

from fastmcp.server.middleware import Middleware

if TYPE_CHECKING:
    from fastmcp.server.middleware import MiddlewareContext, CallNext

logger = logging.getLogger("n8n-middleware")

# Extra parameters that n8n sends but aren't part of the tool schema
EXTRA_KEYS = {"sessionId", "action", "chatInput", "toolCallId"}


class N8NRemoveParametersMiddleware(Middleware):
    """
    Remove extra parameters n8n sends in tool calls that aren't part of the tool schema.

    n8n automatically adds several parameters to tool calls:
    - sessionId: Session identifier
    - action: Action type
    - chatInput: Chat input text
    - toolCallId: Tool call identifier

    These parameters are not defined in the tool schema and cause FastMCP validation errors.
    This middleware strips them before the tool is invoked.
    """

    async def on_call_tool(self, context: "MiddlewareContext", call_next: "CallNext"):
        """
        Strip extra n8n parameters from tool call arguments.

        Args:
            context: Middleware context containing the message
            call_next: Next middleware in the chain

        Returns:
            Result from the next middleware/tool handler
        """
        args = getattr(context.message, "arguments", None)

        if isinstance(args, dict):
            removed = []
            # Strip only known n8n extras (safe & explicit)
            for k in list(args.keys()):
                if k in EXTRA_KEYS:
                    args.pop(k, None)
                    removed.append(k)

            if removed:
                logger.debug("Stripped extra n8n tool args: %s", ", ".join(removed))

        return await call_next(context)
