"""Tests for src/boo_lab/beats.py -- beat_this vs allin1 dispatch. Intern
APIs are mocked; no torch/beat_this/allin1 required."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import beats


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    flac = tmp_path / "T.flac"
    flac.write_bytes(b"x")
    return lab, flac


def _rows(lab):
    path = lab / "data" / "beats.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _raise_ie(_p):
    raise ImportError("not installed")


def test_prefers_beats_this(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", lambda p: ([0.5, 1.0], [0.0], "beat_this"))
    monkeypatch.setattr(beats, "_allin1", lambda p: ([9.0], [9.0], "allin1"))

    report = beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 1
    rec = _rows(lab)[0]
    assert rec["source"] == "beat_this" and rec["beats"] == [0.5, 1.0]


def test_falls_back_to_allin1(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", _raise_ie)
    monkeypatch.setattr(beats, "_allin1", lambda p: ([1.0, 2.0], [0.0], "allin1"))

    beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    rec = _rows(lab)[0]
    assert rec["source"] == "allin1" and rec["beats"] == [1.0, 2.0] and rec["downbeats"] == [0.0]


def test_skips_when_no_tracker(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", _raise_ie)
    monkeypatch.setattr(beats, "_allin1", _raise_ie)

    report = beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 0 and report["skipped"] == 1


def test_album_filter_and_missing_flac(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", lambda p: ([1.0], [0.0], "beat_this"))
    rows = [
        {"album": "A", "track": "T", "flac_path": str(flac)},
        {"album": "B", "track": "U", "flac_path": str(flac)},
        {"album": "A", "track": "V", "flac_path": str(tmp_path / "nope.flac")},
    ]

    report = beats.build_beats(lab, rows, album="A")

    assert report["written"] == 1 and report["skipped"] == 1
    assert _rows(lab)[0]["album"] == "A"
