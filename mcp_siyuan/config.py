"""Configuration loaded from environment variables."""

from __future__ import annotations

import warnings
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    siyuan_url: str = "http://siyuan:6806"
    siyuan_token: SecretStr = SecretStr("")
    transport: Literal["stdio", "http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000

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
