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


def _raise_ie(_p, **_k):
    raise ImportError("not installed")


def test_prefers_beats_this(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", lambda p: ([0.5, 1.0], [0.0], "beat_this"))
    monkeypatch.setattr(beats, "_allin1", lambda p, cache_dir=None: ([9.0], [9.0], "allin1"))

    report = beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 1
    rec = _rows(lab)[0]
    assert rec["source"] == "beat_this" and rec["beats"] == [0.5, 1.0]


def test_falls_back_to_allin1(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", _raise_ie)
    monkeypatch.setattr(beats, "_allin1", lambda p, cache_dir=None: ([1.0, 2.0], [0.0], "allin1"))

    beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    rec = _rows(lab)[0]
    assert rec["source"] == "allin1" and rec["beats"] == [1.0, 2.0] and rec["downbeats"] == [0.0]


def test_skips_when_no_tracker(tmp_path, monkeypatch):
    lab, flac = _lab(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", _raise_ie)
    monkeypatch.setattr(beats, "_allin1", _raise_ie)

    report = beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 0 and report["skipped"] == 1


def _existing(tmp_path):
    lab, flac = _lab(tmp_path)
    out = lab / "data" / "beats.jsonl"
    out.write_text(
        '{"album":"A","track":"T","beats":[1.0],"downbeats":[],"source":"beat_this"}\n',
        encoding="utf-8",
    )
    return lab, flac, out, out.read_text(encoding="utf-8")


def test_zero_rows_does_not_blank_existing_file(tmp_path):
    lab, flac, out, before = _existing(tmp_path)
    report = beats.build_beats(lab, [])
    assert report["written"] == 0
    assert out.read_text(encoding="utf-8") == before


def test_all_skipped_does_not_blank_existing_file(tmp_path, monkeypatch):
    lab, flac, out, before = _existing(tmp_path)
    monkeypatch.setattr(beats, "_beat_this", _raise_ie)
    monkeypatch.setattr(beats, "_allin1", _raise_ie)

    report = beats.build_beats(lab, [{"album": "A", "track": "T", "flac_path": str(flac)}])

    assert report["written"] == 0 and report["skipped"] == 1
    assert out.read_text(encoding="utf-8") == before


def test_album_mismatch_does_not_blank_existing_file(tmp_path):
    lab, flac, out, before = _existing(tmp_path)
    report = beats.build_beats(
        lab, [{"album": "A", "track": "T", "flac_path": str(flac)}], album="Nonexistent"
    )
    assert report["written"] == 0
    assert out.read_text(encoding="utf-8") == before


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

def test_build_beats_merges_without_wiping_other_albums(tmp_path, monkeypatch):
    """Rebuilding one album must not erase other albums in beats.jsonl."""
    import json
    from boo_lab import beats as B

    lab = tmp_path
    (lab / "data").mkdir(parents=True)
    existing = lab / "data" / "beats.jsonl"
    existing.write_text(
        json.dumps({"album": "A", "track": "1", "beats": [0.0], "downbeats": [],
                    "source": "beat_this"}) + "\n",
        encoding="utf-8",
    )
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"flac")

    def fake_track_beats(flac, cache_dir=None, lab_root=None):
        return [1.0, 2.0], [1.0], "beat_this"

    monkeypatch.setattr(B, "track_beats", fake_track_beats)
    B.build_beats(lab, [{"album": "B", "track": "2", "flac": str(flac)}])
    lines = [json.loads(l) for l in existing.read_text(encoding="utf-8").splitlines() if l.strip()]
    keys = {(r["album"], r["track"]) for r in lines}
    assert ("A", "1") in keys and ("B", "2") in keys


def test_track_beats_uses_disk_cache(tmp_path, monkeypatch):
    import json
    from boo_lab import beats as B

    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x" * 100)
    cache = B._beats_cache_path(tmp_path, flac)
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"beats": [0.5, 1.0], "downbeats": [0.5],
                                 "source": "beat_this"}), encoding="utf-8")
    calls = {"n": 0}

    def boom(flac):
        calls["n"] += 1
        raise AssertionError("should not call beat_this")

    monkeypatch.setattr(B, "_beat_this", boom)
    beats, downs, src = B.track_beats(flac, lab_root=tmp_path)
    assert calls["n"] == 0
    assert beats == [0.5, 1.0] and "cache" in src
