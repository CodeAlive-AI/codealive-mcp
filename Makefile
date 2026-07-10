.PHONY: help install audit test smoke-test unit-test integration-test clean run dev

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync --locked --extra test

audit:  ## Check the locked environment for known vulnerabilities
	uv audit

smoke-test:  ## Run smoke tests (quick sanity check)
	@echo "Running smoke tests..."
	uv run python smoke_test.py

unit-test:  ## Run unit tests with pytest
	@echo "Running unit tests..."
	uv run pytest src/tests/ -v

integration-test:  ## Run live smoke tests (requires CODEALIVE_API_KEY and CODEALIVE_TEST_DATA_SOURCE)
	@echo "Running integration tests..."
	uv run python integration_test.py

test: unit-test smoke-test  ## Run all tests (unit + smoke)

clean:  ## Clean up cache and temp files
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf src/__pycache__
	rm -rf src/tests/__pycache__
	rm -rf *.pyc
	rm -rf src/*.pyc
	rm -rf .coverage
	rm -rf htmlcov

run:  ## Run the MCP server with stdio transport
	uv run python src/codealive_mcp_server.py

dev:  ## Run the MCP server in debug mode
	uv run python src/codealive_mcp_server.py --debug
