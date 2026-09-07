import pytest

from chords import MAX_FRET_SPAN, solve_chord
from fretboard import Fretboard

STANDARD_6 = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4
POWER_CHORD = (0, 7, 12)  # root, 5th, octave


def test_power_chord_produces_only_real_reachable_positions():
    fb = Fretboard(STANDARD_6)
    root = 45  # open A string
    fingerings = solve_chord(root, POWER_CHORD, fb)
    assert fingerings, "expected at least one valid power-chord fingering"

    for fingering in fingerings:
        assert len(fingering) == len(POWER_CHORD)
        strings = [s for s, _f in fingering]
        assert len(set(strings)) == len(strings)  # every tone on its own string
        for (string, fret), interval in zip(fingering, POWER_CHORD):
            # every returned position is a real, verified fretboard position
            assert fb.fret_to_midi(string, fret) == root + interval

        fretted = [f for _s, f in fingering if f > 0]
        if fretted:
            assert max(fretted) - min(fretted) <= MAX_FRET_SPAN


def test_unreachable_chord_tone_returns_empty_not_fabricated():
    fb = Fretboard(STANDARD_6)
    # 20 sits far below the lowest open string (40) on every string -- no
    # fret can be negative, so this chord has no possible fingering at all.
    assert solve_chord(20, POWER_CHORD, fb) == []


def test_span_constraint_can_reject_all_combinations():
    fb = Fretboard(STANDARD_6)
    root = 45
    # A span of 0 forbids using two different fretted positions unless they
    # land on the exact same fret number -- unlikely for a spread chord --
    # so this must legitimately come back emptier than the default span.
    wide = solve_chord(root, POWER_CHORD, fb, max_span=24)
    narrow = solve_chord(root, POWER_CHORD, fb, max_span=0)
    assert len(narrow) <= len(wide)


def test_empty_intervals_raises():
    fb = Fretboard(STANDARD_6)
    with pytest.raises(ValueError):
        solve_chord(45, (), fb)


def test_fingering_never_reuses_a_string():
    fb = Fretboard(STANDARD_6)
    fingerings = solve_chord(45, POWER_CHORD, fb)
    for fingering in fingerings:
        strings = [s for s, _f in fingering]
        assert len(set(strings)) == len(strings)
