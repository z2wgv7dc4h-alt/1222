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


def _make_track(song, number, pitches_by_measure, instrument=30, is_percussion=False, name="Guitar", n_strings=1):
    track = guitarpro.Track(
        song,
        number=number,
        strings=[guitarpro.GuitarString(i + 1, 0) for i in range(n_strings)],
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


def _make_chord_track(song, number, chords_by_measure, instrument=30, name="Guitar", n_strings=6):
    """`chords_by_measure` maps a 0-based measure index to a list of beats;
    each beat is either `None` (a rest) or a real list of `(string, fret)`
    pairs -- a genuine multi-note chord when the list has >1 entry."""
    track = _make_track(song, number, {}, instrument=instrument, name=name, n_strings=n_strings)
    for measure in track.measures:
        chords = chords_by_measure.get(measure.header.number - 1, [])
        voice = measure.voices[0]
        beats = []
        for chord in chords:
            beat = guitarpro.Beat(voice)
            if chord is None:
                beat.status = guitarpro.BeatStatus.rest
                beat.notes = []
            else:
                beat.status = guitarpro.BeatStatus.normal
                beat.notes = [
                    guitarpro.Note(beat, value=fret, string=string)
                    for string, fret in chord
                ]
            beat.duration = guitarpro.Duration(value=8)
            beats.append(beat)
        voice.beats = beats
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
    assert first.track == "Guitar"
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
        track="Guitar",
        cell=[{"duration": 0.5, "is_rest": False}, {"duration": 0.5, "is_rest": True}],
        deltas=[0],
        role="verse",
        raw_marker="Verse",
    )
    out_path = tmp_path / "bank.json"
    rb.save_riff_bank([fragment], out_path)
    loaded = rb.load_riff_bank(out_path)
    assert loaded == [fragment]


# --- _candidate_riff_runs / _resolve_run / _tile_cell_and_deltas / select_and_resolve_motif ---

import random

from theory import Scale

_SCALE = Scale(root=40, name="minor")


def _bar(role, measure_index, source_song="Song A", source_file="a.gp5", track="Guitar", deltas=None):
    return rb.RiffFragment(
        source_song=source_song, source_file=source_file, measure_index=measure_index, track=track,
        cell=[{"duration": 1.0, "is_rest": False} for _ in range(4)],
        deltas=deltas if deltas is not None else [0, 2, -2, 1],
        role=role, raw_marker=role,
    )


def test_candidate_riff_runs_finds_every_real_2_to_4_bar_contiguous_same_role_window():
    bars = [_bar("verse", i) for i in range(5)]  # 5 contiguous real verse bars
    runs = rb._candidate_riff_runs(bars, "verse")
    lengths = sorted(len(r) for r in runs)
    # From 5 contiguous bars: 4 real 2-bar windows, 3 real 3-bar, 2 real 4-bar.
    assert lengths.count(2) == 4
    assert lengths.count(3) == 3
    assert lengths.count(4) == 2
    assert 5 not in lengths  # never longer than _MAX_RIFF_BARS


def test_candidate_riff_runs_never_crosses_a_role_boundary():
    bars = [_bar("verse", 0), _bar("verse", 1), _bar("chorus", 2), _bar("verse", 3)]
    runs = rb._candidate_riff_runs(bars, "verse")
    # measure 3 is isolated (chorus breaks contiguity before it) -- only
    # the real [0,1] window is a valid verse run, never [1,3] or [0,1,2,3].
    assert [[f.measure_index for f in r] for r in runs] == [[0, 1]]


def test_candidate_riff_runs_never_stitches_across_two_different_songs():
    bars = [_bar("verse", 0, source_song="Song A"), _bar("verse", 0, source_song="Song B")]
    runs = rb._candidate_riff_runs(bars, "verse")
    assert runs == []  # each song only has ONE real verse bar -- below _MIN_RIFF_BARS alone


def test_candidate_riff_runs_returns_nothing_for_an_uncovered_role():
    bars = [_bar("verse", 0), _bar("verse", 1)]
    assert rb._candidate_riff_runs(bars, "breakdown") == []


def test_resolve_run_stays_within_the_real_register_bound_under_extreme_climb():
    # An extreme synthetic run -- every real hit a large upward leap, never
    # downward -- mirrors the exact pattern already used for motif.
    # generate_pitch_deltas/riff_model.generate_riff_motif to prove the
    # register-bound reflection actually engages.
    run = [_bar("verse", 0, deltas=[0, 11, 11, 11]), _bar("verse", 1, deltas=[11, 11, 11, 11])]
    cell, deltas = rb._resolve_run(run, _SCALE, 0)
    pitches = []
    degree_index = 0
    for d in deltas:
        degree_index += d
        pitches.append(_SCALE.degree(degree_index))
    anchor = _SCALE.degree(0)
    span = rb._RIFF_REGISTER_SPAN_SEMITONES
    assert all(anchor - span <= p <= anchor + span for p in pitches)
    assert any(p2 < p1 for p1, p2 in zip(pitches, pitches[1:]))  # real reflection happened


