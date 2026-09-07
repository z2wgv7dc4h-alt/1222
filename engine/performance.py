"""Double-tracking: two independently-humanized performances of one riff.

Per god-tier-metal-scope.md ### 17.1 and the documented mistake in ### 18.3:
an earlier attempt's "double-tracking" was just one performance copied and
time-shifted +8 MIDI ticks -- not two independent takes, which they flagged
themselves as unfinished. This module exists specifically so that mistake
cannot silently recur: `double_track` always draws its two takes' jitter
from two DIFFERENT `random.Random` instances, never one take derived from
the other by a fixed offset.
"""
from __future__ import annotations

import random

__all__ = ["humanize_take", "double_track"]


def humanize_take(
    cell: list[dict],
    rng: random.Random,
    timing_jitter: float = 0.02,
    velocity_base: float = 100.0,
    velocity_jitter: float = 10.0,
) -> list[dict]:
    """One humanized performance of `cell`: each hit gets independent
    micro-timing jitter (`timing_offset`, beats) and velocity variation;
    rests carry no timing/velocity content. Rhythm shape (duration/is_rest
    per slot) is preserved exactly -- humanization only touches the two new
    per-hit fields.
    """
    if timing_jitter < 0:
        raise ValueError("timing_jitter must be >= 0")
    if velocity_jitter < 0:
        raise ValueError("velocity_jitter must be >= 0")

    out = []
    for c in cell:
        if c["is_rest"]:
            out.append({"duration": c["duration"], "is_rest": True, "timing_offset": 0.0, "velocity": 0})
            continue
        offset = rng.uniform(-timing_jitter, timing_jitter)
        velocity = max(1, min(127, round(velocity_base + rng.uniform(-velocity_jitter, velocity_jitter))))
        out.append({"duration": c["duration"], "is_rest": False, "timing_offset": offset, "velocity": velocity})
    return out


def double_track(
    cell: list[dict],
    rng_a: random.Random,
    rng_b: random.Random,
    **humanize_kwargs,
) -> tuple[list[dict], list[dict]]:
    """Two independently-humanized takes of the same riff `cell`.

    `rng_a` and `rng_b` MUST be two distinct `random.Random` instances (or
    the same instance passed once and advanced between calls by the
    caller -- either way, document which) so take B is never take A's jitter
    replayed or shifted by a constant; see the module docstring. Both takes
    share the exact same rhythm shape (duration/is_rest per slot), since
    both come from the same input `cell` -- only the humanization differs.
    """
    take_a = humanize_take(cell, rng_a, **humanize_kwargs)
    take_b = humanize_take(cell, rng_b, **humanize_kwargs)
    return take_a, take_b
