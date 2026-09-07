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
from motif import Motif, render_motif
from performance import double_track
from presets import Preset, get_tuning, load_all_presets, load_tunings, resolve_preset_id
from structure import (
    generate_section_sequence,
    generate_song_sections,
    judge,
    judge_and_retry,
)
from theory import Scale

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

    section_results = generate_song_sections(
        sequence, scale, rng, total_beats, _ALLOWED_LENGTHS,
        preset.open_chance, preset.vocab.weights, chromatic=chromatic,
    )

    registry = RhythmRegistry()
    sections: list[dict] = []
    guitar_track: list[dict] = []
    drum_track: list[dict] = []

    for idx, (role, result) in enumerate(zip(sequence, section_results)):
        m: Motif = result["motif"]
        arc_row = result["arc"]
        guitar_cells = m.cell
        cell_pitches = pitches_per_cell(m, scale, start_degree=arc_row["start_degree"])

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

        lead_anchor = pad_root
        lead_notes = generate_lead_line(
            scale, preset.vocab.weights, preset.vocab.motion, rng,
            low=lead_anchor - 12, high=lead_anchor + 12, anchor=lead_anchor,
            num_notes=max(1, m.hit_count),
        )

        sections.append({
            "role": role,
            "arc": arc_row,
            "motif": m,
            "pitches_per_cell": cell_pitches,
            "guitar_take_a": take_a,
            "guitar_take_b": take_b,
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

    Retries with fresh seeds (via `structure.judge_and_retry`) up to
    `max_seeds` times if the generated result doesn't judge `ok` -- the
    same real, ported `judge()` thresholds used everywhere else in this
    project, not a separate quality bar invented for this entry point.

    Raises `KeyError` if `preset_id` doesn't resolve to a real preset --
    never silently falls back to a default preset (that would fabricate a
    song from the wrong style).
    """
    presets = load_all_presets()
    resolved = resolve_preset_id(preset_id)
    if resolved not in presets:
        raise KeyError(f"unknown preset id or alias: {preset_id!r}")
    preset = presets[resolved]

    return judge_and_retry(
        lambda rng: _generate_attempt(rng, preset, num_sections),
        max_seeds=max_seeds,
    )
