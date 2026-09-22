"""Real, fixed whole-song validation split for the boo-lab pipeline.

Mirrors `engine/riff_model.py`'s own established discipline (`train`'s
`val_song_count`): validation holds out ENTIRE real songs, never a
note-/row-level split, so near-duplicate material from one song can never
leak across train/val.

Selection is deterministic and stable: real candidate songs sorted by
album+track, then every Nth taken. Once written to `data/holdout.csv` it is
a fixed, reserved set -- never re-rolled per run.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

_MATCH_YES = {"yes", "y", "1", "true"}

HOLDOUT_FILENAME = "holdout.csv"

# data/holdout.csv is FROZEN at its seven rows -- tests/test_holdout_freeze.py
# pins them; do not re-roll, append, or rewrite. CSV has no comment syntax that
# csv.DictReader skips, so this note lives here instead of in the file.

# ~12.5% held out (within the requested 10-15%) -- deterministic every-Nth.
_TARGET_EVERY = 8


def candidate_songs(rows: list[dict], sections: list[dict]) -> list[tuple[str, str]]:
    """Real, sorted `(album, track)` universe eligible for the split:
    every map row that is matched with a real GP file on disk, plus every
    track that carries real human labels (a labeled song is real training
    data even when it fell back to audio transcription)."""
    from .gate import is_bankable_track, is_stub_gp

    candidates: set[tuple[str, str]] = set()
    for r in rows:
        match = (r.get("match") or "").lower()
        gp = r.get("gp_path") or r.get("gp") or ""
        track = r.get("track") or ""
        if match not in _MATCH_YES or not gp or not Path(gp).exists():
            continue
        # A non-bankable track/GP (Misha mix, *_solo*, tiny stub, cover,
        # bass-only) is not a holdout candidate. `ensure_holdout` honors an
        # existing data/holdout.csv as-is, so this only changes a FUTURE
        # empty-file reselect -- the frozen seven rows are never re-rolled.
        if not is_bankable_track(track, Path(gp).name) or is_stub_gp(gp):
            continue
        candidates.add((r.get("album") or "", track))
    for rec in sections:
        if rec.get("album") and rec.get("track"):
            candidates.add((rec.get("album"), rec.get("track")))
    return sorted(candidates)


def select_holdout(candidates: list[tuple[str, str]], every: int = _TARGET_EVERY) -> set[tuple[str, str]]:
    """Deterministic every-Nth selection over the already-sorted candidate
    list -- same input, same reserved set, every run. Fails closed on a
    nonsensical stride rather than silently holding out everything."""
    if every <= 1:
        raise ValueError("every must be > 1")
    return {song for i, song in enumerate(candidates) if i % every == 0}


def load_holdout(lab_root: Path) -> set[tuple[str, str]]:
    """Real reserved set from `data/holdout.csv`; empty set (not an error)
    when it doesn't exist yet. Malformed/blank rows are skipped."""
    path = Path(lab_root) / "data" / HOLDOUT_FILENAME
    out: set[tuple[str, str]] = set()
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            album = (row.get("album") or "").strip()
            track = (row.get("track") or "").strip()
            if album and track:
                out.add((album, track))
    return out


def write_holdout(lab_root: Path, holdout: set[tuple[str, str]]) -> Path:
    path = Path(lab_root) / "data" / HOLDOUT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["album", "track"])
        for album, track in sorted(holdout):
            writer.writerow([album, track])
    return path


def ensure_holdout(lab_root: Path, rows: list[dict]) -> set[tuple[str, str]]:
    """The fixed reserved set: an existing `data/holdout.csv` is always
    honored as-is; otherwise a deterministic set is selected from the real
    current candidates and written once."""
    from .schema import load_section_rows

    path = Path(lab_root) / "data" / HOLDOUT_FILENAME
    if path.exists():
        # Empty file means "deliberately reserve nothing" ? do not re-select.
        return load_holdout(lab_root)
    # Keepers-only: a validation split must be reserved from real labeled
    # songs, never from machine drafts. Shares schema's single reader.
    sections = load_section_rows(Path(lab_root) / "data" / "sections.jsonl")
    candidates = candidate_songs(rows, sections)
    holdout = select_holdout(candidates)
    write_holdout(lab_root, holdout)
    return holdout


def split_for(album: str | None, track: str | None, holdout: set[tuple[str, str]]) -> str:
    """Real `"val"`/`"train"` tag for one whole song."""
    return "val" if ((album or ""), (track or "")) in holdout else "train"


def tag(record: dict, holdout: set[tuple[str, str]]) -> dict:
    record["split"] = split_for(record.get("album"), record.get("track"), holdout)
    return record
