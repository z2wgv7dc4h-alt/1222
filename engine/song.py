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

`preset.kick` (the kick-style name, e.g. "euclid"/"lock"), `preset.group`
(djent-style N-against-4 displacement), `preset.pedal` (pedal-note return
frequency) and `preset.octave_stab` are now wired through here too:
  - `preset.kick` selects the real kick mechanism via `drums.
    kick_pattern_for_style` (see that function for the per-style
    mechanisms) instead of always running the fixed `kick_follows_guitar`
    algorithm regardless of what a preset declares.
  - `preset.group`, when set, is threaded into `motif.generate_motif` as
    `group_beats` -- a `group`-beat cell is generated and tiled via
    `rhythm.tile_cell` across the section instead of one cell spanning the
    whole section directly, producing the N-against-4 phase-drift effect.
  - `preset.pedal`, when set, is threaded into `motif.generate_motif` as
    `pedal`, biasing delta selection toward the root/anchor degree (see
    `motif.apply_pedal_bias`).
  - `preset.octave_stab`, when true, adds a real `theory.VoiceLeader.stab()`
    leap at each of a section's `atmosphere.find_accents` positions
    (`section["octave_stabs"]`); when false, that list stays empty -- a
    section's use of the octave-stab device is now conditional on the
    preset actually declaring it, not applied (or not) unconditionally.
  - X.6b: `chill`/`interlude` sections (the `lead_mode == "harmony"`
    branch) now also get a real extended chord voicing via
    `chord_vocab.quality_for_dissonance`/`voice_named_chord`
    (`section["chord_quality"]`/`section["chord_voicing"]`) -- the named
    jazz-influenced chord vocabulary (`maj7`/`min7`/`add9`/`sus2`/etc.)
    god-tier-metal-scope.md calls for on ambient/clean sections, alongside
    (not instead of) the existing `riff.harmonize_line` melodic doubling.
    Every other role leaves both fields `None`.
  - X.9: every section now also gets a real snare backbeat
    (`section["snare"]`) via `drums.snare_pattern_for_role` -- wired for
    every preset, not gated to one genre (breakdown-style backbeats are a
    shared genre convention; a preset's own `.kick`/`.group`/rhythmic
    density are what actually differentiate one genre's breakdown from
    another's). `chill`/`interlude` sections get no backbeat (silent),
    matching the same judgment call this file's `lead_mode` logic already
    makes for those two atmospheric roles.
  - X.11: `build`/`solo` sections now get a real, varied kick overlay
    (`double_kick` or `blast`, picked per section via the real seeded
    `rng`) via `drums.resolve_kick_style`/`kick_pattern_for_style`
    (X.24 split `drums.kick_pattern_for_role`'s real style-resolution
    logic out into `resolve_kick_style` so the chosen style could be
    stored and reused for the post-blend kick re-lock -- same real
    behavior, still delegates to `kick_pattern_for_style` for the cells),
    regardless of what the preset otherwise declares -- direct answer to
    real listening
    feedback that generated drums felt too generic/repetitive in
    high-energy sections. Every section also gets a real steady hihat
    (`section["hihat"]`) via `drums.hihat_pattern_for_role` -- this
    engine previously had zero cymbal content at all. `chill`/
    `interlude` stay silent, same rule as the snare/kick tables.
  - X.13: the hihat layer now gets real variation -- open-hat accents at
    the same structural-accent positions octave stabs already use
    (`drums.apply_hihat_accents`), and a real crash cymbal
    (`drums.add_transition_crash`) at a section's opening whenever its
    role actually changes from the previous section's (ported technique
    from Metalerator's real "crash on pattern change" cymbal generator,
    generalized to this project's own role-based arrangement unit).
    Direct response to a real finding: analyzing an isolated drum stem
    of a real reference track showed cymbals/hihat are 84% of all real
    drum onsets -- the most constantly-present element in a real mix --
    while this project's hihat had zero variation until now.
"""
from __future__ import annotations

import random

from atmosphere import find_accents, pad_voicing, synth_double
from bass import build_bass_fretboard, follow_guitar_rhythm
from chord_vocab import quality_for_dissonance, voice_named_chord
from drums import (
    add_transition_crash,
    apply_hihat_accents,
    blast_kick_cells,
    blast_snare_cells,
    hihat_pattern_for_role,
    kick_pattern_for_style,
    render_blast_beat,
    render_blast_beat_for_type,
    resolve_kick_style,
    snare_pattern_for_role,
)
from fretboard import Fretboard
from lead import generate_lead_line, generate_sequence_line
from legato import generate_legato_lick
from metric_modulation import apply_metric_modulation, modulation_ratio
from motif import (
    Motif,
    ThemeRegistry,
    degree_delta_for_interval,
    generate_motif,
    generate_pitch_deltas,
    invert,
    pick_pitch_interval,
    render_motif,
    transpose,
)
from rhythm import duration_bias_for_feel, generate_rhythm
from performance import double_track, humanize_take
from presets import Preset, get_tuning, load_all_presets, load_tunings, resolve_preset_id
from progression import CHORUS_PROGRESSIONS, VERSE_PROGRESSIONS, pitches_per_cell_with_progression
from riff import harmonize_line
from structure import generate_section_sequence, judge, tempo_at
from theory import Scale, VoiceLeader, arc

__all__ = ["compose_song", "compose_song_from_preset", "regenerate_section", "pitches_per_cell"]

# A section is `preset.bars` bars of 4/4; slots are sixteenth/eighth/quarter
# notes -- a reasonable default vocabulary for chug-driven metal rhythm.
_ALLOWED_LENGTHS = [0.25, 0.5, 1.0]
_BEATS_PER_BAR = 4
# X.14 -- real diatonic-third "repeat and lift" interval for theme
# development (see _develop_theme). Degrees, not semitones (Motif deltas
# are scale-degree offsets, so this stays scale-legal automatically
# regardless of which scale is active).
_THEME_DEVELOP_TRANSPOSE_DEGREES = 2
# Below this preset dissonance, generation stays in-scale (chromatic=False);
# at or above it, motif.generate_motif reshapes the interval vocabulary via
# shade() toward the dissonant set. A simple, documented threshold -- not a
# claim that 0.5 is musically special, just a single consistent cutoff.
_CHROMATIC_DISSONANCE_THRESHOLD = 0.5

# X.20 -- real rest-vs-hit density, ported from the real reference
# implementation (reference/ww-forge-prior-attempt/engine/riff_engine.py,
# ~line 646-652: `base_density = float(knobs.get("density", 0.72))`, then
# `density = max(0.12, min(0.98, base_density * (0.55 + 0.9 *
# arcv["energy"])))`). Fixes a real, previously-uncaught bug: this project
# had been passing `preset.open_chance` as `hit_chance` -- but the real
# source's `open_chance` is a completely different axis (`wants_open =
# rng.random() < open_chance`, an OPEN-ringing-vs-muted PITCH/articulation
# choice per hit, not a rest-vs-hit density knob at all). Verified via real
# generated output before this fix: tech.json ("extreme technical...
# kick-locked triplet chug") had a REAL 5.56% hit rate -- 94% rests --
# because its correctly-low open_chance (0.10, "rarely open/ringing, mostly
# muted") was being misapplied as "almost never even a hit." The real
# source never gave presets their own density number either (grepped
# style_packs.py -- no per-pack "density" key exists); per-preset character
# comes through feel/group/pedal/vocab instead, consistent with this
# project's own existing architecture, so `_BASE_HIT_CHANCE` is a single
# shared baseline, real per-ROLE variation comes from `theory.arc()`'s
# already-computed `"energy"` field (previously computed for every section,
# never consumed -- same "capability exists, never used" pattern as
# IRVD/X.19). `preset.open_chance` itself is untouched (still a real,
# validated preset field) but no longer wired here -- its real purpose
# (open-string articulation) is a genuine, separate, deliberately deferred
# gap; this project's pitch model has no muted-vs-open axis to wire it into
# yet.
_BASE_HIT_CHANCE = 0.72

# X.30 -- which real progression table (if any) a role draws from. Only
# verse/chorus get real per-bar tonal-center movement (see progression.py's
# module docstring); every other role keeps one fixed anchor for the whole
# section, unchanged.
_PROGRESSION_TABLES = {"verse": VERSE_PROGRESSIONS, "chorus": CHORUS_PROGRESSIONS}

# X.31 -- real verse pedal-bias override. Matches Metalerator's own real
# verse riff frequency (~65% root note, occasional colored note) -- see
# song._generate_attempt's `theme-{role}` call site for where this is used.
_VERSE_PEDAL_BIAS = 0.65

# X.32 -- real per-role feel override, closing the architectural gap this
# session's audit surfaced: `feel` was one value per whole PRESET, so a
# metalcore song's intro/verse/build/chorus/outro all got the exact same
# duration-weighting as the actual breakdown section -- zero rhythmic
# contrast between "riffing toward the breakdown" and "the breakdown
# itself" within one song. `breakdown` ALWAYS gets real breakdown duration
# weighting (dense chug) regardless of what the preset otherwise declares --
# the one section a "breakdown" role must always chug like a breakdown.
# `build` gets a real chance at the classic gallop/stutter-chug riffing
# devices (scope sec.4), picked per-section via the section's own seeded
# rng alongside the preset's own declared feel as a real, always-available
# choice (so build doesn't ALWAYS gallop -- genuine variety, same real
# precedent as X.11's build/solo kick-style overlay).
_ROLE_FEEL_FORCED = {"breakdown": "breakdown"}
_ROLE_FEEL_OVERRIDE_CHOICES = {"build": ("gallop", "stutter_chug")}


def _resolve_hit_chance(base: float, energy: float) -> float:
    """The real rest-vs-hit probability for one section: `base` (this
    project's `_BASE_HIT_CHANCE`) scaled by real ARC energy, clamped to
    `[0.12, 0.98]` -- the exact real formula from `riff_engine.py` (see
    module-level comment above `_BASE_HIT_CHANCE`), not invented. `energy`
    ranges `[0.0, 1.0]` in `theory.ARC`'s real table (K=0.20 lowest,
    C/breakdown=1.00 highest -- "breakdown hits hardest" is real, derived
    data, not an assumption)."""
    return max(0.12, min(0.98, base * (0.55 + 0.9 * energy)))

# X.6c/X.12 -- real metric modulation, wired into a real per-section
# trigger. Originally wired as a single one-shot switch at the first
# "build" -> "breakdown" transition, held for the rest of the song -- real
# listening feedback on a longer generated song ("drums are too slow...
# not really metal") confirmed this was a real bug, not a stylistic
# choice: for a song whose sequence revisits "breakdown" many times (real
# for any longer song), the tempo dropped once and NEVER RECOVERED,
# spending the rest of the song at half-time. Fixed to the real, genre-
# correct behavior instead: the half-time modulation applies
# INDEPENDENTLY to every "breakdown"-role section (the classic djent/
# deathcore half-time-under-the-breakdown treatment, real and temporary,
# same as an actual arrangement), and every other role stays at the
# preset's own full `base_bpm` -- a build, solo, or interlude immediately
# after a breakdown is back at full tempo, not still halved.
_METRIC_MOD_OLD_SUBDIVISION = (1, 2)  # straight eighth
_METRIC_MOD_NEW_SUBDIVISION = (1, 1)  # new quarter -> ratio 0.5, a half-time feel

# X.18 -- real MID-section tempo drops (scope sec.14.2 item 4: "a riff
# that's blasting, then half-times for 2 bars as a slam moment"), distinct
# from X.6c/X.12's BETWEEN-section modulation above. Same real device, same
# real ratio (reuses `modulation_ratio`/`apply_metric_modulation`, not a
# second modulation mechanism), just triggered partway through one section
# instead of at a section boundary. Eligible roles are the two genre homes
# for this move: "build" (blasting energy that suddenly drops, foreshadowing
# a breakdown) and "breakdown" itself (a breakdown that further drops into
# its own slam moment). Needs `preset.bars >= _TEMPO_DROP_MIN_BARS` so at
# least `_TEMPO_DROP_MIN_BARS - _TEMPO_DROP_TAIL_BARS` full-tempo bars play
# before the drop -- a 1-bar section has no room for a real "blasting, THEN"
# contrast. Not every eligible section gets one (`_TEMPO_DROP_CHANCE`,
# rolled per-section on that section's own seeded rng) -- every single
# breakdown/build dropping would read as mechanical, not a real device.
_TEMPO_DROP_ROLES = ("build", "breakdown")
_TEMPO_DROP_MIN_BARS = 4
_TEMPO_DROP_TAIL_BARS = 2
_TEMPO_DROP_CHANCE = 0.5

# X.33 -- real, direct measurement across every preset (10 seeds each, 80
# real generated songs) found EVERY breakdown section unconditionally
# halving tempo (the old _compute_tempo_map behavior below) sent 41.8% of
# every song's real elapsed wall-clock time into half-tempo alone --
# breakdown is already the single most common role, so "always half-time"
# meant the default state of the most frequent section type, not a
# dramatic occasional device. Same real precedent as `_TEMPO_DROP_CHANCE`
# just above: rolled per-section on that section's own seeded rng.
_BREAKDOWN_HALFTIME_CHANCE = 0.4

# X.34 -- real, occasional blast beats. Direct response to a real, checked
# gap: `drums.generate_vocabulary_informed_blast_fill` (P4.3/P4.4, real,
# tested, three genuine alternating-KICK/SNARE blast-beat renderers) was
# called here for every breakdown/solo section and its real output was
# simply discarded -- `midi_export.py`'s own docstring admitted this
# outright ("section['fill'] is intentionally NOT exported... _generate_
# attempt never actually blends it into the song's assembled drum data").
# Wired here instead via `drums.render_blast_beat` (rendered directly onto
# this section's own guitar_cells, guaranteed cell-aligned with kick/snare
# -- see that function's own docstring for why the OLD independent-skeleton
# approach couldn't be used as-is). Occasional, not universal (same real
# precedent as `_BREAKDOWN_HALFTIME_CHANCE` just above) -- not every
# breakdown/solo should erupt into a blast, same reasoning X.33 already
# established for half-time.
_BLAST_FILL_ROLES = ("breakdown", "solo")
_BLAST_FILL_CHANCE = 0.35
_BLAST_WEIGHTS = {"traditional": 1.0, "gravity": 1.0, "hammer": 1.0}

# X.36 -- real melodic sequence passage length for solo sections. See
# lead.generate_sequence_line's own module docstring for the full real
# reference-MIDI/research citation.
_SOLO_SEQUENCE_MOTIF_LEN = 4
_SOLO_SEQUENCE_REPEATS = 4

# Real "synth doubles the riff an octave up" device (scope sec.16.1's own
# Born-of-Osiris research finding) -- see the dense-chug `else` branch of
# `_generate_one_section` for the full real citation.
_SYNTH_DOUBLE_TRANSPOSE = 12

# Real, second, genuinely-different rhythm-guitar part -- a near-
# monophonic low pedal/chug doubler, distinct from the wide, melodic
# guitar_take_a/take_b pair (which are the SAME riff double-tracked for
# stereo width, per scope sec.17.1). Found via direct measurement of a
# real user-supplied Born-of-Osiris-style reference MIDI (2026-09-10):
# its own "Guitar 2" track was 95.9% root-note, in a tight 1-octave-low
# register, a genuinely separate musical idea from "Guitar 1"'s wider,
# more melodic riff -- not another humanized copy of it. Weights below
# are the real measured interval percentages from that track (root/P4/
# M3/m6/P5), converted to engine weight units; see `_pedal_double_
# pitches`'s own docstring for the full real citation.
_PEDAL_DOUBLE_WEIGHTS = {0: 96.0, 5: 2.0, 4: 1.0, 8: 0.5, 7: 0.5}


def _resolve_tempo_drop(section_bpm: float, trigger_beat: float | None) -> dict | None:
    """The real, final `section["tempo_drop"]` value: `None` if this
    section was never eligible/triggered (`trigger_beat is None`), else
    `{"trigger_beat": ..., "bpm": ...}` where `bpm` is `section_bpm` scaled
    by the SAME real half-time ratio X.6c's between-section modulation
    uses (`modulation_ratio(_METRIC_MOD_OLD_SUBDIVISION,
    _METRIC_MOD_NEW_SUBDIVISION)` == 0.5) via the same real, already-tested
    `apply_metric_modulation` -- no separate modulation math invented for
    the mid-section case."""
    if trigger_beat is None:
        return None
    ratio = modulation_ratio(_METRIC_MOD_OLD_SUBDIVISION, _METRIC_MOD_NEW_SUBDIVISION)
    return {"trigger_beat": trigger_beat, "bpm": apply_metric_modulation(section_bpm, ratio)}


def _compute_tempo_map(sequence: list[str], base_bpm: float, halftime_flags: list[bool]) -> list[float]:
    """Per-section effective BPM for every section in `sequence`: the
    preset's own real `base_bpm` for every role, EXCEPT a "breakdown"
    section whose own `halftime_flags[i]` is `True` (X.33 -- resolved once
    per section on that section's own seeded rng via
    `_BREAKDOWN_HALFTIME_CHANCE`, real "occasional dramatic device" rather
    than the old "every single breakdown, unconditionally" behavior),
    which gets the real metric-modulation-scaled half-time tempo (X.6c) --
    computed via `structure.tempo_at`'s `"metric_modulation"` curve for
    that one section (`at` equal to the section's own index, so the
    curve's own "hold base_bpm before `at`" branch never applies), never a
    separate parallel calculation that skips that dispatch path.
    """
    tempos: list[float] = []
    for i, role in enumerate(sequence):
        if role != "breakdown" or not halftime_flags[i]:
            tempos.append(float(base_bpm))
            continue
        curve = {
            "type": "metric_modulation",
            "at": i,
            "old_subdivision": _METRIC_MOD_OLD_SUBDIVISION,
            "new_subdivision": _METRIC_MOD_NEW_SUBDIVISION,
        }
        tempos.append(tempo_at(i, base_bpm, curve))
    return tempos


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


# X.24 -- real cross-section blending on the main rhythm guitar. Real,
# ported machinery already exists for this (structure.pickup/bridge/
# flatten, P6.2 -- "overwrite the last couple of cells of the outgoing
# section with information from the incoming section's first cells") but
# was confirmed via grep to be called nowhere, ever: every section
# transition in every generated song has been a raw, unblended
# concatenation this whole session.
#
# `structure.pickup` isn't reused directly: it returns cells carrying ONLY
# `duration`/`is_rest` (the real reference source's simpler data model
# never needed more), but this project's cells carry extra real keys --
# `role` for drums, `velocity`/`timing_offset` for humanized guitar takes.
# A naive port would silently STRIP those at every blended boundary,
# producing a real hit with no role/velocity data (a missing-role KeyError
# for drums, a silently-orphaned pitch for guitar). `_pickup_cells`/
# `_pickup_values` below encode the exact same real rule ("last n cells of
# prev copy first n of next") but copy the FULL source cell/value, never a
# stripped-down one.
#
# Deliberately guitar-only for this pass: bass/kick/snare/hihat all
# "follow" the guitar's rhythm in various ways (`bass.follow_guitar_rhythm`,
# `bounce`/`two_step` kick locking) and would desync from a blended guitar
# unless also regenerated -- real, compounding complexity across 6 parallel
# per-section cell arrays, scoped out and documented rather than rushed.
# `structure.bridge()`'s inserted-transition-cell device is also
# deliberately deferred: inserting new cells changes a section's total
# beat count, which would desync every other instrument's own beat count
# too -- a real, coordinated multi-instrument redesign, not a quick add.
#
# X.28 CORRECTION -- real bug found via direct user listening feedback
# ("it's the composition"), confirmed by measuring real per-track total
# beat-durations on a composed song: `structure.pickup`'s source line
# (`out[start+j] = {"duration": src["duration"], "is_rest": src["is_rest"]}`)
# copies `duration` from the incoming cell. In the SOURCE project this is a
# real no-op -- that project's cells are fixed-size grid slots, so every
# cell's `duration` is already identical. This project's cells have
# VARIABLE durations (0.25/0.5/1.0 beat cells), so copying `duration` is
# NOT a no-op here: it silently changed a blended section's real total beat
# count away from `preset.bars * 4` (measured drifts of 0.25-1.75 beats per
# boundary on a real composed song). `bass`/`kick` get regenerated from the
# blended guitar afterward so they follow the new (wrong) total, but
# `snare`/`hihat` are generated once BEFORE blending and never touched
# again -- so from the first blended boundary onward, guitar/bass/kick run
# on a different absolute-time grid than snare/hihat, a real compounding
# desync between instrument tracks for the rest of the song. Fixed by
# preserving the OUTGOING cell's own `duration` at every blended position --
# every other real key (is_rest/role/velocity/timing_offset/
# pinch_harmonic) still comes from the incoming cell, so the real "lean
# toward what's coming" blend effect is unchanged, but a section's total
# beat count is now exactly invariant under blending, matching this
# project's own law ("a section is `preset.bars` bars of 4/4") and keeping
# every parallel per-section track on the same absolute-time grid.
_BLEND_N = 2


def _pickup_cells(prev_cells: list[dict], next_cells: list[dict], n: int = _BLEND_N) -> list[dict]:
    """Real reimplementation of `structure.pickup`'s rule, adapted for this
    project's variable-duration cells (see the X.28 correction comment
    above): the last `n` cells of `prev_cells` take on every real key from
    `next_cells`' first `n` cells (role/velocity/timing_offset/is_rest/
    pinch_harmonic -- real content, never stripped) EXCEPT `duration`,
    which stays the outgoing cell's own original value -- so a section's
    total beat count is exactly invariant under blending, never drifting
    away from `preset.bars * 4`. `n` is capped to whatever both lists
    actually have, matching the source's own bounds-safety; empty inputs
    return `prev_cells` unchanged (nothing to pick up from/into), matching
    `structure.pickup`'s own early-return contract."""
    if not prev_cells or not next_cells:
        return [dict(c) for c in prev_cells]
    out = [dict(c) for c in prev_cells]
    k = min(n, len(out), len(next_cells))
    for j in range(k):
        idx = len(out) - k + j
        original_duration = out[idx]["duration"]
        blended = dict(next_cells[j])
        blended["duration"] = original_duration
        out[idx] = blended
    return out


