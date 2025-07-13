import os
import json
import httpx
import asyncio
import ssl
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Any, AsyncIterator, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dotenv import load_dotenv
import argparse
import sys

# Load environment variables from .env file
# Use the actual script directory to find .env file
script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
dotenv_path = os.path.join(project_dir, '.env')
load_dotenv(dotenv_path=dotenv_path)

# Import FastMCP components
from fastmcp import Context, FastMCP
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
    transport_mode = os.environ.get("TRANSPORT_MODE", "stdio")
    
    if transport_mode == "http":
        # HTTP mode - extract from Authorization header
        # Check if we have HTTP request context
        if hasattr(ctx, 'request') and ctx.request:
            auth_header = ctx.request.headers.get("Authorization", "")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise ValueError("HTTP mode: Authorization: Bearer <api-key> header required")
            return auth_header[7:]  # Remove "Bearer "
        else:
            raise ValueError("HTTP mode: No request context available for Authorization header")
    else:
        # STDIO mode - use environment variable
        api_key = os.environ.get("CODEALIVE_API_KEY", "")
        if not api_key:
            raise ValueError("STDIO mode: CODEALIVE_API_KEY environment variable required")
        return api_key

@asynccontextmanager
async def codealive_lifespan(server: FastMCP) -> AsyncIterator[CodeAliveContext]:
    """Manage CodeAlive API client lifecycle"""
    transport_mode = os.environ.get("TRANSPORT_MODE", "stdio")
    
    # Get base URL from environment or use default
    if os.environ.get("CODEALIVE_BASE_URL") is None:
        print("WARNING: CODEALIVE_BASE_URL not found in environment, using default")
        base_url = "https://app.codealive.ai"
    else:
        base_url = os.environ.get("CODEALIVE_BASE_URL")
        print(f"DEBUG: Found CODEALIVE_BASE_URL in environment: '{base_url}'")

    # Check if we should bypass SSL verification
    verify_ssl = not os.environ.get("CODEALIVE_IGNORE_SSL", "").lower() in ["true", "1", "yes"]

    if transport_mode == "stdio":
        # STDIO mode: create client with fixed API key
        api_key = os.environ.get("CODEALIVE_API_KEY", "")
        print(f"CodeAlive MCP Server starting in STDIO mode:")
        print(f"  - API Key: {'*' * 5}{api_key[-5:] if api_key else 'Not set'}")
        print(f"  - Base URL: {base_url}")
        print(f"  - SSL Verification: {'Enabled' if verify_ssl else 'Disabled'}")
        
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
        print(f"CodeAlive MCP Server starting in HTTP mode:")
        print(f"  - API Keys: Extracted from Authorization headers per request")
        print(f"  - Base URL: {base_url}")
        print(f"  - SSL Verification: {'Enabled' if verify_ssl else 'Disabled'}")
        
        # Create base client without authentication headers
        client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Content-Type": "application/json",
            },
            timeout=60.0,
            verify=verify_ssl,
        )

    try:
        yield CodeAliveContext(
            client=client,
            api_key="",  # Will be set per-request in HTTP mode
            base_url=base_url
        )
    finally:
        await client.aclose()

# Initialize FastMCP server with lifespan and enhanced system instructions
mcp = FastMCP(
    name="CodeAlive MCP Server",
    instructions="""
    This server provides access to the CodeAlive API for AI-powered code assistance and code understanding.
    
    CodeAlive enables you to:
    - Analyze code repositories and workspaces
    - Search through code using natural language
    - Understand code structure, dependencies, and patterns
    - Answer questions about code implementation details
    - Integrate with local git repositories for seamless code exploration
    
    When working with a codebase:
    1. First use `get_data_sources` to identify available repositories and workspaces
    2. Then use `search_code` to find relevant files and code snippets
    3. Finally, use `chat_completions` for in-depth analysis of the code
    
    For effective code exploration:
    - Start with broad queries to understand the overall structure
    - Use specific function/class names when looking for particular implementations
    - Combine natural language with code patterns in your queries
    - Always use "auto" search mode by default; it intelligently selects the appropriate search depth
    - IMPORTANT: Only use "deep" search mode for very complex conceptual queries as it's resource-intensive
    - Remember that context from previous messages is maintained in the same conversation
    
    Flexible data source usage:
    - You can use a workspace ID as a single data source to search or chat across all its repositories at once
    - Alternatively, you can use specific repository IDs for more targeted searches
    - For complex queries, you can combine multiple repository IDs from different workspaces
    - Choose between workspace-level or repository-level access based on the scope of the query
    
    Repository integration:
    - CodeAlive can connect to repositories you've indexed in the system
    - If a user is working within a git repository that matches a CodeAlive-indexed repository (by URL), 
      you can suggest using CodeAlive's search and chat to understand the codebase
    - Data sources include repository URLs to help match with local git repositories
    - Workspaces include a list of repository IDs, allowing you to understand their composition
    - You can use repository IDs from workspaces to search or chat about specific repositories within a workspace
    
    When analyzing search results:
    - Pay attention to file paths to understand the project structure
    - Look for patterns across multiple matching files
    - Consider the relationships between different code components
    """,
    lifespan=codealive_lifespan
)

