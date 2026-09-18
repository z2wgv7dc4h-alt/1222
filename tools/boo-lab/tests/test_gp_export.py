"""Tests for src/boo_lab/gp_export.py -- fake GP roots under tmp_path; no real
Guitar Pro file, no network."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from boo_lab import gp_export

FIX = Path(__file__).parent / "fixtures" / "tiny.gp"


def _lab(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    return lab


def _rows(lab):
    path = lab / "data" / "gp_export.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_gpx_records_gpx_unsupported(tmp_path):
    gp_root = tmp_path / "gp"
    (gp_root / "gp7" / "band").mkdir(parents=True)
    (gp_root / "gp7" / "band" / "x.gpx").write_bytes(b"PK\x03\x04garbage")
    lab = _lab(tmp_path)

    report = gp_export.export_gp(lab, gp_root)

    assert report["scanned"] == 1 and report["wrote"] is True
    assert report["unsupported"][0]["reason"] == "gpx-unsupported"
    assert _rows(lab)[0]["reason"] == "gpx-unsupported"


def test_unsupported_gp_records_gp7_reason(tmp_path):
    gp_root = tmp_path / "gp"
    (gp_root / "gp7" / "band").mkdir(parents=True)
    (gp_root / "gp7" / "band" / "x.gp").write_bytes(b"definitely not a guitar pro file")

    report = gp_export.export_gp(_lab(tmp_path), gp_root)

    assert report["unsupported"][0]["reason"] == "gp7-unsupported"


def test_missing_gp_root_does_not_crash(tmp_path):
    report = gp_export.export_gp(_lab(tmp_path), tmp_path / "nope")

    assert report["scanned"] == 0 and report["wrote"] is False
    assert report["unsupported"] == []


def test_gpif_zip_is_converted_and_recorded(tmp_path):
    gp_root = tmp_path / "gp"
    (gp_root / "gp7").mkdir(parents=True)
    shutil.copy(FIX, gp_root / "gp7" / "tiny.gp")
    lab = _lab(tmp_path)

    report = gp_export.export_gp(lab, gp_root)

    row = _rows(lab)[0]
    assert row["converted"] is True and row["drops"] == []
    assert (lab / "work" / "gp5-from-gpif" / "tiny.from-gpif.gp5").exists()
    assert report["unsupported"][0]["converted"] is True


def test_parsing_file_needs_no_export(tmp_path, monkeypatch):
    gp_root = tmp_path / "gp"
    (gp_root / "gp7").mkdir(parents=True)
    (gp_root / "gp7" / "ok.gpx").write_bytes(b"x")
    lab = _lab(tmp_path)
    monkeypatch.setattr(gp_export, "classify", lambda p, rb=None: (True, ""))

    report = gp_export.export_gp(lab, gp_root)

    assert report["ok"] and not report["unsupported"]
    assert _rows(lab) == []
