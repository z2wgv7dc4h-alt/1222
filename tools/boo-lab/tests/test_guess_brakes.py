"""Guess refuses off-clock / mix / album-file (JS brake + USER doc)."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def test_js_estimate_refuses_the_three_rows():
    text = _html()
    fn = text[text.index("function estimate("):]
    fn = fn[:fn.index("const finished=")]

    assert "t.off_clock" in fn and "off-clock" in fn and "pin by ear" in fn
    assert "t.mix" in fn and "do not Guess" in fn
    assert "t.album_file" in fn and "album file" in fn and "pin the numbered track" in fn


def test_user_doc_lists_the_refuses():
    user = (LAB / "USER.md").read_text(encoding="utf-8")

    assert "Guess refuses off-clock" in user
    assert "pin the numbered track" in user
