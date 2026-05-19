"""Async HTTP client for the SiYuan kernel API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from mcp_siyuan.config import settings
from mcp_siyuan.observability.context import set_kernel_status

logger = logging.getLogger(__name__)

# HTTP status codes that indicate a transient upstream issue worth retrying
# (CDI-1093). 5xx responses surface as httpx.HTTPStatusError on
# raise_for_status(); we inspect the response code before propagating.
_RETRYABLE_STATUS = {502, 503, 504}


class SiYuanError(Exception):
    """Raised when the SiYuan kernel returns a non-zero code."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        # Hint to callers (and the response envelope) that retrying is safe.
        self.retryable = retryable


class SiYuanClient:
    """Thin wrapper around SiYuan's POST-based JSON API.

    Supports both header-based auth (Token) and session-based auth (loginAuth).
    Falls back to session auth if header auth fails with 401.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.siyuan_url).rstrip("/")
        self._token = token if token is not None else settings.siyuan_token.get_secret_value()
        self._http: httpx.AsyncClient | None = None
        self._session_authed = False

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Token {self._token}"
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._http

    async def _login(self) -> None:
        """Authenticate via session login (SiYuan 3.x)."""
        if not self._token or self._session_authed:
            return
        client = await self._client()
        try:
            resp = await client.post(
                "/api/system/loginAuth",
                json={"authCode": self._token},
            )
        except httpx.ConnectError:
            return  # Let the actual call raise the error
        body = resp.json()
        if body.get("code") == 0:
            self._session_authed = True
            # Remove Token header — SiYuan rejects it even with valid cookie
            client.headers.pop("Authorization", None)
            logger.info("SiYuan session auth successful")
        else:
            logger.warning("SiYuan session login failed: %s", body.get("msg", ""))

    async def call(self, endpoint: str, **payload: Any) -> Any:
        """POST to a SiYuan API endpoint and return the data field.

        Retries on transient transport errors and 5xx responses (502/503/504)
        with capped exponential backoff. Configurable via
        ``SIYUAN_RETRY_MAX_ATTEMPTS`` / ``SIYUAN_RETRY_INITIAL_BACKOFF`` /
        ``SIYUAN_RETRY_MAX_BACKOFF``.
        """
        client = await self._client()

        # Ensure we're authenticated
        if not self._session_authed and self._token:
            await self._login()

        max_attempts = max(1, int(settings.siyuan_retry_max_attempts))
        backoff = max(0.0, float(settings.siyuan_retry_initial_backoff))
        max_backoff = max(backoff, float(settings.siyuan_retry_max_backoff))

        last_exc: Exception | None = None
        resp: httpx.Response | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.post(endpoint, json=payload)
                resp.raise_for_status()
                break
            except httpx.ConnectError as exc:
                last_exc = exc
                set_kernel_status("unreachable")
                if attempt >= max_attempts:
                    raise SiYuanError(
                        f"Cannot reach SiYuan at {self._base_url}{endpoint}",
                        retryable=True,
                    ) from exc
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                set_kernel_status(f"http_{status}")
                if status in _RETRYABLE_STATUS and attempt < max_attempts:
                    logger.warning(
                        "siyuan.transient_http_error",
                        extra={
                            "endpoint": endpoint,
                            "status": status,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                        },
                    )
                else:
                    raise
            except httpx.TransportError as exc:
                # ReadError, RemoteProtocolError, etc. — treat as transient.
                last_exc = exc
                set_kernel_status("transport_error")
                if attempt >= max_attempts:
                    raise SiYuanError(
                        f"Transport error talking to SiYuan: {exc}",
                        retryable=True,
                    ) from exc
            # Backoff before the next attempt.
            await asyncio.sleep(min(backoff, max_backoff))
            backoff = min(backoff * 2 if backoff > 0 else 0.1, max_backoff)

        if resp is None:
            # Should not happen — the loop either returns a response or raises.
            raise SiYuanError(
                f"SiYuan call exhausted retries: {last_exc}", retryable=True
            )

        body = resp.json()
        code = body.get("code", -1)
        set_kernel_status(str(code))
        if code != 0:
            msg = body.get("msg", "unknown error")
            raise SiYuanError(f"SiYuan {endpoint}: {msg}", code=code)
        return body.get("data")

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()


# Module-level singleton used by tools.
sy = SiYuanClient()
