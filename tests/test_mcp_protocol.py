"""The MCP surface itself: server stands up, registers its tools, dispatches a call.

Every other test calls tool functions directly, so nothing else would notice a
framework upgrade that stops the server importing, drops a tool from the
manifest, or breaks dispatch. Pattern: mcp-stolperfalle tests/test_mcp_protocol.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client

from mcp_siyuan.server import mcp

EXPECTED_TOOLS = {
    "list_notebooks", "sql_query", "get_document", "search", "get_block",
    "create_document", "update_block", "append_block", "upsert_section",
    "delete_block", "daily_note", "find_tasks", "export_pdf",
}


def _hint(annotations, snake: str, camel: str):
    # fastmcp 3 exposes camelCase, 4 snake_case; read whichever exists.
    return getattr(annotations, snake, getattr(annotations, camel, None))


@pytest.mark.asyncio
async def test_server_registers_its_tools():
    async with Client(mcp) as client:
        names = {t.name for t in await client.list_tools()}
    assert EXPECTED_TOOLS <= names, f"missing: {EXPECTED_TOOLS - names}"


@pytest.mark.asyncio
async def test_read_only_annotations_survive_the_wire():
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    ann = tools["list_notebooks"].annotations
    assert ann is not None
    assert _hint(ann, "read_only_hint", "readOnlyHint") is True
    assert _hint(tools["delete_block"].annotations, "destructive_hint", "destructiveHint") is True


@pytest.mark.asyncio
async def test_a_tool_call_round_trips():
    with patch("mcp_siyuan.tools.read.sy") as sy:
        sy.call = AsyncMock(return_value={
            "notebooks": [{"id": "nb1", "name": "Work", "icon": "", "sort": 0, "closed": False}]
        })
        async with Client(mcp) as client:
            result = await client.call_tool("list_notebooks", {})
    sy.call.assert_awaited_once_with("/api/notebook/lsNotebooks")
    assert result.content, "list_notebooks returned no content"
    assert "nb1" in result.content[0].text
