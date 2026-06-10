"""Test that the FastMCP version-pin guard logs a mismatch without crashing."""

from __future__ import annotations

import logging
from unittest.mock import patch

from mcp_siyuan import server


def test_version_match_logs_info(caplog):
    caplog.set_level(logging.INFO)
    with patch(
        "mcp_siyuan.server.importlib_metadata.version", return_value="3.4.2"
    ):
        server._check_fastmcp_version()
    assert any("fastmcp loaded" in rec.message for rec in caplog.records)
    assert not any(rec.levelno == logging.ERROR for rec in caplog.records)


def test_version_in_range_logs_info(caplog):
    """A newer 3.x patch/minor within the pin range must not error."""
    caplog.set_level(logging.INFO)
    with patch(
        "mcp_siyuan.server.importlib_metadata.version", return_value="3.9.1"
    ):
        server._check_fastmcp_version()
    assert any("fastmcp loaded" in rec.message for rec in caplog.records)
    assert not any(rec.levelno == logging.ERROR for rec in caplog.records)


def test_version_mismatch_logs_error_but_does_not_raise(caplog):
    caplog.set_level(logging.INFO)
    with patch(
        "mcp_siyuan.server.importlib_metadata.version", return_value="9.9.9"
    ):
        server._check_fastmcp_version()
    error_records = [rec for rec in caplog.records if rec.levelno == logging.ERROR]
    assert error_records, "expected an ERROR record on version mismatch"
    assert "9.9.9" in error_records[0].getMessage()
    assert "3.4.2" in error_records[0].getMessage()
