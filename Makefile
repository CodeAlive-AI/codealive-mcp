.PHONY: help install test smoke-test unit-test clean run dev

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv pip install -e ".[test]"

smoke-test:  ## Run smoke tests (quick sanity check)
	@echo "Running smoke tests..."
	python smoke_test.py

unit-test:  ## Run unit tests with pytest
	@echo "Running unit tests..."
	pytest src/tests/ -v

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
	python src/codealive_mcp_server.py

dev:  ## Run the MCP server in debug mode
	python src/codealive_mcp_server.py --debug
