# Middleware

This directory contains middleware implementations for the CodeAlive MCP Server.

## N8N Middleware

The `N8NRemoveParametersMiddleware` automatically strips extra parameters that n8n sends in tool calls:

- `sessionId` - Session identifier
- `action` - Action type
- `chatInput` - Chat input text
- `toolCallId` - Tool call identifier

### Why is this needed?

n8n's AI Agent node automatically adds these parameters to every tool call, but they're not part of the tool schema. Without this middleware, FastMCP would reject the tool calls with "Unexpected keyword argument" errors.

### How it works

The middleware intercepts tool calls before FastMCP validates the parameters against the function signature. It safely strips only the known n8n parameters, leaving all valid tool parameters intact.

### Usage

The middleware is automatically registered in `codealive_mcp_server.py`:

```python
from middleware import N8NRemoveParametersMiddleware

mcp = FastMCP(name="CodeAlive MCP Server")
mcp.add_middleware(N8NRemoveParametersMiddleware())
```

No additional configuration is needed. The middleware works transparently for all tool calls.

### Testing

See `src/tests/test_n8n_middleware.py` for comprehensive test coverage including:
- Stripping n8n parameters
- Preserving valid parameters
- Handling edge cases (missing arguments, non-dict arguments)
- Ensuring only exact parameter names are stripped

Run tests with:
```bash
pytest src/tests/test_n8n_middleware.py -v
```
