import json

import numpy as np
import pretty_midi
import pytest
import soundfile as sf

import reference_vocab as rv

try:
    import guitarpro
except ImportError:
    guitarpro = None


# ---------------------------------------------------------------------------
# Synthetic, self-constructed fixtures only -- never a real copyrighted
# reference file (mirrors test_audio_vocab.py's own documented strategy,
# itself mirroring midi_vocab.py's synthetic-in-memory-MIDI approach).
# ---------------------------------------------------------------------------


def _write_midi_reference(path, pitches, name="Guitar", bpm=120.0):
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=30, name=name)
    t = 0.0
    for p in pitches:
        inst.notes.append(pretty_midi.Note(velocity=100, pitch=p, start=t, end=t + 0.2))
        t += 0.25
    pm.instruments.append(inst)
    pm.write(str(path))


def _build_gp_song(pitches, tempo=120):
    song = guitarpro.Song()
    song.tempo = tempo
    track = guitarpro.Track(song, number=1, strings=[guitarpro.GuitarString(1, 0)])
    track.name = "Test Guitar"
    song.tracks = [track]
    header = guitarpro.MeasureHeader()
    measure = guitarpro.Measure(track, header)
    track.measures = [measure]
    voice = guitarpro.Voice(measure)
    beats = []
    for p in pitches:
        beat = guitarpro.Beat(voice)
        beat.status = guitarpro.BeatStatus.normal
        beat.duration = guitarpro.Duration(value=8)
        note = guitarpro.Note(beat, value=p, string=1)
        beat.notes = [note]
        beats.append(beat)
    voice.beats = beats
    # Real Guitar Pro files always carry a second (often empty) voice
    # slot per measure -- pyguitarpro's own writer expects exactly 2.
    second_voice = guitarpro.Voice(measure)
    empty_beat = guitarpro.Beat(second_voice)
    empty_beat.status = guitarpro.BeatStatus.empty
    empty_beat.duration = guitarpro.Duration(value=8)
    second_voice.beats = [empty_beat]
    measure.voices = [voice, second_voice]
    return song


def _write_click_track(path, sr=22050, bpm=120.0, duration_s=8.0):
    """Same real synthetic-click-track technique test_audio_vocab.py
    already uses -- no real audio file needed."""
    n_samples = int(sr * duration_s)
    y = np.zeros(n_samples, dtype=np.float32)
    beat_period = 60.0 / bpm
    click_len = int(sr * 0.03)
    t_click = np.arange(click_len) / sr
    click_wave = 0.8 * np.sin(2 * np.pi * 4000.0 * t_click) * np.exp(-t_click * 40)
    t = 0.0
    while t < duration_s:
        start = int(t * sr)
        end = min(n_samples, start + click_len)
        y[start:end] += click_wave[: end - start]
        t += beat_period
    sf.write(str(path), y, sr)


# A deliberately root-heavy pitch sequence (root=60, mostly root + a real
# P5/m3 sprinkle) -- enough real hits for a real, non-trivial statistical
# check, matching the shape of the real reference this module was built
# to analyze (heavily root-weighted, real secondary color).
_ROOT = 60
_ROOT_HEAVY_PITCHES = [_ROOT] * 20 + [_ROOT + 7] * 5 + [_ROOT + 3] * 3


def test_analyze_midi_reference_finds_the_real_root_heavy_vocab(tmp_path):
    path = tmp_path / "ref.mid"
    _write_midi_reference(path, _ROOT_HEAVY_PITCHES)

    result = rv.analyze_midi_reference(path)
    assert result["format"] == "midi"
    assert len(result["tracks"]) == 1
    track = result["tracks"][0]
    assert track["key_root_pc"] == _ROOT % 12
    assert track["interval_vocab_pct"][0] > 60.0  # real, dominant root weight
    assert track["register_low"] == _ROOT
    assert track["register_high"] == _ROOT + 7


