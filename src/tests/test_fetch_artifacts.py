"""Test suite for fetch_artifacts tool."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context
from tools.fetch_artifacts import fetch_artifacts, _add_line_numbers, _build_artifacts_xml


class TestAddLineNumbers:
    """Test cases for _add_line_numbers helper."""

    def test_multi_line_content(self):
        content = "line1\nline2\nline3"
        result = _add_line_numbers(content)
        assert result == "1 | line1\n2 | line2\n3 | line3"

    def test_single_line_content(self):
        content = "only one line"
        result = _add_line_numbers(content)
        assert result == "1 | only one line"

    def test_empty_content(self):
        assert _add_line_numbers("") == ""

    def test_right_aligned_padding(self):
        lines = "\n".join(f"line{i}" for i in range(100))
        result = _add_line_numbers(lines)
        first_line = result.split("\n")[0]
        assert first_line == "  1 | line0"
        last_line = result.split("\n")[99]
        assert last_line == "100 | line99"

    def test_start_line_offset(self):
        result = _add_line_numbers("a\nb", start_line=50)
        assert result == "50 | a\n51 | b"

    def test_start_line_default(self):
        result = _add_line_numbers("x", start_line=1)
        assert result == "1 | x"

    def test_start_line_right_aligned_padding(self):
        result = _add_line_numbers("a\nb\nc", start_line=98)
        assert result == " 98 | a\n 99 | b\n100 | c"

    def test_start_line_empty_content(self):
        assert _add_line_numbers("", start_line=50) == ""


class TestBuildArtifactsXmlStartLine:
    """Test _build_artifacts_xml uses startLine from API response."""

    def test_artifact_with_start_line(self):
        data = {"artifacts": [
            {"identifier": "repo::file.py::func", "content": "line1\nline2", "contentByteSize": 10, "startLine": 50}
        ]}
        result = _build_artifacts_xml(data)
        assert "50 | line1" in result
        assert "51 | line2" in result

    def test_artifact_without_start_line_defaults_to_1(self):
        data = {"artifacts": [
            {"identifier": "repo::file.py::func", "content": "line1\nline2", "contentByteSize": 10}
        ]}
        result = _build_artifacts_xml(data)
        assert "1 | line1" in result
        assert "2 | line2" in result

    def test_artifact_with_null_start_line_defaults_to_1(self):
        data = {"artifacts": [
            {"identifier": "repo::file.py", "content": "hello", "contentByteSize": 5, "startLine": None}
        ]}
        result = _build_artifacts_xml(data)
        assert "1 | hello" in result


class TestBuildArtifactsXmlContentWrapper:
    """Test that content is wrapped in <content> element."""

    def test_content_wrapped_in_element(self):
        data = {"artifacts": [
            {"identifier": "repo::file.py::func", "content": "code here", "contentByteSize": 9}
        ]}
        result = _build_artifacts_xml(data)
        assert "<content>" in result
        assert "</content>" in result
        assert "<content>1 | code here</content>" in result

    def test_artifact_structure_has_content_child(self):
        data = {"artifacts": [
            {"identifier": "repo::f.py::fn", "content": "x = 1", "contentByteSize": 5}
        ]}
        result = _build_artifacts_xml(data)
        assert "<artifact" in result
        assert "</artifact>" in result
        assert "<content>" in result


class TestBuildArtifactsXmlRelationships:
    """Test relationships rendering in _build_artifacts_xml."""

    def test_relationships_with_outgoing_and_incoming(self):
        data = {"artifacts": [{
            "identifier": "repo::src/a.ts::FuncA",
            "content": "code",
            "contentByteSize": 4,
            "relationships": {
                "outgoingCallsCount": 12,
                "outgoingCalls": [
                    {"identifier": "repo::src/b.ts::FuncB", "summary": "Validates token"},
                    {"identifier": "repo::src/c.ts::FuncC", "summary": "Logs event"},
                ],
                "incomingCallsCount": 3,
                "incomingCalls": [
                    {"identifier": "repo::src/d.ts::FuncD", "summary": "Entry point"},
                ],
            }
        }]}
        result = _build_artifacts_xml(data)
        assert "<relationships>" in result
        assert '</relationships>' in result
        assert '<outgoing_calls count="12">' in result
        assert '</outgoing_calls>' in result
        assert '<incoming_calls count="3">' in result
        assert '</incoming_calls>' in result
        assert 'identifier="repo::src/b.ts::FuncB" summary="Validates token"' in result
        assert 'identifier="repo::src/d.ts::FuncD" summary="Entry point"' in result

    def test_relationships_with_only_outgoing(self):
        data = {"artifacts": [{
            "identifier": "repo::src/a.ts::FuncA",
            "content": "code",
            "contentByteSize": 4,
            "relationships": {
                "outgoingCallsCount": 2,
                "outgoingCalls": [
                    {"identifier": "repo::src/b.ts::FuncB", "summary": "Does stuff"},
                ],
                "incomingCallsCount": None,
                "incomingCalls": None,
            }
        }]}
        result = _build_artifacts_xml(data)
        assert "<relationships>" in result
        assert "<outgoing_calls" in result
        assert "<incoming_calls" not in result

    def test_relationships_null_omits_relationships_element(self):
        data = {"artifacts": [{
            "identifier": "repo::src/a.ts",
            "content": "code",
            "contentByteSize": 4,
            "relationships": None,
        }]}
        result = _build_artifacts_xml(data)
        assert "<relationships>" not in result
        assert "<content>" in result

    def test_relationships_absent_omits_relationships_element(self):
        data = {"artifacts": [{
            "identifier": "repo::src/a.ts",
            "content": "code",
            "contentByteSize": 4,
        }]}
        result = _build_artifacts_xml(data)
        assert "<relationships>" not in result

    def test_relationships_call_without_summary_omits_summary_attr(self):
        data = {"artifacts": [{
            "identifier": "repo::src/a.ts::FuncA",
            "content": "code",
            "contentByteSize": 4,
            "relationships": {
                "outgoingCallsCount": 1,
                "outgoingCalls": [
                    {"identifier": "repo::src/b.ts::FuncB", "summary": None},
                ],
                "incomingCallsCount": None,
                "incomingCalls": None,
            }
        }]}
        result = _build_artifacts_xml(data)
        assert 'identifier="repo::src/b.ts::FuncB"/>' in result
        assert 'summary' not in result.split('FuncB')[1].split('/>')[0]

    def test_relationships_escapes_xml_in_summary(self):
        data = {"artifacts": [{
            "identifier": "repo::src/a.ts::FuncA",
            "content": "code",
            "contentByteSize": 4,
            "relationships": {
                "outgoingCallsCount": 1,
                "outgoingCalls": [
                    {"identifier": "repo::src/b.ts::FuncB", "summary": 'Checks if x < 10 & y > 5'},
                ],
                "incomingCallsCount": None,
                "incomingCalls": None,
            }
        }]}
        result = _build_artifacts_xml(data)
        assert "&lt;" in result
        assert "&amp;" in result


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_returns_xml(mock_get_api_key):
    """Test that fetch_artifacts returns properly formatted XML."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "artifacts": [
            {
                "identifier": "owner/repo::src/auth.py::login",
                "content": "def login(user, pwd):\n    return True",
                "contentByteSize": 38
            },
            {
                "identifier": "owner/repo::src/missing.py::func",
                "content": None,
                "contentByteSize": None
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await fetch_artifacts(
        ctx=ctx,
        identifiers=["owner/repo::src/auth.py::login", "owner/repo::src/missing.py::func"],
    )

    assert isinstance(result, str)
    assert "<artifacts>" in result
    assert "</artifacts>" in result
    # Found artifact has line-numbered content wrapped in <content>
    assert "<content>" in result
    assert "1 | def login(user, pwd):" in result
    assert "2 |     return True" in result
    assert 'contentByteSize="38"' in result
    assert 'identifier="owner/repo::src/auth.py::login"' in result
    # Not-found artifact is skipped (not in output)
    assert "missing.py" not in result


@pytest.mark.asyncio
async def test_fetch_artifacts_empty_identifiers():
    """Test that empty identifiers list returns an error."""
    ctx = MagicMock(spec=Context)

    result = await fetch_artifacts(ctx=ctx, identifiers=[])

    assert "<error>" in result
    assert "At least one identifier" in result


@pytest.mark.asyncio
async def test_fetch_artifacts_exceeds_max_identifiers():
    """Test that more than 20 identifiers returns an error."""
    ctx = MagicMock(spec=Context)

    identifiers = [f"owner/repo::file{i}.py::func{i}" for i in range(21)]

    result = await fetch_artifacts(ctx=ctx, identifiers=identifiers)

    assert "<error>" in result
    assert "Maximum 20" in result


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_posts_correct_body(mock_get_api_key):
    """Test that fetch_artifacts sends the correct POST body."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"artifacts": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    await fetch_artifacts(
        ctx=ctx,
        identifiers=["id1", "id2"],
    )

    call_args = mock_client.post.call_args
    assert call_args.args[0] == "/api/search/artifacts"
    body = call_args.kwargs["json"]
    assert body["identifiers"] == ["id1", "id2"]
    assert "names" not in body


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_api_error(mock_get_api_key):
    """Test that API errors are handled gracefully."""
    import httpx

    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"

    def raise_500():
        raise httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=mock_response
        )

    mock_response.raise_for_status = raise_500

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await fetch_artifacts(
        ctx=ctx,
        identifiers=["some-id"],
    )

    assert isinstance(result, str)
    assert "<error>" in result


@pytest.mark.asyncio
@patch('tools.fetch_artifacts.get_api_key_from_context')
async def test_fetch_artifacts_escapes_xml(mock_get_api_key):
    """Test that content with XML special characters is properly escaped."""
    mock_get_api_key.return_value = "test_key"

    ctx = MagicMock(spec=Context)
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "artifacts": [
            {
                "identifier": "owner/repo::file.py::func",
                "content": 'if x < 10 && y > 5:\n    return "<ok>"',
                "contentByteSize": 40
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    mock_codealive_context = MagicMock()
    mock_codealive_context.client = mock_client
    mock_codealive_context.base_url = "https://app.codealive.ai"

    ctx.request_context.lifespan_context = mock_codealive_context
    ctx.request_context.headers = {"authorization": "Bearer test_key"}

    result = await fetch_artifacts(
        ctx=ctx,
        identifiers=["owner/repo::file.py::func"],
    )

    # Line numbers are added before escaping
    assert "1 | if x &lt; 10 &amp;&amp; y &gt; 5:" in result
    assert "&lt;" in result
    assert "&amp;" in result
    assert "<artifacts>" in result
    assert "</artifacts>" in result
