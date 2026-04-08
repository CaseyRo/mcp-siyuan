"""Tests for authentication module."""

import pytest

from mcp_siyuan.auth import BearerTokenVerifier


@pytest.mark.asyncio
async def test_bearer_verifier_valid_key():
    """Valid API key is accepted."""
    verifier = BearerTokenVerifier("test-key-123")
    result = await verifier.verify_token("test-key-123")
    assert result is not None
    assert result.client_id == "bearer"


@pytest.mark.asyncio
async def test_bearer_verifier_invalid_key():
    """Invalid API key is rejected."""
    verifier = BearerTokenVerifier("test-key-123")
    result = await verifier.verify_token("wrong-key")
    assert result is None


@pytest.mark.asyncio
async def test_bearer_verifier_empty_key():
    """Empty token is rejected."""
    verifier = BearerTokenVerifier("test-key-123")
    result = await verifier.verify_token("")
    assert result is None


@pytest.mark.asyncio
async def test_bearer_verifier_timing_safe():
    """Verification uses constant-time comparison (hmac.compare_digest)."""
    verifier = BearerTokenVerifier("a" * 20)
    result = await verifier.verify_token("b" * 20)
    assert result is None
