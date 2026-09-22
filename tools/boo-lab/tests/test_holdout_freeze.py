"""data/holdout.csv is FROZEN -- any edit to its seven rows fails here."""
from __future__ import annotations

import csv
from pathlib import Path

HOLDOUT = Path(__file__).resolve().parents[1] / "data" / "holdout.csv"

FROZEN = [
    ("2009 - A Higher Place", "01 - Rebirth"),
    ("2009 - A Higher Place", "09 - A Descent"),
    ("2013 - Tomorrow We Die ∆live", "05 - ∆bsolution"),
    ("Born Of Osiris - The Eternal Reign - 2017", "04 - Abstract Art"),
    ("Born of Osiris - Soul Sphere (2015)", "03 - Free Fall"),
    ("Born of Osiris - The Discovery (Fye Edition) (FLAC)", "04 Devastate"),
    ("Born of Osiris - The Discovery (Fye Edition) (FLAC)", "14 XIV"),
]


def test_holdout_header_is_album_track():
    with HOLDOUT.open(newline="", encoding="utf-8") as f:
        assert next(csv.reader(f)) == ["album", "track"]


def test_holdout_frozen_rows_exact():
    with HOLDOUT.open(newline="", encoding="utf-8") as f:
        rows = [(r.get("album"), r.get("track")) for r in csv.DictReader(f)]
    assert rows == FROZEN


def test_load_holdout_reads_the_same_frozen_set():
    from boo_lab.holdout import load_holdout

    assert load_holdout(HOLDOUT.parent.parent) == set(FROZEN)