def test_analyze_midi_reference_captures_a_real_alternating_transition(tmp_path):
    # A deliberately ALTERNATING pattern (root, P5, root, P5, ...) -- the
    # marginal `interval_vocab_pct` would report a boring, uninformative
    # 50/50 root-vs-P5 split for this data (order-independent), but the
    # real sequence has a strong, deterministic structure: interval 0 is
    # ALWAYS followed by interval 7, and vice versa. Proves
    # `interval_transition_counts` captures that real structure the
    # marginal histogram cannot.
    alternating = [_ROOT, _ROOT + 7] * 10
    path = tmp_path / "ref.mid"
    _write_midi_reference(path, alternating)

    result = rv.analyze_midi_reference(path)
    track = result["tracks"][0]
    transitions = track["interval_transition_counts"]
    # After a root (0), the next interval is ALWAYS 7 -- a real, strong
    # signal a marginal histogram would never show.
    assert transitions[0] == {7: 10}
    assert transitions[7] == {0: 9}


def test_analyze_midi_reference_skips_drum_and_sparse_tracks(tmp_path):
    path = tmp_path / "ref.mid"
    pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    drums.notes.append(pretty_midi.Note(velocity=100, pitch=36, start=0.0, end=0.1))
    pm.instruments.append(drums)
    sparse = pretty_midi.Instrument(program=30, name="Sparse")
    sparse.notes.append(pretty_midi.Note(velocity=100, pitch=60, start=0.0, end=0.1))
    pm.instruments.append(sparse)
    pm.write(str(path))

    result = rv.analyze_midi_reference(path)
    assert result["tracks"] == []


def test_role_guess_distinguishes_pedal_riff_and_lead():
    pedal_pitches = [60] * 30 + [67]  # 96.9% root, tight register
    riff_pitches = [60, 67, 63, 70, 55, 72, 60, 67] * 3  # wide register, real movement
    lead_pitches = [72, 84, 76]  # sparse, wide high register

    assert rv._role_guess(pedal_pitches, rv._interval_vocab_from_pitches(pedal_pitches, 60).get(0, 0), 6.0) == "pedal"
    assert rv._role_guess(riff_pitches, rv._interval_vocab_from_pitches(riff_pitches, 60).get(0, 0), 6.0) == "riff"
    assert rv._role_guess(lead_pitches, rv._interval_vocab_from_pitches(lead_pitches, 72).get(0, 0), 1.0) == "lead"
    assert rv._role_guess([], 0.0, 0.0) == "unknown"


@pytest.mark.skipif(guitarpro is None, reason="pyguitarpro not installed")
def test_analyze_gp_reference_finds_the_real_root_heavy_vocab(tmp_path):
    song = _build_gp_song(_ROOT_HEAVY_PITCHES, tempo=140)
    path = tmp_path / "ref.gp5"
    guitarpro.write(song, str(path))

    result = rv.analyze_gp_reference(path)
    assert result["format"] == "gp"
    assert result["tempo_bpm"] == 140.0
    assert len(result["tracks"]) == 1
    track = result["tracks"][0]
    assert track["key_root_pc"] == _ROOT % 12
    assert track["interval_vocab_pct"][0] > 60.0


@pytest.mark.skipif(guitarpro is None, reason="pyguitarpro not installed")
def test_analyze_gp_reference_skips_percussion_tracks(tmp_path):
    song = _build_gp_song(_ROOT_HEAVY_PITCHES, tempo=120)
    song.tracks[0].isPercussionTrack = True
    path = tmp_path / "ref.gp5"
    guitarpro.write(song, str(path))

    result = rv.analyze_gp_reference(path)
    assert result["tracks"] == []


def test_analyze_audio_reference_returns_real_structural_stats(tmp_path):
    path = tmp_path / "ref.wav"
    _write_click_track(path, bpm=140.0, duration_s=6.0)

    result = rv.analyze_audio_reference(path)
    assert result["format"] == "audio"
    assert result["tempo_bpm"] > 0
    assert result["duration_s"] > 0
    assert result["transcription"] in ("full", "structural_only")
    # Never silently claims note-level precision it doesn't have.
    if result["transcription"] == "structural_only":
        assert result["tracks"] == []
    # Real rhythm-pattern classification and dynamic-density curve --
    # previously computed by audio_vocab but discarded here.
    assert result["rhythm_pattern"] in ("straight", "gallop", "syncopated", "insufficient_onsets")
    assert isinstance(result["section_density_curve"], list)
    assert len(result["section_density_curve"]) > 0
    # No drum stem supplied -- honestly None, never fabricated.
    assert result["drum_role_pct"] is None


