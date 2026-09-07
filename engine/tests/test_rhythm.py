import math
import random

import pytest

from rhythm import (
    RhythmRegistry,
    generate_rhythm,
    irvd_split,
    metric_polyrhythm,
    phrase_plan,
    pick_blast_type,
    tile_cell,
    tuplet_grid,
)


# --- P2.1: generate_rhythm ---------------------------------------------------


@pytest.mark.parametrize("seed", range(30))
def test_generate_rhythm_sums_exactly(seed):
    rng = random.Random(seed)
    total = 16.0
    cells = generate_rhythm(total, [0.25, 0.5, 1.0, 1.5], hit_chance=0.6, rng=rng)
    assert math.isclose(sum(c["duration"] for c in cells), total, rel_tol=0, abs_tol=1e-9)
    for c in cells:
        assert c["duration"] > 0
        assert isinstance(c["is_rest"], bool)


@pytest.mark.parametrize("total", [1.0, 3.5, 7.0, 12.25])
def test_generate_rhythm_various_totals_land_exact(total):
    rng = random.Random(42)
    cells = generate_rhythm(total, [0.5, 1.0], hit_chance=0.5, rng=rng)
    assert math.isclose(sum(c["duration"] for c in cells), total, rel_tol=0, abs_tol=1e-9)


def test_generate_rhythm_hit_chance_zero_is_all_rests():
    rng = random.Random(7)
    cells = generate_rhythm(8.0, [0.5, 1.0], hit_chance=0.0, rng=rng)
    assert all(c["is_rest"] for c in cells)


def test_generate_rhythm_hit_chance_one_is_all_hits():
    rng = random.Random(7)
    cells = generate_rhythm(8.0, [0.5, 1.0], hit_chance=1.0, rng=rng)
    assert all(not c["is_rest"] for c in cells)


def test_generate_rhythm_rejects_bad_input():
    rng = random.Random(1)
    with pytest.raises(ValueError):
        generate_rhythm(0.0, [1.0], 0.5, rng)
    with pytest.raises(ValueError):
        generate_rhythm(4.0, [], 0.5, rng)
    with pytest.raises(ValueError):
        generate_rhythm(4.0, [1.0], 1.5, rng)
    with pytest.raises(ValueError):
        generate_rhythm(4.0, [-1.0], 0.5, rng)


# --- P2.2: tile_cell + 7-into-16 phase drift ---------------------------------


def test_tile_cell_never_overshoots_and_sums_exact():
    rng = random.Random(3)
    cell = generate_rhythm(7.0, [0.5, 1.0, 1.5], hit_chance=0.7, rng=rng)
    tiled = tile_cell(cell, 16.0)
    assert math.isclose(sum(c["duration"] for c in tiled), 16.0, abs_tol=1e-9)


