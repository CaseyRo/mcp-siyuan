"""Tests for Pydantic models."""

from mcp_siyuan.models import Block, Notebook, SearchResult


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
