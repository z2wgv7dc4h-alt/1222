"""Drums -- Phase 4 of the engine.

Drums reference articulations by a semantic ROLE, never a raw MIDI note.
This is deliberate and load-bearing: the user's real SFZ kit (confirmed in
god-tier-metal-scope.md sec. 11.7) maps note numbers to articulations in a
way that conflicts with older/other conventions -- e.g. on THIS kit note 48
is a hi-hat "swish/open" articulation, not an extra tom, and note 63 is a
rototom, not a "closed hat" as an older internal vocabulary assumed. A
different kit could remap every note. By writing the generation logic
against roles (`KICK`, `SNARE`, ...) and resolving role -> note only through
`note_for_role`, swapping kits means swapping `ROLE_TO_NOTE`/`FALLBACKS`,
never touching generation code.

Hard law from CLAUDE.md that every function here obeys:
  - Grid is the writer. No cloud/AI model anywhere in this file.
  - Seeded RNG only: every random draw goes through a `random.Random`
    instance passed in by the caller.
  - One class per job (this module defines none of its own -- it reuses
    `rhythm.RhythmRegistry` for the shared-sequence mechanism rather than
    inventing a second cache).
"""

from __future__ import annotations

import random

from midi_vocab import vocabulary_informed_hit_chance
from rhythm import RhythmRegistry, pick_blast_type

_EPS = 1e-9


# --- P4.1: role -> kit MIDI note, with an explicit, wired fallback ----------

# This kit's real note map (god-tier-metal-scope.md sec. 11.7, read directly
# from the four .sfz files -- "Black Pearl"/"Red Zeppelin", 4pc/5pc). Every
# role the engine can emit resolves to one of these notes except CHINA,
# which this kit has no sample for at all (see FALLBACKS below).
#
# Tom assignment: this kit exposes four tom notes (41 floor tom, 43 floor
# tom 2/edge -- kit-dependent, only present on some configs, 45 rack tom,
# 47 rack tom 2) but the role vocabulary only has three tom roles. Note 43
# is deliberately left unmapped to a role (it is the kit-dependent "extra"
# tom, not a stable articulation every kit config has); the three stable
# notes are assigned high-to-low by note number ascending = pitch
# descending, which is this project's documented, internally-consistent
# convention for this kit:
#   TOM_HIGH -> 45 (rack tom)      TOM_MID -> 47 (rack tom 2)
#   TOM_LOW  -> 41 (floor tom)
ROLE_TO_NOTE: dict[str, int] = {
    "KICK": 36,
    "SNARE": 38,
    "HANDCLAP": 39,
    "SNARE_RIMSHOT": 40,
    "TOM_LOW": 41,
    "HIHAT_CLOSED": 42,
    "HIHAT_PEDAL": 44,
    "TOM_HIGH": 45,
    "HIHAT_SEMI_OPEN": 46,
    "TOM_MID": 47,
    "HIHAT_OPEN": 48,
    "CRASH_1": 49,
    "CRASH_1_CHOKE": 50,
    "RIDE": 51,
    "RIDE_CHOKE": 52,
    "RIDE_BELL": 53,
    "TAMBOURINE": 54,
    "SPLASH": 55,
    "COWBELL": 56,
    "CRASH_2": 57,
    "CRASH_2_CHOKE": 58,
    "RIDE_SHANK": 59,
    "ROTOTOM_HI": 61,
    "ROTOTOM_MID": 62,
    "ROTOTOM_LO": 63,
    "MARACA": 64,
    # Deliberately NOT present: CHINA -- this kit has no china sample. See
    # FALLBACKS. Adding a fabricated note here would be exactly the
    # "silently emit a wrong/missing note" failure mode sec. 11.7 forbids.
}

# Roles with no sample on this kit resolve through here instead of
# `ROLE_TO_NOTE`. Recommended substitute per sec. 11.7: CHINA -> CRASH_2
# (both are bright, fast-decaying accent cymbals -- the closest stand-in
# this kit has).
FALLBACKS: dict[str, str] = {
    "CHINA": "CRASH_2",
}


