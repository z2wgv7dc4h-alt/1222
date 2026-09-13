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


def _key(s: str) -> str:
    import re
    s = (s or "").replace("∆", "A").replace("Δ", "A").replace("δ", "a").lower()
    s = re.sub(r"^\d+\s*[-_.]\s*", "", s)
    s = re.sub(r"^bornofosiris", "", s)
    s = re.sub(r"s\d+$", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def _album_of(p: Path) -> str:
    d = p.parent
    if d.name.lower() in {"tracks", "track"}:
        d = d.parent
    return d.name


def _looks_like_disc_image(p: Path) -> bool:
    if p.parent.name.lower() in {"tracks", "track"}:
        return False
    if (p.parent / "tracks").is_dir():
        return True
    if list(p.parent.glob("*.cue")) and list(p.parent.glob("tracks/*")):
        return True
    return False


def _find_gp(stem: str, gps: dict[str, Path]) -> Path | None:
    k = _key(stem)
    if not k:
        return None
    if k in gps:
        return gps[k]
    for name, path in gps.items():
        nk = _key(name)
        if nk == k or (len(k) > 5 and (k in nk or nk in k)):
            return path
    return None


def scan_roots(flac_root: Path | None, gp_root: Path | None) -> list[dict]:
    """One row per track FLAC. Album = album folder, not 'tracks'."""
    gps: dict[str, Path] = {}
    if gp_root and gp_root.exists():
        for p in gp_root.rglob("*"):
            if p.suffix.lower() in GP_EXT:
                gps.setdefault(_key(p.stem) or _stem(p).casefold(), p)
    rows = []
    if flac_root and flac_root.exists():
        flacs = sorted(
            p for p in flac_root.rglob("*")
            if p.suffix.lower() in AUDIO_EXT and not _looks_like_disc_image(p)
        )
        for fp in flacs:
            gp = _find_gp(_stem(fp), gps)
            rows.append(
                {
                    "album": _album_of(fp),
                    "track": fp.stem,
                    "year": "",
                    "flac": str(fp),
                    "gp": str(gp) if gp else "",
                    "tuning": "drop_g_7",
                    "match": "yes" if gp else "unknown",
                    "notes": "",
                }
            )
    rows.sort(key=lambda r: ((r.get("album") or ""), r.get("track") or ""))
    return rows


def filter_album(rows: list[dict], album: str | None) -> list[dict]:
    if not album:
        return rows
    key = album.casefold()
    return [r for r in rows if (r.get("album") or "").casefold() == key]
