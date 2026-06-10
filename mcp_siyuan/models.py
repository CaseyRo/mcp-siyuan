"""Pydantic models for SiYuan API types.

The input/read models (``Notebook``, ``Block``, ``SearchResult``) describe the
projected shapes the read tools already emit. The ``*Result`` models below are
used as tool return types so FastMCP advertises an ``output_schema`` and emits
structured content — turning the prose ``Returns:`` blocks into a machine-checkable
contract. All fields match the keys the tools returned before this change, so
existing clients that read those keys keep working.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Notebook(BaseModel):
    id: str
    name: str
    icon: str = ""
    sort: int = 0
    closed: bool = False


class Block(BaseModel):
    id: str
    type: str = ""
    content: str = ""
    parent_id: str = ""
    root_id: str = ""
    box: str = ""
    path: str = ""


class SearchResult(BaseModel):
    id: str
    content: str = ""
    root_id: str = ""
    box: str = ""
    path: str = ""
    hpath: str = ""


class DocUpsertResult(BaseModel):
    """Return shape of ``get_or_create_doc``."""

    block_id: str | None = None
    was_created: bool = False
    was_updated: bool = False
    hpath: str = ""


class DocExistsResult(BaseModel):
    """Return shape of ``doc_exists``."""

    exists: bool = False
    block_id: str | None = None
    hpath: str = ""


class BulkDocResult(BaseModel):
    """Per-item result of ``bulk_create_documents``."""

    path: str = ""
    block_id: str | None = None
    status: Literal["ok", "error"] = "ok"
    error: str | None = None


class BulkAttrResult(BaseModel):
    """Per-item result of ``bulk_set_attrs``."""

    block_id: str = ""
    status: Literal["ok", "error"] = "ok"
    error: str | None = None
