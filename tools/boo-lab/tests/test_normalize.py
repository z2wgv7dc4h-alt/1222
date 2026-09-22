"""tests for src/boo_lab/normalize.py -- comparable keys, not filenames."""
from __future__ import annotations

from boo_lab.catalogue import resolve_row
from boo_lab.identity import resolve_song
from boo_lab.normalize import album_key, track_key


# --- track_key ---------------------------------------------------------------


def test_track_key_ignores_number_separator_and_extension():
    assert track_key("04 Devastate") == track_key("04 - Devastate")
    assert track_key("04 Devastate") == track_key("Devastate.flac")


def test_track_key_maps_twda_delta_to_a():
    assert track_key("05 - ∆bsolution") == track_key("05 - Absolution")
    assert track_key("01 - M∆chine") == track_key("01 - Machine")


def test_track_key_is_not_a_filename_rewrite():
    assert track_key("01 - Rebirth") == "rebirth"
    assert track_key("Follow the Signs (Misha Mansoor Demo Mix)") == \
        "follow the signs misha mansoor demo mix"


# --- album_key ---------------------------------------------------------------


def test_album_key_shares_loose_discovery_key():
    fye = album_key("Born of Osiris - The Discovery (Fye Edition) (FLAC)")
    assert "discovery" in fye
    assert fye == album_key("The Discovery")
    assert fye != album_key("Born of Osiris - Soul Sphere (2015)")


def test_album_key_strips_year_and_band_prefix():
    assert album_key("2009 - A Higher Place") == album_key("A Higher Place")
    assert album_key("Born of Osiris - Soul Sphere (2015)") == "soul sphere"


# --- catalogue.resolve_row ---------------------------------------------------


def test_resolve_row_prefers_exact_over_loose():
    rows = [
        {"album": "Born of Osiris - The Discovery (Fye Edition) (FLAC)",
         "track": "14 XIV", "which": "exact"},
        {"album": "The Discovery", "track": "14 XIV", "which": "loose"},
    ]

    hit = resolve_row(rows, "Born of Osiris - The Discovery (Fye Edition) (FLAC)", "14 XIV")

    assert hit is not None and hit["which"] == "exact"


def test_resolve_row_falls_back_to_loose_keys():
    rows = [{"album": "Born of Osiris - The Discovery (Fye Edition) (FLAC)",
             "track": "14 XIV"}]

    hit = resolve_row(rows, "The Discovery", "14 XIV")

    assert hit is rows[0]


# --- identity.resolve_song second chance -------------------------------------


def test_resolve_song_second_chance_uses_track_key():
    rows = [
        {"album_id": "boo.soul_sphere", "folder_name": "Born of Osiris - Soul Sphere (2015)",
         "track_token": "04 Illuminate"},
        {"album_id": "boo.discovery",
         "folder_name": "Born of Osiris - The Discovery (Fye Edition) (FLAC)",
         "track_token": "14 XIV"},
    ]

    # exact folder + token
    assert resolve_song("Born of Osiris - The Discovery (Fye Edition) (FLAC)", "14 XIV",
                        rows=rows)["album_id"] == "boo.discovery"
    # loose spelling -> second chance
    assert resolve_song("The Discovery", "14 XIV", rows=rows)["album_id"] == "boo.discovery"
