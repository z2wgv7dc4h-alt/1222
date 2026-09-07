import json
import math
import random

import mido
import pytest

import midi_vocab
from drums import generate_vocabulary_informed_blast_fill
from midi_vocab import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CORPUS_DIR,
    FALLBACK_HIT_CHANCE,
    aggregate_vocabulary,
    build_vocabulary,
    extract_corpus_stats,
    extract_file_stats,
    load_vocabulary,
    vocabulary_informed_hit_chance,
)
from rhythm import RhythmRegistry


def _synthetic_midi_file(ticks_per_beat=480, beats=4, note=36):
    """A tiny, fully in-memory mido.MidiFile: `beats` note_on/note_off pairs,
    one beat apart, all on the same note -- a known, hand-computed pattern
    (no disk I/O, no dependency on the real corpus being present)."""
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    for _ in range(beats):
        track.append(mido.Message("note_on", note=note, velocity=100, time=0))
        track.append(mido.Message("note_off", note=note, velocity=0, time=ticks_per_beat))
    return mid


# --- extract_file_stats: main correctness test ------------------------------


def test_extract_file_stats_four_evenly_spaced_hits_over_four_beats():
    mid = _synthetic_midi_file(ticks_per_beat=480, beats=4, note=36)

    stats = extract_file_stats(midi_file=mid)

    assert stats["hits"] == 4
    assert stats["beats"] == pytest.approx(4.0)
    assert stats["hits_per_beat"] == pytest.approx(1.0)
    assert stats["distinct_notes"] == 1
    assert stats["note_counts"] == {36: 4}
    assert stats["tempo_bpm"] is None  # no set_tempo meta in this synthetic file


def test_extract_file_stats_multiple_notes_counted_distinctly():
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    # kick, snare, kick, hihat -- 4 hits, 3 distinct notes, spread over 2 beats.
    track.append(mido.Message("note_on", note=36, velocity=100, time=0))
    track.append(mido.Message("note_off", note=36, velocity=0, time=240))
    track.append(mido.Message("note_on", note=38, velocity=100, time=0))
    track.append(mido.Message("note_off", note=38, velocity=0, time=240))
    track.append(mido.Message("note_on", note=36, velocity=100, time=0))
    track.append(mido.Message("note_off", note=36, velocity=0, time=240))
    track.append(mido.Message("note_on", note=42, velocity=100, time=0))
    track.append(mido.Message("note_off", note=42, velocity=0, time=240))

    stats = extract_file_stats(midi_file=mid)

    assert stats["hits"] == 4
    assert stats["beats"] == pytest.approx(2.0)
    assert stats["hits_per_beat"] == pytest.approx(2.0)
    assert stats["distinct_notes"] == 3
    assert stats["note_counts"] == {36: 2, 38: 1, 42: 1}


def test_extract_file_stats_note_on_zero_velocity_is_not_a_hit():
    # Real-world convention: note_on with velocity 0 is a note-off in
    # disguise (running-status encoding) -- must not be counted as a hit.
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("note_on", note=36, velocity=100, time=0))
    track.append(mido.Message("note_on", note=36, velocity=0, time=480))

    stats = extract_file_stats(midi_file=mid)

    assert stats["hits"] == 1
    assert stats["note_counts"] == {36: 1}


def test_extract_file_stats_requires_path_or_midi_file():
    with pytest.raises(ValueError):
        extract_file_stats()


def test_extract_file_stats_rejects_missing_ticks_per_beat():
    mid = mido.MidiFile(ticks_per_beat=480)
    mid.ticks_per_beat = 0  # simulate a malformed/non-tick-based file
    with pytest.raises(ValueError):
        extract_file_stats(midi_file=mid)


# --- extract_corpus_stats: glob-based walk + graceful skip handling --------


def test_extract_corpus_stats_globs_directory_and_skips_bad_files(tmp_path):
    pack_dir = tmp_path / "some_pack" / "01 - 100 - 120 BPM" / "Fills"
    pack_dir.mkdir(parents=True)

    good = _synthetic_midi_file(ticks_per_beat=480, beats=2, note=38)
    good.save(str(pack_dir / "Groove 01.mid"))

    # A second, valid file elsewhere in the tree (glob must find both).
    groove_dir = tmp_path / "some_pack" / "01 - 100 - 120 BPM" / "Grooves"
    groove_dir.mkdir(parents=True)
    good2 = _synthetic_midi_file(ticks_per_beat=480, beats=4, note=36)
    good2.save(str(groove_dir / "Groove 02.mid"))

    # A corrupt "MIDI" file that must be skipped, not crash the walk.
    bad_path = pack_dir / "corrupt.mid"
    bad_path.write_bytes(b"this is not a real midi file at all")

    result = extract_corpus_stats(tmp_path)

    assert result["skipped"] == 1
    assert any("corrupt.mid" in ex for ex in result["skipped_examples"])
    assert len(result["files"]) == 2

    by_name = {f["path"]: f for f in result["files"]}
    fill_entry = next(f for f in result["files"] if f["kind"] == "fill")
    groove_entry = next(f for f in result["files"] if f["kind"] == "groove")
    assert fill_entry["pack"] == "some_pack"
    assert fill_entry["bpm"] == pytest.approx(110.0)  # midpoint of 100-120
    assert fill_entry["bucket"] == "100-120"
    assert groove_entry["bucket"] == "100-120"