def note_for_role(
    role: str,
    mapping: dict[str, int] = ROLE_TO_NOTE,
    fallback: dict[str, str] = FALLBACKS,
) -> int:
    """Resolve a semantic drum role to this kit's real MIDI note.

    This is the ONLY wired lookup path generation code should use -- never
    a bare `ROLE_TO_NOTE[role]` dict index, which would `KeyError` on a
    missing-sample role like `CHINA` instead of falling back, or (worse)
    a `.get(role, some_default)` that would silently fabricate a note for
    a typo'd/unknown role.

    Resolution order:
      1. `role` is directly in `mapping` -> return its note.
      2. `role` is in `fallback` -> resolve the substitute role instead
         (recursively, so a chain of fallbacks would also work, with a
         cycle guard so a misconfigured fallback loop fails loudly rather
         than recursing forever).
      3. Neither -> raise `KeyError`. An unknown/bogus role must never
         resolve to a fabricated note.
    """
    seen: set[str] = set()
    current = role
    while True:
        if current in mapping:
            return mapping[current]
        if current in fallback and current not in seen:
            seen.add(current)
            current = fallback[current]
            continue
        raise KeyError(
            f"unknown or unmapped drum role {role!r} for this kit "
            f"(no entry in ROLE_TO_NOTE or FALLBACKS)"
        )


# --- P4.2: kick follows guitar accents (breakdown convention) ---------------


def kick_follows_guitar(guitar_cells: list[dict]) -> list[dict]:
    """Derive a KICK pattern that hits on exactly the slots where the guitar
    hits, for palm-muted breakdown-style riffs.

    This is a deliberate "keep as-is" port of the project's prior validated
    convention: in breakdowns, the kick doubles the guitar's palm-muted
    accents rather than running an independent pattern -- standard practice
    in the genre (Born of Osiris / Infant Annihilator breakdown writing).
    Fully deterministic (no RNG): the guitar's hit/rest layout IS the kick's
    hit/rest layout, one-to-one, slot for slot.

    `guitar_cells` is any `list[{"duration", "is_rest"}]`, e.g. straight from
    `rhythm.generate_rhythm`. Returns a same-length list of
    `{"duration", "is_rest", "role"}` cells: `role` is `"KICK"` on every
    slot the guitar hits, and `None` on every slot the guitar rests --
    i.e. the returned cells' hit positions are exactly the guitar's hit
    positions, never more, never fewer.
    """
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")

    kick_cells: list[dict] = []
    for cell in guitar_cells:
        is_rest = bool(cell["is_rest"])
        kick_cells.append(
            {
                "duration": cell["duration"],
                "is_rest": is_rest,
                "role": None if is_rest else "KICK",
            }
        )
    return kick_cells


# --- kick-style dispatch (closes the real, tracked gap: preset.kick was ---
# --- declared per style but nothing branched on it) -------------------------


def _kick_sparse(guitar_cells: list[dict]) -> list[dict]:
    """"sparse" kick style: a reduced subset of the guitar's own hit
    positions -- every OTHER guitar hit becomes a kick (hit index 0, 2, 4,
    ... among the guitar's hits, 0-indexed), the rest stay silent. Lower
    density than "bounce"/"lock" (which double every guitar hit 1:1), but
    still anchored to real guitar hit positions rather than an independent
    grid -- a thinned-out lock, not a different rhythm entirely.
    """
    out: list[dict] = []
    hit_index = 0
    for cell in guitar_cells:
        is_rest = bool(cell["is_rest"])
        if is_rest:
            out.append({"duration": cell["duration"], "is_rest": True, "role": None})
            continue
        keep = (hit_index % 2 == 0)
        hit_index += 1
        out.append(
            {
                "duration": cell["duration"],
                "is_rest": not keep,
                "role": "KICK" if keep else None,
            }
        )
    return out


def _euclidean_hits(pulses: int, steps: int) -> list[bool]:
    """`pulses` hits distributed as evenly as possible across `steps` slots.

    Uses the modular/"Bresenham" construction -- hit at step `i` (0-indexed)
    iff `(i * pulses) % steps < pulses` -- which is a well-known equivalent
    to Bjorklund's algorithm for generating maximally-even distributions
    (e.g. `_euclidean_hits(3, 8)` gives the canonical E(3,8) tresillo
    X..X..X., hits at indices 0, 3, 6). `pulses` is clamped into
    `[0, steps]` first so a caller can never overshoot (more "pulses" than
    slots is meaningless for this construction).
    """
    if steps <= 0:
        raise ValueError("steps must be > 0")
    if pulses < 0:
        raise ValueError("pulses must be >= 0")
    pulses = min(pulses, steps)
    if pulses == 0:
        return [False] * steps
    if pulses == steps:
        return [True] * steps
    return [((i * pulses) % steps) < pulses for i in range(steps)]


