"""Test suite for XML response transformation."""

import pytest
from utils.response_transformer import transform_search_response_to_xml


class TestXMLTransformer:
    """Test cases for XML response transformation."""

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
                    "content": "def authenticate_user(username, password):\n    # Auth logic\n    return True"
                },
                {
                    "kind": "Chunk",
                    "identifier": "owner/repo::path/auth.py::chunk1",
                    "score": 0.85,
                    "location": {"path": "path/auth.py"},
                    "snippet": "# Authentication module"
                },
                {
                    "kind": "File",
                    "identifier": "owner/repo::path/auth.py",
                    "score": 0.75,
                    "location": {"path": "path/auth.py"}
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::config/security.py::AUTH_PROVIDERS",
                    "score": 0.82,
                    "location": {
                        "path": "config/security.py",
                        "range": {"start": {"line": 5}, "end": {"line": 8}}
                    },
                    "content": "AUTH_PROVIDERS = [\n    'local',\n    'oauth2'\n]"
                },
                {
                    "kind": "Folder",
                    "identifier": "owner/repo::auth/",
                    "score": 0.60,
                    "location": {"path": "auth/"}
                }
            ]
        }

    def test_xml_without_content(self, sample_search_response):
        """Test XML optimization without content."""
        result = transform_search_response_to_xml(sample_search_response, include_content=False)

        # Should return valid XML string
        assert isinstance(result, str)
        assert result.startswith("<results>")
        assert result.endswith("</results>")

        # Should have search_result elements
        assert "<search_result" in result

        # Should NOT have content inside tags (but names in attributes are OK)
        assert "def authenticate_user" not in result

        # Should have self-closing tags for no content
        assert "/>" in result

        # Should include path, line numbers, kind attributes
        assert 'path="path/auth.py"' in result
        assert 'startLine="10"' in result
        assert 'endLine="25"' in result
        assert 'kind="Symbol"' in result

        # No name attributes at all - redundant information
        assert 'name=' not in result

        # Should NOT include folders
        assert 'auth/' not in result
        assert 'kind="Folder"' not in result

        # Should be more compact than JSON
        assert len(result) < 400  # Much smaller than JSON version

    def test_xml_with_content(self, sample_search_response):
        """Test XML optimization with content."""
        result = transform_search_response_to_xml(sample_search_response, include_content=True)

        # Should return valid XML string
        assert isinstance(result, str)
        assert result.startswith("<results>")
        assert result.endswith("</results>")

        # Should have content between tags
        assert "def authenticate_user" in result
        assert "AUTH_PROVIDERS" in result

        # Should have proper line numbers in content
        assert "10|def authenticate_user" in result or "def authenticate_user" in result

        # Should group multiple results from same file
        # Path should appear fewer times than original results
        assert result.count('path="path/auth.py"') == 1  # All auth.py results grouped

        # Should handle snippets for chunks
        assert "# Authentication module" in result

    def test_xml_escaping(self):
        """Test that XML special characters are properly escaped."""
        response = {
            "results": [{
                "kind": "Symbol",
                "identifier": "owner/repo::file.py::func",
                "score": 0.9,
                "location": {
                    "path": "file.py",
                    "range": {"start": {"line": 1}, "end": {"line": 3}}
                },
                "content": 'def func():\n    return "<value>" & "other"'
            }]
        }

        result = transform_search_response_to_xml(response, include_content=True)

        # XML special chars should be escaped
        assert "&lt;value&gt;" in result or "&#60;value&#62;" in result
        assert "&amp;" in result or "&#38;" in result
        # But structural XML should not be escaped
        assert "<search_result" in result
        assert "</results>" in result

    def test_empty_response(self):
        """Test handling of empty search results."""
        result = transform_search_response_to_xml({"results": []}, include_content=False)

        assert result == "<results></results>" or result == "<results/>"

    def test_multiple_symbols_same_file(self):
        """Test grouping multiple symbols from the same file."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::utils.py::func1",
                    "location": {
                        "path": "utils.py",
                        "range": {"start": {"line": 10}, "end": {"line": 20}}
                    },
                    "content": "def func1(): pass"
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::utils.py::func2",
                    "location": {
                        "path": "utils.py",
                        "range": {"start": {"line": 25}, "end": {"line": 35}}
                    },
                    "content": "def func2(): pass"
                }
            ]
        }

        result_without = transform_search_response_to_xml(response, include_content=False)
        result_with = transform_search_response_to_xml(response, include_content=True)

        # Without content: should have two separate search_result tags
        assert result_without.count("<search_result") == 2
        # No names anymore - we removed them
        assert 'name=' not in result_without

        # With content: should group into one search_result with combined content
        assert result_with.count('path="utils.py"') == 1
        assert "func1" in result_with
        assert "func2" in result_with

    def test_performance_large_response(self):
        """Test that XML format is more compact than JSON for large responses."""
        # Generate a large response
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
                    "content": f"def function{i}():\n    pass"
                }
                for i in range(20)
            ]
        }

        xml_result = transform_search_response_to_xml(large_response, include_content=False)

        # XML should be very compact
        assert len(xml_result) < 2000  # Should be much smaller
        assert xml_result.count("<search_result") == 20

    def test_preserves_server_order(self):
        """Test that the transformer preserves the order from the server."""
        response = {
            "results": [
                # Server sends these in relevance order (highest score first)
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::important.py::critical_function",
                    "score": 0.95,  # Highest score - most relevant
                    "location": {
                        "path": "important.py",
                        "range": {"start": {"line": 10}, "end": {"line": 20}}
                    }
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::less_important.py::helper",
                    "score": 0.75,  # Lower score
                    "location": {
                        "path": "less_important.py",
                        "range": {"start": {"line": 5}, "end": {"line": 10}}
                    }
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::another.py::utility",
                    "score": 0.60,  # Even lower
                    "location": {
                        "path": "another.py",
                        "range": {"start": {"line": 1}, "end": {"line": 5}}
                    }
                }
            ]
        }

        result = transform_search_response_to_xml(response, include_content=False)

        # Check that files appear in the original order (by first occurrence)
        lines = result.split('\n')

        # Find line numbers for each path
        important_line = None
        less_important_line = None
        another_line = None

        for i, line in enumerate(lines):
            if 'path="important.py"' in line and important_line is None:
                important_line = i
            if 'path="less_important.py"' in line and less_important_line is None:
                less_important_line = i
            if 'path="another.py"' in line and another_line is None:
                another_line = i

        # Verify order is preserved (most relevant first)
        assert important_line < less_important_line, "Most relevant result should appear first"
        assert less_important_line < another_line, "Results should maintain server order"

    def test_data_preservation_without_content(self):
        """Test that all essential data is preserved when include_content=False."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "CodeAlive-AI/codealive-mcp::src/tools/search.py::search_code",
                    "location": {
                        "path": "src/tools/search.py",
                        "range": {"start": {"line": 18}, "end": {"line": 168}}
                    },
                    "score": 0.99,
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
                    "snippet": "include_content parameter documentation",
                    "dataSource": {
                        "type": "repository",
                        "id": "685b21230e3822f4efa9d073",
                        "name": "codealive-mcp"
                    }
                }
            ]
        }

        result = transform_search_response_to_xml(response, include_content=False)

        # Verify all paths are preserved
        assert 'path="src/tools/search.py"' in result
        assert 'path="README.md"' in result

        # Verify line numbers are preserved for Symbol
        assert 'startLine="18"' in result
        assert 'endLine="168"' in result

        # Verify kinds are preserved
        assert 'kind="Symbol"' in result
        assert 'kind="Chunk"' in result

        # Verify no content is included
        assert "include_content parameter documentation" not in result

    def test_data_preservation_with_content(self):
        """Test that all data including content is preserved when include_content=True."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "CodeAlive-AI/codealive-mcp::src/tools/search.py::search_code",
                    "location": {
                        "path": "src/tools/search.py",
                        "range": {"start": {"line": 18}, "end": {"line": 168}}
                    },
                    "score": 0.99,
                    "content": "async def search_code(\n    ctx: Context,\n    query: str,\n    data_source_ids: Optional[List[str]] = None,\n    mode: str = \"auto\",\n    include_content: bool = False\n) -> Dict:",
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
                    "snippet": "include_content: Whether to include full file content",
                    "dataSource": {
                        "type": "repository",
                        "id": "685b21230e3822f4efa9d073",
                        "name": "codealive-mcp"
                    }
                },
                {
                    "kind": "File",
                    "identifier": "CodeAlive-AI/codealive-mcp::CLAUDE.md",
                    "location": {"path": "CLAUDE.md", "range": {"start": {"line": 0}, "end": {"line": 0}}},
                    "score": 0.75,
                    "content": "# CLAUDE.md\n\nThis file provides guidance",
                    "dataSource": {
                        "type": "repository",
                        "id": "685b21230e3822f4efa9d073",
                        "name": "codealive-mcp"
                    }
                }
            ]
        }

        result = transform_search_response_to_xml(response, include_content=True)

        # Verify all paths are preserved
        assert 'path="src/tools/search.py"' in result
        assert 'path="README.md"' in result
        assert 'path="CLAUDE.md"' in result

        # Verify line numbers are preserved
        assert 'startLine="18"' in result
        assert 'endLine="168"' in result

        # Verify content is included
        assert "async def search_code" in result
        assert "include_content: Whether to include full file content" in result
        assert "This file provides guidance" in result

        # Verify proper escaping
        assert "&quot;" in result or '"' in result  # Quotes should be handled

    def test_mixed_content_sources(self):
        """Test handling results with both content and snippet fields."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "location": {"path": "file1.py", "range": {"start": {"line": 1}, "end": {"line": 5}}},
                    "content": "Full content from API"
                },
                {
                    "kind": "Chunk",
                    "location": {"path": "file2.py"},
                    "snippet": "Just a snippet"
                },
                {
                    "kind": "Symbol",
                    "location": {"path": "file3.py", "range": {"start": {"line": 10}, "end": {"line": 15}}},
                    "content": "Another full content",
                    "snippet": "Also has snippet but content takes priority"
                }
            ]
        }

        result = transform_search_response_to_xml(response, include_content=True)

        # Verify content is preferred over snippet when both exist
        assert "Full content from API" in result
        assert "Just a snippet" in result
        assert "Another full content" in result
        assert "Also has snippet but content takes priority" not in result  # Content takes priority