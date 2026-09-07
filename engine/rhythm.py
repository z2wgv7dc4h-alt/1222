"""Rhythm/timing structure -- pitch-agnostic.

Phase 2 ("Rhythm") of the engine. Nothing in this file knows or cares about
pitch; a cell is just {"duration": float, "is_rest": bool}. Pitch/timbre is
layered on top of these skeletons by other code.

Hard law from CLAUDE.md that every function here obeys:
  - Grid is the writer. No cloud/AI model anywhere in this file.
  - Seeded RNG only: every random draw goes through a `random.Random`
    instance passed in by the caller. Nothing here touches the global
    `random` module, so two independent calls with the same seed produce
    provably identical output and never interfere with each other or with
    parallel work.
  - One class per job.

Documented historical mistake this file explicitly does NOT repeat: an
earlier attempt faked triplet feel by cherry-picking indices
{0,2,3,5,6,8,10,11,13,14} out of a 16-slot 16th-note grid ("the fake 3+3+2
grid"). `tuplet_grid()` below produces genuine evenly-spaced compound-meter
subdivisions instead -- see its docstring and the guard test in
tests/test_rhythm.py.
"""

from __future__ import annotations

import random

_EPS = 1e-9


# --- P2.1: two-layer generation model ---------------------------------------


def generate_rhythm(
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    rng: random.Random,
) -> list[dict]:
    """Generate a flat list of rhythm cells summing EXACTLY to `total_beats`.

    Each non-final cell recursively (i.e. one draw at a time, consuming the
    remaining span) picks a length from `allowed_lengths` with uniform
    probability (`rng.choice`) -- every allowed length is equally likely to
    be picked at each step, regardless of how many cells have already been
    placed. This is a deliberate, documented choice; a weighted variant
    would take a parallel `weights` argument rather than silently changing
    this function's contract.

    Each cell independently rolls `hit_chance` (rng.random() < hit_chance)
    to decide hit vs rest.

    The final cell is corrected to land exactly on `total_beats`: if the
    drawn length would overshoot the remaining span, it is clamped to
    whatever beats remain, and a last float-drift correction snaps the sum
    to `total_beats` exactly.

    Pitch-agnostic: cells carry no pitch/instrument information.
    """
    if total_beats <= 0:
        raise ValueError("total_beats must be > 0")
    if not allowed_lengths:
        raise ValueError("allowed_lengths must be non-empty")
    if any(length <= 0 for length in allowed_lengths):
        raise ValueError("allowed_lengths must all be > 0")
    if not (0.0 <= hit_chance <= 1.0):
        raise ValueError("hit_chance must be within [0, 1]")

    cells: list[dict] = []
    remaining = total_beats
    while remaining > _EPS:
        length = rng.choice(allowed_lengths)
        if length > remaining:
            length = remaining
        is_hit = rng.random() < hit_chance
        cells.append({"duration": length, "is_rest": not is_hit})
        remaining -= length

    # Correct any float drift so the sum is exactly total_beats.
    drift = total_beats - sum(c["duration"] for c in cells)
    if cells and abs(drift) > 0:
        cells[-1]["duration"] += drift

    return cells


# --- P2.2: cell-tile polymeter ----------------------------------------------


def tile_cell(cell: list[dict], total_beats: float) -> list[dict]:
    """Repeat `cell` end-to-end to fill `total_beats`, truncating the final
    repeat so the output sums to exactly `total_beats` (never overshoots).

    This is the "odd cell against a longer/fixed span" device (e.g. a 7-beat
    riff cell tiled across a 16-beat span): because the cell length does not
    evenly divide the total, each successive repeat starts at a different
    phase relative to the underlying pulse -- the accent pattern drifts
    against the beat instead of realigning every bar. See
    tests/test_rhythm.py::test_seven_into_sixteen_drifts_phase for a
    concrete demonstration.

    Truncation happens WITHIN a sub-cell if needed (a sub-cell's duration is
    shortened to fit) rather than by dropping whole sub-cells, so the total
    always lands exactly on `total_beats`.
    """
    if not cell:
        raise ValueError("cell must be non-empty")
    if total_beats <= 0:
        raise ValueError("total_beats must be > 0")
    cell_sum = sum(c["duration"] for c in cell)
    if cell_sum <= 0:
        raise ValueError("cell must have positive total duration")

    result: list[dict] = []
    remaining = total_beats
    while remaining > _EPS:
        for sub in cell:
            if remaining <= _EPS:
                break
            dur = min(sub["duration"], remaining)
            result.append({"duration": dur, "is_rest": sub["is_rest"]})
            remaining -= dur

    return result


# --- P2.3: metric polyrhythm (mechanically distinct from tile_cell) --------


def metric_polyrhythm(
    span_beats: float,
    voices: dict[str, int],
    hit_chance: float,
    rng: random.Random,
) -> dict[str, list[dict]]:
    """Two (or more) independently-subdivided FIXED grids over the SAME
    `span_beats`, e.g. a 6-feel voice and a 4-feel voice both fitting inside
    one bar.

    This is a different device from `tile_cell`: there is no short cell that
    gets repeated/truncated to fill a longer span. Each voice's grid is
    `voices[name]` evenly-spaced slots computed directly across the full
    `span_beats` in one shot -- the number of cells a voice produces is
    always exactly its subdivision count, never a function of repeating a
    smaller pattern.

    Returns {voice_name: [{"offset": float, "duration": float,
    "is_rest": bool}, ...]}.
    """
    if span_beats <= 0:
        raise ValueError("span_beats must be > 0")
    if not voices:
        raise ValueError("voices must be non-empty")
    if not (0.0 <= hit_chance <= 1.0):
        raise ValueError("hit_chance must be within [0, 1]")

    result: dict[str, list[dict]] = {}
    for name, n in voices.items():
        if n <= 0:
            raise ValueError(f"subdivision count must be > 0 for voice {name!r}")
        slot = span_beats / n
        cells = []
        for i in range(n):
            is_hit = rng.random() < hit_chance
            cells.append(
                {"offset": i * slot, "duration": slot, "is_rest": not is_hit}
            )
        result[name] = cells
    return result


