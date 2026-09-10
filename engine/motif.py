"""Motif system: rhythm + scale-degree contour, developed across sections.

Phase 3 ("Motif/riff") of the engine. Per god-tier-metal-scope.md ## 4:
"generate a short thematic cell once (rhythm + contour, not fixed pitches)
and *develop* it across sections (transposition, augmentation/diminution,
inversion, fragmentation) instead of every section rolling independently."

A `Motif` pairs a pitch-agnostic rhythm cell (from `rhythm.generate_rhythm`,
`{"duration": float, "is_rest": bool}` dicts) with a list of SCALE-DEGREE
DELTAS -- not absolute pitches -- one delta per non-rest hit in the cell.
Deltas are relative motion (e.g. +2 = up two scale degrees from wherever the
line currently sits), which is what makes one motif replayable against a
different root or `Scale` later (see `render_motif`) without regenerating
anything.

Hard law from CLAUDE.md/anti-patterns.md this file obeys:
  - Seeded RNG only: every random draw goes through a `random.Random`
    instance passed in by the caller.
  - A validator that is not called is not done: the cell/delta count
    invariant is checked in `Motif.__post_init__`, so it is enforced on
    EVERY construction path (including every develop op below), not just
    a standalone function tests could call and production code could skip.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from groove import gallop_cell, stutter_chug_cell
from rhythm import duration_bias_for_feel, generate_rhythm, generate_triplet_rhythm, phrase_plan, tile_cell
from theory import Scale, _weighted_choice, pick_pitch_interval_markov, shade

__all__ = [
    "Motif",
    "render_motif",
    "transpose",
    "augment",
    "invert",
    "fragment",
    "pick_pitch_interval",
    "degree_delta_for_interval",
    "generate_pitch_deltas",
    "apply_pedal_bias",
    "generate_motif",
    "ThemeRegistry",
]


def _count_hits(cell: list[dict]) -> int:
    return sum(1 for c in cell if not c["is_rest"])


@dataclass
class Motif:
    """A rhythm cell plus one scale-degree delta per non-rest hit.

    `cell` is a list of `{"duration": float, "is_rest": bool}` dicts, exactly
    as produced by `rhythm.generate_rhythm`/`tile_cell`. `deltas` has exactly
    one entry per hit (non-rest cell) -- rests carry no pitch information.
    """

    cell: list[dict] = field(default_factory=list)
    deltas: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        hits = _count_hits(self.cell)
        if len(self.deltas) != hits:
            raise ValueError(
                f"Motif invariant violated: {len(self.deltas)} deltas for "
                f"{hits} non-rest hits in the rhythm cell"
            )

    @property
    def hit_count(self) -> int:
        return _count_hits(self.cell)


# --- P3.2: render a motif's contour into absolute pitches -------------------


def render_motif(motif: Motif, scale: Scale, start_degree: int = 0) -> list[int]:
    """Turn `motif.deltas` into absolute MIDI pitches against `scale`,
    starting from scale-degree index `start_degree`.

    Each delta is interpreted relative to the SAME fixed `start_degree` (a
    riff's pedal/anchor degree), not a running cursor -- so `deltas =
    [0, 0, 2, -1]` always means "root, root, up-a-step-from-root,
    down-a-step-from-root", regardless of `scale.root` or `start_degree`.
    That is exactly what makes two calls with different roots/scales produce
    the same relative shape (see tests/test_motif.py).
    """
    return [scale.degree(start_degree + d) for d in motif.deltas]


# --- P3.3: develop ops -------------------------------------------------------
# Every op returns a NEW Motif; `Motif.__post_init__` re-validates the
# cell/delta pairing on construction, so a broken op fails loudly instead of
# silently drifting.


def transpose(motif: Motif, degrees: int) -> Motif:
    """Shift every delta by `degrees` scale degrees. Rhythm is untouched."""
    return Motif(cell=[dict(c) for c in motif.cell], deltas=[d + int(degrees) for d in motif.deltas])


def augment(motif: Motif, factor: float) -> Motif:
    """Stretch (`factor` > 1, augmentation) or shrink (`factor` < 1,
    diminution) the rhythm cell's DURATIONS by `factor`. Pitch deltas are
    untouched -- hit/rest placement doesn't change, only how long each cell
    lasts, so the delta count still matches the (unchanged) hit count."""
    if factor <= 0:
        raise ValueError("factor must be > 0")
    new_cell = [{"duration": c["duration"] * float(factor), "is_rest": c["is_rest"]} for c in motif.cell]
    return Motif(cell=new_cell, deltas=list(motif.deltas))


def invert(motif: Motif) -> Motif:
    """Negate every delta (mirror the contour around the anchor degree)."""
    return Motif(cell=[dict(c) for c in motif.cell], deltas=[-d for d in motif.deltas])


def fragment(motif: Motif, start: int, end: int) -> Motif:
    """Take a sub-slice of the motif by CELL index (not time): `cell[start:
    end]` plus exactly the deltas that belong to the hits inside that slice.
    """
    if start < 0 or end < start:
        raise ValueError("fragment requires 0 <= start <= end")
    sub_cell = motif.cell[start:end]
    hits_before = _count_hits(motif.cell[:start])
    hits_in = _count_hits(sub_cell)
    sub_deltas = motif.deltas[hits_before:hits_before + hits_in]
    return Motif(cell=sub_cell, deltas=sub_deltas)


# --- P3.6: chromatic-biased delta selection ----------------------------------


def pick_pitch_interval(weights: dict, rng: random.Random) -> int:
    """Weighted pick of one semitone interval (a key of `weights`). A real
    thin wrapper around `theory._weighted_choice` -- previously an
    independent copy of the same accumulate-and-compare loop
    `VoiceLeader._weighted_interval` also implemented; now the one real
    shared primitive, same public signature/behavior as before (verified
    byte-identical by this module's own distribution tests).
    """
    items = list((weights or {}).items())
    if not items:
        raise ValueError("weights must be non-empty")
    return _weighted_choice(items, rng)


def degree_delta_for_interval(scale: Scale, base_degree_index: int, semitone_interval: int) -> int:
    """Snap `base_degree_index`'s pitch + `semitone_interval` semitones into
    the scale, and express the result as a scale-degree DELTA from
    `base_degree_index` -- so chromatic bias (picked in semitone space, where
    `shade()` operates) still comes out as a scale-legal degree delta, never
    a fabricated off-scale pitch.

    X.36 -- made public (was `_degree_delta_for_interval`): `lead.
    generate_sequence_line` became a real second caller needing this exact
    logic (the same real weighted-interval-to-scale-degree-delta mechanism
    `generate_motif`'s own pitch loop uses), same established precedent as
    X.24's `resolve_kick_style` extraction -- promote to public rather than
    duplicate."""
    base_pitch = scale.degree(base_degree_index)
    target = scale.nearest(base_pitch + semitone_interval)
    return scale.index_of(target) - base_degree_index


def apply_pedal_bias(weights: dict, pedal: float) -> dict:
    """Re-weight `weights` (semitone-interval -> weight) toward the root
    (interval 0) proportional to `pedal` in `[0, 1]` -- the mechanism this
    project uses to make `preset.pedal` (documented in presets.py as "how
    often a phrase returns to the open low string") measurably change
    `generate_motif`'s output: picking semitone interval 0 always resolves
    to scale-degree DELTA 0 (see `degree_delta_for_interval` -- interval 0
    added to the current pitch snaps right back to that same degree), so
    biasing the interval-0 draw probability directly biases the fraction of
    root/pedal (`delta == 0`) hits a motif ends up with.

    `pedal=0` leaves `weights` unchanged. `pedal=1` sends effectively all
    probability mass onto interval 0. In between, interval 0's SHARE of the
    total weight mass moves linearly from its existing share toward 1.0 by
    `pedal`:

        target_share = existing_share + pedal * (1 - existing_share)

    every other interval keeps its relative proportions to each other, just
    scaled down to make room -- the same "rebalance, never zero out" design
    `theory.shade()` already uses, applied to a single interval instead of
    the dissonant/consonant split.
    """
    d = max(0.0, min(1.0, float(pedal)))
    out = dict(weights)
    total = sum(out.values())
    if total <= 0 or d <= 0:
        return out
    root_w = out.get(0, 0.0)
    existing_share = root_w / total
    target_share = existing_share + d * (1.0 - existing_share)
    if target_share >= 1.0:
        return {0: total}
    rest = total - root_w
    if rest <= 0:
        return out
    out[0] = target_share * rest / (1.0 - target_share)
    return out


# X.32 -- real slot size for feel="stutter_chug" (groove.stutter_chug_cell),
# matching this project's existing shortest allowed rhythm length (16th
# note) rather than inventing a new duration value.
_STUTTER_CHUG_HIT_LEN = 0.25


def generate_motif(
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    rng: random.Random,
    scale: Scale,
    vocab_weights: dict,
    chromatic: bool = False,
    dissonance: float = 0.85,
    base_degree: int = 0,
    group_beats: float | None = None,
    pedal: float | None = None,
    feel: str | None = None,
    irvd_bars: int | None = None,
    markov: dict[int, dict[int, float]] | None = None,
) -> Motif:
    """Generate a fresh Motif: a rhythm cell (via `rhythm.generate_rhythm`)
    plus a scale-degree contour drawn from `vocab_weights` (a preset's
    `vocab.weights`, semitone-interval -> weight).

    `feel`, when it names a style with real ported duration-bias data
    (currently only `"breakdown"` -- see `rhythm.FEEL_DURATION_WEIGHTS`),
    threads that bias into the underlying `generate_rhythm` call so a
    preset's declared `.feel` actually changes its rhythm's duration
    mix, not just its label. `feel=None` or an unmapped name (the
    default) keeps rhythm generation exactly as before this parameter
    existed -- uniform duration selection, no forced pairing.

    `feel="gallop"`/`feel="stutter_chug"` (X.32) dispatch to
    `groove.gallop_cell`/`groove.stutter_chug_cell` instead -- real, named
    rhythmic-cell DEVICES (a fixed short-short-long pattern / rapid
    equal-length hits with random rests), not a duration-weight reshaping
    of the standard menu, same real "different subdivision path entirely"
    treatment `feel="triplet"` already gets.

    `chromatic=True` reshapes `vocab_weights` through `theory.shade()` at
    `dissonance` before picking, biasing draws toward the dissonant interval
    set (1, 2, 6, 11 semitones) -- see tests/test_motif.py for the
    distribution-level check. `chromatic=False` uses the raw preset weights.

    `group_beats`, when not `None`, realizes `preset.group`'s djent-style
    N-against-4 displacement: instead of drawing one rhythm cell that spans
    `total_beats` directly, a SHORT cell of length `group_beats` is drawn
    first and then tiled across `total_beats` via `rhythm.tile_cell`. Since
    `group_beats` need not evenly divide `total_beats` (e.g. 3 into 16),
    each successive repeat of the short cell starts at a different phase
    against the underlying pulse -- the same "cell doesn't evenly divide
    the total, so accents drift against the beat" polymeter device
    `tile_cell` already documents, applied here to a preset's own riff cell
    rather than a hand-built fixture. `group_beats=None` (the default)
    keeps the previous, ungrouped behavior exactly (`generate_rhythm`
    filling the whole section directly).

    `pedal`, when not `None`, biases delta selection toward the root via
    `apply_pedal_bias` before picking (see that function's docstring) --
    the wired realization of `preset.pedal`'s "how often a phrase returns
    to the pedal note".

    Deltas walk from `base_degree` (each pick's semitone interval is
    resolved against the degree the previous pick landed on), so a chromatic
    contour can wander instead of always leaping from the same anchor.

    `irvd_bars`, when not `None`, replaces the single flat rhythm+pitch draw
    above with real IRVD phrase development (X.19, scope sec.18.2's
    Introduction/Repetition/Variation/Destruction) via `rhythm.phrase_plan`
    -- see `_generate_irvd_motif`'s own docstring for the real bar-by-bar
    construction. Mutually exclusive with `group_beats`: raises `ValueError`
    if both are given, since `group_beats`'s own phase-drift polymeter
    device (the tile length deliberately NOT dividing evenly into the
    section) would directly fight IRVD's verbatim-repeat-then-vary bar
    structure -- a preset uses one real device or the other, never both.

    `markov`, when given (a real, corpus-derived first-order transition
    table -- see `reference_vocab.build_preset_from_corpus`), threads
    straight through to `generate_pitch_deltas`' own real sequence-aware
    picking. `markov=None` (every preset that predates this feature) is
    byte-identical to before.
    """
    if irvd_bars is not None and group_beats is not None:
        raise ValueError("irvd_bars and group_beats are mutually exclusive")
    if irvd_bars is not None:
        return _generate_irvd_motif(
            irvd_bars, total_beats, allowed_lengths, hit_chance, rng, scale,
            vocab_weights, chromatic=chromatic, dissonance=dissonance,
            base_degree=base_degree, pedal=pedal, feel=feel, markov=markov,
        )
    if feel == "gallop":
        # X.32 -- the classic short-short-long metal gallop (scope sec.4:
        # "named rhythmic cells... 'gallop'"). `groove.gallop_cell` is
        # deterministic (the gallop feel comes from the fixed duration
        # pattern, not a random draw) and already tiles to fill `span`
        # exactly -- same real "short cell then tile again under
        # group_beats" structure as the "triplet" branch below.
        span = float(group_beats) if group_beats is not None else total_beats
        short_cell = gallop_cell(span)
        cell = tile_cell(short_cell, total_beats) if group_beats is not None else short_cell
    elif feel == "stutter_chug":
        # X.32 -- rapid equal-length hits with rests punched in at random
        # (scope sec.4: "'stutter-chug'") -- structurally distinct from
        # gallop's fixed short-short-long pattern.
        span = float(group_beats) if group_beats is not None else total_beats
        short_cell = stutter_chug_cell(span, _STUTTER_CHUG_HIT_LEN, hit_chance, rng)
        cell = tile_cell(short_cell, total_beats) if group_beats is not None else short_cell
    elif feel == "triplet":
        # X.15: a real triplet feel is a genuinely different subdivision
        # device, not a duration-weight reshaping of the standard
        # [0.25, 0.5, 1.0] menu (see generate_triplet_rhythm's own
        # docstring) -- dispatched here instead of through
        # duration_bias_for_feel/generate_rhythm's weighted-choice path.
        span = float(group_beats) if group_beats is not None else total_beats
        short_cell = generate_triplet_rhythm(span, hit_chance, rng)
        cell = tile_cell(short_cell, total_beats) if group_beats is not None else short_cell
    else:
        duration_weights, no_singular_short = duration_bias_for_feel(feel)
        if group_beats is not None:
            short_cell = generate_rhythm(
                group_beats, allowed_lengths, hit_chance, rng,
                weights=duration_weights, no_singular_short=no_singular_short,
            )
            cell = tile_cell(short_cell, total_beats)
        else:
            cell = generate_rhythm(
                total_beats, allowed_lengths, hit_chance, rng,
                weights=duration_weights, no_singular_short=no_singular_short,
            )
    hits = _count_hits(cell)
    deltas = generate_pitch_deltas(
        hits, scale, vocab_weights, rng,
        chromatic=chromatic, dissonance=dissonance, base_degree=base_degree, pedal=pedal,
        markov=markov,
    )
    return Motif(cell=cell, deltas=deltas)


# P9.3 -- extracted from generate_motif's own tail (the real per-hit pitch
# loop), made public since a second real caller (song.regenerate_section's
# "new notes, same hits" primitive) needs the EXACT same real weighted-
# interval-to-scale-degree-delta mechanism against an EXISTING rhythm cell
# it isn't regenerating -- same established precedent as X.24's
# resolve_kick_style / X.36's degree_delta_for_interval extractions
# (promote to public when a genuine second caller needs it, never
# duplicate). generate_motif itself now calls this, zero behavior change.
def generate_pitch_deltas(
    hit_count: int,
    scale: Scale,
    vocab_weights: dict,
    rng: random.Random,
    chromatic: bool = False,
    dissonance: float = 0.85,
    base_degree: int = 0,
    pedal: float | None = None,
    markov: dict[int, dict[int, float]] | None = None,
) -> list[int]:
    """Real per-hit scale-degree deltas for `hit_count` hits, walking from
    `base_degree` -- the exact same real mechanism `generate_motif`'s own
    pitch loop uses (`shade()` for chromatic bias, `apply_pedal_bias` for
    `pedal`, then one real weighted interval draw per hit).

    `markov`, when given (a real, corpus-derived first-order transition
    table over interval classes -- see `reference_vocab.
    build_preset_from_corpus`), makes each pick AFTER the first depend on
    the PREVIOUS interval actually chosen, via `theory.
    pick_pitch_interval_markov` -- real corpus-observed note-to-note
    tendencies instead of an independent marginal draw every hit.
    `markov=None` (every call site/preset that predates this feature) is
    byte-identical to before."""
    weights = shade(vocab_weights, dissonance) if chromatic else dict(vocab_weights)
    if pedal is not None:
        weights = apply_pedal_bias(weights, pedal)

    deltas: list[int] = []
    degree_index = int(base_degree)
    prev_interval: int | None = None
    for _ in range(hit_count):
        iv = pick_pitch_interval_markov(weights, rng, markov, prev_interval)
        d = degree_delta_for_interval(scale, degree_index, iv)
        deltas.append(d)
        degree_index += d
        prev_interval = iv
    return deltas


# X.19 -- real IRVD phrase development (Introduction/Repetition/Variation/
# Destruction, scope sec.18.2), the modest, real, audible pitch shift used
# for the Variation bar. A different device from song.py's own cross-
# SECTION `_THEME_DEVELOP_TRANSPOSE_DEGREES` (that one develops a whole
# section's theme across multiple reuses of a role; this one develops
# PITCH within a single section's own bars) -- doesn't need to share the
# same number, chosen independently.
_IRVD_VARIATION_DEGREES = 2


def _generate_irvd_motif(
    irvd_bars: int,
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    rng: random.Random,
    scale: Scale,
    vocab_weights: dict,
    chromatic: bool,
    dissonance: float,
    base_degree: int,
    pedal: float | None,
    feel: str | None,
    markov: dict[int, dict[int, float]] | None = None,
) -> Motif:
    """Real bar-by-bar IRVD construction (see `generate_motif`'s docstring
    for why this exists and when it's used). `rhythm.phrase_plan(irvd_bars)`
    gives one label per bar; each bar is built from already-real, already-
    tested primitives, never a fresh, uncontrolled pitch/rhythm-choice path:

      I  a real `generate_motif` call for ONE bar's worth of beats
         (`total_beats / irvd_bars`) -- the stated idea.
      R  a literal deep copy of the "I" bar -- "play it again, verbatim."
      V  `transpose(I_bar, _IRVD_VARIATION_DEGREES)` -- same rhythm
         skeleton as "I", pitches shifted -- "same skeleton, re-voiced".
      D  `augment(previous_bar, 0.5)` (halves every cell's duration,
         preserving hit count/deltas exactly) concatenated with a deep
         copy of itself -- the same rhythmic/pitch content played twice as
         fast, refilling the bar exactly (0.5 + 0.5 == 1.0 of the bar) --
         real "fragment and densify", derived from whatever bar came
         immediately before it (real forward momentum into the next
         section), not always reaching back to "I". Only the FIRST "D" in
         a real consecutive run halves -- `phrase_plan`'s own real formula
         (`d = bars // 4`) produces MULTIPLE consecutive "D" labels for
         any `bars >= 8` (confirmed: `phrase_plan(8) == [..., "D", "D"]`),
         and halving a bar that's already been halved compounds --
         0.25 -> 0.125 -> 0.0625 beats, a real 64th-note subdivision that
         measurably read as chaotic "random drum spam" once every other
         layer of clutter was cut (direct user listening feedback,
         2026-09-11). A second (or third...) consecutive "D" instead
         repeats the FIRST "D" bar's own already-fragmented result
         verbatim -- same real principle "R" already uses for "I", just
         applied to "D"'s own output -- keeping the real "faster,
         fragmenting" character of a D-run audible without unbounded
         compounding.

    Every bar's cell/deltas are concatenated in label order into one Motif
    spanning the full `total_beats` -- exactly what a non-IRVD
    `generate_motif` call would have returned, so nothing downstream needs
    to know IRVD was involved at all.
    """
    labels = phrase_plan(irvd_bars)
    bar_beats = total_beats / irvd_bars

    base_bar: Motif | None = None
    previous_bar: Motif | None = None
    first_d_bar: Motif | None = None
    prev_label: str | None = None
    cells: list[dict] = []
    deltas: list[int] = []
    for label in labels:
        if label == "I":
            bar = generate_motif(
                bar_beats, allowed_lengths, hit_chance, rng, scale, vocab_weights,
                chromatic=chromatic, dissonance=dissonance, base_degree=base_degree,
                group_beats=None, pedal=pedal, feel=feel, markov=markov,
            )
            base_bar = bar
        elif label == "R":
            bar = Motif(cell=[dict(c) for c in base_bar.cell], deltas=list(base_bar.deltas))
        elif label == "V":
            bar = transpose(base_bar, _IRVD_VARIATION_DEGREES)
        elif prev_label == "D":
            # A real, CONSECUTIVE "D" -- reuse the first D bar's own
            # already-fragmented result verbatim (real "R"-for-"D"),
            # never a second halving of an already-halved bar. See this
            # function's own docstring for the real, measured evidence
            # this compounding caused.
            bar = Motif(cell=[dict(c) for c in first_d_bar.cell], deltas=list(first_d_bar.deltas))
        else:  # the FIRST "D" in a real run
            half = augment(previous_bar, 0.5)
            bar = Motif(
                cell=half.cell + [dict(c) for c in half.cell],
                deltas=half.deltas + list(half.deltas),
            )
            first_d_bar = bar
        cells.extend(bar.cell)
        deltas.extend(bar.deltas)
        previous_bar = bar
        prev_label = label

    return Motif(cell=cells, deltas=deltas)


# --- P3.4: cross-section theme registry --------------------------------------


class ThemeRegistry:
    """Explicit, caller-owned cache mapping a theme id to a base `Motif`,
    the same pattern as `rhythm.RhythmRegistry`. The first caller for a
    given theme id generates the motif and stores it; every later caller
    with the same id gets back the identical cached Motif -- so a later
    section can look up and *develop* (transpose/augment/invert/fragment)
    an earlier section's theme instead of rolling an unrelated one.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Motif] = {}

    def get_or_create(
        self,
        theme_id: str,
        total_beats: float,
        allowed_lengths: list[float],
        hit_chance: float,
        rng: random.Random,
        scale: Scale,
        vocab_weights: dict,
        chromatic: bool = False,
        dissonance: float = 0.85,
        base_degree: int = 0,
        group_beats: float | None = None,
        pedal: float | None = None,
        feel: str | None = None,
        irvd_bars: int | None = None,
        markov: dict[int, dict[int, float]] | None = None,
    ) -> Motif:
        if theme_id not in self._cache:
            self._cache[theme_id] = generate_motif(
                total_beats,
                allowed_lengths,
                hit_chance,
                rng,
                scale,
                vocab_weights,
                chromatic=chromatic,
                dissonance=dissonance,
                base_degree=base_degree,
                group_beats=group_beats,
                pedal=pedal,
                feel=feel,
                irvd_bars=irvd_bars,
                markov=markov,
            )
        return self._cache[theme_id]

    def __contains__(self, theme_id: str) -> bool:
        return theme_id in self._cache
