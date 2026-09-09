"""MIDI export (P10.1): a real, playable Standard MIDI File from a
composed song -- the file Reaper (Phase 8) actually imports.

Per CLAUDE.md's law ("Grid is the writer... Reaper renders"), this module
adds NO new note-choice logic. Every pitch/duration/velocity written here
was already chosen by `compose_song` (rhythm.py/motif.py/drums.py/bass.py/
riff.py/legato.py); this module only turns that already-real data into
real `mido` MIDI events on real tracks, using the real per-section tempo
from `song["tempo_map"]` (X.6c) -- never a flat, single-tempo file.

Tracks written: two double-tracked rhythm-guitar takes, bass (on its OWN
fretboard's real positions, per Phase 5), drums (the kick pattern actually
assembled into `song["_comp"]["drums"]`, i.e. exactly what `judge()` also
scored -- not a separately re-derived pattern -- PLUS the real per-role
snare backbeat from X.9's `drums.snare_pattern_for_role`, both sharing one
"Drums" track on the real GM percussion channel, standard practice for a
single drum-kit MIDI track), and the second-guitar lead voice. A dedicated
tempo track (track 0, no notes) carries the real `set_tempo` meta events
at each section boundary.

Lead-voice timing, and why it's exact (not fabricated):
  - `chill`/`interlude` sections (`lead_mode == "harmony"`, X.6b/P3.12):
    `riff.harmonize_line` renders its notes against the SAME rhythm
    motif's `.cell` as the guitar itself, one note per guitar HIT, in
    order -- so its timing is read directly from that section's own
    `guitar_take_a` cells, hit-for-hit. Not inferred.
  - `solo` sections (`lead_mode == "solo"`, X.6a): `song.py` requests
    `num_notes = round(total_beats * 2)` evenly-implied notes with no
    stored per-note duration -- there is no richer timing to read back,
    so this module places them at that exact even 8th-note spacing
    (`total_beats / num_notes == 0.5` beat, by that same arithmetic every
    solo line in this project already uses). The legato tail spliced onto
    a solo (X.6a's `generate_legato_lick`) DOES carry real per-note
    `cells` durations (`legato_run_rhythm`), used directly, appended right
    after the main phrase.
  - all other roles: `lead_mode == "silent"`, no lead events.

`section["fill"]` (vocabulary-informed blast fills) is intentionally NOT
exported here: `_generate_attempt` never actually blends it into the
song's assembled drum data (`drum_track` is built from `kick_cells` alone)
-- inventing a fill/kick blend in the exporter would be new arrangement
logic this project's own generation code doesn't define, not a wiring job.

Also written: a real sustained synth-pad track (`atmosphere.pad_voicing`,
GM "Pad 2 (warm)") spanning each section's full length, and a real
accent-hit track (`atmosphere.find_accents`' own per-accent
`stab_voicing`, GM "Orchestra Hit", landing exactly on each structurally-
accented cell -- scope sec.16.3's "a single orchestral hit landing
exactly on a structural accent") layered with `preset.octave_stab`'s real
`VoiceLeader.stab()` leap when a section has one (`section["octave_stabs"]`,
positionally zipped 1:1 with `section["accents"]` by `song.py`). Both were
real, computed, tested data since P7.1-P7.3 but were never wired into any
exported output until now -- found via a 2026-09-10 full scope re-read
(see TASKS.md's tracker).
"""
from __future__ import annotations

from pathlib import Path

try:
    import mido
except ImportError as exc:  # pragma: no cover - exercised only when mido is missing
    raise ImportError(
        "midi_export requires the 'mido' package. It is listed in "
        "engine/requirements.txt -- install with `pip install mido`."
    ) from exc

from atmosphere import ORCH_HIT_PROGRAM, PAD_PROGRAM
from chords import solve_chord
from drums import note_for_role
from fretboard import Fretboard

__all__ = ["song_to_midi"]

# X.23 -- real power chords on the main rhythm guitar. Confirmed via a
# whole-engine grep (same method that found X.19/X.20/X.21's gaps):
# `song.pitches_per_cell` returns exactly one pitch per hit, and every
# consumer (bass, this module, reaper_project.py) has been strictly
# monophonic all session -- the main riff has never played a real chord.
# Real, already-tested chord machinery already exists (`chords.solve_chord`,
# P1.11; `riff.voice_chord_section`, P3.11) but was only ever wired into
# chill/interlude's ambient `chord_quality` (X.6b), never the main chugging
# riff. `chord_vocab.py`'s own module docstring names this exact gap.
# `(0, 7)` is the minimal real power chord (root + 5th) -- not the fuller
# `(0, 7, 12)` triad, to avoid pushing a chord's upper tone into a
# thinner-sounding higher register on an already-low root; a real, easy
# follow-up if more fullness is wanted later.
_POWER_CHORD_INTERVALS = (0, 7)
_POWER_CHORD_MAX_SPAN = 4

