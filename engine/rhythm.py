"""Rhythm/timing structure -- pitch-agnostic."""

from __future__ import annotations

import random

_EPS = 1e-9


# --- Feel-driven duration weighting (real, ported technique) ----------------
#
# Ported from the real reference implementation "Metalerator" (reference/
# metalerator/metalerator/rhythm_guitar/breakdown/default_melodic.py,
# RGuitarDefaultMelodicBreakdown.randomize_duration): its breakdown generator
# draws from durations [0.25, 0.5, 1, 2] (16th/8th/quarter/half, in the same
# "1 bar = 4 position-units" convention this project already uses for
# beats) with weights [1, 3, 3, 1] -- clearly biased toward 8th/quarter-note
# chugging over rapid 16ths or held half notes, which is exactly what makes
# a real breakdown riff read as "breakdown" rather than generic chug. This
# project's own rhythm vocabulary (`song._ALLOWED_LENGTHS`) deliberately
# caps at quarter notes (no half notes), so the half-note weight is DROPPED
# and the remaining three weights are kept in their original 1:3:3 ratio --
# adapted for a different duration vocabulary, not invented from scratch.
#
# Metalerator's `feel` concept is really "which song SECTION generator is
# active" (verse/chorus/breakdown/intro/outro are separate Python classes
# there), not a named, swappable table the way this project's
# `preset.feel` field is -- so only "breakdown" has real ported data behind
# it below. Other feel names (bounce/triplet/chug/wall/etc.) stay on the
# uniform default until a real reference technique exists for them too;
# inventing weight tables for those without a real source would violate
# this project's own "port, don't invent" discipline.
FEEL_DURATION_WEIGHTS: dict[str, dict[float, float]] = {
    "breakdown": {0.25: 1.0, 0.5: 3.0, 1.0: 3.0},
    # X.15 -- "chug" (deathcore.json's real declared feel, previously
    # completely unwired, same as "breakdown" was before this table
    # existed). Unlike "breakdown", there's no Metalerator source for this
    # one -- but the technique itself needs none: constant rapid 16th-note
    # palm-muted picking is the single most generic, textbook-recognized
    # "chug" convention in metal rhythm guitar (the same category of
    # "universal, no source needed" real music fact as X.11's hihat closed-
    # 8ths pulse). Weights are the deliberate INVERSE of "breakdown"'s
    # 8th/quarter bias -- 16ths dominant, not incidental.
    "chug": {0.25: 6.0, 0.5: 2.0, 1.0: 1.0},
    # X.16 -- "bounce" (the MOST common real preset feel: djent, groovy,
    # melodic, and progressive all declare it) had ZERO real duration
    # weighting until now -- unlike "breakdown"/"chug", it fell all the
    # way through to fully uniform selection, meaning roughly a third of
    # every "bounce" preset's notes were quarter notes. Real, exact
    # ground truth this time, not textbook genericity: parsed a real
    # user-supplied original MIDI transcription ("born of osiris style
    # midi.mid") with `mido` (exact note data, no transcription
    # uncertainty at all) -- its real Guitar 1 track measured 57.5% 16th
    # notes, 36.9% 8th notes, and a literal 0% quarter notes across 1464
    # real notes. Weights below preserve that real ~58:37:0 ratio
    # (quarter kept at a small nonzero floor rather than a hard 0 --
    # occasional real phrase-ending quarters do occur, at 32nd-note-level
    # rarity in the source data, not literally never).
    "bounce": {0.25: 6.0, 0.5: 4.0, 1.0: 0.3},
    # X.17 -- real regression fix: chill.json shared "bounce" with djent/
    # groovy/melodic/progressive, so the X.16 density fix (correct for
    # those four energetic presets) also made chill's own duration mix
    # dense/16th-heavy -- directly contradicting chill's own documented
    # identity ("Low-density breather... Airy, Periphery slow-part
    # feel"). "airy" is chill's own real, distinct feel: the deliberate
    # INVERSE weighting from "bounce" -- longer, sustained durations
    # dominant, 16ths rare, matching a genuine breather section rather
    # than constant chugging.
    "airy": {0.25: 1.0, 0.5: 3.0, 1.0: 4.0},
}

# Metalerator's companion rule (same method): a single isolated 16th note
# never occurs alone -- if the previous draw was a lone 16th, the next draw
# is FORCED to also be a 16th, pairing them up. This reads as a real
# realism fix (isolated 16ths sound like a stray flam, not a phrase) rather
# than a breakdown-specific quirk, but is only ever exercised here via the
# same real source method, so it travels together with "breakdown" above
# rather than being applied unconditionally to every feel. Also real,
# independently, for "chug": a lone stray 16th reads as a rhythm mistake
# there too, for the same reason.
FEEL_NO_SINGULAR_SHORT: dict[str, float] = {
    "breakdown": 0.25,
    "chug": 0.25,
    "bounce": 0.25,
}