@pytest.mark.parametrize("seed", range(15))
def test_seven_into_sixteen_drifts_phase(seed):
    """The real Meshuggah/djent device: a 7-beat cell tiled across a 16-beat
    span does not evenly divide, so each repeat of the cell starts at a
    different phase relative to the underlying 4-beat bar pulse -- the
    accent pattern drifts instead of realigning every loop."""
    rng = random.Random(seed)
    cell = generate_rhythm(7.0, [0.5, 1.0], hit_chance=0.6, rng=rng)
    cell_total = sum(c["duration"] for c in cell)
    assert math.isclose(cell_total, 7.0, abs_tol=1e-9)

    total_beats = 16.0
    tiled = tile_cell(cell, total_beats)
    assert math.isclose(sum(c["duration"] for c in tiled), total_beats, abs_tol=1e-9)

    # Phase (relative to a 4-beat bar) of each full repeat's start offset.
    num_full_repeats = int(total_beats // cell_total)
    starts = [i * cell_total for i in range(num_full_repeats)]
    phases = sorted({round(s % 4.0, 6) for s in starts})
    # 7 % 4 == 3 != 0, so successive repeats must NOT all land on the same
    # phase -- this is what proves the riff phase-shifts against the beat.
    assert len(phases) > 1, (
        f"expected drifting phases across repeats, got constant phase {phases}"
    )


def test_tile_cell_rejects_bad_input():
    with pytest.raises(ValueError):
        tile_cell([], 4.0)
    with pytest.raises(ValueError):
        tile_cell([{"duration": 1.0, "is_rest": False}], 0.0)


# --- P2.3: metric_polyrhythm is mechanically distinct from tile_cell -------


def test_metric_polyrhythm_produces_exact_subdivision_counts():
    rng = random.Random(5)
    result = metric_polyrhythm(4.0, {"six_feel": 6, "four_feel": 4}, hit_chance=0.5, rng=rng)
    assert len(result["six_feel"]) == 6
    assert len(result["four_feel"]) == 4
    for voice, n in (("six_feel", 6), ("four_feel", 4)):
        slot = 4.0 / n
        offsets = [c["offset"] for c in result[voice]]
        assert offsets == [pytest.approx(i * slot) for i in range(n)]


def test_metric_polyrhythm_never_repeats_or_truncates_a_subcell():
    """Structural proof this is a different mechanism from tile_cell: a
    voice's cell count is ALWAYS exactly its subdivision count regardless of
    span, never the result of repeating/truncating some smaller pattern.
    tile_cell, by contrast, must repeat and can truncate its input cell to
    fill a longer span."""
    rng = random.Random(9)
    for span in (2.0, 4.0, 9.5):
        result = metric_polyrhythm(span, {"v": 5}, hit_chance=0.5, rng=rng)
        assert len(result["v"]) == 5  # never a multiple of some smaller cell

    # tile_cell, given a "cell" of 5 slots whose total does not equal the
    # span, MUST repeat/truncate -- producing an output length that is a
    # function of how many times the cell fits, not a fixed count.
    small_cell = [{"duration": 1.0, "is_rest": False} for _ in range(5)]  # sums to 5
    tiled_short = tile_cell(small_cell, 3.0)   # truncates mid-cell
    tiled_long = tile_cell(small_cell, 12.0)   # repeats ~2.4x
    assert len(tiled_short) == 3
    assert len(tiled_long) != len(small_cell)


def test_metric_polyrhythm_rejects_bad_input():
    rng = random.Random(1)
    with pytest.raises(ValueError):
        metric_polyrhythm(0.0, {"a": 4}, 0.5, rng)
    with pytest.raises(ValueError):
        metric_polyrhythm(4.0, {}, 0.5, rng)
    with pytest.raises(ValueError):
        metric_polyrhythm(4.0, {"a": 0}, 0.5, rng)


# --- P2.4: real tuplet grids -------------------------------------------------


@pytest.mark.parametrize("n,over,span", [(3, 2, 1.0), (5, 4, 1.0), (7, 4, 1.0)])
def test_tuplet_grid_evenly_spaced(n, over, span):
    offsets = tuplet_grid(n, over, span)
    assert len(offsets) == n
    assert offsets[0] == 0.0
    diffs = [offsets[i + 1] - offsets[i] for i in range(len(offsets) - 1)]
    for d in diffs:
        assert math.isclose(d, span / n, abs_tol=1e-9)


def test_tuplet_offsets_not_subset_of_16_or_4_grid():
    """Guard against regressing into the documented fake-triplet mistake:
    real tuplet offsets must NOT coincide with positions on a straight 4- or
    16-slot grid built over the same span (except the shared 0 start)."""
    span = 4.0  # one bar
    grid16 = {round(i * (span / 16), 9) for i in range(16)}
    grid4 = {round(i * (span / 4), 9) for i in range(4)}

    for n, over in [(3, 2), (5, 4), (7, 4)]:
        offsets = tuplet_grid(n, over, span)
        non_zero = [round(o, 9) for o in offsets[1:]]
        assert not any(o in grid16 for o in non_zero), (n, offsets, grid16)
        assert not any(o in grid4 for o in non_zero), (n, offsets, grid4)


def test_tuplet_grid_rejects_bad_input():
    with pytest.raises(ValueError):
        tuplet_grid(0, 2, 1.0)
    with pytest.raises(ValueError):
        tuplet_grid(3, 0, 1.0)
    with pytest.raises(ValueError):
        tuplet_grid(3, 2, 0.0)


# --- P2.5: blast family -------------------------------------------------


def test_zero_weight_blast_type_never_appears():
    rng = random.Random(11)
    weights = {"traditional": 5, "gravity": 5, "hammer": 0}
    picks = {pick_blast_type(weights, rng) for _ in range(200)}
    assert "hammer" not in picks
    assert picks <= {"traditional", "gravity"}


def test_all_positive_weight_blast_types_can_appear():
    rng = random.Random(13)
    weights = {"traditional": 1, "gravity": 1, "hammer": 1}
    picks = {pick_blast_type(weights, rng) for _ in range(200)}
    assert picks == {"traditional", "gravity", "hammer"}


def test_pick_blast_type_rejects_all_zero_weights():
    rng = random.Random(1)
    with pytest.raises(ValueError):
        pick_blast_type({"traditional": 0, "gravity": 0}, rng)


# --- P2.6: shared rhythm id ---------------------------------------------


def test_shared_rhythm_id_returns_identical_rhythm():
    registry = RhythmRegistry()
    rng = random.Random(21)
    guitar = registry.get_or_create("verse_a", 8.0, [0.5, 1.0], 0.6, rng)
    kick = registry.get_or_create("verse_a", 8.0, [0.5, 1.0], 0.6, rng)
    assert guitar == kick
    assert guitar is kick  # same cached object, no regeneration


def test_different_rhythm_ids_generate_independently():
    registry = RhythmRegistry()
    rng = random.Random(21)
    a = registry.get_or_create("id_a", 8.0, [0.5, 1.0], 0.6, rng)
    b = registry.get_or_create("id_b", 8.0, [0.5, 1.0], 0.6, rng)
    # Drawn from the same rng stream at different points -- extremely likely
    # to differ (not a hard guarantee, but this is a sanity check only).
    assert a != b or [c["is_rest"] for c in a] != [c["is_rest"] for c in b]


# --- P2.7: IRVD --------------------------------------------------------
# Ported verbatim from reference/ww-forge-prior-attempt/engine/theory.py's
# `phrase_plan` (PORTS.md originally pointed IRVD at style_packs.py, which
# does not contain it -- corrected to theory.py after finding the real
# source via riff_engine.py's "see theory.phrase_plan" comment).


@pytest.mark.parametrize("bars,expected", [
    (1, ["I"]),
    (2, ["I", "D"]),
    (4, ["I", "R", "V", "D"]),
    (6, ["I", "R", "R", "V", "V", "D"]),
    (10, ["I", "R", "R", "R", "V", "V", "V", "V", "D", "D"]),
])
def test_phrase_plan_matches_source_worked_examples(bars, expected):
    assert phrase_plan(bars) == expected


def test_phrase_plan_clamps_rather_than_rejects_small_input():
    # The real source clamps (`bars = max(1, int(bars))`) rather than
    # raising -- this is a port, so behavioral fidelity to the source wins
    # over the project's usual fail-closed convention.
    assert phrase_plan(1) == phrase_plan(0) == phrase_plan(-5) == ["I"]


@pytest.mark.parametrize("total_bars", [1, 2, 4, 5, 8, 13, 16, 32])
def test_irvd_intro_always_one_bar(total_bars):
    split = irvd_split(total_bars)
    start, end = split["introduction"]
    assert (start, end) == (0, 1)


@pytest.mark.parametrize("total_bars", [2, 4, 6, 8, 12, 16, 32])
def test_irvd_destruction_is_last_quarter_floor_min_one(total_bars):
    split = irvd_split(total_bars)
    start, end = split["destruction"]
    assert end == total_bars
    expected_len = max(1, total_bars // 4)
    assert end - start == expected_len


@pytest.mark.parametrize("total_bars", [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 16, 20, 32])
def test_irvd_phases_present_are_contiguous_and_cover_total(total_bars):
    split = irvd_split(total_bars)
    order = ["introduction", "repetition", "variation", "destruction"]
    prev_end = 0
    for phase in order:
        if phase not in split:
            continue
        start, end = split[phase]
        assert start == prev_end
        assert end >= start
        prev_end = end
    assert prev_end == total_bars


def test_irvd_split_single_bar_has_only_introduction():
    assert irvd_split(1) == {"introduction": (0, 1)}
