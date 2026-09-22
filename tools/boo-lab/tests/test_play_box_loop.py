"""Taller section-table strip; Play box lights (and stops) while looping."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_table_strip_is_taller():
    assert "grid-template-rows:1fr minmax(160px, 28vh)" in _text()


def test_loop_lights_the_play_box():
    text = _text()
    start = text[text.index("function startBoxLoop("):]
    start = start[:start.index("\n}")]
    stop = text[text.index("function stopBoxLoop("):]
    stop = stop[:stop.index("\n}")]

    assert 'classList.add("on")' in start
    assert "looping" in start and "click to stop" in start
    assert 'classList.remove("on")' in stop


def test_play_box_click_stops_an_armed_loop():
    text = _text()

    assert "if(window._boxLoop){" in text
    assert "stopBoxLoop(); try{ ws&&ws.pause(); }" in text
    assert "playBox();  // no loop: unchanged one-shot" in text


def test_user_mark_says_play_box_lights():
    user = (LAB / "USER.md").read_text(encoding="utf-8")

    assert "Play box lights while looping" in user
