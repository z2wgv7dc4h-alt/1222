"""Empty keepers means no bank slices: pack/extract/export/bank/drums/vocals.

Machines never invent boxes from drafts or from the dead rebirth snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import cli, drums_extract, guess, pack, vocal_melody
from boo_lab.catalogue import save_map


def _lab(tmp_path: Path) -> Path:
    lab = tmp_path / "lab"
    (lab / "data").mkdir(parents=True)
    (lab / "data" / "sections.jsonl").write_text("", encoding="utf-8")
    (lab / "data" / "holdout.csv").write_text("album,track\n", encoding="utf-8")
    return lab


def test_pack_empty_keepers_writes_zero_clips(tmp_path, capsys):
    lab = _lab(tmp_path)
    rows = [{"album": "A", "track": "T", "flac": "", "gp": ""}]

    report = pack.build_pack(lab, rows, lab / "work" / "stems")

    assert report["written"] == 0
    assert "pack: no keepers" in capsys.readouterr().out


def test_pack_sees_one_heard_keeper(tmp_path, monkeypatch):
    lab = _lab(tmp_path)
    flac = tmp_path / "song.flac"
    flac.write_bytes(b"x")
    (lab / "data" / "sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 0.0, "end": 4.0,
                    "role": "riff", "source": "human", "heard": True}) + "\n",
        encoding="utf-8",
    )
    rows = [{"album": "A", "track": "T", "flac": str(flac), "gp": ""}]

    import boo_lab.stems as stems

    monkeypatch.setattr(stems, "find_stem", lambda f, c, n: None)
    monkeypatch.setattr(stems, "run_demucs", lambda *a, **k: None)
    monkeypatch.setattr(pack, "_slice", lambda *a, **k: True)

    report = pack.build_pack(lab, rows, lab / "work" / "stems")

    assert report["written"] == 1          # exactly the one keeper box


def test_drums_and_vocals_write_zero_rows_on_empty_gold(tmp_path):
    lab = _lab(tmp_path)
    rows = [{"album": "A", "track": "T", "flac": "", "gp": ""}]
    cache = lab / "work" / "stems"

    drums = drums_extract.build_drum_patterns(lab, rows, cache)
    vocals = vocal_melody.build_vocal_melody(lab, rows, cache)

    assert drums["sections"] == 0
    assert vocals["sections"] == 0


def test_extract_ignores_snapshot_and_drafts(tmp_path, monkeypatch, capsys):
    lab = _lab(tmp_path)
    # Only the dead snapshot + a draft exist -- neither is a keeper/fragment source.
    (lab / "data" / "rebirth-sections.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 1.0, "end": 2.0,
                    "role": "riff", "source": "human", "heard": True,
                    "invalid": True}) + "\n",
        encoding="utf-8",
    )
    (lab / "data" / "drafts.jsonl").write_text(
        json.dumps({"album": "A", "track": "T", "start": 1.0, "end": 2.0,
                    "role": "riff", "source": "msa-draft", "heard": False}) + "\n",
        encoding="utf-8",
    )
    save_map(lab / "data" / "map.csv",
             [{"album": "A", "track": "T", "match": "unknown", "flac": "", "gp": ""}])
    monkeypatch.setattr(cli, "root", lambda: lab)
    monkeypatch.setattr(cli, "data_dir", lambda: lab / "data")
    monkeypatch.setattr(guess, "_prefer_tab", lambda gp, track: None)

    rc = cli.main(["extract"])

    assert rc == 0
    riffs = lab / "data" / "riffs.jsonl"
    assert not riffs.exists() or riffs.read_text(encoding="utf-8").strip() == ""
    assert "SKIP extract" in capsys.readouterr().out


def test_export_bank_with_no_riffs_is_empty(tmp_path, monkeypatch):
    lab = _lab(tmp_path)
    monkeypatch.setattr(cli, "root", lambda: lab)
    monkeypatch.setattr(cli, "data_dir", lambda: lab / "data")
    out = lab / "bank.json"

    rc = cli.main(["export-bank", "--out", str(out)])

    assert rc == 0
    assert json.loads(out.read_text(encoding="utf-8")) == []
