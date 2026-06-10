"""Tests for Pydantic models."""

import pytest

from mcp_siyuan.models import (
    Backlink,
    Block,
    BlockChildren,
    BlockInfo,
    BulkAttrResult,
    BulkDocResult,
    CaptureTaskResult,
    ContextSearchHit,
    DeleteBlockResult,
    DeleteDocResult,
    DocExistsResult,
    DocUpsertResult,
    Notebook,
    NotebookInfo,
    OutlineHeading,
    RecentDoc,
    SearchHit,
    SearchResult,
    SectionResult,
    SqlRow,
    TagCount,
    TaggedBlock,
    TaskItem,
    WriteResult,
)

# Every output-schema model paired with a representative SUCCESS payload whose
# keys are the EXACT top-level wire keys the tool emits today. The contract
# tests below assert (a) those keys round-trip unchanged and (b) the model also
# validates an error payload — the dual-validation rule we regressed in
# mcp-zernio.
_SUCCESS_PAYLOADS = {
    NotebookInfo: {"id": "nb1", "name": "Work", "icon": "x", "sort": 1, "closed": True},
    SqlRow: {"id": "b1", "content": "x", "markdown": "## h"},
    SearchHit: {"id": "b1", "content": "c", "root_id": "r", "box": "nb", "hpath": "/h"},
    BlockInfo: {
        "id": "b1", "type": "p", "content": "c", "parent_id": "d",
        "root_id": "r", "box": "nb", "hpath": "/h", "updated": "2026",
    },
    RecentDoc: {"id": "d", "title": "t", "box": "nb", "hpath": "/h", "updated": "2026"},
    TaskItem: {
        "id": "t", "content": "c", "box": "nb", "hpath": "/h",
        "root_id": "r", "updated": "2026", "doc_title": "D",
    },
    Backlink: {
        "id": "b", "content": "c", "type": "p", "hpath": "/h",
        "box": "nb", "doc_title": "D",
    },
    TagCount: {"tag": "cars/porsche", "count": 3},
    TaggedBlock: {
        "id": "b", "content": "c", "type": "p", "box": "nb",
        "hpath": "/h", "updated": "2026",
    },
    BlockChildren: {"id": "d", "content": "c", "type": "d", "children": [{"id": "h1"}]},
    ContextSearchHit: {
        "id": "b", "content": "c", "type": "p", "hpath": "/h",
        "box": "nb", "root_id": "r", "context": [{"id": "x"}],
    },
    OutlineHeading: {"id": "h", "content": "c", "level": "h2", "sort": 10},
    CaptureTaskResult: {
        "ok": True, "daily_note_id": "d", "notebook": "nb",
        "task": "t", "transactions": [],
    },
    WriteResult: {"ok": True, "transactions": [{"doOperations": []}]},
    DeleteBlockResult: {"ok": True, "already_absent": True, "transactions": []},
    DeleteDocResult: {
        "ok": True, "deleted_id": "d", "already_absent": False, "result": None,
    },
    SectionResult: {"ok": True, "action": "replaced", "heading_id": "h1"},
    DocUpsertResult: {
        "block_id": "d", "was_created": True, "was_updated": False, "hpath": "/h",
    },
    DocExistsResult: {"exists": True, "block_id": "d", "hpath": "/h"},
}


def test_notebook_defaults():
    """Notebook model has sensible defaults."""
    nb = Notebook(id="nb1", name="Test")
    assert nb.icon == ""
    assert nb.sort == 0
    assert nb.closed is False


def test_notebook_full():
    """Notebook model parses all fields."""
    nb = Notebook(id="nb1", name="Work", icon="1f4bc", sort=2, closed=True)
    assert nb.closed is True
    assert nb.sort == 2


def test_block_defaults():
    """Block model has sensible defaults."""
    b = Block(id="b1")
    assert b.type == ""
    assert b.content == ""
    assert b.parent_id == ""


