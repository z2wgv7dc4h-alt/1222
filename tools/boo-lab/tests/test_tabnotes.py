"""Tests for src/boo_lab/tabnotes.py -- the local tab-notes pack reader.

All fixtures are hand-made synthetic packs under tests/fixtures/; no
commercial tab (The New Reign / s32187 etc.) is vendored.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from boo_lab import tabnotes as tn

FIX_DIR = Path(__file__).parent / "fixtures" / "tabnotes_tiny"
FIX_ZIP = Path(__file__).parent / "fixtures" / "tabnotes_tiny.zip"


def test_zip_and_folder_load_identically():
    z = tn.load_pack(FIX_ZIP)
    f = tn.load_pack(FIX_DIR)

    assert z.title == f.title == "Tiny Pack"
    assert z.artist == f.artist == "Synthetic"
    assert len(z.events) == len(f.events) == 6
    assert tn.onsets_audio(z, category="guitar") == tn.onsets_audio(f, category="guitar")


def test_audio_sec_first_guitar_is_the_timeline_start():
    pack = tn.load_pack(FIX_DIR)
    guitar = tn.events_for(pack, category="guitar")

    assert pack.audio_sec(guitar[0]) == pytest.approx(1.0)
    assert tn.onsets_audio(pack, category="guitar")[:3] == [1.0, 1.5, 3.0]


def test_tracks_tuning_by_track_and_raw_detail():
    pack = tn.load_pack(FIX_DIR)

    assert [(t.index, t.name, t.category) for t in pack.tracks] == [
        (0, "Guitar", "guitar"), (1, "Drums", "drums")]
    assert tn.tuning_of(pack, 0) == [40, 45, 50, 55, 59, 64]
    by_track = tn.onsets_audio_by_track(pack)
    assert by_track[0] == [1.0, 1.5, 3.0, 3.5]
    assert by_track[1] == [1.0, 3.0]
    # raw/ parsed too: the tuplet beat and the bend-points pair
    assert any(b.tuplet for b in pack.raw_beats)
    assert any(n.bend_points for b in pack.raw_beats for n in b.notes)


def test_clocks_and_video_points():
    pack = tn.load_pack(FIX_DIR)

    assert pack.notated_total_ms == 4000.0
    assert pack.audio_total_sec == pytest.approx(5.0)
    assert pack.clock_ratio == pytest.approx(1.0)
    assert pack.video_points == [1.0, 3.0]
    assert pack.measures[1].video_sec == 3.0


def test_tempo_map_and_bar_fingerprint():
    pack = tn.load_pack(FIX_DIR)

    assert tn.tempo_map(pack) == [(1.0, 120.0)]
    # Full MIDI pitch + in-bar 16th onset/dur + articulation (not pitch-class sludge)
    assert tn.bar_fp_tab(pack, 0, 0) == "0:4:40:p|4:4:42:h"
    assert tn.bar_fp_tab(pack, 1, 0) == "0:4:45:-|4:4:47:d"


def test_bar_fp_tab_onset_pitch_chord_collapse():
    """Same-onset chord notes collapse; duration floors at 1 sixteenth."""
    from types import SimpleNamespace

    pack = SimpleNamespace(
        measures=[SimpleNamespace(measure=0, time_signature="4/4", length_beats=4.0)],
        events=[
            SimpleNamespace(
                measure=0, track=0, category="guitar",
                onset_beat=0.0, onset_ms=0.0, duration_beats=0.5,
                pitch=40, palm_mute=True, dead=False, hammer=False,
            ),
            SimpleNamespace(
                measure=0, track=0, category="guitar",
                onset_beat=0.0, onset_ms=0.0, duration_beats=0.5,
                pitch=47, palm_mute=True, dead=False, hammer=False,
            ),
            SimpleNamespace(
                measure=0, track=0, category="guitar",
                onset_beat=0.25, onset_ms=125.0, duration_beats=0.125,
                pitch=42, palm_mute=False, dead=False, hammer=False,
            ),
        ],
        tracks=[],
    )
    fp = tn.bar_fp_tab(pack, 0, 0)
    assert fp == "0:2:40,47:p,p|1:1:42:-"


def test_cli_prints_summary(capsys):
    from boo_lab import cli

    assert cli.main(["tabnotes", "--path", str(FIX_DIR)]) == 0
    out = capsys.readouterr().out
    assert "Tiny Pack" in out
    assert "guitar=1 drums=1 other=0" in out
    assert "raw tuplets=1 bends_with_points=1" in out
    assert "first guitar audio onsets: [1.0, 1.5, 3.0]" in out


def test_cli_json_round_trips(capsys):
    from boo_lab import cli

    assert cli.main(["tabnotes", "--path", str(FIX_ZIP), "--json"]) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["title"] == "Tiny Pack" and len(obj["events"]) == 6


def test_append_index_writes_only_its_file(tmp_path):
    pack = tn.load_pack(FIX_DIR)

    path = tn.append_index(tmp_path, pack)

    assert path == tmp_path / "data" / "tabnotes_index.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert recs[0]["title"] == "Tiny Pack" and recs[0]["tracks"] == 2
    assert not (tmp_path / "data" / "sections.jsonl").exists()


def test_is_pack_detects_only_tabnotes(tmp_path):
    assert tn.is_pack(FIX_DIR) is True
    assert tn.is_pack(FIX_ZIP) is True

    plain = tmp_path / "x.zip"
    with zipfile.ZipFile(plain, "w") as z:
        z.writestr("a.txt", "hi")
    assert tn.is_pack(plain) is False
    # the GP fixture is a zip too, but not a tab-notes pack
    assert tn.is_pack(Path(__file__).parent / "fixtures" / "tiny.gp") is False


def test_safe_id():
    assert tn.safe_id("Tiny Pack!") == "tiny_pack"
    assert tn.safe_id("") == "pack"


def test_ingest_detects_tabnotes_zip(tmp_path):
    from boo_lab.ingest import ingest

    drop = tmp_path / "drop"
    (drop / "album").mkdir(parents=True)
    shutil.copy(FIX_ZIP, drop / "album" / "tabnotes_tiny.zip")
    (drop / "album" / "Dummy.flac").write_bytes(b"not really audio")
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)

    report = ingest(drop, tmp_path / "corpus", tmp_path / "gp", "Synthetic", lab_root=lab)

    dest = lab / "data" / "tabnotes" / "tabnotes_tiny"
    assert (dest / "notes.json").exists()
    pack = tn.load_pack(dest)                     # parses without any FLAC
    assert pack.title == "Tiny Pack" and len(pack.tracks) == 2
    assert report["tabnotes"] == 1
    # never copied into the FLAC/GP roots
    assert not (tmp_path / "corpus" / "Synthetic" / "album" / "notes.json").exists()
    # index row written; no keepers anywhere
    assert (lab / "data" / "tabnotes_index.jsonl").exists()
    assert not (lab / "data" / "sections.jsonl").exists()


def test_sync_prefers_the_tabnotes_pack(tmp_path, monkeypatch):
    from boo_lab import sync
    from boo_lab.catalogue import save_map

    lab = tmp_path / "lab"
    (lab / "data" / "tabnotes").mkdir(parents=True)
    shutil.copytree(FIX_DIR, lab / "data" / "tabnotes" / "tabnotes_tiny")
    flac = tmp_path / "x.flac"
    flac.write_bytes(b"x")
    save_map(lab / "data" / "map.csv", [
        {"album": "Synthetic Album", "track": "Tiny Pack", "gp": "", "flac": str(flac)}])

    pack = tn.load_pack(FIX_DIR)
    onsets = tn.onsets_audio(pack, category="guitar")
    monkeypatch.setattr(sync, "audio_envelope",
                        lambda p: (sync.envelope_from_times(onsets, 400, 0.01), 0.01))
    monkeypatch.setattr(sync, "audio_chroma",
                        lambda p: (_ for _ in ()).throw(RuntimeError("no chroma")))
    monkeypatch.setattr(sync, "gp_onset_times",
                        lambda p: (_ for _ in ()).throw(AssertionError("gp must not be used")))

    rec = sync.sync_track(lab, "Synthetic Album", "Tiny Pack")

    assert rec["tabnotes"].endswith("tabnotes_tiny")
    assert rec["tabnotes_tracks"] == 2
    assert "tabnotes" in rec["note"]
    assert rec["sync_ok"] is True


def test_bar_events_accepts_tabmeasure_object():
    """Regression: comparing TabMeasure to int left every bar_fp empty."""
    from types import SimpleNamespace
    from boo_lab.tabnotes import bar_events, TabEvent

    pack = SimpleNamespace(events=[
        SimpleNamespace(measure=3, track=1, category="guitar", pitch=40,
                        duration_beats=1.0, palm_mute=False, dead=False, hammer=False,
                        onset_beat=0, onset_ms=0),
    ])
    # monkeypatch events_for used inside bar_events
    import boo_lab.tabnotes as tn

    def fake_events_for(pack, category=None, track=None):
        return list(pack.events)

    tn.events_for = fake_events_for
    m = SimpleNamespace(measure=3)
    got = tn.bar_events(pack, m, track=1)
    assert len(got) == 1
    assert tn.bar_events(pack, 3, track=1)[0].measure == 3
