"""Structure -- Phase 6 of the engine: song-level shape.

Everything below this file is section-level (a rhythm cell, a Motif, a
drum fill). This module is the first thing that thinks about a whole SONG:
what order sections come in, how they're stitched together at the seams,
mid-section devices (half-time drops), how a section's melodic anchor
(scale degree) shifts across the arc, whether a generated section is any
good, and how tempo can move across the section sequence.

Ported per PORTS.md from two functions in
reference/ww-forge-prior-attempt/engine/song_writer.py
(`pickup`, `flatten`/`_bridge`) and one from
reference/ww-forge-prior-attempt/engine/riff_engine.py (`judge`), each
adapted from that project's raw MIDI-slot-list data shapes to this
project's rhythm-cell shapes (`{"duration", "is_rest"}` from `rhythm.py`,
optionally carrying `velocity` from `performance.humanize_take`/
`slam.mark_pinch_harmonics`, or `role`/`roles` from `drums.py`).

Hard law from CLAUDE.md/anti-patterns.md this file obeys:
  - Seeded RNG only: every random draw goes through a `random.Random`
    instance passed in by the caller.
  - A mechanism designed but not called from real generation is not done:
    `generate_song_sections` below is what actually calls `theory.arc()`
    and threads its `start_degree` into `motif.generate_motif` for a real
    section sequence -- `arc()` having a `start_degree` field was already
    true before this file existed; this file is what makes it matter.
"""
from __future__ import annotations

import random

from motif import Motif, generate_motif, render_motif
from rhythm import generate_rhythm
from theory import Scale, arc

__all__ = [
    "DEFAULT_GRAPH",
    "walk_graph",
    "generate_section_sequence",
    "pickup",
    "bridge",
    "flatten",
    "apply_half_time",
    "generate_section_content",
    "generate_song_sections",
    "judge",
    "judge_and_retry",
    "tempo_at",
]


# ---------------------------------------------------------------------------
# P6.1 -- weighted section graph
# ---------------------------------------------------------------------------
# Vocabulary reuses theory.ROLE_LETTER's role names (the canonical, non-alias
# keys: intro/build/solo/outro/breakdown/chill) plus "interlude" (P6.6 -- a
# genuinely new node type, not in ROLE_LETTER; see generate_section_content,
# which routes it through arc(role="chill") at a further-reduced hit_chance
# rather than inventing a seventh ARC row).
#
# Each node maps to {destination: weight}. A destination with weight 0 (or
# simply absent) can never be walked to from that node -- same hard
# guarantee as rhythm.pick_blast_type, not just "unlikely". "outro only
# follows certain sections" is expressed structurally: only breakdown, solo
# and interlude have any positive-weight edge to "outro" at all; intro,
# build and chill do not list it, so the walk can never land on outro
# straight out of an intro.
DEFAULT_GRAPH: dict[str, dict[str, float]] = {
    "intro": {"build": 3.0, "chill": 1.0, "breakdown": 1.0},
    "build": {"breakdown": 4.0, "solo": 1.0, "chill": 1.0},
    "breakdown": {"build": 2.0, "interlude": 2.0, "solo": 1.0, "chill": 1.0, "outro": 1.0},
    "solo": {"breakdown": 3.0, "build": 1.0, "outro": 1.0},
    "interlude": {"breakdown": 3.0, "build": 1.0, "outro": 1.0},
    "chill": {"build": 2.0, "breakdown": 1.0, "interlude": 1.0},
    "outro": {},
}