# General MIDI program numbers (0-indexed, per mido/MIDI convention).
_GUITAR_PROGRAM = 30   # Distortion Guitar
_BASS_PROGRAM = 33     # Electric Bass (finger)
_LEAD_PROGRAM = 30     # Distortion Guitar -- same patch family as rhythm
_DRUM_CHANNEL = 9      # GM percussion channel (channel 10 in 1-indexed MIDI)
_GUITAR_A_CHANNEL = 0
_GUITAR_B_CHANNEL = 1
_BASS_CHANNEL = 2
_LEAD_CHANNEL = 3
_PAD_CHANNEL = 4
_ACCENT_CHANNEL = 5
_DEFAULT_VELOCITY = 100


def _section_beats(section: dict) -> float:
    """A section's real length in beats, read directly from its own
    already-generated rhythm cells (`guitar_take_a`'s duration sum) --
    `song`'s dict never stores the source `Preset` object, so this is the
    real total, not a re-derivation from preset internals this module
    doesn't have."""
    return sum(c["duration"] for c in section["guitar_take_a"])


def _beats_to_ticks(beats: float, ppq: int) -> int:
    return round(beats * ppq)


def _cell_events(
    cells: list[dict],
    pitches: list[int | None],
    start_beat: float,
    ppq: int,
) -> list[tuple[int, int, int, int]]:
    """`(on_tick, off_tick, pitch, velocity)` events for one cell sequence
    (one dict per SLOT; `is_rest` true on rests) paired with a same-length
    parallel `pitches` list (`None` on rests). Honors each cell's own
    `timing_offset` (humanization, in beats) and `velocity` when present
    (double-tracked guitar takes carry both); falls back to
    `_DEFAULT_VELOCITY` and zero offset for cell shapes that don't
    (bass/lead cells).
    """
    if len(cells) != len(pitches):
        raise ValueError("cells and pitches must be the same length")
    events: list[tuple[int, int, int, int]] = []
    t = start_beat
    for cell, pitch in zip(cells, pitches):
        duration = cell["duration"]
        if not cell["is_rest"] and pitch is not None:
            offset = cell.get("timing_offset", 0.0)
            velocity = cell.get("velocity") or _DEFAULT_VELOCITY
            on_tick = _beats_to_ticks(t + offset, ppq)
            off_tick = _beats_to_ticks(t + offset + duration, ppq)
            events.append((max(0, on_tick), max(on_tick + 1, off_tick), pitch, velocity))
        t += duration
    return events


def _guitar_chord_tone_pitches(
    fretboard: Fretboard,
    root: int,
    intervals: tuple[int, ...] = _POWER_CHORD_INTERVALS,
    max_span: int = _POWER_CHORD_MAX_SPAN,
) -> list[int]:
    """Real power-chord tones for one already-chosen root pitch: calls
    `chords.solve_chord` (ground-up fretboard fingering solver, no lookup
    tables) and picks the lowest-position fingering -- the same real
    tie-break `riff.voice_chord_section` uses. Falls back to `[root]` alone
    (never fabricates a shape, never raises) if no real `(string, fret)`
    fingering is reachable for this root at `max_span` -- rare, but a
    single note beats a crashed export."""
    fingerings = solve_chord(root, intervals, fretboard, max_span=max_span)
    if not fingerings:
        return [root]
    best = min(fingerings, key=lambda fingering: sum(fret for _string, fret in fingering))
    return [fretboard.fret_to_midi(string, fret) for string, fret in best]


def _chord_cell_events(
    cells: list[dict],
    pitches: list[int | None],
    start_beat: float,
    ppq: int,
    fretboard: Fretboard,
) -> list[tuple[int, int, int, int]]:
    """Real power-chord version of `_cell_events`: identical on/off-tick
    and velocity logic, but each real hit emits one event PER CHORD TONE
    (`_guitar_chord_tone_pitches`) instead of a single note -- the main
    rhythm guitar's real per-hit pitch movement (vocab-weighted intervals,
    pedal bias) is untouched, only how each already-chosen root gets
    voiced when written out."""
    if len(cells) != len(pitches):
        raise ValueError("cells and pitches must be the same length")
    events: list[tuple[int, int, int, int]] = []
    t = start_beat
    for cell, pitch in zip(cells, pitches):
        duration = cell["duration"]
        if not cell["is_rest"] and pitch is not None:
            offset = cell.get("timing_offset", 0.0)
            velocity = cell.get("velocity") or _DEFAULT_VELOCITY
            on_tick = max(0, _beats_to_ticks(t + offset, ppq))
            off_tick = max(on_tick + 1, _beats_to_ticks(t + offset + duration, ppq))
            for tone in _guitar_chord_tone_pitches(fretboard, pitch):
                events.append((on_tick, off_tick, tone, velocity))
        t += duration
    return events


