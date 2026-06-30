"""Tests for the /health endpoint."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from codealive_mcp_server import health_check


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_includes_runtime_metadata_from_environment(self):
        env = {
            "CODEALIVE_MCP_SOURCE_REVISION": "430b85651e18fdf78992f919a36c573715358288",
        }
        with patch.dict("os.environ", env, clear=False), patch(
            "codealive_mcp_server.version", return_value="2.0.4"
        ):
            response = await health_check(MagicMock())

        assert response.status_code == 200
        body = json.loads(response.body)
        assert body["status"] == "healthy"
        assert body["service"] == "codealive-mcp-server"
        assert body["version"] == "2.0.4"
        assert body["sourceRevision"] == "430b85651e18fdf78992f919a36c573715358288"
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_uses_unknown_for_missing_runtime_metadata(self):
        with patch.dict("os.environ", {}, clear=True), patch(
            "codealive_mcp_server.version", return_value="2.0.4"
        ):
            response = await health_check(MagicMock())

        body = json.loads(response.body)
        assert body["version"] == "2.0.4"
        assert body["sourceRevision"] == "unknown"
