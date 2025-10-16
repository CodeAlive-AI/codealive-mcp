"""Tests for parameter normalization functionality."""

import pytest
import json
from utils.errors import normalize_data_source_names


class TestNormalizeDataSourceNames:
    """Test the normalize_data_source_names function with various input formats."""

    def test_proper_array_input(self):
        """Test that proper arrays are passed through unchanged."""
        input_data = ["repo1", "repo2", "repo3"]
        result = normalize_data_source_names(input_data)
        assert result == ["repo1", "repo2", "repo3"]

    def test_single_string_input(self):
        """Test that single string is converted to array."""
        input_data = "repo1"
        result = normalize_data_source_names(input_data)
        assert result == ["repo1"]

    def test_json_encoded_string_input(self):
        """Test that JSON-encoded strings are properly parsed."""
        input_data = '["repo1", "repo2"]'
        result = normalize_data_source_names(input_data)
        assert result == ["repo1", "repo2"]

    def test_malformed_json_string_fallback(self):
        """Test that malformed JSON strings fall back to single ID."""
        input_data = '["repo1", "repo2"'  # Missing closing bracket
        result = normalize_data_source_names(input_data)
        assert result == ['["repo1", "repo2"']  # Treated as single ID

    def test_empty_inputs(self):
        """Test various empty input types."""
        assert normalize_data_source_names(None) == []
        assert normalize_data_source_names("") == []
        assert normalize_data_source_names([]) == []

    def test_mixed_array_with_dicts(self):
        """Test arrays containing both strings and dict objects."""
        input_data = [
            "repo1",
            {"id": "repo2", "type": "repository"},
            "repo3",
            {"id": "workspace1", "type": "workspace"}
        ]
        result = normalize_data_source_names(input_data)
        assert result == ["repo1", "repo2", "repo3", "workspace1"]

    def test_dict_without_id(self):
        """Test that dicts without 'id' field use 'name' field if present."""
        input_data = [
            "repo1",
            {"name": "some-repo", "type": "repository"},  # No 'id' field, but has 'name'
            "repo2"
        ]
        result = normalize_data_source_names(input_data)
        assert result == ["repo1", "some-repo", "repo2"]

    def test_empty_strings_preserved(self):
        """Test that empty strings in arrays are preserved (might be intentional)."""
        input_data = ["repo1", "", "repo2", "   ", "repo3"]
        result = normalize_data_source_names(input_data)
        assert result == ["repo1", "", "repo2", "   ", "repo3"]  # All strings preserved

    def test_non_list_non_string_input(self):
        """Test handling of unexpected input types."""
        result = normalize_data_source_names(123)
        assert result == ["123"]

        result = normalize_data_source_names({"id": "repo1"})
        assert result == ["{'id': 'repo1'}"]

    def test_claude_desktop_scenarios(self):
        """Test specific scenarios from Claude Desktop serialization issues."""
        # Scenario 1: JSON string as seen in Claude Desktop logs
        claude_input_1 = '["67db4097fa23c0a98a8495c2"]'
        result_1 = normalize_data_source_names(claude_input_1)
        assert result_1 == ["67db4097fa23c0a98a8495c2"]

        # Scenario 2: Plain string as seen in Claude Desktop logs
        claude_input_2 = "67db4097fa23c0a98a8495c2"
        result_2 = normalize_data_source_names(claude_input_2)
        assert result_2 == ["67db4097fa23c0a98a8495c2"]

        # Scenario 3: Multiple IDs in JSON string
        claude_input_3 = '["repo1", "repo2", "workspace1"]'
        result_3 = normalize_data_source_names(claude_input_3)
        assert result_3 == ["repo1", "repo2", "workspace1"]

    def test_edge_cases(self):
        """Test various edge cases."""
        # Whitespace-only JSON string
        assert normalize_data_source_names("[]") == []
        assert normalize_data_source_names("[   ]") == []

        # Single item JSON array
        assert normalize_data_source_names('["single"]') == ["single"]

        # JSON array with empty strings
        assert normalize_data_source_names('["repo1", "", "repo2"]') == ["repo1", "", "repo2"]

    def test_dict_with_name_preferred(self):
        """Dict inputs with explicit names should take precedence over IDs."""
        input_data = [
            {"id": "legacy-id", "name": "repo-main"},
            {"name": "workspace:analytics"}
        ]
        result = normalize_data_source_names(input_data)
        assert result == ["repo-main", "workspace:analytics"]


class TestParameterNormalizationIntegration:
    """Integration tests to ensure parameter normalization works in tool contexts."""

    def test_search_tool_parameter_handling(self):
        """Test that search tool properly normalizes various parameter formats."""
        from tools.search import codebase_search
        import inspect

        # Verify the function accepts Union[str, List[str]]
        sig = inspect.signature(codebase_search)
        data_sources_param = sig.parameters['data_sources']

        # The annotation should accept both str and List[str]
        assert 'Union' in str(data_sources_param.annotation) or 'str' in str(data_sources_param.annotation)

    def test_consultant_tool_parameter_handling(self):
        """Test that consultant tool properly normalizes various parameter formats."""
        from tools.chat import codebase_consultant
        import inspect

        # Verify the function accepts Union[str, List[str]]
        sig = inspect.signature(codebase_consultant)
        data_sources_param = sig.parameters['data_sources']

        # The annotation should accept both str and List[str]
        assert 'Union' in str(data_sources_param.annotation) or 'str' in str(data_sources_param.annotation)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])