# X.23 -- roles whose main riff gets real power-chord thickening. Excludes
# chill/interlude, matching the established real precedent (kick/snare/
# hihat all already go quiet/sparse for those two atmospheric roles,
# X.9/X.11/X.22) -- their already-real melodic/harmony character
# (`riff.harmonize_line`) should stay single-note, not get chugged up.
# X.31 -- "chorus" added: real power chords, same real device Metalerator's
# own RGuitarChorus uses (root+5th+octave on quarter notes). Not "verse":
# Metalerator's verse riff is real single-note pedal tone, not chorded.
_CHORD_THICKENED_ROLES = frozenset({"intro", "breakdown", "build", "outro", "solo", "chorus"})


def _lead_events_for_section(section: dict, start_beat: float, ppq: int) -> list[tuple[int, int, int, int]]:
    """Real lead-voice events for one section -- see this module's
    docstring for exactly how each `lead_mode` maps to timing."""
    mode = section["lead_mode"]
    if mode == "silent":
        return []

    if mode == "harmony":
        # One lead note per guitar HIT, in order -- riff.harmonize_line's
        # own contract (see module docstring). Rebuild a per-CELL pitch
        # list aligned to guitar_take_a, same technique as
        # song.pitches_per_cell.
        take_a = section["guitar_take_a"]
        hit_pitches = iter(section["lead"])
        per_cell = [None if c["is_rest"] else next(hit_pitches) for c in take_a]
        return _cell_events(take_a, per_cell, start_beat, ppq)

    if mode in ("solo", "chorus_lead"):
        # X.31: chorus_lead reuses the exact same even-8th-note timing as
        # solo's main phrase -- `legato` is always None for chorus_lead
        # (song.py never splices one), which this branch already handles
        # gracefully (empty legato_pitches/legato_cells).
        legato = section["legato"]
        legato_pitches = legato["pitches"] if legato else []
        legato_cells = legato["cells"] if legato else []
        main_count = len(section["lead"]) - len(legato_pitches)
        main_pitches = section["lead"][:main_count]

        events: list[tuple[int, int, int, int]] = []
        t = start_beat
        # Main phrase: even 8th-note spacing -- exact given how song.py
        # derived this many notes in the first place (see module
        # docstring), not an approximation.
        for pitch in main_pitches:
            on_tick = _beats_to_ticks(t, ppq)
            off_tick = _beats_to_ticks(t + 0.5, ppq)
            events.append((on_tick, max(on_tick + 1, off_tick), pitch, _DEFAULT_VELOCITY))
            t += 0.5
        # Legato tail: real per-note durations from legato_run_rhythm.
        for pitch, cell in zip(legato_pitches, legato_cells):
            duration = cell["duration"]
            if not cell["is_rest"]:
                on_tick = _beats_to_ticks(t, ppq)
                off_tick = _beats_to_ticks(t + duration, ppq)
                events.append((on_tick, max(on_tick + 1, off_tick), pitch, _DEFAULT_VELOCITY))
            t += duration
        return events

    raise ValueError(f"unknown lead_mode: {mode!r}")


def _pad_events_for_section(
    section: dict, start_beat: float, section_beats: float, ppq: int
) -> list[tuple[int, int, int, int]]:
    """Real sustained pad-chord events for one section: `section["pad"]`
    (`atmosphere.pad_voicing`, a real 3-note chord) held for the section's
    entire real length -- one note-on/off pair per chord tone, all
    sharing the section's own start/end ticks. `section.get("pad")` is
    never missing on a real `compose_song`/`regenerate_section` result
    (every role gets one, chill/interlude included -- an ambient pad
    suits them especially), but the empty-list fallback keeps this
    honestly defensive against a malformed/hand-built section dict rather
    than assuming."""
    pad = section.get("pad") or []
    on_tick = _beats_to_ticks(start_beat, ppq)
    off_tick = max(on_tick + 1, _beats_to_ticks(start_beat + section_beats, ppq))
    return [(on_tick, off_tick, pitch, _DEFAULT_VELOCITY) for pitch in pad]


