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

from rhythm import generate_rhythm, tile_cell
from theory import Scale, shade

__all__ = [
    "Motif",
    "render_motif",
    "transpose",
    "augment",
    "invert",
    "fragment",
    "pick_pitch_interval",
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
    """Weighted pick of one semitone interval (a key of `weights`), by the
    same accumulate-and-compare scheme as `VoiceLeader._weighted_interval`,
    but standalone so it can be reused (and its distribution tested) without
    a full VoiceLeader/Scale context.
    """
    items = list((weights or {}).items())
    if not items:
        raise ValueError("weights must be non-empty")
    total = sum(w for _iv, w in items)
    if total <= 0:
        raise ValueError("weights must sum to a positive total")
    r = rng.random() * total
    acc = 0.0
    for iv, w in items:
        acc += w
        if r <= acc:
            return int(iv)
    return int(items[-1][0])


def _degree_delta_for_interval(scale: Scale, base_degree_index: int, semitone_interval: int) -> int:
    """Snap `base_degree_index`'s pitch + `semitone_interval` semitones into
    the scale, and express the result as a scale-degree DELTA from
    `base_degree_index` -- so chromatic bias (picked in semitone space, where
    `shade()` operates) still comes out as a scale-legal degree delta, never
    a fabricated off-scale pitch."""
    base_pitch = scale.degree(base_degree_index)
    target = scale.nearest(base_pitch + semitone_interval)
    return scale.index_of(target) - base_degree_index


def apply_pedal_bias(weights: dict, pedal: float) -> dict:
    """Re-weight `weights` (semitone-interval -> weight) toward the root
    (interval 0) proportional to `pedal` in `[0, 1]` -- the mechanism this
    project uses to make `preset.pedal` (documented in presets.py as "how
    often a phrase returns to the open low string") measurably change
    `generate_motif`'s output: picking semitone interval 0 always resolves
    to scale-degree DELTA 0 (see `_degree_delta_for_interval` -- interval 0
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
) -> Motif:
    """Generate a fresh Motif: a rhythm cell (via `rhythm.generate_rhythm`)
    plus a scale-degree contour drawn from `vocab_weights` (a preset's
    `vocab.weights`, semitone-interval -> weight).

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
    """
    if group_beats is not None:
        short_cell = generate_rhythm(group_beats, allowed_lengths, hit_chance, rng)
        cell = tile_cell(short_cell, total_beats)
    else:
        cell = generate_rhythm(total_beats, allowed_lengths, hit_chance, rng)
    hits = _count_hits(cell)
    weights = shade(vocab_weights, dissonance) if chromatic else dict(vocab_weights)
    if pedal is not None:
        weights = apply_pedal_bias(weights, pedal)

    deltas: list[int] = []
    degree_index = int(base_degree)
    for _ in range(hits):
        iv = pick_pitch_interval(weights, rng)
        d = _degree_delta_for_interval(scale, degree_index, iv)
        deltas.append(d)
        degree_index += d

    return Motif(cell=cell, deltas=deltas)


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
            )
        return self._cache[theme_id]

    def __contains__(self, theme_id: str) -> bool:
        return theme_id in self._cache
