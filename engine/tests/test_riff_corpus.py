import pytest

import riff_corpus
from riff_corpus import (
    BAR,
    BOS,
    DURATION_BUCKETS,
    ENERGY_HIGH,
    ENERGY_LOW,
    ENERGY_MID,
    PAD,
    VOCAB_SIZE,
    energy_bucket_from_relative_energy,
    load_corpus_tokens,
    notes_to_tokens,
    save_song_tokens,
    token_id,
    token_to_interval_duration,
)


def test_vocab_size_matches_special_plus_interval_duration_grid():
    assert VOCAB_SIZE == 6 + 12 * len(DURATION_BUCKETS)
    assert {PAD, BOS, BAR, ENERGY_LOW, ENERGY_MID, ENERGY_HIGH} == {0, 1, 2, 3, 4, 5}


def test_token_id_round_trips_through_token_to_interval_duration():
    for interval in range(12):
        for idx, duration in enumerate(DURATION_BUCKETS):
            tok = token_id(interval, idx)
            got_interval, got_duration = token_to_interval_duration(tok)
            assert got_interval == interval
            assert got_duration == pytest.approx(duration)


def test_token_id_rejects_out_of_range_interval():
    with pytest.raises(ValueError):
        token_id(12, 0)
    with pytest.raises(ValueError):
        token_id(-1, 0)


def test_token_id_rejects_out_of_range_duration_index():
    with pytest.raises(ValueError):
        token_id(0, len(DURATION_BUCKETS))


def test_token_to_interval_duration_rejects_special_tokens():
    for special in (PAD, BOS, BAR, ENERGY_LOW, ENERGY_MID, ENERGY_HIGH):
        with pytest.raises(ValueError):
            token_to_interval_duration(special)


# --- real energy-bucket conditioning ----------------------------------------


def test_energy_bucket_from_relative_energy_terciles():
    assert energy_bucket_from_relative_energy(0.5) == ENERGY_LOW
    assert energy_bucket_from_relative_energy(0.84) == ENERGY_LOW
    assert energy_bucket_from_relative_energy(1.0) == ENERGY_MID
    assert energy_bucket_from_relative_energy(1.14) == ENERGY_MID
    assert energy_bucket_from_relative_energy(1.16) == ENERGY_HIGH
    assert energy_bucket_from_relative_energy(2.0) == ENERGY_HIGH


def test_notes_to_tokens_inserts_energy_token_only_at_real_transitions():
    # Three notes: first two share LOW energy (no token between them),
    # the third is HIGH (one real transition token inserted).
    notes = [(0.0, 0.25, 60), (0.5, 0.25, 62), (1.0, 0.25, 64)]
    energy_by_time = {0.0: 0.5, 0.5: 0.5, 1.0: 2.0}  # LOW, LOW, HIGH

    tokens = notes_to_tokens(notes, bpm=120.0, energy_at=lambda t: energy_by_time[t])

    assert tokens[0] == ENERGY_LOW  # real energy label at the very start
    # No second ENERGY_LOW between the first two notes (same bucket).
    assert ENERGY_HIGH in tokens
    assert tokens.count(ENERGY_LOW) == 1
    assert tokens.count(ENERGY_HIGH) == 1


def test_notes_to_tokens_emits_no_energy_tokens_when_energy_at_is_none():
    notes = [(0.0, 0.25, 60), (0.5, 0.25, 62), (1.0, 0.25, 64)]
    tokens = notes_to_tokens(notes, bpm=120.0)
    assert not any(t in (ENERGY_LOW, ENERGY_MID, ENERGY_HIGH) for t in tokens)


def test_notes_to_tokens_hand_checkable_sequence():
    # 120 bpm -> 2 beats/sec. Notes at beats 0, 1, 2, 4, 20 (pitches
    # 60, 62, 60, 67, 60) -- verified by hand against the real bucket
    # table and bar-crossing logic.
    notes = [(0.0, 0.25, 60), (0.5, 0.25, 62), (1.0, 0.25, 60), (2.0, 0.5, 67), (10.0, 0.5, 60)]
    tokens = notes_to_tokens(notes, bpm=120.0)

    assert tokens[0] == token_id(2, DURATION_BUCKETS.index(1.0))  # 60->62, gap 1 beat
    assert tokens[1] == token_id(10, DURATION_BUCKETS.index(1.0))  # 62->60, gap 1 beat
    assert tokens[2] == BAR  # beat 2 crosses into bar 1
    assert tokens[3] == token_id(7, DURATION_BUCKETS.index(2.0))  # 60->67, gap 2 beats
    assert tokens[4] == BAR  # beat 20 crosses into bar 5 (single BAR, not one per skipped bar)
    assert tokens[5] == token_id(5, DURATION_BUCKETS.index(4.0))  # 67->60, gap 16 beats -> clamped to max bucket


def test_notes_to_tokens_never_inserts_more_than_one_bar_per_note():
    # A real long rest (many bars skipped) must not fabricate repeated
    # BAR tokens -- exactly one, matching this project's own "never
    # fabricate structure a genuine rest doesn't carry" discipline.
    notes = [(0.0, 0.25, 60), (100.0, 0.25, 62)]
    tokens = notes_to_tokens(notes, bpm=120.0)
    assert tokens.count(BAR) == 1


def test_notes_to_tokens_empty_for_fewer_than_two_notes():
    assert notes_to_tokens([], bpm=120.0) == []
    assert notes_to_tokens([(0.0, 0.25, 60)], bpm=120.0) == []


def test_notes_to_tokens_rejects_nonpositive_bpm():
    notes = [(0.0, 0.25, 60), (0.5, 0.25, 62)]
    with pytest.raises(ValueError):
        notes_to_tokens(notes, bpm=0.0)
    with pytest.raises(ValueError):
        notes_to_tokens(notes, bpm=-10.0)


def test_save_and_load_corpus_tokens_round_trip(tmp_path):
    tokens = [token_id(0, 0), BAR, token_id(5, 3)]
    save_song_tokens("real_song", tokens, out_dir=tmp_path)
    loaded = load_corpus_tokens(tmp_path)
    assert loaded == {"real_song": tokens}


def test_load_corpus_tokens_empty_dict_when_cache_missing(tmp_path):
    assert load_corpus_tokens(tmp_path / "does_not_exist") == {}
