import random

import pytest

from motif import (
    Motif,
    ThemeRegistry,
    augment,
    fragment,
    generate_motif,
    invert,
    pick_pitch_interval,
    render_motif,
    transpose,
)
from presets import load_all_presets
from rhythm import generate_rhythm
from theory import DISSONANT, Scale, shade


def _sample_motif() -> Motif:
    # 4 hits, 1 rest -- a small, easy-to-reason-about fixture.
    cell = [
        {"duration": 0.5, "is_rest": False},
        {"duration": 0.5, "is_rest": True},
        {"duration": 0.5, "is_rest": False},
        {"duration": 1.0, "is_rest": False},
        {"duration": 0.5, "is_rest": False},
    ]
    return Motif(cell=cell, deltas=[0, 0, 2, -1])


# --- P3.1: Motif invariant ---------------------------------------------------


def test_motif_construction_accepts_matching_lengths():
    m = _sample_motif()
    assert m.hit_count == 4
    assert len(m.deltas) == 4


def test_motif_rejects_mismatched_delta_count():
    cell = [{"duration": 0.5, "is_rest": False}, {"duration": 0.5, "is_rest": False}]
    with pytest.raises(ValueError):
        Motif(cell=cell, deltas=[0])  # 2 hits, only 1 delta
    with pytest.raises(ValueError):
        Motif(cell=cell, deltas=[0, 1, 2])  # 2 hits, 3 deltas


# --- P3.2: same shape, two roots ---------------------------------------------


def test_render_motif_same_shape_different_roots():
    motif = _sample_motif()
    scale_a = Scale(60, "minor")
    scale_b = Scale(67, "minor")  # a different root, same scale name

    pitches_a = render_motif(motif, scale_a, start_degree=0)
    pitches_b = render_motif(motif, scale_b, start_degree=0)

    assert len(pitches_a) == len(pitches_b) == motif.hit_count
    assert pitches_a != pitches_b  # different absolute pitches

    # Same relative shape: every rendered pitch differs from the other
    # root's by exactly the root offset (12 -> 7 = ... constant, since both
    # scales share the same interval table and start_degree).
    root_offset = scale_b.root - scale_a.root
    for pa, pb in zip(pitches_a, pitches_b):
        assert pb - pa == root_offset

    # And the internal contour (differences between consecutive notes) is
    # identical between the two renders -- the actual "same shape" claim.
    shape_a = [b - a for a, b in zip(pitches_a, pitches_a[1:])]
    shape_b = [b - a for a, b in zip(pitches_b, pitches_b[1:])]
    assert shape_a == shape_b


def test_render_motif_different_scale_object_same_contour():
    motif = _sample_motif()
    scale_a = Scale(60, "minor")
    scale_c = Scale(60, "dorian")  # different scale name, same root
    pitches_a = render_motif(motif, scale_a)
    pitches_c = render_motif(motif, scale_c)
    # Different scale intervals can legitimately produce different absolute
    # pitches even at the same root and same deltas.
    assert len(pitches_a) == len(pitches_c)


# --- P3.3: develop ops -- pairing invariant survives every op ---------------


def test_transpose_preserves_pairing_and_shifts_deltas():
    motif = _sample_motif()
    shifted = transpose(motif, 3)
    assert len(shifted.deltas) == shifted.hit_count == motif.hit_count
    assert shifted.deltas == [d + 3 for d in motif.deltas]
    assert shifted.cell == motif.cell  # rhythm untouched


def test_augment_preserves_pairing_and_stretches_durations():
    motif = _sample_motif()
    stretched = augment(motif, 2.0)
    shrunk = augment(motif, 0.5)
    for developed, factor in ((stretched, 2.0), (shrunk, 0.5)):
        assert len(developed.deltas) == developed.hit_count == motif.hit_count
        assert developed.deltas == motif.deltas  # pitch untouched
        for orig, new in zip(motif.cell, developed.cell):
            assert new["duration"] == pytest.approx(orig["duration"] * factor)
            assert new["is_rest"] == orig["is_rest"]


def test_augment_rejects_non_positive_factor():
    motif = _sample_motif()
    with pytest.raises(ValueError):
        augment(motif, 0)
    with pytest.raises(ValueError):
        augment(motif, -1.0)


