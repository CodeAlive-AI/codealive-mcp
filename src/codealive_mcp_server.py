import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import List, AsyncIterator

import httpx
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
# Use the actual script directory to find .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
dotenv_path = os.path.join(project_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

def configure_logging(debug_mode: bool = False):
    """Configure loguru logging based on debug mode"""
    # Remove default handler
    logger.remove()
    
    if debug_mode:
        # In debug mode, log to both console and file
        logger.add(
            sys.stderr,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG"
        )
        
        # Log to file in debug mode
        log_file = os.path.join(project_dir, "logs", "codealive-mcp-debug.log")
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="7 days",
            compression="gz"
        )
        logger.debug("Debug mode enabled - logging to console and file")
    else:
        # In normal mode, log only warnings and errors to console
        logger.add(
            sys.stderr,
            format="{time:HH:mm:ss} | {level: <8} | {message}",
            level="WARNING"
        )
        logger.info("Normal mode enabled - minimal logging to console only")

# Import FastMCP components
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import get_http_headers
from starlette.requests import Request
from starlette.responses import JSONResponse
import datetime

@dataclass
class CodeAliveContext:
    """Context for CodeAlive API access"""
    client: httpx.AsyncClient
    api_key: str
    base_url: str

def get_api_key_from_context(ctx: Context) -> str:
    """Extract API key based on transport mode"""
    logger.debug("Extracting API key from context")
    
    # Try to get HTTP headers safely using FastMCP dependency function
    try:
        headers = get_http_headers()
        auth_header = headers.get("authorization", "")
        logger.debug(f"Retrieved headers, authorization header present: {bool(auth_header)}")
        
        if auth_header and auth_header.startswith("Bearer "):
            # HTTP mode with Bearer token
            api_key = auth_header[7:]  # Remove "Bearer " prefix
            logger.debug(f"HTTP mode: API key extracted from Bearer token (length: {len(api_key)})")
            return api_key
        elif headers:
            # HTTP mode but no/invalid Authorization header
            logger.error("HTTP mode: Invalid or missing Authorization header")
            raise ValueError("HTTP mode: Authorization: Bearer <api-key> header required")
        else:
            # STDIO mode - no HTTP headers available
            logger.debug("No HTTP headers available, falling back to STDIO mode")
            api_key = os.environ.get("CODEALIVE_API_KEY", "")
            if not api_key:
                logger.error("STDIO mode: CODEALIVE_API_KEY environment variable not found")
                raise ValueError("STDIO mode: CODEALIVE_API_KEY environment variable required")
            logger.debug(f"STDIO mode: API key extracted from environment (length: {len(api_key)})")
            return api_key
    except Exception as e:
        # Fallback to STDIO mode if header access fails
        logger.warning(f"Header access failed ({type(e).__name__}), falling back to STDIO mode: {e}")
        api_key = os.environ.get("CODEALIVE_API_KEY", "")
        if not api_key:
            logger.error("Fallback: CODEALIVE_API_KEY environment variable not found")
            raise ValueError("STDIO mode: CODEALIVE_API_KEY environment variable required")
        logger.debug(f"Fallback: API key extracted from environment (length: {len(api_key)})")
        return api_key

