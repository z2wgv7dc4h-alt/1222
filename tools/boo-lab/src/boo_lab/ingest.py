from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

AUDIO = {".flac", ".wav"}
GP5_EXT = {".gp5", ".gp4", ".gp3"}
GP7_EXT = {".gpx"}
ART = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _band_slug(name: str) -> str:
    s = (name or "unknown").strip().lower().replace(" ", "_")
    return "".join(c if c.isalnum() or c == "_" else "" for c in s) or "unknown"


def _infer_band_album(folder: str, typed: str) -> tuple[str, str]:
    raw = (folder or "").strip()
    typed = (typed or "").strip()
    if typed and typed.lower() not in {"new_band", "unknown", "band"}:
        return _band_slug(typed), raw or "album"
    parts = [x.strip() for x in raw.replace("—", "-").split(" - ") if x.strip()]
    if len(parts) >= 3 and parts[-1].isdigit() and len(parts[-1]) == 4:
        return _band_slug(parts[0]), f"{parts[-1]} - {parts[1]}"
    if len(parts) >= 2 and not parts[0][:1].isdigit():
        return _band_slug(parts[0]), " - ".join(parts[1:])
    return _band_slug(typed or raw or "unknown"), raw or "album"



def _from_filename(stem: str) -> tuple[str, str] | None:
    s = (stem or "").replace("_", " ").strip()
    s = s.split(" - s")[0]
    import re
    s = re.sub(r"\s*s\d+$", "", s)
    if " - " in s:
        a, b = s.split(" - ", 1)
        if a and b:
            return _band_slug(a), b.strip()
    if "-" in stem and "_" in stem:
        # Born_Of_Osiris-Elimination
        left, right = stem.split("-", 1)
        if left and right:
            return _band_slug(left.replace("_", " ")), right.replace("_", " ")
    return None

def _corpus_root(flac_root: Path, band: str) -> Path:
    if flac_root.name.lower() in {"audio-corpus", "audio", "flacs", "flac"}:
        return flac_root
    if band and band != _band_slug(flac_root.name):
        return flac_root.parent
    return flac_root


def _safe_under(root: Path, rel: Path) -> Path | None:
    if ".." in rel.parts:
        return None
    out = (root / rel).resolve()
    try:
        out.relative_to(root.resolve())
    except ValueError:
        return None
    return out


