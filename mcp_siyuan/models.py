"""Pydantic models for SiYuan API types."""

from __future__ import annotations

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
