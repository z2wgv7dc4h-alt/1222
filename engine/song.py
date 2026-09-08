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
    `rng`) via `drums.kick_pattern_for_role`, regardless of what the
    preset otherwise declares -- direct answer to real listening
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

from atmosphere import find_accents, pad_voicing
from bass import build_bass_fretboard, follow_guitar_rhythm
from chord_vocab import quality_for_dissonance, voice_named_chord
from drums import (
    RhythmRegistry,
    add_transition_crash,
    apply_hihat_accents,
    generate_vocabulary_informed_blast_fill,
    hihat_pattern_for_role,
    kick_pattern_for_role,
    snare_pattern_for_role,
)
from fretboard import Fretboard
from lead import generate_lead_line
from legato import generate_legato_lick
from metric_modulation import apply_metric_modulation, modulation_ratio
from motif import Motif, ThemeRegistry, invert, render_motif, transpose
from performance import double_track
from presets import Preset, get_tuning, load_all_presets, load_tunings, resolve_preset_id
from riff import harmonize_line
from structure import generate_section_sequence, judge, tempo_at
from theory import Scale, VoiceLeader, arc

__all__ = ["compose_song", "pitches_per_cell"]

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


def _compute_tempo_map(sequence: list[str], base_bpm: float) -> list[float]:
    """Per-section effective BPM for every section in `sequence`: the
    preset's own real `base_bpm` for every role, EXCEPT "breakdown",
    which independently gets the real metric-modulation-scaled half-time
    tempo (X.6c) every time it occurs -- computed via `structure.
    tempo_at`'s `"metric_modulation"` curve for that one section (`at`
    equal to the section's own index, so the curve's own "hold base_bpm
    before `at`" branch never applies), never a separate parallel
    calculation that skips that dispatch path.
    """
    tempos: list[float] = []
    for i, role in enumerate(sequence):
        if role != "breakdown":
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


# X.14 -- real listening feedback ("not much is going on") traced to a
# real architectural limitation: ThemeRegistry keys a base theme by ROLE
# ALONE, so every occurrence of that role for the WHOLE SONG reused just
# one of two pitch contours (base, or invert() -- alternating). A longer
# song revisiting a role many times (real for any longer song) heard the
# same 2 states over and over, no matter how many times the role recurred.
# `motif.transpose`/`motif.invert` already existed, fully real and tested,
# but only `invert` was ever wired into this rotation.
def _develop_theme(base_theme: Motif, occurrence: int) -> Motif:
    """Real per-occurrence development for a reused role theme: a 4-state
    rotation using ONLY safe, length-preserving develop ops (`transpose`/
    `invert` touch pitch deltas alone, never rhythm cell count or
    duration, so every downstream section-length/timing invariant this
    file depends on stays untouched):

      0: base theme, unchanged
      1: `invert(base)` -- contour mirrored around the anchor
      2: `transpose(base, +2 degrees)` -- a real diatonic-third "repeat
         and lift", a standard real songwriting development move
      3: `transpose(invert(base), +2 degrees)` -- both combined

    Quadruples real pitch-content variety per role compared to the
    previous 2-state (base/invert-only) rotation.
    """
    state = occurrence % 4
    if state == 0:
        return base_theme
    if state == 1:
        return invert(base_theme)
    if state == 2:
        return transpose(base_theme, _THEME_DEVELOP_TRANSPOSE_DEGREES)
    return transpose(invert(base_theme), _THEME_DEVELOP_TRANSPOSE_DEGREES)


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
    previous_role: str | None = None

    for idx, role in enumerate(sequence):
        arc_row = arc(role=role)
        occurrence = role_occurrences.get(role, 0)
        role_occurrences[role] = occurrence + 1

        base_theme = themes.get_or_create(
            f"theme-{role}", total_beats, _ALLOWED_LENGTHS, preset.open_chance,
            rng, scale, preset.vocab.weights, chromatic=chromatic,
            dissonance=arc_row["dissonance"],
            base_degree=arc_row["start_degree"],
            group_beats=(float(preset.group) if preset.group is not None else None),
            pedal=preset.pedal,
            feel=preset.feel,
            # X.19 -- real IRVD phrase development (bar-by-bar
            # intro/repeat/vary/destroy shape) for every preset EXCEPT
            # djent/progressive, whose real `group_beats` polymeter tiling
            # is a different, already-real "something happens across the
            # section" device that IRVD's verbatim-repeat structure would
            # directly fight (see motif.generate_motif's docstring).
            irvd_bars=(preset.bars if preset.group is None else None),
        )
        m: Motif = _develop_theme(base_theme, occurrence)
        guitar_cells = m.cell
        cell_pitches = [
            (None if p is None else _snap_to_playable_octave(guitar_fb, p))
            for p in pitches_per_cell(m, scale, start_degree=arc_row["start_degree"])
        ]

        seed_a, seed_b = _two_child_seeds(rng)
        take_a, take_b = double_track(
            guitar_cells, random.Random(seed_a), random.Random(seed_b)
        )

        kick_cells = kick_pattern_for_role(guitar_cells, role, preset.kick, rng=rng)
        snare_cells = snare_pattern_for_role(guitar_cells, role)
        hihat_cells = hihat_pattern_for_role(guitar_cells, role)

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
        previous_role = role

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
            # Dense chug sections (intro/build/breakdown/outro): a busy
            # independent lead would just clash with the rhythm here --
            # real arrangements leave the second guitar out (or doubling
            # the riff, already covered by the double-tracked pair) rather
            # than noodling a melody over a breakdown. Silent, not a
            # fabricated part filling space it doesn't belong in.
            lead_mode = "silent"
            lead_notes = []
            legato = None

        # X.18: real mid-section half-time drop trigger -- see module-level
        # docstring above `_resolve_tempo_drop`. Only the TRIGGER BEAT is
        # decided here (needs this section's own seeded `rng` and
        # `preset.bars`); the actual dropped BPM is resolved after
        # `tempo_map` exists below, since it scales THIS section's own
        # already-computed tempo, not `preset.bpm` directly.
        tempo_drop_trigger_beat: float | None = None
        if (
            role in _TEMPO_DROP_ROLES
            and preset.bars >= _TEMPO_DROP_MIN_BARS
            and rng.random() < _TEMPO_DROP_CHANCE
        ):
            tempo_drop_trigger_beat = total_beats - _TEMPO_DROP_TAIL_BARS * _BEATS_PER_BAR

        sections.append({
            "role": role,
            "arc": arc_row,
            "motif": m,
            "pitches_per_cell": cell_pitches,
            "guitar_take_a": take_a,
            "guitar_take_b": take_b,
            "lead_mode": lead_mode,
            "lead": lead_notes,
            "legato": legato,
            "kick": kick_cells,
            "snare": snare_cells,
            "hihat": hihat_cells,
            "fill": fill,
            "bass": bass_cells,
            "pad": pad,
            "accents": accents,
            "octave_stabs": octave_stabs,
            "chord_quality": chord_quality,
            "chord_voicing": chord_voicing,
            "_tempo_drop_trigger_beat": tempo_drop_trigger_beat,
        })

        guitar_track.extend(take_a)
        drum_track.extend(kick_cells)

    tempo_map = _compute_tempo_map(sequence, preset.bpm)
    for section, bpm in zip(sections, tempo_map):
        section["tempo_drop"] = _resolve_tempo_drop(bpm, section.pop("_tempo_drop_trigger_beat"))

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
