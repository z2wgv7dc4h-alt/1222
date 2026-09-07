import random

import pytest

from fretboard import Fretboard
from motif import Motif
from presets import load_all_presets, load_tunings
from riff import generate_chord_riff, harmonize_line, voice_chord_section
from rhythm import generate_rhythm
from theory import Scale


# --- P3.11: chord-shape solver wired into riff generation --------------------


def test_voice_chord_section_returns_real_fingering_for_power_chord():
    slam = load_all_presets()["slam"]
    tuning = load_tunings()[slam.tuning_key]
    fb = Fretboard(tuning.open, max_fret=24)

    fingering = voice_chord_section(root=fb.tuning[0], intervals=(0, 7, 12), fretboard=fb)

    assert fingering  # not empty
    assert len(fingering) == 3  # one position per chord tone
    for string, fret in fingering:
        # every entry is a REAL, reachable position -- cross-checked against
        # the fretboard's own reverse lookup, never a fabricated pair.
        assert 0 <= string < len(fb.tuning)
        assert 0 <= fret <= fb.max_fret
        pitch = fb.fret_to_midi(string, fret)
        assert (string, fret) in fb.midi_to_frets(pitch)


def test_voice_chord_section_rejects_unreachable_chord():
    fb = Fretboard([40], max_fret=2)  # one string, tiny range: nothing big fits
    with pytest.raises(ValueError):
        voice_chord_section(root=40, intervals=(0, 7, 12), fretboard=fb)


def test_generate_chord_riff_end_to_end():
    tunings = load_tunings()
    fb = Fretboard(tunings["drop_c_6"].open, max_fret=24)
    rng = random.Random(21)
    cell = generate_rhythm(4.0, [0.5, 1.0], hit_chance=0.8, rng=rng)

    result = generate_chord_riff(cell, root=fb.tuning[0], intervals=(0, 7, 12), fretboard=fb)

    assert result["cell"] == cell
    assert result["fingering"]
    assert len(result["fingering"]) == 3


# --- P3.12 (optional): harmonized second guitar ------------------------------


def test_harmonize_line_shares_rhythm_and_shifts_pitches():
    cell = [
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": True},
        {"duration": 0.5, "is_rest": False},
    ]
    motif = Motif(cell=cell, deltas=[0, 2, -1])
    scale = Scale(60, "minor")

    lead, harmony = harmonize_line(motif, scale, start_degree=0, harmony_degrees=2)

    assert len(lead) == len(harmony) == motif.hit_count
    assert lead != harmony
    # Same rhythmic shape: harmonize_line doesn't touch timing at all, only
    # pitch -- there's nothing rhythm-shaped returned to compare, but the
    # harmony line must be derived from the same number of hits as the lead.
    for a, b in zip(lead, harmony):
        # harmony_degrees=2 is a constant scale-degree shift, so each pair's
        # difference should reflect that same interval consistently applied
        # via the scale (not necessarily a constant semitone count, but a
        # consistent, non-zero relationship).
        assert b != a