def test_tile_cell_and_deltas_repeats_verbatim_and_lands_exactly_on_total_beats():
    cell = [{"duration": 1.0, "is_rest": False} for _ in range(4)]
    deltas = [0, 2, -2, 1]
    out_cell, out_deltas = rb._tile_cell_and_deltas(cell, deltas, 10.0)
    assert sum(c["duration"] for c in out_cell) == pytest.approx(10.0)
    # 2 full real repeats (8 beats) + a real 2-beat partial third repeat --
    # deltas repeat verbatim in lockstep with each hit, including the
    # partial repeat's own first two hits.
    assert out_deltas == [0, 2, -2, 1, 0, 2, -2, 1, 0, 2]


def test_tile_cell_and_deltas_rejects_bad_input():
    with pytest.raises(ValueError):
        rb._tile_cell_and_deltas([], [], 4.0)
    with pytest.raises(ValueError):
        rb._tile_cell_and_deltas([{"duration": 1.0, "is_rest": False}], [0], 0.0)


def test_select_and_resolve_motif_returns_none_with_no_matching_role():
    bars = [_bar("verse", 0), _bar("verse", 1)]
    result = rb.select_and_resolve_motif(bars, "breakdown", 4.0, _SCALE, 0, random.Random(1))
    assert result is None


def test_select_and_resolve_motif_returns_none_when_coverage_is_below_min_riff_bars():
    bars = [_bar("verse", 0)]  # only 1 real bar -- below _MIN_RIFF_BARS
    result = rb.select_and_resolve_motif(bars, "verse", 4.0, _SCALE, 0, random.Random(1))
    assert result is None


def test_select_and_resolve_motif_tiles_one_real_riff_and_carries_provenance():
    bars = [_bar("verse", 0), _bar("verse", 1), _bar("verse", 2)]
    result = rb.select_and_resolve_motif(bars, "verse", 16.0, _SCALE, 0, random.Random(1))
    assert result is not None
    assert sum(c["duration"] for c in result.cell) == pytest.approx(16.0)
    assert result.source_song == "Song A"
    assert result.measure_start in (0, 1)  # start of whichever real 2- or 3-bar run was picked
    assert result.track == "Guitar"


def test_select_and_resolve_motif_same_rng_same_pick():
    bars = [_bar("verse", 0), _bar("verse", 1), _bar("verse", 2), _bar("verse", 3)]
    a = rb.select_and_resolve_motif(bars, "verse", 8.0, _SCALE, 0, random.Random(7))
    b = rb.select_and_resolve_motif(bars, "verse", 8.0, _SCALE, 0, random.Random(7))
    assert a.deltas == b.deltas and a.measure_start == b.measure_start


# --- real per-note technique/articulation capture ---------------------------

_TECHNIQUE_KEYS = ("palm_mute", "harmonic", "slide", "tremolo", "vibrato", "accent")


def _notes_of(track):
    return [n for m in track.measures for v in m.voices for b in v.beats for n in b.notes]


def test_measure_cell_and_deltas_captures_real_techniques_only_when_true():
    song = _make_song(1)
    track = _make_track(song, 1, {0: [40, None, 44]}, instrument=30)
    notes = _notes_of(track)
    notes[0].effect = guitarpro.NoteEffect(palmMute=True, vibrato=True, accentuatedNote=True)
    notes[1].effect = guitarpro.NoteEffect(
        harmonic=guitarpro.HarmonicEffect(),
        slides=[guitarpro.SlideType.shiftSlideTo],
        tremoloPicking=guitarpro.TremoloPickingEffect(),
    )
    cell, _, _, _ = rb._measure_cell_and_deltas(track.measures[0])

    assert cell[0]["palm_mute"] is True
    assert cell[0]["vibrato"] is True
    assert cell[0]["accent"] is True
    assert "harmonic" not in cell[0] and "slide" not in cell[0] and "tremolo" not in cell[0]

    assert cell[1]["is_rest"] is True
    assert not any(k in cell[1] for k in _TECHNIQUE_KEYS)

    assert cell[2]["harmonic"] is True
    assert cell[2]["slide"] is True
    assert cell[2]["tremolo"] is True
    assert "palm_mute" not in cell[2] and "accent" not in cell[2]


def test_heavy_accentuated_note_maps_to_accent():
    song = _make_song(1)
    track = _make_track(song, 1, {0: [40]}, instrument=30)
    _notes_of(track)[0].effect = guitarpro.NoteEffect(heavyAccentuatedNote=True)
    cell, _, _, _ = rb._measure_cell_and_deltas(track.measures[0])
    assert cell[0]["accent"] is True


