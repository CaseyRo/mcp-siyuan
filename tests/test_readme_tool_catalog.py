"""Fail CI if any registered FastMCP tool isn't documented in README.md."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_every_registered_tool_appears_in_readme():
    from mcp_siyuan import server

    tools = await server.mcp.list_tools()
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    missing: list[str] = []
    for tool in tools:
        # Tools register as bare names; the portal exposes them as `siyuan_<name>`.
        # The README documents the user-facing form.
        user_facing = f"siyuan_{tool.name}"
        if user_facing not in readme:
            missing.append(user_facing)
    assert not missing, (
        f"README.md is missing entries for: {missing}. "
        "Add them to the Tool Catalog or update the catalog test."
    )