def _pickup_values(prev_values: list, next_values: list, n: int = _BLEND_N) -> list:
    """Same real rule as `_pickup_cells`, for a plain parallel value list
    (`pitches_per_cell`, not cell dicts) -- kept in lock-step with
    `_pickup_cells` so a guitar take's blended hit positions and its
    blended pitches stay mutually consistent."""
    if not prev_values or not next_values:
        return list(prev_values)
    out = list(prev_values)
    k = min(n, len(out), len(next_values))
    for j in range(k):
        out[len(out) - k + j] = next_values[j]
    return out


# X.27 -- real pinch-harmonic accent (scope sec.4: "Slam-specific devices:
# pinch-harmonic accent simulation..." -- kept as a real, genre-agnostic
# technique per the user's own standing direction that Metalerator-mined
# techniques generalize across every relevant genre, not just the original
# slam target this project no longer builds for). Confirmed via grep this
# whole session: `slam.mark_pinch_harmonics` (P3.10, real and tested) was
# never called from `song.py`. Applied to the roles where a real chug riff
# idiomatically punches a closing squeal -- `breakdown` and `outro`, the
# real phrase-ending roles.
#
# NOT calling `slam.mark_pinch_harmonics` directly: its own real contract
# resets EVERY hit in the cell to a flat `velocity_base`, which would
# destroy X.21's real per-hit open-vs-muted velocity data. This reuses the
# same real CONCEPT (the phrase's last real hit gets a velocity spike) but
# only touches that one accent cell, leaving every other cell's existing
# velocity untouched.
_PINCH_HARMONIC_ROLES = ("breakdown", "outro")
_PINCH_HARMONIC_VELOCITY = 127  # matches slam.mark_pinch_harmonics' own real default


