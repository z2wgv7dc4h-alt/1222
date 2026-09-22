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


def test_find_gp_ignores_a_generic_short_alias():
    # Regression: the last `_` segment of "..._Of_Me-s123" is "me", a substring
    # of "throwMEinthejungle", so one tab matched four unrelated songs.
    assert cat._find_gp("02 - Throw Me in the Jungle", {"me": Path("x.gp")}) is None
    assert cat._find_gp("11 - River of Time", {"me": Path("x.gp")}) is None


def test_scan_roots_assigns_each_gp_once(tmp_path):
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    for name in ("01 - The Other Half of Me.flac", "02 - Throw Me in the Jungle.flac",
                 "11 - River of Time.flac"):
        (album / "tracks" / name).write_bytes(b"x")
    gp_root = tmp_path / "gp"
    gp_root.mkdir()
    (gp_root / "Born_Of_Osiris-The_Other_Half_Of_Me-s405302.gp").write_bytes(b"x" * 10_000)

    rows = {r["track"]: r for r in cat.scan_roots(flac_root, gp_root)}

    assert rows["01 - The Other Half of Me"]["match"] == "yes"
    assert rows["02 - Throw Me in the Jungle"]["match"] == "unknown"
    assert rows["02 - Throw Me in the Jungle"]["gp"] == ""
    assert rows["11 - River of Time"]["match"] == "unknown"


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


# --- resolve_row (studio names vs year-prefixed map folders) -----------------

_HP = {"album": "2009 - A Higher Place", "track": "07 - Exist",
       "gp": r"...\gp5\A Higher Place\07 Exist.gp5"}
_DISCO = {"album": "2008 - The Discovery", "track": "02 - Exist"}


def test_resolve_row_short_album_year_prefix():
    rows = [_HP, _DISCO]
    got = cat.resolve_row(rows, "A Higher Place", "07 - Exist")
    assert got is _HP and got["album"] == "2009 - A Higher Place"
    assert got["track"] == "07 - Exist"


def test_resolve_row_casefold_and_track_number_punctuation():
    rows = [_HP, _DISCO]
    assert cat.resolve_row(rows, "a higher place", "exist") is _HP
    assert cat.resolve_row(rows, "2009 - A Higher Place", "07 Exist") is _HP


def test_resolve_row_does_not_steal_another_album_by_year():
    rows = [_HP, _DISCO]
    got = cat.resolve_row(rows, "The Discovery", "Exist")
    assert got is _DISCO
    assert cat.resolve_row(rows, "A Higher Place", "Exist") is _HP


def test_resolve_row_prefers_numbered_track_when_ambiguous():
    rows = [
        {"album": "A Higher Place", "track": "05 - Exist"},
        {"album": "A Higher Place", "track": "07 - Exist"},
    ]
    assert cat.resolve_row(rows, "A Higher Place", "07 Exist")["track"] == "07 - Exist"


def test_resolve_row_unknown_track_is_none():
    assert cat.resolve_row([_HP], "A Higher Place", "no such song") is None
    assert cat.resolve_row([], "A Higher Place", "Exist") is None
    assert cat.resolve_row([_HP], None, "Exist") is None


# --- load_map / save_map -----------------------------------------------------


