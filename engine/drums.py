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
