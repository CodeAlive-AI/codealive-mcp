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

    def test_xml_without_content(self, sample_search_response):
        """Test XML output with descriptions, identifiers, and contentByteSize."""
        result = transform_search_response_to_xml(sample_search_response)

        assert isinstance(result, str)
        assert result.startswith("<results>")
        assert result.endswith("</results>")

        assert "<search_result" in result

        # Should include path, line numbers, kind attributes
        assert 'path="path/auth.py"' in result
        assert 'startLine="10"' in result
        assert 'endLine="25"' in result
        assert 'kind="Symbol"' in result

        # Should include identifier attributes
        assert 'identifier="owner/repo::path/auth.py::authenticate_user"' in result
        assert 'identifier="owner/repo::config/security.py::AUTH_PROVIDERS"' in result

        # Should include contentByteSize attributes
        assert 'contentByteSize="1234"' in result
        assert 'contentByteSize="456"' in result

        # Should include description as child element
        assert "<description>" in result
        assert "Authenticates a user with username and password" in result
        assert "List of configured authentication providers" in result

        # Should NOT include folders
        assert 'auth/' not in result or 'identifier="owner/repo::path/auth.py' in result
        assert 'kind="Folder"' not in result

    def test_description_renders_as_child_element(self):
        """Test that description is rendered as a child element, not self-closing."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::file.py::func",
                    "location": {
                        "path": "file.py",
                        "range": {"start": {"line": 1}, "end": {"line": 5}}
                    },
                    "description": "A helper function",
                    "contentByteSize": 200
                }
            ]
        }

        result = transform_search_response_to_xml(response)

        # Should have opening and closing search_result tags (not self-closing)
        assert "<search_result " in result
        assert "</search_result>" in result
        assert "<description>A helper function</description>" in result

    def test_no_description_uses_self_closing_tag(self):
        """Test that results without description use self-closing tags."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::file.py::func",
                    "location": {
                        "path": "file.py",
                        "range": {"start": {"line": 1}, "end": {"line": 5}}
                    }
                }
            ]
        }

        result = transform_search_response_to_xml(response)

        assert "/>" in result
        assert "<description>" not in result

    def test_identifier_in_attributes(self):
        """Test that identifier is included as an XML attribute."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "CodeAlive-AI/backend::src/auth.py::login",
                    "location": {
                        "path": "src/auth.py",
                        "range": {"start": {"line": 10}, "end": {"line": 20}}
                    }
                }
            ]
        }

        result = transform_search_response_to_xml(response)
        assert 'identifier="CodeAlive-AI/backend::src/auth.py::login"' in result

    def test_content_byte_size_in_attributes(self):
        """Test that contentByteSize is included as an XML attribute."""
        response = {
            "results": [
                {
                    "kind": "File",
                    "identifier": "owner/repo::large_file.py",
                    "location": {"path": "large_file.py"},
                    "contentByteSize": 98765
                }
            ]
        }

        result = transform_search_response_to_xml(response)
        assert 'contentByteSize="98765"' in result

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
                "description": 'Returns "<value>" & "other"'
            }]
        }

        result = transform_search_response_to_xml(response)

        # XML special chars should be escaped in description
        assert "&lt;value&gt;" in result
        assert "&amp;" in result
        # But structural XML should not be escaped
        assert "<search_result" in result
        assert "</results>" in result

    def test_empty_response(self):
        """Test handling of empty search results."""
        result = transform_search_response_to_xml({"results": []})

        assert result == "<results></results>" or result == "<results/>"

    def test_multiple_symbols_same_file(self):
        """Test multiple symbols from the same file produce separate entries."""
        response = {
            "results": [
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::utils.py::func1",
                    "location": {
                        "path": "utils.py",
                        "range": {"start": {"line": 10}, "end": {"line": 20}}
                    },
                    "description": "First function"
                },
                {
                    "kind": "Symbol",
                    "identifier": "owner/repo::utils.py::func2",
                    "location": {
                        "path": "utils.py",
                        "range": {"start": {"line": 25}, "end": {"line": 35}}
                    },
                    "description": "Second function"
                }
            ]
        }

        result = transform_search_response_to_xml(response)

        # Should have two separate search_result tags
        assert result.count("<search_result") == 2
        assert "First function" in result
        assert "Second function" in result

    def test_performance_large_response(self):
        """Test that XML format is compact for large responses."""
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

        xml_result = transform_search_response_to_xml(large_response)

        assert xml_result.count("<search_result") == 20

    def test_preserves_server_order(self):
        """Test that the transformer preserves the order from the server."""
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

        result = transform_search_response_to_xml(response)

        lines = result.split('\n')

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

        assert important_line < less_important_line
        assert less_important_line < another_line

    def test_data_preservation_without_content(self):
        """Test that all essential data is preserved."""
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

        result = transform_search_response_to_xml(response)

        # Verify paths
        assert 'path="src/tools/search.py"' in result
        assert 'path="README.md"' in result

        # Verify line numbers
        assert 'startLine="18"' in result
        assert 'endLine="168"' in result

        # Verify kinds
        assert 'kind="Symbol"' in result
        assert 'kind="Chunk"' in result

        # Verify identifiers
        assert 'identifier="CodeAlive-AI/codealive-mcp::src/tools/search.py::codebase_search"' in result

        # Verify contentByteSize
        assert 'contentByteSize="8500"' in result

        # Verify descriptions
        assert "Main search function" in result
        assert "Search documentation section" in result