def test_extract_corpus_stats_empty_directory_returns_no_files(tmp_path):
    result = extract_corpus_stats(tmp_path)
    assert result["files"] == []
    assert result["skipped"] == 0


# --- aggregate_vocabulary / build_vocabulary / load_vocabulary -------------


def test_aggregate_vocabulary_buckets_by_bpm_and_pack(tmp_path):
    pack_dir = tmp_path / "pack_a" / "02 - 200 - 220 BPM" / "Fills"
    pack_dir.mkdir(parents=True)
    for i in range(3):
        m = _synthetic_midi_file(ticks_per_beat=480, beats=4, note=36)
        m.save(str(pack_dir / f"Groove {i}.mid"))

    extraction = extract_corpus_stats(tmp_path)
    vocab = aggregate_vocabulary(extraction)

    assert vocab["total_files_parsed"] == 3
    assert vocab["skipped_files"] == 0
    assert "200-220" in vocab["by_bpm_bucket"]
    bucket = vocab["by_bpm_bucket"]["200-220"]
    assert bucket["file_count"] == 3
    assert bucket["avg_hits_per_beat"] == pytest.approx(1.0)
    assert bucket["fill_length_beats"]["count"] == 3
    assert bucket["fill_length_beats"]["min"] == pytest.approx(4.0)
    assert bucket["fill_length_beats"]["median"] == pytest.approx(4.0)
    assert bucket["fill_length_beats"]["max"] == pytest.approx(4.0)
    assert "pack_a" in vocab["by_pack"]


def test_build_and_load_vocabulary_round_trip(tmp_path):
    pack_dir = tmp_path / "pack_a" / "01 - 140 - 160 BPM" / "Grooves"
    pack_dir.mkdir(parents=True)
    m = _synthetic_midi_file(ticks_per_beat=480, beats=4, note=36)
    m.save(str(pack_dir / "Groove 01.mid"))

    cache_path = tmp_path / "cache" / "midi_vocab.json"
    written = build_vocabulary(corpus_dir=tmp_path, cache_path=cache_path)

    assert cache_path.exists()
    loaded = load_vocabulary(cache_path)
    assert loaded == written
    assert loaded["total_files_parsed"] == 1


# --- cached vocabulary JSON shape (the real, checked-in cache) -------------


def test_cached_vocabulary_json_has_expected_shape():
    if not DEFAULT_CACHE_PATH.exists():
        pytest.skip("engine/data/midi_vocab.json not built in this checkout")

    with DEFAULT_CACHE_PATH.open(encoding="utf-8") as fh:
        vocab = json.load(fh)

    assert isinstance(vocab["total_files_parsed"], int)
    assert vocab["total_files_parsed"] > 0
    assert isinstance(vocab["by_bpm_bucket"], dict)
    assert len(vocab["by_bpm_bucket"]) > 0
    for bucket_key, bucket in vocab["by_bpm_bucket"].items():
        assert isinstance(bucket["file_count"], int)
        assert isinstance(bucket["avg_hits_per_beat"], (int, float))
        assert "min" in bucket["fill_length_beats"]
        assert "median" in bucket["fill_length_beats"]
        assert "max" in bucket["fill_length_beats"]
        assert isinstance(bucket["avg_distinct_notes_per_file"], (int, float))


# --- vocabulary_informed_hit_chance: bad-input handling --------------------


_SAMPLE_VOCAB = {
    "bucket_width_bpm": 20,
    "total_files_parsed": 10,
    "skipped_files": 0,
    "by_bpm_bucket": {
        "100-120": {"file_count": 5, "avg_hits_per_beat": 2.0, "fill_length_beats": {}, "avg_distinct_notes_per_file": 3.0},
        "200-220": {"file_count": 5, "avg_hits_per_beat": 3.6, "fill_length_beats": {}, "avg_distinct_notes_per_file": 5.0},
        "unknown": {"file_count": 2, "avg_hits_per_beat": 99.0, "fill_length_beats": {}, "avg_distinct_notes_per_file": 1.0},
    },
    "by_pack": {},
}


