"""Tests for src/boo_lab/learn.py -- fake compare.json + tmp lab_root.
No FLAC, no torch, no network."""
from __future__ import annotations

import json

from boo_lab import learn


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    return lab


def _track(album, track, source, f05, n_keep=2, n_draft=2, split="train", role3=1.0):
    return {
        "album": album, "track": track, "source": source, "split": split,
        "n_keep": n_keep, "n_draft": n_draft,
        "precision_0_5": f05, "recall_0_5": f05, "f_0_5": f05,
        "precision_3_0": f05, "recall_3_0": f05, "f_3_0": f05,
        "role_agree_3_0": role3, "hit_pairs_3_0": n_keep,
    }


def _write_compare(lab, tracks):
    (lab / "data" / "compare.json").write_text(
        json.dumps({"tracks": tracks, "micro": {}}), encoding="utf-8")


def test_fewer_than_five_voted_songs_is_none(tmp_path):
    lab = _lab(tmp_path)
    _write_compare(lab, [_track("A", "T%d" % i, "guess", 0.99) for i in range(4)])

    rank = learn.build_rank(lab)

    assert rank["prefer"] == "none"
    assert rank["scores"]["guess"]["n"] == 4


def test_five_songs_prefers_the_higher_f05(tmp_path):
    lab = _lab(tmp_path)
    _write_compare(lab, [_track("A", "T%d" % i, "guess", 0.75) for i in range(5)]
                   + [_track("A", "T%d" % i, "msa-draft", 0.50) for i in range(5)])

    rank = learn.build_rank(lab)

    assert rank["prefer"] == "guess"
    assert rank["n_voted"] == 5
    assert rank["scores"]["guess"]["f05"] == 0.75
    assert rank["scores"]["guess"]["f05"] > rank["scores"]["msa-draft"]["f05"]


def test_holdout_scores_do_not_vote(tmp_path):
    lab = _lab(tmp_path)
    _write_compare(lab, [_track("A", "G%d" % i, "guess", 0.70) for i in range(5)]
                   + [_track("H", "H%d" % i, "msa-draft", 0.99, split="holdout") for i in range(20)])

    rank = learn.build_rank(lab)

    assert rank["prefer"] == "guess"          # holdout msa-draft ignored
    assert "msa-draft" not in rank["scores"]  # never a voter
    assert rank["holdout"]["msa-draft"]["n"] == 20
    assert rank["n_voted"] == 5


def test_run_learn_does_not_touch_sections_jsonl(tmp_path):
    lab = _lab(tmp_path)
    sec = lab / "data" / "sections.jsonl"
    sec.write_text(
        '{"album":"A","track":"T","role":"riff","source":"human","heard":true,"start":0,"end":1}\n',
        encoding="utf-8",
    )
    before = sec.read_text(encoding="utf-8")
    _write_compare(lab, [_track("A", "T%d" % i, "guess", 0.70) for i in range(5)])

    learn.run_learn(lab)

    assert sec.read_text(encoding="utf-8") == before


def test_record_never_raises_when_the_lab_path_is_broken(tmp_path):
    broken = tmp_path / "afile"
    broken.write_text("not a directory", encoding="utf-8")

    assert learn.record(broken, "policy", prefer="guess") is None


def test_record_appends_one_event(tmp_path):
    lab = _lab(tmp_path)

    learn.record(lab, "policy", album="A", track="T", prefer="guess")

    rows = [json.loads(line) for line in
            (lab / "data" / "learn.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["kind"] == "policy"
    assert rows[0]["album"] == "A" and rows[0]["payload"]["prefer"] == "guess"


def test_preferred_source_reads_none(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "intern_rank.json").write_text('{"prefer":"none"}\n', encoding="utf-8")
    assert learn.preferred_source(lab) is None
    assert learn.preferred_source(tmp_path / "missing") is None
