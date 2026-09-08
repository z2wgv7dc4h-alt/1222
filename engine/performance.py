"""Double-tracking: two independently-humanized performances of one riff.

Per god-tier-metal-scope.md ### 17.1 and the documented mistake in ### 18.3:
an earlier attempt's "double-tracking" was just one performance copied and
time-shifted +8 MIDI ticks -- not two independent takes, which they flagged
themselves as unfinished. This module exists specifically so that mistake
cannot silently recur: `double_track` always draws its two takes' jitter
from two DIFFERENT `random.Random` instances, never one take derived from
the other by a fixed offset.

X.21 -- real open-string-vs-muted articulation via velocity, ported from the
real reference (`reference/ww-forge-prior-attempt/engine/riff_engine.py`):
`wants_open = rng.random() < open_chance` (line 125) decides per-hit whether
a note is an open ringing accent or a muted chug, and the real emitted
velocities (lines 183/187) are `120` for an open hit vs `88`/`96`/`100`
otherwise -- `artic.py`'s real `PALM_MUTE_VELOCITY_THRESHOLD = 110` confirms
opens are always emitted comfortably above that line, everything else
comfortably below. This is the real, previously-unwired purpose of
`preset.open_chance` (X.20 removed its INCORRECT prior use as `hit_chance`).
Deliberately a simplified 2-tier port (open=120 / muted=88, dropping the
reference's accent/downbeat 3rd-4th tiers) -- ships the real, dominant,
audible contrast without plumbing `atmosphere.find_accents`' accent data
through a new call chain; the richer tiering is a real, deliberately
deferred refinement, not silently dropped.
"""
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
