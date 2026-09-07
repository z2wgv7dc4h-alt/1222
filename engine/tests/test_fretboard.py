import pytest

from engine.fretboard import Fretboard

STANDARD_6 = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4
DROP_G_7 = [31, 38, 43, 48, 53, 57, 62]  # Born of Osiris "Discovery" tuning


def test_fret_to_midi_basic():
    fb = Fretboard(STANDARD_6)
    assert fb.fret_to_midi(0, 3) == 43  # low E, 3rd fret = G2
    assert fb.fret_to_midi(5, 0) == 64  # open high E


def test_midi_to_frets_basic():
    fb = Fretboard(STANDARD_6)
    positions = fb.midi_to_frets(55)  # open G string, also reachable elsewhere
    assert (3, 0) in positions
    for string, fret in positions:
        assert fb.fret_to_midi(string, fret) == 55


def test_midi_to_frets_unreachable_returns_empty():
    fb = Fretboard(STANDARD_6)
    assert fb.midi_to_frets(20) == []


def test_fret_to_midi_invalid_string_raises():
    fb = Fretboard(STANDARD_6)
    with pytest.raises(ValueError):
        fb.fret_to_midi(6, 0)
    with pytest.raises(ValueError):
        fb.fret_to_midi(-1, 0)


def test_fret_to_midi_invalid_fret_raises():
    fb = Fretboard(STANDARD_6)
    with pytest.raises(ValueError):
        fb.fret_to_midi(0, -1)
    with pytest.raises(ValueError):
        fb.fret_to_midi(0, 25)


def test_extended_range_tuning():
    fb = Fretboard(DROP_G_7)
    assert fb.fret_to_midi(0, 0) == 31
    assert fb.fret_to_midi(6, 0) == 62
    assert (0, 0) in fb.midi_to_frets(31)


def test_pitch_to_fret_prefers_lowest_string_with_no_prev():
    fb = Fretboard(STANDARD_6)
    # 55 = open G (string 3, fret 0) but also reachable on string 0 fret 15 (out of window)
    # and string 1 fret 10, string 2 fret 5 -- lowest string among in-window candidates wins.
    assert fb.pitch_to_fret(55) == (1, 10)


def test_pitch_to_fret_minimizes_cost_from_prev():
    fb = Fretboard(STANDARD_6)
    # From (3, 5) [G string, 5th fret = C4/60], moving to 62 (D4):
    # string 3 fret 7 costs |7-5|=2; string 4 fret 3 costs |3-5|+2=4 -> stay on string 3.
    assert fb.pitch_to_fret(62, prev=(3, 5)) == (3, 7)


def test_pitch_to_fret_rejects_unplayable_midi():
    fb = Fretboard(STANDARD_6)
    with pytest.raises(ValueError):
        fb.pitch_to_fret(20)  # far below the lowest open string
    with pytest.raises(ValueError):
        fb.pitch_to_fret(120)  # far above any string within the search window
