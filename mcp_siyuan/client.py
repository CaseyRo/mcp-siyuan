"""Async HTTP client for the SiYuan kernel API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from mcp_siyuan.config import settings

logger = logging.getLogger(__name__)


class SiYuanError(Exception):
    """Raised when the SiYuan kernel returns a non-zero code."""


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
            logger.info("SiYuan session auth successful")
        else:
            logger.warning("SiYuan session login failed: %s", body.get("msg", ""))

    async def call(self, endpoint: str, **payload: Any) -> Any:
        """POST to a SiYuan API endpoint and return the data field."""
        client = await self._client()

        # Ensure we're authenticated
        if not self._session_authed and self._token:
            await self._login()

        try:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise SiYuanError(
                f"Cannot reach SiYuan at {self._base_url}{endpoint}"
            ) from exc

        body = resp.json()
        code = body.get("code", -1)
        if code != 0:
            msg = body.get("msg", "unknown error")
            raise SiYuanError(f"SiYuan {endpoint}: {msg}")
        return body.get("data")

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()


# Module-level singleton used by tools.
sy = SiYuanClient()