def walk_graph(
    graph: dict[str, dict[str, float]],
    start: str,
    length: int,
    rng: random.Random,
) -> list[str]:
    """Walk a weighted section-transition graph for up to `length` steps
    (the returned sequence always starts with `start`).

    At each step, the next node is chosen from `graph[current]` by weight
    (`rng.choices`, the same accumulate-and-compare mechanism already
    validated for `rhythm.pick_blast_type`): a destination with weight <= 0
    is filtered out first and so can NEVER be picked, not merely made
    unlikely. If a node has no positive-weight outgoing edge at all (e.g.
    "outro" in `DEFAULT_GRAPH`), the walk stops early and the returned
    sequence is shorter than `length` -- this is deliberate (a terminal
    node terminates the song), not a bug.

    Two calls with the same `graph`, `start`, `length` and an
    identically-seeded `random.Random` produce byte-identical sequences
    (project law: seeded RNG, same seed = same bytes).
    """
    if start not in graph:
        raise ValueError(f"unknown start node {start!r} (not in graph)")
    if length <= 0:
        raise ValueError("length must be > 0")
    for node, edges in graph.items():
        for dest, weight in edges.items():
            if weight < 0:
                raise ValueError(
                    f"negative weight for edge {node!r} -> {dest!r}: {weight!r}"
                )

    seq = [start]
    current = start
    while len(seq) < length:
        edges = graph.get(current) or {}
        items = [(dest, w) for dest, w in edges.items() if w > 0]
        if not items:
            break
        names = [dest for dest, _w in items]
        weights = [w for _dest, w in items]
        current = rng.choices(names, weights=weights, k=1)[0]
        seq.append(current)
    return seq


def generate_section_sequence(
    rng: random.Random,
    length: int,
    start: str = "intro",
    graph: dict[str, dict[str, float]] | None = None,
) -> list[str]:
    """Convenience wrapper over `walk_graph` using `DEFAULT_GRAPH` unless a
    caller supplies their own."""
    return walk_graph(graph if graph is not None else DEFAULT_GRAPH, start, length, rng)


# ---------------------------------------------------------------------------
# P6.2 -- flatten + bridge + pickup
# ---------------------------------------------------------------------------
# Ported from song_writer.pickup/_bridge/flatten. The source operates on
# whole-song dicts with parallel guitar/guitar_r/drums/bass MIDI-slot lists
# and a "slots_per_bar" grid; this project's sections are plain rhythm-cell
# lists (`{"duration", "is_rest", ...}`), so every "slot" below is a cell
# and "resample" maps a cell list onto a different cell COUNT rather than a
# different slot count within a fixed bar.


def _resample(cells: list[dict], n: int) -> list[dict]:
    """Port of song_writer._resample: stretch/shrink `cells` onto exactly
    `n` entries by nearest-index lookup (no interpolation of duration --
    each output slot copies whichever input cell falls at its proportional
    position), the same cheap resampling the source uses to fit a
    variable-length section onto a fixed bridge span.
    """
    if n <= 0:
        return []
    if not cells:
        return [{"duration": 0.0, "is_rest": True} for _ in range(n)]
    out = []
    for i in range(n):
        j = min(len(cells) - 1, int(i * len(cells) / n))
        out.append(dict(cells[j]))
    return out


def pickup(prev_cells: list[dict], next_cells: list[dict], n: int = 2) -> list[dict]:
    """Port of song_writer.pickup: "last n cells of prev copy first n of
    next so joins don't drop." Returns a NEW cell list shaped like
    `prev_cells` but with its last `n` cells' `duration`/`is_rest`
    overwritten from `next_cells`' first `n` -- `n` is capped to whatever
    both lists actually have, so a short section never indexes out of
    range. Empty `prev_cells` or `next_cells` is returned as `prev_cells`
    unchanged (nothing to pick up from/into), matching the source's
    early-return.
    """
    if not prev_cells or not next_cells:
        return list(prev_cells)
    out = [dict(c) for c in prev_cells]
    k = min(n, len(out), len(next_cells))
    if k <= 0:
        return out
    start = len(out) - k
    for j in range(k):
        src = next_cells[j]
        out[start + j] = {"duration": src["duration"], "is_rest": src["is_rest"]}
    return out


