"""While dragging/resizing, same-role >50ms overlap is painted `.overlap-bad`.

Paint only: Save still refuses via schema.same_role_overlap_pairs, same 50 ms.
"""
from __future__ import annotations

from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_overlap_bad_class_is_styled():
    assert ".overlap-bad" in _text()


def test_paint_helper_uses_the_50ms_save_rule():
    text = _text()

    assert "const OVERLAP_EPS = 0.05;" in text
    assert "function paintOverlap(" in text
    assert "a.role!==b.role" in text                    # different roles stay legal
    assert "same_role_overlap_pairs" in text            # comment points at Save's rule


def test_paint_runs_during_drag_and_on_repaint():
    text = _text()

    assert "paintOverlap();  // live same-role" in text  # region-updated
    assert 'classList.toggle("overlap-bad"' in text
    assert text.count("paintOverlap();") >= 3            # updated + repaint + pointerup
