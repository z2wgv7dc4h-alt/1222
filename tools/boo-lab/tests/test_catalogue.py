"""Tests for src/boo_lab/catalogue.py -- filesystem fixtures under tmp_path
only; no real FLAC/GP files."""
from __future__ import annotations

from pathlib import Path

import pytest

from boo_lab import catalogue as cat


# --- _key (title normalization) ---------------------------------------------


def test_key_normalizes_titles():
    assert cat._key("03 - ∆eon III") == "aeoniii"
    assert cat._key("bornofosirisrecreate") == "recreate"
    assert cat._key("Recreate.s77727") == "recreate"
    assert cat._key(None) == ""
    assert cat._key("   ") == ""


# --- _stem / _album_of / _looks_like_disc_image ------------------------------


def test_stem_and_album_of():
    assert cat._stem(Path("01 - Rebirth.flac")) == "01 - Rebirth"
    assert cat._album_of(Path("Album/tracks/01 - Rebirth.flac")) == "Album"
    assert cat._album_of(Path("Album/01 - Rebirth.flac")) == "Album"


def test_looks_like_disc_image(tmp_path):
    album = tmp_path / "Album"
    (album / "tracks").mkdir(parents=True)
    disc = album / "Album.flac"
    disc.write_bytes(b"x")
    track = album / "tracks" / "01.flac"
    track.write_bytes(b"x")
    assert cat._looks_like_disc_image(disc) is True
    assert cat._looks_like_disc_image(track) is False


# --- _find_gp ----------------------------------------------------------------


def test_find_gp_exact_and_substring():
    gps = {"elimination": Path("elim.gp5"), "mikasa": Path("mikasa.gp5")}
    assert cat._find_gp("02 - Elimination", gps) == Path("elim.gp5")
    assert cat._find_gp("mikasa", {"mikasasong": Path("m.gp5")}) == Path("m.gp5")
    assert cat._find_gp("", gps) is None
    assert cat._find_gp("unknown", gps) is None


# --- resolve -----------------------------------------------------------------


def test_resolve_joins_roots_for_relative_paths(tmp_path):
    out = cat.resolve({"flac": "a.flac", "gp": "x.gp5"}, tmp_path, tmp_path / "gp")
    assert Path(out["flac_path"]) == tmp_path / "a.flac"
    assert Path(out["gp_path"]) == tmp_path / "gp" / "x.gp5"


def test_resolve_keeps_absolute_paths(tmp_path):
    out = cat.resolve({"flac": str(tmp_path / "a.flac")}, tmp_path, None)
    assert Path(out["flac_path"]) == tmp_path / "a.flac"


def test_resolve_without_paths_or_roots_is_unchanged():
    row = {"album": "A"}
    assert cat.resolve(row, Path("C:/root"), Path("C:/gp")) == row
    assert cat.resolve(row, None, None) == row


# --- filter_album ------------------------------------------------------------


def test_filter_album_is_case_insensitive_and_none_passes_all():
    rows = [{"album": "A Higher Place"}, {"album": "Other"}]
    assert cat.filter_album(rows, None) == rows
    assert cat.filter_album(rows, "a higher place") == [rows[0]]
    assert cat.filter_album(rows, "missing") == []


# --- load_map / save_map -----------------------------------------------------


def test_save_and_load_map_round_trip(tmp_path):
    rows = [{
        "album": "A", "track": "T", "year": "", "flac": "f",
        "gp": "g", "tuning": "drop_g_7", "match": "yes", "notes": "n",
    }]
    path = tmp_path / "map.csv"
    cat.save_map(path, rows)
    assert cat.load_map(path) == rows


def test_save_map_writes_blanks_for_missing_fields(tmp_path):
    path = tmp_path / "map.csv"
    cat.save_map(path, [{"album": "A", "track": "T"}])
    row = cat.load_map(path)[0]
    assert row["flac"] == "" and row["match"] == "" and row["notes"] == ""


def test_load_map_missing_file_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        cat.load_map(tmp_path / "nope.csv")


# --- scan_roots --------------------------------------------------------------


def test_scan_roots_matches_a_flac_to_a_gp(tmp_path):
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    (album / "tracks" / "01 - Rebirth.flac").write_bytes(b"x")

    gp_root = tmp_path / "gp"
    gp_root.mkdir()
    gp = gp_root / "Born_Of_Osiris-Rebirth-s12345.gp5"
    gp.write_bytes(b"x")

    rows = cat.scan_roots(flac_root, gp_root)

    assert len(rows) == 1
    assert rows[0]["track"] == "01 - Rebirth"
    assert rows[0]["album"] == "Album"
    assert rows[0]["match"] == "yes"
    assert rows[0]["gp"] == str(gp)


def test_scan_roots_excludes_disc_images(tmp_path):
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    (album / "Album.flac").write_bytes(b"x")  # disc image at album root
    (album / "tracks" / "01.flac").write_bytes(b"x")

    rows = cat.scan_roots(flac_root, None)
    assert [r["track"] for r in rows] == ["01"]


def test_scan_roots_bad_input_is_empty(tmp_path):
    assert cat.scan_roots(None, None) == []
    assert cat.scan_roots(tmp_path / "nope", tmp_path / "nope2") == []