def _kick_euclid(guitar_cells: list[dict]) -> list[dict]:
    """"euclid" kick style: a genuine Euclidean rhythm (see
    `_euclidean_hits`) placed across exactly `len(guitar_cells)` slots, with
    the pulse COUNT derived from the guitar's own hit count (so density is
    comparable to the guitar part) but the PLACEMENT computed independently
    via the even-distribution formula -- deliberately NOT a copy of the
    guitar's own hit positions, which is the whole point of "euclid" as a
    distinct style from "bounce"/"lock".
    """
    steps = len(guitar_cells)
    pulses = sum(1 for c in guitar_cells if not c["is_rest"])
    hits = _euclidean_hits(pulses, steps)
    return [
        {
            "duration": cell["duration"],
            "is_rest": not is_hit,
            "role": "KICK" if is_hit else None,
        }
        for cell, is_hit in zip(guitar_cells, hits)
    ]


# Shared by every "fixed metric overlay on the guitar's own cell grid"
# style below (two_step's kick pattern, and the snare-backbeat family
# further down): compute each cell's cumulative start time, then decide
# hits by real absolute beat position rather than by copying/thinning the
# guitar's own hit/rest layout.


def _cell_starts(cells: list[dict]) -> tuple[list[float], float]:
    """Per-cell cumulative start time (beats) and the sequence's total
    length -- the real timeline every cyclic-overlay style below places
    its hits against."""
    starts: list[float] = []
    cumulative = 0.0
    for cell in cells:
        starts.append(cumulative)
        cumulative += cell["duration"]
    return starts, cumulative


def _time_to_cell_index(starts: list[float], t: float) -> int | None:
    """Index of the cell whose span contains real time `t`, or `None` if
    `t` falls before the first cell (never fabricates a position)."""
    idx = None
    for i, s in enumerate(starts):
        if s <= t + _EPS:
            idx = i
        else:
            break
    return idx


def _cyclic_hit_indices(
    starts: list[float], total_beats: float, cycle_beats: float, offsets: tuple[float, ...]
) -> set[int]:
    """Cell indices hit by a pattern that repeats every `cycle_beats`,
    firing at each of `offsets` (beats from the start of each cycle) --
    the real, shared mechanism behind "two_step"'s kick pattern and every
    named snare-backbeat style below. A target time past the sequence's
    end, or one that doesn't land inside any cell's span, is simply
    skipped -- never a fabricated extra hit."""
    hit_indices: set[int] = set()
    cycle_start = 0.0
    while cycle_start < total_beats - _EPS:
        for offset in offsets:
            t = cycle_start + offset
            if t >= total_beats - _EPS:
                continue
            idx = _time_to_cell_index(starts, t)
            if idx is not None:
                hit_indices.add(idx)
        cycle_start += cycle_beats
    return hit_indices


def _cells_from_hit_indices(cells: list[dict], hit_indices: set[int], role_name: str) -> list[dict]:
    """Same-length role-tagged cell list from a set of hit indices --
    shared output shape for every style in this module."""
    return [
        {
            "duration": cell["duration"],
            "is_rest": i not in hit_indices,
            "role": role_name if i in hit_indices else None,
        }
        for i, cell in enumerate(cells)
    ]


def _kick_two_step(guitar_cells: list[dict]) -> list[dict]:
    """"two_step" kick style: this project's documented interpretation of
    the metalcore breakdown "two-step" convention (no single universally
    rigid definition exists in the genre, so this one is deliberately
    concrete and testable): a half-time stepping feel where the kick lands
    twice per 2-beat cycle -- on the cycle's downbeat (beat offset 0.0) and
    on the "and" of the second beat (beat offset 1.5), the classic
    kick-into-the-snare-on-3 breakdown step. This is a fixed metric overlay
    on the SAME cell/duration grid the guitar used (like "blast" is), not a
    copy of the guitar's own hit/rest layout -- so it reads as genuinely
    different from "sparse"/"bounce" rather than a thinned or exact copy.

    Cell durations come straight from `guitar_cells` (same length, same
    duration per slot); only which cells count as a "hit" is decided by
    this pattern. A target time that does not land inside any cell's span
    (e.g. a very short section) is simply skipped rather than fabricating
    an extra slot.
    """
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    starts, total_beats = _cell_starts(guitar_cells)
    hit_indices = _cyclic_hit_indices(starts, total_beats, 2.0, (0.0, 1.5))
    return _cells_from_hit_indices(guitar_cells, hit_indices, "KICK")


def _kick_blast(guitar_cells: list[dict]) -> list[dict]:
    """"blast" kick style: kick on every single cell, continuous and dense,
    regardless of the guitar's own rest positions -- the "constant blast
    under a brutal chug" convention (deathcore.json's straightforward
    brutal-chugging archetype)."""
    return [
        {"duration": cell["duration"], "is_rest": False, "role": "KICK"}
        for cell in guitar_cells
    ]