def _apply_pinch_harmonic_accent(cells: list[dict]) -> list[dict]:
    """Real pinch-harmonic accent on `cells`' final real hit only -- see
    the module-level comment above `_PINCH_HARMONIC_ROLES` for the real
    design (why this doesn't call `slam.mark_pinch_harmonics` directly).
    A cell list with no real hits is returned unchanged (never fabricates
    an accent on a rest)."""
    out = [dict(c) for c in cells]
    hit_indices = [i for i, c in enumerate(out) if not c["is_rest"]]
    if hit_indices:
        last = hit_indices[-1]
        out[last]["velocity"] = _PINCH_HARMONIC_VELOCITY
        out[last]["pinch_harmonic"] = True
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


def _pedal_double_pitches(
    guitar_cells: list[dict], scale: Scale, guitar_fb: Fretboard, rng: random.Random,
) -> list[int | None]:
    """Real per-cell pitches for the pedal/chug doubler guitar
    (`section["guitar_pedal"]`) -- a genuinely separate second rhythm-
    guitar part, not another double-tracked copy of the main riff. See
    `_PEDAL_DOUBLE_WEIGHTS`' own module comment for the full real
    measured-reference citation (a real user-supplied Born-of-Osiris-
    style MIDI's own "Guitar 2" track: 95.9% root, tight low register,
    genuinely distinct from "Guitar 1"'s wider melodic riff).

    Draws deltas from that heavily root-biased vocab via the exact same
    real `generate_pitch_deltas` mechanism the main guitar's own pitch
    layer uses, anchored at `start_degree=0` (no `arc_row["register"]`
    offset -- keeps this part in the section's own low, tight register,
    matching the real reference), reusing the SAME rhythm cells as the
    main guitar (`guitar_cells`, a deliberate simplification -- see
    `_generate_one_section`'s own comment on the real production
    precedent for a rhythmically-locked low doubler). Every resulting
    pitch is snapped through the same real `_snap_to_playable_octave`
    every other guitar pitch in this project already gets, for a real,
    reachable `(string, fret)` -- never a fabricated note.
    """
    hit_count = sum(1 for c in guitar_cells if not c["is_rest"])
    deltas = generate_pitch_deltas(hit_count, scale, _PEDAL_DOUBLE_WEIGHTS, rng)
    pedal_motif = Motif(cell=guitar_cells, deltas=deltas)
    raw_pitches = pitches_per_cell(pedal_motif, scale, start_degree=0)
    return [None if p is None else _snap_to_playable_octave(guitar_fb, p) for p in raw_pitches]


# X.14 -- real listening feedback ("not much is going on") traced to a
# real architectural limitation: ThemeRegistry keys a base theme by ROLE
# ALONE, so every occurrence of that role for the WHOLE SONG reused just
# one of two pitch contours (base, or invert() -- alternating). A longer
# song revisiting a role many times (real for any longer song) heard the
# same 2 states over and over, no matter how many times the role recurred.
# `motif.transpose`/`motif.invert` already existed, fully real and tested,
# but only `invert` was ever wired into this rotation.
#
# X.35 CORRECTION -- real evidence from a user-supplied reference MIDI
# ("born of osiris style midi.mid", a genuine transcription) found the
# ORIGINAL fixed 4-state rotation below was itself wrong: the reference's
# own opening riff recurs BYTE-IDENTICALLY 23 times across the song, never
# varied anywhere -- confirmed by web research (Fundamental Changes'
# "Writing Better Metal Riffs: Sequencing") that real riff practice is
# "repeat first, vary rarely," not a mechanical vary-every-occurrence cycle.
# The fixed `occurrence % 4` rotation guaranteed variation starting on the
# very 2nd occurrence, every time -- the opposite of the real convention.
# Replaced with a real, seeded probabilistic choice: the same three real
# develop ops (invert/transpose/both) are kept as legitimate, occasional
# devices, but verbatim repetition is now the real DEFAULT outcome.
_THEME_REPEAT_VERBATIM_CHANCE = 0.7


