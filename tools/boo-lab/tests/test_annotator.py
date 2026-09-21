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


def test_canonical_role_maps_known_and_fails_closed():
    assert ann.canonical_role("verse") == "riff"
    assert ann.canonical_role("Chorus") == "hook"
    assert ann.canonical_role("interlude") == "chill"
    assert ann.canonical_role("riff") == "riff"
    assert ann.canonical_role(None) is None
    assert ann.canonical_role("") is None
    assert ann.canonical_role("bogus") is None


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

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "chorus", "start": 0.0, "end": 2.0, "source": "human", "heard": True},
    ]})
    assert resp.status_code == 200 and resp.json()["saved"] == 1
    saved = [json.loads(l) for l in (lab / "data" / "sections.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert saved[0]["role"] == "hook"
    assert saved[0]["source"] == "human" and saved[0]["heard"] is True
    assert saved[0]["figure_id"] == "hook-A" and saved[0]["layer"] == "figure"


def _sections_rows(lab):
    path = lab / "data" / "sections.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_save_keeps_identity_fields_on_heard_box(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "solo", "start": 1, "end": 3, "source": "human", "heard": True,
         "form": "b", "unique": True, "instrument": "lead", "start_bar": 17, "end_bar": 20},
    ]})
    assert resp.status_code == 200 and resp.json()["saved"] == 1
    row = _sections_rows(lab)[0]
    assert row["form"] == "B" and row["unique"] is True and row["instrument"] == "lead"
    assert row["start_bar"] == 17 and row["end_bar"] == 20


def test_save_does_not_invent_bars_without_matching_gp(tmp_path):
    lab = _lab(tmp_path)  # map row is match=unknown with no gp path
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "source": "human", "heard": True}]})
    row = _sections_rows(lab)[0]
    assert row["start_bar"] is None and row["end_bar"] is None


def test_save_drops_unheard_and_unaccepted_drafts(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "source": "human", "heard": True},
        {"role": "hook", "start": 3, "end": 5, "source": "human", "heard": False},
        {"role": "breakdown", "start": 6, "end": 8, "source": "msa-draft", "heard": False},
        {"role": "solo", "start": 9, "end": 11, "source": "guess", "heard": False},
        {"role": "pulse", "start": 12, "end": 14},  # legacy, no source/heard
    ]})
    assert resp.status_code == 200 and resp.json()["saved"] == 1
    rows = _sections_rows(lab)
    assert len(rows) == 1
    assert rows[0]["role"] == "riff"
    assert rows[0]["source"] == "human" and rows[0]["heard"] is True


def test_save_keeps_heard_drafts_as_guess_accepted(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "solo", "start": 0, "end": 2, "source": "guess", "heard": True},
        {"role": "breakdown", "start": 3, "end": 5, "source": "msa-draft", "heard": True, "msa_label": "break"},
        {"role": "riff", "start": 6, "end": 8, "source": "guess-accepted", "heard": True},
    ]})
    assert resp.status_code == 200 and resp.json()["saved"] == 3
    rows = _sections_rows(lab)
    assert {r["source"] for r in rows} == {"guess-accepted"}
    assert {r["role"] for r in rows} == {"solo", "breakdown", "riff"}
    # extra keys stamp_box doesn't know are preserved
    assert any(r.get("msa_label") == "break" for r in rows)


def test_save_rejects_same_role_overlap_and_writes_nothing(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    before = (lab / "data" / "sections.jsonl").read_text(encoding="utf-8")
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 4, "source": "human", "heard": True},
        {"role": "riff", "start": 2, "end": 6, "source": "human", "heard": True},
    ]})
    assert resp.status_code == 400
    assert "overlap" in resp.json()["detail"]
    assert (lab / "data" / "sections.jsonl").read_text(encoding="utf-8") == before


