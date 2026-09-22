"""Heard warns when a box was not looped this session; it never refuses.

Session-only JS Set; nothing is written to sections.jsonl.
"""
from __future__ import annotations

from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "src" / "boo_lab" / "static" / "annotator.html"
WARN = "heard without a loop this session"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_warning_text_is_present():
    assert WARN in _text()


def test_session_looped_set_and_helpers_exist():
    text = _text()

    assert "window._looped" in text
    assert "function markLooped(" in text
    assert "function heardUnlooped(" in text


def test_a_completed_loop_marks_the_box():
    text = _text()

    assert "markLooped(L.idx)" in text              # A-B wrap
    assert "markLooped(window._playBoxIdx)" in text  # full one-shot Play box pass


def test_heard_still_sets_and_only_warns():
    text = _text()
    seg = text[text.index('if(f==="heard")'):]
    seg = seg[:seg.index("return;")]

    assert "p.heard=!!inp.checked;" in seg   # still saves, never blocks
    assert WARN in seg