def _kick_double_kick(guitar_cells: list[dict]) -> list[dict]:
    """"double_kick" style: a continuous, fixed straight-16th-note pulse
    (real double bass) -- ported from Metalerator's real `double_bass`
    kick generator (`reference/metalerator/metalerator/drums/kick/
    kick.py`, `Kick.double_bass`: `j=0; for _ in range(4): kicks.append(
    ...+j); j+=0.25` -- four hits per beat, every beat, unconditionally).
    Mechanically distinct from "blast" (which hits every GUITAR cell
    regardless of that cell's own duration -- 8th/quarter/16th mixed) --
    this is a fixed ABSOLUTE 16th-note grid independent of the guitar's
    own rhythm, same `_cyclic_hit_indices` overlay mechanism as
    "two_step"/the snare-backbeat family."""
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    starts, total_beats = _cell_starts(guitar_cells)
    hit_indices = _cyclic_hit_indices(starts, total_beats, 0.25, (0.0,))
    return _cells_from_hit_indices(guitar_cells, hit_indices, "KICK")


_KICK_STYLES = {
    "bounce": kick_follows_guitar,
    "lock": kick_follows_guitar,
    "sparse": _kick_sparse,
    "euclid": _kick_euclid,
    "two_step": _kick_two_step,
    "blast": _kick_blast,
    "double_kick": _kick_double_kick,
}


def kick_pattern_for_style(
    guitar_cells: list[dict], style: str, rng: random.Random | None = None
) -> list[dict]:
    """Real dispatch on a preset's declared `.kick` style name -- the wired
    replacement for always calling `kick_follows_guitar` regardless of what
    style a preset actually declares (see this module's and song.py's
    docstrings on the gap this closes).

    `"bounce"` and `"lock"` share `kick_follows_guitar`'s exact-match
    behavior: the real presets that declare them (groovy/melodic for
    "bounce", tech for "lock" -- tech.json's own description says
    "kick-locked triplet chug") both want the kick doubling the guitar's
    hits 1:1; there is no real preset asking for a different mechanical
    behavior between the two names, just a different genre label for the
    same lock convention. `"sparse"`, `"euclid"`, `"two_step"` and
    `"blast"` are real, distinct mechanisms -- see `_kick_sparse`/
    `_kick_euclid`/`_kick_two_step`/`_kick_blast`.

    `rng` is accepted for interface symmetry with the rest of this
    project's generation calls (every real style here is currently fully
    deterministic given `guitar_cells`, same as `kick_follows_guitar`
    itself), but is not required by any current style.

    Raises `ValueError` on an unrecognized style name rather than silently
    falling back to a default style -- per project law (anti-patterns.md),
    an unrecognized input must fail closed, never guess.
    """
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    handler = _KICK_STYLES.get(style)
    if handler is None:
        raise ValueError(
            f"unknown kick style {style!r} "
            f"(no handler wired for it in drums._KICK_STYLES)"
        )
    return handler(guitar_cells)


# Real per-ROLE overlay on top of a preset's own declared kick style:
# high-energy sections (build/solo) get a real, VARIED overlay -- either
# "double_kick" (continuous pulse) or "blast" (every cell), picked per
# section via the caller's own real rng -- regardless of what the preset
# otherwise declares. Real drumming uses both devices for high-energy
# passages, not just one repeated choice every time (direct answer to
# real listening feedback: "no double kick... just generic kicks every
# now and then"). Every genre gets this identically -- the same "wire by
# mechanism, not by preset id" principle X.9's snare-role table already
# uses, not something gated to one style. Every other role keeps the
# preset's own kick style exactly as before (backward compatible with
# every existing kick-style test).
_ROLE_KICK_OVERRIDE_CHOICES: dict[str, tuple[str, ...]] = {
    "build": ("double_kick", "blast"),
    "solo": ("double_kick", "blast"),
}