def test_vocabulary_informed_hit_chance_exact_bucket_match():
    result = vocabulary_informed_hit_chance(210, vocab=_SAMPLE_VOCAB)
    assert result == pytest.approx(3.6 / 4.0)


def test_vocabulary_informed_hit_chance_nearest_bucket_for_out_of_range_bpm():
    # 5 BPM is nonsense for a metal groove, but must resolve to the nearest
    # POPULATED bucket (100-120, the lowest one present) rather than raising
    # or extrapolating -- documented fallback behavior.
    low = vocabulary_informed_hit_chance(5, vocab=_SAMPLE_VOCAB)
    assert low == pytest.approx(2.0 / 4.0)

    high = vocabulary_informed_hit_chance(5000, vocab=_SAMPLE_VOCAB)
    assert high == pytest.approx(3.6 / 4.0)


def test_vocabulary_informed_hit_chance_ignores_unknown_bucket():
    # The "unknown" bucket (files with no parseable BPM at all) must never
    # be selected as a real answer, even though it has files and an extreme
    # avg_hits_per_beat that would otherwise dominate the nearest-bucket
    # search.
    result = vocabulary_informed_hit_chance(150, vocab=_SAMPLE_VOCAB)
    assert result != pytest.approx(99.0 / 4.0)


def test_vocabulary_informed_hit_chance_nonnumeric_bpm_falls_back_to_default():
    assert vocabulary_informed_hit_chance("not-a-bpm", vocab=_SAMPLE_VOCAB) == FALLBACK_HIT_CHANCE
    assert vocabulary_informed_hit_chance(None, vocab=_SAMPLE_VOCAB) == FALLBACK_HIT_CHANCE
    assert vocabulary_informed_hit_chance(math.nan, vocab=_SAMPLE_VOCAB) == FALLBACK_HIT_CHANCE
    assert vocabulary_informed_hit_chance(math.inf, vocab=_SAMPLE_VOCAB) == FALLBACK_HIT_CHANCE


def test_vocabulary_informed_hit_chance_empty_vocab_falls_back_to_default():
    empty_vocab = {"by_bpm_bucket": {}}
    assert vocabulary_informed_hit_chance(140, vocab=empty_vocab) == FALLBACK_HIT_CHANCE


def test_vocabulary_informed_hit_chance_missing_cache_falls_back_to_default(monkeypatch):
    def _raise_missing(cache_path=DEFAULT_CACHE_PATH):
        raise FileNotFoundError(cache_path)

    monkeypatch.setattr(midi_vocab, "load_vocabulary", _raise_missing)

    result = vocabulary_informed_hit_chance(140)
    assert result == FALLBACK_HIT_CHANCE


def test_vocabulary_informed_hit_chance_result_always_in_valid_range():
    for bpm in [-500, 0, 1, 60, 140, 210, 999, 10000]:
        result = vocabulary_informed_hit_chance(bpm, vocab=_SAMPLE_VOCAB)
        assert 0.0 <= result <= 1.0


# --- wired into drums.py's actual fill-generation flow ---------------------


def test_generate_vocabulary_informed_blast_fill_uses_corpus_derived_hit_chance():
    registry = RhythmRegistry()
    rng = random.Random(7)

    result = generate_vocabulary_informed_blast_fill(
        "vocab-fill",
        registry,
        4.0,
        [0.5, 1.0],
        bpm=210,
        blast_weights={"traditional": 1.0},
        rng=rng,
        vocab=_SAMPLE_VOCAB,
    )

    assert result["blast_type"] == "traditional"
    assert "vocab-fill" in registry
    total_duration = sum(c["duration"] for c in result["cells"])
    assert total_duration == pytest.approx(4.0)


def test_generate_vocabulary_informed_blast_fill_rejects_bad_blast_type():
    registry = RhythmRegistry()
    with pytest.raises(ValueError):
        generate_vocabulary_informed_blast_fill(
            "vocab-fill-bad",
            registry,
            4.0,
            [0.5],
            bpm=140,
            blast_weights={"not_a_real_blast": 1.0},
            rng=random.Random(1),
            vocab=_SAMPLE_VOCAB,
        )


# --- optional, slow integration test against the REAL corpus --------------


@pytest.mark.skipif(
    not DEFAULT_CORPUS_DIR.exists(),
    reason="reference/midi-corpus is gitignored and not present in this checkout",
)
def test_real_corpus_extraction_produces_plausible_stats():
    extraction = extract_corpus_stats(DEFAULT_CORPUS_DIR)
    assert len(extraction["files"]) > 1000
    vocab = aggregate_vocabulary(extraction)
    assert len(vocab["by_bpm_bucket"]) > 0
    for bucket in vocab["by_bpm_bucket"].values():
        if bucket["file_count"] > 0:
            assert bucket["avg_hits_per_beat"] > 0
