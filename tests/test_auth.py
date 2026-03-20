"""Tests for authentication module."""

import pytest

from mcp_siyuan.auth import BearerTokenVerifier, create_auth, generate_api_key


@pytest.mark.asyncio
async def test_bearer_verifier_valid_key():
    """Valid API key is accepted."""
    verifier = BearerTokenVerifier("smcp_test-key-123")
    result = await verifier.verify_token("smcp_test-key-123")
    assert result is not None
    assert result.client_id == "mcp-siyuan-client"
    assert "all" in result.scopes


@pytest.mark.asyncio
async def test_bearer_verifier_invalid_key():
    """Invalid API key is rejected."""
    verifier = BearerTokenVerifier("smcp_test-key-123")
    result = await verifier.verify_token("wrong-key")
    assert result is None


@pytest.mark.asyncio
async def test_bearer_verifier_empty_key():
    """Empty token is rejected."""
    verifier = BearerTokenVerifier("smcp_test-key-123")
    result = await verifier.verify_token("")
    assert result is None


@pytest.mark.asyncio
async def test_bearer_verifier_timing_safe():
    """Verification uses constant-time comparison (hmac.compare_digest)."""
    # We can't directly test timing, but we verify the code path works
    verifier = BearerTokenVerifier("smcp_a" * 20)
    result = await verifier.verify_token("smcp_b" * 20)
    assert result is None


def test_generate_api_key_format():
    """Generated API key has correct prefix and length."""
    key = generate_api_key()
    assert key.startswith("smcp_")
    assert len(key) > 20  # prefix + 32 bytes base64


def test_generate_api_key_unique():
    """Generated keys are unique."""
    keys = {generate_api_key() for _ in range(10)}
    assert len(keys) == 10


def test_create_auth_with_api_key():
    """create_auth returns MultiAuth with bearer verifier when key is provided."""
    auth = create_auth(
        api_key="smcp_test",
        base_url="https://example.com",
        keycloak_issuer="https://auth.example.com/realms/test",
        keycloak_audience="mcp-test",
    )
    assert auth is not None


def test_create_auth_without_api_key():
    """create_auth works without API key (JWT only)."""
    auth = create_auth(
        api_key=None,
        base_url="https://example.com",
        keycloak_issuer="https://auth.example.com/realms/test",
        keycloak_audience="mcp-test",
    )
    assert auth is not None
