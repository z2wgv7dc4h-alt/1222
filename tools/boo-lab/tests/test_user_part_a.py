"""USER.md Part A invariants: one double-click story, one VAL paragraph.

Part B is out of scope here; only the working half is pinned.
"""
from __future__ import annotations

from pathlib import Path

USER = Path(__file__).resolve().parents[1] / "USER.md"


def _text() -> str:
    return USER.read_text(encoding="utf-8")


def _part_a() -> str:
    text = _text()
    return text[text.index("# Part A"):text.index("# Part B")]


def test_part_a_has_exactly_one_val_paragraph():
    assert _part_a().count("VAL songs do not train and do not vote prefer=") == 1


def test_double_click_never_toggles_heard():
    assert "Double-click a bar to toggle heard" not in _text()
    assert "heard" in _part_a() and "right-click menu" in _part_a()


def test_open_section_carries_no_intern_step_list():
    open_sec = _part_a().split("## Open", 1)[1].split("## Mark", 1)[0]

    assert "Double-click START.bat. Browser opens. Prep may run in another window; ignore it." in open_sec
    assert "SongFormer" not in open_sec
    assert "PREP.bat" not in open_sec
    assert "python -m boo_lab.cli" not in open_sec


def test_how_pointer_and_val_is_pinnable():
    a = _part_a()

    assert "The **How** button in studio is this Mark list" in a
    assert "do not pin VAL" not in _text().lower()
