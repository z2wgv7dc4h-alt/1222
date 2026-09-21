"""Tests for src/boo_lab/figures.py -- riff identity from fake cells/tmp labs.
No guitarpro, no FLAC, no network."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from boo_lab import figures

FIX_DIR = Path(__file__).parent / "fixtures" / "tabnotes_tiny"


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


def test_tab_fragments_and_slots_from_fixture_pack():
    from boo_lab import tabnotes as tn

    pack = tn.load_pack(FIX_DIR)

    fragments, slots = figures._tab_fragments_and_slots(pack)

    assert slots == [(0, 1.0, 1, 2.0), (1, 3.0, 2, 2.0)]
    assert [f.measure_index for f in fragments] == [0, 1]
    assert all(f.track == "tabnotes" and f.instrument == "guitar" for f in fragments)
    assert fragments[0].cell == [
        {"duration": 1.0, "is_rest": False, "palm_mute": True},
        {"duration": 1.0, "is_rest": False},  # source event is hammer=True, but
        {"duration": 2.0, "is_rest": True},   # "hammer" isn't in RiffFragment's
    ]                                          # technique vocabulary (see its docstring)
    assert fragments[0].chord_notes == [[40], [42]]
    assert fragments[0].deltas == [0, 2]
    assert fragments[1].chord_notes == [[45], [47]]
    assert fragments[1].deltas == [0, 2]


def _pulse_pack():
    from boo_lab.tabnotes import TabEvent, TabMeasure, TabNotesPack, TabTrack

    tracks = [TabTrack(index=0, name="Guitar", category="guitar"),
              TabTrack(index=1, name="Synth", category="other")]
    measures = [
        TabMeasure(measure=0, start_ms=0.0, start_sec_audio=10.0, duration_ms=2000.0),
        TabMeasure(measure=1, start_ms=2000.0, start_sec_audio=12.0, duration_ms=2000.0),
        TabMeasure(measure=2, start_ms=4000.0, start_sec_audio=14.0, duration_ms=2000.0),
        TabMeasure(measure=3, start_ms=6000.0, start_sec_audio=16.0, duration_ms=2000.0),
    ]
    events = [
        TabEvent(track=1, measure=0, onset_beat=0.0, onset_ms=0.0, duration_ms=2000.0, pitch=40),
        TabEvent(track=1, measure=1, onset_beat=0.0, onset_ms=2000.0, duration_ms=2000.0, pitch=40),
        # measure 2 silent on the synth track -- splits the run.
        TabEvent(track=1, measure=3, onset_beat=0.0, onset_ms=6000.0, duration_ms=2000.0, pitch=40),
    ]
    return TabNotesPack(id="p", title="P", tracks=tracks, events=events, measures=measures)


def test_tab_pulse_windows_splits_on_gap_and_reports_bars():
    windows = figures._tab_pulse_windows(_pulse_pack())

    assert windows == [
        {"start": 10.0, "end": 14.0, "start_bar": 1, "end_bar": 2},
        {"start": 16.0, "end": 18.0, "start_bar": 4, "end_bar": 4},
    ]


def test_tab_pulse_windows_empty_without_other_track():
    from boo_lab.tabnotes import TabNotesPack, TabTrack

    pack = TabNotesPack(id="p", title="P",
                        tracks=[TabTrack(index=0, name="Guitar", category="guitar")])

    assert figures._tab_pulse_windows(pack) == []


def test_build_figures_emits_pulse_rows_even_without_riff_fragments(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "data" / "tabnotes").mkdir(parents=True)
    shutil.copytree(FIX_DIR, lab / "data" / "tabnotes" / "tabnotes_tiny")
    (lab / "data" / "sync.jsonl").write_text(
        '{"album":"Synthetic Album","track":"Tiny Pack","sync_ok":true}\n', encoding="utf-8")

    # No usable guitar fragments at all -- proves Pulse doesn't depend on
    # riff-figure extraction succeeding.
    monkeypatch.setattr(figures, "_tab_fragments_and_slots", lambda pack: (None, None))
    monkeypatch.setattr(figures, "_tab_pulse_windows",
                        lambda pack: [{"start": 5.0, "end": 9.0, "start_bar": 3, "end_bar": 5}])

    report = figures.build_figures(lab, [{"album": "Synthetic Album", "track": "Tiny Pack",
                                          "gp_path": "", "match": "no"}])

    rows = figures.load_figures(lab, "Synthetic Album", "Tiny Pack")
    pulses = [r for r in rows if r.get("role") == "pulse"]
    assert report["skipped"] == 0
    assert len(pulses) == 1
    p = pulses[0]
    assert p["figure_id"] == "pulse-A"
    assert p["start"] == 5.0 and p["end"] == 9.0
    assert p["start_bar"] == 3 and p["end_bar"] == 5
    assert p["times_trusted"] is True
    assert p["note_source"] == "tabnotes"


def _two_guitar_pack():
    from boo_lab.tabnotes import TabEvent, TabMeasure, TabNotesPack, TabTrack

    # track 0 = lowest mean pitch (picked as the primary/unprefixed guitar);
    # track 1 = a second guitar track, currently discarded before this ticket.
    tracks = [TabTrack(index=0, name="Rhythm A", category="guitar"),
              TabTrack(index=1, name="Rhythm B", category="guitar")]
    measures = [TabMeasure(measure=i, start_ms=i * 1000.0, start_sec_audio=float(i),
                           duration_ms=1000.0, length_beats=1.0) for i in range(4)]
    events = []
    for i in range(4):
        events.append(TabEvent(track=0, measure=i, onset_beat=0.0, onset_ms=i * 1000.0,
                               duration_beats=1.0, duration_ms=1000.0,
                               pitch=(28 if i % 2 == 0 else 33)))
        events.append(TabEvent(track=1, measure=i, onset_beat=0.0, onset_ms=i * 1000.0,
                               duration_beats=1.0, duration_ms=1000.0,
                               pitch=(60 if i % 2 == 0 else 65)))
    return TabNotesPack(id="p", title="P", tracks=tracks, events=events, measures=measures)


def test_build_figures_clusters_a_second_guitar_track_separately(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        '{"album":"A","track":"T","sync_ok":true}\n', encoding="utf-8")

    pack = _two_guitar_pack()
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: pack)

    figures.build_figures(lab, [{"album": "A", "track": "T", "gp_path": "", "match": "no"}])

    rows = figures.load_figures(lab, "A", "T")
    primary = [r for r in rows if r.get("instrument") == "guitar" and "track_index" not in r]
    extra = [r for r in rows if r.get("track_index") == 1]
    assert primary and all(not r["figure_id"].startswith("guitar1-") for r in primary)
    assert extra and all(r["figure_id"].startswith("guitar1-") for r in extra)
    assert all(r["instrument"] == "guitar" and r["note_source"] == "tabnotes" for r in extra)


def _bass_pack():
    from boo_lab.tabnotes import TabEvent, TabMeasure, TabNotesPack, TabTrack

    tracks = [TabTrack(index=0, name="Guitar", category="guitar"),
              TabTrack(index=1, name="Bass", category="bass")]
    measures = [TabMeasure(measure=i, start_ms=i * 1000.0, start_sec_audio=float(i),
                           duration_ms=1000.0, length_beats=1.0) for i in range(4)]
    # Alternating pitch so bars 0/2 and 1/3 each form a real n_hits=2 cluster.
    events = [TabEvent(track=1, measure=i, onset_beat=0.0, onset_ms=i * 1000.0,
                       duration_beats=1.0, duration_ms=1000.0,
                       pitch=(28 if i % 2 == 0 else 33)) for i in range(4)]
    return TabNotesPack(id="p", title="P", tracks=tracks, events=events, measures=measures)


def test_build_figures_emits_bass_cluster_with_prefixed_id(tmp_path, monkeypatch):
    from boo_lab import tabnotes as tn

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text(
        '{"album":"A","track":"T","sync_ok":true}\n', encoding="utf-8")

    pack = _bass_pack()
    monkeypatch.setattr(tn, "discover_pack", lambda lab_root, album, track: "fake-path")
    monkeypatch.setattr(tn, "load_pack", lambda path: pack)

    figures.build_figures(lab, [{"album": "A", "track": "T", "gp_path": "", "match": "no"}])

    rows = figures.load_figures(lab, "A", "T")
    bass_rows = [r for r in rows if r.get("instrument") == "bass"]
    assert bass_rows
    assert all(r["figure_id"].startswith("bass-") for r in bass_rows)
    assert all(r["times_trusted"] is True and r["note_source"] == "tabnotes"
              for r in bass_rows)
    # The (event-less) guitar track produced no rows -- proves bass doesn't
    # depend on the guitar path succeeding, same decoupling as Pulse.
    assert not [r for r in rows if r.get("instrument") == "guitar"]


def test_build_figures_prefers_tabnotes_pack_over_gp(tmp_path, monkeypatch):
    from boo_lab import extract

    lab = tmp_path / "lab"
    (lab / "data" / "tabnotes").mkdir(parents=True)
    shutil.copytree(FIX_DIR, lab / "data" / "tabnotes" / "tabnotes_tiny")

    # Alternating-bar fake fragments so clustering yields real n_hits>=2
    # clusters, same pattern `_gated_lab` above already uses for the GP path.
    fake_frags = [_Frag(mi, pc=(0 if mi % 2 == 0 else 5)) for mi in range(4)]
    fake_slots = [(mi, float(mi), mi + 1, 1.0) for mi in range(4)]
    monkeypatch.setattr(
        figures, "_tab_fragments_and_slots",
        lambda pack, category="guitar", track=None:
            (fake_frags, fake_slots) if category == "guitar" else (None, None))

    def _boom():
        raise AssertionError("GP path must not run when a tabnotes pack exists")
    monkeypatch.setattr(extract, "_engine_riff_bank", _boom)

    gp = tmp_path / "unused.gp5"
    gp.write_bytes(b"x")
    report = figures.build_figures(lab, [{"album": "Synthetic Album", "track": "Tiny Pack",
                                          "gp_path": str(gp), "match": "yes"}])

    rows = figures.load_figures(lab, "Synthetic Album", "Tiny Pack")
    assert report["written"] > 0
    assert rows and all(r["note_source"] == "tabnotes" for r in rows)


def test_build_figures_gp_marker_spine_beats_a_discovered_pack(tmp_path, monkeypatch):
    guitarpro = pytest.importorskip("guitarpro")
    from gp_fixtures import make_song, make_track

    from boo_lab import guess as g

    lab = tmp_path / "lab"
    (lab / "data" / "tabnotes").mkdir(parents=True)
    shutil.copytree(FIX_DIR, lab / "data" / "tabnotes" / "tabnotes_tiny")
    (lab / "data" / "sync.jsonl").write_text(
        json.dumps({"album": "A", "track": "Tiny Pack", "sync_ok": True}) + "\n",
        encoding="utf-8")

    song = make_song(4, markers={0: "Verse"}, title="Fixture")
    track = make_track(song, 1, {0: [40], 1: [45], 2: [40], 3: [45]}, instrument=30)
    song.tracks = [track]
    gp = tmp_path / "fixture.gp5"
    guitarpro.write(song, str(gp))

    monkeypatch.setattr(g, "_prefer_tab", lambda p, track: p)

    report = figures.build_figures(lab, [{"album": "A", "track": "Tiny Pack",
                                          "gp_path": str(gp), "match": "yes"}])

    rows = figures.load_figures(lab, "A", "Tiny Pack")
    assert report["written"] > 0
    assert rows and all(r["note_source"] == "gp" for r in rows)


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


def test_emit_clusters_includes_unique_one_shot_runs():
    """Through-composed packs must still write unique bar-run rows."""
    rows = []
    windows = [
        {"hash": "A", "n_bars": 2, "start": 0.0, "end": 3.3,
         "start_bar": 1, "end_bar": 2, "letter": None, "role": "riff"},
        {"hash": "B", "n_bars": 2, "start": 3.3, "end": 6.6,
         "start_bar": 3, "end_bar": 4, "letter": None, "role": "riff"},
        {"hash": "A", "n_bars": 2, "start": 6.6, "end": 9.9,
         "start_bar": 5, "end_bar": 6, "letter": None, "role": "riff"},
    ]
    clusters = figures._emit_clusters(
        rows, windows, album="Alb", track="Trk", trusted=True,
        note_source="tabnotes", instrument="guitar",
    )
    assert len(clusters) == 2  # A repeats, B unique
    by_id = {r["figure_id"]: r for r in rows}
    assert by_id["riff-A"]["n_hits"] == 2 and by_id["riff-A"]["unique"] is False
    assert by_id["riff-B"]["n_hits"] == 1 and by_id["riff-B"]["unique"] is True
    assert by_id["riff-B"]["times_trusted"] is True
