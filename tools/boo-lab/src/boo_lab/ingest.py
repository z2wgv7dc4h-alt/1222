from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

AUDIO = {".flac", ".wav"}
GP5 = {".gp5", ".gp4", ".gp3"}
GP7 = {".gp", ".gpx"}


def _band_slug(name: str) -> str:
    s = (name or "unknown").strip().lower().replace(" ", "_")
    return "".join(c if c.isalnum() or c == "_" else "" for c in s) or "unknown"


def _unpack_zips(drop: Path, scratch: Path) -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    for z in drop.rglob("*.zip"):
        dest = scratch / z.stem
        dest.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(z) as zh:
                zh.extractall(dest)
        except Exception as e:
            print("skip zip", z, e)


def ingest(drop: Path, flac_root: Path, gp_root: Path, band: str) -> dict:
    """Copy FLACs + GP into the corpus. Never deletes the drop folder."""
    band = _band_slug(band)
    scratch = drop / "_unpacked"
    _unpack_zips(drop, scratch)
    audio_dest = flac_root / band
    gp5_dest = gp_root / "gp5" / band
    gp7_dest = gp_root / "gp7" / band
    audio_dest.mkdir(parents=True, exist_ok=True)
    gp5_dest.mkdir(parents=True, exist_ok=True)
    gp7_dest.mkdir(parents=True, exist_ok=True)
    n_a = n_5 = n_7 = 0
    search = [drop, scratch]
    seen = set()
    for root in search:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or "_unpacked" in p.parts and root == drop:
                continue
            key = (p.suffix.lower(), p.stat().st_size, p.name.lower())
            if key in seen:
                continue
            ext = p.suffix.lower()
            if ext in AUDIO:
                album = p.parent.name
                if album.lower() in {"tracks", "track", drop.name.lower(), "_unpacked"}:
                    album = p.parent.parent.name if p.parent.parent != drop else "album"
                dest = audio_dest / album / p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(p, dest)
                    n_a += 1
                seen.add(key)
            elif ext in GP5:
                dest = gp5_dest / p.name
                if not dest.exists():
                    shutil.copy2(p, dest)
                    n_5 += 1
                seen.add(key)
            elif ext in GP7:
                dest = gp7_dest / p.name
                if not dest.exists():
                    shutil.copy2(p, dest)
                    n_7 += 1
                seen.add(key)
    return {"band": band, "flac": n_a, "gp5": n_5, "gp7": n_7, "audio": str(audio_dest)}
