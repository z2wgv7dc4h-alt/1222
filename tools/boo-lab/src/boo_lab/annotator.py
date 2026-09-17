from __future__ import annotations

import json
import math
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .catalogue import load_map, resolve
from .schema import (
    KEEPER_SOURCES,
    SOURCES,
    ROLES as _SCHEMA_ROLES,
    canonical_role,
    same_role_overlaps,
    stamp_box,
    write_jsonl_atomic,
)

# Lab role vocabulary + pin schema live in schema.py (single source of truth).
ROLES = list(_SCHEMA_ROLES)

# Every non-keeper source promotes to `guess-accepted` once heard. Derived from
# schema (not a hardcoded literal) so a newly added draft source can't be
# silently rejected by `is_keeper` after a human listened to it.
_PROMOTABLE_SOURCES = SOURCES - KEEPER_SOURCES

# Real demucs stems boo-lab can cache and the annotator can serve.
STEM_NAMES = ("drums", "bass", "guitar", "piano", "other", "vocals")

# One atomic writer for every JSONL store (schema.write_jsonl_atomic). Kept
# under the local name so callers/tests patch a single symbol.
_atomic_write_jsonl = write_jsonl_atomic


def _within(path: Path, root: Path | None) -> bool:
    """True only when `path` really resolves inside `root`. Guards every
    destructive action -- a corpus file outside the configured roots is
    never deleted."""
    if root is None:
        return False
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False


def _prune_empty(dirs, root: Path | None) -> list[str]:
    """Remove now-empty directories, walking upward but never past `root`
    itself (and never deleting a non-empty dir)."""
    removed: list[str] = []
    if root is None:
        return removed
    rootr = Path(root).resolve()
    for d in sorted(set(dirs), key=lambda x: len(str(x)), reverse=True):
        cur = Path(d)
        while True:
            try:
                if not cur.exists() or not cur.is_dir():
                    break
                if cur.resolve() == rootr or not _within(cur, root):
                    break
                if any(cur.iterdir()):
                    break
                cur.rmdir()
                removed.append(str(cur))
                cur = cur.parent
            except Exception:
                break
    return removed


