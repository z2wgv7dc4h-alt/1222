"""Tests for src/boo_lab/drums_extract.py's measured per-section confidence
signal (the documented classify_drum_onsets snare-undercount/cymbal-
over-read failure mode). Synthetic onsets only."""
from __future__ import annotations

import json

import pytest

from boo_lab import drums_extract as de


def test_build_drum_patterns_write_failure_leaves_prior_file(tmp_path, monkeypatch):
    from boo_lab import schema

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    out = lab / "data" / "drum_patterns.jsonl"
    out.write_text(json.dumps({"album": "A", "track": "T", "role": "riff", "onsets": []}) + "\n", encoding="utf-8")
    before = out.read_text(encoding="utf-8")

    def _boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(schema, "write_jsonl_atomic", _boom)
    with pytest.raises(OSError):
        de.build_drum_patterns(lab, [], lab / "work" / "stems")

    assert out.read_text(encoding="utf-8") == before  # atomic write failed safely


def test_build_drum_patterns_ignores_non_keeper_rows(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 5.0, "role": "riff", "source": "human", "heard": True}) + "\n"
        + json.dumps({"album": "A", "track": "T", "start": 6.0, "end": 9.0, "role": "intro", "source": "msa-draft"}) + "\n",
        encoding="utf-8",
    )
    report = de.build_drum_patterns(lab, [], lab / "work" / "stems")
    assert report["sections"] == 1  # the msa-draft row is not a labeled section
    rows = [json.loads(l) for l in (lab / "data" / "drum_patterns.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["role"] == "riff"


def _onsets(*roles):
    return [{"time": i * 0.5, "role": r} for i, r in enumerate(roles)]


def test_balanced_section_not_flagged():
    conf = de._drum_confidence(_onsets("kick", "snare", "hihat", "kick", "snare", "hihat"))
    assert conf["low_confidence"] is False
    assert conf["drum_class_counts"] == {"kick": 2, "snare": 2, "hihat": 2}
    assert conf["hihat_snare_ratio"] == 1.0
    assert "confidence_reason" not in conf


def test_zero_snare_with_many_hihat_is_flagged():
    conf = de._drum_confidence(_onsets(*(["hihat"] * 20), *(["kick"] * 5)))
    assert conf["low_confidence"] is True
    assert conf["drum_class_counts"]["snare"] == 0
    assert conf["hihat_snare_ratio"] is None
    assert "0 snare" in conf["confidence_reason"]


def test_extreme_ratio_is_flagged():
    conf = de._drum_confidence(_onsets(*(["hihat"] * 20), "snare"))  # 20:1
    assert conf["low_confidence"] is True
    assert conf["hihat_snare_ratio"] == 20.0
    assert "20.0:1" in conf["confidence_reason"]


def test_few_hihat_below_min_is_not_flagged():
    conf = de._drum_confidence(_onsets(*(["hihat"] * 3)))
    assert conf["low_confidence"] is False


def test_empty_onsets_not_flagged():
    conf = de._drum_confidence([])
    assert conf["low_confidence"] is False
    assert conf["hihat_snare_ratio"] is None
    assert conf["drum_class_counts"] == {"kick": 0, "snare": 0, "hihat": 0}


def test_unknown_role_is_ignored_in_counts():
    conf = de._drum_confidence(_onsets("kick", "tom", "snare"))
    assert conf["drum_class_counts"]["kick"] == 1
    assert conf["drum_class_counts"]["snare"] == 1
    assert conf["drum_class_counts"]["hihat"] == 0
