"""tests for src/boo_lab/identity.py -- stable album ids from the real tree."""
from __future__ import annotations

from boo_lab import identity

FYE = "Born of Osiris - The Discovery (Fye Edition) (FLAC)"
SOUL = "Born of Osiris - Soul Sphere (2015)"
SIM = "Born of Osiris - The Simulation (2019)"


def test_load_identity_exposes_expected_columns():
    rows = identity.load_identity()

    assert rows
    assert set(identity._COLUMNS) <= set(rows[0])


def test_fye_xiv_resolves_to_discovery():
    row = identity.resolve_song(FYE, "14 XIV")

    assert row is not None
    assert row["album_id"] == "boo.discovery"
    assert identity.album_id_for(FYE, "14 XIV") == "boo.discovery"


def test_soul_sphere_free_fall_is_soul_sphere_never_discovery():
    album_id = identity.album_id_for(SOUL, "03 - Free Fall")

    assert album_id == "boo.soul_sphere"
    assert album_id != "boo.discovery"


def test_simulation_first_track_resolves():
    assert identity.album_id_for(SIM, "01 The Accursed") == "boo.simulation"


def test_tracks_container_is_not_an_album():
    assert identity.resolve_song("tracks", "01 - Rebirth") is None
    assert identity.album_id_for("tracks", "01 - Rebirth") is None


def test_match_is_casefold_when_not_exact():
    assert identity.album_id_for(SOUL.upper(), "03 - FREE FALL") == "boo.soul_sphere"


def test_misha_mix_stays_discovery_and_is_flagged():
    row = identity.resolve_song(FYE, "16 Follow the Signs (Misha Mansoor Demo Mix)")

    assert row is not None
    assert row["album_id"] == "boo.discovery"
    assert "misha-mix" in (row.get("notes") or "")


def test_unknown_pair_is_none_never_guessed():
    assert identity.album_id_for(SOUL, "99 - Nope") is None
    assert identity.album_id_for("Not A Real Album", "01 - Rebirth") is None
    assert identity.load_identity(lab_root=None)  # shipped table found
