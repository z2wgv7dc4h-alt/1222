import pytest

from fretboard import Fretboard
from slam import chromatic_creep, mark_pinch_harmonics


DROP_C_6 = [36, 43, 48, 53, 57, 62]  # matches presets/tunings.json drop_c_6


def _plain_chug(n=4):
    return [{"duration": 0.5, "is_rest": False} for _ in range(n)]


# --- (a) pinch harmonic accent -----------------------------------------------


def test_mark_pinch_harmonics_flags_only_the_last_hit():
    chug = _plain_chug(4)
    marked = mark_pinch_harmonics(chug)
    assert len(marked) == len(chug)
    for c in marked[:-1]:
        assert c["pinch_harmonic"] is False
    assert marked[-1]["pinch_harmonic"] is True
    assert marked[-1]["velocity"] > marked[0]["velocity"]


def test_mark_pinch_harmonics_differs_from_plain_chug():
    chug = _plain_chug(4)
    marked = mark_pinch_harmonics(chug)
    # A plain chug has no pinch/velocity distinction at all -- marking must
    # introduce a structural difference (a velocity spike + flag) the plain
    # pattern never has.
    assert "pinch_harmonic" not in chug[0]
    assert any(c["pinch_harmonic"] for c in marked)
    velocities = {c["velocity"] for c in marked}
    assert len(velocities) == 2  # base velocity + the spike


def test_mark_pinch_harmonics_skips_rests_for_the_accent():
    cell = [
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": True},
    ]
    marked = mark_pinch_harmonics(cell)
    assert marked[-1]["is_rest"] is True
    assert marked[-1]["pinch_harmonic"] is False  # the rest is never accented
    assert marked[0]["pinch_harmonic"] is True  # the last actual hit is


def test_mark_pinch_harmonics_handles_all_rests():
    cell = [{"duration": 0.5, "is_rest": True}] * 3
    marked = mark_pinch_harmonics(cell)
    assert not any(c["pinch_harmonic"] for c in marked)


# --- (b) low open-string chromatic creep -------------------------------------


def test_chromatic_creep_produces_real_increasing_fret_positions():
    fb = Fretboard(DROP_C_6, max_fret=24)
    positions = chromatic_creep(fb, string=0, steps=6, direction=1, start_fret=0)
    assert len(positions) == 6
    frets = [fret for _string, fret in positions]
    assert frets == sorted(frets)  # monotonically creeping upward
    assert len(set(frets)) == len(frets)  # one semitone step each time, no repeats
    # every position must be genuinely reachable on this fretboard
    for string, fret in positions:
        assert fb.fret_to_midi(string, fret) is not None


def test_chromatic_creep_differs_from_plain_chug():
    fb = Fretboard(DROP_C_6, max_fret=24)
    creep = chromatic_creep(fb, string=0, steps=5, direction=1, start_fret=0)
    chug_positions = [(0, 0)] * 5  # a plain chug: same fret held throughout
    creep_frets = [f for _s, f in creep]
    chug_frets = [f for _s, f in chug_positions]
    assert creep_frets != chug_frets
    assert len(set(creep_frets)) > 1
    assert len(set(chug_frets)) == 1


def test_chromatic_creep_rejects_unreachable_walk():
    fb = Fretboard(DROP_C_6, max_fret=24)
    with pytest.raises(ValueError):
        # Walking down from an open string goes negative -- unreachable
        # anywhere on this fretboard, must fail closed rather than fabricate
        # a position.
        chromatic_creep(fb, string=0, steps=2, direction=-1, start_fret=0)


def test_chromatic_creep_rejects_bad_input():
    fb = Fretboard(DROP_C_6, max_fret=24)
    with pytest.raises(ValueError):
        chromatic_creep(fb, string=99, steps=3)
    with pytest.raises(ValueError):
        chromatic_creep(fb, string=0, steps=0)
    with pytest.raises(ValueError):
        chromatic_creep(fb, string=0, steps=3, direction=2)