def _write_low_thump_track(path, sr=22050, bpm=140.0, duration_s=6.0):
    """A synthetic low-frequency (80Hz) thumping pattern -- a real
    kick-drum proxy for testing `classify_drum_onsets`'s real low-band
    energy heuristic, without needing a real recorded drum sample."""
    n_samples = int(sr * duration_s)
    y = np.zeros(n_samples, dtype=np.float32)
    beat_period = 60.0 / bpm
    thump_len = int(sr * 0.08)
    t_thump = np.arange(thump_len) / sr
    thump_wave = 0.9 * np.sin(2 * np.pi * 80.0 * t_thump) * np.exp(-t_thump * 25)
    t = 0.0
    while t < duration_s:
        start = int(t * sr)
        end = min(n_samples, start + thump_len)
        y[start:end] += thump_wave[: end - start]
        t += beat_period
    sf.write(str(path), y, sr)


def test_analyze_audio_reference_captures_real_drum_role_pct_when_drum_stem_given(tmp_path):
    guitar_path = tmp_path / "no_drums.wav"
    drums_path = tmp_path / "drums.wav"
    _write_click_track(guitar_path, bpm=140.0, duration_s=6.0)
    _write_low_thump_track(drums_path, bpm=140.0, duration_s=6.0)

    result = rv.analyze_audio_reference(guitar_path, drums_path=drums_path)
    assert result["drum_role_pct"] is not None
    # A real low-frequency-dominant onset pattern should classify as
    # mostly KICK, per classify_drum_onsets's own documented heuristic.
    assert result["drum_role_pct"].get("KICK", 0.0) > 50.0
    total_pct = sum(result["drum_role_pct"].values())
    assert 99.0 <= total_pct <= 101.0  # real percentages, sum to ~100


def test_add_reference_passes_drums_path_through_for_audio(tmp_path):
    guitar_path = tmp_path / "no_drums.wav"
    drums_path = tmp_path / "drums.wav"
    _write_click_track(guitar_path, bpm=140.0, duration_s=6.0)
    _write_low_thump_track(drums_path, bpm=140.0, duration_s=6.0)
    corpus_path = tmp_path / "corpus.json"

    result = rv.add_reference(guitar_path, corpus_path=corpus_path, drums_path=drums_path)
    assert result["drum_role_pct"] is not None
    corpus = rv.load_reference_corpus(corpus_path)
    assert corpus["no_drums.wav"]["drum_role_pct"] is not None