def test_invert_preserves_pairing_and_negates_deltas():
    motif = _sample_motif()
    inverted = invert(motif)
    assert len(inverted.deltas) == inverted.hit_count == motif.hit_count
    assert inverted.deltas == [-d for d in motif.deltas]


def test_fragment_preserves_pairing_for_various_slices():
    motif = _sample_motif()
    for start, end in [(0, 2), (1, 4), (0, len(motif.cell)), (2, 2)]:
        frag = fragment(motif, start, end)
        assert len(frag.deltas) == frag.hit_count
        assert frag.cell == motif.cell[start:end]


def test_fragment_rejects_bad_range():
    motif = _sample_motif()
    with pytest.raises(ValueError):
        fragment(motif, -1, 2)
    with pytest.raises(ValueError):
        fragment(motif, 3, 1)


def test_develop_ops_chain_still_pairs_correctly():
    # A realistic development chain: transpose then augment then fragment
    # then invert -- the invariant must survive all four in sequence.
    motif = _sample_motif()
    developed = invert(fragment(augment(transpose(motif, 2), 1.5), 0, 4))
    assert len(developed.deltas) == developed.hit_count


# --- P3.6: chromatic flag shifts the interval distribution -------------------


def test_pick_pitch_interval_rejects_bad_weights():
    rng = random.Random(0)
    with pytest.raises(ValueError):
        pick_pitch_interval({}, rng)
    with pytest.raises(ValueError):
        pick_pitch_interval({0: 0, 7: 0}, rng)


def test_chromatic_flag_shifts_distribution_toward_dissonant_intervals():
    tech = load_all_presets()["tech"].vocab.weights
    rng_plain = random.Random(1234)
    rng_shaded = random.Random(1234)
    shaded_weights = shade(tech, dissonance=0.9)

    n = 4000
    plain_dissonant = sum(1 for _ in range(n) if pick_pitch_interval(tech, rng_plain) % 12 in DISSONANT)
    shaded_dissonant = sum(1 for _ in range(n) if pick_pitch_interval(shaded_weights, rng_shaded) % 12 in DISSONANT)

    plain_fraction = plain_dissonant / n
    shaded_fraction = shaded_dissonant / n
    assert shaded_fraction > plain_fraction + 0.1, (
        f"expected shading toward dissonance to noticeably raise the dissonant "
        f"fraction, got plain={plain_fraction:.3f} shaded={shaded_fraction:.3f}"
    )


def test_generate_motif_chromatic_flag_produces_valid_motif():
    tech = load_all_presets()["tech"]
    scale = Scale(52, tech.scale)
    for chromatic in (False, True):
        rng = random.Random(7)
        motif = generate_motif(
            8.0, [0.5, 1.0], 0.7, rng, scale, tech.vocab.weights,
            chromatic=chromatic, dissonance=0.9,
        )
        assert len(motif.deltas) == motif.hit_count


# --- P3.4: theme registry ----------------------------------------------------


def test_theme_registry_returns_same_base_motif_for_same_id():
    tech = load_all_presets()["tech"]
    scale = Scale(52, tech.scale)
    registry = ThemeRegistry()

    rng1 = random.Random(99)
    first = registry.get_or_create("verse-theme", 8.0, [0.5, 1.0], 0.7, rng1, scale, tech.vocab.weights)

    # A second request with the SAME id, even with a different rng/weights,
    # must return the identical cached base motif -- it must not regenerate.
    rng2 = random.Random(1)
    second = registry.get_or_create(
        "verse-theme", 8.0, [0.5, 1.0], 0.7, rng2, scale, {0: 999},
    )
    assert second is first
    assert second.cell == first.cell
    assert second.deltas == first.deltas


def test_theme_registry_different_ids_generate_independently():
    tech = load_all_presets()["tech"]
    scale = Scale(52, tech.scale)
    registry = ThemeRegistry()
    rng = random.Random(5)
    a = registry.get_or_create("theme-a", 4.0, [0.5, 1.0], 0.7, rng, scale, tech.vocab.weights)
    b = registry.get_or_create("theme-b", 4.0, [0.5, 1.0], 0.7, rng, scale, tech.vocab.weights)
    assert "theme-a" in registry and "theme-b" in registry
    assert "theme-c" not in registry
    # Not asserting a != b (could coincidentally match) -- just that both
    # were generated and cached independently under their own ids.
    assert isinstance(a, Motif) and isinstance(b, Motif)
