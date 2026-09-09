import mido
import pytest

from fretboard import Fretboard
from midi_export import _CHORD_THICKENED_ROLES, _guitar_chord_tone_pitches, song_to_midi
from presets import load_all_presets
from song import compose_song

ALL_PRESET_IDS = sorted(load_all_presets().keys())


def test_guitar_chord_tone_pitches_returns_real_root_and_fifth():
    fb = Fretboard([40, 45, 50, 55, 59, 64])  # standard 6-string
    tones = _guitar_chord_tone_pitches(fb, 40)
    assert 40 in tones  # the real root itself must be one of the tones
    assert len(tones) >= 2, "expected a real power chord (root + 5th), not just the root alone"
    for tone in tones:
        assert fb.midi_to_frets(tone), f"expected every real chord tone to be reachable on the fretboard, got {tone}"


def test_guitar_chord_tone_pitches_falls_back_to_root_when_unreachable():
    """Fail-closed: a genuinely unreachable interval (e.g. a pitch far
    beyond the fretboard's max_fret for the 5th) must fall back to the
    bare root alone -- never fabricate a fingering, never raise."""
    fb = Fretboard([40], max_fret=1)  # one string, almost no room
    tones = _guitar_chord_tone_pitches(fb, 41)
    assert tones == [41]


def _read_back(path):
    return mido.MidiFile(str(path))


@pytest.mark.parametrize("preset_id", ALL_PRESET_IDS)
def test_song_to_midi_writes_a_real_parseable_file_for_every_preset(preset_id, tmp_path):
    song = compose_song(preset_id, seed=42, num_sections=4)
    out = tmp_path / f"{preset_id}.mid"
    song_to_midi(song, out)

    assert out.exists() and out.stat().st_size > 0
    parsed = _read_back(out)
    assert parsed.type == 1
    # Tempo track + guitar A/B + bass + lead + drums.
    assert len(parsed.tracks) == 6


def test_guitar_track_note_count_matches_real_guitar_hit_count():
    """X.23: a chord-thickened role's real hit now emits MULTIPLE note_ons
    (one per real chord tone from `_guitar_chord_tone_pitches`), not one --
    expected count must account for that real thickening, not assume 1:1."""
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_hits")
    guitar_fb = song["guitar_fretboard"]

    expected_note_events = 0
    for section in song["sections"]:
        thickened = section["role"] in _CHORD_THICKENED_ROLES
        for c, p in zip(section["guitar_take_a"], section["pitches_per_cell"]):
            if c["is_rest"] or p is None:
                continue
            expected_note_events += len(_guitar_chord_tone_pitches(guitar_fb, p)) if thickened else 1

    parsed = _read_back(out_path)
    guitar_a_track = _track_by_name(parsed, "Guitar (Take A)")
    note_ons = [m for m in guitar_a_track if m.type == "note_on"]
    assert len(note_ons) == expected_note_events
    assert expected_note_events > 0


def test_guitar_pitches_match_the_real_pitches_per_cell_data():
    """X.23: chord-thickened roles emit real chord TONES (root + 5th via
    `_guitar_chord_tone_pitches`), not just the bare root -- expected
    pitches must include those real extra tones for eligible roles."""
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_pitches")
    guitar_fb = song["guitar_fretboard"]

    expected_pitches = []
    for section in song["sections"]:
        thickened = section["role"] in _CHORD_THICKENED_ROLES
        for p in section["pitches_per_cell"]:
            if p is None:
                continue
            expected_pitches.extend(_guitar_chord_tone_pitches(guitar_fb, p) if thickened else [p])
    expected_pitches.sort()

    parsed = _read_back(out_path)
    guitar_a_track = _track_by_name(parsed, "Guitar (Take A)")
    actual_pitches = sorted(m.note for m in guitar_a_track if m.type == "note_on")
    assert actual_pitches == expected_pitches


def test_chord_thickened_role_has_real_simultaneous_chord_tones():
    """X.23's real, direct proof: a chord-thickened section's exported
    guitar track must have at least one real hit where multiple note_ons
    share the exact same tick -- an actual chord, not just a note-count
    change that could coincidentally match from unrelated causes."""
    song = compose_song("djent", seed=5, num_sections=3)
    assert any(s["role"] in _CHORD_THICKENED_ROLES for s in song["sections"])
    out_path = _write_tmp(song, "djent_chord_proof")

    parsed = _read_back(out_path)
    guitar_a_track = _track_by_name(parsed, "Guitar (Take A)")
    tick = 0
    on_ticks: dict[int, int] = {}
    for m in guitar_a_track:
        tick += m.time
        if m.type == "note_on":
            on_ticks[tick] = on_ticks.get(tick, 0) + 1
    assert any(count > 1 for count in on_ticks.values()), "expected at least one real simultaneous chord"


