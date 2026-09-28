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
    assert ann.read_only_hint is True
    assert tools["delete_block"].annotations.destructive_hint is True


@pytest.mark.asyncio
async def test_c3_fields_survive_in_output_schemas():
    async with Client(mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
    assert "inserted_ids" in tools["update_block"].output_schema["properties"]
    assert "markdown" in tools["get_block"].output_schema["properties"]


@pytest.mark.asyncio
async def test_no_tool_returns_raw_kernel_transactions():
    """Write results carry ids, never the kernel's DOM transaction echo."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
    leaking = [
        t.name for t in tools
        if "transactions" in ((t.output_schema or {}).get("properties") or {})
    ]
    assert leaking == []


@pytest.mark.asyncio
async def test_delete_proceeds_when_client_cannot_elicit():
    """No elicitation handler on the client: ctx.elicit fails fast, delete proceeds."""
    with patch("mcp_siyuan.tools.write.sy") as sy:
        sy.call = AsyncMock(return_value=[{"doOperations": [{"action": "delete"}]}])
        async with Client(mcp) as client:
            result = await client.call_tool("delete_block", {"id": "20210808180320-fqgskfj"})
    sy.call.assert_awaited_once_with("/api/block/deleteBlock", id="20210808180320-fqgskfj")
    assert result.structured_content["ok"] is True


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


@pytest.mark.asyncio
async def test_a_tool_call_writes_one_usage_line(capsys):
    with patch("mcp_siyuan.tools.read.sy") as sy:
        sy.call = AsyncMock(return_value={"notebooks": []})
        async with Client(mcp) as client:
            await client.call_tool("list_notebooks", {})
    lines = [ln for ln in capsys.readouterr().err.splitlines() if '"mcp_usage"' in ln]
    assert len(lines) == 1
    assert all(s in lines[0] for s in ('"siyuan"', '"list_notebooks"', '"outcome": "ok"'))
