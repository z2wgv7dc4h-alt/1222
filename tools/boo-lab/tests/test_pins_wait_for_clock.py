"""Role pins/keys wait for a real duration; no box while clock is 0:00."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_pins_are_disabled_and_muted_until_ready():
    text = _text()
    fn = text[text.index("function setPinsReady("):]
    fn = fn[:fn.index("\n}")]

    assert "b.disabled=!on" in fn
    assert 'classList.toggle("muted", !on)' in fn
    assert ".pins button:disabled" in text and ".muted" in text


def test_pins_ready_uses_the_clock_and_duration():
    text = _text()
    fn = text[text.index("function pinsReady("):]
    fn = fn[:fn.index("\n}")]

    assert "getDuration" in fn
    assert "0:00" in fn


def test_set_pins_ready_runs_on_load_new_song_and_ready():
    assert _text().count("setPinsReady();") >= 3


def test_role_keys_no_op_before_the_clock():
    text = _text()

    assert 'showErr("wait for the clock")' in text
    assert 'if(!pinsReady()){ showErr("wait for the clock"); return; }' in text


def test_role_key_map_covers_the_nine_keys():
    text = _text()
    seg = text[text.index("const roleKey={"):]
    seg = seg[:seg.index("}[e.key]")]

    for binding in ('"1":"riff"', '"2":"hook"', '"3":"breakdown"', '"t":"blast"',
                    '"T":"blast"', '"4":"solo"', '"i":"intro"', '"I":"intro"',
                    '"b":"build"', '"B":"build"', '"c":"chill"', '"C":"chill"',
                    '"p":"pulse"', '"P":"pulse"'):
        assert binding in seg
