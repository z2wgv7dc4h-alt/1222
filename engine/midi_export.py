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

from drums import note_for_role

__all__ = ["song_to_midi"]

# General MIDI program numbers (0-indexed, per mido/MIDI convention).
_GUITAR_PROGRAM = 30   # Distortion Guitar
_BASS_PROGRAM = 33     # Electric Bass (finger)
_LEAD_PROGRAM = 30     # Distortion Guitar -- same patch family as rhythm
_DRUM_CHANNEL = 9      # GM percussion channel (channel 10 in 1-indexed MIDI)
_GUITAR_A_CHANNEL = 0
_GUITAR_B_CHANNEL = 1
_BASS_CHANNEL = 2
_LEAD_CHANNEL = 3
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

    if mode == "solo":
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
    single-tempo assumption."""
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="Tempo Map", time=0))

    events = []
    start_beat = 0.0
    for section, bpm in zip(song["sections"], song["tempo_map"]):
        tick = _beats_to_ticks(start_beat, ppq)
        events.append((tick, mido.bpm2tempo(bpm)))
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

    start_beat = 0.0
    for section in song["sections"]:
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
        start_beat += _section_beats(section)

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

    midi_file.save(str(path))
