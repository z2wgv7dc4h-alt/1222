"""Draft source is visible on the row without opening More columns.

The table row builder (JS) appends a muted `sourcePip`; keepers stay unmarked.
"""
from __future__ import annotations

from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def _source_pip_fn() -> str:
    text = _text()
    start = text.index("function sourcePip(")
    return text[start:text.index("\n}", start)]


def test_row_builder_appends_the_source_pip():
    # cFig (nth-child 2) is always visible, unlike the .extra source cell.
    assert "sourcePip(p.source)" in _text()


def test_source_pip_marks_drafts_but_not_keepers():
    fn = _source_pip_fn()

    assert '"human"' in fn and '"guess-accepted"' in fn
    assert "srcpip" in fn
    assert 'return ""' in fn          # keepers: empty
    assert "guess" in fn              # a draft short label exists


def test_source_pip_has_a_muted_style():
    assert ".srcpip" in _text()
