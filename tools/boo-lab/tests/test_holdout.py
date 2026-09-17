"""Tests for src/boo_lab/holdout.py -- the fixed whole-song validation
split. Pure synthetic rows/files under tmp_path; no real corpus data."""
from __future__ import annotations

import pytest

from boo_lab import holdout as h


def test_select_holdout_takes_every_nth_deterministically():
    cands = [("A", f"T{i:02d}") for i in range(10)]
    sel = h.select_holdout(cands, every=4)
    assert sel == {cands[0], cands[4], cands[8]}
    assert h.select_holdout(cands, every=4) == sel  # same input -> same set


def test_select_holdout_ratio_within_ten_to_fifteen_percent():
    cands = [("A", f"{i:03d}") for i in range(62)]
    sel = h.select_holdout(cands, every=8)
    assert 0.10 <= len(sel) / len(cands) <= 0.15


def test_select_holdout_rejects_nonsense_stride():
    with pytest.raises(ValueError):
        h.select_holdout([("A", "T")], every=1)


def test_candidate_songs_includes_matched_gp_and_labeled(tmp_path):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    rows = [
        {"album": "A", "track": "matched", "match": "yes", "gp_path": str(gp)},
        {"album": "A", "track": "missing_gp", "match": "yes", "gp_path": str(tmp_path / "nope.gp5")},
        {"album": "A", "track": "unmatched", "match": "unknown", "gp_path": ""},
    ]
    sections = [{"album": "B", "track": "labeled", "role": "intro"}]
    assert h.candidate_songs(rows, sections) == [("A", "matched"), ("B", "labeled")]


def test_candidate_songs_missing_gp_column_uses_fallback(tmp_path):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    rows = [{"album": "A", "track": "T", "match": "yes", "gp": str(gp)}]
    assert h.candidate_songs(rows, []) == [("A", "T")]


def test_write_and_load_holdout_round_trip(tmp_path):
    h.write_holdout(tmp_path, {("B", "2"), ("A", "1")})
    assert h.load_holdout(tmp_path) == {("A", "1"), ("B", "2")}


def test_load_holdout_missing_file_is_empty(tmp_path):
    assert h.load_holdout(tmp_path) == set()


def test_load_holdout_skips_blank_rows(tmp_path):
    path = tmp_path / "data" / "holdout.csv"
    path.parent.mkdir(parents=True)
    path.write_text("album,track\nA,1\n,\nB,2\n", encoding="utf-8")
    assert h.load_holdout(tmp_path) == {("A", "1"), ("B", "2")}


def test_ensure_holdout_is_persisted_and_stable(tmp_path):
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    rows = [{"album": "A", "track": f"T{i:02d}", "match": "yes", "gp_path": str(gp)} for i in range(20)]

    first = h.ensure_holdout(tmp_path, rows)

    assert (tmp_path / "data" / "holdout.csv").exists()
    assert first == {("A", f"T{i:02d}") for i in range(0, 20, 8)}
    # a later call honors the already-written file, even with no rows supplied
    assert h.ensure_holdout(tmp_path, []) == first


def test_split_for_tags_val_only_for_reserved_songs():
    holdout = {("A", "1")}
    assert h.split_for("A", "1", holdout) == "val"
    assert h.split_for("A", "2", holdout) == "train"
    assert h.split_for(None, None, holdout) == "train"


def test_tag_mutates_record_with_split():
    rec = {"album": "A", "track": "1"}
    assert h.tag(rec, {("A", "1")}) is rec
    assert rec["split"] == "val"
