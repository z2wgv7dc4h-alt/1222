"""Corpus buttons: typed album-remove confirm; git push labels-only wording."""
from __future__ import annotations

import re
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"
ANNOTATOR = LAB / "src" / "boo_lab" / "annotator.py"
# em dash or hyphen; content is what matters
PHRASE_RE = re.compile(r"labels only . no FLACs, no map\.csv")


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_git_button_tooltip_and_status_say_labels_only():
    text = _text()
    button = text[text.index('id="btnGit"'):]
    button = button[:button.index(">")]

    assert PHRASE_RE.search(button)          # tooltip
    assert len(PHRASE_RE.findall(text)) >= 2  # tooltip + status line


def test_album_remove_requires_typed_name():
    text = _text()
    handler = text[text.index('getElementById("btnRemoveAlbum").onclick'):]
    handler = handler[:handler.index('showErr("removing album')]

    assert "prompt(" in handler
    assert "confirm('Remove album" not in text
    assert "typed===null" in handler                    # cancel -> no-op
    assert '!==String(t.album||"").trim().toLowerCase()' in handler  # mismatch -> no-op


def test_server_keeps_root_containment_checks():
    text = ANNOTATOR.read_text(encoding="utf-8")

    assert "_within(p, root)" in text
    assert 'if not (body or {}).get("confirm"):' in text
