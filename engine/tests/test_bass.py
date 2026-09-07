import random

import pytest

from bass import (
    build_bass_fretboard,
    derive_bass_tuning,
    follow_guitar_rhythm,
)
from fretboard import Fretboard
from rhythm import generate_rhythm

STANDARD_6 = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4
DROP_G_7 = [31, 38, 43, 48, 53, 57, 62]  # Born of Osiris "Discovery" tuning


# --- P5.1: bass's own 4/5-string fretboard, derived from a guitar tuning ---


@pytest.mark.parametrize("guitar_open", [DROP_G_7, STANDARD_6])
def test_derive_bass_tuning_4_string_is_lower_than_guitar(guitar_open):
    bass_open = derive_bass_tuning(guitar_open, strings=4)
    assert len(bass_open) == 4
    assert all(note < min(guitar_open) for note in bass_open)
    # ascending (low string to high string), matching this project's
    # tuning convention (presets/tunings.json: index 0 is the lowest string)
    assert bass_open == sorted(bass_open)


@pytest.mark.parametrize("guitar_open", [DROP_G_7, STANDARD_6])
def test_derive_bass_tuning_not_a_copy_of_guitar(guitar_open):
    bass_open = derive_bass_tuning(guitar_open, strings=4)
    assert bass_open != guitar_open[:4]
    assert bass_open != [n - 12 for n in guitar_open[:4]]


def test_derive_bass_tuning_5_string_adds_one_lower_fourth():
    bass_4 = derive_bass_tuning(STANDARD_6, strings=4)
    bass_5 = derive_bass_tuning(STANDARD_6, strings=5)
    assert len(bass_5) == 5
    # top 4 strings of the 5-string variant match the 4-string variant
    assert bass_5[1:] == bass_4
    # the new low string is a perfect 4th (5 semitones) below the old lowest
    assert bass_4[0] - bass_5[0] == 5
    assert all(note < min(STANDARD_6) for note in bass_5)


def test_derive_bass_tuning_rejects_bad_string_count():
    with pytest.raises(ValueError):
        derive_bass_tuning(STANDARD_6, strings=6)
    with pytest.raises(ValueError):
        derive_bass_tuning(STANDARD_6, strings=0)


def test_derive_bass_tuning_rejects_empty_guitar_tuning():
    with pytest.raises(ValueError):
        derive_bass_tuning([], strings=4)


@pytest.mark.parametrize("guitar_open", [DROP_G_7, STANDARD_6])
@pytest.mark.parametrize("strings", [4, 5])
def test_bass_fretboard_roundtrips_like_any_fretboard(guitar_open, strings):
    fb = build_bass_fretboard(guitar_open, strings=strings)
    assert isinstance(fb, Fretboard)
    assert len(fb.tuning) == strings
    for string in range(strings):
        for fret in (0, 3, 7, 12):
            midi = fb.fret_to_midi(string, fret)
            assert (string, fret) in fb.midi_to_frets(midi)


# --- P5.2: bass follows the guitar's rhythm, but resolves pitch on its own fretboard ---


def _guitar_rhythm_and_pitches(seed: int, scale_tones: list[int]):
    rng = random.Random(seed)
    cells = generate_rhythm(8.0, [0.5, 1.0], hit_chance=0.7, rng=rng)
    pitches: list[int | None] = []
    tone_i = 0
    for cell in cells:
        if cell["is_rest"]:
            pitches.append(None)
        else:
            pitches.append(scale_tones[tone_i % len(scale_tones)])
            tone_i += 1
    return cells, pitches


def test_follow_guitar_rhythm_matches_hit_rest_pattern():
    bass_fb = build_bass_fretboard(STANDARD_6, strings=4)
    guitar_scale_tones = [64, 67, 69, 71, 72, 74]  # some guitar-register pitches
    cells, pitches = _guitar_rhythm_and_pitches(seed=7, scale_tones=guitar_scale_tones)

    bass_line = follow_guitar_rhythm(cells, pitches, bass_fb)

    assert len(bass_line) == len(cells)
    assert [c["is_rest"] for c in bass_line] == [c["is_rest"] for c in cells]
    assert [c["duration"] for c in bass_line] == [c["duration"] for c in cells]


def test_follow_guitar_rhythm_hits_are_real_playable_positions():
    bass_fb = build_bass_fretboard(STANDARD_6, strings=4)
    guitar_scale_tones = [64, 67, 69, 71, 72, 74]
    cells, pitches = _guitar_rhythm_and_pitches(seed=7, scale_tones=guitar_scale_tones)

    bass_line = follow_guitar_rhythm(cells, pitches, bass_fb)

    for cell in bass_line:
        if cell["is_rest"]:
            assert cell["string"] is None
            assert cell["fret"] is None
            assert cell["midi"] is None
            continue
        # every hit must round-trip through the BASS fretboard exactly like
        # any other real (string, fret) -- never fabricated
        assert bass_fb.fret_to_midi(cell["string"], cell["fret"]) == cell["midi"]
        assert (cell["string"], cell["fret"]) in bass_fb.midi_to_frets(cell["midi"])


def test_follow_guitar_rhythm_rejects_length_mismatch():
    bass_fb = build_bass_fretboard(STANDARD_6, strings=4)
    cells = [{"duration": 1.0, "is_rest": False}]
    with pytest.raises(ValueError):
        follow_guitar_rhythm(cells, [], bass_fb)


def test_follow_guitar_rhythm_rejects_hit_with_no_pitch():
    bass_fb = build_bass_fretboard(STANDARD_6, strings=4)
    cells = [{"duration": 1.0, "is_rest": False}]
    with pytest.raises(ValueError):
        follow_guitar_rhythm(cells, [None], bass_fb)


def test_follow_guitar_rhythm_falls_back_to_nearest_reachable_octave():
    """Constructed edge case (P5.2c): the guitar's exact octave (pitch - 12)
    is nowhere near this narrow bass fretboard's reachable range, so the
    naive "just transpose down an octave" approach would be unplayable --
    but the SAME pitch class is reachable in a lower octave, and that is
    what must be picked, without raising or fabricating a position."""
    # tuning = [13, 18, 23, 28], max_fret=5 -> reachable MIDI span is 13..33
    bass_fb = Fretboard([13, 18, 23, 28], max_fret=5)

    guitar_pitch = 70  # pitch class 10 (Bb); pitch - 12 = 58, far out of reach
    cells = [{"duration": 1.0, "is_rest": False}]

    bass_line = follow_guitar_rhythm(cells, [guitar_pitch], bass_fb, max_fret=5)

    hit = bass_line[0]
    assert hit["is_rest"] is False
    assert hit["midi"] % 12 == guitar_pitch % 12
    # actually playable: round-trips through the bass fretboard
    assert bass_fb.fret_to_midi(hit["string"], hit["fret"]) == hit["midi"]
    # and it really did fall back to a different octave than the naive one
    assert hit["midi"] != guitar_pitch - 12


def test_follow_guitar_rhythm_raises_when_pitch_class_truly_unreachable():
    """Bad-input case that fails closed: with max_fret=0 every string can
    only sound its own open note's pitch class, so a pitch class none of
    the open strings has is unreachable at ANY octave -- this must raise,
    never fabricate a position."""
    bass_fb = Fretboard([24, 24, 24, 24], max_fret=0)  # every string open = C (pitch class 0)
    cells = [{"duration": 1.0, "is_rest": False}]
    guitar_pitch = 66  # pitch class 6 (F#) -- never reachable on this fretboard

    with pytest.raises(ValueError):
        follow_guitar_rhythm(cells, [guitar_pitch], bass_fb, max_fret=0)
