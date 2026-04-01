"""Tests for the get_artifact_relations tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastmcp import Context

from tools.artifact_relations import get_artifact_relations, _build_relations_xml, PROFILE_MAP


class TestProfileMapping:
    """Test MCP profile names map to backend enum values."""

    def test_default_profile_is_calls_only(self):
        """callsOnly is the default and maps to CallsOnly."""
        assert PROFILE_MAP["callsOnly"] == "CallsOnly"

    def test_inheritance_only_maps_correctly(self):
        assert PROFILE_MAP["inheritanceOnly"] == "InheritanceOnly"

    def test_all_relevant_maps_correctly(self):
        assert PROFILE_MAP["allRelevant"] == "AllRelevant"

    def test_references_only_maps_correctly(self):
        assert PROFILE_MAP["referencesOnly"] == "ReferencesOnly"


class TestBuildRelationsXml:
    """Test XML rendering of relation responses."""

    def test_found_with_grouped_relations(self):
        data = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "CallsOnly",
            "found": True,
            "relations": [
                {
                    "relationType": "OutgoingCalls",
                    "totalCount": 57,
                    "returnedCount": 50,
                    "truncated": True,
                    "items": [
                        {
                            "identifier": "org/repo::path::Dep",
                            "filePath": "src/Data/Repository.cs",
                            "startLine": 88,
                            "shortSummary": "Stores the aggregate",
                        }
                    ],
                },
                {
                    "relationType": "IncomingCalls",
                    "totalCount": 3,
                    "returnedCount": 3,
                    "truncated": False,
                    "items": [
                        {
                            "identifier": "org/repo::path::Caller",
                            "filePath": "src/Services/Worker.cs",
                            "startLine": 142,
                        }
                    ],
                },
            ],
        }

        result = _build_relations_xml(data)

        assert 'sourceIdentifier="org/repo::path::Symbol"' in result
        assert 'profile="callsOnly"' in result
        assert 'found="true"' in result
        assert 'type="outgoing_calls"' in result
        assert 'totalCount="57"' in result
        assert 'returnedCount="50"' in result
        assert 'truncated="true"' in result
        assert 'filePath="src/Data/Repository.cs"' in result
        assert 'startLine="88"' in result
        assert 'shortSummary="Stores the aggregate"' in result
        assert 'type="incoming_calls"' in result
        assert 'truncated="false"' in result
        # Incoming call has no shortSummary
        assert result.count("shortSummary") == 1

    def test_not_found_renders_self_closing(self):
        data = {
            "sourceIdentifier": "org/repo::path::Missing",
            "profile": "CallsOnly",
            "found": False,
            "relations": [],
        }

        result = _build_relations_xml(data)

        assert 'found="false"' in result
        assert result.endswith("/>")
        assert "<relation_group" not in result

    def test_empty_group_still_rendered(self):
        data = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "InheritanceOnly",
            "found": True,
            "relations": [
                {
                    "relationType": "Ancestors",
                    "totalCount": 0,
                    "returnedCount": 0,
                    "truncated": False,
                    "items": [],
                },
                {
                    "relationType": "Descendants",
                    "totalCount": 0,
                    "returnedCount": 0,
                    "truncated": False,
                    "items": [],
                },
            ],
        }

        result = _build_relations_xml(data)

        assert 'type="ancestors"' in result
        assert 'type="descendants"' in result
        assert 'totalCount="0"' in result

    def test_optional_fields_omitted_when_null(self):
        data = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "CallsOnly",
            "found": True,
            "relations": [
                {
                    "relationType": "OutgoingCalls",
                    "totalCount": 1,
                    "returnedCount": 1,
                    "truncated": False,
                    "items": [
                        {
                            "identifier": "org/repo::path::Target",
                            # filePath, startLine, shortSummary all absent
                        }
                    ],
                },
            ],
        }

        result = _build_relations_xml(data)

        assert 'identifier="org/repo::path::Target"' in result
        assert "filePath" not in result
        assert "startLine" not in result
        assert "shortSummary" not in result

    def test_html_entities_escaped(self):
        data = {
            "sourceIdentifier": "org/repo::path::Class<T>",
            "profile": "CallsOnly",
            "found": True,
            "relations": [
                {
                    "relationType": "OutgoingCalls",
                    "totalCount": 1,
                    "returnedCount": 1,
                    "truncated": False,
                    "items": [
                        {
                            "identifier": "org/repo::path::Method<T>",
                            "shortSummary": 'Returns "value" & more',
                        }
                    ],
                },
            ],
        }

        result = _build_relations_xml(data)

        assert "Class&lt;T&gt;" in result
        assert "Method&lt;T&gt;" in result
        assert "&amp;" in result
        assert "&quot;" in result

    def test_profile_mapped_back_to_mcp_name(self):
        """Backend profile enum names are mapped back to MCP-friendly names."""
        for mcp_name, api_name in PROFILE_MAP.items():
            data = {
                "sourceIdentifier": "id",
                "profile": api_name,
                "found": False,
                "relations": [],
            }
            result = _build_relations_xml(data)
            assert f'profile="{mcp_name}"' in result


class TestGetArtifactRelationsTool:
    """Test the async tool function."""

    @pytest.mark.asyncio
    @patch("tools.artifact_relations.get_api_key_from_context")
    async def test_default_profile_sends_calls_only(self, mock_get_api_key):
        mock_get_api_key.return_value = "test_key"

        ctx = MagicMock(spec=Context)
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "CallsOnly",
            "found": True,
            "relations": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        result = await get_artifact_relations(
            ctx=ctx,
            identifier="org/repo::path::Symbol",
        )

        # Verify the API was called with CallsOnly profile
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["profile"] == "CallsOnly"
        assert 'found="true"' in result

    @pytest.mark.asyncio
    @patch("tools.artifact_relations.get_api_key_from_context")
    async def test_explicit_profile_maps_correctly(self, mock_get_api_key):
        mock_get_api_key.return_value = "test_key"

        ctx = MagicMock(spec=Context)
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sourceIdentifier": "id",
            "profile": "InheritanceOnly",
            "found": True,
            "relations": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        await get_artifact_relations(
            ctx=ctx,
            identifier="id",
            profile="inheritanceOnly",
        )

        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["profile"] == "InheritanceOnly"

    @pytest.mark.asyncio
    async def test_empty_identifier_returns_error(self):
        ctx = MagicMock(spec=Context)
        result = await get_artifact_relations(ctx=ctx, identifier="")
        assert "<error>" in result
        assert "required" in result

    @pytest.mark.asyncio
    async def test_unsupported_profile_returns_error(self):
        ctx = MagicMock(spec=Context)
        result = await get_artifact_relations(
            ctx=ctx, identifier="id", profile="invalidProfile"
        )
        assert "<error>" in result
        assert "Unsupported profile" in result

    @pytest.mark.asyncio
    @patch("tools.artifact_relations.get_api_key_from_context")
    async def test_api_error_returns_error_xml(self, mock_get_api_key):
        import httpx

        mock_get_api_key.return_value = "test_key"

        ctx = MagicMock(spec=Context)
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        result = await get_artifact_relations(ctx=ctx, identifier="id")

        assert "<error>" in result
        assert "401" in result

    @pytest.mark.asyncio
    @patch("tools.artifact_relations.get_api_key_from_context")
    async def test_not_found_response_renders_correctly(self, mock_get_api_key):
        mock_get_api_key.return_value = "test_key"

        ctx = MagicMock(spec=Context)
        ctx.info = AsyncMock()
        ctx.error = AsyncMock()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "sourceIdentifier": "org/repo::path::Missing",
            "profile": "CallsOnly",
            "found": False,
            "relations": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        result = await get_artifact_relations(ctx=ctx, identifier="org/repo::path::Missing")

        assert 'found="false"' in result
        assert "<relation_group" not in result