def _accent_events_for_section(section: dict, start_beat: float, ppq: int) -> list[tuple[int, int, int, int]]:
    """Real accent-hit events for one section: one short chord per
    structurally-accented cell (`section["accents"]`, `atmosphere.
    find_accents`' own per-accent `stab_voicing` -- scope sec.16.3's "a
    single orchestral hit landing exactly on a structural accent"),
    landing at that accent's own real cell position/duration within
    `guitar_take_a` (accent `cell_index` values are computed against the
    pre-double-tracked cell list, which `performance.double_track`
    preserves index-for-index -- same real alignment P9.6's tab export
    already relies on). When `preset.octave_stab` was true for this
    section, `section["octave_stabs"]` (real `theory.VoiceLeader.stab()`
    leaps, positionally zipped 1:1 with `accents` by `song.py`) layers
    that accent's own wide-leap note into the SAME event rather than a
    separate track, since it's already generated one-per-accent, not an
    independent stream.

    Fails closed on an accent whose `cell_index` doesn't fit the current
    `guitar_take_a` (never actually produced by real `compose_song`/
    `regenerate_section` output -- accents/pad/octave_stabs are always
    recomputed together with a fresh cell list whenever the rhythm
    changes -- but this module doesn't assume a section dict it's handed
    is necessarily one of those) rather than raising or misplacing a
    note."""
    accents = section.get("accents") or []
    if not accents:
        return []
    cells = section["guitar_take_a"]
    octave_stabs = section.get("octave_stabs") or []

    offsets: list[float] = []
    t = 0.0
    for cell in cells:
        offsets.append(t)
        t += cell["duration"]

    events: list[tuple[int, int, int, int]] = []
    for i, accent in enumerate(accents):
        idx = accent["cell_index"]
        if not (0 <= idx < len(cells)):
            continue
        cell_start = start_beat + offsets[idx]
        cell_duration = cells[idx]["duration"]
        on_tick = _beats_to_ticks(cell_start, ppq)
        off_tick = max(on_tick + 1, _beats_to_ticks(cell_start + cell_duration, ppq))
        pitches = list(accent["voicing"])
        if i < len(octave_stabs):
            pitches.append(octave_stabs[i])
        events += [(on_tick, off_tick, pitch, _DEFAULT_VELOCITY) for pitch in pitches]
    return events


def _events_to_track(
    events: list[tuple[int, int, int, int]],
    channel: int,
    program: int | None,
    name: str,
) -> "mido.MidiTrack":
    """Real `mido.MidiTrack` from absolute-tick `(on, off, pitch,
    velocity)` events: a `track_name` meta message, an optional
    `program_change`, then note on/off pairs converted to the delta-time
    encoding a Standard MIDI File requires. Off-events are ordered before
    on-events at the same tick so a note never appears to overlap itself.
    """
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    if program is not None:
        track.append(mido.Message("program_change", program=program, channel=channel, time=0))

    # (tick, is_off, pitch, velocity) -- is_off=0 sorts note_off (priority
    # 0) before note_on (priority 1) at an identical tick.
    msgs = []
    for on_tick, off_tick, pitch, velocity in events:
        msgs.append((on_tick, 1, pitch, velocity))
        msgs.append((off_tick, 0, pitch, 0))
    msgs.sort(key=lambda m: (m[0], m[1]))

    last_tick = 0
    for tick, is_on, pitch, velocity in msgs:
        delta = max(0, tick - last_tick)
        kind = "note_on" if is_on else "note_off"
        track.append(mido.Message(kind, note=pitch, velocity=velocity, channel=channel, time=delta))
        last_tick = tick
    return track


def _tempo_track(song: dict, ppq: int) -> "mido.MidiTrack":
    """Real tempo-map track (X.6c): one `set_tempo` meta event at the
    start of each section, at that section's real cumulative start tick,
    scaled to `song["tempo_map"]`'s real per-section BPM -- never a flat,
    single-tempo assumption. Plus (X.18) a real SECOND `set_tempo` event
    partway through any section carrying a `tempo_drop` (a mid-section
    half-time slam moment, distinct from the per-section value above) --
    note tick positions elsewhere are unaffected, since MIDI ticks are
    beat-based, not time-based; only this tempo track gains an extra
    point."""
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="Tempo Map", time=0))

    events = []
    start_beat = 0.0
    for section, bpm in zip(song["sections"], song["tempo_map"]):
        tick = _beats_to_ticks(start_beat, ppq)
        events.append((tick, mido.bpm2tempo(bpm)))
        drop = section.get("tempo_drop")
        if drop is not None:
            drop_tick = _beats_to_ticks(start_beat + drop["trigger_beat"], ppq)
            events.append((drop_tick, mido.bpm2tempo(drop["bpm"])))
        start_beat += _section_beats(section)

    last_tick = 0
    for tick, tempo in events:
        delta = max(0, tick - last_tick)
        track.append(mido.MetaMessage("set_tempo", tempo=tempo, time=delta))
        last_tick = tick
    return track