def test_save_rejects_end_not_after_start_and_writes_nothing(tmp_path):
    lab = _lab(tmp_path)
    path = lab / "data" / "sections.jsonl"
    other = {"album": "A", "track": "Other", "start": 0.0, "end": 1.0, "role": "riff", "source": "human"}
    path.write_text(json.dumps(other) + "\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 5.0, "end": 5.0, "source": "human", "heard": True}]})

    assert resp.status_code == 400 and "bad box 0" in resp.json()["detail"]
    assert path.read_text(encoding="utf-8") == before  # other-track row untouched


def test_save_rejects_non_numeric_start_end(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": "abc", "end": 5, "source": "human", "heard": True}]})
    assert resp.status_code == 400 and "numbers" in resp.json()["detail"]


def test_save_skips_and_counts_a_malformed_existing_line(tmp_path):
    lab = _lab(tmp_path)
    path = lab / "data" / "sections.jsonl"
    other = {"album": "A", "track": "Other", "start": 0.0, "end": 1.0, "role": "riff", "source": "human"}
    path.write_text(json.dumps(other) + "\n{ this is not json\n", encoding="utf-8")
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0.0, "end": 2.0, "source": "human", "heard": True}]})

    assert resp.status_code == 200 and resp.json()["saved"] == 1
    assert resp.json()["malformed_lines_skipped"] == 1
    assert resp.json()["malformed_line_numbers"] == [2]
    rows = _sections_rows(lab)  # file parses cleanly again
    assert any(r.get("track") == "Other" for r in rows)  # other-track row preserved
    assert any(r.get("track") == "T" for r in rows)


def test_save_write_failure_leaves_file_untouched(tmp_path, monkeypatch):
    lab = _lab(tmp_path)
    path = lab / "data" / "sections.jsonl"
    other = {"album": "A", "track": "Other", "start": 0.0, "end": 1.0, "role": "riff", "source": "human"}
    path.write_text(json.dumps(other) + "\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    def _boom(p, rows):
        raise OSError("disk full")

    monkeypatch.setattr(ann, "_atomic_write_jsonl", _boom)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0.0, "end": 2.0, "source": "human", "heard": True}]})

    assert resp.status_code == 500 and "unchanged" in resp.json()["detail"]
    assert path.read_text(encoding="utf-8") == before  # aborted save destroyed nothing


def test_save_promotes_a_heard_songformer_draft_to_keeper(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "source": "songformer-draft", "heard": True}]})

    assert resp.status_code == 200 and resp.json()["saved"] == 1
    row = _sections_rows(lab)[0]
    assert row["source"] == "guess-accepted"  # promotable set derived from schema


def test_save_reports_dropped_unheard_and_writes_a_backup(tmp_path):
    lab = _lab(tmp_path)
    path = lab / "data" / "sections.jsonl"
    before = path.read_text(encoding="utf-8")
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "source": "human", "heard": True},
        {"role": "hook", "start": 3, "end": 5, "source": "human", "heard": False},
    ]})

    assert resp.status_code == 200 and resp.json()["saved"] == 1
    assert resp.json()["dropped_unheard"] == 1
    backup = lab / "data" / "sections.jsonl.bak"
    assert backup.read_text(encoding="utf-8") == before  # one-step undo available
    assert not list((lab / "data").glob("*.tmp"))  # no temp left behind


def test_save_rejects_unknown_or_missing_source(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    bad = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "source": "not-a-real-source", "heard": True}]})
    assert bad.status_code == 400 and "unknown source" in bad.json()["detail"]

    missing = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "heard": True}]})
    assert missing.status_code == 400 and "unknown source" in missing.json()["detail"]


def test_save_rejects_a_box_with_no_resolvable_role(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]

    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "bogus", "start": 0, "end": 2, "source": "human", "heard": True}]})

    assert resp.status_code == 400 and "unknown role" in resp.json()["detail"]


