import math
import random

import pytest

from groove import gallop_cell, stutter_chug_cell


# --- P3.5: gallop --------------------------------------------------------


def test_gallop_cell_sums_exactly_and_is_all_hits():
    cell = gallop_cell(4.0, short=0.25, long=0.5)
    assert math.isclose(sum(c["duration"] for c in cell), 4.0, abs_tol=1e-9)
    assert all(not c["is_rest"] for c in cell)


def test_gallop_cell_has_short_short_long_pattern():
    cell = gallop_cell(3.0, short=0.25, long=0.5)
    durations = [c["duration"] for c in cell]
    # The classic gallop unit repeats short, short, long.
    assert durations[:3] == [0.25, 0.25, 0.5]


def test_gallop_cell_rejects_bad_input():
    with pytest.raises(ValueError):
        gallop_cell(0.0)
    with pytest.raises(ValueError):
        gallop_cell(4.0, short=0.0)
    with pytest.raises(ValueError):
        gallop_cell(4.0, long=-1.0)


# --- P3.5: stutter-chug ----------------------------------------------------


def test_stutter_chug_cell_sums_exactly():
    rng = random.Random(1)
    cell = stutter_chug_cell(4.0, hit_len=0.25, hit_chance=0.6, rng=rng)
    assert math.isclose(sum(c["duration"] for c in cell), 4.0, abs_tol=1e-9)


def test_stutter_chug_cell_all_slots_equal_length():
    rng = random.Random(2)
    cell = stutter_chug_cell(4.0, hit_len=0.25, hit_chance=1.0, rng=rng)
    durations = {c["duration"] for c in cell}
    assert len(durations) == 1  # every slot the same length


def test_stutter_chug_cell_rejects_bad_input():
    rng = random.Random(0)
    with pytest.raises(ValueError):
        stutter_chug_cell(0.0, 0.25, 0.5, rng)
    with pytest.raises(ValueError):
        stutter_chug_cell(4.0, 0.0, 0.5, rng)
    with pytest.raises(ValueError):
        stutter_chug_cell(4.0, 0.25, 1.5, rng)


# --- P3.5: gallop and stutter-chug are structurally different ---------------


def test_gallop_and_stutter_chug_differ_structurally_for_same_total():
    total = 4.0
    gallop = gallop_cell(total, short=0.25, long=0.5)
    stutter = stutter_chug_cell(total, hit_len=0.25, hit_chance=1.0, rng=random.Random(3))

    gallop_durations = sorted({round(c["duration"], 6) for c in gallop})
    stutter_durations = sorted({round(c["duration"], 6) for c in stutter})

    # Gallop always has two distinct duration values (short & long); a
    # same-length-hits stutter-chug always has exactly one. This is a
    # structural property of the two generators, not a matter of random luck.
    assert len(gallop_durations) == 2
    assert len(stutter_durations) == 1
    assert gallop_durations != stutter_durations
    assert len(gallop) != len(stutter)
