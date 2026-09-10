import base64
import re

import pytest

from midi_export import _CHORD_THICKENED_ROLES, _guitar_chord_tone_pitches
from presets import load_all_presets
from reaper_project import song_to_rpp
from song import compose_song

ALL_PRESET_IDS = sorted(load_all_presets().keys())

_TRACK_NAMES = ["Guitar (Take A)", "Guitar (Take B)", "Bass", "Lead", "Pad", "Accents", "Synth", "Guitar (Pedal)", "Drums"]


def _write(song, tmp_path, name="song"):
    out = tmp_path / f"{name}.rpp"
    song_to_rpp(song, out)
    return out.read_text(encoding="utf-8")


@pytest.mark.parametrize("preset_id", ALL_PRESET_IDS)
def test_song_to_rpp_writes_a_structurally_balanced_project_for_every_preset(preset_id, tmp_path):
    song = compose_song(preset_id, seed=42, num_sections=4)
    text = _write(song, tmp_path, preset_id)

    assert text.startswith("<REAPER_PROJECT")
    assert text.rstrip().endswith(">")
    # Every '<' opens exactly one matching '>' -- a real, if coarse,
    # structural-validity check (this project was itself verified by
    # actually opening a generated file in a real installed REAPER 7.79
    # and confirming it loads with no error dialog).
    assert text.count("<") == text.count(">")

    for name in _TRACK_NAMES:
        assert f'NAME "{name}"' in text
    assert text.count("<TRACK") == 9


def test_rpp_track_name_x_block_decodes_to_the_real_midi_meta_event(tmp_path):
    song = compose_song("djent", seed=1, num_sections=2)
    text = _write(song, tmp_path)

    # Every <X ...> block's base64 payload must decode to the real,
    # standard MIDI sequence/track-name meta-event (0xFF 0x03 <name>) --
    # verified against a real Reaper-generated ground-truth file, not
    # assumed.
    matches = re.findall(r'<X 0 0 0 0 3 "([^"]*)"\n\s+(\S+)\n', text)
    assert matches, "expected at least one <X> track-name block"
    for name, b64 in matches:
        decoded = base64.b64decode(b64)
        assert decoded == b"\xff\x03" + name.encode("ascii")


def _real_track_pan(text: str, track_name: str) -> float:
    """Real `VOLPAN` pan field for the track named `track_name`, found by
    locating its own `<TRACK ...>` block (never a bare regex across the
    whole file, which could match a DIFFERENT track's VOLPAN line if one
    happened to come first)."""
    block_start = text.index(f'NAME "{track_name}"')
    track_start = text.rindex("<TRACK", 0, block_start)
    next_track = text.find("<TRACK", track_start + 1)
    block = text[track_start:next_track if next_track != -1 else len(text)]
    match = re.search(r"VOLPAN 1 (-?[\d.]+) ", block)
    assert match, f"no VOLPAN line found in {track_name}'s own <TRACK> block"
    return float(match.group(1))


def test_rpp_pans_the_double_tracked_guitars_hard_left_and_right(tmp_path):
    """Regression test for a real, previously-unchecked gap shared with
    the MIDI export: every real `<TRACK>` block used the identical fixed
    `VOLPAN 1 0 -1 -1 1` template regardless of name, so the real
    double-tracked guitar pair (meant to be panned wide in an actual
    mix) collapsed into one centered mass with zero stereo separation."""
    song = compose_song("djent", seed=1, num_sections=6)
    text = _write(song, tmp_path)

    pan_a = _real_track_pan(text, "Guitar (Take A)")
    pan_b = _real_track_pan(text, "Guitar (Take B)")
    assert pan_a < 0.0 < pan_b, "expected Take A panned left of center and Take B right of center"
    assert pan_a == pytest.approx(-pan_b), "expected a real, symmetric mirror-image pan spread"


def test_rpp_and_midi_export_agree_on_which_side_each_guitar_take_sits(tmp_path):
    """The two real export formats (`.rpp`/`.mid`) must not silently
    disagree about which side Take A vs Take B is panned on -- both
    ultimately read from the SAME real `_PAN_*` constants in
    `midi_export.py`."""
    from midi_export import _PAN_GUITAR_A, _PAN_GUITAR_B, _pan_cc_to_reaper

    song = compose_song("djent", seed=1, num_sections=6)
    text = _write(song, tmp_path)
    assert _real_track_pan(text, "Guitar (Take A)") == pytest.approx(_pan_cc_to_reaper(_PAN_GUITAR_A))
    assert _real_track_pan(text, "Guitar (Take B)") == pytest.approx(_pan_cc_to_reaper(_PAN_GUITAR_B))


