"""Test suite for response transformation."""

import pytest
from utils.response_transformer import (
    transform_grep_response,
    transform_search_response,
)


class TestResponseTransformer:
    """Test cases for response transformation."""

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

    def test_returns_dict(self, sample_search_response):
        """Output is a dict with results and hint."""
        result = transform_search_response(sample_search_response)

        assert isinstance(result, dict)
        assert "results" in result
        assert isinstance(result["results"], list)

    def test_includes_all_essential_fields(self, sample_search_response):
        result = transform_search_response(sample_search_response)

        first = result["results"][0]
        assert first["path"] == "path/auth.py"
        assert first["startLine"] == 10
        assert first["endLine"] == 25
        assert first["kind"] == "Symbol"
        assert first["identifier"] == "owner/repo::path/auth.py::authenticate_user"
        assert first["contentByteSize"] == 1234
        assert first["description"] == "Authenticates a user with username and password"

    def test_folders_are_skipped(self, sample_search_response):
        result = transform_search_response(sample_search_response)

        for entry in result["results"]:
            assert entry.get("kind") != "Folder"

    def test_special_chars_preserved(self):
        """Quotes and special chars are preserved as-is in the dict."""
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

        result = transform_search_response(response)
        assert result["results"][0]["description"] == 'Returns "<value>" & "other"'

    def test_unicode_preserved(self):
        """Unicode characters (e.g. Cyrillic) are preserved, not escaped."""
        response = {
            "results": [{
                "kind": "File",
                "identifier": "owner/repo::путь/файл.py",
                "location": {"path": "путь/файл.py"},
                "description": "Описание на русском языке"
            }]
        }

        result = transform_search_response(response)
        assert result["results"][0]["path"] == "путь/файл.py"
        assert result["results"][0]["description"] == "Описание на русском языке"

    def test_empty_response(self):
        result = transform_search_response({"results": []})
        assert result["results"] == []
        assert "grep_search" in result["hint"]
        assert "get_data_sources" in result["hint"]
        assert "fetch_artifacts" not in result["hint"]

    def test_no_results_key(self):
        result = transform_search_response({})
        assert result["results"] == []
        assert "grep_search" in result["hint"]
        assert "fetch_artifacts" not in result["hint"]

    def test_hint_present_in_every_response(self, sample_search_response):
        """Non-empty response carries a hint instructing the agent to load real content."""
        result = transform_search_response(sample_search_response)
        assert "hint" in result
        hint = result["hint"]
        assert "fetch_artifacts" in hint
        assert "description" in hint
        assert "Read()" in hint

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

        result = transform_search_response(response)
        assert result["results"][0]["snippet"] == "def func(): return 42"
        assert "description" not in result["results"][0]

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

        result = transform_search_response(response)
        assert result["results"][0]["description"] == "A helper function"
        assert "snippet" not in result["results"][0]

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

        result = transform_search_response(response)
        entry = result["results"][0]
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

        result = transform_search_response(response)
        paths = [entry["path"] for entry in result["results"]]
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

        result = transform_search_response(large_response)
        assert len(result["results"]) == 20

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

        result = transform_search_response(response)
        first, second = result["results"]

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

    def test_grep_transform_preserves_match_previews(self):
        response = {
            "results": [
                {
                    "kind": "File",
                    "identifier": "owner/repo::src/auth.py",
                    "location": {
                        "path": "src/auth.py",
                        "range": {"start": {"line": 15}, "end": {"line": 15}},
                    },
                    "matchCount": 2,
                    "matches": [
                        {
                            "lineNumber": 15,
                            "startColumn": 5,
                            "endColumn": 10,
                            "lineText": "auth(token)",
                        }
                    ],
                }
            ]
        }

        result = transform_grep_response(response)

        assert result["results"][0]["path"] == "src/auth.py"
        assert result["results"][0]["matchCount"] == 2
        assert result["results"][0]["matches"][0]["lineNumber"] == 15
        assert "fetch_artifacts" in result["hint"] or "Read()" in result["hint"]

    def test_grep_unicode_in_line_text(self):
        """Grep results with Unicode lineText are preserved correctly."""
        response = {
            "results": [
                {
                    "kind": "File",
                    "identifier": "owner/repo::src/module.bsl",
                    "location": {"path": "src/module.bsl"},
                    "matchCount": 1,
                    "matches": [
                        {
                            "lineNumber": 19,
                            "startColumn": 70,
                            "endColumn": 83,
                            "lineText": "\tТипШтрихкодаИВидУпаковки.ТипШтрихкода = Перечисления.ТипыШтрихкодов.GS1_DataMatrix;",
                        }
                    ],
                }
            ]
        }

        result = transform_grep_response(response)
        line = result["results"][0]["matches"][0]["lineText"]
        assert "ТипШтрихкода" in line
        assert "GS1_DataMatrix" in line

    def test_grep_forwards_matched_by_name_flag(self):
        """Name-only hits must carry matchedByName=True through to the MCP output
        so LLM agents can distinguish a file-level name match from a content match.
        Content hits must NOT include the field (backend omits null via
        JsonIgnoreCondition.WhenWritingNull; the transformer mirrors that)."""
        response = {
            "results": [
                {
                    "kind": "File",
                    "identifier": "biterp/.../Ext/Form.xml",
                    "location": {
                        "path": "bsl-checks/src/test/resources/checks/VerifyMetadata/CommonForms/Форма/Ext/Form.xml",
                        "range": {"start": {"line": 1}, "end": {"line": 1}},
                    },
                    "matchCount": 0,
                    "matches": [],
                    "matchedByName": True,
                },
                {
                    "kind": "File",
                    "identifier": "biterp/.../renames.txt",
                    "location": {"path": "renames.txt"},
                    "matchCount": 2,
                    "matches": [
                        {
                            "lineNumber": 3,
                            "startColumn": 1,
                            "endColumn": 9,
                            "lineText": "Form.xml -> Form2.xml",
                        }
                    ],
                    # matchedByName intentionally absent — backend omits it for content hits
                },
            ]
        }

        result = transform_grep_response(response)

        assert len(result["results"]) == 2
        name_only, content_hit = result["results"]
        assert name_only["matchedByName"] is True
        assert name_only["matchCount"] == 0
        assert "matches" not in name_only  # transformer only copies matches when non-empty
        assert "matchedByName" not in content_hit
        assert content_hit["matchCount"] == 2