def _gp_kind(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in GP5_EXT:
        return "gp5"
    if ext in GP7_EXT:
        return "gp7"
    if ext != ".gp":
        return ""
    try:
        head = p.read_bytes()[:40]
    except Exception:
        return "gp7"
    if head.startswith(b"FICHIER GUITAR") or head.startswith(b"FICHIER GUITARE"):
        return "gp5"
    return "gp7"


def _unpack_zips(drop: Path, scratch: Path) -> None:
    from .tabnotes import is_pack

    scratch.mkdir(parents=True, exist_ok=True)
    for z in list(drop.rglob("*.zip")):
        if is_pack(z):  # tab-notes packs go to data/tabnotes, not scratch
            continue
        dest = scratch / z.stem
        dest.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(z) as zh:
                zh.extractall(dest)
        except Exception as e:
            print("skip zip", z, e)


def _pack_id(src: Path) -> str:
    from .tabnotes import read_manifest

    try:
        man = read_manifest(src)
        if man.get("id"):
            return str(man["id"])
    except Exception:
        pass
    return src.stem if src.is_file() else src.name


def _ingest_tabnotes(drop: Path, lab_root: Path) -> list[dict]:
    """Unpack/index every tab-notes pack under the drop into
    `lab_root/data/tabnotes/<safe_id>/`. Never copies a pack into the FLAC or
    GP roots; never deletes another id."""
    from . import tabnotes

    base = Path(lab_root) / "data" / "tabnotes"
    base.mkdir(parents=True, exist_ok=True)

    sources: list[Path] = []
    if tabnotes.is_pack(drop):
        sources.append(drop)
    for z in sorted(drop.rglob("*.zip")):
        if tabnotes.is_pack(z):
            sources.append(z)
    accepted: list[Path] = []
    for d in sorted(p for p in drop.rglob("*") if p.is_dir()):
        if not tabnotes.is_pack(d):
            continue
        if any(d == a or a in d.parents for a in accepted):
            continue  # nested inside an already-accepted pack
        accepted.append(d)
        sources.append(d)

    results: list[dict] = []
    for src in sources:
        try:
            sid = tabnotes.safe_id(_pack_id(src))
            dest = base / sid
            tabnotes.unpack_pack(src, dest)
            pack = tabnotes.load_pack(dest)
            tabnotes.append_index(lab_root, pack)
            results.append({"id": pack.id or sid, "title": pack.title,
                            "tracks": len(pack.tracks), "events": len(pack.events),
                            "dest": str(dest)})
            print("TABNOTES %s | %s | tracks=%d events=%d -> %s"
                  % (pack.id or sid, pack.title or "?", len(pack.tracks), len(pack.events), dest))
        except Exception as e:  # noqa: BLE001 - one bad pack never aborts ingest
            results.append({"source": str(src), "error": str(e)})
            print("TABNOTES FAIL", src, e)
    return results


def _album_name(p: Path, drop: Path) -> str:
    d = p.parent
    skip = {"tracks", "track", "covers", "cover", "art", "artwork", "_unpacked", drop.name.lower()}
    if d.name.lower() in skip:
        d = d.parent
    if d.name.lower() in skip or d == drop:
        return "album"
    return d.name


def ingest(drop: Path, flac_root: Path, gp_root: Path, band: str,
           lab_root: Path | None = None) -> dict:
    """Copy FLACs, art, and GP into the corpus (unchanged), and unpack any
    tab-notes packs into `lab_root/data/tabnotes/`. Never deletes the drop."""
    typed = band
    scratch = drop / "_unpacked"
    _unpack_zips(drop, scratch)
    packs = _ingest_tabnotes(drop, lab_root) if lab_root is not None else []
    audio_dest = gp5_dest = gp7_dest = None
    n_a = n_5 = n_7 = n_art = 0
    search = [drop, scratch]
    seen: set[tuple] = set()
    for root in search:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if root == drop and "_unpacked" in p.parts:
                continue
            ext = p.suffix.lower()
            key = (ext, p.stat().st_size, p.name.lower())
            if key in seen:
                continue
            folder = _album_name(p, drop)
            band, album = _infer_band_album(folder, typed)
            parsed = _from_filename(p.stem)
            if parsed and (not typed or typed.lower() in {"new_band","unknown","band"}):
                band = parsed[0]
                if folder.lower() in {"album","gp5","gp7","tabs","tab"}:
                    album = parsed[1]
            corpus = _corpus_root(flac_root, band)
            audio_dest = corpus / band
            gp5_dest = gp_root / "gp5" / band
            gp7_dest = gp_root / "gp7" / band
            if ext in AUDIO:
                dest = audio_dest / album / p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(p, dest)
                    n_a += 1
                seen.add(key)
            elif ext in ART:
                dest = audio_dest / album / p.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(p, dest)
                    n_art += 1
                seen.add(key)
            else:
                kind = _gp_kind(p)
                if kind == "gp5":
                    dest = gp5_dest / album / p.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copy2(p, dest)
                        n_5 += 1
                    seen.add(key)
                elif kind == "gp7":
                    dest = gp7_dest / album / p.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copy2(p, dest)
                        n_7 += 1
                    seen.add(key)
    return {
        "band": band if audio_dest else _band_slug(typed),
        "flac": n_a,
        "gp5": n_5,
        "gp7": n_7,
        "art": n_art,
        "tabnotes": len([p for p in packs if "error" not in p]),
        "tabnotes_packs": packs,
        "audio": str(audio_dest),
    }