def test_save_allows_figure_over_function_overlap(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 4, "source": "human", "heard": True},
        {"role": "breakdown", "start": 2, "end": 6, "source": "human", "heard": True},
    ]})
    assert resp.status_code == 200 and resp.json()["saved"] == 2


def test_save_accepts_blast_and_round_trips_on_figure(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    resp = client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 4, "source": "human", "heard": True,
         "figure_id": "riff-A"},
        {"role": "blast", "start": 1, "end": 3, "source": "human", "heard": True,
         "figure_id": "blast-A", "on_figure": "riff-A"},
    ]})
    assert resp.status_code == 200 and resp.json()["saved"] == 2
    rows = _sections_rows(lab)
    blast = [r for r in rows if r["role"] == "blast"][0]
    assert blast["layer"] == "function"
    assert blast["on_figure"] == "riff-A"
    assert [r for r in rows if r["role"] == "riff"][0]["on_figure"] == ""


def test_save_never_overwrites_drafts(tmp_path):
    lab = _lab(tmp_path)
    draft = lab / "data" / "drafts.jsonl"
    draft.write_text(json.dumps({"album": "A", "track": "T", "role": "riff", "source": "msa-draft"}) + "\n", encoding="utf-8")
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    client.post("/api/sections/%d" % tid, json={"sections": [
        {"role": "riff", "start": 0, "end": 2, "source": "human", "heard": True}]})
    assert json.loads(draft.read_text(encoding="utf-8"))["source"] == "msa-draft"


def test_api_drafts_returns_only_that_track(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0, "end": 1, "role": "riff", "source": "msa-draft"}) + "\n"
        + json.dumps({"album": "A", "track": "Other", "start": 0, "end": 1, "role": "hook", "source": "msa-draft"}) + "\n",
        encoding="utf-8",
    )
    client = TestClient(ann.create_app(lab, None, None))
    got = client.get("/api/drafts", params={"album": "A", "track": "T"}).json()["drafts"]
    assert len(got) == 1 and got[0]["role"] == "riff"


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


def test_beats_endpoint_returns_the_grid_for_the_track(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "beats.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "beats": [0.5, 1.0, 1.5],
                    "downbeats": [0.0], "source": "beat_this"}) + "\n"
        + json.dumps({"album": "A", "track": "Other", "beats": [9.9], "downbeats": [], "source": "x"}) + "\n",
        encoding="utf-8",
    )
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    got = client.get("/api/beats/%d" % tid).json()
    assert got["beats"] == [0.5, 1.0, 1.5] and got["downbeats"] == [0.0]
    assert got["source"] == "beat_this"


def test_beats_endpoint_empty_when_not_computed(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    tid = client.get("/api/tracks").json()["tracks"][0]["id"]
    assert client.get("/api/beats/%d" % tid).json() == {"beats": [], "downbeats": [], "source": ""}


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


def test_remove_album_aborts_on_malformed_sections_without_deleting(tmp_path):
    lab, flac_root, gp_root, flac, gp = _removable_lab(tmp_path)
    path = lab / "data" / "sections.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "{ not json\n", encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    client = TestClient(ann.create_app(lab, flac_root, gp_root))

    resp = client.post("/api/album/remove", json={"album": "Band", "confirm": True})

    assert resp.status_code == 400 and "malformed" in resp.json()["detail"]
    assert flac.exists() and gp.exists()  # parsed before deleting: nothing removed
    assert path.read_text(encoding="utf-8") == before


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


# --- Guess finished-song guard + prefer --------------------------------------

def test_estimate_refuses_a_finished_song(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac = tmp_path / "T.flac"
    flac.write_bytes(b"x")
    save_map(lab / "data" / "map.csv",
             [{"album": "A", "track": "T", "flac": str(flac), "gp": "", "match": "unknown"}])
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "role": "riff", "source": "human",
                    "heard": True, "start": 0.0, "end": 1.0}) + "\n", encoding="utf-8")
    drafts = lab / "data" / "drafts.jsonl"
    drafts.write_text("", encoding="utf-8")

    client = TestClient(ann.create_app(lab, None, None))
    resp = client.get("/api/estimate/0")

    assert resp.status_code == 409
    assert "already has keepers" in resp.json()["detail"]
    assert drafts.read_text(encoding="utf-8") == ""


