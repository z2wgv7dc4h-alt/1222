"""Groove-grammar: named rhythmic-cell generators."""
from __future__ import annotations

import random

from rhythm import tile_cell

__all__ = ["gallop_cell", "stutter_chug_cell"]


def gallop_cell(total_beats: float, short: float = 0.25, long: float = 0.5) -> list[dict]:
    """The classic metal gallop: short-short-long, all hits, tiled to fill
    `total_beats` exactly. Deterministic -- the gallop feel comes from the
    fixed duration pattern, not from any random draw.
    """
    if total_beats <= 0:
        raise ValueError("total_beats must be > 0")
    if short <= 0 or long <= 0:
        raise ValueError("short and long must be > 0")
    unit = [
        {"duration": short, "is_rest": False},
        {"duration": short, "is_rest": False},
        {"duration": long, "is_rest": False},
    ]
    return tile_cell(unit, total_beats)


def stutter_chug_cell(
    total_beats: float,
    hit_len: float,
    hit_chance: float,
    rng: random.Random,
) -> list[dict]:
    """Rapid-fire, EQUAL-length repeated hits with rests punched in at
    random -- structurally distinct from `gallop_cell`'s short-short-long
    pattern, which always has exactly two duration values in a fixed
    3-slot-per-unit cycle. Here every slot is the same length
    (`total_beats` split into evenly-sized slots of ~`hit_len` each) and
    hit/rest is an independent `hit_chance` roll per slot, the stutter-chug
    "machine-gun with holes punched in it" feel.
    """
    if total_beats <= 0:
        raise ValueError("total_beats must be > 0")
    if hit_len <= 0:
        raise ValueError("hit_len must be > 0")
    if not (0.0 <= hit_chance <= 1.0):
        raise ValueError("hit_chance must be within [0, 1]")

    n = max(1, round(total_beats / hit_len))
    slot = total_beats / n
    cells = []
    for _ in range(n):
        is_hit = rng.random() < hit_chance
        cells.append({"duration": slot, "is_rest": not is_hit})
    return cells
