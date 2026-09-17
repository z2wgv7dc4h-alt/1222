from __future__ import annotations

import csv
import hashlib
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
    "flac_sha256",
]


def load_map(path: Path) -> list[dict]:
    """Keep every column present in the CSV, including unknown extras."""
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_map(path: Path, rows: list[dict]) -> None:
    """Write `FIELDS` first, then any extra columns found in the rows, so a
    load→save round-trip never drops an unknown column."""
    keys = list(FIELDS)
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in keys})


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Hex sha256 of a file, or "" when it can't be read."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as f:
            for block in iter(lambda: f.read(chunk), b""):
                digest.update(block)
        return digest.hexdigest()
    except Exception:
        return ""


def fill_hashes(map_path: Path, album: str | None = None) -> dict:
    """Fill empty `flac_sha256` cells only (never rehash a populated cell).
    Missing files are left empty."""
    rows = load_map(map_path) if map_path.exists() else []
    filled = 0
    for row in rows:
        if album and (row.get("album") or "").casefold() != album.casefold():
            continue
        if row.get("flac_sha256"):
            continue
        flac = row.get("flac") or ""
        p = Path(flac) if flac else None
        if p and p.exists():
            digest = sha256_file(p)
            if digest:
                row["flac_sha256"] = digest
                filled += 1
    save_map(map_path, rows)
    return {"filled": filled, "rows": len(rows)}


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
            if p.suffix.lower() not in GP_EXT:
                continue
            keys = {_key(p.stem), _key(_stem(p))}
            # "07 Exist" (track number + space, no separator) -> also key "exist"
            import re

            keys.add(_key(re.sub(r"^\d+\s+", "", p.stem)))
            # Born_Of_Osiris-Elimination -> elimination
            if "-" in p.stem:
                keys.add(_key(p.stem.split("-")[-1]))
            if "_" in p.stem:
                keys.add(_key(p.stem.split("_")[-1]))
            for k in keys:
                if k:
                    gps.setdefault(k, p)
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
                    "flac_sha256": sha256_file(fp),
                }
            )
    rows.sort(key=lambda r: ((r.get("album") or ""), r.get("track") or ""))
    return rows


def filter_album(rows: list[dict], album: str | None) -> list[dict]:
    if not album:
        return rows
    key = album.casefold()
    return [r for r in rows if (r.get("album") or "").casefold() == key]
