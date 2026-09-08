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


# --- X.21: real open-string-vs-muted articulation via velocity ---------------


def test_open_chance_none_is_byte_identical_to_flat_velocity_base():
    """open_chance=None (the default) must reproduce the exact prior
    flat-velocity_base behavior -- zero regression risk for every existing
    caller that doesn't pass it."""
    cell = _riff_cell()
    with_none = humanize_take(cell, random.Random(42), open_chance=None)
    without_param = humanize_take(cell, random.Random(42))
    assert with_none == without_param


def test_open_chance_one_always_produces_open_velocity():
    """A real, exact distributional check: open_chance=1.0 means every real
    hit rolls open, so every velocity must land at/above the real
    PALM_MUTE_VELOCITY_THRESHOLD (110), never below."""
    cell = _riff_cell()
    take = humanize_take(cell, random.Random(3), open_chance=1.0)
    hit_velocities = [c["velocity"] for c in take if not c["is_rest"]]
    assert hit_velocities, "expected at least one real hit in this fixture"
    assert all(v >= 110 for v in hit_velocities), f"expected every open hit >= 110, got {hit_velocities}"


def test_open_chance_zero_always_produces_muted_velocity():
    """The real inverse: open_chance=0.0 means every real hit rolls muted,
    so every velocity must land strictly below the real threshold."""
    cell = _riff_cell()
    take = humanize_take(cell, random.Random(3), open_chance=0.0)
    hit_velocities = [c["velocity"] for c in take if not c["is_rest"]]
    assert hit_velocities, "expected at least one real hit in this fixture"
    assert all(v < 110 for v in hit_velocities), f"expected every muted hit < 110, got {hit_velocities}"


def test_open_chance_midrange_produces_a_real_mix_of_both_bands():
    """A real, seeded, non-degenerate open_chance must produce a genuine
    mix of both velocity bands across enough hits -- not silently
    collapsing to all-one-value."""
    cell = generate_rhythm(32.0, [0.25, 0.5], hit_chance=0.9, rng=random.Random(1))
    take = humanize_take(cell, random.Random(7), open_chance=0.5)
    hit_velocities = [c["velocity"] for c in take if not c["is_rest"]]
    opens = sum(1 for v in hit_velocities if v >= 110)
    muted = sum(1 for v in hit_velocities if v < 110)
    assert opens > 0 and muted > 0, f"expected a real mix of both bands, got opens={opens} muted={muted}"


def test_double_track_forwards_open_chance_to_both_takes():
    """double_track's **humanize_kwargs pass-through must actually reach
    both real takes, not just one."""
    cell = generate_rhythm(16.0, [0.25, 0.5], hit_chance=0.9, rng=random.Random(1))
    take_a, take_b = double_track(cell, random.Random(1), random.Random(2), open_chance=1.0)
    for take in (take_a, take_b):
        hit_velocities = [c["velocity"] for c in take if not c["is_rest"]]
        assert hit_velocities and all(v >= 110 for v in hit_velocities)
