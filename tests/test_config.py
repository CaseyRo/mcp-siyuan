"""Tests for configuration loading."""

import warnings

import pytest

from mcp_siyuan.config import Settings


def test_default_settings():
    """Settings load with defaults when no env vars set."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = Settings(siyuan_token="test")
    assert s.siyuan_url == "http://siyuan:6806"
    assert s.transport == "stdio"
    assert s.host == "127.0.0.1"
    assert s.port == 8000


def test_settings_from_env(monkeypatch):
    """Settings read from environment variables."""
    monkeypatch.setenv("SIYUAN_URL", "http://localhost:9999")
    monkeypatch.setenv("SIYUAN_TOKEN", "my-secret-token")
    monkeypatch.setenv("TRANSPORT", "http")

    s = Settings()
    assert s.siyuan_url == "http://localhost:9999"
    assert s.siyuan_token.get_secret_value() == "my-secret-token"
    assert s.transport == "http"


def test_invalid_transport():
    """Invalid transport value raises validation error."""
    with pytest.raises(Exception):
        Settings(transport="websocket", siyuan_token="t")


def test_token_is_secret_str():
    """Token is SecretStr and does not appear in repr."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = Settings(siyuan_token="super-secret")
    assert "super-secret" not in repr(s)
    assert s.siyuan_token.get_secret_value() == "super-secret"


def test_empty_token_warns():
    """Empty token emits a warning at startup."""
    with pytest.warns(match="SIYUAN_TOKEN is not set"):
        Settings(siyuan_token="")


def test_invalid_siyuan_url_scheme():
    """Non-http(s) URL scheme is rejected."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(Exception, match="http or https"):
            Settings(siyuan_url="ftp://evil.com", siyuan_token="t")


def test_invalid_siyuan_url_no_host():
    """URL without hostname is rejected."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(Exception, match="hostname"):
            Settings(siyuan_url="http://", siyuan_token="t")


def test_auth_settings_defaults():
    """Auth settings have correct defaults."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = Settings(siyuan_token="t")
    assert s.mcp_api_key == ""
