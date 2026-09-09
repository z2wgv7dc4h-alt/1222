"""Real Reaper `.rpp` project-file export (Phase 8, headless): a complete,
directly-openable Reaper project built from a composed song, entirely
offline -- no live `reapy` connection, no Reaper process, no socket.

Per the user's own explicit requirement ("all being done in the background
... I'm not running Reaper myself"), this sidesteps the live-bridge
approach investigated first (`reapy`/`reapy-boost`): that path hit a real,
reproducible connection bug in this environment that needed console
access to diagnose. Verified with the user directly (2026-09-08) that
nothing Phase 8 actually needs -- project assembly, FX chains, tempo
automation, and rendering to audio (REAPER's real `-renderproject` CLI
flag) -- requires a live connection; all of it is expressible as a static
project file REAPER opens/renders on its own.

The `.rpp` text format below is NOT guessed. It was reverse-engineered
from a real, ground-truth file: this project's own `midi_export.
song_to_midi` output, imported into a real, currently-installed REAPER
7.79 via `reaper.exe -new file.mid -saveas out.rpp`, then read back and
compared field-by-field (project header, `<TRACK>`, `<ITEM>`,
`<SOURCE MIDI>`, and the `<X ...>` track-name meta-event block, which
decodes to the exact standard MIDI "sequence/track name" meta-event
`0xFF 0x03 <name bytes>` -- confirmed by base64-decoding it directly, not
assumed). Every fixed field below (`PEAKCOL`, `AUTOMODE`, `FIXEDLANES`,
etc.) is REAPER's own real default, copied from that ground-truth file,
not invented.

Reuses `midi_export`'s already-real event-extraction functions
(`_cell_events`/`_lead_events_for_section`/`_section_beats`/
`_pad_events_for_section`/`_accent_events_for_section`) rather than
re-deriving per-track note/timing data a second time -- one source of
truth for "what notes are in this song," two serializers (Standard MIDI
File, and this real Reaper project format) on top of it.
"""
from __future__ import annotations

import base64
import uuid
from pathlib import Path

from midi_export import (
    _ACCENT_CHANNEL,
    _BASS_CHANNEL,
    _BASS_PROGRAM,
    _CHORD_THICKENED_ROLES,
    _DRUM_CHANNEL,
    _GUITAR_A_CHANNEL,
    _GUITAR_B_CHANNEL,
    _GUITAR_PROGRAM,
    _LEAD_CHANNEL,
    _LEAD_PROGRAM,
    _PAD_CHANNEL,
    _accent_events_for_section,
    _beats_to_ticks,
    _cell_events,
    _chord_cell_events,
    _lead_events_for_section,
    _pad_events_for_section,
    _section_beats,
)
from drums import note_for_role

__all__ = ["song_to_rpp"]

_PPQ = 480


def _new_guid() -> str:
    """A real Reaper-format GUID: `{UPPERCASE-UUID}`, matching every GUID
    field observed in the ground-truth file exactly (braces included)."""
    return "{" + str(uuid.uuid4()).upper() + "}"


def _name_meta_x_block(name: str, indent: str) -> list[str]:
    """The real `<X ...>` track-name meta-event block Reaper writes for
    every MIDI item's name -- verified by base64-decoding a real one
    (`/wNHdWl0YXIgKFRha2UgQSk=` -> `b'\\xff\\x03Guitar (Take A)'`, the
    standard MIDI sequence/track-name meta-event, byte for byte)."""
    payload = base64.b64encode(b"\xff\x03" + name.encode("ascii", "replace")).decode()
    return [
        f'{indent}<X 0 0 0 0 3 "{name}"',
        f"{indent}  {payload}",
        f"{indent}>",
    ]


def _events_to_e_lines(events: list[tuple[int, int, int, int]], channel: int, indent: str) -> list[str]:
    """Real Reaper `E <delta_ticks> <hex_status> <hex_data1> <hex_data2>`
    MIDI-event lines -- verified against a real ground-truth `<SOURCE
    MIDI>` block (plain delta-time hex text, not an opaque binary blob).
    Same on/off ordering-at-equal-tick convention as `midi_export.
    _events_to_track` (note_off before note_on), so a coincident
    off/on pair never reads as overlapping."""
    msgs: list[tuple[int, int, int, int]] = []
    for on_tick, off_tick, pitch, velocity in events:
        msgs.append((on_tick, 1, pitch, velocity))
        msgs.append((off_tick, 0, pitch, 0))
    msgs.sort(key=lambda m: (m[0], m[1]))

    lines = []
    last_tick = 0
    for tick, is_on, pitch, velocity in msgs:
        delta = max(0, tick - last_tick)
        status = (0x90 if is_on else 0x80) | (channel & 0x0F)
        lines.append(f"{indent}E {delta} {status:02x} {pitch:02x} {velocity:02x}")
        last_tick = tick
    # Real trailing "all notes off" CC event every ground-truth SOURCE MIDI
    # block ends with (channel 0, controller 123) -- a housekeeping event,
    # copied as-is rather than invented.
    lines.append(f"{indent}E 0 b0 7b 00")
    return lines