# --- P2.4: real tuplet grids -------------------------------------------------


def tuplet_grid(n: int, over: int, span_beats: float) -> list[float]:
    """`n` evenly-spaced offsets across `span_beats`, representing a genuine
    "n notes in the time of `over`" compound-meter subdivision (e.g. n=3,
    over=2 for an eighth-note triplet feel across a 1-beat span; n=5, over=4
    for a quintuplet; n=7, over=4 for a septuplet).

    `span_beats` is the duration that `over` notes would normally occupy at
    the base subdivision -- `over` is kept as an explicit, documented
    parameter (rather than folded away) so the grid's musical meaning stays
    legible, even though the offsets themselves only depend on `n` and
    `span_beats`: offset_i = i * (span_beats / n).

    This is a REAL subdivision, not a selection of indices out of some
    fixed larger grid: the spacing is span_beats / n, which for n in
    {3, 5, 7} is irrational relative to a straight 4- or 16-slot 16th-note
    grid built over the same span. Do not "snap" these offsets onto a 16th
    grid -- that was the documented fake-triplet mistake this project must
    not repeat.
    """
    if n <= 0:
        raise ValueError("n must be > 0")
    if over <= 0:
        raise ValueError("over must be > 0")
    if span_beats <= 0:
        raise ValueError("span_beats must be > 0")

    slot = span_beats / n
    return [i * slot for i in range(n)]


# --- P2.5: blast family -------------------------------------------------


def pick_blast_type(weights: dict[str, float], rng: random.Random) -> str:
    """Pick a blast-beat type (e.g. "traditional", "gravity", "hammer") at
    random, weighted by `weights`. A type with weight 0 (or absent) can
    never be picked -- this is enforced by `random.Random.choices`, which
    raises if the total weight is <= 0 and otherwise never selects a
    zero-weight item, not merely "unlikely" to.
    """
    if not weights:
        raise ValueError("weights must be non-empty")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights must be >= 0")
    if sum(weights.values()) <= 0:
        raise ValueError("at least one weight must be > 0")

    types = list(weights.keys())
    picked = rng.choices(types, weights=[weights[t] for t in types], k=1)
    return picked[0]


# --- P2.6: shared rhythm id --------------------------------------------------


class RhythmRegistry:
    """Explicit, caller-owned cache (NOT hidden global state) mapping an
    arbitrary id string to a generated rhythm cell list. The first caller
    for a given id generates the rhythm (via `generate_rhythm`) and stores
    it; every subsequent caller with the same id gets back the identical
    cached list without regenerating -- e.g. so a guitar voice and a kick
    voice can share one rhythm skeleton.

    Callers create their own `RhythmRegistry()` instance and pass it around
    explicitly; nothing is stored at module scope.
    """

    def __init__(self) -> None:
        self._cache: dict[str, list[dict]] = {}

    def get_or_create(
        self,
        rhythm_id: str,
        total_beats: float,
        allowed_lengths: list[float],
        hit_chance: float,
        rng: random.Random,
    ) -> list[dict]:
        if rhythm_id not in self._cache:
            self._cache[rhythm_id] = generate_rhythm(
                total_beats, allowed_lengths, hit_chance, rng
            )
        return self._cache[rhythm_id]

    def __contains__(self, rhythm_id: str) -> bool:
        return rhythm_id in self._cache


# --- P2.7: IRVD (Introduction / Repetition / Variation / Destruction) ------


def phrase_plan(bars: int) -> list[str]:
    """One label per bar: what that bar does to the section's single idea.

      I  Introduction -- state the cell once.
      R  Repetition   -- play it again, verbatim, so the ear locks on.
      V  Variation    -- same skeleton, moved/re-voiced notes.
      D  Destruction  -- fragment and densify into the next section.

    Ported verbatim from reference/ww-forge-prior-attempt/engine/theory.py's
    `phrase_plan` (found via riff_engine.py's "see theory.phrase_plan"
    comment -- PORTS.md originally pointed IRVD at style_packs.py, which
    turned out to hold only PACKS/ALIASES/VOCAB; PORTS.md has been corrected).

    Introduction is always exactly one bar; Destruction takes the last
    quarter (floor division, minimum 1 bar); the remainder splits between
    Repetition and Variation with the odd bar going to Variation. `bars`
    is clamped to >= 1 rather than rejected, matching the source exactly.
    """
    bars = max(1, int(bars))
    if bars == 1:
        return ["I"]
    d = max(1, bars // 4)
    rem = max(0, bars - 1 - d)
    v = (rem + 1) // 2
    r = rem - v
    return ["I"] + ["R"] * r + ["V"] * v + ["D"] * d


def irvd_split(total_bars: int) -> dict[str, tuple[int, int]]:
    """Convenience wrapper over `phrase_plan`: half-open [start, end) bar
    ranges for each phase actually present, 0-indexed, derived by scanning
    the same label list `phrase_plan` returns (never computed separately,
    so the two can't drift apart)."""
    labels = phrase_plan(total_bars)
    ranges: dict[str, tuple[int, int]] = {}
    names = {"I": "introduction", "R": "repetition", "V": "variation", "D": "destruction"}
    i = 0
    while i < len(labels):
        j = i
        while j < len(labels) and labels[j] == labels[i]:
            j += 1
        ranges[names[labels[i]]] = (i, j)
        i = j
    return ranges
