import pytest

import riff_bank as rb

try:
    import guitarpro
except ImportError:
    guitarpro = None

pytestmark = pytest.mark.skipif(guitarpro is None, reason="pyguitarpro not installed")


# ---------------------------------------------------------------------------
# Synthetic, self-constructed fixtures only -- never a real copyrighted
# reference file (mirrors test_reference_vocab.py's own documented
# strategy for this exact same library).
# ---------------------------------------------------------------------------


def _make_track(song, number, pitches_by_measure, instrument=30, is_percussion=False, name="Guitar"):
    track = guitarpro.Track(
        song,
        number=number,
        strings=[guitarpro.GuitarString(1, 0)],
        channel=guitarpro.MidiChannel(instrument=instrument),
        isPercussionTrack=is_percussion,
    )
    track.name = name
    measures = []
    for header in song.measureHeaders:
        measure = guitarpro.Measure(track, header)
        pitches = pitches_by_measure.get(header.number - 1, [])
        voice = guitarpro.Voice(measure)
        beats = []
        for p in pitches:
            beat = guitarpro.Beat(voice)
            if p is None:
                beat.status = guitarpro.BeatStatus.rest
                beat.notes = []
            else:
                beat.status = guitarpro.BeatStatus.normal
                note = guitarpro.Note(beat, value=p, string=1)
                beat.notes = [note]
            beat.duration = guitarpro.Duration(value=8)
            beats.append(beat)
        voice.beats = beats
        second_voice = guitarpro.Voice(measure)
        empty_beat = guitarpro.Beat(second_voice)
        empty_beat.status = guitarpro.BeatStatus.empty
        empty_beat.duration = guitarpro.Duration(value=8)
        second_voice.beats = [empty_beat]
        measure.voices = [voice, second_voice]
        measures.append(measure)
    track.measures = measures
    return track


def _make_song(num_measures, markers=None, title="Test Song"):
    """`markers` maps a real 0-based measure index to a marker title."""
    song = guitarpro.Song()
    song.title = title
    song.tempo = 120
    headers = []
    for i in range(num_measures):
        header = guitarpro.MeasureHeader(number=i + 1)
        if markers and i in markers:
            header.marker = guitarpro.Marker(title=markers[i])
        headers.append(header)
    song.measureHeaders = headers
    return song


# --- _resolve_role -----------------------------------------------------------


@pytest.mark.parametrize(
    "marker_title,expected_role",
    [
        ("Intro", "intro"),
        ("Verse", "verse"),
        ("Pre-Chorus", "build"),
        ("Pre Chorus", "build"),
        ("Chorus", "chorus"),
        ("Bridge", "interlude"),
        ("Breakdown", "breakdown"),
        ("Solo", "solo"),
        ("Outro", "outro"),
        ("  verse 2  ", "verse"),
    ],
)
def test_resolve_role_maps_known_keywords(marker_title, expected_role):
    role, raw = rb._resolve_role(marker_title, song_title="Some Song")
    assert role == expected_role
    assert raw == marker_title.strip()


def test_resolve_role_keeps_unmapped_marker_as_raw_but_no_role():
    role, raw = rb._resolve_role("A", song_title="Some Song")
    assert role is None
    assert raw == "A"


@pytest.mark.parametrize(
    "junk_title",
    [
        "Live Demonstration at youtube.com/SomeUser",
        "www.example.com",
        "https://example.com/tab",
        ".",
        "",
        "   ",
    ],
)
def test_resolve_role_discards_real_junk_markers_entirely(junk_title):
    role, raw = rb._resolve_role(junk_title, song_title="Some Song")
    assert role is None
    assert raw is None


def test_resolve_role_discards_marker_matching_the_songs_own_title():
    role, raw = rb._resolve_role("Some Song", song_title="Some Song")
    assert role is None
    assert raw is None


# --- _select_rhythm_track -----------------------------------------------------