# Add health check endpoint for AWS ALB
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for load balancer"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "service": "codealive-mcp-server"
    })

@mcp.tool()
async def chat_completions(
        ctx: Context,
        messages: List[Dict[str, str]] = None,
        data_sources: List[Dict[str, str]] = None,
        stream: bool = True,
        conversation_id: Optional[str] = None,
        debug: bool = False
) -> str:
    """
    Streams chat completions from the CodeAlive API for code-aware conversations with knowledge of your codebase.
    
    Args:
        messages: List of message objects with "role" and "content" fields
                 Example: [
                   {"role": "system", "content": "Analyze the authentication flow"},
                   {"role": "user", "content": "How does the login process work?"}
                 ]
        
        data_sources: List of data source objects to include in the context
                     Can include workspace IDs (to chat about all repositories in the workspace)
                     or specific repository IDs for more focused analysis.
                     Example: [
                       {"type": "repository", "id": "67f664fd4c2a00698a52bb6f"},
                       {"type": "workspace", "id": "5e8f9a2c1d3b7e4a6c9d0f8e"}
                     ]
        
        stream: Whether to stream the response (must be true, non-streaming is not supported)
               Default: true
        
        conversation_id: Optional ID to continue a previous conversation
                        Example: "conv_6789f123a456b789c123d456"
        
        debug: Whether to include debug information in the response
               Default: false
        
    Returns:
        The generated completion text with code understanding from specified repositories/workspaces.
        The response will incorporate knowledge from the specified code repositories.
        
    Examples:
        1. Start a new conversation about authentication using a specific repository:
           chat_completions(
             messages=[{"role": "user", "content": "Explain the authentication flow in this code"}],
             data_sources=[{"type": "repository", "id": "67f664fd4c2a00698a52bb6f"}]
           )
           
        2. Start a new conversation using an entire workspace:
           chat_completions(
             messages=[{"role": "user", "content": "How do the microservices communicate with each other?"}],
             data_sources=[{"type": "workspace", "id": "5e8f9a2c1d3b7e4a6c9d0f8e"}]
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
    # Get context
    context: CodeAliveContext = ctx.request_context.lifespan_context

    # Validate inputs
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
        "stream": stream,
        "debug": debug
    }

    if conversation_id:
        request_data["conversationId"] = conversation_id

    if data_sources:
        # Validate each data source
        valid_data_sources = []
        for ds in data_sources:
            if ds and ds.get("id") and ds.get("type"):
                valid_data_sources.append(ds)
            else:
                await ctx.warning(f"Skipping invalid data source: {ds}. Each data source must have 'type' and 'id' fields.")

        request_data["dataSources"] = valid_data_sources

    try:
        # Get API key based on transport mode
        api_key = get_api_key_from_context(ctx)
        
        # Log the attempt
        await ctx.info(f"Requesting chat completion with {len(messages)} messages" +
                       (f" in conversation {conversation_id}" if conversation_id else " in a new conversation"))

        # Create headers with authorization
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Make API request
        response = await context.client.post(
            "/api/chat/completions",
            json=request_data,
            headers=headers
        )

        # Check for errors
        response.raise_for_status()

        # For streaming response, we need to concatenate the chunks
        if stream:
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
        else:
            # For non-streaming response, just return the content
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0].get("message", {}).get("content", "")
            return "No content in response. Please check that your data sources are accessible and try again."

    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_detail = e.response.text

        # Provide more helpful error messages based on status codes
        if error_code == 401:
            error_msg = f"Authentication error (401): Invalid API key or insufficient permissions"
        elif error_code == 404:
            error_msg = f"Not found error (404): The requested resource could not be found, check your conversation_id or data_source_ids"
        elif error_code == 429:
            error_msg = f"Rate limit exceeded (429): Too many requests, please try again later"
        elif error_code >= 500:
            error_msg = f"Server error ({error_code}): The CodeAlive service encountered an issue"
        else:
            error_msg = f"HTTP error: {error_code} - {error_detail}"

        await ctx.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Error during chat completion: {str(e)}"
        await ctx.error(error_msg)
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
        
        Use the returned data source IDs with the search_code and chat_completions functions.
    """
    # Get context
    context: CodeAliveContext = ctx.request_context.lifespan_context

    try:
        # Get API key based on transport mode
        api_key = get_api_key_from_context(ctx)
        
        # Determine the endpoint based on alive_only flag
        endpoint = "/api/datasources/alive" if alive_only else "/api/datasources/all"

        # Create headers with authorization
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Make API request
        response = await context.client.get(endpoint, headers=headers)

        # Check for errors
        response.raise_for_status()

        # Parse and format the response
        data_sources = response.json()

        # If no data sources found, return a helpful message
        if not data_sources or len(data_sources) == 0:
            return "No data sources found. Please add a repository or workspace to CodeAlive before using this API."

        # Format the response as a readable string
        formatted_data = json.dumps(data_sources, indent=2)
        result = f"Available data sources:\n{formatted_data}"

        # Add usage hint
        result += "\n\nYou can use these data source IDs with the search_code and chat_completions functions."

        return result

    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_detail = e.response.text

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
        await ctx.error(f"Error retrieving data sources: {str(e)}")
        return f"Error retrieving data sources: {str(e)}. Please check your API credentials and try again."