def test_extract_fragments_from_file_carries_technique_keys(tmp_path):
    song = _make_song(1)
    track = _make_track(song, 1, {0: [40, 44]}, instrument=30)
    _notes_of(track)[0].effect = guitarpro.NoteEffect(palmMute=True)
    song.tracks = [track]
    fragments = _write_and_extract(tmp_path, song)
    assert fragments[0].cell[0]["palm_mute"] is True
    assert "palm_mute" not in fragments[0].cell[1]


def test_extract_bass_fragments_from_file_carries_technique_keys(tmp_path):
    song = _make_song(1)
    track = _make_track(song, 1, {0: [33, 36]}, instrument=33, name="Bass")
    _notes_of(track)[0].effect = guitarpro.NoteEffect(palmMute=True)
    song.tracks = [track]
    path = tmp_path / "bass_technique.gp5"
    guitarpro.write(song, str(path))
    fragments = rb.extract_bass_fragments_from_file(path)
    assert fragments[0].cell[0]["palm_mute"] is True
    assert "palm_mute" not in fragments[0].cell[1]


# --- failure-reason classification -------------------------------------------


def test_classify_failure_reason_maps_known_and_unknown():
    assert rb.classify_failure_reason("gpx sub-format not decodable by this pyguitarpro version") == "gpx_unsupported"
    assert rb.classify_failure_reason("no real guitar-family track found (no GM-program 24-31 track)") == "no_guitar_track"
    assert rb.classify_failure_reason("no real bass-family track found (no GM-program 32-39 track)") == "no_bass_track"
    assert rb.classify_failure_reason("no distinct real lead-guitar track found (needs 2+ guitar-family tracks)") == "no_lead_track"
    assert rb.classify_failure_reason("track has no measures") == "track_has_no_measures"
    assert rb.classify_failure_reason("unsupported version 'PK...'") == "parse_error"


def test_build_riff_bank_records_no_track_reason(tmp_path):
    song = _make_song(1)
    bass = _make_track(song, 1, {0: [30]}, instrument=33, name="Bass")
    song.tracks = [bass]
    guitarpro.write(song, str(tmp_path / "bass_only.gp5"))

    fragments, failures = rb.build_riff_bank(tmp_path)

    assert fragments == []
    assert len(failures) == 1
    assert failures[0][0].endswith("bass_only.gp5")
    assert failures[0][1] == "no real guitar-family track found (no GM-program 24-31 track)"
    assert rb.classify_failure_reason(failures[0][1]) == "no_guitar_track"


# --- real chord / polyphony capture -----------------------------------------


def test_measure_cell_and_deltas_captures_chord_notes_and_frets():
    song = _make_song(1)
    track = _make_chord_track(song, 1, {0: [[(1, 3), (2, 2), (3, 0)], None, [(1, 5)]]})
    cell, deltas, chord_notes, chord_frets = rb._measure_cell_and_deltas(track.measures[0])

    assert [c["is_rest"] for c in cell] == [False, True, False]
    # only hits, in order; the rest contributes nothing
    assert chord_notes == [[3, 2, 0], [5]]
    assert chord_frets == [[(1, 3), (2, 2), (3, 0)], [(1, 5)]]
    # deltas still comes from the top note only: 3 -> 5
    assert deltas == [0, 2]


def test_extract_fragments_from_file_carries_chord_data(tmp_path):
    song = _make_song(1, markers={0: "Verse"}, title="Chord Song")
    track = _make_chord_track(song, 1, {0: [[(1, 3), (2, 2)], [(1, 5)]]})
    song.tracks = [track]
    path = tmp_path / "chords.gp5"
    guitarpro.write(song, str(path))

    fragments = rb.extract_fragments_from_file(path)

    assert fragments[0].chord_notes == [[3, 2], [5]]
    assert fragments[0].chord_frets == [[(1, 3), (2, 2)], [(1, 5)]]
    assert fragments[0].deltas == [0, 2]


def test_extract_bass_fragments_from_file_carries_chord_data(tmp_path):
    song = _make_song(1)
    track = _make_chord_track(song, 1, {0: [[(1, 3), (2, 5)]]}, instrument=33, name="Bass", n_strings=4)
    song.tracks = [track]
    path = tmp_path / "bass_chord.gp5"
    guitarpro.write(song, str(path))

    fragments = rb.extract_bass_fragments_from_file(path)

    assert fragments[0].chord_notes == [[3, 5]]
    assert fragments[0].chord_frets == [[(1, 3), (2, 5)]]


def test_riff_fragment_chord_fields_default_empty_for_backward_compat():
    fragment = rb.RiffFragment(
        source_song="S", source_file="f.gp5", measure_index=0, track="Guitar",
        cell=[{"duration": 1.0, "is_rest": False}], deltas=[0],
        role=None, raw_marker=None,
    )
    assert fragment.chord_notes == []
    assert fragment.chord_frets == []