def _develop_theme(base_theme: Motif, occurrence: int, rng: random.Random) -> Motif:
    """Real per-occurrence development for a reused role theme. Occurrence
    0 always returns `base_theme` unchanged (establishes the theme). Every
    later occurrence real-rolls `_THEME_REPEAT_VERBATIM_CHANCE` on the
    section's own seeded `rng`: most of the time (70%) the theme repeats
    VERBATIM (the real, dominant convention confirmed against a real
    reference transcription -- see the correction comment above), and the
    rest of the time one of three real, length-preserving develop ops
    (`transpose`/`invert` touch pitch deltas alone, never rhythm cell count
    or duration) is picked:

      - `invert(base)` -- contour mirrored around the anchor
      - `transpose(base, +2 degrees)` -- a real diatonic-third "repeat and
        lift", a standard real songwriting development move
      - `transpose(invert(base), +2 degrees)` -- both combined
    """
    if occurrence == 0:
        return base_theme
    if rng.random() < _THEME_REPEAT_VERBATIM_CHANCE:
        return base_theme
    variation = rng.choice(("invert", "transpose", "both"))
    if variation == "invert":
        return invert(base_theme)
    if variation == "transpose":
        return transpose(base_theme, _THEME_DEVELOP_TRANSPOSE_DEGREES)
    return transpose(invert(base_theme), _THEME_DEVELOP_TRANSPOSE_DEGREES)


def _two_child_seeds(rng: random.Random) -> tuple[int, int]:
    """Draw two distinct integer seeds from `rng` for `double_track`'s two
    independent takes -- deterministic given the parent `rng`'s state, so
    the whole song stays reproducible for a fixed top-level seed, while the
    two takes' humanization never shares an RNG stream (see
    performance.py's module docstring on why that must never happen)."""
    return rng.randrange(2**31), rng.randrange(2**31)


def _resolve_section_feel(role: str, preset: Preset, rng: random.Random) -> str | None:
    """X.32's real per-role feel override, extracted so `regenerate_
    section`'s real "same notes, new hits" primitive (P9.3) can resolve
    the exact same feel a full generation run would for this role, without
    duplicating the table lookup. Every role not named in either table
    keeps today's exact behavior (`preset.feel`, unchanged)."""
    if role in _ROLE_FEEL_FORCED:
        return _ROLE_FEEL_FORCED[role]
    if role in _ROLE_FEEL_OVERRIDE_CHOICES:
        return rng.choice(_ROLE_FEEL_OVERRIDE_CHOICES[role] + (preset.feel,))
    return preset.feel


