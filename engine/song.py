"""Song assembly: the missing glue between the preset system (Phase 1) and
every generation phase (2-7).

Gap this closes: every phase built and tested its own mechanism in
isolation (rhythm cells, motifs, drums, bass, structure, atmosphere), but
nothing actually took a real `Preset` (from `presets.load_all_presets`) and
threaded its fields through a full generation run. `compose_song` below is
that real, wired call path -- it is the first place `preset.bpm`,
`preset.bars`, `preset.open_chance`, `preset.dissonance`, `preset.vocab`,
and `preset.tuning_key` are all actually consumed together, not just
validated and stored.

Per CLAUDE.md's law, Grid is the writer: every note here comes from the
existing generation modules (rhythm/motif/drums/bass/structure/atmosphere);
this module only wires them together in the right order and shape, adding
no new note-choice logic of its own.

Honest scope note (documented, not silently dropped): `preset.group`,
`preset.pedal`, `preset.kick` (the kick-STYLE name, e.g. "euclid"/"lock"),
and `preset.octave_stab` are still not consumed anywhere in the engine --
`kick_follows_guitar` is a single fixed algorithm, and nothing yet
branches on a preset's kick-style name or djent's displacement-group
value. That remains a real, tracked gap (see TASKS.md) beyond what this
module closes.
"""
from __future__ import annotations

import random

from atmosphere import find_accents, pad_voicing
from bass import build_bass_fretboard, follow_guitar_rhythm
from drums import RhythmRegistry, generate_vocabulary_informed_blast_fill, kick_follows_guitar
from fretboard import Fretboard
from lead import generate_lead_line
from motif import Motif, ThemeRegistry, invert, render_motif
from performance import double_track
from presets import Preset, get_tuning, load_all_presets, load_tunings, resolve_preset_id
from riff import harmonize_line
from structure import generate_section_sequence, judge
from theory import Scale, arc

__all__ = ["compose_song", "pitches_per_cell"]

# A section is `preset.bars` bars of 4/4; slots are sixteenth/eighth/quarter
# notes -- a reasonable default vocabulary for chug-driven metal rhythm.
_ALLOWED_LENGTHS = [0.25, 0.5, 1.0]
_BEATS_PER_BAR = 4
# Below this preset dissonance, generation stays in-scale (chromatic=False);
# at or above it, motif.generate_motif reshapes the interval vocabulary via
# shade() toward the dissonant set. A simple, documented threshold -- not a
# claim that 0.5 is musically special, just a single consistent cutoff.
_CHROMATIC_DISSONANCE_THRESHOLD = 0.5


def pitches_per_cell(motif: Motif, scale: Scale, start_degree: int = 0) -> list[int | None]:
    """Expand `render_motif`'s per-HIT pitch list (one entry per non-rest
    cell) into a per-CELL list aligned with `motif.cell` (one entry per
    cell, `None` on rests) -- the shape `bass.follow_guitar_rhythm` and
    `drums`/judge zipping need, since `render_motif` itself only returns
    hit pitches with no positional/rest information."""
    hit_pitches = iter(render_motif(motif, scale, start_degree=start_degree))
    out: list[int | None] = []
    for cell in motif.cell:
        out.append(None if cell["is_rest"] else next(hit_pitches))
    return out


def _snap_to_playable_octave(fretboard: Fretboard, pitch: int) -> int:
    """Shift `pitch` by whole octaves (up or down, whichever is closer)
    until it lands on a real, reachable `(string, fret)` on `fretboard`.

    Needed because `motif.invert()` negates a theme's deltas -- a theme
    anchored near the low end of the register can invert to a pitch below
    even the lowest open string. Same discipline `bass._nearest_playable_
    octave` already applies to the bass voice, applied here to the guitar
    voice: never let a develop op silently produce an unplayable note,
    always land on the nearest octave that IS real.
    """
    for shift in (0, -12, 12, -24, 24, -36, 36):
        candidate = pitch + shift
        try:
            fretboard.pitch_to_fret(candidate, max_fret=fretboard.max_fret)
        except ValueError:
            continue
        return candidate
    raise ValueError(f"pitch {pitch} has no reachable octave on this fretboard")


def _two_child_seeds(rng: random.Random) -> tuple[int, int]:
    """Draw two distinct integer seeds from `rng` for `double_track`'s two
    independent takes -- deterministic given the parent `rng`'s state, so
    the whole song stays reproducible for a fixed top-level seed, while the
    two takes' humanization never shares an RNG stream (see
    performance.py's module docstring on why that must never happen)."""
    return rng.randrange(2**31), rng.randrange(2**31)


