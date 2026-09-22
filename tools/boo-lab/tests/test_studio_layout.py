"""Studio layout + load: one-row grid, lazy spectrogram, quiet next-act."""
from __future__ import annotations

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HTML = LAB / "src" / "boo_lab" / "static" / "annotator.html"


def _text() -> str:
    return HTML.read_text(encoding="utf-8")


def test_no_phantom_second_grid_row():
    text = _text()

    assert "grid-template-rows:1fr;" in text
    assert "minmax(160px" not in text
    assert "min-height:0; padding:0 24px 16px;" in text   # main owns the scroll


def test_spectrogram_is_lazy_never_on_ready():
    text = _text()
    ready = text[text.index('ws.on("ready"'):]
    ready = ready[:ready.index('ws.on("error"')]

    assert "buildSpec()" not in ready
    assert 'if(m!=="wave") buildSpec();' in text            # opens on a spec view
    assert "buildSpec();  // user asked for a spec zoom" in text


def test_next_act_has_no_infinite_animation():
    text = _text()

    assert "@keyframes nextpulse" not in text
    assert "animation:nextpulse" not in text
    assert ".next-act { outline:2px solid var(--gold); outline-offset:2px; }" in text


def test_default_err_says_breakdown():
    text = _text()

    assert "3 breakdown T blast" in text
    assert "3 slam" not in text
