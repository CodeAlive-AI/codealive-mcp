"""HTTP Host/Origin protection tests for the FastMCP transport."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import codealive_mcp_server as server

mcp = server.mcp


def _protected_app():
    return mcp.http_app(
        path="/api",
        stateless_http=True,
        host_origin_protection=True,
        allowed_hosts=["mcp.codealive.ai"],
        allowed_origins=["https://mcp.codealive.ai"],
    )


async def _request(path: str, headers: dict[str, str]):
    app = _protected_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mcp.codealive.ai",
        ) as client:
            return await client.get(path, headers=headers)


@pytest.mark.asyncio
async def test_http_transport_rejects_untrusted_host(monkeypatch):
    monkeypatch.setenv("TRANSPORT_MODE", "http")

    response = await _request("/api", {"Host": "attacker.example"})

    assert response.status_code == 421


@pytest.mark.asyncio
async def test_http_transport_rejects_untrusted_origin(monkeypatch):
    monkeypatch.setenv("TRANSPORT_MODE", "http")

    response = await _request("/api", {
        "Host": "mcp.codealive.ai",
        "Origin": "https://attacker.example",
    })

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_http_transport_allows_configured_host_and_origin(monkeypatch):
    monkeypatch.setenv("TRANSPORT_MODE", "http")

    response = await _request("/api", {
        "Host": "mcp.codealive.ai",
        "Origin": "https://mcp.codealive.ai",
    })

    assert response.status_code not in {403, 421}


@pytest.mark.asyncio
async def test_health_route_accepts_configured_probe_host(monkeypatch):
    monkeypatch.setenv("TRANSPORT_MODE", "http")

    response = await _request("/health", {"Host": "mcp.codealive.ai"})

    assert response.status_code == 200


def test_http_main_enables_guard_and_reads_environment_allowlists(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(server.mcp, "run", run)
    monkeypatch.setattr(server, "setup_logging", MagicMock())
    monkeypatch.setattr(server, "init_tracing", MagicMock())
    monkeypatch.setenv(
        "CODEALIVE_MCP_ALLOWED_HOSTS",
        "mcp.codealive.ai,codealive-mcp-server",
    )
    monkeypatch.setenv("CODEALIVE_MCP_ALLOWED_ORIGINS", "https://mcp.codealive.ai")
    monkeypatch.setattr(sys, "argv", ["codealive-mcp", "--transport", "http"])

    server.main()

    run.assert_called_once()
    options = run.call_args.kwargs
    assert options["host"] == "127.0.0.1"
    assert options["host_origin_protection"] is True
    assert options["allowed_hosts"] == ["mcp.codealive.ai", "codealive-mcp-server"]
    assert options["allowed_origins"] == ["https://mcp.codealive.ai"]


def test_http_main_fails_closed_when_oauth_exchange_secret_is_missing(monkeypatch):
    monkeypatch.setattr(server, "setup_logging", MagicMock())
    monkeypatch.setattr(server, "init_tracing", MagicMock())
    monkeypatch.setenv("CODEALIVE_MCP_OAUTH_ENABLED", "true")
    monkeypatch.delenv("CODEALIVE_OAUTH_INTERNAL_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(sys, "argv", ["codealive-mcp", "--transport", "http"])

    with pytest.raises(SystemExit) as error:
        server.main()

    assert error.value.code == 1


def test_debug_mode_does_not_disable_tls_verification(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(server.mcp, "run", run)
    monkeypatch.setattr(server, "setup_logging", MagicMock())
    monkeypatch.setattr(server, "init_tracing", MagicMock())
    monkeypatch.delenv("CODEALIVE_IGNORE_SSL", raising=False)
    monkeypatch.setattr(sys, "argv", ["codealive-mcp", "--transport", "http", "--debug"])

    server.main()

    assert "CODEALIVE_IGNORE_SSL" not in server.os.environ