def create_app(lab_root: Path, flac_root: Path | None, gp_root: Path | None) -> FastAPI:
    app = FastAPI(title="boo-lab annotator")
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")
    map_path = lab_root / "data" / "map.csv"
    sec_path = lab_root / "data" / "sections.jsonl"

    def _norm_name(s: str) -> str:
        import re
        s = (s or "").replace("∆", "A").replace("Δ", "A").replace("δ", "a").lower()
        s = re.sub(r"^\d+\s*[-_.]\s*", "", s)
        return re.sub(r"[^a-z0-9]+", "", s)

    _gp5_cache: dict = {"t": None, "idx": {}}

    def _gp5_index() -> dict[str, Path]:
        # Real GP root (BOO_GP_ROOT) -- no hardcoded absolute path. `.gp5`
        # (and modern `.gp`) files are indexed by normalized stem so the
        # sidebar can show a green match even when map.csv has no gp_path.
        roots = [gp_root] if gp_root and gp_root.exists() else []
        if not roots:
            return {}
        try:
            stamp = tuple(p.stat().st_mtime for p in roots)
        except Exception:
            stamp = None
        if _gp5_cache["idx"] and _gp5_cache["t"] == stamp:
            return _gp5_cache["idx"]
        idx: dict[str, Path] = {}
        for root in roots:
            try:
                for pattern in ("*.gp5", "*.gp4", "*.gp3", "*.gp"):
                    for p in root.rglob(pattern):
                        idx.setdefault(_norm_name(p.stem), p)
            except Exception:
                continue
        _gp5_cache["t"] = stamp
        _gp5_cache["idx"] = idx
        return idx

    def _cover_near(fp: str | None) -> Path | None:
        if not fp:
            return None
        try:
            d = Path(fp).parent
        except Exception:
            return None
        names = ("folder.jpg", "cover.jpg", "Cover.jpg", "folder.png", "cover.png", "Cover.png")
        for folder in (d, d.parent):
            for n in names:
                p = folder / n
                if p.exists():
                    return p
            covers = folder / "Cover"
            if covers.is_dir():
                pics = sorted(covers.glob("*.jpg")) + sorted(covers.glob("*.png"))
                if pics:
                    return pics[0]
            pics = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png"))
            pics = [p for p in pics if p.name.lower() not in {"desktop.ini"}]
            if pics:
                return pics[0]
        return None

    def tracks():
        if not map_path.exists():
            return []
        try:
            rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        except Exception:
            return []
        from .holdout import ensure_holdout, split_for
        from .stems import find_stem

        holdout = ensure_holdout(lab_root, rows)
        stem_cache = lab_root / "work" / "stems"
        idx = _gp5_index()
        out = []
        for i, r in enumerate(rows):
            key = _norm_name(r.get("track") or "")
            gp5 = idx.get(key)
            if not gp5 and key:
                for k, p in idx.items():
                    if key in k or k in key:
                        gp5 = p
                        break
            notes = (r.get("notes") or "").lower()
            partial = False
            if gp5:
                name = gp5.name.lower()
                try:
                    sz = gp5.stat().st_size
                except Exception:
                    sz = 0
                partial = (
                    "stub" in notes
                    or "fragment" in notes
                    or "partial" in notes
                    or ("bass" in name and "guitar" not in name and "xiv" not in name)
                )
            flac_ok = False
            fp = r.get("flac_path") or r.get("flac")
            if fp:
                try:
                    flac_ok = Path(fp).exists()
                except Exception:
                    flac_ok = False
            if not flac_ok and flac_root and flac_root.exists() and key:
                try:
                    for p in flac_root.rglob("*"):
                        if p.suffix.lower() in {".flac", ".wav"} and _norm_name(p.stem) == key:
                            r["flac_path"] = str(p)
                            fp = str(p)
                            flac_ok = True
                            break
                except Exception:
                    pass
            stems = []
            if flac_ok and fp:
                try:
                    stems = [n for n in STEM_NAMES if find_stem(Path(fp), stem_cache, n)]
                except Exception:
                    stems = []
            out.append(
                {
                    "id": i,
                    "album": r.get("album"),
                    "track": r.get("track"),
                    "tuning": r.get("tuning"),
                    "has_flac": flac_ok,
                    "has_gp": bool(gp5),
                    "gp_partial": partial,
                    "gp_name": gp5.name if gp5 else "",
                    "gp_kind": (gp5.suffix.lower().lstrip(".") if gp5 else ""),
                    "has_cover": bool(_cover_near(fp)),
                    "split": split_for(r.get("album"), r.get("track"), holdout),
                    "stems": stems,
                }
            )
        out.sort(key=lambda t: ((t.get("album") or ""), t.get("track") or ""))
        flac_keys = {_norm_name(t.get("track") or "") for t in out if t.get("has_flac")}
        out = [t for t in out if t.get("has_flac") or _norm_name(t.get("track") or "") not in flac_keys]
        return out

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (static / "annotator.html").read_text(encoding="utf-8")

    @app.get("/api/tracks")
    def api_tracks():
        return {"roles": ROLES, "tracks": tracks()}

    def _resolved(track_id: int) -> dict | None:
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        meta = None
        for t in tracks():
            if t.get("id") == track_id:
                meta = t
                break
        if meta:
            for r in rows:
                if (r.get("album") or "") == (meta.get("album") or "") and (r.get("track") or "") == (meta.get("track") or ""):
                    return r
        if 0 <= track_id < len(rows):
            return rows[track_id]
        return None

    @app.get("/api/cover/{track_id}")
    def api_cover(track_id: int):
        row = _resolved(track_id)
        if not row:
            raise HTTPException(404)
        p = _cover_near(row.get("flac_path") or row.get("flac"))
        if not p:
            raise HTTPException(404)
        return FileResponse(p)

    @app.get("/api/audio/{track_id}")
    def api_audio(track_id: int):
        row = _resolved(track_id)
        if not row:
            raise HTTPException(404)
        path = row.get("flac_path") or row.get("flac")
        if not path or not Path(path).exists():
            raise HTTPException(404, "flac missing — set BOO_FLAC_ROOT and map.csv")
        return FileResponse(path, media_type="audio/flac")

    @app.get("/api/tab/{track_id}")
    def api_tab(track_id: int):
        row = _resolved(track_id)
        if not row:
            raise HTTPException(404)
        from .guess import _prefer_gp5

        raw = row.get("gp_path") or row.get("gp") or ""
        gp5 = _prefer_gp5(Path(raw) if raw else None, row.get("track") or "")
        path = gp5
        if not path and raw and Path(raw).exists():
            path = Path(raw)
        if not path:
            raise HTTPException(404, "no tab file")
        return FileResponse(path)

    @app.get("/api/drums/{track_id}")
    def api_drums(track_id: int):
        row = _resolved(track_id)
        if not row:
            raise HTTPException(404)
        flac = row.get("flac_path") or row.get("flac")
        if not flac:
            raise HTTPException(404)
        from .stems import find_drums

        p = find_drums(Path(flac), lab_root / "work" / "stems")
        if not p:
            raise HTTPException(404, "no drums stem yet — press Guess")
        return FileResponse(p, media_type="audio/wav")

    @app.get("/api/stem/{track_id}/{name}")
    def api_stem(track_id: int, name: str):
        """Serve any real cached demucs stem (drums/bass/guitar/piano/
        other/vocals) for the 6-stem lane picker."""
        if name not in STEM_NAMES:
            raise HTTPException(404, "unknown stem")
        row = _resolved(track_id)
        if not row:
            raise HTTPException(404)
        flac = row.get("flac_path") or row.get("flac")
        if not flac:
            raise HTTPException(404)
        from .stems import find_stem

        p = find_stem(Path(flac), lab_root / "work" / "stems", name)
        if not p:
            raise HTTPException(404, "no %s stem cached" % name)
        return FileResponse(p, media_type="audio/wav")

    @app.get("/api/analysis/{track_id}")
    def api_analysis(track_id: int):
        """Real per-section drum classification rows (from
        data/drum_patterns.jsonl) for the selected song -- used to surface
        the measured `low_confidence` flag in the UI."""
        meta = _meta(track_id)
        if not meta:
            return {"sections": []}
        path = lab_root / "data" / "drum_patterns.jsonl"
        found = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("album") == meta["album"] and rec.get("track") == meta["track"]:
                    found.append(rec)
        return {"sections": found}

    @app.get("/api/beats/{track_id}")
    def api_beats(track_id: int):
        """Beat/downbeat grid for the selected song (data/beats.jsonl), so the
        studio can draw ticks and snap box edges. Empty when not computed."""
        meta = _meta(track_id)
        if not meta:
            return {"beats": [], "downbeats": [], "source": ""}
        path = lab_root / "data" / "beats.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("album") == meta["album"] and rec.get("track") == meta["track"]:
                    return {"beats": rec.get("beats") or [],
                            "downbeats": rec.get("downbeats") or [],
                            "source": rec.get("source") or ""}
        return {"beats": [], "downbeats": [], "source": ""}

    @app.get("/api/estimate/{track_id}")
    def api_estimate(track_id: int):
        row = _resolved(track_id)
        if not row:
            raise HTTPException(404)
        flac = row.get("flac_path")
        gp = row.get("gp_path")
        from .guess import estimate_hybrid
        payload = estimate_hybrid(
            Path(flac) if flac else None,
            Path(gp) if gp else None,
            track=row.get("track") or "",
            cache=lab_root / "work" / "stems",
            album=row.get("album") or "",
        )
        return payload

    def _meta(track_id: int):
        for t in tracks():
            if t.get("id") == track_id:
                return t
        listed = tracks()
        if 0 <= track_id < len(listed):
            return listed[track_id]
        return None

    @app.get("/api/sections/{track_id}")
    def api_get_sections(track_id: int):
        meta = _meta(track_id)
        if not meta:
            return []
        found = []
        if sec_path.exists():
            for line in sec_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("album") == meta["album"] and rec.get("track") == meta["track"]:
                    found.append({**rec, "role": canonical_role(rec.get("role"))})
        return found

    @app.get("/api/drafts")
    def api_drafts(album: str = "", track: str = ""):
        """Real MSA/Guess drafts for one song from `data/drafts.jsonl`. Never
        written back as keeper pins -- the UI shows them unheard for review."""
        path = lab_root / "data" / "drafts.jsonl"
        out = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (rec.get("album") or "") == album and (rec.get("track") or "") == track:
                    out.append(rec)
        return {"drafts": out}

    @app.post("/api/sections/{track_id}")
    async def api_save(track_id: int, request: Request):
        """Keeper-only save via `schema.stamp_box`. Writes `sections.jsonl`
        keepers (source human/guess-accepted AND heard); drops unheard boxes
        and raw `guess`/`msa-draft`; a heard draft is stamped
        `guess-accepted`. Same-role overlap >50ms fails the whole save."""
        meta = _meta(track_id)
        if not meta:
            return JSONResponse({"detail": "bad track id", "saved": 0}, status_code=400)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"detail": "body not json", "saved": 0}, status_code=400)
        sections = body.get("sections") if isinstance(body, dict) else body
        if not isinstance(sections, list):
            return JSONResponse({"detail": "need sections list", "saved": 0}, status_code=400)

        known = {"start", "end", "role", "layer", "form", "figure_id", "unique",
                 "instrument", "start_bar", "end_bar", "source", "heard", "album", "track"}
        keepers: list[dict] = []
        dropped_unheard = 0
        for idx, s in enumerate(sections):
            # Bad input rejects the WHOLE save (same contract as the same-role
            # overlap check below): a box with end <= start is exactly the
            # all-tiny-save bug CURRENT.md says to refuse, never repair.
            if not isinstance(s, dict):
                return JSONResponse(
                    {"detail": "bad box %d: not an object" % idx, "saved": 0},
                    status_code=400,
                )
            try:
                start = float(s.get("start"))
                end = float(s.get("end"))
            except (TypeError, ValueError):
                return JSONResponse(
                    {"detail": "bad box %d: start/end must be numbers" % idx, "saved": 0},
                    status_code=400,
                )
            if not (math.isfinite(start) and math.isfinite(end)):
                return JSONResponse(
                    {"detail": "bad box %d: start/end must be finite" % idx, "saved": 0},
                    status_code=400,
                )
            if end <= start:
                return JSONResponse(
                    {"detail": "bad box %d: end (%.3f) must be after start (%.3f)"
                               % (idx, end, start),
                     "saved": 0},
                    status_code=400,
                )

            if not s.get("heard"):
                dropped_unheard += 1  # dropped, but counted so the UI can warn
                continue
            raw_source = s.get("source")
            if raw_source not in SOURCES:
                # Fail closed: an unknown/missing source is never a human pin.
                return JSONResponse(
                    {"detail": "bad box %d: unknown source %r" % (idx, raw_source),
                     "saved": 0},
                    status_code=400,
                )
            source = "guess-accepted" if raw_source in _PROMOTABLE_SOURCES else raw_source

            try:
                rec = stamp_box(
                    start, end, s.get("role"),
                    source=source, figure_id=s.get("figure_id"), heard=True,
                    form=s.get("form"), unique=bool(s.get("unique")),
                    instrument=s.get("instrument"),
                    start_bar=s.get("start_bar"), end_bar=s.get("end_bar"),
                    extra={k: v for k, v in s.items() if k not in known},
                )
            except ValueError as exc:
                return JSONResponse(
                    {"detail": "bad box %d: %s" % (idx, exc), "saved": 0},
                    status_code=400,
                )
            rec["album"] = meta["album"]
            rec["track"] = meta["track"]
            keepers.append(rec)

        # Fill GP bars only when the map row is a real match and the box has
        # none. A GP parse failure just leaves them null -- never blocks Save.
        row = _resolved(track_id) or {}
        gp = row.get("gp_path") or row.get("gp")
        if gp and Path(gp).exists() and (row.get("match") or "").lower() in {"yes", "y", "1", "true"}:
            from .extract import bars_for_times

            for rec in keepers:
                if rec.get("start_bar") is None or rec.get("end_bar") is None:
                    try:
                        start_bar, end_bar = bars_for_times(Path(gp), rec["start"], rec["end"])
                    except Exception:
                        start_bar = end_bar = None
                    if start_bar is not None and rec.get("start_bar") is None:
                        rec["start_bar"] = start_bar
                    if end_bar is not None and rec.get("end_bar") is None:
                        rec["end_bar"] = end_bar

        overlaps = same_role_overlaps(keepers)
        if overlaps:
            i, j, role = overlaps[0]
            lo = max(keepers[i]["start"], keepers[j]["start"])
            hi = min(keepers[i]["end"], keepers[j]["end"])
            return JSONResponse(
                {
                    "detail": "same-role overlap: %s boxes overlap %.2f-%.2fs" % (role, lo, hi),
                    "overlaps": [{"role": r, "i": x, "j": y} for x, y, r in overlaps],
                    "saved": 0,
                },
                status_code=400,
            )

        # Read every OTHER track's rows. A malformed existing line is skipped
        # and COUNTED (reported back), never a silent drop -- one bad line must
        # not permanently block saves for every track.
        old: list[dict] = []
        malformed_lines: list[int] = []
        if sec_path.exists():
            for lineno, line in enumerate(
                sec_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines.append(lineno)
                    continue
                if not isinstance(rec, dict):
                    malformed_lines.append(lineno)
                    continue
                if rec.get("album") == meta["album"] and rec.get("track") == meta["track"]:
                    continue
                old.append(rec)

        # One-step undo: keep the previous file as `sections.jsonl.bak` before
        # replacing it (best-effort; never blocks a save).
        backup_path = sec_path.with_name(sec_path.name + ".bak")
        if sec_path.exists():
            try:
                bak_tmp = backup_path.with_name(backup_path.name + ".tmp")
                bak_tmp.write_bytes(sec_path.read_bytes())
                bak_tmp.replace(backup_path)
            except OSError:
                pass

        # Atomic replace: a failure here leaves the original untouched.
        try:
            _atomic_write_jsonl(sec_path, old + keepers)
        except OSError as exc:
            return JSONResponse(
                {"detail": "save failed, sections.jsonl left unchanged: %s" % exc,
                 "saved": 0},
                status_code=500,
            )
        try:
            from .learn import record

            record(lab_root, meta["album"], meta["track"], keepers)
        except Exception:
            pass
        body: dict = {"saved": len(keepers), "path": str(sec_path),
                      "dropped_unheard": dropped_unheard,
                      "backup": str(backup_path)}
        if malformed_lines:
            body["malformed_lines_skipped"] = len(malformed_lines)
            body["malformed_line_numbers"] = malformed_lines
        return body

    @app.post("/api/ingest")
    async def api_ingest(band: str = Form("new_band"), files: list[UploadFile] = File(...)):
        if not flac_root or not gp_root:
            return JSONResponse({"detail": "BOO_FLAC_ROOT / BOO_GP_ROOT missing"}, status_code=400)
        drop = lab_root / "work" / "drop" / band.replace(" ", "_")
        drop.mkdir(parents=True, exist_ok=True)
        saved = []
        for up in files:
            name = Path(up.filename or "file").name
            dest = drop / name
            data = await up.read()
            dest.write_bytes(data)
            saved.append(str(dest))
        from .catalogue import save_map, scan_roots
        from .ingest import ingest

        report = ingest(drop, flac_root, gp_root, band)
        drafted = scan_roots(flac_root, gp_root)
        save_map(lab_root / "data" / "map.csv", drafted)
        report["saved_uploads"] = saved
        report["map_rows"] = len(drafted)
        return report

    @app.get("/api/lyrics/{track_id}")
    def api_lyrics(track_id: int):
        row = _resolved(track_id)
        if not row:
            return {"lines": [], "note": "bad id"}
        from .lyrics import load_lyrics

        track = row.get("track") or ""
        cached = load_lyrics(lab_root, track)
        if cached.get("lines") or cached.get("plain_lines"):
            return cached
        return {"lines": [], "note": cached.get("note") or "press Lyrics to fetch"}

    @app.post("/api/lyrics/{track_id}")
    def api_lyrics_refresh(track_id: int):
        row = _resolved(track_id)
        if not row:
            return {"lines": [], "note": "bad id"}
        from .lyrics import build_lyrics
        from .stems import find_stem

        flac = row.get("flac_path")
        voc = find_stem(Path(flac), lab_root / "work" / "stems", "vocals") if flac else None
        return build_lyrics(lab_root, row.get("track") or "", Path(flac) if flac else None, voc)

    @app.post("/api/pack/{track_id}")
    def api_pack(track_id: int):
        row = _resolved(track_id)
        if not row:
            return JSONResponse({"detail": "bad id"}, status_code=400)
        from .pack import build_pack

        return build_pack(lab_root, [row], lab_root / "work" / "stems")

    @app.put("/api/lyrics/{track_id}")
    def api_lyrics_save(track_id: int, body: dict):
        row = _resolved(track_id)
        if not row:
            return {"lines": [], "note": "bad id"}
        from .lyrics import save_lyrics

        return save_lyrics(lab_root, row.get("track") or "", body.get("lines") or [])

    @app.post("/api/album/remove")
    async def api_album_remove(request: Request):
        """Real, guarded album removal. Deletes the album's FLAC/GP files
        (ONLY under BOO_FLAC_ROOT / BOO_GP_ROOT), drops its sections and
        holdout rows, then rescans map.csv. Requires explicit `confirm`."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"detail": "body not json"}, status_code=400)
        album = (body or {}).get("album")
        if not album:
            return JSONResponse({"detail": "need album"}, status_code=400)
        if not (body or {}).get("confirm"):
            return JSONResponse({"detail": "missing confirm"}, status_code=400)
        if flac_root is None:
            return JSONResponse({"detail": "BOO_FLAC_ROOT not set"}, status_code=400)

        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)] if map_path.exists() else []
        targets = [r for r in rows if (r.get("album") or "") == album]
        if not targets:
            return JSONResponse({"detail": "album not found in map.csv"}, status_code=404)

        tracks = {(r.get("track") or "") for r in targets}

        # Parse sections.jsonl BEFORE deleting anything: a malformed line
        # aborts the whole removal (fail closed) instead of crashing after
        # files are already gone, and the rewrite below is atomic.
        kept: list[dict] = []
        malformed: list[int] = []
        if sec_path.exists():
            for lineno, line in enumerate(
                sec_path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    malformed.append(lineno)
                    continue
                if not isinstance(rec, dict):
                    malformed.append(lineno)
                    continue
                if rec.get("album") == album and (rec.get("track") or "") in tracks:
                    continue
                kept.append(rec)
        if malformed:
            return JSONResponse(
                {"detail": "sections.jsonl has malformed line(s) %s; fix before "
                           "removing an album (nothing deleted)" % malformed},
                status_code=400,
            )

        deleted: list[str] = []
        skipped: list[str] = []
        file_dirs: set[Path] = set()
        gp_dirs: set[Path] = set()
        for r in targets:
            for value, root, dirs in (
                (r.get("flac_path") or r.get("flac"), flac_root, file_dirs),
                (r.get("gp_path") or r.get("gp"), gp_root, gp_dirs),
            ):
                if not value:
                    continue
                p = Path(value)
                if not p.exists():
                    continue
                if not _within(p, root):
                    skipped.append(str(p))
                    continue
                try:
                    p.unlink()
                    deleted.append(str(p))
                    dirs.add(p.parent)
                except Exception as e:
                    skipped.append(f"{p}: {e}")
            flac = r.get("flac_path") or r.get("flac")
            if flac:
                cover = _cover_near(flac)
                if cover and _within(cover, flac_root):
                    try:
                        cover.unlink()
                        deleted.append(str(cover))
                    except Exception:
                        pass

        removed_dirs = _prune_empty(file_dirs, flac_root) + _prune_empty(gp_dirs, gp_root)

        if sec_path.exists():
            write_jsonl_atomic(sec_path, kept)  # atomic: failure leaves it intact

        from .holdout import load_holdout, write_holdout

        holdout = load_holdout(lab_root)
        trimmed = {(a, t) for (a, t) in holdout if not (a == album and t in tracks)}
        if trimmed != holdout:
            write_holdout(lab_root, trimmed)

        from .catalogue import save_map, scan_roots

        drafted = scan_roots(flac_root, gp_root)
        save_map(map_path, drafted)

        return {
            "album": album,
            "tracks": len(tracks),
            "files": len(deleted),
            "dirs": len(removed_dirs),
            "skipped": skipped,
            "map_rows": len(drafted),
        }

    @app.post("/api/git/push")
    def api_git_push(body: dict | None = None):
        from .gitutil import push_lab

        msg = (body or {}).get("message") if isinstance(body, dict) else None
        return push_lab(lab_root, msg)

    return app