def duration_bias_for_feel(feel: str | None) -> tuple[dict[float, float] | None, float | None]:
    """Real, ported `(weights, no_singular_short)` pair for `feel`, or
    `(None, None)` for a feel with no real reference data yet (see
    `FEEL_DURATION_WEIGHTS`'s docstring) -- callers pass these straight
    through to `generate_rhythm`'s own `weights`/`no_singular_short`
    parameters, which already treat `None` as "uniform, unchanged
    behavior", so an unmapped feel is never a fabricated guess."""
    return FEEL_DURATION_WEIGHTS.get(feel), FEEL_NO_SINGULAR_SHORT.get(feel)


# --- P2.1: two-layer generation model ---------------------------------------


def generate_rhythm(
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    rng: random.Random,
    weights: dict[float, float] | None = None,
    no_singular_short: float | None = None,
) -> list[dict]:
    """Generate a flat list of rhythm cells summing EXACTLY to `total_beats`.

    Each non-final cell recursively (i.e. one draw at a time, consuming the
    remaining span) picks a length from `allowed_lengths`. `weights=None`
    (the default) keeps the original uniform `rng.choice` behavior --
    every allowed length equally likely, unchanged from before this
    parameter existed. When `weights` is given (a real, ported example:
    `duration_bias_for_feel`'s output), the pick uses `rng.choices` with
    those weights instead -- lengths in `allowed_lengths` missing from
    `weights` get weight 0 (never picked), never a silent fallback.

    `no_singular_short`, when given, enforces "this length never appears
    alone" (ported from Metalerator's no-isolated-16th-notes rule -- see
    `FEEL_NO_SINGULAR_SHORT`): if the previous draw was `no_singular_short`
    and this draw's natural pick is a different length, this draw is
    forced to also be `no_singular_short`, pairing them. `None` (the
    default) leaves every draw exactly as picked.

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
    if weights is not None and not any(weights.get(length, 0.0) > 0 for length in allowed_lengths):
        raise ValueError("weights must assign a positive weight to at least one allowed_length")

    cells: list[dict] = []
    remaining = total_beats
    consecutive_short = 0
    while remaining > _EPS:
        if weights is None:
            length = rng.choice(allowed_lengths)
        else:
            length = rng.choices(
                allowed_lengths, weights=[weights.get(l, 0.0) for l in allowed_lengths], k=1
            )[0]

        if no_singular_short is not None:
            if consecutive_short % 2 != 0 and length != no_singular_short:
                length = no_singular_short
            consecutive_short = consecutive_short + 1 if length == no_singular_short else 0

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


# --- X.15: real triplet-feel rhythm generation -------------------------
#
# tech.json's real declared feel ("triplet", own description: "kick-locked
# triplet chug") was, like "chug"/"breakdown" before their own fixes,
# completely unwired -- `duration_bias_for_feel` only ever offers a
# duration-WEIGHT bias over the existing [0.25, 0.5, 1.0] length menu, and
# a genuine eighth-note triplet (span_beats/3 = 1/3 beat) isn't a member
# of that menu at all -- it can't be expressed as a reweighting of it. Per
# `tuplet_grid`'s own documented law ("a REAL subdivision, not a selection
# of indices out of some fixed larger grid... do not snap these offsets
# onto a 16th grid"), a real triplet feel needs its own real generator on
# top of the SAME `tuplet_grid` mechanism already used for legato runs,
# not a hack bolted onto the weighted-duration-menu model.


def generate_triplet_rhythm(total_beats: float, hit_chance: float, rng: random.Random) -> list[dict]:
    """Real, genuine eighth-note-triplet subdivision across `total_beats`:
    for every whole beat, three real evenly-spaced triplet-eighth cells
    (duration `span_beats / 3`, via the same real `tuplet_grid(3, 2,
    1.0)` spacing law every other tuplet in this project uses), each
    independently rolling `hit_chance` for hit vs rest -- the real
    "kick-locked triplet chug" device tech.json's own preset description
    names.

    `total_beats` must be a whole number of beats (always true for a real
    section span or `preset.group` value in this project's own pipeline)
    -- raises `ValueError` rather than silently truncating a fractional
    remainder into a fabricated partial triplet.
    """
    if total_beats <= 0:
        raise ValueError("total_beats must be > 0")
    if total_beats != int(total_beats):
        raise ValueError("total_beats must be a whole number of beats for real triplet subdivision")
    if not (0.0 <= hit_chance <= 1.0):
        raise ValueError("hit_chance must be within [0, 1]")

    offsets = tuplet_grid(3, 2, 1.0)
    triplet_duration = offsets[1] - offsets[0]
    cells: list[dict] = []
    for _ in range(int(total_beats)):
        for _ in range(3):
            is_hit = rng.random() < hit_chance
            cells.append({"duration": triplet_duration, "is_rest": not is_hit})
    return cells


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
