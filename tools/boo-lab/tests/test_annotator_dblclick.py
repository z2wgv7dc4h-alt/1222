"""Double-click = zoom + A-B loop, NEVER heard.

There is one behaviour (selectAndZoomBox) shared by the table row and the
WaveSurfer region; heard changes only via the row checkbox or ctxHeard.
"""
from __future__ import annotations

import re
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def _dblclick_bodies():
    """Each `dblclick` occurrence with the statement that follows it (to `};`
    for a block handler, else the rest of the line)."""
    text = _text()
    for m in re.finditer(r"dblclick", text, re.IGNORECASE):
        tail = text[m.start():m.start() + 400]
        cut = tail.find("};")
        yield tail[:cut + 2] if cut != -1 else tail.split("\n", 1)[0]


def test_no_dblclick_handler_touches_heard():
    for body in _dblclick_bodies():
        assert "heard" not in body.lower(), body


def test_both_dblclick_paths_use_the_same_zoom_loop_helper():
    text = _text()

    row = re.search(r"ondblclick\s*=\s*ev\s*=>\s*\{(.*?)\};", text, re.S)
    assert row and "selectAndZoomBox" in row.group(1)

    region = re.search(r'region-double-clicked"?,\s*\(reg\)\s*=>\s*\{(.*?)\}\);', text, re.S)
    assert region and "selectAndZoomBox" in region.group(1)
