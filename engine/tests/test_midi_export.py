import mido
import pytest

from midi_export import song_to_midi
from presets import load_all_presets
from song import compose_song

ALL_PRESET_IDS = sorted(load_all_presets().keys())


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
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_hits")

    expected_hits = sum(
        1 for section in song["sections"] for c in section["guitar_take_a"] if not c["is_rest"]
    )

    parsed = _read_back(out_path)
    guitar_a_track = _track_by_name(parsed, "Guitar (Take A)")
    note_ons = [m for m in guitar_a_track if m.type == "note_on"]
    assert len(note_ons) == expected_hits
    assert expected_hits > 0


def test_guitar_pitches_match_the_real_pitches_per_cell_data():
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_pitches")

    expected_pitches = sorted(
        p for section in song["sections"] for p in section["pitches_per_cell"] if p is not None
    )

    parsed = _read_back(out_path)
    guitar_a_track = _track_by_name(parsed, "Guitar (Take A)")
    actual_pitches = sorted(m.note for m in guitar_a_track if m.type == "note_on")
    assert actual_pitches == expected_pitches


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
    song = compose_song("djent", seed=11, num_sections=8)
    out_path = _write_tmp(song, "djent_tempo")

    parsed = _read_back(out_path)
    tempo_track = parsed.tracks[0]
    assert tempo_track.name == "Tempo Map"
    # One real set_tempo event per section (no dedup attempted -- harmless
    # to restate an unchanged tempo, and it keeps every section boundary
    # independently checkable), each matching song["tempo_map"] exactly.
    real_tempos = [round(mido.tempo2bpm(m.tempo)) for m in tempo_track if m.type == "set_tempo"]
    expected_tempos = [round(bpm) for bpm in song["tempo_map"]]
    assert real_tempos == expected_tempos
    # This preset/seed/length must actually exercise a real tempo change
    # somewhere (X.6c's build->breakdown trigger), not just constant bpm --
    # otherwise this test wouldn't be checking anything beyond a flat file.
    assert len(set(real_tempos)) > 1, "expected a real metric-modulation tempo change -- try a different seed/length if this fires"


def test_drum_track_uses_real_gm_kick_note():
    song = compose_song("djent", seed=5, num_sections=3)
    out_path = _write_tmp(song, "djent_drums")

    parsed = _read_back(out_path)
    drum_track = _track_by_name(parsed, "Drums")
    note_ons = [m for m in drum_track if m.type == "note_on"]
    assert note_ons, "djent's real euclid kick style must produce at least one hit"
    # note_for_role("KICK") == 36 (ROLE_TO_NOTE) -- every drum note here
    # must be that real GM value, never a fabricated one.
    assert all(m.note == 36 for m in note_ons)
    assert all(m.channel == 9 for m in note_ons)


def test_solo_lead_track_gets_real_notes_when_a_solo_section_exists():
    song = compose_song("djent", seed=11, num_sections=10)
    solo_sections = [s for s in song["sections"] if s["role"] == "solo"]
    assert solo_sections, "need a solo section to test -- try a different seed if this fires"

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