def kick_pattern_for_role(
    guitar_cells: list[dict], role: str, preset_kick: str, rng: random.Random | None = None
) -> list[dict]:
    """Real kick style for a section: `preset_kick` (the preset's own
    declared style) for every role EXCEPT `build`/`solo`, which pick
    between the real "double_kick"/"blast" overlay styles via `rng` --
    see `_ROLE_KICK_OVERRIDE_CHOICES`. Delegates entirely to
    `kick_pattern_for_style`, no reimplemented dispatch logic.

    X.22 -- a real, previously-missed inconsistency: `snare_pattern_for_
    role`/`hihat_pattern_for_role` both go silent for `chill`/`interlude`
    (the same "atmospheric sections stay quiet" rule `song.py`'s own
    `lead_mode` logic makes), but this function had no such check -- every
    chill/interlude section got the SAME full-density kick as every other
    section, undermining the entire point of a quiet breather. Fixed to
    match the exact same real rule the other two drum layers already use.

    Raises `ValueError` if `role` has real overlay choices but `rng` is
    `None` -- a real per-section choice needs a real seeded source, never
    a silent default to "always the first option"."""
    if role in ("chill", "interlude"):
        return [{"duration": c["duration"], "is_rest": True, "role": None} for c in guitar_cells]
    choices = _ROLE_KICK_OVERRIDE_CHOICES.get(role)
    if choices is None:
        style = preset_kick
    else:
        if rng is None:
            raise ValueError(f"role {role!r} has real overlay choices and requires an rng")
        style = rng.choice(choices)
    return kick_pattern_for_style(guitar_cells, style, rng=rng)


# --- X.9: real snare backbeat, wired for every preset -----------------------
#
# Closes a real, previously-unaddressed gap: this engine generated a kick
# (P4.2/X.2) and blast/fill patterns (P4.3) but NO snare or hihat layer at
# all -- every generated song was missing the backbeat entirely. Ported
# from the real reference implementation "Metalerator"
# (reference/metalerator/metalerator/drums/snare/snare.py, `Snare.
# snare_step`/`snare_half_step`/`snare_double_time`), a genuinely
# metalcore-and-djent-shared convention per the user's own framing
# ("breakdowns are kinda universal, djent will just have more chugging")
# -- so this is wired for EVERY preset via `snare_pattern_for_role` below,
# not gated to one genre. Ghost notes (Metalerator's quiet grace-note hits
# around the main snare) are a real technique too but don't fit this
# project's fixed-cell-array model without a larger rework -- documented
# here as a deliberate, deferred follow-up, not silently dropped.
#
# Built on the same "fixed metric overlay on the guitar's own cell grid"
# mechanism `_kick_two_step` already uses (`_cyclic_hit_indices`), since
# Metalerator's own `snare_step`/`snare_half_step` are the identical
# device: a real absolute-beat-position pattern, not a copy/thinning of
# the guitar's hit layout.


def _snare_step(guitar_cells: list[dict]) -> list[dict]:
    """"step" snare style: one hit per 4-beat bar, on beat offset 2.0
    (the third beat, 1-indexed) -- Metalerator's real breakdown backbeat
    (`Snare.snare_step`, `i % 4 == 2`), a half-time "kick-into-the-snare"
    feel, NOT the standard rock "2 and 4" (this project checked the real
    source rather than assuming the generic convention)."""
    starts, total_beats = _cell_starts(guitar_cells)
    hit_indices = _cyclic_hit_indices(starts, total_beats, 4.0, (2.0,))
    return _cells_from_hit_indices(guitar_cells, hit_indices, "SNARE")


def _snare_half_step(guitar_cells: list[dict]) -> list[dict]:
    """"half_step" snare style: one hit per 8-beat (2-bar) cycle, on the
    downbeat of the second bar -- Metalerator's real sparser breakdown
    variant (`Snare.snare_half_step`, `i % 8 == 4`)."""
    starts, total_beats = _cell_starts(guitar_cells)
    hit_indices = _cyclic_hit_indices(starts, total_beats, 8.0, (4.0,))
    return _cells_from_hit_indices(guitar_cells, hit_indices, "SNARE")


def _snare_double_time(guitar_cells: list[dict]) -> list[dict]:
    """"double_time" snare style: a hit on every beat except the very
    first of the section -- Metalerator's real high-energy variant
    (`Snare.snare_double_time`, `i % 1 == 0 and i != 0`; since Metalerator
    counts `i` itself in quarter-note/beat units, that condition is simply
    "every beat", with the explicit `i != 0` exclusion kept here too)."""
    starts, total_beats = _cell_starts(guitar_cells)
    hit_indices = _cyclic_hit_indices(starts, total_beats, 1.0, (0.0,))
    hit_indices.discard(0)
    return _cells_from_hit_indices(guitar_cells, hit_indices, "SNARE")


_SNARE_STYLES = {
    "step": _snare_step,
    "half_step": _snare_half_step,
    "double_time": _snare_double_time,
}