def test_chill_and_interlude_are_excluded_from_chord_thickening():
    """X.23: chill/interlude explicitly stay single-note -- their real,
    already-established melodic/harmony character (X.6b/P3.12) shouldn't
    get chugged into power chords, matching the same real exclusion
    kick/snare/hihat already use (X.9/X.11/X.22)."""
    assert "chill" not in _CHORD_THICKENED_ROLES
    assert "interlude" not in _CHORD_THICKENED_ROLES


def test_bass_pitches_match_the_real_bass_fretboard_data():
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_bass")

    expected_pitches = sorted(
        c["midi"] for section in song["sections"] for c in section["bass"] if not c["is_rest"]
    )

    parsed = _read_back(out_path)
    bass_track = _track_by_name(parsed, "Bass")
    actual_pitches = sorted(m.note for m in bass_track if m.type == "note_on")
    assert actual_pitches == expected_pitches


def test_tempo_track_reflects_the_real_tempo_map():
    # groovy's own preset bpm; num_sections chosen large enough that a
    # build->breakdown transition (X.6c's real trigger) is likely, but the
    # test only asserts against song["tempo_map"] itself -- never a
    # hand-picked expected BPM -- so it's correct either way.
    # X.33: seed bumped from 11 -- half-time breakdown is now a real
    # per-section coin flip (song._BREAKDOWN_HALFTIME_CHANCE), not
    # unconditional, so seed 11 no longer guarantees a real tempo change;
    # seed 0 does.
    song = compose_song("djent", seed=0, num_sections=8)
    out_path = _write_tmp(song, "djent_tempo")

    parsed = _read_back(out_path)
    tempo_track = parsed.tracks[0]
    assert tempo_track.name == "Tempo Map"
    # One real set_tempo event per section (no dedup attempted -- harmless
    # to restate an unchanged tempo, and it keeps every section boundary
    # independently checkable), each matching song["tempo_map"] exactly --
    # PLUS (X.18) one real extra event for any section carrying a
    # mid-section `tempo_drop`, in the same section order.
    real_tempos = [round(mido.tempo2bpm(m.tempo)) for m in tempo_track if m.type == "set_tempo"]
    expected_tempos = []
    for section, bpm in zip(song["sections"], song["tempo_map"]):
        expected_tempos.append(round(bpm))
        drop = section.get("tempo_drop")
        if drop is not None:
            expected_tempos.append(round(drop["bpm"]))
    assert real_tempos == expected_tempos
    # This preset/seed/length must actually exercise a real tempo change
    # somewhere (X.6c's build->breakdown trigger), not just constant bpm --
    # otherwise this test wouldn't be checking anything beyond a flat file.
    assert len(set(real_tempos)) > 1, "expected a real metric-modulation tempo change -- try a different seed/length if this fires"


def test_tempo_drop_event_lands_at_the_real_mid_section_tick():
    """X.18: the real extra set_tempo event for a section with a
    tempo_drop must land at the exact tick this section's own
    trigger_beat implies (start-of-section tick + trigger_beat*ppq),
    not just somewhere in the track."""
    # X.32: seed bumped from 11 -- real per-role feel resolution now draws
    # an extra rng.choice() for every "build" role section, shifting this
    # seed's later draws (including the tempo_drop chance roll) enough that
    # seed 11 no longer lands a real tempo_drop; seed 0 does.
    song = compose_song("djent", seed=0, num_sections=8)
    dropped = [(i, s) for i, s in enumerate(song["sections"]) if s.get("tempo_drop") is not None]
    assert dropped, "expected djent seed=11/8 sections to include a real tempo_drop (see test_tempo_track_reflects_the_real_tempo_map)"

    out_path = _write_tmp(song, "djent_tempo_drop")
    parsed = _read_back(out_path)
    tempo_track = parsed.tracks[0]

    ppq = parsed.ticks_per_beat
    start_beat = 0.0
    expected_drop_ticks = []
    for section in song["sections"]:
        drop = section.get("tempo_drop")
        if drop is not None:
            expected_drop_ticks.append(round((start_beat + drop["trigger_beat"]) * ppq))
        start_beat += sum(c["duration"] for c in section["guitar_take_a"])

    ticks = []
    t = 0
    for m in tempo_track:
        t += m.time
        if m.type == "set_tempo":
            ticks.append(t)
    for expected_tick in expected_drop_ticks:
        assert expected_tick in ticks, f"expected a real set_tempo event at tick {expected_tick}"


