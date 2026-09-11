"""Legato-run generation: TASKS.md X.6a."""
from __future__ import annotations

import random

from fretboard import Fretboard
from rhythm import tuplet_grid
from theory import Scale

__all__ = [
    "generate_legato_run",
    "legato_run_rhythm",
    "fret_positions_for_run",
    "generate_legato_lick",
]

# n-notes-in-the-time-of-`over` pairings that read as a genuine tuplet feel
# rather than a plain subdivision -- same vocabulary rhythm.tuplet_grid's own
# docstring uses (eighth-note triplet, quintuplet, septuplet).
_TUPLET_OVER = {3: 2, 5: 4, 7: 4}


def generate_legato_run(
    scale: Scale,
    start_pitch: int,
    length: int,
    direction: int = 1,
    rng: random.Random | None = None,
    reversal_chance: float = 0.15,
) -> list[int]:
    """A CONTIGUOUS run of `length` consecutive scale degrees, starting at
    the scale degree nearest `start_pitch`, moving one `scale.step()` at a
    time in `direction` (1 = ascending, -1 = descending).

    This is deliberately NOT a `VoiceLeader`-style weighted pick: every
    pitch here is exactly one scale step from the one before it (verified
    by `scale.index_of`), which is what makes the result read as a single
    contiguous scalar lick rather than a sequence of independent choices.

    Optional documented behavior: if `rng` is given, at most ONE direction
    reversal can occur mid-run (rolled fresh at each step, with probability
    `reversal_chance`, until it fires once) -- modeling the common real
    legato shape of "run up, then back down" (or vice versa). Without an
    `rng` (the default), the run is a straight, deterministic line in
    `direction` the whole way -- no randomness is introduced unless the
    caller explicitly opts in by passing one.
    """
    if length <= 0:
        raise ValueError("length must be > 0")
    if direction not in (1, -1):
        raise ValueError("direction must be 1 or -1")
    if not (0.0 <= reversal_chance <= 1.0):
        raise ValueError("reversal_chance must be within [0, 1]")

    current = scale.nearest(start_pitch)
    pitches = [current]
    dir_ = int(direction)
    reversed_once = False
    for _ in range(length - 1):
        if rng is not None and not reversed_once and rng.random() < reversal_chance:
            dir_ = -dir_
            reversed_once = True
        current = scale.step(current, dir_)
        pitches.append(current)
    return pitches


def legato_run_rhythm(
    length: int,
    span_beats: float,
    rng: random.Random | None = None,
) -> list[dict]:
    """Timing for a legato run: `length` fast, EVEN, rest-free cells filling
    `span_beats` -- a legato run is a continuous slur, so unlike a picked/
    chugged rhythm (`rhythm.generate_rhythm`'s rest-heavy hit/rest draws)
    every cell here is a hit.

    Subdivision choice (documented, not incidental): when `length` is one
    of the genuine tuplet counts `rhythm.tuplet_grid` models (3, 5, or 7 --
    "n notes in the time of `over`"), the note spacing is derived from
    `tuplet_grid(length, over, span_beats)` so the run is framed as that
    real tuplet feel. For any other `length`, it falls back to plain even
    subdivision (`span_beats / length` per note). Both branches currently
    produce numerically identical slot widths (`tuplet_grid`'s n offsets
    over `span_beats` are themselves evenly spaced at `span_beats / n`) --
    the branch exists to keep the musical *meaning* (genuine tuplet vs.
    plain subdivision) legible and separately testable/adjustable, not
    because the two cases differ today.

    `rng` is accepted for interface symmetry with the rest of this module
    (and as a hook for future micro-timing/swing humanization) but is not
    drawn from currently -- this function is fully deterministic.
    """
    if length <= 0:
        raise ValueError("length must be > 0")
    if span_beats <= 0:
        raise ValueError("span_beats must be > 0")

    if length in _TUPLET_OVER:
        offsets = tuplet_grid(length, _TUPLET_OVER[length], span_beats)
        slot = offsets[1] - offsets[0] if len(offsets) > 1 else span_beats
    else:
        slot = span_beats / length

    cells = [{"duration": slot, "is_rest": False} for _ in range(length)]
    drift = span_beats - sum(c["duration"] for c in cells)
    if cells and abs(drift) > 0:
        cells[-1]["duration"] += drift
    return cells


def fret_positions_for_run(
    pitches: list[int],
    fretboard: Fretboard,
    prev: tuple[int, int] | None = None,
) -> list[tuple[int, int]]:
    """Resolve a legato run's pitches to real `(string, fret)` positions,
    biased toward staying on ONE STRING -- the idiomatic way a legato run
    is actually played, since hammer-on/pull-off technique depends on the
    fretting hand staying put on a single string; jumping strings mid-run
    is a different technique this is not modeling.

    Reuses `Fretboard.pitch_to_fret`'s own `prev` parameter, which already
    costs a string change at 2x a fret change -- by threading each
    resolved position in as the next call's `prev`, the whole run is
    chained through that same cost-minimizing search, so consecutive notes
    naturally settle on the same string wherever the fretboard's range
    allows it.

    Raises `ValueError` (never fabricates a position) if any pitch has no
    reachable `(string, fret)` on `fretboard` -- the same discipline
    `pitch_to_fret` itself already enforces.
    """
    if not pitches:
        raise ValueError("pitches must be non-empty")

    positions: list[tuple[int, int]] = []
    current_prev = prev
    for pitch in pitches:
        pos = fretboard.pitch_to_fret(pitch, max_fret=fretboard.max_fret, prev=current_prev)
        positions.append(pos)
        current_prev = pos
    return positions


def generate_legato_lick(
    scale: Scale,
    fretboard: Fretboard,
    start_pitch: int,
    length: int,
    span_beats: float,
    rng: random.Random,
    direction: int = 1,
) -> dict:
    """Ties `generate_legato_run` + `legato_run_rhythm` + `fret_positions_
    for_run` into one real lick: `{"pitches": [...], "cells": [...],
    "positions": [...]}`, all three lists the same length (`length`).

    `rng` is required (not optional) here, unlike the lower-level pieces:
    a lick generated for actual use in a song should always be able to
    exercise the documented direction-reversal behavior in
    `generate_legato_run` -- callers who want a bare deterministic run
    without reversal should call `generate_legato_run` directly instead.
    """
    pitches = generate_legato_run(scale, start_pitch, length, direction=direction, rng=rng)
    cells = legato_run_rhythm(length, span_beats, rng=rng)
    positions = fret_positions_for_run(pitches, fretboard)
    return {"pitches": pitches, "cells": cells, "positions": positions}
