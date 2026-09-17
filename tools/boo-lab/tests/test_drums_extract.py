"""Tests for src/boo_lab/drums_extract.py's measured per-section confidence
signal (the documented classify_drum_onsets snare-undercount/cymbal-
over-read failure mode). Synthetic onsets only."""
from __future__ import annotations

from boo_lab import drums_extract as de


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