def song_to_midi(song: dict, path: str | Path, ppq: int = 480) -> None:
    """Write `song` (a real `song.compose_song(...)` result) to a
    Standard MIDI File at `path`.

    Raises `ValueError` if `ppq` isn't a positive integer, or if `song`'s
    own `tempo_map`/`sections` are inconsistent lengths (a malformed song
    dict, not a real `compose_song` result) -- fails closed rather than
    writing a file with an undefined tempo somewhere in it.
    """
    if ppq <= 0:
        raise ValueError(f"ppq must be > 0, got {ppq!r}")
    if len(song["tempo_map"]) != len(song["sections"]):
        raise ValueError(
            f"tempo_map length ({len(song['tempo_map'])}) must match "
            f"sections length ({len(song['sections'])})"
        )

    guitar_a_events: list[tuple[int, int, int, int]] = []
    guitar_b_events: list[tuple[int, int, int, int]] = []
    bass_events: list[tuple[int, int, int, int]] = []
    drum_events: list[tuple[int, int, int, int]] = []
    lead_events: list[tuple[int, int, int, int]] = []
    pad_events: list[tuple[int, int, int, int]] = []
    accent_events: list[tuple[int, int, int, int]] = []

    guitar_fb = song["guitar_fretboard"]
    start_beat = 0.0
    for section in song["sections"]:
        if section["role"] in _CHORD_THICKENED_ROLES:
            guitar_a_events += _chord_cell_events(
                section["guitar_take_a"], section["pitches_per_cell"], start_beat, ppq, guitar_fb
            )
            guitar_b_events += _chord_cell_events(
                section["guitar_take_b"], section["pitches_per_cell"], start_beat, ppq, guitar_fb
            )
        else:
            guitar_a_events += _cell_events(
                section["guitar_take_a"], section["pitches_per_cell"], start_beat, ppq
            )
            guitar_b_events += _cell_events(
                section["guitar_take_b"], section["pitches_per_cell"], start_beat, ppq
            )
        bass_events += _cell_events(
            section["bass"], [c["midi"] for c in section["bass"]], start_beat, ppq
        )
        kick_pitches = [None if c["is_rest"] else note_for_role(c["role"]) for c in section["kick"]]
        drum_events += _cell_events(section["kick"], kick_pitches, start_beat, ppq)
        snare_pitches = [None if c["is_rest"] else note_for_role(c["role"]) for c in section["snare"]]
        drum_events += _cell_events(section["snare"], snare_pitches, start_beat, ppq)
        hihat_pitches = [None if c["is_rest"] else note_for_role(c["role"]) for c in section["hihat"]]
        drum_events += _cell_events(section["hihat"], hihat_pitches, start_beat, ppq)
        lead_events += _lead_events_for_section(section, start_beat, ppq)
        section_beats = _section_beats(section)
        pad_events += _pad_events_for_section(section, start_beat, section_beats, ppq)
        accent_events += _accent_events_for_section(section, start_beat, ppq)
        start_beat += section_beats

    midi_file = mido.MidiFile(type=1, ticks_per_beat=ppq)
    midi_file.tracks.append(_tempo_track(song, ppq))
    midi_file.tracks.append(
        _events_to_track(guitar_a_events, _GUITAR_A_CHANNEL, _GUITAR_PROGRAM, "Guitar (Take A)")
    )
    midi_file.tracks.append(
        _events_to_track(guitar_b_events, _GUITAR_B_CHANNEL, _GUITAR_PROGRAM, "Guitar (Take B)")
    )
    midi_file.tracks.append(_events_to_track(bass_events, _BASS_CHANNEL, _BASS_PROGRAM, "Bass"))
    midi_file.tracks.append(_events_to_track(lead_events, _LEAD_CHANNEL, _LEAD_PROGRAM, "Lead"))
    midi_file.tracks.append(_events_to_track(drum_events, _DRUM_CHANNEL, None, "Drums"))
    midi_file.tracks.append(_events_to_track(pad_events, _PAD_CHANNEL, PAD_PROGRAM, "Pad"))
    midi_file.tracks.append(_events_to_track(accent_events, _ACCENT_CHANNEL, ORCH_HIT_PROGRAM, "Accents"))

    midi_file.save(str(path))
