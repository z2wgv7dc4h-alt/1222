import pytest

from motif import Motif
from progression import (
    CHORUS_PROGRESSIONS,
    VERSE_PROGRESSIONS,
    degree_for_bar,
    pitches_per_cell_with_progression,
    render_motif_with_progression,
)
from theory import Scale


def test_degree_for_bar_wraps_past_table_length():
    progression = [0, 0, 5, 4]
    assert degree_for_bar(progression, 0) == 0
    assert degree_for_bar(progression, 2) == 5
    assert degree_for_bar(progression, 3) == 4
    assert degree_for_bar(progression, 4) == 0  # wraps
    assert degree_for_bar(progression, 7) == 4  # wraps


def test_degree_for_bar_rejects_empty_progression():
    with pytest.raises(ValueError):
        degree_for_bar([], 0)


def test_render_motif_with_progression_differs_by_bar():
    # 2 bars of 4 beats, one hit per bar exactly on the downbeat, delta=0.
    scale = Scale(root=40, name="minor")
    motif = Motif(
        cell=[
            {"duration": 4.0, "is_rest": False},
            {"duration": 4.0, "is_rest": False},
        ],
        deltas=[0, 0],
    )
    progression = [0, 5, 5, 5]  # bar 0 -> degree 0, bar 1 -> degree 5
    pitches = render_motif_with_progression(motif, scale, progression, beats_per_bar=4.0)
    assert pitches[0] == scale.degree(0)
    assert pitches[1] == scale.degree(5)
    assert pitches[0] != pitches[1]


def test_render_motif_with_progression_matches_plain_render_for_flat_progression():
    from motif import render_motif

    scale = Scale(root=40, name="minor")
    motif = Motif(
        cell=[
            {"duration": 1.0, "is_rest": False},
            {"duration": 1.0, "is_rest": True},
            {"duration": 1.0, "is_rest": False},
        ],
        deltas=[0, 2],
    )
    flat = [0, 0, 0, 0]
    assert render_motif_with_progression(motif, scale, flat, beats_per_bar=4.0) == render_motif(motif, scale)


def test_render_motif_with_progression_rejects_bad_beats_per_bar():
    scale = Scale(root=40, name="minor")
    motif = Motif(cell=[{"duration": 1.0, "is_rest": False}], deltas=[0])
    with pytest.raises(ValueError):
        render_motif_with_progression(motif, scale, [0], beats_per_bar=0)


def test_pitches_per_cell_with_progression_is_cell_aligned():
    scale = Scale(root=40, name="minor")
    motif = Motif(
        cell=[
            {"duration": 1.0, "is_rest": False},
            {"duration": 1.0, "is_rest": True},
            {"duration": 1.0, "is_rest": False},
        ],
        deltas=[0, 2],
    )
    out = pitches_per_cell_with_progression(motif, scale, [0, 0, 0, 0], beats_per_bar=4.0)
    assert len(out) == len(motif.cell)
    assert out[1] is None
    assert out[0] is not None and out[2] is not None


def test_verse_and_chorus_progression_tables_are_real_and_nonempty():
    for table in (VERSE_PROGRESSIONS, CHORUS_PROGRESSIONS):
        assert table
        for progression in table.values():
            assert len(progression) == 4
            assert all(isinstance(d, int) for d in progression)
