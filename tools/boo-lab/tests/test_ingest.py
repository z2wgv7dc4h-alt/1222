"""Tests for src/boo_lab/ingest.py -- band inference from file/pack names,
single-file drop handling, and the post-ingest prep pass.

Synthetic drops under tmp_path; no real corpus/audio.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from boo_lab import ingest as ing

FIX_ZIP = Path(__file__).parent / "fixtures" / "tabnotes_tiny.zip"


# --- band inference -------------------------------------------------------
def test_from_pack_id_infers_band_and_title():
    assert ing._from_pack_id("born_of_osiris__the_new_reign__s32187") == (
        "born_of_osiris", "the new reign")
    assert ing._from_pack_id("Veil_Of_Maya__ID") == ("veil_of_maya", "ID")
    # never a false positive on a plain stem or a single underscore
    assert ing._from_pack_id("Born_Of_Osiris-Elimination") is None
    assert ing._from_pack_id("born_of_osiris_elimination") is None


def test_from_filename_handles_hyphen_and_spaced_forms():
    assert ing._from_filename("Born_Of_Osiris-Elimination") == (
        "born_of_osiris", "Elimination")
    assert ing._from_filename("Born Of Osiris - Song") == (
        "born_of_osiris", "Song")


def test_infer_band_title_prefers_pack_id_then_filename():
    assert ing.infer_band_title("born_of_osiris__the_new_reign__s32187") == (
        "born_of_osiris", "the new reign")
    assert ing.infer_band_title("Born Of Osiris - Song") == (
        "born_of_osiris", "Song")
    assert ing.infer_band_title("plain_track") is None


def test_blank_band_is_replaced_but_typed_band_wins(tmp_path):
    assert ing._is_blank_band("")
    assert ing._is_blank_band("new_band")
    assert ing._is_blank_band("unknown")
    assert not ing._is_blank_band("born_of_osiris")

    drop = _tiny_drop_with_gp(tmp_path)
    flac_root = tmp_path / "audio"
    gp_root = tmp_path / "gp"
    flac_root.mkdir()
    gp_root.mkdir()

    report = ing.ingest(drop, flac_root, gp_root, "veil_of_maya")

    assert report["band"] == "veil_of_maya"
    assert report["band_inferred"] is False
    assert (gp_root / "gp5" / "veil_of_maya").exists()


def _tiny_drop_with_gp(base: Path) -> Path:
    drop = base / "drop"
    drop.mkdir(parents=True, exist_ok=True)
    (drop / "Born_Of_Osiris-Elimination.gp5").write_bytes(b"FICHIER GUITAR PRO v5")
    return drop


# --- single-file drops ----------------------------------------------------
def test_lone_gp_file_infers_band_and_album(tmp_path):
    drop = _tiny_drop_with_gp(tmp_path)
    flac_root = tmp_path / "audio"
    gp_root = tmp_path / "gp"
    flac_root.mkdir()
    gp_root.mkdir()

    report = ing.ingest(drop, flac_root, gp_root, "")

    assert report["band"] == "born_of_osiris"
    assert report["band_inferred"] is True
    assert report["gp5"] == 1
    landed = gp_root / "gp5" / "born_of_osiris" / "Elimination" / "Born_Of_Osiris-Elimination.gp5"
    assert landed.exists()


def _minimal_pack_zip(path: Path, pack_id: str) -> Path:
    """A real tab-notes/1 zip with no manifest, so the file name is the id."""
    path.parent.mkdir(parents=True, exist_ok=True)
    notes = json.dumps({"format": "tab-notes/1", "title": "T", "artist": "A",
                        "events": []})
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("notes.json", notes)
    return path


def test_lone_tabnotes_zip_lands_under_data_tabnotes(tmp_path):
    drop = tmp_path / "drop"
    drop.mkdir()
    z = _minimal_pack_zip(drop / "born_of_osiris__the_new_reign__s32187.zip",
                          "born_of_osiris__the_new_reign__s32187")
    flac_root = tmp_path / "audio"
    gp_root = tmp_path / "gp"
    flac_root.mkdir()
    gp_root.mkdir()
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)

    report = ing.ingest(drop, flac_root, gp_root, "", lab_root=lab)

    assert report["tabnotes"] == 1
    # `safe_id` collapses the `__` separators to single underscores
    dest = (lab / "data" / "tabnotes"
            / "born_of_osiris_the_new_reign_s32187" / "notes.json")
    assert dest.exists()
    # the pack id named the band even though nothing audio/GP was dropped
    assert report["band"] == "born_of_osiris"
    assert report["tabnotes_packs"][0]["band"] == "born_of_osiris"


def test_lone_fixture_zip_uses_manifest_id(tmp_path):
    drop = tmp_path / "drop"
    drop.mkdir()
    shutil.copy2(FIX_ZIP, drop / "pack.zip")
    flac_root = tmp_path / "audio"
    gp_root = tmp_path / "gp"
    flac_root.mkdir()
    gp_root.mkdir()
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)

    report = ing.ingest(drop, flac_root, gp_root, "new_band", lab_root=lab)

    assert report["tabnotes"] == 1
    assert (lab / "data" / "tabnotes" / "tabnotes_tiny" / "notes.json").exists()
    # a non-blank typed band is never overridden
    assert report["band"] == "new_band"


# --- post-ingest prep -----------------------------------------------------
def test_prep_after_ingest_runs_scan_hash_interns_density(monkeypatch, tmp_path):
    from boo_lab import catalogue, interns, tabnotes_drafts

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    calls: dict = {}

    def _scan(f, g):
        calls["scan"] = True
        return [{"album": "A", "track": "T"}]

    monkeypatch.setattr(catalogue, "scan_roots", _scan)
    monkeypatch.setattr(catalogue, "save_map",
                        lambda p, rows: calls.__setitem__("saved", len(rows)))
    monkeypatch.setattr(catalogue, "fill_hashes",
                        lambda p, album=None: calls.__setitem__("hash_album", album)
                        or {"filled": 1, "rows": 1})
    monkeypatch.setattr(interns, "run_interns",
                        lambda *a, **k: calls.__setitem__("steps", k.get("steps"))
                        or {"beats": {}, "sync": {}})
    monkeypatch.setattr(tabnotes_drafts, "build_density_drafts",
                        lambda *a, **k: {"written": 0})

    prep = ing.prep_after_ingest(lab, tmp_path / "audio", tmp_path / "gp",
                                 band="born_of_osiris", albums=["A"])

    assert calls["scan"] is True
    assert calls["saved"] == 1
    assert calls["hash_album"] == "A"
    assert calls["steps"] == ["beats", "sync"]
    assert prep["album"] == "A"
    assert prep["scan"] == {"map_rows": 1}
    assert prep["map_rows"] == 1


def test_prep_after_ingest_reports_errors_but_keeps_going(monkeypatch, tmp_path):
    from boo_lab import catalogue, interns

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    intern_called: dict = {}

    def _boom(*_a, **_k):
        raise RuntimeError("no ffmpeg")

    monkeypatch.setattr(catalogue, "scan_roots", _boom)
    monkeypatch.setattr(catalogue, "fill_hashes",
                        lambda p, album=None: {"filled": 0, "rows": 0})
    monkeypatch.setattr(interns, "run_interns",
                        lambda *a, **k: intern_called.setdefault("yes", True))

    prep = ing.prep_after_ingest(lab, None, None, band="")

    assert "no ffmpeg" in prep["scan"]["error"]
    assert intern_called.get("yes") is True
    assert prep["map_rows"] == 0


# --- API wiring -----------------------------------------------------------
def test_api_ingest_returns_prep_without_page_reload(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from boo_lab import annotator as ann

    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    flac_root = tmp_path / "audio"
    gp_root = tmp_path / "gp"
    flac_root.mkdir()
    gp_root.mkdir()

    monkeypatch.setattr(ing, "ingest",
                        lambda *a, **k: {"band": "x", "albums": ["A"], "flac": 0,
                                         "gp5": 0, "gp7": 0, "tabnotes": 0})
    seen: dict = {}

    def _prep(lab_root, f, g, **k):
        seen.update(k)
        return {"map_rows": 3, "scan": {"map_rows": 3}}

    monkeypatch.setattr(ing, "prep_after_ingest", _prep)

    client = TestClient(ann.create_app(lab, flac_root, gp_root))
    r = client.post("/api/ingest", data={"band": ""},
                    files={"files": ("a.flac", b"x")})

    assert r.status_code == 200
    body = r.json()
    assert body["prep"]["map_rows"] == 3
    assert body["map_rows"] == 3
    assert seen.get("band") == "x"
    assert seen.get("albums") == ["A"]
