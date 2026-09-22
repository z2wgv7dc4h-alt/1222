"""The studio #howto panel is the Part A Mark list, not Guess theology.

Copy-only: no CSS/ID/JS behaviour is asserted here.
"""
from __future__ import annotations

from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def _howto() -> str:
    text = _text()
    start = text.index('id="howto"')
    return text[start:text.index("</aside>", start)]


def test_howto_never_says_do_not_pin_val():
    assert "do not pin val" not in _text().lower()


def test_howto_mentions_heard():
    assert "heard" in _howto()


def test_howto_mentions_the_ab_loop():
    panel = _howto()
    assert "A–B" in panel or "A-B" in panel


def test_howto_does_not_toggle_heard():
    assert "toggle heard" not in _howto().lower()
