"""Tests for src/boo_lab/jams_export.py -- keeper-only JAMS 0.3 export with
figure/function layers. Synthetic sections under tmp_path; no real audio."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from boo_lab import jams_export
from boo_lab.holdout import write_holdout


def _lab(tmp_path, boxes):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True, exist_ok=True)
    (lab / "data" / "sections.jsonl").write_text(
        "".join(json.dumps(b) + "\n" for b in boxes), encoding="utf-8"
    )
    return lab


def _box(role, start, end, source="human", heard=True, figure_id=None):
    return {"album": "A", "track": "T", "start": start, "end": end, "role": role,
            "source": source, "heard": heard, "figure_id": figure_id or (role + "-A")}


def test_export_splits_layers_and_skips_drafts(tmp_path):
    lab = _lab(tmp_path, [
        _box("riff", 0, 4, figure_id="riff-A"),
        _box("breakdown", 4, 8, figure_id="breakdown-A"),
        _box("hook", 8, 12, source="msa-draft", figure_id="hook-A"),   # not a keeper
        _box("solo", 12, 16, heard=False, figure_id="solo-A"),          # unheard
    ])
    out = tmp_path / "out"

    report = jams_export.export_jams(lab, out)

    assert report["written"] == 1
    files = list(out.glob("*.jams"))
    assert len(files) == 1
    jam = json.loads(files[0].read_text(encoding="utf-8"))

    by_ns = {a["namespace"]: a for a in jam["annotations"]}
    assert [o["value"]["role"] for o in by_ns["segment_lab_figure"]["data"]] == ["riff"]
    assert [o["value"]["role"] for o in by_ns["segment_lab_function"]["data"]] == ["breakdown"]

    obs = by_ns["segment_lab_figure"]["data"][0]
    assert obs["time"] == 0.0 and obs["duration"] == 4.0
    assert obs["value"]["figure_id"] == "riff-A" and obs["confidence"] == 1.0

    assert jam["file_metadata"]["title"] == "T"
    assert jam["file_metadata"]["artist"] == "A"
    assert jam["sandbox"]["source"] == "boo-lab"


def test_export_skips_holdout_songs(tmp_path):
    lab = _lab(tmp_path, [_box("riff", 0, 4)])
    write_holdout(lab, {("A", "T")})
    out = tmp_path / "out"

    report = jams_export.export_jams(lab, out)

    assert report["written"] == 0
    assert report["skipped_val"] == 1
    assert list(out.glob("*.jams")) == []


def test_export_empty_when_no_keepers(tmp_path):
    lab = _lab(tmp_path, [_box("riff", 0, 4, source="guess", heard=False)])
    out = tmp_path / "out"
    report = jams_export.export_jams(lab, out)
    assert report["written"] == 0 and report["skipped_val"] == 0


def test_export_jam_one_writes_per_album_path(tmp_path):
    lab = _lab(tmp_path, [_box("riff", 0, 4)])

    res = jams_export.export_jam_one(lab, "A", "T", out_dir=tmp_path / "work" / "jams")

    assert res["written"] == 1
    dest = Path(res["path"])
    assert dest.name == "T.jams" and dest.parent.name == "A"


def test_export_jam_one_refuses_no_keepers(tmp_path):
    lab = _lab(tmp_path, [_box("riff", 0, 4, source="guess", heard=False)])

    res = jams_export.export_jam_one(lab, "A", "T")

    assert res["written"] == 0 and "no keepers" in res["reason"]


def test_export_jam_one_refuses_val(tmp_path):
    lab = _lab(tmp_path, [_box("riff", 0, 4)])
    write_holdout(lab, {("A", "T")})

    res = jams_export.export_jam_one(lab, "A", "T")

    assert res["written"] == 0 and "VAL" in res["reason"]


def test_api_jams_writes_for_keepers_and_refuses_empty(tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from boo_lab import annotator as ann
    from boo_lab.catalogue import save_map

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac = tmp_path / "T.flac"
    flac.write_bytes(b"x")
    save_map(lab / "data" / "map.csv", [
        {"album": "A", "track": "T", "flac": str(flac), "gp": "", "match": "unknown"},
        {"album": "A", "track": "U", "flac": str(flac), "gp": "", "match": "unknown"},
    ])
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff", "source": "human",
                    "heard": True, "start": 0.0, "end": 4.0}) + "\n", encoding="utf-8")
    write_holdout(lab, {("A", "U")})  # keep T train, U val

    client = TestClient(ann.create_app(lab, None, None))
    ok = client.post("/api/jams/0")
    empty = client.post("/api/jams/1")

    assert ok.status_code == 200 and Path(ok.json()["written"]).name == "T.jams"
    assert empty.status_code == 409