def _source_midi_block(
    events: list[tuple[int, int, int, int]], channel: int, name: str
) -> list[str]:
    lines = [
        "      <SOURCE MIDI",
        f"        HASDATA 1 {_PPQ} QN",
        "        CCINTERP 32",
        f"        POOLEDEVTS {_new_guid()}",
    ]
    lines += _name_meta_x_block(name, "        ")
    lines += _events_to_e_lines(events, channel, "        ")
    lines += [
        "        CCINTERP 32",
        "        CHASE_CC_TAKEOFFS 1",
        f"        GUID {_new_guid()}",
        "        IGNTEMPO 0 120 4 4",
        "        SRCCOLOR 5",
        "        EVTFILTER 0 -1 -1 -1 -1 0 0 0 0 -1 -1 -1 -1 0 -1 0 -1 -1",
        "      >",
    ]
    return lines


def _track_block(
    name: str,
    channel: int,
    events: list[tuple[int, int, int, int]],
    length_seconds: float,
    item_id: int,
) -> list[str]:
    track_guid = _new_guid()
    lines = [
        f"  <TRACK {track_guid}",
        f'    NAME "{name}"',
        "    PEAKCOL 16576",
        "    BEAT -1",
        "    AUTOMODE 0",
        "    PANLAWFLAGS 3",
        "    VOLPAN 1 0 -1 -1 1",
        "    MUTESOLO 0 0 0",
        "    IPHASE 0",
        "    PLAYOFFS 0 1",
        "    ISBUS 0 0",
        "    BUSCOMP 0 0 0 0 0",
        "    SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0 0",
        "    FIXEDLANES 9 0 0 0 0",
        "    SEL 0",
        "    REC 0 0 1 0 0 0 0 0",
        "    VU 64",
        "    TRACKHEIGHT 0 0 0 0 0 0 0",
        "    INQ 0 0 0 0.5 100 0 0 100",
        "    NCHAN 2",
        "    FX 1",
        f"    TRACKID {track_guid}",
        "    PERF 0",
        "    MIDIOUT -1 -1",
        "    MAINSEND 1 0",
        "    <ITEM",
        "      POSITION 0",
        "      SNAPOFFS 0",
        f"      LENGTH {length_seconds:.6f}",
        "      LOOP 1",
        "      ALLTAKES 0",
        "      FADEIN 1 0 0 1 0 0 0",
        "      FADEOUT 1 0 0 1 0 0 0",
        "      MUTE 0 0",
        "      SEL 1",
        f"      IGUID {_new_guid()}",
        f"      IID {item_id}",
        f'      NAME "{name}"',
        "      VOLPAN 1 0 1 -1",
        "      SOFFS 0 0",
        "      PLAYRATE 1 1 0 -1 0 0.0025",
        "      CHANMODE 0",
        f"      GUID {_new_guid()}",
    ]
    lines += _source_midi_block(events, channel, name)
    lines += ["    >", "  >"]
    return lines


def _tempo_envelope_block(points: list[tuple[float, float]]) -> list[str]:
    """Real `<TEMPOENVEX>` points at real cumulative time (seconds) and
    real bpm -- verified against the ground-truth file's own points, which
    land at exactly `section_beats * 60 / bpm` from each other, confirming
    `PT`'s time field is seconds, not beats. `points` is already flattened
    and in order: one per section (X.6c's `tempo_map`) PLUS one real extra
    point for any section carrying a mid-section `tempo_drop` (X.18) --
    this function itself doesn't know or care which points came from
    where, it just emits them."""
    lines = [
        "  <TEMPOENVEX",
        f"    EGUID {_new_guid()}",
        "    ACT 1 -1",
        "    VIS 1 0 1",
        "    LANEHEIGHT 0 0",
        "    ARM 0",
        "    DEFSHAPE 1 -1 -1",
    ]
    for i, (t, bpm) in enumerate(points):
        if i == 0:
            lines.append(f"    PT {t:.12f} {bpm:.10f} 1 262148 0 1 0 \"\" 0 0 0 ")
        else:
            lines.append(f"    PT {t:.12f} {bpm:.10f} 1")
    lines.append("  >")
    return lines


