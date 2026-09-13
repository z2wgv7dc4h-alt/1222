from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .catalogue import load_map, resolve

ROLES = [
    "intro",
    "build",
    "verse",
    "chorus",
    "breakdown",
    "solo",
    "interlude",
    "chill",
    "outro",
]


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

    _gp5_cache: dict = {"t": 0.0, "idx": {}}

    def _gp5_index() -> dict[str, Path]:
        root = Path(r"C:\Users\RIGGUSPIG\Desktop\god-tier-metal\reference\gp-tabs\gp5")
        if not root.exists():
            return {}
        try:
            stamp = root.stat().st_mtime
        except Exception:
            stamp = 0.0
        if _gp5_cache["idx"] and _gp5_cache["t"] == stamp:
            return _gp5_cache["idx"]
        idx: dict[str, Path] = {}
        try:
            for p in root.rglob("*.gp5"):
                idx[_norm_name(p.stem)] = p
        except Exception:
            return _gp5_cache["idx"] or idx
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
        path = row.get("flac_path")
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
        flac = row.get("flac_path")
        if not flac:
            raise HTTPException(404)
        from .stems import find_drums

        p = find_drums(Path(flac), lab_root / "work" / "stems")
        if not p:
            raise HTTPException(404, "no drums stem yet — press Guess")
        return FileResponse(p, media_type="audio/wav")

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
                    found.append(rec)
        return found

    @app.post("/api/sections/{track_id}")
    async def api_save(track_id: int, request: Request):
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
        old = []
        if sec_path.exists():
            for line in sec_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("album") == meta["album"] and rec.get("track") == meta["track"]:
                    continue
                old.append(rec)
        new = []
        for s in sections:
            try:
                start = float(s.get("start"))
                end = float(s.get("end"))
            except Exception:
                continue
            if end <= start:
                end = start + 0.25
            new.append(
                {
                    "album": meta["album"],
                    "track": meta["track"],
                    "start": start,
                    "end": end,
                    "role": s.get("role") or "verse",
                    "source": "human",
                }
            )
        sec_path.parent.mkdir(parents=True, exist_ok=True)
        with sec_path.open("w", encoding="utf-8") as f:
            for rec in old + new:
                f.write(json.dumps(rec) + "\n")
        try:
            from .learn import record

            record(lab_root, meta["album"], meta["track"], new)
        except Exception:
            pass
        return {"saved": len(new), "path": str(sec_path)}

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
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        if track_id < 0 or track_id >= len(rows):
            return {"lines": [], "note": "bad id"}
        from .lyrics import load_lyrics

        track = rows[track_id].get("track") or ""
        cached = load_lyrics(lab_root, track)
        if cached.get("lines"):
            return cached
        return {"lines": [], "note": cached.get("note") or "press Lyrics to fetch"}

    @app.post("/api/lyrics/{track_id}")
    def api_lyrics_refresh(track_id: int):
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        if track_id < 0 or track_id >= len(rows):
            return {"lines": [], "note": "bad id"}
        from .lyrics import build_lyrics
        from .stems import find_stem

        flac = rows[track_id].get("flac_path")
        voc = find_stem(Path(flac), lab_root / "work" / "stems", "vocals") if flac else None
        return build_lyrics(lab_root, rows[track_id].get("track") or "", Path(flac) if flac else None, voc)

    @app.post("/api/pack/{track_id}")
    def api_pack(track_id: int):
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        if track_id < 0 or track_id >= len(rows):
            return JSONResponse({"detail": "bad id"}, status_code=400)
        from .pack import build_pack

        return build_pack(lab_root, [rows[track_id]], lab_root / "work" / "stems")

    @app.put("/api/lyrics/{track_id}")
    def api_lyrics_save(track_id: int, body: dict):
        row = _resolved(track_id)
        if not row:
            return {"lines": [], "note": "bad id"}
        from .lyrics import save_lyrics

        return save_lyrics(lab_root, row.get("track") or "", body.get("lines") or [])

    @app.post("/api/git/push")
    def api_git_push(body: dict | None = None):
        from .gitutil import push_lab

        msg = (body or {}).get("message") if isinstance(body, dict) else None
        return push_lab(lab_root, msg)

    return app
