import random

import pytest

from atmosphere import (
    ORCH_HIT_PROGRAM,
    PAD_PROGRAM,
    find_accents,
    pad_voicing,
    stab_voicing,
    synth_double,
)
from motif import Motif, render_motif
from presets import load_all_presets
from structure import generate_section_content
from theory import Scale

# ---------------------------------------------------------------------------
# P7.1 -- GM 90 pad / 56 hit
# ---------------------------------------------------------------------------


def test_gm_program_constants():
    assert PAD_PROGRAM == 90
    assert ORCH_HIT_PROGRAM == 56


def test_pad_voicing_is_root_fifth_octave():
    assert pad_voicing(60) == [60, 67, 72]
    assert pad_voicing(40) == [40, 47, 52]


def test_stab_voicing_is_root_fifth_octave_minor_tenth():
    assert stab_voicing(60) == [60, 67, 72, 75]
    assert stab_voicing(40) == [40, 47, 52, 55]


def test_pad_and_stab_reject_bad_root():
    for bad in (None, "60", 60.0, [60], True, False):
        with pytest.raises(TypeError):
            pad_voicing(bad)
        with pytest.raises(TypeError):
            stab_voicing(bad)


# ---------------------------------------------------------------------------
# P7.2 -- synth doubles the motif
# ---------------------------------------------------------------------------


def _sample_motif() -> Motif:
    cell = [
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": True},
        {"duration": 0.5, "is_rest": False},
        {"duration": 1.0, "is_rest": False},
        {"duration": 0.5, "is_rest": False},
    ]
    return Motif(cell=cell, deltas=[0, 0, 2, -1])


def _contour(pitches: list[int]) -> list[int]:
    return [b - a for a, b in zip(pitches, pitches[1:])]


def test_synth_double_matches_guitar_contour_unison():
    motif = _sample_motif()
    scale = Scale(52, "minor")
    guitar_pitches = render_motif(motif, scale, start_degree=0)
    synth_pitches = synth_double(motif, scale, start_degree=0, transpose=0)
    assert synth_pitches == guitar_pitches
    assert _contour(synth_pitches) == _contour(guitar_pitches)


def test_synth_double_octave_up_preserves_contour():
    motif = _sample_motif()
    scale = Scale(52, "minor")
    guitar_pitches = render_motif(motif, scale, start_degree=0)
    synth_pitches = synth_double(motif, scale, start_degree=0, transpose=12)

    assert len(synth_pitches) == len(guitar_pitches)
    for g, s in zip(guitar_pitches, synth_pitches):
        assert s - g == 12
    # Exact same relative shape (interval sequence between consecutive
    # pitches), just transposed -- the actual P7.2 claim.
    assert _contour(synth_pitches) == _contour(guitar_pitches)


def test_synth_double_harmony_interval_preserves_contour():
    motif = _sample_motif()
    scale = Scale(52, "dorian")
    guitar_pitches = render_motif(motif, scale, start_degree=1)
    synth_pitches = synth_double(motif, scale, start_degree=1, transpose=7)

    for g, s in zip(guitar_pitches, synth_pitches):
        assert s - g == 7
    assert _contour(synth_pitches) == _contour(guitar_pitches)


def test_synth_double_end_to_end_with_real_section():
    tech = load_all_presets()["tech"]
    scale = Scale(52, tech.scale)
    content = generate_section_content(
        "breakdown", scale, random.Random(9), 16.0, [0.5, 1.0], 0.8, tech.vocab.weights,
    )
    motif = content["motif"]
    start_degree = content["arc"]["start_degree"]

    guitar_pitches = render_motif(motif, scale, start_degree=start_degree)
    synth_pitches = synth_double(motif, scale, start_degree=start_degree, transpose=12)

    assert len(synth_pitches) == len(guitar_pitches) == motif.hit_count
    assert _contour(synth_pitches) == _contour(guitar_pitches)


# ---------------------------------------------------------------------------
# P7.3 -- accent-synced hits
# ---------------------------------------------------------------------------


def test_find_accents_first_hit_is_always_accented():
    cell = [
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": False},
    ]
    accents = find_accents(cell, root=40)
    assert accents[0]["cell_index"] == 0
    assert accents[0]["voicing"] == stab_voicing(40)


def test_find_accents_marks_hit_after_long_rest():
    cell = [
        {"duration": 0.5, "is_rest": False},   # index 0: first hit -> accent
        {"duration": 0.5, "is_rest": False},   # index 1: no rest before -> not accent
        {"duration": 1.5, "is_rest": True},    # long rest (>= threshold 1.0)
        {"duration": 0.5, "is_rest": False},   # index 3: after long rest -> accent
        {"duration": 0.25, "is_rest": True},   # short rest (< threshold)
        {"duration": 0.5, "is_rest": False},   # index 5: after short rest -> not accent
    ]
    accents = find_accents(cell, root=40)
    indices = [a["cell_index"] for a in accents]
    assert indices == [0, 3]


def test_find_accents_all_rests_produces_zero_accents():
    cell = [{"duration": 0.5, "is_rest": True} for _ in range(6)]
    assert find_accents(cell, root=40) == []


def test_find_accents_empty_cell_produces_zero_accents():
    assert find_accents([], root=40) == []


def test_find_accents_rejects_bad_root():
    cell = [{"duration": 0.5, "is_rest": False}]
    with pytest.raises(TypeError):
        find_accents(cell, root=None)


def test_find_accents_rejects_negative_threshold():
    cell = [{"duration": 0.5, "is_rest": False}]
    with pytest.raises(ValueError):
        find_accents(cell, root=40, threshold=-1.0)


def test_find_accents_end_to_end_with_real_section():
    tech = load_all_presets()["tech"]
    scale = Scale(52, tech.scale)
    content = generate_section_content(
        "breakdown", scale, random.Random(3), 16.0, [0.5, 1.0], 0.9, tech.vocab.weights,
    )
    motif = content["motif"]
    accents = find_accents(motif.cell, root=40)

    # At least the first hit of the section must be marked, if the section
    # has any hits at all.
    if motif.hit_count > 0:
        hit_indices = [i for i, c in enumerate(motif.cell) if not c["is_rest"]]
        assert accents  # non-empty
        assert accents[0]["cell_index"] == hit_indices[0]
        for a in accents:
            assert a["voicing"] == stab_voicing(40)
    else:
        assert accents == []