# P9.3 -- real single-section generation, extracted from _generate_attempt's
# own per-section loop body (a pure extraction, zero behavior change for
# the full-song path -- verified against the full existing suite). This is
# the ONE real place a section's content is actually built; both the
# full-song loop below AND the real single-section `regenerate_section`
# (the new capability this extraction exists for) call it.
#
# `theme_source` is the only real difference between the two callers: the
# full-song path shares a base theme across every occurrence of a role
# (`ThemeRegistry.get_or_create`, X.14/X.35's own real repetition-bias
# design); a single-section regen always wants a FRESH theme (`generate_
# motif` called directly, ignoring the key). Both have the exact same real
# signature (`get_or_create`'s is `generate_motif`'s with a `key` prepended
# -- confirmed by reading both), so `theme_source(key, *args, **kwargs)` is
# a real, uniform seam, not an invented abstraction layer.
def _generate_one_section(
    rng: random.Random,
    preset: Preset,
    role: str,
    occurrence: int,
    scale: Scale,
    guitar_fb: Fretboard,
    bass_fb,
    total_beats: float,
    chromatic: bool,
    previous_role: str | None,
    theme_source,
    hit_chance_bias: float = 0.0,
    motif_override: Motif | None = None,
    blast_fill_chance: float | None = None,
) -> tuple[dict, str | None, str | None]:
    """Real, standalone per-section generation. Returns `(section, kick_
    style, blast_type)` -- `section` has no `"tempo_drop"` key yet (whole-
    song tempo resolution stays the caller's job, see `_compute_tempo_map`/
    `_resolve_tempo_drop`); `kick_style`/`blast_type` are returned
    separately (not stored on `section`) so a caller building a whole song
    can track them in its own parallel lists for the post-loop blend pass,
    matching the pre-extraction shape exactly.

    `hit_chance_bias` (P9.3): added to the real `_resolve_hit_chance`
    output before ITS OWN existing `[0.12, 0.98]` clamp -- the real
    density-nudge knob the editor's "too busy"/"too thin" primitive needs.
    `0.0` (the default) reproduces the original, pre-P9.3 hit_chance

    `motif_override` (P9.3): when given, `theme_source`/`_develop_theme`
    are skipped entirely and this EXACT motif is used as `m` -- the real
    seam `regenerate_section`'s "same notes, new hits" primitive needs (a
    freshly-drawn rhythm cell paired with an adapted pitch contour), while
    every downstream real step (kick/snare/hihat/blast/bass/lead/chord)
    still runs fresh against it, same as any other real section.
    exactly.
    """
    arc_row = arc(role=role)
    section_feel = _resolve_section_feel(role, preset, rng)

    hit_chance = _resolve_hit_chance(_BASE_HIT_CHANCE, arc_row["energy"])
    if hit_chance_bias:
        hit_chance = max(0.12, min(0.98, hit_chance + hit_chance_bias))

    if motif_override is not None:
        m: Motif = motif_override
    else:
        base_theme = theme_source(
            f"theme-{role}", total_beats, _ALLOWED_LENGTHS,
            hit_chance,
            rng, scale, preset.vocab.weights, chromatic=chromatic,
            dissonance=arc_row["dissonance"],
            base_degree=arc_row["start_degree"],
            group_beats=(float(preset.group) if preset.group is not None else None),
            # X.31 -- verse forces a real, strong pedal bias regardless of
            # what the preset's own `.pedal` declares (same precedent as
            # X.11's build/solo kick overlay overriding `preset.kick`):
            # Metalerator's real verse riff (RGuitarPedalToneRiff) is ~65%
            # root note, occasional colored upper-scale-degree note -- a
            # distinct, sparser character than the preset's own general
            # riffing, not just "verse again with whatever pedal happens to
            # be set."
            pedal=(_VERSE_PEDAL_BIAS if role == "verse" else preset.pedal),
            feel=section_feel,
            # X.19 -- real IRVD phrase development (bar-by-bar
            # intro/repeat/vary/destroy shape) for every preset EXCEPT
            # djent/progressive, whose real `group_beats` polymeter tiling
            # is a different, already-real "something happens across the
            # section" device that IRVD's verbatim-repeat structure would
            # directly fight (see motif.generate_motif's docstring).
            irvd_bars=(preset.bars if preset.group is None else None),
            markov=preset.vocab.markov,
        )
        m = _develop_theme(base_theme, occurrence, rng)
    guitar_cells = m.cell

    # X.30 -- real per-bar tonal-center progression (see progression.py's
    # module docstring for the full real Metalerator citation). Only
    # verse/chorus get one: this is a real, evidenced verse/chorus
    # device, not applied everywhere by default -- every other role
    # keeps a single fixed anchor for the whole section, unchanged.
    progression_table = _PROGRESSION_TABLES.get(role)
    chord_progression = (
        rng.choice(list(progression_table.values())) if progression_table else None
    )
    if chord_progression is not None:
        raw_pitches = pitches_per_cell_with_progression(
            m, scale, chord_progression, _BEATS_PER_BAR, start_degree=arc_row["start_degree"],
        )
    else:
        raw_pitches = pitches_per_cell(m, scale, start_degree=arc_row["start_degree"])
    cell_pitches = [
        (None if p is None else _snap_to_playable_octave(guitar_fb, p))
        for p in raw_pitches
    ]

    seed_a, seed_b = _two_child_seeds(rng)
    # X.21 -- real open-string-vs-muted articulation (see performance.
    # humanize_take's own docstring for the full real citation). Each
    # take independently rolls its own open/muted pattern (separate
    # rng instances, same as their existing independent timing/velocity
    # jitter) -- a deliberate choice consistent with double_track's own
    # "two independently-humanized takes" philosophy, not an oversight.
    take_a, take_b = double_track(
        guitar_cells, random.Random(seed_a), random.Random(seed_b),
        open_chance=preset.open_chance,
    )

    # Real, second, genuinely-different rhythm-guitar part -- see
    # `_PEDAL_DOUBLE_WEIGHTS`' own module comment for the full real
    # measured-reference citation. Skipped for chill/interlude, which
    # stay deliberately quiet/atmospheric (X.9/X.11/X.22 already keep
    # kick/snare/hihat silent there); a heavy root chug would contradict
    # that same silence contract. A single take (not double-tracked --
    # this is a tight, discrete low layer, not part of the wide-stereo
    # pair), reusing `guitar_cells`' own rhythm (locked timing, a real
    # production precedent -- a "low string doubler" commonly follows
    # the main riff's picking rhythm exactly, and this avoids an
    # independently-generated rhythm stream needing its own cross-
    # section-blending/kick-lock consideration for a single reference's
    # ambiguous density difference).
    if role not in ("chill", "interlude"):
        pedal_pitches_per_cell = _pedal_double_pitches(guitar_cells, scale, guitar_fb, rng)
        pedal_seed = rng.randrange(2**31)
        guitar_pedal = humanize_take(
            guitar_cells, random.Random(pedal_seed), open_chance=preset.open_chance,
        )
    else:
        pedal_pitches_per_cell = []
        guitar_pedal = []

    # X.24 -- resolve the STYLE explicitly (rather than calling
    # drums.kick_pattern_for_role directly) so it can be stored and
    # reused later to re-lock kick to the blended guitar rhythm after
    # the post-loop blending pass, without re-rolling a second random
    # choice for build/solo roles' real overlay (same rng draw, same
    # order, as calling kick_pattern_for_role would have made).
    kick_style = resolve_kick_style(role, preset.kick, rng=rng)
    if kick_style is None:
        kick_cells = [{"duration": c["duration"], "is_rest": True, "role": None} for c in guitar_cells]
    else:
        kick_cells = kick_pattern_for_style(guitar_cells, kick_style, rng=rng)
    snare_cells = snare_pattern_for_role(guitar_cells, role)
    hihat_cells = hihat_pattern_for_role(guitar_cells, role)

    # X.34 -- real, occasional blast beat (see module-level
    # _BLAST_FILL_ROLES/_BLAST_FILL_CHANCE comment). Rendered directly
    # onto this section's own guitar_cells (guaranteed cell-aligned
    # with kick/snare, unlike the old, real-but-never-wired
    # generate_vocabulary_informed_blast_fill's independent skeleton),
    # so it REPLACES the kick/snare cells just resolved above -- a real
    # KICK/SNARE-alternating blast, not the old guitar-locked-but-
    # kick-only "blast" kick style.
    blast_type: str | None = None
    effective_blast_chance = _BLAST_FILL_CHANCE if blast_fill_chance is None else blast_fill_chance
    if role in _BLAST_FILL_ROLES and rng.random() < effective_blast_chance:
        blast = render_blast_beat(guitar_cells, _BLAST_WEIGHTS, rng)
        blast_type = blast["blast_type"]
        kick_cells = blast_kick_cells(blast["cells"])
        snare_cells = blast_snare_cells(blast["cells"])

    bass_cells = follow_guitar_rhythm(guitar_cells, cell_pitches, bass_fb)

    pad_root = scale.root + arc_row["register"]
    pad = pad_voicing(pad_root)
    accents = find_accents(guitar_cells, pad_root)

    # X.13: real hihat accents at the same structurally-accented
    # positions the rest of the arrangement already uses (never an
    # independently-invented accent set), plus a real crash at the
    # start of a section whose role genuinely changed from the
    # previous one -- skipped for chill/interlude, which stay silent
    # by design (a crash into an atmospheric section would contradict
    # that same silence contract). `previous_role=None` on the first
    # section still counts as "changed", a real opening crash.
    accent_indices = {a["cell_index"] for a in accents}
    hihat_cells = apply_hihat_accents(hihat_cells, accent_indices)
    if role not in ("chill", "interlude"):
        hihat_cells = add_transition_crash(hihat_cells, fire=(role != previous_role))

    # preset.octave_stab wiring: a real theory.VoiceLeader.stab() leap
    # (a deliberate wide interval jump, explicitly exempt from
    # VoiceLeader's normal voice-leading smoothing -- see theory.py's
    # docstring) at each of this section's structurally-accented
    # positions, but ONLY for presets that actually declare
    # octave_stab=True. A False preset gets an empty list here, never a
    # fabricated stab -- the boolean now measurably changes
    # compose_song's output instead of being validated and stored only.
    #
    # `stab()` itself draws no randomness at all (it is a deterministic
    # leap from `prev`, see theory.py), so the VoiceLeader built here
    # deliberately does NOT consume the section's shared `rng` (it is
    # constructed with `rng=None`, which VoiceLeader defaults to its
    # own throwaway `random.Random(0)`) -- octave_stab's effect on a
    # song must stay isolated to the stab pitches themselves, never
    # silently reseed every later section's independent rng draws just
    # because the boolean flipped.
    if preset.octave_stab and accents:
        voice_leader = VoiceLeader(
            scale, weights=preset.vocab.weights, rng=None,
            anchor=pad_root, motion=preset.vocab.motion,
        )
        octave_stabs = [voice_leader.stab(prev=pad_root) for _ in accents]
    else:
        octave_stabs = []

    # The lead guitar is NOT the same busy melodic voice in every
    # section all song long -- a real second guitar changes role by
    # section, same as it would in an actual arrangement:
    lead_anchor = pad_root
    lead_mode: str
    # Only chill/interlude sections ever populate these (X.6b); every
    # other role leaves them None -- not applicable, never fabricated.
    chord_quality: str | None = None
    chord_voicing: list[tuple[int, int]] | None = None
    # Only dense-chug ("ambient_lead" lead_mode) sections ever populate
    # this (see the `else` branch below) -- solo/chorus/chill already
    # have their own real melodic voice and don't need a doubled riff on
    # top. Per-cell shape (None on rest), same as `pitches_per_cell` --
    # see the `else` branch's own comment for why.
    synth_double_pitches: list[int | None] = []
    if role == "solo":
        # A genuine featured lead: denser (roughly 8th-note-rate across
        # the section rather than one note per rhythm hit), more active
        # (`motion` raised -> more stepwise walking, per VoiceLeader's
        # own "active styles walk" design), more wide leaps
        # (`stab_chance` raised -- scope sec.4's "occasional wide
        # sweep-style interval leaps for technicality"), and a register
        # pushed up an extra octave (solos sit above the rhythm pedal).
        lead_mode = "solo"
        # A genuinely separate lead-register vocab, when the preset has
        # one (calibrated by reference_vocab.build_preset_from_corpus
        # from real corpus songs' own transcribed LEAD-register content,
        # distinct from the rhythm-guitar riff vocab). Falls back to the
        # riff vocab for any preset that hasn't been calibrated against
        # real lead-register data yet -- the same real fallback
        # `presets.blend_presets` already uses, never a fabricated guess.
        lead_vocab = preset.lead_vocab if preset.lead_vocab is not None else preset.vocab
        lead_notes = generate_lead_line(
            scale, lead_vocab.weights, min(1.0, lead_vocab.motion + 0.3), rng,
            low=lead_anchor - 12, high=lead_anchor + 24, anchor=lead_anchor + 12,
            num_notes=max(1, round(total_beats * 2)),
            stab_chance=0.35,
            markov=lead_vocab.markov,
        )
        # X.36 -- real melodic "sequence" passage (see lead.
        # generate_sequence_line's own module-level comment for the
        # full real reference-MIDI/research citation): a real solo
        # reads as a phrase with a beginning, middle, and end -- the
        # established main phrase above, a real sequence passage here
        # (a short motif repeated at shifting scale positions, the
        # real core solo-writing technique), then the existing legato
        # close below. Picks up where the main phrase's last note
        # landed (never a disconnected new register), and moves in a
        # real seeded-random direction (ascending or descending --
        # both real, valid forms of the device).
        seq_start_degree = scale.index_of(lead_notes[-1]) if lead_notes else scale.index_of(lead_anchor + 12)
        seq_step = rng.choice((-1, 1))
        sequence_notes = generate_sequence_line(
            scale, lead_vocab.weights, rng,
            start_degree=seq_start_degree,
            motif_len=_SOLO_SEQUENCE_MOTIF_LEN,
            num_repeats=_SOLO_SEQUENCE_REPEATS,
            step_degrees=seq_step,
            markov=lead_vocab.markov,
        )
        # Same real register guarantee generate_lead_line's own clamp
        # already gives the main phrase -- a sequence's own repeated
        # shifting can otherwise drift outside the solo's real playable
        # register.
        seq_low, seq_high = lead_anchor - 12, lead_anchor + 24
        sequence_notes = [max(seq_low, min(seq_high, p)) for p in sequence_notes]
        lead_notes = list(lead_notes) + sequence_notes
        # X.6a: a real featured solo needs legato technique too, not
        # just VoiceLeader's leap-and-settle phrasing -- splice one
        # genuine contiguous legato run (engine/legato.py) onto the end
        # of the featured line every solo section (a documented
        # "always", not a probability roll, so the path is exercised
        # deterministically by every seed/preset). Direction and
        # length are drawn from the section's own `rng` so the whole
        # song stays reproducible for a fixed seed. Length favors the
        # genuine tuplet counts legato_run_rhythm knows how to frame
        # (3/5/7); span is one beat, a fast burst rather than a slow
        # phrase, per the brief's own framing of a legato run as
        # "often a subdivision within a beat".
        legato_length = rng.choice((3, 5, 6, 7))
        legato_direction = rng.choice((1, -1))
        legato_start = lead_notes[-1] if lead_notes else lead_anchor + 12
        try:
            legato = generate_legato_lick(
                scale, guitar_fb, legato_start, legato_length,
                span_beats=1.0, rng=rng, direction=legato_direction,
            )
        except ValueError:
            # Genuinely unplayable on this preset's tuning/fretboard
            # (e.g. the run would run off the top of the neck) --
            # fail closed by skipping the splice rather than
            # fabricating fret positions. The lead line itself is
            # untouched either way.
            legato = None
        else:
            lead_notes = list(lead_notes) + legato["pitches"]
    elif role == "chorus":
        # X.31 -- real chorus lead, the second half of Metalerator's own
        # RGuitarChorus device (a chorus riff generates an accompanying
        # lead alongside it, `generate_lead`, not silent like the other
        # dense-chug roles). Deliberately less extreme than "solo"'s
        # fully-featured technical break: motion stays at the preset's
        # own value (not solo's `+0.3` boost -- a chorus lead sits WITH
        # the riff, not over it as a featured break), a narrower
        # `stab_chance`, and register one octave above the riff (not
        # solo's wider `-12..+24` span) -- "a lead sits over the
        # chorus", not a second solo. No legato splice (that's a real,
        # deliberately solo-only technical device).
        lead_mode = "chorus_lead"
        # Same real lead-register vocab fallback as the "solo" branch
        # above -- a chorus lead is still a lead-guitar melodic voice,
        # not the rhythm riff, so it draws from the same calibrated
        # source when one exists.
        lead_vocab = preset.lead_vocab if preset.lead_vocab is not None else preset.vocab
        lead_notes = generate_lead_line(
            scale, lead_vocab.weights, lead_vocab.motion, rng,
            low=lead_anchor, high=lead_anchor + 24, anchor=lead_anchor + 12,
            num_notes=max(1, round(total_beats * 2)),
            stab_chance=0.15,
            markov=lead_vocab.markov,
        )
        legato = None
    elif role in ("chill", "interlude"):
        # A melodic/atmospheric section: the second guitar harmonizes
        # the rhythm's own theme at a fixed interval (riff.
        # harmonize_line, P3.12) rather than playing an independent
        # phrase -- rhythmically locked to the SAME motif, so it reads
        # as one arranged part, not two guitars doing unrelated things.
        lead_mode = "harmony"
        _lead_line, lead_notes = harmonize_line(m, scale, start_degree=arc_row["start_degree"])
        legato = None
        # X.6b: these are exactly the ambient/clean sections
        # god-tier-metal-scope.md names as needing a real extended
        # chord vocabulary (Periphery-style maj7/add9/sus2/min9 pads,
        # not just the power-chord/triad tuples used elsewhere in this
        # file). `arc_row["dissonance"]` -- the SAME per-section value
        # already threaded into this section's `generate_motif` call
        # above -- picks a chord quality via `chord_vocab.
        # quality_for_dissonance` (low dissonance -> open/consonant
        # sus2/add9/maj7; high -> darker min7/min9; see that function's
        # docstring for the exact bucketing), voiced at `pad_root` (the
        # same real, already-computed section root the plain
        # `atmosphere.pad_voicing` triad above uses). A genuinely
        # unreachable chord on this preset's tuning/fretboard (e.g. an
        # extended 5-note voicing that doesn't fit within max_span on a
        # narrow-range tuning) fails closed to `None` -- never a
        # fabricated/partial shape.
        chord_quality = quality_for_dissonance(arc_row["dissonance"])
        try:
            chord_voicing = voice_named_chord(pad_root, chord_quality, guitar_fb, max_span=4)
        except ValueError:
            chord_voicing = None
    else:
        # Dense chug sections (intro/build/breakdown/outro/verse): a
        # BUSY independently-composed lead (solo-density, wide leaps)
        # would clash with the rhythm here -- real arrangements leave
        # the second guitar out of a hard breakdown rather than
        # noodling a competing technical line over it. But this engine
        # has no vocals (a permanent, deliberate non-goal), and a real
        # vocal-fronted song like this one's own reference corpus has a
        # continuous melodic/rhythmic voice through EVERY section,
        # verses included -- leaving 70-80% of a generated song with
        # ZERO independent melodic content (confirmed directly via
        # direct user listening feedback: real generated songs had
        # `lead_mode="silent"` for 8 of 10 sections) is a real,
        # structural gap the riff-doubling synth below doesn't close,
        # since doubling the SAME riff an octave up is reinforcement,
        # not a second musical idea.
        #
        # `lead_mode = "ambient_lead"`: a real, genuinely INDEPENDENT
        # melodic line, reusing the exact same `generate_lead_line`/
        # `lead_vocab` machinery solo/chorus_lead already use (a preset
        # calibrated with real corpus lead-register data, including its
        # own Markov transitions, drives this too -- not a separate,
        # invented mechanism), but deliberately SPARSE and SUSTAINED
        # (one note every 2 beats -- half the rate of solo/chorus_lead's
        # own dense 8th-note convention) so it reads as a real
        # background melodic voice riding OVER the dense chug, never
        # competing with it rhythmically. `stab_chance=0.0`: wide
        # technical leaps are a featured-solo device, not appropriate
        # for a background line sitting under a breakdown.
        lead_mode = "ambient_lead"
        lead_vocab = preset.lead_vocab if preset.lead_vocab is not None else preset.vocab
        lead_notes = generate_lead_line(
            scale, lead_vocab.weights, lead_vocab.motion, rng,
            low=lead_anchor, high=lead_anchor + 24, anchor=lead_anchor + 12,
            num_notes=max(1, round(total_beats / 2)),
            stab_chance=0.0,
            markov=lead_vocab.markov,
        )
        legato = None
        # The riff-doubling synth (scope sec.16.1's own real research
        # finding -- the synth should double/harmonize the SAME riff
        # essentially continuously, "a genuine compositional voice under
        # riffs and interludes, not just intro-only ambience") stays,
        # additive to the new ambient lead above, not replaced by it --
        # two distinct real devices, not a swap. `atmosphere.
        # synth_double` re-renders THIS section's own `m` motif via the
        # same `render_motif` the guitar itself uses, so its rhythm/
        # contour is GUARANTEED identical -- a doubling, never a second
        # competing idea -- shifted up `_SYNTH_DOUBLE_TRANSPOSE`
        # semitones (an octave).
        #
        # Stored PER-CELL (None on rest), the exact same shape as
        # `pitches_per_cell` -- not per-hit -- specifically so X.24's own
        # cross-section blending pass (`_pickup_values`, below and in
        # `regenerate_section`) can blend it the identical real way it
        # already blends `pitches_per_cell`, keeping it index-aligned
        # with `guitar_take_a` even after the tail gets overwritten by a
        # neighbor. A per-HIT list (this function's first real attempt)
        # broke exactly there: blending can change how many hits land in
        # a section's tail without this list knowing, desyncing a
        # naive hit-by-hit zip in the exporter -- the same real class of
        # bug X.28 already fixed once for guitar/bass/kick.
        synth_double_hits = iter(synth_double(
            m, scale, start_degree=arc_row["start_degree"], transpose=_SYNTH_DOUBLE_TRANSPOSE,
        ))
        synth_double_pitches = [None if c["is_rest"] else next(synth_double_hits) for c in m.cell]

    # X.18: real mid-section half-time drop trigger -- see module-level
    # docstring above `_resolve_tempo_drop`. Only the TRIGGER BEAT is
    # decided here (needs this section's own seeded `rng` and
    # `preset.bars`); the actual dropped BPM is resolved after
    # `tempo_map` exists, since it scales THIS section's own
    # already-computed tempo, not `preset.bpm` directly.
    tempo_drop_trigger_beat: float | None = None
    if (
        role in _TEMPO_DROP_ROLES
        and preset.bars >= _TEMPO_DROP_MIN_BARS
        and rng.random() < _TEMPO_DROP_CHANCE
    ):
        tempo_drop_trigger_beat = total_beats - _TEMPO_DROP_TAIL_BARS * _BEATS_PER_BAR

    section = {
        "role": role,
        "arc": arc_row,
        "motif": m,
        "pitches_per_cell": cell_pitches,
        "guitar_take_a": take_a,
        "guitar_take_b": take_b,
        "guitar_pedal": guitar_pedal,
        "pedal_pitches_per_cell": pedal_pitches_per_cell,
        "lead_mode": lead_mode,
        "lead": lead_notes,
        "legato": legato,
        "kick": kick_cells,
        "snare": snare_cells,
        "hihat": hihat_cells,
        "bass": bass_cells,
        "pad": pad,
        "accents": accents,
        "octave_stabs": octave_stabs,
        "synth_double": synth_double_pitches,
        "chord_quality": chord_quality,
        "chord_voicing": chord_voicing,
        "chord_progression": chord_progression,
        "_tempo_drop_trigger_beat": tempo_drop_trigger_beat,
    }
    return section, kick_style, blast_type


