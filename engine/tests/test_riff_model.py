import json
import random

import pytest

pytest.importorskip("torch")

import riff_corpus
import riff_model


def _write_synthetic_corpus(corpus_dir, num_songs=4, tokens_per_song=40, seed=1):
    rng = random.Random(seed)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    for i in range(num_songs):
        tokens = [rng.randrange(3, riff_corpus.VOCAB_SIZE) for _ in range(tokens_per_song)]
        (corpus_dir / f"song{i}.json").write_text(json.dumps({"tokens": tokens}), encoding="utf-8")


def test_train_produces_a_real_checkpoint_and_honest_loss_curve(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"

    result = riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    assert checkpoint_path.exists()
    assert result["songs_trained"] == 3
    assert len(result["songs_held_out"]) == 1
    assert len(result["train_loss"]) == 1
    assert len(result["val_loss"]) == 1
    assert result["train_loss"][0] > 0


def test_train_rejects_a_corpus_too_small_to_hold_out_real_val_songs(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir, num_songs=2)
    with pytest.raises(ValueError):
        riff_model.train(
            corpus_dir=corpus_dir, checkpoint_path=tmp_path / "model.pt",
            epochs=1, val_song_count=2,
        )


def test_generate_riff_tokens_same_seed_is_byte_identical(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    first = riff_model.generate_riff_tokens(seed=7, num_tokens=12, checkpoint_path=checkpoint_path, corpus_dir=None)
    second = riff_model.generate_riff_tokens(seed=7, num_tokens=12, checkpoint_path=checkpoint_path, corpus_dir=None)
    assert first == second


def test_generate_riff_tokens_different_seeds_can_differ(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    outputs = {
        tuple(riff_model.generate_riff_tokens(seed=s, num_tokens=16, checkpoint_path=checkpoint_path, corpus_dir=None))
        for s in range(5)
    }
    assert len(outputs) > 1  # a real untrained-ish model with varying seeds shouldn't collapse to one output


def test_generate_riff_tokens_output_is_real_interval_duration_pairs(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    tokens = riff_model.generate_riff_tokens(seed=3, num_tokens=20, checkpoint_path=checkpoint_path, corpus_dir=None)
    for interval, duration in tokens:
        assert 0 <= interval < 12
        assert duration in riff_corpus.DURATION_BUCKETS


def test_generate_riff_tokens_rejects_missing_checkpoint(tmp_path):
    with pytest.raises(FileNotFoundError):
        riff_model.generate_riff_tokens(seed=1, checkpoint_path=tmp_path / "does_not_exist.pt", corpus_dir=None)


def test_ngram_overlap_ratio_flags_a_real_verbatim_memorized_sequence():
    corpus = {"song_a": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}
    # Generated sequence IS the training sequence, verbatim -- must flag as
    # fully memorized (ratio 1.0), the real failure mode this check exists
    # to catch.
    memorized = [3, 4, 5, 6, 7, 8, 9, 10]
    ratio = riff_model._ngram_overlap_ratio(memorized, corpus, n=8)
    assert ratio == pytest.approx(1.0)


def test_ngram_overlap_ratio_low_for_a_real_novel_sequence():
    corpus = {"song_a": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}
    novel = [50, 51, 52, 53, 54, 55, 56, 57, 58, 59]
    ratio = riff_model._ngram_overlap_ratio(novel, corpus, n=8)
    assert ratio == pytest.approx(0.0)


def test_generate_riff_tokens_raises_when_overlap_exceeds_threshold(tmp_path, monkeypatch):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )
    # Force a fabricated 100% overlap regardless of what the model
    # actually generated -- proves the real safeguard fires, without
    # depending on a specific real model output being memorized.
    monkeypatch.setattr(riff_model, "_ngram_overlap_ratio", lambda generated, corpus, n=8: 1.0)
    with pytest.raises(RuntimeError):
        riff_model.generate_riff_tokens(
            seed=1, num_tokens=16, checkpoint_path=checkpoint_path, corpus_dir=corpus_dir,
        )


# --- v2: real section-role energy conditioning + restored pedal-bias -------


def test_energy_bucket_from_arc_energy_matches_the_real_arc_table_intent():
    # Real theory.ARC values, confirmed by direct table read: chill 0.20,
    # intro 0.30, outro 0.40 (low); verse 0.60, chorus 0.70 (mid);
    # solo 0.80, build 0.85, breakdown 1.00 (high).
    assert riff_model.energy_bucket_from_arc_energy(0.20) == riff_corpus.ENERGY_LOW
    assert riff_model.energy_bucket_from_arc_energy(0.30) == riff_corpus.ENERGY_LOW
    assert riff_model.energy_bucket_from_arc_energy(0.40) == riff_corpus.ENERGY_LOW
    assert riff_model.energy_bucket_from_arc_energy(0.60) == riff_corpus.ENERGY_MID
    assert riff_model.energy_bucket_from_arc_energy(0.70) == riff_corpus.ENERGY_MID
    assert riff_model.energy_bucket_from_arc_energy(0.80) == riff_corpus.ENERGY_HIGH
    assert riff_model.energy_bucket_from_arc_energy(0.85) == riff_corpus.ENERGY_HIGH
    assert riff_model.energy_bucket_from_arc_energy(1.00) == riff_corpus.ENERGY_HIGH


def test_generate_riff_tokens_rejects_bad_energy_bucket(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )
    with pytest.raises(ValueError):
        riff_model.generate_riff_tokens(
            seed=1, checkpoint_path=checkpoint_path, corpus_dir=None, energy_bucket=999,
        )


def test_generate_riff_tokens_same_seed_and_energy_bucket_is_byte_identical(tmp_path):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    first = riff_model.generate_riff_tokens(
        seed=7, num_tokens=12, checkpoint_path=checkpoint_path, corpus_dir=None,
        energy_bucket=riff_corpus.ENERGY_HIGH,
    )
    second = riff_model.generate_riff_tokens(
        seed=7, num_tokens=12, checkpoint_path=checkpoint_path, corpus_dir=None,
        energy_bucket=riff_corpus.ENERGY_HIGH,
    )
    assert first == second


def test_generate_riff_motif_threads_arc_energy_into_the_real_bucket(tmp_path, monkeypatch):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    seen_buckets = []
    real_generate = riff_model.generate_riff_tokens

    def spy(*args, **kwargs):
        seen_buckets.append(kwargs.get("energy_bucket"))
        return real_generate(*args, **kwargs)

    monkeypatch.setattr(riff_model, "generate_riff_tokens", spy)

    from theory import Scale
    scale = Scale(root=0, name="minor")
    riff_model.generate_riff_motif(
        seed=1, scale=scale, base_degree=0, total_beats=4.0,
        checkpoint_path=checkpoint_path, corpus_dir=None, arc_energy=1.00,  # breakdown-level
    )
    assert seen_buckets == [riff_corpus.ENERGY_HIGH]


def test_generate_riff_motif_arc_energy_none_generates_unconditioned(tmp_path, monkeypatch):
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    checkpoint_path = tmp_path / "model.pt"
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    seen_buckets = []
    real_generate = riff_model.generate_riff_tokens

    def spy(*args, **kwargs):
        seen_buckets.append(kwargs.get("energy_bucket"))
        return real_generate(*args, **kwargs)

    monkeypatch.setattr(riff_model, "generate_riff_tokens", spy)

    from theory import Scale
    scale = Scale(root=0, name="minor")
    riff_model.generate_riff_motif(
        seed=1, scale=scale, base_degree=0, total_beats=4.0,
        checkpoint_path=checkpoint_path, corpus_dir=None,
    )
    assert seen_buckets == [None]


def test_generate_riff_motif_stays_within_the_real_register_bound_under_extreme_climb(tmp_path, monkeypatch):
    # Real bug, found via direct listening feedback + measurement: `motif.
    # degree_delta_for_interval` is structurally biased non-negative (0
    # negative deltas across every real interval class, confirmed
    # empirically), so a long continuous walk (this function's own real
    # use case -- one riff spanning a whole section, unlike every other
    # real pitch-generation path in this project, which uses SHORT,
    # repeated/tiled motifs) compounds into a runaway climb the existing
    # fretboard octave-snap then yanks back down repeatedly, producing an
    # audible zigzag -- not a training-data quality problem. Force the
    # WORST real case directly: every real token proposes the largest
    # real interval class (11) at the smallest real duration, maximizing
    # real upward climbing pressure over many real notes.
    from theory import Scale

    checkpoint_path = tmp_path / "model.pt"
    corpus_dir = tmp_path / "corpus"
    _write_synthetic_corpus(corpus_dir)
    riff_model.train(
        corpus_dir=corpus_dir, checkpoint_path=checkpoint_path,
        seed=0, epochs=1, batch_size=4, val_song_count=1,
    )

    extreme_pairs = [(11, riff_corpus.DURATION_BUCKETS[0])] * 200
    monkeypatch.setattr(riff_model, "generate_riff_tokens", lambda *a, **kw: extreme_pairs)

    scale = Scale(root=0, name="minor")
    base_degree = 3
    motif = riff_model.generate_riff_motif(
        seed=1, scale=scale, base_degree=base_degree, total_beats=1000.0,
        checkpoint_path=checkpoint_path, corpus_dir=None,
    )

    anchor_pitch = scale.degree(base_degree)
    degree_index = base_degree
    for d in motif.deltas:
        degree_index += d
        pitch = scale.degree(degree_index)
        assert anchor_pitch - riff_model._RIFF_REGISTER_SPAN_SEMITONES <= pitch <= anchor_pitch + riff_model._RIFF_REGISTER_SPAN_SEMITONES


# --- v2: restored real verse pedal-bias -------------------------------------


def test_apply_pedal_bias_to_motif_zero_is_byte_identical():
    from motif import Motif
    motif = Motif(cell=[{"duration": 0.5, "is_rest": False} for _ in range(20)], deltas=[3] * 20)
    result = riff_model.apply_pedal_bias_to_motif(motif, 0.0, random.Random(1))
    assert result.deltas == motif.deltas
    assert result.cell == motif.cell


def test_apply_pedal_bias_to_motif_one_forces_every_hit_to_root():
    from motif import Motif
    motif = Motif(cell=[{"duration": 0.5, "is_rest": False} for _ in range(20)], deltas=[3] * 20)
    result = riff_model.apply_pedal_bias_to_motif(motif, 1.0, random.Random(1))
    assert result.deltas == [0] * 20


def test_apply_pedal_bias_to_motif_partial_probability_real_mix():
    from motif import Motif
    motif = Motif(cell=[{"duration": 0.5, "is_rest": False} for _ in range(200)], deltas=[3] * 200)
    result = riff_model.apply_pedal_bias_to_motif(motif, 0.65, random.Random(1))
    zero_count = sum(1 for d in result.deltas if d == 0)
    # A real, statistically meaningful fraction near 65%, not exact --
    # 200 real draws gives a tight enough real margin to check honestly.
    assert 100 <= zero_count <= 170


def test_apply_pedal_bias_to_motif_does_not_mutate_the_input():
    from motif import Motif
    motif = Motif(cell=[{"duration": 0.5, "is_rest": False} for _ in range(20)], deltas=[3] * 20)
    riff_model.apply_pedal_bias_to_motif(motif, 1.0, random.Random(1))
    assert motif.deltas == [3] * 20


def test_apply_pedal_bias_to_motif_rejects_out_of_range_pedal():
    from motif import Motif
    motif = Motif(cell=[{"duration": 0.5, "is_rest": False}], deltas=[3])
    with pytest.raises(ValueError):
        riff_model.apply_pedal_bias_to_motif(motif, -0.1, random.Random(1))
    with pytest.raises(ValueError):
        riff_model.apply_pedal_bias_to_motif(motif, 1.1, random.Random(1))
