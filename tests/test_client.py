"""Tests for the SiYuan HTTP client."""

import pytest
import httpx

from mcp_siyuan.client import SiYuanClient, SiYuanError


@pytest.fixture
def client():
    return SiYuanClient(base_url="http://test:6806", token="test-token")


@pytest.mark.asyncio
async def test_call_success(client, httpx_mock):
    """Successful API call returns data field."""
    httpx_mock.add_response(
        json={"code": 0, "msg": "", "data": {"notebooks": [{"id": "nb1", "name": "Test"}]}},
    )
    result = await client.call("/api/notebook/lsNotebooks")
    assert result == {"notebooks": [{"id": "nb1", "name": "Test"}]}


@pytest.mark.asyncio
async def test_call_error_response(client, httpx_mock):
    """Non-zero code raises SiYuanError with message."""
    httpx_mock.add_response(
        json={"code": -1, "msg": "block not found", "data": None},
    )
    with pytest.raises(SiYuanError, match="block not found"):
        await client.call("/api/block/getBlockInfo", id="nonexistent")


@pytest.mark.asyncio
async def test_call_connection_error(client, httpx_mock):
    """Connection failure raises SiYuanError with URL."""
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    with pytest.raises(SiYuanError, match="Cannot reach SiYuan"):
        await client.call("/api/notebook/lsNotebooks")


@pytest.mark.asyncio
async def test_auth_header(client, httpx_mock):
    """Client sends Authorization header with token."""
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": None})
    await client.call("/api/test")
    request = httpx_mock.get_request()
    assert request.headers["Authorization"] == "Token test-token"


@pytest.mark.asyncio
async def test_no_token():
    """Client without token omits Authorization header."""
    c = SiYuanClient(base_url="http://test:6806", token="")
    http = await c._client()
    assert "Authorization" not in http.headers
    await c.close()


@pytest.mark.asyncio
async def test_close(client):
    """Client close is safe to call."""
    await client.close()
