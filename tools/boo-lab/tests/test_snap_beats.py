"""Snap beats: off by default; refused for off-clock / mix / album-file rows."""
from __future__ import annotations

import re
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_snap_checkbox_defaults_unchecked():
    tag = re.search(r'<input[^>]*id="snapBeat"[^>]*>', _text()).group(0)

    assert "checked" not in tag


def test_snap_tooltip_names_the_refusal():
    assert "Off by default. Disabled when the tab is off-clock" in _text()


def test_snap_blocked_for_off_clock_mix_album():
    text = _text()
    fn = text[text.index("function applySnapAvailability("):]
    fn = fn[:fn.index("\n}")]

    assert "t.off_clock" in fn and "t.mix" in fn and "t.album_file" in fn
    assert "cb.disabled=blocked" in fn
    assert "cb.checked=false" in fn
    assert "applySnapAvailability(t);" in text   # wired on select
    assert "on.disabled" in text                 # snapTime no-op guard


def test_user_doc_mentions_snap_off():
    user = (LAB / "USER.md").read_text(encoding="utf-8")

    assert "Snap starts off" in user
