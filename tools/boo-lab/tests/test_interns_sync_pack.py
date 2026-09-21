# -*- coding: utf-8 -*-
"""Pack-only rows must sync during interns (ingest prep)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from boo_lab.interns import _step_sync


def test_step_sync_runs_when_pack_exists_without_gp(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text("", encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"fake")

    rows = [{
        "album": "Album",
        "track": "01 - Song",
        "flac": str(flac),
        "gp": "",
    }]
    calls = []

    def fake_sync(lab_root, album, track):
        calls.append((album, track))
        return {"sync_ok": True}

    with mock.patch("boo_lab.interns.discover_pack", create=True):
        pass
    with mock.patch("boo_lab.tabnotes.discover_pack", return_value=lab / "pack"):
        with mock.patch("boo_lab.sync.sync_track", side_effect=fake_sync):
            out = _step_sync(lab, rows, {})
    assert out["sync_run"] == 1
    assert calls == [("Album", "01 - Song")]


def test_step_sync_skips_when_no_gp_and_no_pack(tmp_path):
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sync.jsonl").write_text("", encoding="utf-8")
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"fake")
    rows = [{"album": "A", "track": "T", "flac": str(flac), "gp": ""}]
    with mock.patch("boo_lab.tabnotes.discover_pack", return_value=None):
        with mock.patch("boo_lab.sync.sync_track") as sync_track:
            out = _step_sync(lab, rows, {})
    assert out["sync_run"] == 0
    sync_track.assert_not_called()