def _generate_attempt(rng: random.Random, preset: Preset, num_sections: int) -> dict:
    """One full attempt at composing a song from `preset`. Called
    repeatedly (with fresh seeds) by `judge_and_retry` in `compose_song`
    below until the result judges `ok`, or attempts run out."""
    tunings = load_tunings()
    tuning = get_tuning(preset.tuning_key, tunings)
    guitar_fb = Fretboard(tuning.open)
    bass_fb = build_bass_fretboard(tuning.open)
    scale = Scale(root=tuning.open[0], name=preset.scale)

    sequence = generate_section_sequence(rng, num_sections)
    total_beats = float(preset.bars * _BEATS_PER_BAR)
    chromatic = preset.dissonance >= _CHROMATIC_DISSONANCE_THRESHOLD

    # Cross-section thematic reuse (P3.4's ThemeRegistry, wired here for the
    # first time): per the scope doc, developing one theme across sections
    # is "the single highest-leverage change for making songs sound
    # composed rather than generated" -- so every section does NOT get an
    # independently-rolled motif. Sections sharing a ROLE share a base
    # theme (first occurrence creates it; later occurrences reuse the same
    # rhythm+contour), rendered at THAT section's own arc()-driven
    # start_degree/register (Motif deltas are relative, so the same theme
    # naturally lands differently per section -- real modulation, not a
    # copy). Every second reuse of a role is additionally `invert`-ed, a
    # cheap, real develop op, so a repeat is a variation, not identical.
    themes = ThemeRegistry()
    role_occurrences: dict[str, int] = {}

    registry = RhythmRegistry()
    sections: list[dict] = []
    guitar_track: list[dict] = []
    drum_track: list[dict] = []

    for idx, role in enumerate(sequence):
        arc_row = arc(role=role)
        occurrence = role_occurrences.get(role, 0)
        role_occurrences[role] = occurrence + 1

        base_theme = themes.get_or_create(
            f"theme-{role}", total_beats, _ALLOWED_LENGTHS, preset.open_chance,
            rng, scale, preset.vocab.weights, chromatic=chromatic,
            dissonance=arc_row["dissonance"],
            base_degree=arc_row["start_degree"],
        )
        m: Motif = invert(base_theme) if occurrence % 2 == 1 else base_theme
        guitar_cells = m.cell
        cell_pitches = [
            (None if p is None else _snap_to_playable_octave(guitar_fb, p))
            for p in pitches_per_cell(m, scale, start_degree=arc_row["start_degree"])
        ]

        seed_a, seed_b = _two_child_seeds(rng)
        take_a, take_b = double_track(
            guitar_cells, random.Random(seed_a), random.Random(seed_b)
        )

        kick_cells = kick_follows_guitar(guitar_cells)

        fill = None
        if role in ("breakdown", "solo"):
            fill = generate_vocabulary_informed_blast_fill(
                rhythm_id=f"section-{idx}-{role}",
                registry=registry,
                total_beats=total_beats,
                allowed_lengths=_ALLOWED_LENGTHS,
                bpm=preset.bpm,
                blast_weights={"traditional": 1.0, "gravity": 1.0, "hammer": 1.0},
                rng=rng,
            )

        bass_cells = follow_guitar_rhythm(guitar_cells, cell_pitches, bass_fb)

        pad_root = scale.root + arc_row["register"]
        pad = pad_voicing(pad_root)
        accents = find_accents(guitar_cells, pad_root)

        # The lead guitar is NOT the same busy melodic voice in every
        # section all song long -- a real second guitar changes role by
        # section, same as it would in an actual arrangement:
        lead_anchor = pad_root
        lead_mode: str
        if role == "solo":
            # A genuine featured lead: denser (roughly 8th-note-rate across
            # the section rather than one note per rhythm hit), more active
            # (`motion` raised -> more stepwise walking, per VoiceLeader's
            # own "active styles walk" design), more wide leaps
            # (`stab_chance` raised -- scope sec.4's "occasional wide
            # sweep-style interval leaps for technicality"), and a register
            # pushed up an extra octave (solos sit above the rhythm pedal).
            lead_mode = "solo"
            lead_notes = generate_lead_line(
                scale, preset.vocab.weights, min(1.0, preset.vocab.motion + 0.3), rng,
                low=lead_anchor - 12, high=lead_anchor + 24, anchor=lead_anchor + 12,
                num_notes=max(1, round(total_beats * 2)),
                stab_chance=0.35,
            )
        elif role in ("chill", "interlude"):
            # A melodic/atmospheric section: the second guitar harmonizes
            # the rhythm's own theme at a fixed interval (riff.
            # harmonize_line, P3.12) rather than playing an independent
            # phrase -- rhythmically locked to the SAME motif, so it reads
            # as one arranged part, not two guitars doing unrelated things.
            lead_mode = "harmony"
            _lead_line, lead_notes = harmonize_line(m, scale, start_degree=arc_row["start_degree"])
        else:
            # Dense chug sections (intro/build/breakdown/outro): a busy
            # independent lead would just clash with the rhythm here --
            # real arrangements leave the second guitar out (or doubling
            # the riff, already covered by the double-tracked pair) rather
            # than noodling a melody over a breakdown. Silent, not a
            # fabricated part filling space it doesn't belong in.
            lead_mode = "silent"
            lead_notes = []

        sections.append({
            "role": role,
            "arc": arc_row,
            "motif": m,
            "pitches_per_cell": cell_pitches,
            "guitar_take_a": take_a,
            "guitar_take_b": take_b,
            "lead_mode": lead_mode,
            "lead": lead_notes,
            "kick": kick_cells,
            "fill": fill,
            "bass": bass_cells,
            "pad": pad,
            "accents": accents,
        })

        guitar_track.extend(take_a)
        drum_track.extend(kick_cells)

    comp = {"guitar": guitar_track, "drums": drum_track}
    return {
        "preset_id": preset.id,
        "tuning_key": preset.tuning_key,
        "sequence": sequence,
        "sections": sections,
        "guitar_fretboard": guitar_fb,
        "bass_fretboard": bass_fb,
        "judge": judge(comp),
        "_comp": comp,
    }