def test_select_rhythm_track_prefers_the_lower_register_guitar_track():
    song = _make_song(1)
    rhythm = _make_track(song, 1, {0: [40, 41, 42]}, instrument=30, name="Rhythm")
    lead = _make_track(song, 2, {0: [70, 71, 72]}, instrument=30, name="Lead")
    song.tracks = [lead, rhythm]
    picked = rb._select_rhythm_track(song)
    assert picked is rhythm


def test_select_rhythm_track_excludes_non_guitar_and_percussion_tracks():
    song = _make_song(1)
    bass = _make_track(song, 1, {0: [30, 31]}, instrument=33, name="Bass")
    drums = _make_track(song, 2, {0: [36, 38]}, instrument=0, is_percussion=True, name="Drums")
    rhythm = _make_track(song, 3, {0: [40, 41]}, instrument=30, name="Guitar")
    song.tracks = [bass, drums, rhythm]
    assert rb._select_rhythm_track(song) is rhythm


def test_select_rhythm_track_returns_none_when_no_guitar_family_track_exists():
    song = _make_song(1)
    bass = _make_track(song, 1, {0: [30, 31]}, instrument=33, name="Bass")
    song.tracks = [bass]
    assert rb._select_rhythm_track(song) is None


# --- extract_fragments_from_file (via a real temp .gp5 file) -----------------


def _write_and_extract(tmp_path, song, filename="test.gp5"):
    path = tmp_path / filename
    guitarpro.write(song, str(path))
    return rb.extract_fragments_from_file(path)


def test_extract_fragments_from_file_real_cell_and_delta_shape(tmp_path):
    song = _make_song(2, markers={0: "Verse"}, title="Fixture Song")
    track = _make_track(song, 1, {0: [40, None, 44], 1: [47, 40]}, instrument=30)
    song.tracks = [track]
    fragments = _write_and_extract(tmp_path, song)

    assert len(fragments) == 2
    first, second = fragments
    assert first.measure_index == 0
    assert [c["is_rest"] for c in first.cell] == [False, True, False]
    assert first.deltas == [0, 4]  # 40->40 (first note, delta 0), 40->44 (+4 semitones)
    assert first.role == "verse"
    assert first.raw_marker == "Verse"

    # Second measure carries no marker of its own -- real role persists
    # forward from the last real marker seen, same as a tab reader would
    # assume "still in the verse" until told otherwise.
    assert second.role == "verse"
    assert second.deltas == [0, -7]  # 47->47, 47->40 (-7 semitones)


def test_extract_fragments_from_file_fails_closed_with_no_guitar_track(tmp_path):
    song = _make_song(1)
    bass = _make_track(song, 1, {0: [30, 31]}, instrument=33, name="Bass")
    song.tracks = [bass]
    path = tmp_path / "no_guitar.gp5"
    guitarpro.write(song, str(path))
    with pytest.raises(ValueError, match="no real guitar-family track"):
        rb.extract_fragments_from_file(path)


# --- build_riff_bank / save_riff_bank / load_riff_bank -----------------------


def test_build_riff_bank_walks_directory_and_reports_real_failures(tmp_path):
    song = _make_song(1, markers={0: "Chorus"}, title="Bank Song")
    track = _make_track(song, 1, {0: [40, 41]}, instrument=30)
    song.tracks = [track]
    guitarpro.write(song, str(tmp_path / "song_a.gp5"))

    (tmp_path / "unreadable.gpx").write_bytes(b"not a real gpx file")

    fragments, failures = rb.build_riff_bank(tmp_path)

    assert len(fragments) == 1
    assert fragments[0].role == "chorus"
    assert len(failures) == 1
    assert "unreadable.gpx" in failures[0][0]
    assert "gpx sub-format" in failures[0][1]


