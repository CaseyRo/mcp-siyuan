"""Configuration loaded from environment variables."""

from __future__ import annotations

import logging
import warnings
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # SiYuan kernel connection
    siyuan_url: str = "http://siyuan:6806"
    siyuan_token: SecretStr = SecretStr("")

    # Server transport
    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000

    # Bearer token auth
    mcp_api_key: str = ""

    # Observability + reliability (siyuan-mcp-reliability-fixes)
    siyuan_log_level: str = "INFO"
    siyuan_diag_buffer_size: int = 50
    siyuan_idempotency_ttl_seconds: int = 300
    upstream_probe_interval: int = 30

    # HTTP-level retry on transient upstream failures (CDI-1093).
    # Applied to 5xx responses (502/503/504) and httpx transport errors.
    siyuan_retry_max_attempts: int = 3
    siyuan_retry_initial_backoff: float = 0.25
    siyuan_retry_max_backoff: float = 2.0

    model_config = {"env_prefix": "", "case_sensitive": False}

    @field_validator("siyuan_url")
    @classmethod
    def validate_siyuan_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("SIYUAN_URL must use http or https scheme")
        if not parsed.hostname:
            raise ValueError("SIYUAN_URL must have a hostname")
        return v

    def model_post_init(self, __context: Any) -> None:
        if not self.siyuan_token.get_secret_value():
            warnings.warn(
                "SIYUAN_TOKEN is not set. Requests to SiYuan will be unauthenticated.",
                stacklevel=2,
            )

settings = Settings()