@asynccontextmanager
async def codealive_lifespan(server: FastMCP) -> AsyncIterator[CodeAliveContext]:
    """Manage CodeAlive API client lifecycle"""
    logger.debug("Initializing CodeAlive lifespan context")
    transport_mode = os.environ.get("TRANSPORT_MODE", "stdio")
    logger.debug(f"Transport mode: {transport_mode}")
    
    # Get base URL from environment or use default
    if os.environ.get("CODEALIVE_BASE_URL") is None:
        logger.warning("CODEALIVE_BASE_URL not found in environment, using default")
        base_url = "https://app.codealive.ai"
    else:
        base_url = os.environ.get("CODEALIVE_BASE_URL")
        logger.debug(f"Found CODEALIVE_BASE_URL in environment: '{base_url}'")

    # Check if we should bypass SSL verification
    verify_ssl = not os.environ.get("CODEALIVE_IGNORE_SSL", "").lower() in ["true", "1", "yes"]
    logger.debug(f"SSL verification: {'enabled' if verify_ssl else 'disabled'}")

    client = None
    try:
        if transport_mode == "stdio":
            # STDIO mode: create client with fixed API key
            api_key = os.environ.get("CODEALIVE_API_KEY", "")
            logger.info(f"CodeAlive MCP Server starting in STDIO mode:")
            logger.info(f"  - API Key: {'*' * 5}{api_key[-5:] if api_key else 'Not set'}")
            logger.info(f"  - Base URL: {base_url}")
            logger.info(f"  - SSL Verification: {'Enabled' if verify_ssl else 'Disabled'}")
            
            logger.debug("Creating HTTP client for STDIO mode")
            # Create client with fixed headers for STDIO mode
            client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
                verify=verify_ssl,
            )
        else:
            # HTTP mode: create client factory (no fixed API key)
            logger.info(f"CodeAlive MCP Server starting in HTTP mode:")
            logger.info(f"  - API Keys: Extracted from Authorization headers per request")
            logger.info(f"  - Base URL: {base_url}")
            logger.info(f"  - SSL Verification: {'Enabled' if verify_ssl else 'Disabled'}")
            
            logger.debug("Creating HTTP client for HTTP mode")
            # Create base client without authentication headers
            client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "Content-Type": "application/json",
                },
                timeout=60.0,
                verify=verify_ssl,
            )

        logger.info("CodeAlive HTTP client successfully initialized")
        context = CodeAliveContext(
            client=client,
            api_key="",  # Will be set per-request in HTTP mode
            base_url=base_url
        )
        logger.debug("CodeAlive context created, yielding to application")
        
        yield context
        
    except Exception as e:
        logger.error(f"Failed to initialize CodeAlive client: {type(e).__name__}: {e}")
        raise
    finally:
        if client:
            logger.debug("Closing CodeAlive HTTP client")
            await client.aclose()
            logger.info("CodeAlive HTTP client closed successfully")

# Initialize FastMCP server with lifespan and enhanced system instructions
mcp = FastMCP(
    name="CodeAlive MCP Server",
    instructions="""
    CodeAlive MCP lets you search and chat over indexed codebases.
    
    Quick start
    1) get_data_sources — list repositories/workspaces you can query.
    2) search_code — semantic search; start with mode="auto", then refine.
    3) ask_question — ask natural-language questions about code. Always use this tool for user's questions or code understanding.
    
    Examples:
    - search_code(query="What is the auth flow?", data_source_ids=["1234567890"])
    - ask_question(question="How do services communicate with the billing API?", data_source_id="1234567890")
    
    Tips
    - Use workspace IDs to search across many repos; repo IDs for precision.
    - Reserve mode="deep" for tough, cross-cutting queries (it’s slower).
    - Read file paths/line ranges to understand structure and relationships.
    - You can pass a single workspace ID to search all its repositories.
    """,
    lifespan=codealive_lifespan
)

