"""Tests for src/boo_lab/tempo_hints.py -- tempo-automation boundary hints.
No guitarpro, no FLAC, no network."""
from __future__ import annotations

from boo_lab import tempo_hints


def test_build_tempo_hints_writes_rows_for_bpm_changes(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        '{"album":"A","track":"T","sync_ok":true}\n', encoding="utf-8")

    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: object())
    monkeypatch.setattr(tn, "tempo_map",
                        lambda pack: [(0.0, 120.0), (10.0, 141.0), (20.0, 150.0)])

    report = tempo_hints.build_tempo_hints(lab, [{"album": "A", "track": "T"}])

    rows = tempo_hints.load_tempo_hints(lab, "A", "T")
    assert report["written"] == 2
    assert [(r["bpm_before"], r["bpm_after"], r["sec"]) for r in rows] == [
        (120.0, 141.0, 10.0), (141.0, 150.0, 20.0)]
    assert all(r["times_trusted"] is True and r["source"] == "tempo-automation" for r in rows)


def test_build_tempo_hints_single_tempo_writes_nothing(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: object())
    monkeypatch.setattr(tn, "tempo_map", lambda pack: [(0.0, 120.0)])  # start tempo only

    report = tempo_hints.build_tempo_hints(lab, [{"album": "A", "track": "T"}])

    assert report["written"] == 0
    assert tempo_hints.load_tempo_hints(lab, "A", "T") == []


def test_build_tempo_hints_zero_rows_does_not_blank_existing(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    out = lab / "data" / "tempo_hints.jsonl"
    out.write_text('{"album":"A","track":"T","sec":5.0}\n', encoding="utf-8")
    before = out.read_text(encoding="utf-8")

    report = tempo_hints.build_tempo_hints(lab, [])

    assert report["written"] == 0
    assert out.read_text(encoding="utf-8") == before


def test_untrusted_hints_hide_seconds_but_keep_bpm(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)  # no sync.jsonl -> not trusted
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: object())
    monkeypatch.setattr(tn, "tempo_map", lambda pack: [(0.0, 120.0), (10.0, 141.0)])

    tempo_hints.build_tempo_hints(lab, [{"album": "A", "track": "T"}])

    rows = tempo_hints.load_tempo_hints(lab, "A", "T")
    assert rows[0]["sec"] is None and rows[0]["times_trusted"] is False
    assert rows[0]["bpm_before"] == 120.0 and rows[0]["bpm_after"] == 141.0


def test_load_tempo_hints_filters_by_album_track(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "tempo_hints.jsonl").write_text(
        '{"album":"A","track":"T","sec":5.0}\n'
        '{"album":"B","track":"U","sec":7.0}\n',
        encoding="utf-8",
    )

    assert len(tempo_hints.load_tempo_hints(lab, "A", "T")) == 1
    assert tempo_hints.load_tempo_hints(lab, "A", "U") == []
