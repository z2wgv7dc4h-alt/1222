"""Tests for src/boo_lab/figures.py -- riff identity from fake cells/tmp labs.
No guitarpro, no FLAC, no network."""
from __future__ import annotations

import pytest

from boo_lab import figures


def _m(hits):
    """Fake one measure. `hits` is a list of pitch-class lists, or None for a
    rest. One hit per beat (duration 1.0), so onsets land on beats 0..3."""
    cell = []
    chord_notes = []
    for h in hits:
        if h is None:
            cell.append({"duration": 1.0, "is_rest": True})
        else:
            cell.append({"duration": 1.0, "is_rest": False})
            chord_notes.append(list(h))
    return {"cell": cell, "chord_notes": chord_notes, "deltas": []}


def test_hash_window_identical_cells_same_hash():
    a = _m([[0, 7], [5]])
    b = _m([[3], [10]])
    assert figures.hash_window([a, b]) == figures.hash_window([a, b])


def test_hash_window_octave_ignored():
    low = _m([[48], [55]])
    high = _m([[60], [67]])
    assert figures.hash_window([low]) == figures.hash_window([high])


def test_hash_window_different_pitch_classes_differ():
    assert figures.hash_window([_m([[0, 7]])]) != figures.hash_window([_m([[0, 8]])])


def test_hash_window_chord_does_not_collapse_to_top_note():
    two_note = _m([[0, 7]])
    top_only = _m([[7]])
    assert figures.hash_window([two_note]) != figures.hash_window([top_only])


def _w(h, start, bars=4, bar0=1):
    return {"hash": h, "start": start, "end": start + 8.0, "start_bar": bar0,
            "end_bar": bar0 + bars - 1, "n_bars": bars}


def test_cluster_song_identical_four_bar_hashes_one_cluster():
    clusters = figures.cluster_song([_w("H", 0.0), _w("H", 8.0), _w("H", 16.0)])

    assert len(clusters) == 1
    c = clusters[0]
    assert c["n_hits"] == 3 and c["figure_id"] == "riff-A" and c["unique"] is False


def test_cluster_song_two_hashes_lettered_by_start():
    clusters = figures.cluster_song([_w("Y", 10.0), _w("X", 0.0)])

    assert [c["figure_id"] for c in clusters] == ["riff-A", "riff-B"]
    assert clusters[0]["start"] == 0.0 and clusters[1]["start"] == 10.0
    assert clusters[0]["unique"] is True


def test_build_figures_zero_rows_does_not_blank_existing(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    out = lab / "data" / "figures.jsonl"
    out.write_text('{"album":"A","track":"T","figure_id":"riff-A"}\n', encoding="utf-8")
    before = out.read_text(encoding="utf-8")

    report = figures.build_figures(lab, [])

    assert report["written"] == 0
    assert out.read_text(encoding="utf-8") == before


def test_load_figures_filters_by_album_track(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "figures.jsonl").write_text(
        '{"album":"A","track":"T","figure_id":"riff-A"}\n'
        '{"album":"B","track":"U","figure_id":"riff-A"}\n',
        encoding="utf-8",
    )

    assert len(figures.load_figures(lab, "A", "T")) == 1
    assert figures.load_figures(lab, "A", "U") == []


def test_api_figures_returns_rows_for_selected_song(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from boo_lab import annotator as ann
    from boo_lab.catalogue import save_map

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac = tmp_path / "T.flac"
    flac.write_bytes(b"x")
    save_map(lab / "data" / "map.csv",
             [{"album": "A", "track": "T", "flac": str(flac), "gp": "",
               "match": "unknown"}])
    (lab / "data" / "figures.jsonl").write_text(
        '{"album":"A","track":"T","figure_id":"riff-A","n_hits":2}\n',
        encoding="utf-8",
    )

    client = TestClient(ann.create_app(lab, None, None))
    data = client.get("/api/figures/0").json()

    assert data["figures"][0]["figure_id"] == "riff-A"
