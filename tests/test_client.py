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
    # Login response
    httpx_mock.add_response(
        json={"code": 0, "msg": "", "data": None},
    )
    # Actual API call
    httpx_mock.add_response(
        json={"code": 0, "msg": "", "data": {"notebooks": [{"id": "nb1", "name": "Test"}]}},
    )
    result = await client.call("/api/notebook/lsNotebooks")
    assert result == {"notebooks": [{"id": "nb1", "name": "Test"}]}


@pytest.mark.asyncio
async def test_call_error_response(client, httpx_mock):
    """Non-zero code raises SiYuanError with message."""
    # Login
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": None})
    # Error response
    httpx_mock.add_response(
        json={"code": -1, "msg": "block not found", "data": None},
    )
    with pytest.raises(SiYuanError, match="block not found"):
        await client.call("/api/block/getBlockInfo", id="nonexistent")


@pytest.mark.asyncio
async def test_call_connection_error(client, httpx_mock):
    """Connection failure raises SiYuanError with URL."""
    # Login attempt fails
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    # Actual call also fails
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    with pytest.raises(SiYuanError, match="Cannot reach SiYuan"):
        await client.call("/api/notebook/lsNotebooks")


@pytest.mark.asyncio
async def test_session_login(client, httpx_mock):
    """Client logs in via session auth on first call."""
    # Login
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": None})
    # API call
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": []})

    await client.call("/api/notebook/lsNotebooks")

    requests = httpx_mock.get_requests()
    assert requests[0].url.path == "/api/system/loginAuth"
    assert client._session_authed is True


@pytest.mark.asyncio
async def test_session_login_only_once(client, httpx_mock):
    """Login is called only once, not on every request."""
    # Login
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": None})
    # Two API calls
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": []})
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": []})

    await client.call("/api/notebook/lsNotebooks")
    await client.call("/api/notebook/lsNotebooks")

    login_requests = [r for r in httpx_mock.get_requests() if "loginAuth" in str(r.url)]
    assert len(login_requests) == 1


@pytest.mark.asyncio
async def test_no_token():
    """Client without token omits Authorization header and skips login."""
    c = SiYuanClient(base_url="http://test:6806", token="")
    http = await c._client()
    assert "Authorization" not in http.headers
    await c.close()


@pytest.mark.asyncio
async def test_close(client):
    """Client close is safe to call."""
    await client.close()
