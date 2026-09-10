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