def generate_snare_backbeat(guitar_cells: list[dict], style: str) -> list[dict]:
    """Real dispatch on a named snare-backbeat style -- see `_snare_step`/
    `_snare_half_step`/`_snare_double_time`. Raises `ValueError` on an
    unrecognized style, same fail-closed contract as
    `kick_pattern_for_style`."""
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    handler = _SNARE_STYLES.get(style)
    if handler is None:
        raise ValueError(
            f"unknown snare style {style!r} "
            f"(no handler wired for it in drums._SNARE_STYLES)"
        )
    return handler(guitar_cells)


# Real per-ROLE dispatch (not per-preset): every preset's breakdown/intro/
# outro sections get the same real half-time backbeat ("breakdowns are
# kinda universal" -- the user's own framing), build/solo sections (rising
# or featured energy) get the denser double_time variant, and chill/
# interlude sections get NO backbeat at all -- the same judgment call
# `song.py`'s `lead_mode` logic already makes for those two roles (a busy
# kit would clash with an atmospheric/harmonized section).
_ROLE_TO_SNARE_STYLE: dict[str, str | None] = {
    "intro": "step",
    "breakdown": "step",
    "outro": "step",
    "build": "double_time",
    "solo": "double_time",
    "chill": None,
    "interlude": None,
}


def snare_pattern_for_role(guitar_cells: list[dict], role: str) -> list[dict]:
    """Real snare-backbeat cells for a section's ROLE (see
    `_ROLE_TO_SNARE_STYLE`) -- wired for every preset via `song.py`, not
    gated to one genre. An unmapped role defaults to `"step"` (the
    universal breakdown/chug backbeat) rather than raising, since new
    roles can be added to `structure.DEFAULT_GRAPH` independently of this
    table; `chill`/`interlude` are the only roles that go silent."""
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    style = _ROLE_TO_SNARE_STYLE.get(role, "step")
    if style is None:
        return [{"duration": c["duration"], "is_rest": True, "role": None} for c in guitar_cells]
    return generate_snare_backbeat(guitar_cells, style)


# --- X.11: hihat/cymbal layer, wired for every preset -----------------------
#
# Real listening feedback on a generated song: "the drums were really
# basic... no double kick no cymbals or anything being hit. just generic
# kicks every now and then." Confirms a real, previously-unaddressed gap:
# through X.9 this engine had kick + snare, but NOTHING keeping time on a
# cymbal at all -- a real drum kit's hihat/ride is nearly always present
# under a riff, and its total absence is a real, audible reason a
# generated song reads as sparse/basic rather than a real performance.
#
# "closed" is a steady 8th-note pulse -- the universal "hand keeping time"
# convention under a riff (real, generic music knowledge, not genre- or
# reference-specific -- unlike X.8/X.9's ported Metalerator techniques,
# this doesn't need a named source to justify: a hihat playing straight
# 8ths under a chug riff is as basic and universal a drumming fact as
# "snare on the backbeat"). Built on the same `_cyclic_hit_indices`
# overlay mechanism as every other fixed-metric style in this module.


def _hihat_closed(guitar_cells: list[dict]) -> list[dict]:
    """"closed" hihat style: a steady 8th-note pulse (cycle_beats=0.5,
    hit at each cycle's downbeat) -- the real, universal "keeping time"
    convention under a riff."""
    starts, total_beats = _cell_starts(guitar_cells)
    hit_indices = _cyclic_hit_indices(starts, total_beats, 0.5, (0.0,))
    return _cells_from_hit_indices(guitar_cells, hit_indices, "HIHAT_CLOSED")


_HIHAT_STYLES = {"closed": _hihat_closed}


def generate_hihat_pattern(guitar_cells: list[dict], style: str) -> list[dict]:
    """Real dispatch on a named hihat style -- see `_hihat_closed`.
    Raises `ValueError` on an unrecognized style, same fail-closed
    contract as `kick_pattern_for_style`/`generate_snare_backbeat`."""
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    handler = _HIHAT_STYLES.get(style)
    if handler is None:
        raise ValueError(
            f"unknown hihat style {style!r} "
            f"(no handler wired for it in drums._HIHAT_STYLES)"
        )
    return handler(guitar_cells)


# Real per-ROLE dispatch, same shape as the snare table: every role keeps
# a steady hihat except `chill`/`interlude` (the same atmospheric-section
# judgment call the snare table and `song.py`'s `lead_mode` logic both
# already make -- a busy kit clashes with a harmonized/ambient section).
_ROLE_TO_HIHAT_STYLE: dict[str, str | None] = {
    "intro": "closed",
    "breakdown": "closed",
    "outro": "closed",
    "build": "closed",
    "solo": "closed",
    "chill": None,
    "interlude": None,
}