def _generate_attempt(
    rng: random.Random, preset: Preset, num_sections: int, blast_fill_chance: float | None = None,
) -> dict:
    """One full attempt at composing a song from `preset`. Called
    repeatedly (with fresh seeds) by `judge_and_retry` in `compose_song`
    below until the result judges `ok`, or attempts run out.

    `blast_fill_chance` (P9.2): real per-request override of the module
    default `_BLAST_FILL_CHANCE`, threaded straight through to every
    section -- Guided Mode's "blast-beat frequency" dial. `None` (the
    default) reproduces the exact pre-P9.2 behavior."""
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

    sections: list[dict] = []
    guitar_track: list[dict] = []
    drum_track: list[dict] = []
    kick_styles: list[str | None] = []
    blast_types: list[str | None] = []
    breakdown_halftime_flags: list[bool] = []
    previous_role: str | None = None

    # P9.3 -- the loop is now a thin wrapper over _generate_one_section
    # (extracted from what used to be this loop's own body, verbatim,
    # verified byte-identical against the full test suite): theme_source
    # binds ThemeRegistry.get_or_create so sections sharing a role share a
    # base theme (X.14/X.35's own real repetition-bias design) -- the
    # single-section regen path below (regenerate_section) passes a
    # different theme_source that always builds fresh instead.
    def _shared_theme_source(key, *args, **kwargs):
        return themes.get_or_create(key, *args, **kwargs)

    for idx, role in enumerate(sequence):
        occurrence = role_occurrences.get(role, 0)
        role_occurrences[role] = occurrence + 1

        section, kick_style, blast_type = _generate_one_section(
            rng, preset, role, occurrence, scale, guitar_fb, bass_fb,
            total_beats, chromatic, previous_role, _shared_theme_source,
            blast_fill_chance=blast_fill_chance,
        )
        kick_styles.append(kick_style)
        blast_types.append(blast_type)
        breakdown_halftime_flags.append(role == "breakdown" and rng.random() < _BREAKDOWN_HALFTIME_CHANCE)
        previous_role = role
        sections.append(section)

    tempo_map = _compute_tempo_map(sequence, preset.bpm, breakdown_halftime_flags)
    for section, bpm in zip(sections, tempo_map):
        section["tempo_drop"] = _resolve_tempo_drop(bpm, section.pop("_tempo_drop_trigger_beat"))

    # X.24 -- real cross-section blending on the main rhythm guitar, applied
    # once every section is fully generated (see _pickup_cells/_pickup_
    # values' own docstrings for the real design). Pure/deterministic --
    # consumes no rng, so this never affects reproducibility for anything
    # computed above. Real, found-during-testing exclusion: chill/interlude
    # (lead_mode == "harmony") tie section["lead"] to the guitar's own
    # PRE-blend hit count (riff.harmonize_line renders one lead note per
    # guitar hit, computed before double-tracking/blending) -- blending
    # those sections' guitar hit pattern would desync that pairing and
    # crash midi_export's real per-hit harmony zip. Excluded here, matching
    # the same real role-exclusion pattern used everywhere else this
    # session (kick/snare/hihat/chord-thickening all already exempt these
    # two atmospheric roles for their own real reasons).
    for i in range(len(sections) - 1):
        this_section, next_section = sections[i], sections[i + 1]
        if this_section["role"] in ("chill", "interlude"):
            # Only THIS section's own cells get modified below (next_section
            # is read-only, used purely as a blend source) -- so only
            # THIS section's role matters for the real harmony-mode
            # exclusion described above.
            continue
        this_section["guitar_take_a"] = _pickup_cells(this_section["guitar_take_a"], next_section["guitar_take_a"])
        this_section["guitar_take_b"] = _pickup_cells(this_section["guitar_take_b"], next_section["guitar_take_b"])
        this_section["pitches_per_cell"] = _pickup_values(
            this_section["pitches_per_cell"], next_section["pitches_per_cell"]
        )
        # Same real per-cell blend, same reason: keeps synth_double
        # index-aligned with the just-blended guitar_take_a. Safe to call
        # unconditionally -- `_pickup_values` returns its input unchanged
        # when either side is empty (solo/chorus/chill sections carry an
        # empty synth_double, never populated).
        this_section["synth_double"] = _pickup_values(
            this_section["synth_double"], next_section["synth_double"]
        )
        # Same real per-cell blend for the new pedal/chug doubler guitar
        # -- keeps it index-aligned with guitar_take_a/take_b, same
        # unconditional-safety reasoning as synth_double above (empty on
        # chill/interlude, never populated there).
        this_section["guitar_pedal"] = _pickup_cells(
            this_section["guitar_pedal"], next_section["guitar_pedal"]
        )
        this_section["pedal_pitches_per_cell"] = _pickup_values(
            this_section["pedal_pitches_per_cell"], next_section["pedal_pitches_per_cell"]
        )

        # Real, "do it properly" extension: bass and (the guitar-locking
        # kick styles) both derive from the guitar's own rhythm/pitches --
        # left unregenerated, they'd silently desync from the now-blended
        # guitar at exactly the boundary cells that just changed. Both
        # regenerations are pure/deterministic (`follow_guitar_rhythm` has
        # no rng at all; `kick_pattern_for_style`'s own docstring confirms
        # every real style is deterministic given guitar_cells -- `rng` is
        # accepted only for interface symmetry), so this re-lock is exact,
        # not approximated, and consumes no additional rng draws --
        # `kick_styles[i]` reuses the SAME style already chosen for this
        # section, never a fresh random re-roll. Styles that don't actually
        # look at guitar's specific hit/rest positions (`two_step`, `blast`,
        # `double_kick`, `burst`) regenerate to byte-identical output, so
        # this is safe to apply uniformly rather than branching per style.
        this_section["bass"] = follow_guitar_rhythm(
            this_section["guitar_take_a"], this_section["pitches_per_cell"], bass_fb
        )

        # X.34 -- a blast-fill section (see _BLAST_FILL_ROLES/_BLAST_FILL_
        # CHANCE) is guitar-locked too, so it needs the exact same real
        # re-lock treatment as a guitar-locking kick style -- reusing the
        # SAME blast type already chosen for this section (render_blast_
        # beat_for_type, no rng/re-roll), never a fresh random re-pick.
        # This is the one place snare_cells becomes blend-aware -- a real,
        # deliberate, documented exception to the "snare stays exactly as
        # generated" rule above, scoped only to blast-fill sections. Skips
        # the normal kick_style re-lock below entirely: blast owns both
        # kick and snare for this section, not the resolved kick style.
        blast_type = blast_types[i]
        if blast_type is not None:
            blast = render_blast_beat_for_type(this_section["guitar_take_a"], blast_type)
            this_section["kick"] = blast_kick_cells(blast["cells"])
            this_section["snare"] = blast_snare_cells(blast["cells"])
            continue

        kick_style = kick_styles[i]
        if kick_style is not None:
            this_section["kick"] = kick_pattern_for_style(this_section["guitar_take_a"], kick_style)

    # X.27 -- real pinch-harmonic accent, applied last (after blending) so
    # it always lands on the TRUE final hit of each fully-assembled
    # section, not one that blending might later overwrite.
    for section in sections:
        if section["role"] in _PINCH_HARMONIC_ROLES:
            section["guitar_take_a"] = _apply_pinch_harmonic_accent(section["guitar_take_a"])
            section["guitar_take_b"] = _apply_pinch_harmonic_accent(section["guitar_take_b"])

    for section in sections:
        guitar_track.extend(section["guitar_take_a"])
        drum_track.extend(section["kick"])

    comp = {"guitar": guitar_track, "drums": drum_track}
    return {
        "preset_id": preset.id,
        "tuning_key": preset.tuning_key,
        "sequence": sequence,
        "sections": sections,
        "tempo_map": tempo_map,
        "guitar_fretboard": guitar_fb,
        "bass_fretboard": bass_fb,
        "judge": judge(comp),
        "_comp": comp,
    }


