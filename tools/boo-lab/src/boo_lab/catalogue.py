from __future__ import annotations

import csv
from pathlib import Path

FIELDS = [
    "album",
    "track",
    "year",
    "flac",
    "gp",
    "tuning",
    "match",
    "notes",
]


def load_map(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_map(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def resolve(row: dict, flac_root: Path | None, gp_root: Path | None) -> dict:
    out = dict(row)
    if flac_root and row.get("flac"):
        p = Path(row["flac"])
        out["flac_path"] = str(p if p.is_absolute() else flac_root / p)
    if gp_root and row.get("gp"):
        p = Path(row["gp"])
        out["gp_path"] = str(p if p.is_absolute() else gp_root / p)
    return out


AUDIO_EXT = {".flac", ".wav", ".mp3", ".m4a"}
GP_EXT = {".gp3", ".gp4", ".gp5", ".gpx", ".gp"}


def _stem(p: Path) -> str:
    return p.stem.replace("_", " ").strip()


def scan_roots(flac_root: Path | None, gp_root: Path | None) -> list[dict]:
    """Draft map rows by matching file stems (casefold). Album = parent folder name."""
    flacs: dict[str, Path] = {}
    if flac_root and flac_root.exists():
        for p in flac_root.rglob("*"):
            if p.suffix.lower() in AUDIO_EXT:
                flacs.setdefault(_stem(p).casefold(), p)
    gps: dict[str, Path] = {}
    if gp_root and gp_root.exists():
        for p in gp_root.rglob("*"):
            if p.suffix.lower() in GP_EXT:
                gps.setdefault(_stem(p).casefold(), p)
    keys = sorted(set(flacs) | set(gps))
    rows = []
    for k in keys:
        fp, gp = flacs.get(k), gps.get(k)
        album = ""
        if fp:
            album = fp.parent.name
        elif gp:
            album = gp.parent.name
        rows.append(
            {
                "album": album,
                "track": (fp or gp).stem,
                "year": "",
                "flac": str(fp) if fp else "",
                "gp": str(gp) if gp else "",
                "tuning": "drop_g_7",
                "match": "yes" if fp and gp else "unknown",
                "notes": "",
            }
        )
    return rows


def filter_album(rows: list[dict], album: str | None) -> list[dict]:
    if not album:
        return rows
    key = album.casefold()
    return [r for r in rows if (r.get("album") or "").casefold() == key]
