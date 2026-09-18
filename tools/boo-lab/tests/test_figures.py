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


def test_bar_fp_ignores_octave():
    assert figures.bar_fp(_m([[48], [55]])) == figures.bar_fp(_m([[60], [67]]))


def test_bar_fp_chord_not_collapsed_to_top_note():
    assert figures.bar_fp(_m([[0, 7]])) != figures.bar_fp(_m([[7]]))


class _FragFp:
    def __init__(self, mi, pc, raw=None):
        self.measure_index = mi
        self.cell = [{"duration": 1.0, "is_rest": False}]
        self.chord_notes = [[pc]]
        self.deltas = []
        self.raw_marker = raw
        self.role = "riff"


def test_windowing_eight_identical_bars_is_one_ostinato():
    frags = [_FragFp(mi, 0) for mi in range(8)]
    slots = [(mi, mi * 2.0, mi + 1, 2.0) for mi in range(8)]

    wins = figures._song_windows(frags, slots)

    assert len(wins) == 1  # not seven sliding 2-bar windows
    assert wins[0]["n_bars"] == 8 and wins[0]["n_repeats"] == 8


def test_cluster_conflict_when_letter_maps_to_two_fingerprints():
    wins = [
        {"hash": "H1", "start": 0, "end": 2, "start_bar": 1, "end_bar": 1,
         "n_bars": 1, "letter": "A", "role": "riff"},
        {"hash": "H2", "start": 4, "end": 6, "start_bar": 3, "end_bar": 3,
         "n_bars": 1, "letter": "A", "role": "riff"},
        {"hash": "H2", "start": 8, "end": 10, "start_bar": 5, "end_bar": 5,
         "n_bars": 1, "letter": "A", "role": "riff"},
    ]

    clusters = figures.cluster_song(wins)

    assert all(c["conflict"] for c in clusters)
    assert {c["figure_id"] for c in clusters} == {"riff-A"}


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


class _Frag:
    def __init__(self, mi, pc=0):
        self.measure_index = mi
        self.cell = [{"duration": 1.0, "is_rest": False}]
        self.chord_notes = [[pc]]
        self.deltas = []


class _FakeBank:
    def extract_fragments_from_file(self, gp, song_title=None):
        # Alternate bars so the run windowing emits two matching 2-bar blocks.
        return [_Frag(mi, pc=(0 if mi % 2 == 0 else 5)) for mi in range(4)]


def _gated_lab(tmp_path, monkeypatch, sync_ok):
    from boo_lab import extract

    monkeypatch.setattr(extract, "_engine_riff_bank", lambda: _FakeBank())
    monkeypatch.setattr(figures, "_playback_slots",
                        lambda gp: [(mi, float(mi), mi + 1, 1.0) for mi in range(4)])
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    gp = tmp_path / "x.gp5"
    gp.write_bytes(b"x")
    (lab / "data" / "sync.jsonl").write_text(
        '{"album":"A","track":"T","sync_ok":%s}\n' % ("true" if sync_ok else "false"),
        encoding="utf-8",
    )
    figures.build_figures(lab, [{"album": "A", "track": "T",
                                 "gp_path": str(gp), "match": "yes"}])
    return figures.load_figures(lab, "A", "T")


def test_build_figures_omits_seconds_when_sync_not_ok(tmp_path, monkeypatch):
    rows = _gated_lab(tmp_path, monkeypatch, sync_ok=False)

    assert rows
    assert all(r["start"] is None and r["end"] is None for r in rows)
    assert all(r["times_trusted"] is False for r in rows)
    assert all(o["start"] is None and o["end"] is None
               for r in rows for o in r["occurrences"])
    assert all(r["start_bar"] is not None for r in rows)


def test_build_figures_keeps_seconds_when_sync_ok(tmp_path, monkeypatch):
    rows = _gated_lab(tmp_path, monkeypatch, sync_ok=True)

    assert rows
    assert all(r["times_trusted"] is True for r in rows)
    assert any(r["start"] is not None for r in rows)


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
