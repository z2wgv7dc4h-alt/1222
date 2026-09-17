"""Tests for src/boo_lab/annotator.py -- canonical role handling, safe
track-id resolution, and the new split/stem/analysis endpoints. Synthetic
lab under tmp_path; no real corpus/audio."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from boo_lab import annotator as ann  # noqa: E402
from boo_lab.catalogue import save_map  # noqa: E402


def test_canonical_role_maps_legacy_and_defaults():
    assert ann.canonical_role("verse") == "riff"
    assert ann.canonical_role("Chorus") == "hook"
    assert ann.canonical_role("interlude") == "chill"
    assert ann.canonical_role("riff") == "riff"
    assert ann.canonical_role(None) == "riff"
    assert ann.canonical_role("bogus") == "riff"


def test_every_canonical_role_maps_to_itself():
    assert all(ann.canonical_role(r) == r for r in ann.ROLES)


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac = tmp_path / "audio" / "T.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"x")
    save_map(
        lab / "data" / "map.csv",
        [{"album": "A", "track": "T", "year": "", "flac": str(flac),
          "gp": "", "tuning": "drop_g_7", "match": "unknown", "notes": ""}],
    )
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 5.0,
                    "role": "verse", "source": "human"}) + "\n",
        encoding="utf-8",
    )
    stem = lab / "work" / "stems" / "htdemucs_6s" / "T" / "guitar.wav"
    stem.parent.mkdir(parents=True)
    stem.write_bytes(b"RIFF")
    (lab / "data" / "drum_patterns.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff", "start": 0.0,
                    "end": 5.0, "split": "train", "low_confidence": True,
                    "confidence_reason": "test reason",
                    "drum_class_counts": {"kick": 1, "snare": 0, "hihat": 9},
                    "hihat_snare_ratio": None, "onsets": []}) + "\n",
        encoding="utf-8",
    )
    return lab


def test_tracks_expose_split_and_available_stems(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    data = client.get("/api/tracks").json()
    assert data["roles"] == ann.ROLES
    assert data["tracks"], "expected one track"
    t = data["tracks"][0]
    assert "guitar" in t["stems"]
    assert t["split"] in {"train", "val"}


def test_sections_legacy_role_is_canonicalized_on_read_and_write(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    got = client.get("/api/sections/%d" % tid).json()
    assert got[0]["role"] == "riff"  # stored legacy "verse"

    resp = client.post("/api/sections/%d" % tid, json={"sections": [{"role": "chorus", "start": 0.0, "end": 2.0}]})
    assert resp.status_code == 200 and resp.json()["saved"] == 1
    saved = [json.loads(l) for l in (lab / "data" / "sections.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert saved[0]["role"] == "hook"


def test_stem_endpoint_serves_known_and_rejects_unknown(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    assert client.get("/api/stem/%d/guitar" % tid).status_code == 200
    assert client.get("/api/stem/%d/bogus" % tid).status_code == 404


def test_analysis_endpoint_returns_measured_confidence(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    secs = client.get("/api/analysis/%d" % tid).json()["sections"]
    assert secs and secs[0]["low_confidence"] is True
    assert secs[0]["drum_class_counts"]["hihat"] == 9


def _removable_lab(tmp_path, flac_path=None):
    from boo_lab.holdout import write_holdout

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac_root = tmp_path / "flac"
    gp_root = tmp_path / "gp"
    album_dir = flac_root / "Band" / "Deluxe"
    album_dir.mkdir(parents=True)
    gp_dir = gp_root / "Band"
    gp_dir.mkdir(parents=True)
    flac = Path(flac_path) if flac_path else (album_dir / "01 - Song.flac")
    flac.write_bytes(b"x")
    gp = gp_dir / "01 - Song.gp5"
    gp.write_bytes(b"x")
    save_map(
        lab / "data" / "map.csv",
        [{"album": "Band", "track": "01 - Song", "year": "", "flac": str(flac),
          "gp": str(gp), "tuning": "drop_g_7", "match": "yes", "notes": ""}],
    )
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "Band", "track": "01 - Song", "start": 0.0, "end": 2.0,
                    "role": "riff", "source": "human"}) + "\n",
        encoding="utf-8",
    )
    write_holdout(lab, {("Band", "01 - Song"), ("Other", "X")})
    return lab, flac_root, gp_root, flac, gp


def test_remove_album_deletes_files_labels_and_rescans(tmp_path):
    from boo_lab.catalogue import load_map
    from boo_lab.holdout import load_holdout

    lab, flac_root, gp_root, flac, gp = _removable_lab(tmp_path)
    client = TestClient(ann.create_app(lab, flac_root, gp_root))

    resp = client.post("/api/album/remove", json={"album": "Band", "confirm": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["tracks"] == 1 and body["files"] >= 2
    assert not flac.exists() and not gp.exists()
    assert not [l for l in (lab / "data" / "sections.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert load_holdout(lab) == {("Other", "X")}
    assert all((r.get("album") or "") != "Band" for r in load_map(lab / "data" / "map.csv"))
    assert not (flac_root / "Band" / "Deluxe").exists()


def test_remove_album_requires_confirm_and_does_not_touch_files(tmp_path):
    lab, flac_root, gp_root, flac, gp = _removable_lab(tmp_path)
    client = TestClient(ann.create_app(lab, flac_root, gp_root))
    assert client.post("/api/album/remove", json={"album": "Band"}).status_code == 400
    assert flac.exists() and gp.exists()


def test_remove_album_unknown_is_404(tmp_path):
    lab, flac_root, gp_root, _, _ = _removable_lab(tmp_path)
    client = TestClient(ann.create_app(lab, flac_root, gp_root))
    assert client.post("/api/album/remove", json={"album": "Nope", "confirm": True}).status_code == 404


def test_remove_album_never_deletes_outside_configured_roots(tmp_path):
    outside = tmp_path / "outside.flac"
    outside.write_bytes(b"keep me")
    lab, flac_root, gp_root, _, _ = _removable_lab(tmp_path, flac_path=outside)
    client = TestClient(ann.create_app(lab, flac_root, gp_root))

    body = client.post("/api/album/remove", json={"album": "Band", "confirm": True}).json()

    assert outside.exists(), "file outside BOO_FLAC_ROOT must never be deleted"
    assert any("outside" in s for s in body["skipped"])