def test_block_full():
    """Block model parses all fields."""
    b = Block(
        id="b1", type="p", content="hello", parent_id="doc1",
        root_id="root1", box="nb1", path="/test"
    )
    assert b.type == "p"
    assert b.root_id == "root1"


def test_search_result():
    """SearchResult model parses fields."""
    sr = SearchResult(id="b1", content="test", hpath="/notes/test")
    assert sr.hpath == "/notes/test"
    assert sr.box == ""


# --- Output-schema contract tests (deepen pass) ---------------------------
#
# These guard the backward-compat invariants the manually-synced Cloudflare
# portal + live clients depend on: top-level wire keys are preserved exactly,
# and every output model also validates an error payload.


@pytest.mark.parametrize(
    "model, payload",
    list(_SUCCESS_PAYLOADS.items()),
    ids=lambda x: x.__name__ if isinstance(x, type) else "",
)
def test_success_payload_preserves_top_level_keys(model, payload):
    """Each model round-trips the EXACT top-level keys the tool emits today.

    model_dump(by_alias=True) must contain every wire key with the same value;
    no key is renamed or dropped. (Extra schema-only fields like ``error`` may
    appear with their defaults — that's additive and allowed.)
    """
    instance = model(**payload)
    dumped = instance.model_dump(by_alias=True)
    for key, value in payload.items():
        assert key in dumped, f"{model.__name__} dropped wire key {key!r}"
        assert dumped[key] == value, (
            f"{model.__name__} changed wire key {key!r}: {dumped[key]!r} != {value!r}"
        )


@pytest.mark.parametrize(
    "model",
    list(_SUCCESS_PAYLOADS.keys()),
    ids=lambda m: m.__name__,
)
def test_error_payload_validates(model):
    """Every output model must validate a bare ``{"error": "..."}`` payload.

    This is the exact dual-validation bug fixed in mcp-zernio: a model used as an
    output_schema MUST accept the error path, not just the success path.
    """
    instance = model(error="boom")
    assert instance.error == "boom"


@pytest.mark.parametrize(
    "model",
    list(_SUCCESS_PAYLOADS.keys()),
    ids=lambda m: m.__name__,
)
def test_empty_payload_validates(model):
    """Every output model must validate an empty payload (all defaults)."""
    instance = model()  # must not raise — collection fields default, others Optional
    assert instance.error is None


def test_section_result_validates_append_variant():
    """SectionResult validates the append_to_section payload shape too."""
    inst = SectionResult(ok=True, heading_id="h1", anchor_id="p2")
    dumped = inst.model_dump()
    assert dumped["heading_id"] == "h1"
    assert dumped["anchor_id"] == "p2"


def test_write_result_preserves_kernel_passthrough():
    """WriteResult keeps SiYuan's notebook object verbatim via extra='allow'."""
    inst = WriteResult(**{"notebook": {"id": "nb1", "name": "Work"}})
    dumped = inst.model_dump()
    assert dumped["notebook"] == {"id": "nb1", "name": "Work"}
    assert dumped["ok"] is True  # additive default, harmless


def test_bulk_doc_result_success_and_error():
    """BulkDocResult validates both per-item ok and error rows."""
    ok = BulkDocResult(path="/a", block_id="id-a", status="ok", error=None)
    err = BulkDocResult(path="/b", block_id=None, status="error", error="conflict")
    assert ok.model_dump()["status"] == "ok"
    assert err.error == "conflict"
    assert BulkDocResult().status == "ok"  # empty payload validates


def test_bulk_attr_result_success_and_error():
    """BulkAttrResult validates both per-item ok and error rows."""
    ok = BulkAttrResult(block_id="b1", status="ok", error=None)
    err = BulkAttrResult(block_id="b2", status="error", error="bad attr")
    assert ok.model_dump()["block_id"] == "b1"
    assert err.error == "bad attr"
    assert BulkAttrResult().status == "ok"  # empty payload validates
