"""Pydantic models for SiYuan API types.

The input/read models (``Notebook``, ``Block``, ``SearchResult``) describe the
projected shapes the read tools already emit. The ``*Result`` models below are
used as tool return types so FastMCP advertises an ``output_schema`` and emits
structured content — turning the prose ``Returns:`` blocks into a machine-checkable
contract. All fields match the keys the tools returned before this change, so
existing clients that read those keys keep working.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


# ---------------------------------------------------------------------------
# Output-schema models (deepen pass — CDI structured-output coverage).
#
# Every model below is used as a tool ``output_schema`` and MUST validate BOTH
# the success payload AND the error payload a tool can emit. To stay
# forward/backward-compatible with the manually-synced Cloudflare portal and
# live clients, each model:
#   * preserves the EXACT current top-level wire keys (all snake_case today, so
#     no serialization_alias is needed; documented here so future edits keep it),
#   * gives collection fields a ``default_factory=list`` so an empty/error
#     payload validates,
#   * makes non-guaranteed fields Optional with defaults,
#   * carries an optional ``error: str | None = None`` for error payloads, and
#   * sets ``model_config = ConfigDict(extra="allow")`` so kernel-passthrough
#     keys (e.g. SiYuan's notebook object, transaction arrays) never trip
#     validation. (This is the exact bug fixed in mcp-zernio.)
# ---------------------------------------------------------------------------

_ALLOW = ConfigDict(extra="allow")


class NotebookInfo(BaseModel):
    """One row of ``list_notebooks`` (projected ``Notebook`` shape)."""

    model_config = _ALLOW

    id: str = ""
    name: str = ""
    icon: str = ""
    sort: int = 0
    closed: bool = False
    error: str | None = None


class SqlRow(BaseModel):
    """One row of ``sql_query`` — columns vary by SELECT, so all are optional.

    ``extra="allow"`` keeps whatever columns the SELECT projected; ``id`` is the
    only near-universal column on the blocks/spans/refs/attributes tables.
    """

    model_config = _ALLOW

    id: str | None = None
    error: str | None = None


class SearchHit(BaseModel):
    """One row of ``search`` (full-text, no context)."""

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    root_id: str = ""
    box: str = ""
    hpath: str = ""
    error: str | None = None


class BlockInfo(BaseModel):
    """Return shape of ``get_block`` (success) or its ``{"error": ...}`` path."""

    model_config = _ALLOW

    id: str = ""
    type: str = ""
    content: str = ""
    parent_id: str = ""
    root_id: str = ""
    box: str = ""
    hpath: str = ""
    updated: str = ""
    error: str | None = None


class RecentDoc(BaseModel):
    """One row of ``get_recent_docs``."""

    model_config = _ALLOW

    id: str = ""
    title: str = ""
    box: str = ""
    hpath: str = ""
    updated: str = ""
    error: str | None = None


class TaskItem(BaseModel):
    """One row of ``find_tasks`` (task list-item with parent doc title)."""

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    box: str = ""
    hpath: str = ""
    root_id: str = ""
    updated: str = ""
    doc_title: str | None = None
    error: str | None = None


class Backlink(BaseModel):
    """One row of ``get_backlinks`` (referencing block + its doc title)."""

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    type: str = ""
    hpath: str = ""
    box: str = ""
    doc_title: str = ""
    error: str | None = None


class TagCount(BaseModel):
    """One row of ``get_tags`` (flattened tag path + usage count)."""

    model_config = _ALLOW

    tag: str = ""
    count: int = 0
    error: str | None = None


class TaggedBlock(BaseModel):
    """One row of ``search_by_tag`` (raw SQL projection)."""

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    type: str = ""
    box: str = ""
    hpath: str = ""
    updated: str = ""
    error: str | None = None


class BlockChildren(BaseModel):
    """Return shape of ``get_block_children`` — a block + its child tree.

    ``children`` are left as raw dicts (recursive SiYuan rows projected with
    id/content/type/sort/parent_id/children) so the nested structure passes
    through unchanged; ``extra="allow"`` covers any future per-node keys.
    """

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    type: str = ""
    children: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ContextSearchHit(BaseModel):
    """One row of ``search_with_context`` (hit + optional sibling context)."""

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    type: str = ""
    hpath: str = ""
    box: str = ""
    root_id: str = ""
    context: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class OutlineHeading(BaseModel):
    """One row of ``get_document_outline`` (heading-only projection)."""

    model_config = _ALLOW

    id: str = ""
    content: str = ""
    level: str = ""
    sort: int = 0
    error: str | None = None


class CaptureTaskResult(BaseModel):
    """Return shape of ``capture_task`` (success or ``{"error": ...}``)."""

    model_config = _ALLOW

    ok: bool = False
    daily_note_id: str | None = None
    notebook: str | None = None
    task: str | None = None
    transactions: list[Any] = Field(default_factory=list)
    error: str | None = None


class WriteResult(BaseModel):
    """Generic write-tool result.

    Covers the normalised ``{"ok": True}`` / ``{"ok": True, "transactions": [...]}``
    shape returned by ``_wrap_result`` as well as kernel-passthrough dicts (e.g.
    ``create_notebook`` returns ``{"notebook": {...}}``). ``extra="allow"`` keeps
    every passthrough key; the named fields document the common ones.
    """

    model_config = _ALLOW

    ok: bool = True
    transactions: list[Any] = Field(default_factory=list)
    error: str | None = None


class DeleteBlockResult(BaseModel):
    """Return shape of ``delete_block`` (idempotent delete)."""

    model_config = _ALLOW

    ok: bool = True
    already_absent: bool = False
    transactions: list[Any] = Field(default_factory=list)
    error: str | None = None


class DeleteDocResult(BaseModel):
    """Return shape of ``delete_doc``."""

    model_config = _ALLOW

    ok: bool = True
    deleted_id: str = ""
    already_absent: bool = False
    result: Any = None
    error: str | None = None


class SectionResult(BaseModel):
    """Return shape of ``upsert_section`` and ``append_to_section``.

    ``upsert_section`` emits ``action`` + ``heading_id``; ``append_to_section``
    emits ``heading_id`` + ``anchor_id``. Both unioned here (all optional) so a
    single model validates either tool's payload.
    """

    model_config = _ALLOW

    ok: bool = True
    action: Literal["replaced", "created"] | None = None
    heading_id: str | None = None
    anchor_id: str | None = None
    error: str | None = None


class DocUpsertResult(BaseModel):
    """Return shape of ``get_or_create_doc``."""

    model_config = _ALLOW

    block_id: str | None = None
    was_created: bool = False
    was_updated: bool = False
    hpath: str = ""
    error: str | None = None


class DocExistsResult(BaseModel):
    """Return shape of ``doc_exists``."""

    model_config = _ALLOW

    exists: bool = False
    block_id: str | None = None
    hpath: str = ""
    error: str | None = None


class BulkDocResult(BaseModel):
    """Per-item result of ``bulk_create_documents``."""

    model_config = _ALLOW

    path: str = ""
    block_id: str | None = None
    status: Literal["ok", "error"] = "ok"
    error: str | None = None


class BulkAttrResult(BaseModel):
    """Per-item result of ``bulk_set_attrs``."""

    model_config = _ALLOW

    block_id: str = ""
    status: Literal["ok", "error"] = "ok"
    error: str | None = None