def test_save_and_load_map_round_trip(tmp_path):
    rows = [{
        "album": "A", "track": "T", "year": "", "flac": "f",
        "gp": "g", "tuning": "drop_g_7", "match": "yes", "notes": "n",
        "flac_sha256": "",
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


def test_fill_hashes_fills_empty_skips_valid(tmp_path):
    import hashlib

    flac = tmp_path / "a.flac"
    flac.write_bytes(b"hello")
    missing = tmp_path / "nope.flac"
    valid = "a" * 64
    cat.save_map(tmp_path / "map.csv", [
        {"album": "A", "track": "T", "flac": str(flac)},
        {"album": "A", "track": "U", "flac": str(missing)},
        {"album": "A", "track": "V", "flac": str(flac), "flac_sha256": valid},
    ])

    report = cat.fill_hashes(tmp_path / "map.csv")

    rows = cat.load_map(tmp_path / "map.csv")
    assert report["filled"] == 1
    assert rows[0]["flac_sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert rows[1]["flac_sha256"] == ""          # missing file, left empty
    assert rows[2]["flac_sha256"] == valid        # valid 64-hex, never rehashed


def test_fill_hashes_repairs_a_malformed_cell(tmp_path):
    import hashlib

    flac = tmp_path / "a.flac"
    flac.write_bytes(b"hello")
    cat.save_map(tmp_path / "map.csv", [
        {"album": "A", "track": "V", "flac": str(flac), "flac_sha256": "deadbeef"},
    ])

    report = cat.fill_hashes(tmp_path / "map.csv")

    assert report["filled"] == 1
    assert cat.load_map(tmp_path / "map.csv")[0]["flac_sha256"] == \
        hashlib.sha256(b"hello").hexdigest()


def test_save_map_preserves_unknown_columns(tmp_path):
    path = tmp_path / "m.csv"
    cat.save_map(path, [{"album": "A", "track": "T", "custom_col": "keep"}])
    assert cat.load_map(path)[0]["custom_col"] == "keep"


# --- scan_roots --------------------------------------------------------------


def test_scan_roots_matches_a_flac_to_a_gp(tmp_path):
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    (album / "tracks" / "01 - Rebirth.flac").write_bytes(b"x")

    gp_root = tmp_path / "gp"
    gp_root.mkdir()
    gp = gp_root / "Born_Of_Osiris-Rebirth-s12345.gp5"
    gp.write_bytes(b"x" * 10_000)

    rows = cat.scan_roots(flac_root, gp_root)

    assert len(rows) == 1
    assert rows[0]["track"] == "01 - Rebirth"
    assert rows[0]["album"] == "Album"
    assert rows[0]["match"] == "yes"
    assert rows[0]["gp"] == str(gp)


def test_scan_roots_numbered_gp_beats_songsterr_for_the_album_track(tmp_path):
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    (album / "tracks" / "02 Singularity.flac").write_bytes(b"x")
    (album / "tracks" / "17 Singularity (Demo).flac").write_bytes(b"x")

    gp_root = tmp_path / "gp"
    (gp_root / "album").mkdir(parents=True)
    (gp_root / "album" / "02 Singularity.gp5").write_bytes(b"x")
    (gp_root / "Singularity-s83278.gp").write_bytes(b"x")

    rows = {r["track"]: r for r in cat.scan_roots(flac_root, gp_root)}

    assert Path(rows["02 Singularity"]["gp"]).name == "02 Singularity.gp5"
    assert Path(rows["17 Singularity (Demo)"]["gp"]).name == "Singularity-s83278.gp"


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


def test_scan_roots_matches_space_numbered_gp(tmp_path):
    # Regression: "07 Exist.gp5" keyed as "07exist" and silently never matched
    # "07 - Exist.flac" (looked like the song simply had no tab).
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    (album / "tracks" / "07 - Exist.flac").write_bytes(b"x")

    gp_root = tmp_path / "gp"
    gp_root.mkdir()
    gp = gp_root / "07 Exist.gp5"
    gp.write_bytes(b"x" * 10_000)

    rows = cat.scan_roots(flac_root, gp_root)

    assert rows[0]["match"] == "yes"
    assert rows[0]["gp"] == str(gp)


def test_scan_roots_space_numbered_gp_does_not_overmatch(tmp_path):
    flac_root = tmp_path / "corpus"
    album = flac_root / "Album"
    (album / "tracks").mkdir(parents=True)
    (album / "tracks" / "07 - Exist.flac").write_bytes(b"x")

    gp_root = tmp_path / "gp"
    gp_root.mkdir()
    (gp_root / "07 Something Else.gp5").write_bytes(b"x")

    rows = cat.scan_roots(flac_root, gp_root)

    assert rows[0]["match"] == "unknown" and rows[0]["gp"] == ""