def hihat_pattern_for_role(guitar_cells: list[dict], role: str) -> list[dict]:
    """Real hihat cells for a section's ROLE -- wired for every preset,
    not gated to one genre. An unmapped role defaults to `"closed"`
    (real, universal time-keeping) rather than raising; `chill`/
    `interlude` stay silent."""
    if not guitar_cells:
        raise ValueError("guitar_cells must be non-empty")
    style = _ROLE_TO_HIHAT_STYLE.get(role, "closed")
    if style is None:
        return [{"duration": c["duration"], "is_rest": True, "role": None} for c in guitar_cells]
    return generate_hihat_pattern(guitar_cells, style)


# --- X.13: hihat accents + section-transition crashes -----------------------
#
# Real finding from analyzing an isolated drum stem of a real user-supplied
# reference track (demucs-separated, classify_drum_onsets): cymbals/hihat
# were 84% of ALL detected drum onsets (1079 of 1282) -- by far the most
# constantly-present, audible element of a real mix, and the flat, single-
# velocity "closed" pulse X.11 shipped had zero variation at all. Real
# drumming varies that same hand: occasional OPEN accents on structurally
# important beats, and a real crash at a section's own opening when the
# arrangement actually changes -- ported from the same real technique
# Metalerator's cymbal generator uses (`drums/breakdown/default_melodic.py`,
# `should_add_opening_cymbals`: a crash fires when the kick/snare pattern
# differs from the previous section's), generalized here to "the section's
# own ROLE changed" since that's this project's real unit of arrangement
# change (`song.py`'s section-role loop), not a raw kick/snare diff.


def apply_hihat_accents(hihat_cells: list[dict], accent_indices: set[int]) -> list[dict]:
    """Real open-hat accent overlay: at each index in `accent_indices` that
    IS an existing hihat hit, swap its role from `HIHAT_CLOSED` to
    `HIHAT_OPEN` -- never fabricates a NEW hit at a rest position, only
    accentuates a hit that's already there. `accent_indices` is meant to
    come from the same real structural-accent positions `atmosphere.
    find_accents` already computes for octave stabs (`{a["cell_index"]
    for a in accents}`), so hihat accents land on the same real
    structurally-important beats the rest of the arrangement already
    treats as accented, not an independently-invented set of positions.
    """
    out = []
    for i, cell in enumerate(hihat_cells):
        if i in accent_indices and not cell["is_rest"] and cell["role"] == "HIHAT_CLOSED":
            out.append({**cell, "role": "HIHAT_OPEN"})
        else:
            out.append(cell)
    return out


def add_transition_crash(hihat_cells: list[dict], fire: bool) -> list[dict]:
    """When `fire` is true, override the FIRST cell in `hihat_cells` to a
    real `CRASH_1` hit -- regardless of whether that cell already held a
    hit or a rest, since a section-opening crash accent is a genuine,
    real arrangement event that should always land there when the caller
    determines the section's role actually changed (see this section's
    module-level docstring). `fire=False` returns `hihat_cells`
    unchanged -- never a fabricated crash on an unchanged section."""
    if not hihat_cells or not fire:
        return hihat_cells
    first = {**hihat_cells[0], "is_rest": False, "role": "CRASH_1"}
    return [first] + hihat_cells[1:]


# --- P4.3: fills/blasts via shared-sequence + blast-type rendering ----------


def _render_traditional(cells: list[dict]) -> list[dict]:
    """Traditional blast: hits alternate KICK/SNARE straight through the
    whole span, one global toggle that only advances on hit slots (rests
    never flip it) -- "roughly every subdivision" alternates, regardless of
    where beat boundaries fall."""
    out: list[dict] = []
    next_role = "KICK"
    for cell in cells:
        if cell["is_rest"]:
            out.append({**cell, "roles": []})
            continue
        out.append({**cell, "roles": [next_role]})
        next_role = "SNARE" if next_role == "KICK" else "KICK"
    return out


def _render_gravity(cells: list[dict]) -> list[dict]:
    """Gravity blast: alternation resets at the start of EVERY beat instead
    of running continuously across the whole span -- this is what "alternating
    hits within a single beat" means mechanically: each new beat starts back
    on KICK, so the KICK/SNARE pattern re-aligns to the beat grid every time
    instead of drifting the way the traditional rendering does."""
    out: list[dict] = []
    cumulative = 0.0
    current_beat = -1
    next_role = "KICK"
    for cell in cells:
        beat = int(cumulative + _EPS)
        if beat != current_beat:
            current_beat = beat
            next_role = "KICK"
        if cell["is_rest"]:
            out.append({**cell, "roles": []})
        else:
            out.append({**cell, "roles": [next_role]})
            next_role = "SNARE" if next_role == "KICK" else "KICK"
        cumulative += cell["duration"]
    return out