def test_rpp_guitar_note_count_matches_real_song_data(tmp_path):
    """X.23: chord-thickened roles emit multiple real note-on events per
    hit (one per chord tone) -- expected count must account for that."""
    song = compose_song("djent", seed=5, num_sections=3)
    text = _write(song, tmp_path)
    guitar_fb = song["guitar_fretboard"]

    expected_note_events = 0
    for s in song["sections"]:
        thickened = s["role"] in _CHORD_THICKENED_ROLES
        for c, p in zip(s["guitar_take_a"], s["pitches_per_cell"]):
            if c["is_rest"] or p is None:
                continue
            expected_note_events += len(_guitar_chord_tone_pitches(guitar_fb, p)) if thickened else 1
    # Guitar (Take A)'s SOURCE MIDI block: count real note-on 0x9_ events
    # (channel 0 -> status byte 90) between its <SOURCE MIDI and the next
    # track's opening, matching the real generated cell data exactly.
    block_start = text.index("<SOURCE MIDI")
    block_end = text.index("<SOURCE MIDI", block_start + 1)
    block = text[block_start:block_end]
    note_ons = re.findall(r"^\s*E \d+ 90 ", block, flags=re.MULTILINE)
    assert len(note_ons) == expected_note_events
    assert expected_note_events > 0


def test_rpp_drum_events_use_real_gm_notes_on_channel_nine(tmp_path):
    song = compose_song("djent", seed=5, num_sections=3)
    text = _write(song, tmp_path)

    drums_block_start = text.rindex("<SOURCE MIDI")  # Drums is the last track
    block = text[drums_block_start:]
    hits = re.findall(r"^\s*E \d+ 99 ([0-9a-f]{2}) ", block, flags=re.MULTILINE)
    assert hits, "expected real drum hits on channel 9 (status 0x99)"
    # 0x24=36=KICK, 0x26=38=SNARE, 0x2a=42=HIHAT_CLOSED, 0x30=48=HIHAT_OPEN,
    # 0x31=49=CRASH_1 (X.9/X.11/X.13).
    assert all(h in ("24", "26", "2a", "30", "31") for h in hits)
    assert "2a" in hits, "expected real hihat hits (X.11)"


def _source_midi_block_for_track(text, name):
    """The `<SOURCE MIDI ...>` block belonging to the track whose real
    `<X ...>` name-meta-event decodes to `name` -- located by name, not
    position, so it's robust to the real track order in the file."""
    x_marker = f'<X 0 0 0 0 3 "{name}"'
    x_index = text.index(x_marker)
    block_start = text.rindex("<SOURCE MIDI", 0, x_index)
    next_block = text.find("<SOURCE MIDI", x_index)
    block_end = next_block if next_block != -1 else len(text)
    return text[block_start:block_end]


def test_rpp_pad_track_has_real_sustained_chord_events(tmp_path):
    song = compose_song("djent", seed=1, num_sections=6)  # djent: octave_stab=true
    text = _write(song, tmp_path)

    block = _source_midi_block_for_track(text, "Pad")
    # Channel 4 (_PAD_CHANNEL) note-on status byte: 0x90 | 4 = 0x94.
    note_ons = re.findall(r"^\s*E \d+ 94 ", block, flags=re.MULTILINE)
    assert note_ons, "expected real pad-chord note-on events on channel 4"


def test_rpp_accents_track_has_real_accent_hit_events(tmp_path):
    song = compose_song("djent", seed=1, num_sections=6)  # djent: octave_stab=true
    text = _write(song, tmp_path)

    block = _source_midi_block_for_track(text, "Accents")
    # Channel 5 (_ACCENT_CHANNEL) note-on status byte: 0x90 | 5 = 0x95.
    note_ons = re.findall(r"^\s*E \d+ 95 ", block, flags=re.MULTILINE)
    assert note_ons, "expected real accent-hit note-on events on channel 5"


def test_rpp_synth_track_exists_but_is_now_empty(tmp_path):
    """`atmosphere.synth_double` was retired from `song.py`'s real
    per-section generation 2026-09-11 (redundant with `lead_mode ==
    "ambient_lead"`'s own genuinely independent melody, once measured to
    be one of six voices all locked to the identical rhythm in a single
    section -- see `test_song.py`'s own dedicated comment). The "Synth"
    track still exists in the real `.rpp` output (export plumbing kept,
    in case a future role wants it again), but real generated output now
    correctly has ZERO synth note events."""
    song = compose_song("metalcore", seed=3, num_sections=8)  # metalcore: octave_stab=true
    text = _write(song, tmp_path)

    block = _source_midi_block_for_track(text, "Synth")
    # Channel 6 (_SYNTH_DOUBLE_CHANNEL) note-on status byte: 0x90 | 6 = 0x96.
    note_ons = re.findall(r"^\s*E \d+ 96 ", block, flags=re.MULTILINE)
    assert note_ons == [], "expected zero synth-double note-on events now that the call site is retired"