def test_build_preset_from_corpus_calibrates_pedal_from_real_pedal_tracks(tmp_path):
    # A synthetic corpus with one real, heavily root-weighted "pedal"
    # track (matching the real ~96% measured Guitar-2 reference this
    # session's own pedal-guitar architecture was built from) plus a
    # normal "riff" track (required for build_preset_from_corpus to run
    # at all, since it aggregates vocab from "riff"-role tracks).
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
                {"role_guess": "pedal", "key_mode": "minor", "interval_vocab_pct": {0: 96.0, 7: 2.0, 5: 2.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_pedal_calibration",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.pedal == pytest.approx(0.96, abs=0.01)


def test_build_preset_from_corpus_calibrates_pedal_from_string_keyed_corpus(tmp_path):
    # A real corpus loaded via `load_reference_corpus` (i.e. round-tripped
    # through JSON) has STRING interval keys ("0", "7", ...), not the int
    # keys a freshly-in-memory `analyze_*` result carries -- confirmed via
    # `test_add_reference_and_load_reference_corpus_round_trip`'s own
    # documented JSON round-trip effect. Regression test for a real bug
    # caught on the actual 31-song production corpus: the pedal-bias
    # calculation looked up `interval_vocab_pct.get(0, ...)` with an int
    # key, silently finding nothing (default 0.0) against every real
    # string-keyed corpus entry loaded from disk.
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {"0": 50.0, "7": 30.0, "3": 20.0}},
                {"role_guess": "pedal", "key_mode": "minor", "interval_vocab_pct": {"0": 96.0, "7": 2.0, "5": 2.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_pedal_string_keys",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.pedal == pytest.approx(0.96, abs=0.01)


def test_pool_transition_counts_sums_raw_counts_across_tracks():
    tracks = [
        {"interval_transition_counts": {0: {7: 3}, 7: {0: 2}}},
        {"interval_transition_counts": {0: {7: 1, 3: 1}}},
    ]
    pooled = rv._pool_transition_counts(tracks)
    # Row for prev=0: 7 appears 3+1=4 times, 3 appears 1 time -> total 5.
    assert pooled[0][7] == pytest.approx(80.0)
    assert pooled[0][3] == pytest.approx(20.0)
    # Row for prev=7: only ever followed by 0, in one track -> 100%.
    assert pooled[7] == {0: 100.0}


def test_pool_transition_counts_handles_real_json_string_keys():
    # Regression coverage for the exact class of bug caught in the real
    # pedal-bias calibration (a corpus loaded from disk has STRING keys,
    # not the int keys a freshly-in-memory analysis result carries).
    tracks = [{"interval_transition_counts": {"0": {"7": 3}, "7": {"0": 2}}}]
    pooled = rv._pool_transition_counts(tracks)
    assert pooled[0][7] == pytest.approx(100.0)
    assert pooled[7][0] == pytest.approx(100.0)


def test_pool_transition_counts_none_when_no_track_has_real_data():
    tracks = [{"interval_vocab_pct": {0: 100.0}}]  # no interval_transition_counts key
    assert rv._pool_transition_counts(tracks) is None


def test_build_preset_from_corpus_calibrates_a_real_markov_table(tmp_path):
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {
                    "role_guess": "riff", "key_mode": "minor",
                    "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0},
                    "interval_transition_counts": {0: {7: 10}, 7: {0: 9}},
                },
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_markov_calibration",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.vocab.markov is not None
    assert preset.vocab.markov[0][7] == pytest.approx(100.0)
    # Written to and reloadable from the real preset JSON file too.
    from presets import load_preset

    reloaded = load_preset(tmp_path / "test_markov_calibration.json")
    assert reloaded.vocab.markov[0][7] == pytest.approx(100.0)


def test_build_preset_from_corpus_markov_none_without_transition_data(tmp_path):
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_markov_fallback",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.vocab.markov is None


def test_build_preset_from_corpus_calibrates_triplet_feel_from_syncopated_corpus(tmp_path):
    # Regression test for the "Fix rytyhm" finding: ALL 13/13 real Born
    # of Osiris audio corpus entries measure rhythm_pattern="syncopated"
    # (via audio_vocab.guitar_rhythm_pattern's real onset-timing
    # classification), yet build_preset_from_corpus previously hardcoded
    # feel="bounce" regardless -- never actually calibrated from real
    # data. A corpus with a majority-"syncopated" real rhythm_pattern
    # should now produce feel="triplet" (rhythm.generate_triplet_rhythm's
    # real evenly-spaced 1/3-beat subdivision, the closest existing real
    # device to Singularity's own measured ~0.31-beat median IOI).
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "rhythm_pattern": "syncopated",
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
            ],
        },
        "song_b": {
            "tempo_bpm": 150.0,
            "rhythm_pattern": "syncopated",
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_triplet_feel_calibration",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.feel == "triplet"


def test_build_preset_from_corpus_calibrates_gallop_feel_from_gallop_corpus(tmp_path):
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "rhythm_pattern": "gallop",
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_gallop_feel_calibration",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.feel == "gallop"


def test_build_preset_from_corpus_feel_defaults_to_bounce_without_rhythm_pattern_data(tmp_path):
    # A corpus with no audio-analyzed entries (e.g. all MIDI/GP) carries
    # no rhythm_pattern field at all -- must fall back to the original
    # default rather than fabricating a mapping for absent data.
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_feel_default_fallback",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.feel == "bounce"


def test_build_preset_from_corpus_calibrates_a_real_separate_lead_vocab(tmp_path):
    # A "lead" track with a genuinely DIFFERENT interval color than the
    # "riff" track -- proves lead_vocab is really its own calibration,
    # not just a copy of the riff vocab.
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 70.0, 7: 20.0, 3: 10.0}},
                {"role_guess": "lead", "key_mode": "minor", "interval_vocab_pct": {0: 20.0, 5: 30.0, 9: 50.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_lead_calibration",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.lead_vocab is not None
    assert preset.lead_vocab.weights != preset.vocab.weights
    assert preset.lead_vocab.weights[9] == 50.0
    # Written to and reloadable from the real preset JSON file too.
    from presets import load_preset

    reloaded = load_preset(tmp_path / "test_lead_calibration.json")
    assert reloaded.lead_vocab is not None
    assert reloaded.lead_vocab.weights[9] == 50.0


def test_build_preset_from_corpus_lead_vocab_none_without_lead_tracks(tmp_path):
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 70.0, 7: 20.0, 3: 10.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_lead_fallback",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.lead_vocab is None


def test_build_preset_from_corpus_pedal_falls_back_to_default_without_pedal_tracks(tmp_path):
    corpus = {
        "song_a": {
            "tempo_bpm": 150.0,
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor", "interval_vocab_pct": {0: 50.0, 7: 30.0, 3: 20.0}},
            ],
        },
    }
    preset = rv.build_preset_from_corpus(
        preset_id="test_pedal_fallback",
        description="test",
        tuning_key="drop_g_7",
        output_dir=tmp_path,
        corpus=corpus,
    )
    assert preset.pedal == 0.5


def test_add_reference_and_load_reference_corpus_round_trip(tmp_path):
    ref_path = tmp_path / "ref.mid"
    _write_midi_reference(ref_path, _ROOT_HEAVY_PITCHES)
    corpus_path = tmp_path / "corpus.json"

    result = rv.add_reference(ref_path, corpus_path=corpus_path)
    corpus = rv.load_reference_corpus(corpus_path)
    assert list(corpus.keys()) == ["ref.mid"]
    # A real, expected JSON round-trip effect: `interval_vocab_pct`'s
    # int interval keys become string keys once written through JSON --
    # not a bug, so compare on the real substance instead of raw equality.
    assert corpus["ref.mid"]["tracks"][0]["key_root_pc"] == result["tracks"][0]["key_root_pc"]
    assert corpus["ref.mid"]["tracks"][0]["interval_vocab_pct"]["0"] == result["tracks"][0]["interval_vocab_pct"][0]


def test_load_reference_corpus_missing_file_returns_empty_dict(tmp_path):
    assert rv.load_reference_corpus(tmp_path / "does_not_exist.json") == {}


def test_add_reference_updates_rather_than_duplicates_same_filename(tmp_path):
    ref_path = tmp_path / "ref.mid"
    corpus_path = tmp_path / "corpus.json"
    _write_midi_reference(ref_path, _ROOT_HEAVY_PITCHES)
    rv.add_reference(ref_path, corpus_path=corpus_path)
    _write_midi_reference(ref_path, [67] * 20)  # a real, different reference
    rv.add_reference(ref_path, corpus_path=corpus_path)

    corpus = rv.load_reference_corpus(corpus_path)
    assert len(corpus) == 1


def test_nearest_scale_matches_a_real_root_and_fifth_heavy_vocab():
    # Root + P5 + M3 (0, 7, 4) is real major-triad color -- should match
    # a real major-family scale, never "chromatic" (excluded on purpose).
    weights = {0: 60.0, 7: 25.0, 4: 15.0}
    assert rv._nearest_scale(weights) != "chromatic"
    assert rv._nearest_scale(weights) in ("major", "lydian", "mixolydian", "harmonic_major", "power")


def test_build_preset_from_corpus_writes_a_real_loadable_preset(tmp_path):
    from presets import load_preset, load_tunings, validate_preset

    corpus = {
        "song_a.mid": {
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor",
                 "interval_vocab_pct": {"0": 50.0, "7": 20.0, "3": 10.0}},
            ]
        },
        "song_b.gp": {
            "tracks": [
                {"role_guess": "riff", "key_mode": "minor",
                 "interval_vocab_pct": {"0": 40.0, "7": 30.0, "3": 15.0}},
            ]
        },
    }

    preset = rv.build_preset_from_corpus(
        "test_calibrated", "A real test preset.", "drop_a_7",
        output_dir=tmp_path, corpus=corpus,
    )
    assert preset.id == "test_calibrated"

    out_path = tmp_path / "test_calibrated.json"
    assert out_path.exists()
    # A real, independently-loadable preset -- the actual production path,
    # not just "a file was written".
    tunings = load_tunings()
    validate_preset(json.loads(out_path.read_text()), tunings, expected_id="test_calibrated")
    reloaded = load_preset(out_path, tunings)
    assert reloaded.id == "test_calibrated"
    # Real averaged weight: (50+40)/2 = 45.
    assert reloaded.vocab.weights[0] == 45.0


def test_build_preset_from_corpus_rejects_when_no_matching_role():
    with pytest.raises(ValueError):
        rv.build_preset_from_corpus(
            "empty_test", "desc", "drop_a_7", corpus={"x": {"tracks": []}},
        )
