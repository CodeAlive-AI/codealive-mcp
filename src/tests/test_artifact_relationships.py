"""Tests for the get_artifact_relationships tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastmcp import Context
from fastmcp.exceptions import ToolError

from tools.artifact_relationships import (
    PROFILE_MAP,
    _build_relationships_dict,
    get_artifact_relationships,
)


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


class TestBuildRelationshipsDict:
    """Test dict shape of relationship responses (FastMCP handles serialization)."""

    def test_found_with_grouped_relationships(self):
        data = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "CallsOnly",
            "found": True,
            "relationships": [
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

        parsed = _build_relationships_dict(data)
        assert parsed["sourceIdentifier"] == "org/repo::path::Symbol"
        assert parsed["profile"] == "callsOnly"
        assert parsed["found"] is True

        outgoing = parsed["relationships"][0]
        assert outgoing["type"] == "outgoing_calls"
        assert outgoing["totalCount"] == 57
        assert outgoing["returnedCount"] == 50
        assert outgoing["truncated"] is True
        assert outgoing["items"][0]["filePath"] == "src/Data/Repository.cs"
        assert outgoing["items"][0]["startLine"] == 88
        assert outgoing["items"][0]["shortSummary"] == "Stores the aggregate"

        incoming = parsed["relationships"][1]
        assert incoming["type"] == "incoming_calls"
        assert incoming["truncated"] is False
        # Incoming call has no shortSummary
        assert "shortSummary" not in incoming["items"][0]

    def test_not_found_omits_relationships(self):
        data = {
            "sourceIdentifier": "org/repo::path::Missing",
            "profile": "CallsOnly",
            "found": False,
            "relationships": [],
        }

        parsed = _build_relationships_dict(data)
        assert parsed["found"] is False
        assert "relationships" not in parsed

    def test_empty_groups_still_rendered(self):
        data = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "InheritanceOnly",
            "found": True,
            "relationships": [
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

        parsed = _build_relationships_dict(data)
        types = [g["type"] for g in parsed["relationships"]]
        assert types == ["ancestors", "descendants"]
        for g in parsed["relationships"]:
            assert g["totalCount"] == 0
            assert g["items"] == []

    def test_optional_fields_omitted_when_null(self):
        data = {
            "sourceIdentifier": "org/repo::path::Symbol",
            "profile": "CallsOnly",
            "found": True,
            "relationships": [
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

        parsed = _build_relationships_dict(data)
        item = parsed["relationships"][0]["items"][0]
        assert item["identifier"] == "org/repo::path::Target"
        assert "filePath" not in item
        assert "startLine" not in item
        assert "shortSummary" not in item

    def test_quotes_and_specials_pass_through_unchanged(self):
        """Special chars (<, >, &, ") are preserved as-is in the dict — no HTML encoding."""
        data = {
            "sourceIdentifier": "org/repo::path::Class<T>",
            "profile": "CallsOnly",
            "found": True,
            "relationships": [
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

        parsed = _build_relationships_dict(data)
        assert parsed["sourceIdentifier"] == "org/repo::path::Class<T>"
        assert parsed["relationships"][0]["items"][0]["identifier"] == "org/repo::path::Method<T>"
        assert parsed["relationships"][0]["items"][0]["shortSummary"] == 'Returns "value" & more'

    def test_profile_mapped_back_to_mcp_name(self):
        """Backend profile enum names are mapped back to MCP-friendly names."""
        for mcp_name, api_name in PROFILE_MAP.items():
            data = {
                "sourceIdentifier": "id",
                "profile": api_name,
                "found": False,
                "relationships": [],
            }
            parsed = _build_relationships_dict(data)
            assert parsed["profile"] == mcp_name


class TestGetArtifactRelationshipsTool:
    """Test the async tool function."""

    @pytest.mark.asyncio
    @patch("tools.artifact_relationships.get_api_key_from_context")
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
            "relationships": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        result = await get_artifact_relationships(
            ctx=ctx,
            identifier="org/repo::path::Symbol",
        )

        # Verify the API was called with CallsOnly profile
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["profile"] == "CallsOnly"
        assert result["found"] is True

    @pytest.mark.asyncio
    @patch("tools.artifact_relationships.get_api_key_from_context")
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
            "relationships": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        await get_artifact_relationships(
            ctx=ctx,
            identifier="id",
            profile="inheritanceOnly",
        )

        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["profile"] == "InheritanceOnly"

    @pytest.mark.asyncio
    async def test_empty_identifier_raises_tool_error(self):
        ctx = MagicMock(spec=Context)
        with pytest.raises(ToolError, match="required"):
            await get_artifact_relationships(ctx=ctx, identifier="")

    @pytest.mark.asyncio
    async def test_unsupported_profile_raises_tool_error(self):
        ctx = MagicMock(spec=Context)
        with pytest.raises(ToolError, match="Unsupported profile"):
            await get_artifact_relationships(
                ctx=ctx, identifier="id", profile="invalidProfile"
            )

    @pytest.mark.asyncio
    @patch("tools.artifact_relationships.get_api_key_from_context")
    async def test_api_error_returns_error_json(self, mock_get_api_key):
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

        with pytest.raises(ToolError, match="401"):
            await get_artifact_relationships(ctx=ctx, identifier="id")

    @pytest.mark.asyncio
    @patch("tools.artifact_relationships.get_api_key_from_context")
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
            "relationships": [],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response

        mock_context = MagicMock()
        mock_context.client = mock_client
        mock_context.base_url = "https://app.codealive.ai"
        ctx.request_context.lifespan_context = mock_context

        data = await get_artifact_relationships(ctx=ctx, identifier="org/repo::path::Missing")

        assert data["found"] is False
        assert "relationships" not in data