# ---------------------------------------------------------------------------
# P9.3 -- real single-section regeneration, the editor's real regen
# primitives (rhythm-only / pitch-only / full reroll / density nudge /
# section-type conversion all reduce to this one real capability).
# ---------------------------------------------------------------------------

_REGEN_MODES = ("full", "pitch", "rhythm")


def _adapt_deltas(old_deltas: list[int], new_hit_count: int) -> list[int]:
    """Real, deterministic pitch-contour adaptation for `regenerate_
    section`'s "rhythm" mode ("same notes, new hits"): cycles the existing
    deltas to fit a real, possibly-different new hit count -- an honest,
    documented interpretation (a contour can't be losslessly preserved
    across a genuinely different hit count, so it repeats instead of being
    silently truncated to nothing or padded with fabricated zeros)."""
    if new_hit_count <= 0:
        return []
    if not old_deltas:
        return [0] * new_hit_count
    return [old_deltas[i % len(old_deltas)] for i in range(new_hit_count)]


def _regenerate_pitch_only(
    original: dict, rng: random.Random, preset: Preset, scale: Scale, guitar_fb: Fretboard, bass_fb,
) -> dict:
    """Real "new notes, same hits" (scope sec.10.2): the section's own
    existing rhythm cell (`motif.cell`) is untouched -- only the pitch
    deltas are redrawn, via the exact real per-hit weighted-interval
    mechanism `generate_motif`'s own pitch loop uses (`motif.
    generate_pitch_deltas`). Kick/snare/hihat/blast/lead/chord data all
    carry through from `original` unchanged, since none of them depend on
    pitch content -- matches the real two-layer rhythm/pitch model this
    device is named after (only the pitch layer changes)."""
    old_motif: Motif = original["motif"]
    arc_row = original["arc"]
    role = original["role"]
    hit_count = sum(1 for c in old_motif.cell if not c["is_rest"])
    chromatic = preset.dissonance >= _CHROMATIC_DISSONANCE_THRESHOLD
    new_deltas = generate_pitch_deltas(
        hit_count, scale, preset.vocab.weights, rng,
        chromatic=chromatic, dissonance=arc_row["dissonance"],
        base_degree=arc_row["start_degree"],
        pedal=(_VERSE_PEDAL_BIAS if role == "verse" else preset.pedal),
        markov=preset.vocab.markov,
    )
    new_motif = Motif(cell=[dict(c) for c in old_motif.cell], deltas=new_deltas)

    chord_progression = original.get("chord_progression")
    if chord_progression is not None:
        raw_pitches = pitches_per_cell_with_progression(
            new_motif, scale, chord_progression, _BEATS_PER_BAR, start_degree=arc_row["start_degree"],
        )
    else:
        raw_pitches = pitches_per_cell(new_motif, scale, start_degree=arc_row["start_degree"])
    cell_pitches = [(None if p is None else _snap_to_playable_octave(guitar_fb, p)) for p in raw_pitches]

    seed_a, seed_b = _two_child_seeds(rng)
    take_a, take_b = double_track(
        new_motif.cell, random.Random(seed_a), random.Random(seed_b), open_chance=preset.open_chance,
    )
    if role in _PINCH_HARMONIC_ROLES:
        take_a = _apply_pinch_harmonic_accent(take_a)
        take_b = _apply_pinch_harmonic_accent(take_b)
    bass_cells = follow_guitar_rhythm(new_motif.cell, cell_pitches, bass_fb)

    new_section = dict(original)
    new_section.update({
        "motif": new_motif,
        "pitches_per_cell": cell_pitches,
        "guitar_take_a": take_a,
        "guitar_take_b": take_b,
        "bass": bass_cells,
    })
    return new_section


