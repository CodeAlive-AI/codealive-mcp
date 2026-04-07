"""Tests for configuration helpers."""

from core.config import Config, normalize_base_url


def test_normalize_base_url_keeps_cloud_origin():
    assert normalize_base_url("https://app.codealive.ai") == "https://app.codealive.ai"


def test_normalize_base_url_strips_api_suffix():
    assert normalize_base_url("https://codealive.example.com/api") == "https://codealive.example.com"
    assert normalize_base_url("https://codealive.example.com/api/") == "https://codealive.example.com"


def test_normalize_base_url_preserves_path_prefix():
    assert normalize_base_url("https://codealive.example.com/internal") == "https://codealive.example.com/internal"
    assert normalize_base_url("https://codealive.example.com/internal/api") == "https://codealive.example.com/internal"


def test_config_from_environment_uses_normalized_base_url(monkeypatch):
    monkeypatch.setenv("CODEALIVE_BASE_URL", "https://codealive.example.com/api/")

    config = Config.from_environment()

    assert config.base_url == "https://codealive.example.com"
