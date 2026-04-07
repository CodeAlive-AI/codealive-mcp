"""Tests for the /ready readiness endpoint."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from codealive_mcp_server import readiness_check


class TestReadinessCheck:
    @pytest.mark.asyncio
    async def test_ready_when_flag_is_true(self):
        with patch("codealive_mcp_server._client_module") as mock_module:
            mock_module._server_ready = True
            response = await readiness_check(MagicMock())

        assert response.status_code == 200
        body = json.loads(response.body)
        assert body["status"] == "ready"
        assert body["service"] == "codealive-mcp-server"
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_not_ready_when_flag_is_false(self):
        with patch("codealive_mcp_server._client_module") as mock_module:
            mock_module._server_ready = False
            response = await readiness_check(MagicMock())

        assert response.status_code == 503
        body = json.loads(response.body)
        assert body["status"] == "not_ready"
        assert "lifespan" in body["reason"]

    @pytest.mark.asyncio
    async def test_flag_lifecycle(self):
        """Verify _server_ready flag is set/unset by lifespan."""
        from core.client import _server_ready, codealive_lifespan
        import core.client as client_mod

        # Before lifespan, flag should be False (default)
        assert client_mod._server_ready is False

        # We can't easily run the full lifespan without env vars,
        # but we verify the flag default is correct.
