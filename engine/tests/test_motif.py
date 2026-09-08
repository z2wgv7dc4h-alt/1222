import random

import pytest

from motif import (
    Motif,
    ThemeRegistry,
    apply_pedal_bias,
    augment,
    fragment,
    generate_motif,
    invert,
    pick_pitch_interval,
    render_motif,
    transpose,
)
from presets import load_all_presets
from rhythm import generate_rhythm, tile_cell
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


# --- preset.group: N-against-4 displacement via tile_cell -------------------


def test_generate_motif_group_beats_tiles_a_short_cell_across_the_section():
    rng_grouped = random.Random(77)
    rng_reference = random.Random(77)
    scale = Scale(52, "phrygian")
    weights = {0: 20, 1: 3, 7: 3, 8: 1, 5: 1}

    grouped = generate_motif(
        16.0, [0.25, 0.5, 1.0], 0.5, rng_grouped, scale, weights, group_beats=3.0,
    )
    # Reproduce the same construction by hand (same rng state going in) to
    # prove generate_motif's group_beats path really is "generate a
    # group-beat cell, then rhythm.tile_cell it across total_beats" and not
    # some other mechanism.
    rng_manual = random.Random(77)
    short_cell = generate_rhythm(3.0, [0.25, 0.5, 1.0], 0.5, rng_manual)
    expected_cell = tile_cell(short_cell, 16.0)
    assert grouped.cell == expected_cell

    # Sanity: the section-filling ungrouped path produces a DIFFERENT cell
    # shape from the same rng seed (since it draws directly for 16 beats
    # instead of tiling a 3-beat cell) -- group_beats really changes
    # something, it isn't a silent no-op.
    ungrouped = generate_motif(16.0, [0.25, 0.5, 1.0], 0.5, rng_reference, scale, weights)
    assert ungrouped.cell != grouped.cell


def test_generate_motif_group_beats_none_is_unchanged_behavior():
    rng_a = random.Random(3)
    rng_b = random.Random(3)
    scale = Scale(52, "minor")
    weights = {0: 10, 7: 4}
    a = generate_motif(8.0, [0.5, 1.0], 0.6, rng_a, scale, weights, group_beats=None)
    b = generate_motif(8.0, [0.5, 1.0], 0.6, rng_b, scale, weights)
    assert a.cell == b.cell
    assert a.deltas == b.deltas


# --- preset.pedal: bias delta selection toward the root ---------------------


def test_apply_pedal_bias_zero_leaves_weights_unchanged():
    weights = {0: 10, 7: 4, 3: 2}
    assert apply_pedal_bias(weights, 0.0) == weights


def test_apply_pedal_bias_one_sends_almost_all_mass_to_root():
    weights = {0: 1, 7: 4, 3: 2}
    biased = apply_pedal_bias(weights, 1.0)
    total = sum(biased.values())
    assert biased[0] / total > 0.999


def test_apply_pedal_bias_never_zeroes_out_other_intervals():
    weights = {0: 1, 7: 4, 3: 2}
    for pedal in (0.2, 0.5, 0.85):
        biased = apply_pedal_bias(weights, pedal)
        assert set(biased) == set(weights)
        assert all(w > 0 for w in biased.values())


def test_apply_pedal_bias_handles_empty_weights_without_crashing():
    # Bad/edge input: nothing to bias toward -- must not raise or fabricate
    # an interval that was never in the input.
    assert apply_pedal_bias({}, 0.5) == {}


def test_apply_pedal_bias_rejects_out_of_range_pedal_by_clamping():
    weights = {0: 1, 7: 1}
    # Out-of-range pedal values are clamped into [0, 1] rather than
    # producing negative/garbage weights.
    low = apply_pedal_bias(weights, -5.0)
    high = apply_pedal_bias(weights, 5.0)
    assert low == apply_pedal_bias(weights, 0.0)
    assert high == apply_pedal_bias(weights, 1.0)


def test_generate_motif_pedal_raises_root_degree_fraction_statistically():
    """The real, wired claim: a high `pedal` must measurably increase the
    fraction of root-degree (delta == 0) hits versus no pedal bias at all,
    across many independent draws -- not a single-seed fluke."""
    djent = load_all_presets()["djent"]
    scale = Scale(52, djent.scale)

    def root_fraction(pedal, n_seeds=300):
        total_deltas = 0
        root_deltas = 0
        for seed in range(n_seeds):
            rng = random.Random(seed)
            m = generate_motif(
                4.0, [0.25, 0.5, 1.0], 0.7, rng, scale, djent.vocab.weights,
                pedal=pedal,
            )
            total_deltas += len(m.deltas)
            root_deltas += sum(1 for d in m.deltas if d == 0)
        return root_deltas / total_deltas if total_deltas else 0.0

    no_pedal_fraction = root_fraction(None)
    high_pedal_fraction = root_fraction(djent.pedal)  # 0.85
    assert high_pedal_fraction > no_pedal_fraction + 0.1, (
        f"expected pedal={djent.pedal} to noticeably raise the root-degree "
        f"fraction, got no_pedal={no_pedal_fraction:.3f} "
        f"high_pedal={high_pedal_fraction:.3f}"
    )


def test_theme_registry_group_and_pedal_are_threaded_through():
    djent = load_all_presets()["djent"]
    scale = Scale(52, djent.scale)
    registry = ThemeRegistry()
    rng = random.Random(1)
    m = registry.get_or_create(
        "grouped-theme", 16.0, [0.25, 0.5, 1.0], 0.5, rng, scale, djent.vocab.weights,
        group_beats=float(djent.group), pedal=djent.pedal,
    )
    # Same construction, by hand, from an identical rng seed.
    rng_manual = random.Random(1)
    expected = generate_motif(
        16.0, [0.25, 0.5, 1.0], 0.5, rng_manual, scale, djent.vocab.weights,
        group_beats=float(djent.group), pedal=djent.pedal,
    )
    assert m.cell == expected.cell
    assert m.deltas == expected.deltas


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
