"""Test suite for compact JSON response transformation."""

import json

import pytest
from utils.response_transformer import transform_search_response_to_json


class TestJsonTransformer:
    """Test cases for compact JSON response transformation."""

    @pytest.fixture
    def sample_search_response(self):
        """Sample search response with various result types."""
        return {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::path/auth.py::authenticate_user",
                    "score": 0.95,
                    "location": {
                        "path": "path/auth.py",
                        "range": {"start": {"line": 10}, "end": {"line": 25}}
                    },
                    "description": "Authenticates a user with username and password",
                    "contentByteSize": 1234
                },
                {
                    "kind": "Chunk",
                    "identifier": "owner/repo::path/auth.py::chunk1",
                    "score": 0.85,
                    "location": {"path": "path/auth.py"},
                    "description": "Authentication module header"
                },
                {
                    "kind": "File",
                    "identifier": "owner/repo::path/auth.py",
                    "score": 0.75,
                    "location": {"path": "path/auth.py"},
                    "contentByteSize": 5678
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::config/security.py::AUTH_PROVIDERS",
                    "score": 0.82,
                    "location": {
                        "path": "config/security.py",
                        "range": {"start": {"line": 5}, "end": {"line": 8}}
                    },
                    "description": "List of configured authentication providers",
                    "contentByteSize": 456
                },
                {
                    "kind": "Folder",
                    "identifier": "owner/repo::auth/",
                    "score": 0.60,
                    "location": {"path": "auth/"}
                }
            ]
        }

    def _is_compact(self, payload: str) -> bool:
        """Compact JSON has no spaces after separators."""
        return ", " not in payload and ": " not in payload

    def test_returns_compact_json_string(self, sample_search_response):
        """Output is a parseable, compact JSON string."""
        result = transform_search_response_to_json(sample_search_response)

        assert isinstance(result, str)
        assert self._is_compact(result)

        data = json.loads(result)
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_includes_all_essential_fields(self, sample_search_response):
        result = transform_search_response_to_json(sample_search_response)
        data = json.loads(result)

        first = data["results"][0]
        assert first["path"] == "path/auth.py"
        assert first["startLine"] == 10
        assert first["endLine"] == 25
        assert first["kind"] == "Symbol"
        assert first["identifier"] == "owner/repo::path/auth.py::authenticate_user"
        assert first["contentByteSize"] == 1234
        assert first["description"] == "Authenticates a user with username and password"

    def test_folders_are_skipped(self, sample_search_response):
        result = transform_search_response_to_json(sample_search_response)
        data = json.loads(result)

        for entry in data["results"]:
            assert entry.get("kind") != "Folder"

    def test_quotes_and_special_chars_use_json_escaping(self):
        """Quotes and other JSON-significant chars are escaped using JSON conventions."""
        response = {
            "results": [{
                "kind": "Symbol",
                "identifier": "owner/repo::file.py::func",
                "score": 0.9,
                "location": {
                    "path": "file.py",
                    "range": {"start": {"line": 1}, "end": {"line": 3}}
                },
                "description": 'Returns "<value>" & "other"'
            }]
        }

        result = transform_search_response_to_json(response)
        data = json.loads(result)

        # Round-trips cleanly without HTML entities
        assert data["results"][0]["description"] == 'Returns "<value>" & "other"'
        assert "&quot;" not in result
        assert "&amp;" not in result

    def test_empty_response(self):
        result = transform_search_response_to_json({"results": []})
        assert result == '{"results":[]}'

    def test_no_results_key(self):
        result = transform_search_response_to_json({})
        assert result == '{"results":[]}'

    def test_snippet_fallback_when_no_description(self):
        response = {
            "results": [{
                "kind": "Symbol",
                "identifier": "owner/repo::file.py::func",
                "location": {
                    "path": "file.py",
                    "range": {"start": {"line": 1}, "end": {"line": 5}}
                },
                "snippet": "def func(): return 42"
            }]
        }

        result = transform_search_response_to_json(response)
        data = json.loads(result)

        assert data["results"][0]["snippet"] == "def func(): return 42"
        assert "description" not in data["results"][0]

    def test_description_takes_precedence_over_snippet(self):
        response = {
            "results": [{
                "kind": "Symbol",
                "identifier": "owner/repo::file.py::func",
                "location": {
                    "path": "file.py",
                    "range": {"start": {"line": 1}, "end": {"line": 5}}
                },
                "description": "A helper function",
                "snippet": "def func(): return 42"
            }]
        }

        result = transform_search_response_to_json(response)
        data = json.loads(result)

        assert data["results"][0]["description"] == "A helper function"
        assert "snippet" not in data["results"][0]

    def test_no_description_no_snippet(self):
        response = {
            "results": [{
                "kind": "Symbol",
                "identifier": "owner/repo::file.py::func",
                "location": {
                    "path": "file.py",
                    "range": {"start": {"line": 1}, "end": {"line": 5}}
                }
            }]
        }

        result = transform_search_response_to_json(response)
        data = json.loads(result)

        entry = data["results"][0]
        assert "description" not in entry
        assert "snippet" not in entry

    def test_preserves_server_order(self):
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::important.py::critical_function",
                    "score": 0.95,
                    "location": {
                        "path": "important.py",
                        "range": {"start": {"line": 10}, "end": {"line": 20}}
                    }
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::less_important.py::helper",
                    "score": 0.75,
                    "location": {
                        "path": "less_important.py",
                        "range": {"start": {"line": 5}, "end": {"line": 10}}
                    }
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::another.py::utility",
                    "score": 0.60,
                    "location": {
                        "path": "another.py",
                        "range": {"start": {"line": 1}, "end": {"line": 5}}
                    }
                }
            ]
        }

        result = transform_search_response_to_json(response)
        data = json.loads(result)

        paths = [entry["path"] for entry in data["results"]]
        assert paths == ["important.py", "less_important.py", "another.py"]

    def test_performance_large_response(self):
        large_response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": f"owner/repo::file{i}.py::function{i}",
                    "score": 0.8 + (i * 0.01),
                    "location": {
                        "path": f"file{i}.py",
                        "range": {"start": {"line": i*10}, "end": {"line": i*10 + 5}}
                    },
                    "description": f"Function {i} description"
                }
                for i in range(20)
            ]
        }

        result = transform_search_response_to_json(large_response)
        data = json.loads(result)

        assert len(data["results"]) == 20

    def test_data_preservation(self):
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "CodeAlive-AI/codealive-mcp::src/tools/search.py::codebase_search",
                    "location": {
                        "path": "src/tools/search.py",
                        "range": {"start": {"line": 18}, "end": {"line": 168}}
                    },
                    "score": 0.99,
                    "description": "Main search function",
                    "contentByteSize": 8500,
                    "dataSource": {
                        "type": "repository",
                        "id": "685b21230e3822f4efa9d073",
                        "name": "codealive-mcp"
                    }
                },
                {
                    "kind": "Chunk",
                    "identifier": "CodeAlive-AI/codealive-mcp::README.md::chunk1",
                    "location": {"path": "README.md"},
                    "score": 0.85,
                    "description": "Search documentation section",
                    "dataSource": {
                        "type": "repository",
                        "id": "685b21230e3822f4efa9d073",
                        "name": "codealive-mcp"
                    }
                }
            ]
        }

        result = transform_search_response_to_json(response)
        data = json.loads(result)

        first, second = data["results"]

        assert first["path"] == "src/tools/search.py"
        assert first["startLine"] == 18
        assert first["endLine"] == 168
        assert first["kind"] == "Symbol"
        assert first["identifier"] == "CodeAlive-AI/codealive-mcp::src/tools/search.py::codebase_search"
        assert first["contentByteSize"] == 8500
        assert first["description"] == "Main search function"

        assert second["path"] == "README.md"
        assert second["kind"] == "Chunk"
        assert second["description"] == "Search documentation section"
