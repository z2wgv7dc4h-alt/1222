"""First-session coach: one next action, one next-act highlight, new pin loops."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_coach_has_every_state_sentence():
    text = _text()

    for sentence in (
        "Pick a numbered track. Skip mix / album for the first song.",
        "Wait for the clock. Pins stay off until the length appears.",
        "Press 1 (riff) or another role. Drag does not create a box.",
        "Double-click the bar to loop it.",
        "Tick heard on that row.",
        "unheard boxes will be dropped.",
        "keepers on this song. Next part, or J / K for another track.",
    ):
        assert sentence in text, sentence


def test_coach_uses_pins_ready_and_dirty_state():
    text = _text()

    assert "function coach(" in text
    assert "pinsReady()" in text
    assert "window._dirty" in text
    assert "window._lastSaved" in text


def test_highlight_next_marks_exactly_the_control():
    text = _text()
    fn = text[text.index("function highlightNext("):]
    fn = fn[:fn.index("\n}")]

    assert ".next-act" in fn
    assert "data-role='riff'" in fn
    assert '"btnPlayBox"' in fn
    assert "data-f='heard'" in fn
    assert '"btnSave"' in fn
    assert ".next-act {" in text


def test_new_pin_starts_its_loop():
    text = _text()
    add = text[text.index("function add(role){"):]
    add = add[:add.index("document.querySelectorAll(\".pins button\")")]

    assert "startBoxLoop(sel)" in add


def test_dirty_is_set_by_edits_and_cleared_by_save():
    text = _text()

    assert "window._dirty=true;" in text
    save = text[text.index("function save(){"):]
    save = save[:save.index("function nextGreen()")]
    assert "window._dirty=false" in save
    assert "window._lastSaved=+x.saved||0" in save


def test_user_part_a_says_new_box_loops_and_coach():
    user = (LAB / "USER.md").read_text(encoding="utf-8")

    assert "A new box starts its loop at once" in user
    assert "coach line under the pins" in user