def test_save_and_load_riff_bank_round_trips_exactly(tmp_path):
    fragment = rb.RiffFragment(
        source_song="Fixture Song",
        source_file="test.gp5",
        measure_index=0,
        cell=[{"duration": 0.5, "is_rest": False}, {"duration": 0.5, "is_rest": True}],
        deltas=[0],
        role="verse",
        raw_marker="Verse",
    )
    out_path = tmp_path / "bank.json"
    rb.save_riff_bank([fragment], out_path)
    loaded = rb.load_riff_bank(out_path)
    assert loaded == [fragment]


# --- select_and_resolve_motif -------------------------------------------------

import random

from theory import Scale

_SCALE = Scale(root=40, name="minor")

_ONE_BAR_FRAGMENT = rb.RiffFragment(
    source_song="Fixture Song", source_file="fixture.gp5", measure_index=0,
    cell=[{"duration": 1.0, "is_rest": False} for _ in range(4)],
    deltas=[0, 2, -2, 1],
    role="verse", raw_marker="Verse",
)


def test_select_and_resolve_motif_returns_none_with_no_matching_role():
    result = rb.select_and_resolve_motif([_ONE_BAR_FRAGMENT], "breakdown", 4.0, _SCALE, 0, random.Random(1))
    assert result is None


def test_select_and_resolve_motif_chains_fragments_to_fill_total_beats():
    result = rb.select_and_resolve_motif([_ONE_BAR_FRAGMENT], "verse", 8.0, _SCALE, 0, random.Random(1))
    assert result is not None
    assert sum(c["duration"] for c in result.cell) == pytest.approx(8.0)
    assert result.hit_count == len(result.deltas) == 8  # two real 4-hit bars chained


def test_select_and_resolve_motif_trims_the_final_fragment_to_land_exactly_on_total_beats():
    # 6.0 beats isn't a multiple of the fragment's own 4.0-beat bar --
    # the second real fragment draw must be trimmed, not overshoot.
    result = rb.select_and_resolve_motif([_ONE_BAR_FRAGMENT], "verse", 6.0, _SCALE, 0, random.Random(1))
    assert result is not None
    assert sum(c["duration"] for c in result.cell) == pytest.approx(6.0)


def test_select_and_resolve_motif_stays_within_the_real_register_bound_under_extreme_climb():
    # An extreme synthetic fragment -- every real hit a large upward leap,
    # never a downward one -- mirrors the exact real test pattern already
    # used for motif.generate_pitch_deltas/riff_model.generate_riff_motif
    # to prove the register-bound reflection actually engages rather than
    # reproducing the same unbounded-walk bug fixed earlier this session.
    climbing_fragment = rb.RiffFragment(
        source_song="Fixture Song", source_file="fixture.gp5", measure_index=0,
        cell=[{"duration": 1.0, "is_rest": False} for _ in range(4)],
        deltas=[0, 11, 11, 11],
        role="verse", raw_marker="Verse",
    )
    result = rb.select_and_resolve_motif(
        [climbing_fragment], "verse", 64.0, _SCALE, 0, random.Random(1),
    )
    assert result is not None
    pitches = []
    degree_index = 0
    for d in result.deltas:
        degree_index += d
        pitches.append(_SCALE.degree(degree_index))
    anchor = _SCALE.degree(0)
    span = rb._FRAGMENT_REGISTER_SPAN_SEMITONES
    assert all(anchor - span <= p <= anchor + span for p in pitches)
    # A genuinely unbounded climb would use only one direction -- real
    # reflection means the register bound was actually hit and turned.
    assert any(p2 < p1 for p1, p2 in zip(pitches, pitches[1:]))


def test_select_and_resolve_motif_draws_with_replacement_when_only_one_fragment_covers_a_role():
    # A role with exactly one real fragment must still be able to fill a
    # long section by reusing it -- sparse real coverage is legitimate,
    # not a hard stop.
    result = rb.select_and_resolve_motif([_ONE_BAR_FRAGMENT], "verse", 16.0, _SCALE, 0, random.Random(1))
    assert result is not None
    assert result.hit_count == 16