def song_to_rpp(song: dict, path: str | Path) -> None:
    """Write `song` (a real `song.compose_song(...)` result) to a real,
    directly-openable Reaper `.rpp` project file at `path` -- no live
    Reaper connection needed to write it, or to open/render it later.

    Raises `ValueError` on the same malformed-song cases `midi_export.
    song_to_midi` rejects (mismatched `tempo_map`/`sections` length) --
    fails closed rather than writing a project with an undefined tempo.
    """
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

    section_start_beats: list[float] = []
    section_start_seconds: list[float] = []
    tempo_points: list[tuple[float, float]] = []
    guitar_fb = song["guitar_fretboard"]
    start_beat = 0.0
    start_seconds = 0.0
    for section, bpm in zip(song["sections"], song["tempo_map"]):
        section_start_beats.append(start_beat)
        section_start_seconds.append(start_seconds)
        tempo_points.append((start_seconds, bpm))

        if section["role"] in _CHORD_THICKENED_ROLES:
            guitar_a_events += _chord_cell_events(
                section["guitar_take_a"], section["pitches_per_cell"], start_beat, _PPQ, guitar_fb
            )
            guitar_b_events += _chord_cell_events(
                section["guitar_take_b"], section["pitches_per_cell"], start_beat, _PPQ, guitar_fb
            )
        else:
            guitar_a_events += _cell_events(
                section["guitar_take_a"], section["pitches_per_cell"], start_beat, _PPQ
            )
            guitar_b_events += _cell_events(
                section["guitar_take_b"], section["pitches_per_cell"], start_beat, _PPQ
            )
        bass_events += _cell_events(
            section["bass"], [c["midi"] for c in section["bass"]], start_beat, _PPQ
        )
        kick_pitches = [None if c["is_rest"] else note_for_role(c["role"]) for c in section["kick"]]
        drum_events += _cell_events(section["kick"], kick_pitches, start_beat, _PPQ)
        snare_pitches = [None if c["is_rest"] else note_for_role(c["role"]) for c in section["snare"]]
        drum_events += _cell_events(section["snare"], snare_pitches, start_beat, _PPQ)
        hihat_pitches = [None if c["is_rest"] else note_for_role(c["role"]) for c in section["hihat"]]
        drum_events += _cell_events(section["hihat"], hihat_pitches, start_beat, _PPQ)
        lead_events += _lead_events_for_section(section, start_beat, _PPQ)

        beats = _section_beats(section)
        pad_events += _pad_events_for_section(section, start_beat, beats, _PPQ)
        accent_events += _accent_events_for_section(section, start_beat, _PPQ)
        start_beat += beats
        # X.18: a section with a mid-section `tempo_drop` spends its real
        # elapsed time in two parts -- the portion before the trigger at
        # this section's own `bpm`, and the remainder at the dropped bpm --
        # so every LATER section's start time still lands correctly in
        # real time (not just this section's own drop point).
        drop = section.get("tempo_drop")
        if drop is not None:
            trigger_beat = drop["trigger_beat"]
            drop_seconds = start_seconds + trigger_beat * 60.0 / bpm
            tempo_points.append((drop_seconds, drop["bpm"]))
            start_seconds = drop_seconds + (beats - trigger_beat) * 60.0 / drop["bpm"]
        else:
            start_seconds += beats * 60.0 / bpm

    total_seconds = start_seconds
    base_bpm = song["tempo_map"][0] if song["tempo_map"] else 120.0

    lines: list[str] = [
        f'<REAPER_PROJECT 0.1 "7.79/win64" 0 0',
        "  <NOTES 0 2",
        "  >",
        "  RIPPLE 0 0",
        "  GROUPOVERRIDE 0 0 0 0",
        "  AUTOXFADE 129",
        "  ENVATTACH 3",
        "  POOLEDENVATTACH 0",
        "  TCPUIFLAGS 0",
        "  MIXERUIFLAGS 11 48 0",
        "  ENVFADESZ10 40",
        "  PEAKGAIN 1",
        "  FEEDBACK 0",
        "  PANLAW 1",
        "  PROJOFFS 0 0 0",
        "  MAXPROJLEN 0 0",
        "  GRID 3199 8 1 8 1 0 0 0",
        "  TIMEMODE 1 5 -1 30 0 0 -1 0",
        "  VIDEO_CONFIG 0 0 65792",
        "  PANMODE 3",
        "  PANLAWFLAGS 3",
        "  CURSOR 0",
        "  ZOOM 100 0 0",
        "  VZOOMEX 6 0",
        "  USE_REC_CFG 0",
        "  RECMODE 1",
        "  SMPTESYNC 0 30 100 40 1000 300 0 0 1 0 0",
        "  LOOP 0",
        "  LOOPGRAN 0 4",
        '  RECORD_PATH "Media" ""',
        "  <RECORD_CFG",
        "    ZXZhdxgAAQ==",
        "  >",
        "  <APPLYFX_CFG",
        "  >",
        '  RENDER_FILE ""',
        '  RENDER_PATTERN ""',
        "  RENDER_FMT 0 2 0",
        "  RENDER_1X 0",
        "  RENDER_RANGE 1 0 0 0 1000",
        "  RENDER_RESAMPLE 3 0 1",
        "  RENDER_ADDTOPROJ 0",
        "  RENDER_STEMS 0",
        "  RENDER_DITHER 0",
        "  RENDER_TRIM 0.000001 0.000001 0 0",
        "  TIMELOCKMODE 1",
        "  TEMPOENVLOCKMODE 1",
        "  ITEMMIX 1",
        "  DEFPITCHMODE 589824 0",
        "  TAKELANE 1",
        "  SAMPLERATE 44100 0 0",
        "  <RENDER_CFG",
        "    ZXZhdxgAAQ==",
        "  >",
        "  LOCK 1",
        "  <METRONOME 6 2",
        "    VOL 0.25 0.125",
        "    BEATLEN 4",
        "    FREQ 1760 880 1",
        '    SAMPLES "" "" "" ""',
        "    SPLIGNORE 0 0",
        '    SPLDEF 2 660 "" 0 ""',
        '    SPLDEF 3 440 "" 0 ""',
        "    PATTERN 0 169",
        "    PATTERNSTR ABBB",
        "    MULT 1",
        "  >",
        "  GLOBAL_AUTO -1",
        f"  TEMPO {base_bpm:.10f} 4 4 0",
        "  PLAYRATE 1 0 0.25 4",
        "  SELECTION 0 0",
        "  SELECTION2 0 0",
        "  MASTERAUTOMODE 0",
        "  MASTERTRACKHEIGHT 0 0",
        "  MASTERPEAKCOL 16576",
        "  MASTERMUTESOLO 0",
        "  MASTERTRACKVIEW 0 0.6667 0.5 0.5 0 0 0 0 0 0 0 0 0 0 1",
        "  MASTERHWOUT 0 0 1 0 0 0 0 -1",
        "  MASTER_NCH 2 2",
        "  MASTER_VOLUME 1 0 -1 -1 1",
        "  MASTER_PANMODE 3",
        "  MASTER_PANLAWFLAGS 3",
        "  MASTER_FX 1",
        f"  MASTER_TRACKID {_new_guid()}",
        "  MASTER_SEL 0",
        "  <MASTERPLAYSPEEDENV",
        f"    EGUID {_new_guid()}",
        "    ACT 0 -1",
        "    VIS 0 1 1",
        "    LANEHEIGHT 0 0",
        "    ARM 0",
        "    DEFSHAPE 0 -1 -1",
        "  >",
    ]
    lines += _tempo_envelope_block(tempo_points)
    lines += [
        "  RULERHEIGHT 86 86",
        '  RULERLANE 1 4 "" 0 -1 0',
        '  RULERLANE 2 8 "" 0 -1 0',
        "  <PROJBAY",
        "  >",
    ]

    # Drums stays LAST -- tests/test_reaper_project.py locates the drum
    # track's real <SOURCE MIDI> block via "the last one in the file"
    # (`text.rindex`), same real convention as this list's own prior
    # ordering; Pad/Accents are new real tracks inserted before it, not
    # appended after.
    tracks = [
        ("Guitar (Take A)", _GUITAR_A_CHANNEL, guitar_a_events, 1),
        ("Guitar (Take B)", _GUITAR_B_CHANNEL, guitar_b_events, 2),
        ("Bass", _BASS_CHANNEL, bass_events, 3),
        ("Lead", _LEAD_CHANNEL, lead_events, 4),
        ("Pad", _PAD_CHANNEL, pad_events, 5),
        ("Accents", _ACCENT_CHANNEL, accent_events, 6),
        ("Drums", _DRUM_CHANNEL, drum_events, 7),
    ]
    for name, channel, events, item_id in tracks:
        lines += _track_block(name, channel, events, total_seconds, item_id)

    lines.append(">")

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