def _render_hammer(cells: list[dict]) -> list[dict]:
    """Hammer blast: kick and snare struck together in unison on every hit
    slot (a doubled "hammering" texture) instead of alternating -- a
    defensible, documented third genre-standard blast variant distinct from
    both traditional and gravity."""
    out: list[dict] = []
    for cell in cells:
        if cell["is_rest"]:
            out.append({**cell, "roles": []})
        else:
            out.append({**cell, "roles": ["KICK", "SNARE"]})
    return out


_BLAST_RENDERERS = {
    "traditional": _render_traditional,
    "gravity": _render_gravity,
    "hammer": _render_hammer,
}


def generate_blast_fill(
    rhythm_id: str,
    registry: RhythmRegistry,
    total_beats: float,
    allowed_lengths: list[float],
    hit_chance: float,
    blast_weights: dict[str, float],
    rng: random.Random,
) -> dict:
    """Generate a drum fill/blast-beat span.

    Shared-sequence: the underlying skeleton (duration/is_rest per slot)
    comes from `registry.get_or_create(rhythm_id, ...)` -- `rhythm.
    RhythmRegistry`'s existing cache, not a new one (one class per job: this
    module does not reinvent that cache). If `rhythm_id` was already used
    -- by this call or by another instrument entirely -- the EXACT same
    cell list (same durations, same offsets) comes back instead of a fresh
    draw, so a fill's timing can be locked to something already generated.

    Blast-type selection goes through `rhythm.pick_blast_type(blast_weights,
    rng)` -- same weighted-choice mechanism already validated for rhythm
    (a zero-weight type can never be picked).

    Returns `{"blast_type": str, "cells": list[{"duration", "is_rest",
    "roles"}]}`. `cells` has exactly one entry per skeleton slot, in the
    same order and with the same durations as the skeleton -- `roles` is
    `[]` on a rest slot and one-or-more role names on a hit slot, per the
    blast type's rendering (see `_render_traditional`/`_render_gravity`/
    `_render_hammer`).
    """
    skeleton = registry.get_or_create(
        rhythm_id, total_beats, allowed_lengths, hit_chance, rng
    )
    blast_type = pick_blast_type(blast_weights, rng)
    renderer = _BLAST_RENDERERS.get(blast_type)
    if renderer is None:
        raise ValueError(
            f"unsupported blast type {blast_type!r} "
            f"(no renderer wired for it in drums._BLAST_RENDERERS)"
        )
    return {"blast_type": blast_type, "cells": renderer(skeleton)}


# --- P4.4: reference-MIDI density vocabulary informs fill hit_chance --------


def generate_vocabulary_informed_blast_fill(
    rhythm_id: str,
    registry: RhythmRegistry,
    total_beats: float,
    allowed_lengths: list[float],
    bpm: float,
    blast_weights: dict[str, float],
    rng: random.Random,
    vocab: dict | None = None,
) -> dict:
    """`generate_blast_fill`, but `hit_chance` comes from the real
    reference-MIDI corpus's density vocabulary for `bpm` (P4.4,
    god-tier-metal-scope.md sec. 18.6) instead of being chosen by the
    caller.

    This is the real, wired call path for `midi_vocab.
    vocabulary_informed_hit_chance` -- it is not a standalone function
    nothing uses (anti-patterns.md: "a validator that is not called is not
    done"). The corpus (1967 real GM drum-groove/fill MIDI files) is mined
    once into `engine/data/midi_vocab.json` -- see `midi_vocab.
    build_vocabulary` -- and never re-parsed here; this function only reads
    that cache (or an explicitly-passed `vocab` dict, mainly for tests).

    The grid itself is still `rhythm.RhythmRegistry`/`generate_blast_fill`
    -- CLAUDE.md's law that the grid is the writer and audio/reference data
    is only paint on top holds here too: the corpus never contributes an
    actual note or cell, only a `hit_chance` density parameter.
    """
    hit_chance = vocabulary_informed_hit_chance(bpm, vocab=vocab)
    return generate_blast_fill(
        rhythm_id,
        registry,
        total_beats,
        allowed_lengths,
        hit_chance,
        blast_weights,
        rng,
    )