# Add health check endpoint for AWS ALB
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for load balancer"""
    logger.debug("Health check endpoint called")
    response_data = {
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "service": "codealive-mcp-server"
    }
    logger.debug(f"Health check response: {response_data}")
    return JSONResponse(response_data)

@mcp.tool()
async def ask_question(
        ctx: Context,
        question: str,
        data_source_id: str|None = None,
) -> str:
    """
    Ask natural-language questions about a codebase using CodeAlive chat.

    Args:
      ctx: FastMCP context
      question: Your question about the code.
      data_source_id: Optional repository/workspace ID. If omitted and your API key
                      has exactly one data source, that one is used.

    Returns:
      The model's answer grounded in the selected data source.

    Example:
      ask_question("Where is OAuth callback handled?", data_source_id="1234567890")
        
    Note:
        - data_source_id is optional if the API key has exactly one assigned data source
        - If a user is working in a local git repository that matches one of the indexed repositories
          in CodeAlive (by URL), you can leverage this integration for enhanced code understanding
    """
    import time
    start_time = time.time()
    
    logger.info(f"ask_question called with question length: {len(question) if question else 0}, data_source_id: {data_source_id or 'None'}")
    logger.debug(f"Question preview: {question[:100] + '...' if len(question) > 100 else question}")
    
    # Get context
    context: CodeAliveContext = ctx.request_context.lifespan_context
    logger.debug("Retrieved CodeAlive context from lifespan")

    # Validate inputs
    if not question or len(question) == 0:
        logger.warning("ask_question: Empty question provided")
        return "Error: No question provided. Please provide a natural language question."

    # Validate that either conversation_id or data_sources is provided
    if not data_source_id or len(data_source_id) == 0:
        logger.info("No data source provided, will use API key default")
        await ctx.info("No data source provided. If the API key has exactly one assigned data source, that will be used as default.")

    stream = True
    request_data = {
        "messages": [
            {"role": "system", "content": ""},
            {"role": "user", "content": question}
        ],
        "stream": stream
    }
    logger.debug(f"Created request data with streaming: {stream}")

    if data_source_id is not None:
        # TODO: COD-448. type: "auto"
        request_data["dataSources"] = [{"type": "repository", "id": data_source_id}]
        logger.debug(f"Added data source to request: {data_source_id}")

    try:
        # Get API key based on transport mode
        logger.debug("Extracting API key from context for ask_question")
        api_key = get_api_key_from_context(ctx)
        logger.debug(f"API key extracted successfully (length: {len(api_key)})")

        await ctx.info(f"Asking question: '{question}' using data source: '{data_source_id or 'default from API key'}'")

        # Create headers with authorization
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-App": "codealive-mcp-server/1.0",
        }
        logger.debug("Created request headers with authorization")
        
        # Make API request
        # ---- streaming with retries + graceful EOF ----
        MAX_RETRIES = 2
        BASE_BACKOFF = 0.5  # seconds
        full_response = ""
        got_any_content = False
        logger.debug(f"Initialized streaming with max_retries: {MAX_RETRIES}, base_backoff: {BASE_BACKOFF}s")

        async def process_event(data_str: str) -> bool:
            """Return True to continue, False to stop (on [DONE])."""
            nonlocal full_response, got_any_content
            if data_str.strip() == "[DONE]":
                logger.debug("Received [DONE] marker, stopping stream")
                return False
            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                logger.debug("Skipping non-JSON SSE data chunk")
                await ctx.debug("Skipping non-JSON SSE data chunk")
                return True

            if "choices" in obj and obj["choices"]:
                delta = obj["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    full_response += content
                    got_any_content = True
                    logger.debug(f"Received content chunk (length: {len(content)}, total: {len(full_response)})")
            return True

        # steady progress during stream
        PROGRESS_START, PROGRESS_CAP, STEP = 0.10, 0.95, 0.01
        chunk_count = 0
        logger.debug(f"Starting streaming with progress tracking: start={PROGRESS_START}, cap={PROGRESS_CAP}, step={STEP}")

        for attempt in range(MAX_RETRIES + 1):
            logger.debug(f"Starting attempt {attempt + 1}/{MAX_RETRIES + 1} for ask_question")
            try:
                await ctx.report_progress(0.10, 1.0, "Sending request to CodeAlive")
                # Ensure we're using a true streaming response
                timeout = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
                logger.debug(f"Created timeout config: connect=10s, read=180s, write=30s, pool=10s")
                
                logger.debug("Starting streaming POST request to /api/chat/completions")
                async with context.client.stream(
                        "POST",
                        "/api/chat/completions",
                        json=request_data,
                        headers=headers,
                        timeout=timeout,
                ) as response:
                    logger.debug(f"Received response with status: {response.status_code}")
                    await ctx.report_progress(0.35, 1.0, "Request sent; awaiting response")
                    response.raise_for_status()
                    logger.debug("HTTP response status check passed")

                    await ctx.report_progress(0.40, 1.0, "Streaming started")
                    logger.debug("Starting SSE stream processing")

                    # Minimal SSE parser: collect 'data:' lines until a blank line
                    data_buf: list[str] = []
                    lines_processed = 0
                    async for line in response.aiter_lines():
                        if line is None:
                            # keep-alive from some servers; ignore
                            continue
                        line = line.rstrip("\n")
                        lines_processed += 1

                        if line == "":
                            if data_buf:
                                data_str = "\n".join(data_buf)
                                data_buf.clear()
                                # process one SSE event
                                cont = await process_event(data_str)
                                if got_any_content:
                                    chunk_count += 1
                                    if chunk_count % 3 == 0:
                                        p = min(PROGRESS_START + STEP * chunk_count, PROGRESS_CAP)
                                        await ctx.report_progress(p, 1.0, f"Receiving content… ({chunk_count} chunks)")
                                if not cont:
                                    logger.debug("Stream processing stopped by [DONE] marker")
                                    break
                            continue

                        if line.startswith(":"):
                            # comment/heartbeat; ignore
                            continue

                        if line.startswith("data:"):
                            data_buf.append(line[5:].lstrip())
                        else:
                            # tolerate other SSE fields (event:, id:, retry:) by ignoring
                            continue

                    logger.debug(f"Stream processing completed: {lines_processed} lines, {chunk_count} content chunks")
                    
                    # flush any trailing buffered data at EOF
                    if data_buf:
                        logger.debug("Processing remaining buffered data at EOF")
                        data_str = "\n".join(data_buf)
                        await process_event(data_str)

                # success or graceful EOF
                logger.info(f"ask_question streaming completed successfully on attempt {attempt + 1}")
                break

            except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ProtocolError) as e:
                # This is where incomplete chunked reads land.
                logger.warning(f"Stream error on attempt {attempt + 1}: {type(e).__name__}: {e}")
                if got_any_content:
                    logger.info(f"Stream ended early but got partial content (length: {len(full_response)})")
                    await ctx.warning(f"Stream ended early ({type(e).__name__}); using partial content")
                    break  # treat as success with partial content
                if attempt < MAX_RETRIES:
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    logger.info(f"Retrying ask_question in {backoff:.1f}s (attempt {attempt + 2}/{MAX_RETRIES + 1})")
                    await ctx.warning(f"Stream error ({type(e).__name__}): {e}. Retrying in {backoff:.1f}s…")
                    await asyncio.sleep(backoff)
                    continue
                else:
                    logger.error(f"ask_question failed after {MAX_RETRIES + 1} attempts: {e}")
                    await ctx.error(f"Stream failed after {MAX_RETRIES + 1} attempts: {e}")
                    await ctx.report_progress(0.99, 1.0, "Failed")
                    return f"Error: streaming failed due to a network/proxy interruption ({type(e).__name__}). Please try again."

        # Success path
        elapsed_time = time.time() - start_time
        response_length = len(full_response)
        logger.info(f"ask_question completed successfully: {response_length} chars in {elapsed_time:.2f}s")
        await ctx.report_progress(1.0, 1.0, "Completed")
        
        result = full_response or "No content returned from the API. Please check that your data sources are accessible and try again."
        if not full_response:
            logger.warning("ask_question returned empty response from API")
        return result

    except httpx.HTTPStatusError as e:
        elapsed_time = time.time() - start_time
        error_code = e.response.status_code
        error_detail = e.response.text
        logger.error(f"HTTP error in ask_question after {elapsed_time:.2f}s: {error_code} - {error_detail[:200]}")
        
        if error_code == 401:
            error_msg = "Authentication error (401): Invalid API key or insufficient permissions"
        elif error_code == 404:
            error_msg = "Not found error (404): The requested resource could not be found, check your conversation_id or data_source_ids"
        elif error_code == 429:
            error_msg = "Rate limit exceeded (429): Too many requests, please try again later"
        elif error_code >= 500:
            error_msg = f"Server error ({error_code}): The CodeAlive service encountered an issue"
        else:
            error_msg = f"HTTP error: {error_code} - {error_detail}"
        
        await ctx.error(error_msg)
        await ctx.report_progress(0.99, 1.0, "Failed")
        return f"Error: {error_msg}"
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Error during chat completion: {str(e)}"
        logger.error(f"Unexpected error in ask_question after {elapsed_time:.2f}s: {type(e).__name__}: {e}")
        await ctx.error(error_msg)
        await ctx.report_progress(0.99, 1.0, "Failed")
        return f"Error: {error_msg}. Please check your input parameters and try again."

@mcp.tool()
async def get_data_sources(
        ctx: Context,
        alive_only: bool = True
) -> str:
    """
    Gets all available data sources (repositories and workspaces) for the user's account.
    
    A data source is a code repository or workspace that has been indexed by CodeAlive
    and can be used for code search and chat completions.
    
    Args:
        ctx: FastMCP context
        alive_only: If True (default), returns only data sources in "Alive" state ready for use with chat.
                   If False, returns all data sources regardless of processing state.
                   Example: true
        
    Returns:
        A formatted list of available data sources with the following information for each:
        - id: Unique identifier for the data source, used in other API calls
        - name: Human-readable name of the repository or workspace
        - type: The type of data source ("Repository" or "Workspace")
        - url: URL of the repository (for Repository type only)
        - repositoryIds: List of repository IDs included in the workspace (for Workspace type only)
        - state: The processing state of the data source (if alive_only=false)
        
    Examples:
        1. Get only ready-to-use data sources:
           get_data_sources()
        
        2. Get all data sources including those still processing:
           get_data_sources(alive_only=false)
        
    Note:
        Data sources in "Alive" state are fully processed and ready for search and chat.
        Other states include "New" (just added), "Processing" (being indexed), 
        "Failed" (indexing failed), etc.
        
        For repositories, the URL can be used to match with local git repositories
        to provide enhanced context for code understanding.
        
        For workspaces, the repositoryIds can be used to identify and work with 
        individual repositories that make up the workspace.
        
        Use the returned data source IDs with the search_code and ask_question functions.
    """
    import time
    start_time = time.time()
    
    logger.info(f"get_data_sources called with alive_only: {alive_only}")
    
    # Get context
    context: CodeAliveContext = ctx.request_context.lifespan_context
    logger.debug("Retrieved CodeAlive context from lifespan")

    try:
        # Get API key based on transport mode
        logger.debug("Extracting API key from context for get_data_sources")
        api_key = get_api_key_from_context(ctx)
        logger.debug(f"API key extracted successfully (length: {len(api_key)})")
        
        # Determine the endpoint based on alive_only flag
        endpoint = "/api/datasources/alive" if alive_only else "/api/datasources/all"
        logger.debug(f"Using endpoint: {endpoint}")

        # Create headers with authorization
        headers = {"Authorization": f"Bearer {api_key}"}
        logger.debug("Created request headers with authorization")
        
        # Make API request
        logger.debug(f"Making GET request to {endpoint}")
        response = await context.client.get(endpoint, headers=headers)

        # Check for errors
        logger.debug(f"Received response with status: {response.status_code}")
        response.raise_for_status()

        # Parse and format the response
        data_sources = response.json()
        count = len(data_sources) if data_sources else 0
        logger.info(f"Retrieved {count} data sources from API")

        # If no data sources found, return a helpful message
        if not data_sources or len(data_sources) == 0:
            logger.warning("No data sources found in user account")
            return "No data sources found. Please add a repository or workspace to CodeAlive before using this API."

        # Format the response as a readable string
        formatted_data = json.dumps(data_sources, indent=2)
        result = f"Available data sources:\n{formatted_data}"

        # Add usage hint
        result += "\n\nYou can use these data source IDs with the search_code and ask_question functions."

        elapsed_time = time.time() - start_time
        logger.info(f"get_data_sources completed successfully: {count} sources in {elapsed_time:.2f}s")
        return result

    except httpx.HTTPStatusError as e:
        elapsed_time = time.time() - start_time
        error_code = e.response.status_code
        error_detail = e.response.text
        logger.error(f"HTTP error in get_data_sources after {elapsed_time:.2f}s: {error_code} - {error_detail[:200]}")

        # Provide more helpful error messages based on status codes
        if error_code == 401:
            error_msg = f"Authentication error (401): Invalid API key or insufficient permissions"
        elif error_code == 429:
            error_msg = f"Rate limit exceeded (429): Too many requests, please try again later"
        elif error_code >= 500:
            error_msg = f"Server error ({error_code}): The CodeAlive service encountered an issue"
        else:
            error_msg = f"HTTP error: {error_code} - {error_detail}"

        await ctx.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"Unexpected error in get_data_sources after {elapsed_time:.2f}s: {type(e).__name__}: {e}")
        await ctx.error(f"Error retrieving data sources: {str(e)}")
        return f"Error retrieving data sources: {str(e)}. Please check your API credentials and try again."

@mcp.tool()
async def search_code(
        ctx: Context,
        query: str,
        data_source_ids: List[str] = None,
        mode: str = "auto",
        include_content: bool = False
) -> str:
    """
    SEMANTIC search across your codebases.

    This endpoint is optimized for **natural-language** questions and intent-driven queries
    (not rigid templates). Ask it things like:
      • "What is the authentication flow?"
      • "Where is the user registration logic implemented?"
      • "How do services communicate with the billing API?"
      • "Where is rate limiting handled?"
      • "Show me how we validate JWTs."

    You can still include function/class names if you know them, but it's not required.

    Args:
        ctx: FastMCP context
        query: A natural-language description of what you're looking for.
               Prefer questions/phrases over template strings.
               Examples: "What initializes the database connection?",
                         "Where do we parse OAuth callbacks?",
                         "user registration controller"

        data_source_ids: List of data source IDs to search in (required).
                         Can be workspace IDs (search all repositories in the workspace)
                         or individual repository IDs for targeted searches.
                         Example: ["67f664fd4c2a00698a52bb6f", "5e8f9a2c1d3b7e4a6c9d0f8e"]

        mode: Search mode (case-insensitive):
              - "auto": (Default, recommended) Adaptive semantic search.
              - "fast": Lightweight/lexical pass; quickest for obvious matches.
              - "deep": Exhaustive semantic exploration; use sparingly for hard,
                        cross-cutting questions.

        include_content: Whether to include full file content in results (default: false).
                         It's **not recommended** to include full file content, cause files content may be outdated.

    Returns:
        Formatted search results including:
        - Source repository/workspace name and type
        - File path
        - Line numbers
        - Code snippet showing the matching section
        - Full file content (if include_content=true)

    Examples:
        1. Natural-language question (recommended):
           search_code(query="What is the auth flow?", data_source_ids=["repo123"])

        2. Intent query:
           search_code(query="Where is user registration logic?", data_source_ids=["repo123"])

        3. Workspace-wide question:
           search_code(query="How do microservices talk to the billing API?", data_source_ids=["workspace456"])

        4. Mixed query with a known identifier:
           search_code(query="Where do we validate JWTs (AuthService)?", data_source_ids=["repo123"])

        5. Concise results without full file contents:
           search_code(query="Where is password reset handled?", data_source_ids=["repo123"], include_content=false)

    Note:
        - At least one data_source_id must be provided
        - All data sources must be in "Alive" state
        - The API key must have access to the specified data sources
        - Prefer natural-language questions; templates are unnecessary.
        - Start with "auto" for best semantic results; escalate to "deep" only if needed.
        - If you know precise symbols (functions/classes), include them to narrow scope.
    """
    import time
    start_time = time.time()
    
    data_source_count = len(data_source_ids) if data_source_ids else 0
    logger.info(f"search_code called: query_length={len(query) if query else 0}, "
               f"data_sources={data_source_count}, mode={mode}, include_content={include_content}")
    logger.debug(f"Query preview: {query[:100] + '...' if len(query) > 100 else query}")
    if data_source_ids:
        logger.debug(f"Data source IDs: {data_source_ids}")
    
    # Get context
    context: CodeAliveContext = ctx.request_context.lifespan_context
    logger.debug("Retrieved CodeAlive context from lifespan")

    # Validate inputs
    if not query or not query.strip():
        logger.warning("search_code: Empty query provided")
        return "Error: Query cannot be empty. Please provide a search term, function name, or description of the code you're looking for."

    if not data_source_ids or len(data_source_ids) == 0:
        logger.info("No data source IDs provided, will use API key default")
        await ctx.info("No data source IDs provided. If the API key has exactly one assigned data source, that will be used as default.")

    try:
        # Normalize mode string to match expected enum values
        normalized_mode = mode.lower() if mode else "auto"
        logger.debug(f"Normalized search mode: {mode} -> {normalized_mode}")

        # Map input mode to backend's expected enum values
        if normalized_mode not in ["auto", "fast", "deep"]:
            logger.warning(f"Invalid search mode '{mode}', using 'auto' instead")
            await ctx.warning(f"Invalid search mode: {mode}. Valid modes are 'auto', 'fast', and 'deep'. Using 'auto' instead.")
            normalized_mode = "auto"

        # Log the search attempt
        if data_source_ids and len(data_source_ids) > 0:
            await ctx.info(f"Searching for '{query}' in {len(data_source_ids)} data source(s) using {normalized_mode} mode")
        else:
            await ctx.info(f"Searching for '{query}' using API key's default data source with {normalized_mode} mode")

        # Prepare query parameters
        params = {
            "Query": query,
            "Mode": normalized_mode,
            "IncludeContent": "true" if include_content else "false"
        }
        logger.debug(f"Base query parameters: {params}")

        if data_source_ids and len(data_source_ids) > 0:
            # Add each data source ID as a separate query parameter
            valid_ds_count = 0
            for ds_id in data_source_ids:
                if ds_id:  # Skip None or empty values
                    params["DataSourceIds"] = ds_id
                    valid_ds_count += 1
            logger.debug(f"Added {valid_ds_count} data source IDs to query")
        else:
            logger.debug("No data source IDs provided, using API key default")
            await ctx.info("Using API key's default data source (if available)")

        # Get API key based on transport mode
        logger.debug("Extracting API key from context for search_code")
        api_key = get_api_key_from_context(ctx)
        logger.debug(f"API key extracted successfully (length: {len(api_key)})")
        
        # Create headers with authorization
        headers = {"Authorization": f"Bearer {api_key}"}
        logger.debug("Created request headers with authorization")
        
        # Make API request
        logger.debug("Making GET request to /api/search")
        response = await context.client.get("/api/search", params=params, headers=headers)

        # Check for errors
        logger.debug(f"Received response with status: {response.status_code}")
        response.raise_for_status()
        logger.debug("HTTP response status check passed")

        # Parse the response
        search_results = response.json()
        result_count = len(search_results.get("results", [])) if search_results else 0
        logger.info(f"Retrieved {result_count} search results from API")

        # Format the results for readability
        if not search_results or not search_results.get("results") or len(search_results.get("results", [])) == 0:
            # Provide helpful suggestions if no results found
            logger.warning(f"No search results found for query: '{query}' with mode: {normalized_mode}")
            return (
                "No search results found. Consider trying:\n"
                "1. Different search terms or more specific keywords\n"
                "2. A different search mode (try 'deep' for semantic search)\n"
                "3. Checking if the data sources are correctly indexed\n"
                "4. Using simpler or more common terms related to your query"
            )

        logger.debug(f"Formatting {result_count} search results")
        formatted_results = []
        for idx, result in enumerate(search_results.get("results", [])):
            if not result:
                continue

            data_source = result.get("dataSource", {}) or {}
            location = result.get("location", {}) or {}

            result_str = f"Result {idx+1}:\n"
            result_str += f"  Source: {data_source.get('name', 'Unknown')} ({data_source.get('type', 'Unknown')})\n"
            result_str += f"  Path: {location.get('path', 'Unknown')}\n"

            # Add line numbers if available
            if location and location.get("range"):
                start = location["range"].get("start", {}) or {}
                end = location["range"].get("end", {}) or {}
                if start and end:
                    result_str += f"  Lines: {start.get('line', 0)}-{end.get('line', 0)}\n"

            # Add snippet
            if result.get("snippet"):
                result_str += f"  Snippet: {result['snippet']}\n"

            # Add full content if available and requested
            if include_content and result.get("content"):
                content_length = len(result['content'])
                result_str += f"  Content:\n{result['content']}\n"
                logger.debug(f"Included full content for result {idx+1} (length: {content_length})")

            formatted_results.append(result_str)

        result_text = "\n".join(formatted_results)

        # Add search metadata
        result_count = len(search_results.get("results", []))
        mode_used = search_results.get("searchMode", normalized_mode)

        metadata = (
            f"\nFound {result_count} results using {mode_used} search mode.\n"
            f"Query: '{query}'\n"
        )

        # Add usage hint
        usage_hint = (
            "\nTo explore these results further:\n"
            "1. Use ask_question() to ask detailed questions about specific files\n"
            "2. Try a different search mode for more or fewer results\n"
            "3. Refine your query with more specific terms"
        )

        elapsed_time = time.time() - start_time
        logger.info(f"search_code completed successfully: {result_count} results in {elapsed_time:.2f}s")
        return result_text + metadata + usage_hint

    except httpx.HTTPStatusError as e:
        elapsed_time = time.time() - start_time
        error_code = e.response.status_code
        error_detail = e.response.text
        logger.error(f"HTTP error in search_code after {elapsed_time:.2f}s: {error_code} - {error_detail[:200]}")

        # Provide more helpful error messages based on status codes
        if error_code == 401:
            error_msg = f"Authentication error (401): Invalid API key or insufficient permissions"
        elif error_code == 404:
            error_msg = f"Not found error (404): One or more data sources could not be found. Check your data_source_ids."
        elif error_code == 429:
            error_msg = f"Rate limit exceeded (429): Too many requests, please try again later"
        elif error_code >= 500:
            error_msg = f"Server error ({error_code}): The CodeAlive service encountered an issue"
        else:
            error_msg = f"HTTP error: {error_code} - {error_detail}"

        await ctx.error(error_msg)
        return f"Error: {error_msg}"
    except json.JSONDecodeError as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Invalid JSON response: {str(e)}"
        logger.error(f"JSON decode error in search_code after {elapsed_time:.2f}s: {e}")
        await ctx.error(error_msg)
        return f"Error: {error_msg}. The server returned an invalid response."
    except Exception as e:
        elapsed_time = time.time() - start_time
        error_msg = f"Error during code search: {str(e)}"
        logger.error(f"Unexpected error in search_code after {elapsed_time:.2f}s: {type(e).__name__}: {e}")
        await ctx.error(error_msg)
        return f"Error: {error_msg}. Please check your input parameters and try again."

# Run the server when script is executed directly
if __name__ == "__main__":
    # Get command line arguments or use environment variables
    parser = argparse.ArgumentParser(description="CodeAlive MCP Server")
    parser.add_argument("--api-key", help="CodeAlive API Key")
    parser.add_argument("--base-url", help="CodeAlive Base URL")
    parser.add_argument("--transport", help="Transport type (stdio or http)", default="stdio")
    parser.add_argument("--host", help="Host for HTTP transport", default="0.0.0.0")
    parser.add_argument("--port", help="Port for HTTP transport", type=int, default=8000)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for verbose logging")
    parser.add_argument("--ignore-ssl", action="store_true", help="Ignore SSL certificate validation")

    args = parser.parse_args()

    # Configure logging based on debug mode
    configure_logging(debug_mode=args.debug)

    # Set environment variables if provided as arguments
    # Command line arguments always take precedence over .env file/environment variables
    if args.api_key:
        os.environ["CODEALIVE_API_KEY"] = args.api_key

    if args.base_url:
        os.environ["CODEALIVE_BASE_URL"] = args.base_url
        logger.info(f"Using base URL from command line: {args.base_url}")

    # Set SSL verification flag
    # Disable SSL verification if explicitly requested or in debug mode
    if args.ignore_ssl or args.debug:
        os.environ["CODEALIVE_IGNORE_SSL"] = "true"
        if args.ignore_ssl:
            logger.warning("SSL certificate validation disabled by --ignore-ssl flag")
        elif args.debug:
            logger.warning("SSL certificate validation disabled in debug mode")

    # Debug environment if requested
    if args.debug:
        logger.debug("\nDEBUG MODE ENABLED")
        logger.debug("Environment:")
        logger.debug(f"  - Current working dir: {os.getcwd()}")
        logger.debug(f"  - Script location: {__file__}")
        logger.debug(f"  - Dotenv path: {dotenv_path}")
        logger.debug(f"  - Dotenv file exists: {os.path.exists(dotenv_path)}")
        if os.path.exists(dotenv_path):
            with open(dotenv_path, 'r') as f:
                env_content = f.read()
                # Mask API key if present
                masked_env = env_content.replace(os.environ.get("CODEALIVE_API_KEY", ""), "****API_KEY****")
                logger.debug(f"  - Dotenv content:\n{masked_env}")

    # Set transport mode for validation
    os.environ["TRANSPORT_MODE"] = args.transport
    
    # Validate configuration based on transport mode
    api_key = os.environ.get("CODEALIVE_API_KEY", "")
    base_url = os.environ.get("CODEALIVE_BASE_URL", "")

    if args.transport == "stdio":
        # STDIO mode: require API key in environment
        if not api_key:
            logger.error("STDIO mode requires CODEALIVE_API_KEY environment variable.")
            logger.error("Please set this in your .env file or environment.")
            sys.exit(1)
        logger.info(f"STDIO mode: Using API key from environment (ends with: ...{api_key[-4:] if len(api_key) > 4 else '****'})")
    else:
        # HTTP mode: API keys must be provided via Authorization: Bearer headers
        if api_key:
            logger.warning("HTTP mode detected CODEALIVE_API_KEY in environment.")
            logger.warning("In production, API keys should be provided via Authorization: Bearer headers.")
            logger.warning("Environment variable will be ignored in HTTP mode.")
        logger.info("HTTP mode: API keys will be extracted from Authorization: Bearer headers")

    if not base_url:
        logger.warning("CODEALIVE_BASE_URL environment variable is not set, using default.")
        logger.warning("CodeAlive will connect to the production API at https://app.codealive.ai")

    # Run the server with the selected transport
    if args.transport == "http":
        # Use /api path to avoid conflicts with health endpoint
        mcp.run(transport="http", host=args.host, port=args.port, path="/api")
    else:
        mcp.run(transport="stdio")
