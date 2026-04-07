"""Tests for the /ready readiness endpoint."""

import datetime
import sys
from unittest.mock import MagicMock, PropertyMock

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

# Import the readiness_check function from the server module.
# This also triggers FastMCP initialization, which is acceptable in tests.
from codealive_mcp_server import readiness_check


def _make_request(lifespan_context=None, *, has_state=True):
    """Build a mock Starlette Request with the given app state."""
    request = MagicMock()
    if has_state:
        request.app.state.lifespan_context = lifespan_context
    else:
        # Simulate missing state attribute
        del request.app.state
    return request


class TestReadinessCheck:
    @pytest.mark.asyncio
    async def test_ready_when_client_available(self):
        client = MagicMock()
        client.is_closed = False
        ctx = MagicMock()
        ctx.client = client

        request = _make_request(lifespan_context=ctx)
        response = await readiness_check(request)

        assert response.status_code == 200
        import json
        body = json.loads(response.body)
        assert body["status"] == "ready"
        assert body["service"] == "codealive-mcp-server"
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_not_ready_when_lifespan_not_initialized(self):
        request = _make_request(lifespan_context=None)
        response = await readiness_check(request)

        assert response.status_code == 503
        import json
        body = json.loads(response.body)
        assert body["status"] == "not_ready"
        assert "lifespan" in body["reason"]

    @pytest.mark.asyncio
    async def test_not_ready_when_client_closed(self):
        client = MagicMock()
        client.is_closed = True
        ctx = MagicMock()
        ctx.client = client

        request = _make_request(lifespan_context=ctx)
        response = await readiness_check(request)

        assert response.status_code == 503
        import json
        body = json.loads(response.body)
        assert body["status"] == "not_ready"
        assert "client" in body["reason"]

    @pytest.mark.asyncio
    async def test_not_ready_when_client_is_none(self):
        ctx = MagicMock()
        ctx.client = None

        request = _make_request(lifespan_context=ctx)
        response = await readiness_check(request)

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_not_ready_on_unexpected_exception(self):
        request = MagicMock()
        # Make app.state raise an exception
        type(request.app).state = PropertyMock(side_effect=RuntimeError("kaboom"))

        response = await readiness_check(request)

        assert response.status_code == 503
        import json
        body = json.loads(response.body)
        assert body["status"] == "not_ready"
        assert "kaboom" in body["reason"]