def test_rpp_pedal_guitar_track_has_real_note_events(tmp_path):
    song = compose_song("metalcore", seed=3, num_sections=8)
    text = _write(song, tmp_path)

    block = _source_midi_block_for_track(text, "Guitar (Pedal)")
    # Channel 7 (_PEDAL_CHANNEL) note-on status byte: 0x90 | 7 = 0x97.
    note_ons = re.findall(r"^\s*E \d+ 97 ", block, flags=re.MULTILINE)
    assert note_ons, "expected real pedal-guitar note-on events on channel 7"


def test_rpp_tempo_envelope_matches_real_tempo_map(tmp_path):
    # X.33: seed bumped from 11 -- see the equivalent test_midi_export.py
    # test's own comment for why.
    song = compose_song("djent", seed=0, num_sections=8)
    text = _write(song, tmp_path)

    tempo_block = text[text.index("<TEMPOENVEX"):text.index(">", text.index("<TEMPOENVEX"))]
    pt_bpms = [float(m) for m in re.findall(r"^    PT [\d.]+ ([\d.]+)", tempo_block, flags=re.MULTILINE)]
    # (X.18) one real extra point for any section carrying a mid-section
    # `tempo_drop`, in the same section order -- same real-data contract
    # as the MIDI tempo-track test.
    expected = []
    for section, bpm in zip(song["sections"], song["tempo_map"]):
        expected.append(round(bpm, 6))
        drop = section.get("tempo_drop")
        if drop is not None:
            expected.append(round(drop["bpm"], 6))
    assert [round(b, 6) for b in pt_bpms] == expected
    assert len(set(pt_bpms)) > 1, "expected a real tempo change for this seed -- try another if this fires"


def test_rpp_tempo_drop_point_lands_at_the_real_time_and_shifts_later_sections(tmp_path):
    """X.18: the real extra TEMPOENVEX point for a dropped section must
    land at real elapsed seconds (pre-drop bpm up to the trigger), AND
    every later section's own point must reflect the slower real time the
    dropped portion actually took -- not just the flat `beats*60/bpm`
    every section used before this feature existed."""
    # X.32: seed bumped from 11 -- see the equivalent test_midi_export.py
    # test's own comment for why.
    song = compose_song("djent", seed=0, num_sections=8)
    dropped_indices = [i for i, s in enumerate(song["sections"]) if s.get("tempo_drop") is not None]
    assert dropped_indices, "expected djent seed=11/8 sections to include a real tempo_drop"

    text = _write(song, tmp_path, "djent_tempo_drop")
    tempo_block = text[text.index("<TEMPOENVEX"):text.index(">", text.index("<TEMPOENVEX"))]
    pt_points = [
        (float(t), float(bpm))
        for t, bpm in re.findall(r"^    PT ([\d.]+) ([\d.]+)", tempo_block, flags=re.MULTILINE)
    ]

    # Independently re-derive expected (time, bpm) points the same way a
    # real DAW would accumulate elapsed time -- section by section, with
    # the dropped portion split into its pre-drop and post-drop halves.
    expected_points = []
    t = 0.0
    for section, bpm in zip(song["sections"], song["tempo_map"]):
        expected_points.append((t, bpm))
        beats = sum(c["duration"] for c in section["guitar_take_a"])
        drop = section.get("tempo_drop")
        if drop is not None:
            trigger = drop["trigger_beat"]
            drop_t = t + trigger * 60.0 / bpm
            expected_points.append((drop_t, drop["bpm"]))
            t = drop_t + (beats - trigger) * 60.0 / drop["bpm"]
        else:
            t += beats * 60.0 / bpm

    assert len(pt_points) == len(expected_points)
    for (actual_t, actual_bpm), (exp_t, exp_bpm) in zip(pt_points, expected_points):
        assert actual_t == pytest.approx(exp_t, abs=1e-6)
        assert actual_bpm == pytest.approx(exp_bpm, abs=1e-6)


def test_song_to_rpp_rejects_mismatched_tempo_map_length(tmp_path):
    song = compose_song("djent", seed=1, num_sections=2)
    song["tempo_map"] = song["tempo_map"][:1]
    with pytest.raises(ValueError):
        song_to_rpp(song, tmp_path / "bad.rpp")


def test_song_to_rpp_reproducible_structure_across_calls(tmp_path):
    """Same song -> same note/timing content every time (GUIDs are the
    only thing allowed to differ -- this project's own seeded-determinism
    law applies to the composed song, not to Reaper's own random GUIDs)."""
    song = compose_song("tech", seed=3, num_sections=3)
    text_a = _write(song, tmp_path, "a")
    text_b = _write(song, tmp_path, "b")

    strip_guids = lambda t: re.sub(r"\{[0-9A-F-]+\}", "{GUID}", t)
    assert strip_guids(text_a) == strip_guids(text_b)