def bridge(prev_cells: list[dict], next_cells: list[dict], bridge_len: int = 2) -> list[dict]:
    """Port of song_writer._bridge: a short standalone transition cell
    list -- first half sampled from the TAIL of `prev_cells`, second half
    sampled from the HEAD of `next_cells` (each resampled to fit its half
    of `bridge_len` if the source section is shorter), i.e. "first half
    last bar of prev, second half first bar of next" per the source
    docstring, translated from bars to cells.

    Two of the source's concrete devices are carried over structurally
    (this project's cells have no drum-note-number concept, so they are
    expressed as forced hits rather than specific crash/kick/snare notes):
      - downbeat accent: the transition's FIRST cell is forced to a hit
        (stand-in for the source unconditionally adding crash(49)+kick(36)
        to the bridge's slot 0).
      - pickup fill: the transition's last 1-2 cells are forced to hits
        (stand-in for the source's snare(38) pickup fill on the last 1-2
        slots) -- so the seam always resolves into the next section with
        motion, never a hole.
    """
    if bridge_len <= 0:
        raise ValueError("bridge_len must be > 0")
    if not prev_cells or not next_cells:
        raise ValueError("prev_cells and next_cells must both be non-empty")

    half = max(1, bridge_len // 2)
    tail_src = prev_cells[-half:] if len(prev_cells) >= half else prev_cells
    head_src = next_cells[: bridge_len - half] if len(next_cells) >= (bridge_len - half) else next_cells
    tail = _resample(tail_src, half)
    head = _resample(head_src, bridge_len - half)
    cells = [dict(c) for c in (tail + head)]

    cells[0] = {**cells[0], "is_rest": False}
    fill_len = min(2, len(cells))
    for k in range(1, fill_len + 1):
        cells[-k] = {**cells[-k], "is_rest": False}
    return cells


def flatten(sections: list[list[dict]], blend_n: int = 2, bridge_len: int = 2) -> list[dict]:
    """Port of song_writer.flatten: assemble a whole song by concatenating
    `sections` (each a rhythm cell list) in order, with a real transition
    at every seam instead of a naive concatenation -- matching the
    source's per-pair `_bridge(s, secs[i + 1])` call between every
    adjacent section.

    In addition (per the P6.2 brief: "blend/overwrite the last couple of
    cells of the outgoing section with information from the incoming
    section's first cells"), each outgoing section's own tail is first run
    through `pickup()` against the next section's head, so the seam shows
    a measurable blend on BOTH sides: the outgoing section's last
    `blend_n` cells already lean toward what's coming, and a `bridge()`
    transition is spliced in between before the incoming section starts.
    """
    if not sections:
        return []

    blended: list[list[dict]] = []
    for i, sec in enumerate(sections):
        cells = [dict(c) for c in sec]
        if i + 1 < len(sections):
            cells = pickup(cells, sections[i + 1], n=blend_n)
        blended.append(cells)

    flat: list[dict] = []
    for i, cells in enumerate(blended):
        flat.extend(cells)
        if i + 1 < len(sections):
            flat.extend(bridge(sections[i], sections[i + 1], bridge_len=bridge_len))
    return flat


# ---------------------------------------------------------------------------
# P6.3 -- half-time inside a section
# ---------------------------------------------------------------------------


def apply_half_time(cells: list[dict], start: int, length: int, factor: float = 2.0) -> list[dict]:
    """Half-time drop scoped to a SUB-RANGE of a larger cell list: cell
    indices `[start, start + length)` get their durations multiplied by
    `factor` (default 2.0 -- doubled duration = halved density), reusing
    exactly `motif.augment`'s per-cell duration-scaling rule but applied to
    only part of the list instead of the whole thing. Cells outside the
    range are returned byte-identical to the input.

    Matching `augment`, this does not merge adjacent cells into fewer,
    longer ones -- each targeted cell keeps its own (now longer) slot, the
    same behaviour `augment` already has for a whole motif. The total
    duration of the targeted range still doubles either way, which is the
    audible half-time effect; a caller wanting fewer/merged cells can
    additionally re-tile the result.
    """
    if factor <= 0:
        raise ValueError("factor must be > 0")
    if start < 0 or length < 0:
        raise ValueError("start and length must both be >= 0")
    if start + length > len(cells):
        raise ValueError("start + length exceeds the cell list's bounds")

    out = [dict(c) for c in cells]
    for i in range(start, start + length):
        out[i] = {**out[i], "duration": out[i]["duration"] * float(factor)}
    return out


# ---------------------------------------------------------------------------
# P6.4 / P6.6 -- arc()-driven section content (modulation + interlude)
# ---------------------------------------------------------------------------
# "A mechanism designed but not called from real generation is not done":
# theory.arc()'s start_degree/register fields already existed before this
# file; generate_section_content and generate_song_sections below are what
# actually route them into motif.generate_motif for a real sequence.

# P6.6: "interlude" is a genuinely new node (not in theory.ROLE_LETTER).
# Per the brief, it does not get a new ARC row -- it borrows the existing
# low-energy "chill" row (letter K, energy 0.20) via arc(role="chill"), and
# is additionally scaled further down on top of that, so an interlude reads
# as distinctly calmer than a plain chill section, not just a synonym for
# one.
_INTERLUDE_ARC_ROLE = "chill"
_INTERLUDE_HIT_CHANCE_SCALE = 0.5


def generate_section_content(
    role: str,
    scale: Scale,
    rng: random.Random,
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    vocab_weights: dict,
    chromatic: bool = False,
    dissonance: float | None = None,
) -> dict:
    """Generate one section's motif, actually anchored on `theory.arc()`'s
    `start_degree` for `role` -- this is the P6.4 wiring: `arc(role=role)`
    is looked up and its `start_degree` is passed straight through as
    `motif.generate_motif`'s `base_degree`, and its `register` (a semitone
    neck-position offset) is added to every rendered pitch. Two sections
    with different roles/letters therefore anchor on different scale
    degrees for real, not just as an available-but-unused field.

    `role == "interlude"` (P6.6) routes through `arc(role="chill")`
    instead of its own ARC row, and additionally scales `hit_chance` down
    by `_INTERLUDE_HIT_CHANCE_SCALE` -- a distinctly lower-energy character
    than a verse/breakdown, not merely "chill again".

    Returns `{"motif": Motif, "pitches": list[int], "arc": dict}`.
    """
    arc_role = _INTERLUDE_ARC_ROLE if role == "interlude" else role
    row = arc(role=arc_role)
    dis = row["dissonance"] if dissonance is None else dissonance
    effective_hit_chance = (
        hit_chance * _INTERLUDE_HIT_CHANCE_SCALE if role == "interlude" else hit_chance
    )

    m = generate_motif(
        total_beats,
        allowed_lengths,
        effective_hit_chance,
        rng,
        scale,
        vocab_weights,
        chromatic=chromatic,
        dissonance=dis,
        base_degree=row["start_degree"],
    )
    pitches = [p + row["register"] for p in render_motif(m, scale, start_degree=row["start_degree"])]
    return {"motif": m, "pitches": pitches, "arc": row}


def generate_song_sections(
    sequence: list[str],
    scale: Scale,
    rng: random.Random,
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    vocab_weights: dict,
    chromatic: bool = False,
) -> list[dict]:
    """Generate real content for a whole section-graph sequence (from
    `generate_section_sequence`/`walk_graph`): one `generate_section_content`
    call per role in `sequence`, sharing one `rng` across the whole song
    (so the song is one seeded draw, not N independent ones) and one
    `Scale`/`vocab_weights` (the song's key and interval vocabulary stay
    fixed; only the per-section anchor degree/energy moves, per
    god-tier-metal-scope.md sec. 2's "home key vs modulated key").
    """
    if not sequence:
        raise ValueError("sequence must be non-empty")
    return [
        generate_section_content(
            role, scale, rng, total_beats, allowed_lengths, hit_chance,
            vocab_weights, chromatic=chromatic,
        )
        for role in sequence
    ]


# ---------------------------------------------------------------------------
# P6.5 -- judge / retry
# ---------------------------------------------------------------------------
# Ported from riff_engine.judge, adapted from the source's raw
# `[(pitch, velocity), ...]` MIDI-slot lists to this project's rhythm
# cells. The source's `hits`/`opens`/`pms`/`kicks`/`locked`/`pm_ratio`/
# `kick_lock`/`ok` names and thresholds are kept verbatim; only how a "hit",
# "open" and "kick" are read off a cell changes:
#   - a guitar "hit" is a non-rest cell (`not cell["is_rest"]`), matching
#     every rhythm cell in this project (generate_rhythm/Motif.cell).
#   - "open" vs "palm-muted" is this project's existing `velocity` field
#     (produced by `performance.humanize_take`/`slam.mark_pinch_harmonics`,
#     both of which default plain hits to velocity_base=100 and reserve
#     higher velocities for accents) at the source's own threshold:
#     velocity >= 110 is open/ringing, < 110 is palm-muted. A cell with no
#     `velocity` field at all (e.g. a bare `generate_rhythm` cell that was
#     never humanized) defaults to 100 -- i.e. muted, the genre-typical
#     default articulation, matching humanize_take's own default.
#   - a drum "kick" slot is one this project's own drums.py already marks
#     as a kick: `role == "KICK"` (drums.kick_follows_guitar's shape) or
#     `"KICK" in roles` (drums.generate_blast_fill's shape) -- both
#     existing conventions are honoured rather than inventing a third.
def _cell_is_hit(cell: dict) -> bool:
    return not cell.get("is_rest", True)


def _cell_is_open(cell: dict) -> bool:
    return cell.get("velocity", 100) >= 110


def _cell_has_kick(cell: dict) -> bool:
    if cell.get("role") == "KICK":
        return True
    return "KICK" in (cell.get("roles") or [])


def judge(comp: dict) -> dict:
    """Judge one composition's `{"guitar": [...], "drums": [...]}` cell
    lists for breakdown-writing quality, per riff_engine.judge's real
    thresholds: enough hits, a healthy mix of open/muted (not either
    extreme), and the muted hits mostly locked to a kick underneath.
    """
    guitar = comp.get("guitar") or []
    drums = comp.get("drums") or []

    hits = sum(1 for c in guitar if _cell_is_hit(c))
    opens = sum(1 for c in guitar if _cell_is_hit(c) and _cell_is_open(c))
    pms = hits - opens

    locked = 0
    for g, d in zip(guitar, drums):
        if _cell_is_hit(g) and not _cell_is_open(g) and _cell_has_kick(d):
            locked += 1

    pm_ratio = (pms / hits) if hits else 0
    kick_lock = (locked / max(1, pms)) if pms else 0
    ok = hits >= 4 and 0.25 <= pm_ratio <= 0.95 and kick_lock >= 0.25
    return {"ok": ok, "hits": hits, "pm_ratio": round(pm_ratio, 2), "kick_lock": round(kick_lock, 2)}


def judge_and_retry(generate_fn, *args, max_seeds: int = 6, **kwargs) -> dict:
    """Call `generate_fn(rng, *args, **kwargs) -> comp` with a fresh
    `random.Random(seed)` for `seed` in `range(max_seeds)`, stopping at the
    first attempt `judge()` calls `ok`. If none of `max_seeds` attempts
    pass, the LAST attempt is returned anyway (documented gracefully-give-up
    behaviour -- callers that need a hard failure should check
    `judge(result)["ok"]` themselves) rather than raising.
    """
    if max_seeds <= 0:
        raise ValueError("max_seeds must be > 0")

    result = None
    for seed in range(max_seeds):
        rng = random.Random(seed)
        result = generate_fn(rng, *args, **kwargs)
        if judge(result)["ok"]:
            return result
    return result


# ---------------------------------------------------------------------------
# P6.7 -- tempo curve
# ---------------------------------------------------------------------------
# Song-internal planning data only -- per scope sec. 17.5 the Reaper export
# stays one constant tempo; this never touches a Reaper tempo map.


def tempo_at(section_index: int, base_bpm: float, curve: dict) -> float:
    """BPM for `section_index` given `base_bpm` and one curve descriptor:

      {"type": "drop", "at": int, "bpm": float}
        `base_bpm` for every section before `at`; from `at` onward, BPM
        jumps straight to `bpm` -- no intermediate value, an abrupt
        slam-breakdown tempo drop.

      {"type": "ramp", "start": int, "end": int, "bpm": float}
        `base_bpm` at/before `start`, linearly interpolated up to `bpm` by
        `end` (inclusive), holding `bpm` from `end` onward -- a gradual,
        monotonic change across `[start, end]`, never a single step.
    """
    kind = curve.get("type")
    if kind == "drop":
        at = int(curve["at"])
        return float(curve["bpm"]) if section_index >= at else float(base_bpm)

    if kind == "ramp":
        start = int(curve["start"])
        end = int(curve["end"])
        if end <= start:
            raise ValueError("ramp curve requires end > start")
        target = float(curve["bpm"])
        base = float(base_bpm)
        if section_index <= start:
            return base
        if section_index >= end:
            return target
        frac = (section_index - start) / (end - start)
        return base + frac * (target - base)

    raise ValueError(f"unknown tempo curve type: {kind!r}")
