"""one-tab picker: GPIF GP7 > legacy GP3/4/5 > largest, never a stub."""
from __future__ import annotations

import zipfile
from pathlib import Path

from boo_lab.catalogue import pick_gp, scan_roots


def _file(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def _gp7_zip(path: Path, size: int = 20_000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("VERSION", "7.0")
        z.writestr("Content/score.gpif",
                   "<GPIF><Score><Title>X</Title></Score></GPIF>" + " " * size)
    return path


# --- pick_gp -----------------------------------------------------------------


def test_picks_the_larger_bankable_gp5(tmp_path):
    tiny = _file(tmp_path / "exhilarate.gp5", 3_000)
    full = _file(tmp_path / "exhilarate_2.gp5", 132_000)

    assert pick_gp([tiny, full]) == full


def test_gpif_gp7_beats_a_larger_gp5(tmp_path):
    gp5 = _file(tmp_path / "song.gp5", 132_000)
    gp7 = _gp7_zip(tmp_path / "song.gp", 20_000)

    assert pick_gp([gp5, gp7]) == gp7


def test_tiny_gp4_is_never_picked(tmp_path):
    stub = _file(tmp_path / "Illusionist.gp4", 4_000)

    assert pick_gp([stub]) is None


def test_solo_is_never_picked_even_when_large(tmp_path):
    solo = _file(tmp_path / "Devastate Solo.gp5", 132_000)
    full = _file(tmp_path / "Devastate.gp5", 50_000)

    assert pick_gp([solo, full]) == full
    assert pick_gp([solo]) is None


def test_no_candidates_is_none():
    assert pick_gp([]) is None


# --- scan wiring -------------------------------------------------------------


def test_scan_tiny_gp4_leaves_gp_empty_and_not_yes(tmp_path):
    flac_root = tmp_path / "flac"
    (flac_root).mkdir(parents=True)
    (flac_root / "Illusionist.flac").write_bytes(b"x")
    gp_root = tmp_path / "gp"
    _file(gp_root / "Illusionist.gp4", 4_000)

    rows = scan_roots(flac_root, gp_root)

    assert len(rows) == 1
    assert rows[0]["gp"] == ""
    assert rows[0]["match"] != "yes"


def test_scan_picks_the_larger_gp5(tmp_path):
    flac_root = tmp_path / "flac"
    flac_root.mkdir(parents=True)
    (flac_root / "Exhilarate.flac").write_bytes(b"x")
    gp_root = tmp_path / "gp"
    tiny = _file(gp_root / "Exhilarate-s1.gp5", 3_000)
    full = _file(gp_root / "Exhilarate_2.gp5", 132_000)

    rows = scan_roots(flac_root, gp_root)

    assert rows[0]["gp"] == str(full)
    assert rows[0]["match"] == "yes"
    assert tiny.name in rows[0]["notes"]
