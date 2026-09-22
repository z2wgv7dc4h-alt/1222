"""Stable song identity.

`data/identity.csv` maps the disk reality (`folder_name` + `track_token`, the
strings scan/holdout use TODAY) onto stable `album_id` values like
`boo.soul_sphere`. Album ids never depend on a mutable folder title, so a
misnamed folder can be fixed without changing every holdout key.

Additive only: `catalogue.resolve_row` stays the string-first studio lookup.
This module never writes keepers and never re-rolls the holdout split.
"""
from __future__ import annotations

import csv
from pathlib import Path

_IDENTITY_FILENAME = "identity.csv"

# A `tracks/` child folder is a container, never an album.
_NON_ALBUM = {"tracks", "track"}

# Shipped identity table (this file: src/boo_lab/identity.py).
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / _IDENTITY_FILENAME

_COLUMNS = (
    "album_id", "album_title", "year", "folder_name",
    "track_id", "track_title", "track_token", "notes",
)


def _path_for(lab_root) -> Path:
    if lab_root is None:
        return _DEFAULT_PATH
    return Path(lab_root) / "data" / _IDENTITY_FILENAME


def load_identity(lab_root=None) -> list[dict]:
    """Real identity rows, in file order. Empty list when the CSV is missing
    (not an error); malformed rows simply lack fields, never are fabricated."""
    path = _path_for(lab_root)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _norm(value) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def resolve_song(album, track, rows: list[dict] | None = None) -> dict | None:
    """The identity row for a `(folder_name, track_token)` pair.

    Exact match first, then casefold. `None` for a `tracks`/`track` container
    or anything unknown (never a guessed album id)."""
    album_key = _norm(album)
    if not album_key or album_key in _NON_ALBUM:
        return None
    if rows is None:
        rows = load_identity()
    album_raw = album.strip() if isinstance(album, str) else ""
    track_raw = track.strip() if isinstance(track, str) else ""
    track_key = track_raw.casefold()
    for r in rows:
        if ((r.get("folder_name") or "").strip() == album_raw
                and (r.get("track_token") or "").strip() == track_raw):
            return r
    for r in rows:
        if _norm(r.get("folder_name")) == album_key and _norm(r.get("track_token")) == track_key:
            return r
    # Second chance: comparable keys (separator / `∆` / parenthetical spellings).
    from .normalize import album_key as _album_key, track_key as _track_key

    loose_album = _album_key(album)
    loose_track = _track_key(track)
    if loose_album and loose_track:
        for r in rows:
            if (_album_key(r.get("folder_name")) == loose_album
                    and _track_key(r.get("track_token")) == loose_track):
                return r
    return None


def album_id_for(album, track, rows: list[dict] | None = None) -> str | None:
    """Stable album id for a `(folder_name, track_token)` pair, else `None`."""
    row = resolve_song(album, track, rows=rows)
    return (row.get("album_id") or None) if row else None
