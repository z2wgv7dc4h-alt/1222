"""Double-tracking: two independently-humanized performances of one riff."""
from __future__ import annotations

import random

__all__ = ["humanize_take", "double_track"]

# X.21 -- the real reference's open/muted velocities (riff_engine.py lines
# 183/187), and the real threshold that separates them (artic.py's
# PALM_MUTE_VELOCITY_THRESHOLD). Jitter is layered on top of these but
# clamped so it can never cross this line in either direction -- an "open"
# hit must always read as open, a "muted" hit must always read as muted.
_OPEN_VELOCITY = 120
_MUTED_VELOCITY = 88
_PALM_MUTE_VELOCITY_THRESHOLD = 110


def humanize_take(
    cell: list[dict],
    rng: random.Random,
    timing_jitter: float = 0.02,
    velocity_base: float = 100.0,
    velocity_jitter: float = 10.0,
    open_chance: float | None = None,
) -> list[dict]:
    """One humanized performance of `cell`: each hit gets independent
    micro-timing jitter (`timing_offset`, beats) and velocity variation;
    rests carry no timing/velocity content. Rhythm shape (duration/is_rest
    per slot) is preserved exactly -- humanization only touches the two new
    per-hit fields.

    `open_chance`, when not `None`, replaces the flat `velocity_base`
    scheme with real open-string-vs-muted articulation (X.21, see module
    docstring): each hit independently rolls `rng.random() < open_chance`
    to decide open (`_OPEN_VELOCITY` + jitter, clamped to stay >=
    `_PALM_MUTE_VELOCITY_THRESHOLD`) vs muted (`_MUTED_VELOCITY` + jitter,
    clamped to stay below it). `open_chance=None` (the default) keeps the
    exact prior flat-`velocity_base` behavior, byte-identical.
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
        if open_chance is None:
            velocity = max(1, min(127, round(velocity_base + rng.uniform(-velocity_jitter, velocity_jitter))))
        elif rng.random() < open_chance:
            velocity = max(
                _PALM_MUTE_VELOCITY_THRESHOLD,
                min(127, round(_OPEN_VELOCITY + rng.uniform(-velocity_jitter, velocity_jitter))),
            )
        else:
            velocity = max(
                1,
                min(_PALM_MUTE_VELOCITY_THRESHOLD - 1, round(_MUTED_VELOCITY + rng.uniform(-velocity_jitter, velocity_jitter))),
            )
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
