"""bankable/stub gate: CATALOG's skip list, enforced in code (no disk deletes)."""
from __future__ import annotations

import json
from pathlib import Path

from boo_lab import identity
from boo_lab.catalogue import scan_roots
from boo_lab.gate import is_bankable_track, is_stub_gp
from boo_lab.holdout import candidate_songs


def _file(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


# --- is_bankable_track -------------------------------------------------------


def test_misha_mix_is_not_bankable():
    assert is_bankable_track("16 Follow the Signs (Misha Mansoor Demo Mix).flac") is False


def test_plain_song_is_bankable():
    assert is_bankable_track("01 - Rebirth") is True
    assert is_bankable_track("04 Devastate") is True


def test_solo_cover_bass_intro_are_not_bankable():
    assert is_bankable_track("Devastate Solo.gp5") is False
    assert is_bankable_track("behold_outro_solo") is False
    assert is_bankable_track("jerome cover") is False
    assert is_bankable_track("Elimination_bass") is False
    assert is_bankable_track("01 - Intro") is False


def test_the_origin_is_not_an_intro_stub():
    assert is_bankable_track("The Origin") is True
    assert is_bankable_track("06 - The Origin") is True


def test_identity_misha_rows_are_not_bankable():
    row = identity.resolve_song(
        "Born of Osiris - The Discovery (Fye Edition) (FLAC)",
        "16 Follow the Signs (Misha Mansoor Demo Mix)",
    )
    assert row is not None and "misha-mix" in row["notes"]
    assert is_bankable_track(row["track_token"]) is False


# --- is_stub_gp --------------------------------------------------------------


def test_tiny_or_skipped_name_gp_is_a_stub(tmp_path):
    solo = _file(tmp_path / "Devastate Solo.gp5", 3_000)
    assert is_stub_gp(solo, solo.stat().st_size) is True

    full = _file(tmp_path / "exhilarate_2.gp5", 132_000)
    assert is_stub_gp(full, full.stat().st_size) is False

    assert is_stub_gp(tmp_path / "missing.gp5", 132_000) is True


# --- scan_roots match string -------------------------------------------------


def test_scan_marks_a_stub_gp_as_stub_not_yes(tmp_path):
    flac_root = tmp_path / "flac"
    gp_root = tmp_path / "gp"
    _file(flac_root / "Song.flac", 100)
    _file(gp_root / "Song.gp5", 3_000)

    rows = scan_roots(flac_root, gp_root)

    assert len(rows) == 1
    assert rows[0]["match"] == "stub"


def test_scan_marks_a_full_gp_as_yes(tmp_path):
    flac_root = tmp_path / "flac"
    gp_root = tmp_path / "gp"
    _file(flac_root / "Song.flac", 100)
    _file(gp_root / "Song.gp5", 132_000)

    rows = scan_roots(flac_root, gp_root)

    assert rows[0]["match"] == "yes"


# --- holdout candidate filter ------------------------------------------------


def test_candidate_songs_skips_non_bankable_and_stub(tmp_path):
    good = _file(tmp_path / "Good.gp5", 132_000)
    stub = _file(tmp_path / "Intro.gp5", 3_000)
    rows = [
        {"album": "A", "track": "01 - Rebirth", "match": "yes", "gp": str(good)},
        {"album": "A", "track": "04 Devastate", "match": "yes", "gp": str(stub)},
        {"album": "A", "track": "16 Follow the Signs (Misha Mansoor Demo Mix)",
         "match": "yes", "gp": str(good)},
    ]

    assert candidate_songs(rows, []) == [("A", "01 - Rebirth")]