def compose_song(
    preset_id: str,
    seed: int,
    num_sections: int = 6,
    max_seeds: int = 6,
) -> dict:
    """Compose a full song from a real preset id (e.g. "djent", or a stale
    band-linked alias like "periphery" -- both resolve via
    `presets.resolve_preset_id`), start to finish through every phase:

      preset -> tuning/Fretboard/Scale -> section sequence (Phase 6) ->
      per-section motif + arc-driven modulation (Phase 3/6) ->
      double-tracked rhythm guitar (Phase 3) -> lead guitar via VoiceLeader
      (Phase 3) -> kick + vocabulary-informed fills (Phase 4) -> bass
      locked to the guitar's own rhythm (Phase 5) -> atmosphere pad +
      accent stabs (Phase 7) -> judge/retry (Phase 6).

    Every section gets a full four-piece band (two rhythm-guitar takes,
    lead, bass) plus drums and atmosphere -- a real band lineup, not just a
    single guitar line. Which parts a final mix actually brings up or mutes
    per section is a Phase 8/9 (Reaper/Editor) concern, not this engine's.

    Retries up to `max_seeds` times if the generated result doesn't judge
    `ok` -- the same real, ported `judge()` thresholds used everywhere else
    in this project, not a separate quality bar invented for this entry
    point. Retries are seeded `seed, seed+1, seed+2, ...` -- NOT
    `structure.judge_and_retry`'s own `range(max_seeds)` (which always
    tries 0, 1, 2... regardless of what seed a caller wants), since that
    would make `seed` dead: every call for a given preset would silently
    collapse onto whichever of seeds 0..max_seeds-1 happens to judge `ok`
    first, no matter what `seed` was passed in. A local loop over
    `structure.judge` keeps `seed` load-bearing, which is what makes
    calling this twice with two different seeds actually produce two
    different songs (see tests/test_song.py's reproducibility test, which
    checks the same seed twice, not that all seeds converge).

    Raises `KeyError` if `preset_id` doesn't resolve to a real preset --
    never silently falls back to a default preset (that would fabricate a
    song from the wrong style).
    """
    presets = load_all_presets()
    resolved = resolve_preset_id(preset_id)
    if resolved not in presets:
        raise KeyError(f"unknown preset id or alias: {preset_id!r}")
    preset = presets[resolved]

    result = None
    for attempt in range(max_seeds):
        rng = random.Random(seed + attempt)
        result = _generate_attempt(rng, preset, num_sections)
        if result["judge"]["ok"]:
            break
    return result