def test_estimate_runs_when_no_keepers(tmp_path, monkeypatch):
    from boo_lab import guess as _guess

    monkeypatch.setattr(_guess, "estimate_hybrid",
                        lambda *a, **k: {"sections": [], "notes": ["stub"]})
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac = tmp_path / "T.flac"
    flac.write_bytes(b"x")
    save_map(lab / "data" / "map.csv",
             [{"album": "A", "track": "T", "flac": str(flac), "gp": "", "match": "unknown"}])

    client = TestClient(ann.create_app(lab, None, None))
    resp = client.get("/api/estimate/0")

    assert resp.status_code == 200


def test_tracks_payload_includes_prefer(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    assert client.get("/api/tracks").json()["prefer"] == "none"


def test_tracks_badge_prefers_gp7_over_legacy_gp5(tmp_path):
    flac = tmp_path / "audio" / "01 - Song.flac"
    flac.parent.mkdir(parents=True)
    flac.write_bytes(b"x")
    gp_root = tmp_path / "gp"
    legacy = gp_root / "gp5" / "Band" / "01 - Song.gp5"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"x")
    modern = gp_root / "gp7" / "Band" / "01 - Song.gp"
    modern.parent.mkdir(parents=True)
    modern.write_bytes(b"x")
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    save_map(lab / "data" / "map.csv", [{
        "album": "Band", "track": "01 - Song", "year": "", "flac": str(flac),
        "gp": str(legacy), "tuning": "drop_g_7", "match": "yes", "notes": ""}])

    client = TestClient(ann.create_app(lab, None, gp_root))
    t = client.get("/api/tracks").json()["tracks"][0]

    assert t["has_gp"] is True
    assert t["gp_kind"] == "gp7"         # display kind; not "gp5" -- GP7 sibling wins
    assert t["gp_name"].endswith(".gp")


def _pack_fixture(lab, title="T", artist="A", pid="mindful"):
    pack = lab / "data" / "tabnotes" / pid
    pack.mkdir(parents=True)
    (pack / "manifest.json").write_text(
        json.dumps({"id": pid, "title": title, "artist": artist}), encoding="utf-8")
    (pack / "notes.json").write_text(
        json.dumps({"format": "tab-notes/1", "id": pid, "title": title, "artist": artist}),
        encoding="utf-8")
    return pack


def test_tracks_report_has_pack_from_discovery(tmp_path):
    lab = _lab(tmp_path)
    _pack_fixture(lab)  # Mindful-like: FLAC + tab-notes pack, no .gp
    client = TestClient(ann.create_app(lab, None, None))
    t = client.get("/api/tracks").json()["tracks"][0]
    assert t["has_pack"] is True
    assert t["pack_source"] == "pack"


def test_tracks_report_has_pack_from_ingested_index(tmp_path):
    lab = _lab(tmp_path)
    (lab / "data" / "tabnotes_index.jsonl").write_text(
        json.dumps({"id": "mindful", "title": "T", "artist": "A"}) + "\n",
        encoding="utf-8")
    client = TestClient(ann.create_app(lab, None, None))
    t = client.get("/api/tracks").json()["tracks"][0]
    assert t["has_pack"] is True
    assert t["pack_source"] == "tn"


def test_tracks_has_pack_false_without_pack(tmp_path):
    lab = _lab(tmp_path)
    client = TestClient(ann.create_app(lab, None, None))
    t = client.get("/api/tracks").json()["tracks"][0]
    assert t["has_pack"] is False
    assert t["pack_source"] == ""
