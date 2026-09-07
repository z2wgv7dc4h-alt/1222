import random

import pytest

from performance import double_track, humanize_take
from rhythm import generate_rhythm


def _riff_cell():
    rng = random.Random(11)
    return generate_rhythm(8.0, [0.5, 1.0], hit_chance=0.7, rng=rng)


# --- P3.8: two independently-humanized takes ---------------------------------


def test_double_track_takes_are_not_identical():
    cell = _riff_cell()
    take_a, take_b = double_track(cell, random.Random(1), random.Random(2))
    assert take_a != take_b


def test_double_track_shares_the_same_underlying_riff_shape():
    cell = _riff_cell()
    take_a, take_b = double_track(cell, random.Random(1), random.Random(2))
    assert len(take_a) == len(take_b) == len(cell)
    for a, b, original in zip(take_a, take_b, cell):
        assert a["duration"] == b["duration"] == original["duration"]
        assert a["is_rest"] == b["is_rest"] == original["is_rest"]


def test_double_track_is_not_a_constant_time_shift_of_one_take():
    """Guards against the documented historical mistake (scope §18.3): an
    earlier attempt's 'double-tracking' was one performance copied and
    shifted by a fixed +8-tick offset, not two independent takes. If take B
    were just take A shifted by a constant, every per-hit timing_offset
    delta would be identical; independent humanization must not collapse to
    that.
    """
    cell = _riff_cell()
    take_a, take_b = double_track(cell, random.Random(5), random.Random(6), timing_jitter=0.05)
    hit_deltas = [
        b["timing_offset"] - a["timing_offset"]
        for a, b in zip(take_a, take_b)
        if not a["is_rest"]
    ]
    assert len(set(round(d, 9) for d in hit_deltas)) > 1, (
        "take B's timing offsets differ from take A's by a single constant "
        "shift -- this is the naive copy-and-shift mistake, not independent "
        "humanization"
    )


def test_double_track_same_rng_instance_advanced_also_differs():
    # Documented alternative: one seeded rng advanced between the two calls
    # (rather than two separate instances) is also acceptable, as long as
    # the two takes actually differ.
    cell = _riff_cell()
    rng = random.Random(123)
    take_a = humanize_take(cell, rng)
    take_b = humanize_take(cell, rng)  # same instance, already advanced
    assert take_a != take_b


def test_humanize_take_rejects_bad_input():
    cell = _riff_cell()
    with pytest.raises(ValueError):
        humanize_take(cell, random.Random(0), timing_jitter=-1.0)
    with pytest.raises(ValueError):
        humanize_take(cell, random.Random(0), velocity_jitter=-1.0)