def test_drum_track_uses_real_gm_kick_snare_and_hihat_notes():
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_drums")

    expected_kick_hits = sum(
        1 for s in song["sections"] for c in s["kick"] if not c["is_rest"]
    )
    expected_snare_hits = sum(
        1 for s in song["sections"] for c in s["snare"] if not c["is_rest"]
    )
    # X.13: a section's "hihat" cells can carry HIHAT_CLOSED, HIHAT_OPEN
    # (accent), or CRASH_1 (transition) -- count each role separately
    # rather than lumping every non-rest cell under one GM note.
    expected_hihat_hits = sum(
        1 for s in song["sections"] for c in s["hihat"] if c["role"] == "HIHAT_CLOSED"
    )
    expected_open_hits = sum(
        1 for s in song["sections"] for c in s["hihat"] if c["role"] == "HIHAT_OPEN"
    )
    expected_crash_hits = sum(
        1 for s in song["sections"] for c in s["hihat"] if c["role"] == "CRASH_1"
    )

    parsed = _read_back(out_path)
    drum_track = _track_by_name(parsed, "Drums")
    note_ons = [m for m in drum_track if m.type == "note_on"]
    assert note_ons, "djent's real euclid kick style must produce at least one hit"
    # note_for_role: KICK=36, SNARE=38, HIHAT_CLOSED=42, HIHAT_OPEN=48,
    # CRASH_1=49 (ROLE_TO_NOTE) -- all real GM values, never fabricated
    # (this track carries all these roles, X.9/X.11/X.13).
    assert all(m.note in (36, 38, 42, 48, 49) for m in note_ons)
    assert all(m.channel == 9 for m in note_ons)
    assert sum(1 for m in note_ons if m.note == 36) == expected_kick_hits
    assert sum(1 for m in note_ons if m.note == 38) == expected_snare_hits
    assert sum(1 for m in note_ons if m.note == 48) == expected_open_hits
    assert sum(1 for m in note_ons if m.note == 49) == expected_crash_hits
    assert expected_crash_hits > 0, "expected at least one real section-transition crash"
    assert sum(1 for m in note_ons if m.note == 42) == expected_hihat_hits
    assert expected_snare_hits > 0, "djent's breakdown/build/solo sections must produce real snare hits"
    assert expected_hihat_hits > 0, "djent's sections must produce real hihat hits"


def test_solo_lead_track_gets_real_notes_when_a_solo_section_exists():
    # X.21: real open/muted velocity now genuinely affects judge()'s
    # pm_ratio scoring, so compose_song's internal seed-retry loop can land
    # on a different real sequence for the same nominal seed than before --
    # a real, expected consequence, not a bug. Seed-search rather than
    # trusting one hardcoded value.
    song = None
    for seed in range(11, 30):
        candidate = compose_song("djent", seed=seed, num_sections=10)
        if any(s["role"] == "solo" for s in candidate["sections"]):
            song = candidate
            break
    assert song is not None, "expected at least one seed in range(11, 30) to produce a real solo section"
    solo_sections = [s for s in song["sections"] if s["role"] == "solo"]

    out_path = _write_tmp(song, "djent_solo")
    parsed = _read_back(out_path)
    lead_track = _track_by_name(parsed, "Lead")
    note_ons = [m for m in lead_track if m.type == "note_on"]

    expected_note_count = sum(len(s["lead"]) for s in song["sections"])
    assert len(note_ons) == expected_note_count
    assert len(note_ons) > 0


def test_song_to_midi_rejects_non_positive_ppq():
    song = compose_song("djent", seed=1, num_sections=2)
    with pytest.raises(ValueError):
        song_to_midi(song, "unused.mid", ppq=0)


def test_song_to_midi_rejects_mismatched_tempo_map_length():
    song = compose_song("djent", seed=1, num_sections=2)
    song["tempo_map"] = song["tempo_map"][:1]  # deliberately truncate
    with pytest.raises(ValueError):
        song_to_midi(song, "unused.mid")


def _write_tmp(song, name):
    import tempfile
    import os
    d = tempfile.mkdtemp()
    path = os.path.join(d, f"{name}.mid")
    song_to_midi(song, path)
    return path


def _track_by_name(parsed, name):
    for track in parsed.tracks:
        if track.name == name:
            return track
    raise AssertionError(f"no track named {name!r} in {[t.name for t in parsed.tracks]}")
