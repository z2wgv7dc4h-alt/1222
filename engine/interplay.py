"""Call-and-response: the guitar reacts to another part's rhythm.

Per god-tier-metal-scope.md ## 4: "Call-and-response between guitar and
drums/lead -- currently each instrument is generated in near isolation
(bass/drums derive from guitar, but guitar never reacts to them)."

`call_and_response` takes another part's already-generated rhythm cells
(standing in for drums or a lead line) and produces a guitar cell of the
SAME slot durations, where slots the other part hits are more likely to be
guitar hits too (an echo on the same slot, or an answer `answer_gap` slots
later) -- so the guitar is measurably correlated with the other part rather
than independently-rolled noise, while slots the other part rests still get
an ordinary `base_hit_chance` roll so the guitar isn't reduced to a pure
copy.
"""
from __future__ import annotations

import random

__all__ = ["call_and_response"]


def call_and_response(
    other_part_cells: list[dict],
    base_hit_chance: float,
    rng: random.Random,
    echo_chance: float = 0.6,
    answer_gap: int = 1,
) -> list[dict]:
    """Guitar rhythm cells (same slot count/durations as `other_part_cells`)
    biased toward the other part's hit positions.

    For each slot where `other_part_cells` hits, roll `echo_chance`: on
    success, force a guitar hit at that SAME slot (echo); on failure, force
    a guitar hit `answer_gap` slots later instead (answer), if that slot
    exists. Every slot not forced by this mechanism still gets an
    independent `base_hit_chance` roll, so a forced-hit slot can also have
    been reached by a plain roll and a non-forced slot isn't a guaranteed
    rest.
    """
    if not (0.0 <= base_hit_chance <= 1.0):
        raise ValueError("base_hit_chance must be within [0, 1]")
    if not (0.0 <= echo_chance <= 1.0):
        raise ValueError("echo_chance must be within [0, 1]")
    if answer_gap < 0:
        raise ValueError("answer_gap must be >= 0")

    n = len(other_part_cells)
    forced_hit = [False] * n
    for i, other in enumerate(other_part_cells):
        if other["is_rest"]:
            continue
        if rng.random() < echo_chance:
            forced_hit[i] = True
        else:
            j = i + answer_gap
            if j < n:
                forced_hit[j] = True

    out = []
    for i, other in enumerate(other_part_cells):
        is_hit = forced_hit[i] or (rng.random() < base_hit_chance)
        out.append({"duration": other["duration"], "is_rest": not is_hit})
    return out
