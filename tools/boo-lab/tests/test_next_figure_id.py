"""New box gets the next free figure letter (A–Z), never silently reuses A."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


# --- python mirror of the JS helper -----------------------------------------


def next_figure_id(role, existing):
    used = set()
    for raw in existing or []:
        s = str(raw or "")
        if not s.startswith(role + "-"):
            continue
        suffix = s[len(role) + 1:]
        if suffix and all("A" <= ch <= "Z" for ch in suffix):
            used.add(suffix)
    for i in range(26):
        c = chr(65 + i)
        if c not in used:
            return role + "-" + c
    n = 26
    while True:
        m, s = n, ""
        while True:
            s = chr(65 + (m % 26)) + s
            m = m // 26 - 1
            if m < 0:
                break
        if s not in used:
            return role + "-" + s
        n += 1


def test_first_box_is_a():
    assert next_figure_id("riff", []) == "riff-A"


def test_next_letter_when_a_is_taken():
    assert next_figure_id("riff", ["riff-A"]) == "riff-B"
    assert next_figure_id("riff", ["riff-A", "riff-B", "riff-C"]) == "riff-D"


def test_other_roles_do_not_count():
    assert next_figure_id("riff", ["hook-A", "breakdown-A"]) == "riff-A"


def test_function_roles_use_their_own_prefix():
    assert next_figure_id("breakdown", ["breakdown-A"]) == "breakdown-B"
    assert next_figure_id("blast", []) == "blast-A"      # never riff-blast-A


def test_non_letter_suffixes_are_ignored():
    assert next_figure_id("riff", ["riff-C1", "riff-a"]) == "riff-A"


def test_all_a_to_z_exhausted_moves_to_aa():
    existing = ["riff-" + chr(65 + i) for i in range(26)]
    assert next_figure_id("riff", existing) == "riff-AA"


# --- the JS side -------------------------------------------------------------


def test_js_helper_exists_and_is_used_for_new_boxes():
    text = _text()

    assert "function nextFigureId(" in text
    assert "figure_id:nextFigureId(role, regs.map(p=>p.figure_id))" in text
    assert "/^[A-Z]+$/" in text                     # suffix is letters only
    assert "list='figureSuggests'" in text          # reuse by typing still works


def test_user_mark_step_5_says_next_letter():
    user = (LAB / "USER.md").read_text(encoding="utf-8")

    assert "next letter by default" in user
    assert "type the old id" in user