def regenerate_section(
    song: dict,
    index: int,
    rng: random.Random,
    preset: Preset,
    mode: str = "full",
    role: str | None = None,
    hit_chance_bias: float = 0.0,
) -> dict:
    """Real, standalone single-section regeneration -- the editor's real
    regen primitives all reduce to this one function. `song` must be a
    real `compose_song`/`_generate_attempt` (or previously-regenerated)
    result. Returns a NEW song dict: `sections`/`sequence` updated at
    `index`, `judge`/`_comp` recomputed against the real edited output;
    `song`'s own dict/lists are never mutated in place.

    `mode`:
      - `"full"`: a completely fresh section (new rhythm AND new pitch) --
        breaks this section's link to X.14/X.35's cross-section theme
        sharing (there's no way to rejoin a shared-theme rotation after
        the fact without regenerating every OTHER section sharing that
        role too -- a real, documented, honest tradeoff, not silently
        dropped).
      - `"pitch"`: "new notes, same hits" -- see `_regenerate_pitch_only`.
      - `"rhythm"`: "same notes, new hits" -- a fresh rhythm cell, the
        existing pitch CONTOUR adapted to fit (`_adapt_deltas`); every
        downstream real step (kick/snare/hihat/blast/lead/chord) runs
        fresh against the new cell, since those genuinely depend on the
        section's rhythm shape.
      `role`, when given, regenerates using a DIFFERENT role's real
      arc/feel/kick/pedal resolution (the "Make breakdown"-style
      section-type-conversion primitive) -- `_generate_one_section`
      already takes `role` as a real parameter, so this falls out for
      free; only meaningful with mode `"full"`/`"rhythm"` (pitch-only
      regen keeps the section's existing role, its rhythm cell doesn't
      change).
      `hit_chance_bias`: the real density-nudge knob ("too busy"/"too
      thin"), added to `_resolve_hit_chance`'s real output before its own
      clamp -- only meaningful for `"full"`/`"rhythm"` (a fresh rhythm
      draw is the only thing hit_chance affects).

    Real, minimal neighbor re-blend: re-applies X.24's own pure, no-rng
    `_pickup_cells`/`_pickup_values` pickup at the (up to) two real
    boundaries touching the edited section, so an edit doesn't leave an
    abrupt seam. A DOCUMENTED, SMALLER scope than a full song's own blend
    pass: a neighbor's bass is re-locked to ITS OWN (just-pickup-blended)
    guitar, but a neighbor's KICK is not re-locked (that needs knowing
    which kick style/blast type the neighbor used, not tracked per
    section today) -- a neighbor's kick can show a small, real, honestly-
    documented inconsistency at just the boundary cells whose content
    just changed.
    """
    if mode not in _REGEN_MODES:
        raise ValueError(f"unknown regen mode: {mode!r} (expected one of {_REGEN_MODES})")
    n = len(song["sections"])
    if not (0 <= index < n):
        raise ValueError(f"index {index} out of range for {n} real sections")

    original = song["sections"][index]
    target_role = role if role is not None else original["role"]
    total_beats = float(preset.bars * _BEATS_PER_BAR)
    chromatic = preset.dissonance >= _CHROMATIC_DISSONANCE_THRESHOLD
    guitar_fb: Fretboard = song["guitar_fretboard"]
    bass_fb = song["bass_fretboard"]
    scale = Scale(root=guitar_fb.tuning[0], name=preset.scale)

    if mode == "pitch" and role is None:
        new_section = _regenerate_pitch_only(original, rng, preset, scale, guitar_fb, bass_fb)
    else:
        motif_override = None
        if mode == "rhythm":
            arc_row = arc(role=target_role)
            section_feel = _resolve_section_feel(target_role, preset, rng)
            hit_chance = _resolve_hit_chance(_BASE_HIT_CHANCE, arc_row["energy"])
            if hit_chance_bias:
                hit_chance = max(0.12, min(0.98, hit_chance + hit_chance_bias))
            duration_weights, no_singular_short = duration_bias_for_feel(section_feel)
            new_cell = generate_rhythm(
                total_beats, _ALLOWED_LENGTHS, hit_chance, rng,
                weights=duration_weights, no_singular_short=no_singular_short,
            )
            new_hits = sum(1 for c in new_cell if not c["is_rest"])
            new_deltas = _adapt_deltas(original["motif"].deltas, new_hits)
            motif_override = Motif(cell=new_cell, deltas=new_deltas)

        def _fresh_theme_source(key, *a, **kw):
            return generate_motif(*a, **kw)

        new_section, _kick_style, _blast_type = _generate_one_section(
            rng, preset, target_role, 0, scale, guitar_fb, bass_fb,
            total_beats, chromatic, None, _fresh_theme_source,
            hit_chance_bias=hit_chance_bias, motif_override=motif_override,
        )
        new_section["tempo_drop"] = original.get("tempo_drop")
        new_section.pop("_tempo_drop_trigger_beat", None)

    new_sections = list(song["sections"])
    new_sections[index] = new_section
    new_sequence = list(song["sequence"])
    new_sequence[index] = new_section["role"]

    for i in (index - 1, index):
        if not (0 <= i < len(new_sections) - 1):
            continue
        if i != index:
            new_sections[i] = dict(new_sections[i])  # real copy -- never mutate a shared neighbor dict
        this_section = new_sections[i]
        next_section = new_sections[i + 1]
        if this_section["role"] in ("chill", "interlude"):
            continue
        this_section["guitar_take_a"] = _pickup_cells(this_section["guitar_take_a"], next_section["guitar_take_a"])
        this_section["guitar_take_b"] = _pickup_cells(this_section["guitar_take_b"], next_section["guitar_take_b"])
        this_section["pitches_per_cell"] = _pickup_values(
            this_section["pitches_per_cell"], next_section["pitches_per_cell"]
        )
        this_section["synth_double"] = _pickup_values(
            this_section["synth_double"], next_section["synth_double"]
        )
        this_section["guitar_pedal"] = _pickup_cells(
            this_section["guitar_pedal"], next_section["guitar_pedal"]
        )
        this_section["pedal_pitches_per_cell"] = _pickup_values(
            this_section["pedal_pitches_per_cell"], next_section["pedal_pitches_per_cell"]
        )
        this_section["bass"] = follow_guitar_rhythm(
            this_section["guitar_take_a"], this_section["pitches_per_cell"], bass_fb
        )
        if this_section["role"] in _PINCH_HARMONIC_ROLES:
            this_section["guitar_take_a"] = _apply_pinch_harmonic_accent(this_section["guitar_take_a"])
            this_section["guitar_take_b"] = _apply_pinch_harmonic_accent(this_section["guitar_take_b"])

    guitar_track: list[dict] = []
    drum_track: list[dict] = []
    for section in new_sections:
        guitar_track.extend(section["guitar_take_a"])
        drum_track.extend(section["kick"])
    comp = {"guitar": guitar_track, "drums": drum_track}

    rearranged = dict(song)
    rearranged["sections"] = new_sections
    rearranged["sequence"] = new_sequence
    rearranged["judge"] = judge(comp)
    rearranged["_comp"] = comp
    return rearranged


def compose_song(
    preset_id: str,
    seed: int,
    num_sections: int = 6,
    max_seeds: int = 6,
    blast_fill_chance: float | None = None,
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
    return compose_song_from_preset(presets[resolved], seed, num_sections, max_seeds, blast_fill_chance)


def compose_song_from_preset(
    preset: Preset,
    seed: int,
    num_sections: int = 6,
    max_seeds: int = 6,
    blast_fill_chance: float | None = None,
) -> dict:
    """P9.2 -- the same real judge/retry loop `compose_song` uses, extracted
    so a caller with a real `Preset` OBJECT already in hand -- e.g. Guided
    Mode's `presets.blend_presets` output, which has no real preset id of
    its own -- doesn't need one. `compose_song` itself now just resolves
    `preset_id` and calls this.

    `blast_fill_chance`: real per-request override of the "blast-beat
    frequency" module default, threaded straight through to
    `_generate_attempt`. `None` reproduces the exact original behavior."""
    result = None
    for attempt in range(max_seeds):
        rng = random.Random(seed + attempt)
        result = _generate_attempt(rng, preset, num_sections, blast_fill_chance=blast_fill_chance)
        if result["judge"]["ok"]:
            break
    return result
