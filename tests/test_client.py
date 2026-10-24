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
async def test_call_connection_error(client, httpx_mock, monkeypatch):
    """Connection failure raises SiYuanError with URL."""
    # Disable retries for this test so the failure surfaces immediately.
    from mcp_siyuan.config import settings as settings_

    monkeypatch.setattr(settings_, "siyuan_retry_max_attempts", 1)
    monkeypatch.setattr(settings_, "siyuan_retry_initial_backoff", 0.0)
    httpx_mock.add_exception(httpx.ConnectError("Connection refused"))
    with pytest.raises(SiYuanError, match="Cannot reach SiYuan"):
        await client.call("/api/notebook/lsNotebooks")


@pytest.mark.asyncio
async def test_call_retries_on_502(client, httpx_mock, monkeypatch):
    """Transient 502 is retried and recovered on a later attempt (CDI-1093)."""
    from mcp_siyuan.config import settings as settings_

    monkeypatch.setattr(settings_, "siyuan_retry_max_attempts", 3)
    monkeypatch.setattr(settings_, "siyuan_retry_initial_backoff", 0.0)
    monkeypatch.setattr(settings_, "siyuan_retry_max_backoff", 0.0)

    # First two attempts return 502; third attempt succeeds.
    httpx_mock.add_response(status_code=502, text="bad gateway")
    httpx_mock.add_response(status_code=502, text="bad gateway")
    httpx_mock.add_response(
        json={"code": 0, "msg": "", "data": {"ok": True}},
    )
    result = await client.call("/api/filetree/renameDocByID", id="x", title="y")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_call_does_not_retry_on_4xx(client, httpx_mock, monkeypatch):
    """4xx responses are not retried (only 502/503/504)."""
    from mcp_siyuan.config import settings as settings_

    monkeypatch.setattr(settings_, "siyuan_retry_max_attempts", 3)
    monkeypatch.setattr(settings_, "siyuan_retry_initial_backoff", 0.0)

    httpx_mock.add_response(status_code=400, text="bad request")
    with pytest.raises(httpx.HTTPStatusError):
        await client.call("/api/x", foo="bar")


@pytest.mark.asyncio
async def test_call_503_retry_exhaustion_marks_retryable(
    client, httpx_mock, monkeypatch
):
    """Persistent 503 surfaces a retryable HTTPStatusError after retries."""
    from mcp_siyuan.config import settings as settings_

    monkeypatch.setattr(settings_, "siyuan_retry_max_attempts", 2)
    monkeypatch.setattr(settings_, "siyuan_retry_initial_backoff", 0.0)

    httpx_mock.add_response(status_code=503, text="unavailable")
    httpx_mock.add_response(status_code=503, text="unavailable")
    with pytest.raises(httpx.HTTPStatusError):
        await client.call("/api/x", foo="bar")


@pytest.mark.asyncio
async def test_header_auth_never_logs_in(client, httpx_mock):
    """Regression: while the Token header works, no loginAuth call is made.

    The old client logged in before every call; SiYuan's brute-force guard then
    answered "Please enter the captcha" forever (13,932 failed attempts in 4.8 days).
    """
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": []})
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": []})

    await client.call("/api/notebook/lsNotebooks")
    await client.call("/api/notebook/lsNotebooks")

    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert all("loginAuth" not in str(r.url) for r in requests)


@pytest.mark.asyncio
async def test_session_login_on_401(client, httpx_mock):
    """A rejected Token header triggers one session login, then the call is retried."""
    httpx_mock.add_response(status_code=401, text="unauthorized")
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": None})  # loginAuth
    httpx_mock.add_response(json={"code": 0, "msg": "", "data": []})  # retry

    await client.call("/api/notebook/lsNotebooks")

    paths = [r.url.path for r in httpx_mock.get_requests()]
    assert paths == [
        "/api/notebook/lsNotebooks",
        "/api/system/loginAuth",
        "/api/notebook/lsNotebooks",
    ]
    assert client._session_authed is True
    assert "Authorization" not in client._http.headers


@pytest.mark.asyncio
async def test_login_attempted_once_when_token_rejected(client, httpx_mock):
    """A token the kernel keeps rejecting costs one loginAuth per process, not one per call."""
    httpx_mock.add_response(status_code=401, text="unauthorized")  # call 1
    httpx_mock.add_response(
        json={"code": -1, "msg": "Please enter the captcha", "data": None}
    )  # loginAuth fails
    httpx_mock.add_response(status_code=401, text="unauthorized")  # call 1 retry
    httpx_mock.add_response(status_code=401, text="unauthorized")  # call 2

    with pytest.raises(httpx.HTTPStatusError):
        await client.call("/api/notebook/lsNotebooks")
    with pytest.raises(httpx.HTTPStatusError):
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