@mcp.tool()
async def search_code(
        ctx: Context,
        query: str,
        data_source_ids: List[str] = None,
        mode: str = "auto",
        include_content: bool = True
) -> str:
    """
    Search for code snippets across the provided data sources using natural language or code patterns.
    
    Args:
        query: The search query - can be natural language ("find authentication code") or code patterns ("function getUserById")
              For best results, be specific and include relevant keywords or function/class names
              Example: "implement JWT token validation"
              
        data_source_ids: List of data source IDs to search in (required)
                        Can be workspace IDs (to search across all repositories in the workspace) 
                        or individual repository IDs for more targeted searches.
                        Example: ["67f664fd4c2a00698a52bb6f", "5e8f9a2c1d3b7e4a6c9d0f8e"]
                        
        mode: Search mode (case-insensitive):
              - "auto": (Default) RECOMMENDED - Intelligently adapts search depth based on query complexity
              - "fast": Quick scan for exact matches, best for simple queries and large codebases
              - "fast_deeper": Balanced search with moderate semantic analysis, good for general use
              - "deep": Use SPARINGLY - Resource-intensive thorough semantic analysis, only for very complex
                        conceptual queries when other modes fail to yield results
              Example: "auto"
                
        include_content: Whether to include the full file content in results (default: true)
                        Set to false for faster, more concise results when only locations are needed
                        Example: true
        
    Returns:
        Formatted search results including:
        - Source repository/workspace name and type
        - File path
        - Line numbers
        - Code snippet showing the matching section
        - Full file content (if include_content=true)
        
    Examples:
        1. Find authentication implementation (using default auto mode - recommended):
           search_code(query="user authentication implementation", data_source_ids=["repo123"])
           
        2. Find a specific function quickly:
           search_code(query="calculateTotalPrice function", data_source_ids=["repo123"], mode="fast")
           
        3. Search across an entire workspace:
           search_code(query="database connection", data_source_ids=["workspace456"])
           
        4. Search across specific repositories from different workspaces:
           search_code(query="authentication flow", data_source_ids=["repo123", "repo789"])
        
        5. Get concise results without full file contents:
           search_code(query="password reset", data_source_ids=["repo123"], include_content=false)
    
    Note:
        - At least one data_source_id must be provided
        - All data sources must be in "Alive" state
        - The API key must have access to the specified data sources
        - Always start with "auto" mode first, as it intelligently chooses the appropriate search strategy
        - The "deep" mode should only be used when absolutely necessary as it's resource-intensive
        - For finding specific implementations, include function names in your query
        - For understanding architectural patterns, use natural language descriptions
    """
    # Get context
    context: CodeAliveContext = ctx.request_context.lifespan_context

    # Validate inputs
    if not query or not query.strip():
        return "Error: Query cannot be empty. Please provide a search term, function name, or description of the code you're looking for."

    if not data_source_ids or len(data_source_ids) == 0:
        await ctx.info("No data source IDs provided. If the API key has exactly one assigned data source, that will be used as default.")

    try:
        # Normalize mode string to match expected enum values
        normalized_mode = mode.lower() if mode else "auto"

        # Map input mode to backend's expected enum values
        if normalized_mode not in ["auto", "fast", "fast_deeper", "deep"]:
            await ctx.warning(f"Invalid search mode: {mode}. Valid modes are 'auto', 'fast', 'fast_deeper', and 'deep'. Using 'auto' instead.")
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

        if data_source_ids and len(data_source_ids) > 0:
            # Add each data source ID as a separate query parameter
            for ds_id in data_source_ids:
                if ds_id:  # Skip None or empty values
                    params["DataSourceIds"] = ds_id
        else:
            await ctx.info("Using API key's default data source (if available)")

        # Get API key based on transport mode
        api_key = get_api_key_from_context(ctx)
        
        # Create headers with authorization
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Make API request
        response = await context.client.get("/api/search", params=params, headers=headers)

        # Check for errors
        response.raise_for_status()

        # Parse the response
        search_results = response.json()

        # Format the results for readability
        if not search_results or not search_results.get("results") or len(search_results.get("results", [])) == 0:
            # Provide helpful suggestions if no results found
            return (
                "No search results found. Consider trying:\n"
                "1. Different search terms or more specific keywords\n"
                "2. A different search mode (try 'deep' for semantic search)\n"
                "3. Checking if the data sources are correctly indexed\n"
                "4. Using simpler or more common terms related to your query"
            )

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
                result_str += f"  Content:\n{result['content']}\n"

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
            "1. Use chat_completions() to ask detailed questions about specific files\n"
            "2. Try a different search mode for more or fewer results\n"
            "3. Refine your query with more specific terms"
        )

        return result_text + metadata + usage_hint

    except httpx.HTTPStatusError as e:
        error_code = e.response.status_code
        error_detail = e.response.text

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
        error_msg = f"Invalid JSON response: {str(e)}"
        await ctx.error(error_msg)
        return f"Error: {error_msg}. The server returned an invalid response."
    except Exception as e:
        error_msg = f"Error during code search: {str(e)}"
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

    # Set environment variables if provided as arguments
    # Command line arguments always take precedence over .env file/environment variables
    if args.api_key:
        os.environ["CODEALIVE_API_KEY"] = args.api_key

    if args.base_url:
        os.environ["CODEALIVE_BASE_URL"] = args.base_url
        print(f"Using base URL from command line: {args.base_url}")

    # Set SSL verification flag
    # Disable SSL verification if explicitly requested or in debug mode
    if args.ignore_ssl or args.debug:
        os.environ["CODEALIVE_IGNORE_SSL"] = "true"
        if args.ignore_ssl:
            print("SSL certificate validation disabled by --ignore-ssl flag")
        elif args.debug:
            print("SSL certificate validation disabled in debug mode")

    # Debug environment if requested
    if args.debug:
        print("\nDEBUG MODE ENABLED")
        print("Environment:")
        print(f"  - Current working dir: {os.getcwd()}")
        print(f"  - Script location: {__file__}")
        print(f"  - Dotenv path: {dotenv_path}")
        print(f"  - Dotenv file exists: {os.path.exists(dotenv_path)}")
        if os.path.exists(dotenv_path):
            with open(dotenv_path, 'r') as f:
                env_content = f.read()
                # Mask API key if present
                masked_env = env_content.replace(os.environ.get("CODEALIVE_API_KEY", ""), "****API_KEY****")
                print(f"  - Dotenv content:\n{masked_env}")

    # Set transport mode for validation
    os.environ["TRANSPORT_MODE"] = args.transport
    
    # Validate configuration based on transport mode
    api_key = os.environ.get("CODEALIVE_API_KEY", "")
    base_url = os.environ.get("CODEALIVE_BASE_URL", "")

    if args.transport == "stdio":
        # STDIO mode: require API key in environment
        if not api_key:
            print("ERROR: STDIO mode requires CODEALIVE_API_KEY environment variable.")
            print("Please set this in your .env file or environment.")
            sys.exit(1)
        print(f"STDIO mode: Using API key from environment (ends with: ...{api_key[-4:] if len(api_key) > 4 else '****'})")
    else:
        # HTTP mode: prohibit API key in environment
        if api_key:
            print("ERROR: HTTP mode detected CODEALIVE_API_KEY in environment.")
            print("Remove the environment variable. API keys must be provided via Authorization: Bearer headers.")
            sys.exit(1)
        print("HTTP mode: API keys will be extracted from Authorization: Bearer headers")

    if not base_url:
        print("WARNING: CODEALIVE_BASE_URL environment variable is not set, using default.")
        print("CodeAlive will connect to the production API at https://app.codealive.ai")

    # Run the server with the selected transport
    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")
