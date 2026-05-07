"""Integration test for /health?diag=1."""

from __future__ import annotations


import pytest
from starlette.testclient import TestClient

from mcp_siyuan.observability import diag_buffer
from mcp_siyuan.observability.tracing import traced_tool


@pytest.fixture
def client(monkeypatch):
    """Build the FastMCP HTTP app and a Starlette TestClient against it."""
    diag_buffer.reset_for_tests(maxlen=50)

    # Skip the upstream probe so /health doesn't try to reach SiYuan
    from mcp_siyuan import server as srv

    async def _ok():
        return True

    monkeypatch.setattr(srv, "_probe_upstream", _ok)
    app = srv.mcp.http_app()
    with TestClient(app) as c:
        yield c
    diag_buffer.reset_for_tests(maxlen=50)


def test_plain_health_unchanged(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "mcp-siyuan"
    assert body["status"] == "healthy"
    assert "diag" not in body


@pytest.mark.asyncio
async def test_diag_returns_recent_calls(client):
    @traced_tool
    async def t(x: str) -> str:
        return x

    await t("one")
    await t("two")

    resp = client.get("/health?diag=1")
    assert resp.status_code == 200
    body = resp.json()
    assert "diag" in body
    diag = body["diag"]
    assert len(diag) == 2
    request_ids = [e["request_id"] for e in diag]
    assert len(set(request_ids)) == 2  # distinct
    assert all(e["tool_name"] == "siyuan_t" for e in diag)
