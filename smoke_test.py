#!/usr/bin/env python3
"""
Smoke test for CodeAlive MCP Server.

This script performs quick sanity checks to verify the MCP server is working correctly.
Run this after making local changes to quickly verify everything still works.

Usage:
    python smoke_test.py

Or with custom API key:
    CODEALIVE_API_KEY=your_key python smoke_test.py
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("❌ ERROR: MCP SDK not installed")
    print("Install it with: pip install mcp")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class SmokeTest:
    """Smoke test runner for MCP server."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.session = None

    def print_header(self, text: str):
        """Print a formatted test header."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

    def print_test(self, name: str):
        """Print test name."""
        print(f"{Colors.BOLD}Testing: {name}{Colors.END}")

    def print_success(self, message: str):
        """Print success message."""
        print(f"  {Colors.GREEN}✓ {message}{Colors.END}")
        self.passed += 1

    def print_error(self, message: str):
        """Print error message."""
        print(f"  {Colors.RED}✗ {message}{Colors.END}")
        self.failed += 1

    def print_info(self, message: str):
        """Print info message."""
        print(f"  {Colors.YELLOW}ℹ {message}{Colors.END}")

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.BOLD}Test Summary{Colors.END}")
        print(f"{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"Total tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.END}")

        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All smoke tests passed!{Colors.END}")
            return 0
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.END}")
            return 1

    @asynccontextmanager
    async def get_client_session(self):
        """Create and connect to MCP server."""
        server_script = str(Path(__file__).parent / "src" / "codealive_mcp_server.py")

        # Prepare server parameters
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env={
                **os.environ,
                # Use environment API key if available
                "CODEALIVE_API_KEY": os.environ.get("CODEALIVE_API_KEY", "test_key_for_smoke_test"),
            }
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.session = session
                yield session

    async def test_server_connection(self) -> bool:
        """Test that server connects and initializes."""
        self.print_test("Server Connection")
        try:
            if self.session is None:
                self.print_error("Session not initialized")
                return False

            self.print_success("Server connected successfully")
            # Note: ClientSession doesn't expose server info directly
            return True
        except Exception as e:
            self.print_error(f"Connection failed: {str(e)}")
            return False

    async def test_list_tools(self) -> bool:
        """Test that server reports available tools."""
        self.print_test("Tool Discovery")
        try:
            result = await self.session.list_tools()
            tools = result.tools

            expected_tools = {"codebase_consultant", "get_data_sources", "codebase_search"}
            actual_tools = {tool.name for tool in tools}

            if expected_tools == actual_tools:
                self.print_success(f"Found all {len(tools)} expected tools")
                for tool in tools:
                    self.print_info(f"  - {tool.name}: {tool.description[:60]}...")
                return True
            else:
                missing = expected_tools - actual_tools
                extra = actual_tools - expected_tools
                if missing:
                    self.print_error(f"Missing tools: {missing}")
                if extra:
                    self.print_error(f"Unexpected tools: {extra}")
                return False

        except Exception as e:
            self.print_error(f"Tool listing failed: {str(e)}")
            return False

    async def test_get_data_sources(self) -> bool:
        """Test the get_data_sources tool."""
        self.print_test("get_data_sources Tool")
        try:
            result = await self.session.call_tool("get_data_sources", {})

            if result.isError:
                # Error is expected if no valid API key
                if "API key" in str(result.content):
                    self.print_success("Tool responds correctly (API key required)")
                    self.print_info("This is expected in smoke test without valid API key")
                    return True
                else:
                    self.print_error(f"Unexpected error: {result.content}")
                    return False

            # If we have a valid API key, check the response structure
            self.print_success("Tool executed successfully")
            self.print_info(f"Response: {str(result.content)[:100]}...")
            return True

        except Exception as e:
            self.print_error(f"Tool execution failed: {str(e)}")
            return False

    async def test_codebase_search(self) -> bool:
        """Test the codebase_search tool."""
        self.print_test("codebase_search Tool")
        try:
            result = await self.session.call_tool("codebase_search", {
                "query": "test query",
                "data_sources": ["test-repo"],
                "mode": "auto",
                "include_content": False
            })

            if result.isError:
                # Error is expected if no valid API key or invalid data source
                error_str = str(result.content)
                if "API key" in error_str or "data source" in error_str or "authorization" in error_str.lower():
                    self.print_success("Tool responds correctly (API key/data source required)")
                    self.print_info("This is expected in smoke test without valid API key")
                    return True
                else:
                    self.print_error(f"Unexpected error: {result.content}")
                    return False

            # If we have a valid API key and data source, check response
            self.print_success("Tool executed successfully")
            self.print_info(f"Response: {str(result.content)[:100]}...")
            return True

        except Exception as e:
            self.print_error(f"Tool execution failed: {str(e)}")
            return False

    async def test_codebase_consultant(self) -> bool:
        """Test the codebase_consultant tool."""
        self.print_test("codebase_consultant Tool")
        try:
            result = await self.session.call_tool("codebase_consultant", {
                "question": "test question",
                "data_sources": ["test-repo"]
            })

            if result.isError:
                # Error is expected if no valid API key
                error_str = str(result.content)
                if "API key" in error_str or "data source" in error_str or "authorization" in error_str.lower():
                    self.print_success("Tool responds correctly (API key/data source required)")
                    self.print_info("This is expected in smoke test without valid API key")
                    return True
                else:
                    self.print_error(f"Unexpected error: {result.content}")
                    return False

            # If we have a valid API key and data source, check response
            self.print_success("Tool executed successfully")
            self.print_info(f"Response: {str(result.content)[:100]}...")
            return True

        except Exception as e:
            self.print_error(f"Tool execution failed: {str(e)}")
            return False

    async def test_parameter_validation(self) -> bool:
        """Test that tools validate parameters correctly."""
        self.print_test("Parameter Validation")
        try:
            # Test with invalid parameters
            result = await self.session.call_tool("codebase_search", {
                "query": "",  # Empty query should fail
                "data_sources": ["test"],
                "mode": "auto",
                "include_content": False
            })

            # Should get an error about empty query
            if result.isError or "empty" in str(result.content).lower() or "cannot be empty" in str(result.content):
                self.print_success("Parameter validation working correctly")
                return True
            else:
                self.print_error("Empty query was not rejected")
                return False

        except Exception as e:
            self.print_error(f"Validation test failed: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all smoke tests."""
        self.print_header("CodeAlive MCP Server - Smoke Tests")

        # Check for API key
        api_key = os.environ.get("CODEALIVE_API_KEY", "")
        if not api_key:
            self.print_info("No CODEALIVE_API_KEY found in environment")
            self.print_info("Tests will verify error handling paths")
            self.print_info("For full testing, set CODEALIVE_API_KEY environment variable\n")
        else:
            self.print_info(f"Using API key: ...{api_key[-4:]}\n")

        try:
            async with self.get_client_session():
                # Run all tests
                await self.test_server_connection()
                await self.test_list_tools()
                await self.test_get_data_sources()
                await self.test_codebase_search()
                await self.test_codebase_consultant()
                await self.test_parameter_validation()

        except Exception as e:
            self.print_error(f"Fatal error during tests: {str(e)}")
            import traceback
            traceback.print_exc()
            self.failed += 1

        return self.print_summary()


async def main():
    """Main entry point."""
    test = SmokeTest()
    return await test.run_all_tests()


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {str(e)}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
