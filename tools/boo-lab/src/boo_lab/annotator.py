from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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

    def tracks():
        if not map_path.exists():
            return []
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        out = []
        for i, r in enumerate(rows):
            out.append(
                {
                    "id": i,
                    "album": r.get("album"),
                    "track": r.get("track"),
                    "tuning": r.get("tuning"),
                    "has_flac": bool(r.get("flac_path") and Path(r["flac_path"]).exists()),
                    "has_gp": bool(r.get("gp_path") and Path(r["gp_path"]).exists()),
                }
            )
        return out

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (static / "annotator.html").read_text(encoding="utf-8")

    @app.get("/api/tracks")
    def api_tracks():
        return {"roles": ROLES, "tracks": tracks()}

    @app.get("/api/audio/{track_id}")
    def api_audio(track_id: int):
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        if track_id < 0 or track_id >= len(rows):
            raise HTTPException(404)
        path = rows[track_id].get("flac_path")
        if not path or not Path(path).exists():
            raise HTTPException(404, "flac missing — set BOO_FLAC_ROOT and map.csv")
        return FileResponse(path, media_type="audio/flac")

    @app.get("/api/estimate/{track_id}")
    def api_estimate(track_id: int):
        rows = [resolve(r, flac_root, gp_root) for r in load_map(map_path)]
        if track_id < 0 or track_id >= len(rows):
            raise HTTPException(404)
        path = rows[track_id].get("flac_path")
        if not path or not Path(path).exists():
            raise HTTPException(404, "flac missing")
        try:
            from .structure import run_allin1, segments_from_allin1
        except Exception as e:
            raise HTTPException(501, f"structure helpers missing: {e}")
        try:
            payload = run_allin1(Path(path))
        except Exception as e:
            raise HTTPException(501, f"allin1 failed (pip install allin1): {e}")
        segs = segments_from_allin1(payload)
        return {
            "bpm": payload.get("bpm"),
            "sections": [
                {
                    "role": s.get("role") or s.get("label") or "verse",
                    "start": s["start"],
                    "end": s["end"],
                    "source": "allin1",
                }
                for s in segs
            ],
        }

    @app.get("/api/sections/{track_id}")
    def api_get_sections(track_id: int):
        meta = tracks()[track_id]
        found = []
        if sec_path.exists():
            for line in sec_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("album") == meta["album"] and rec.get("track") == meta["track"]:
                    found.append(rec)
        return found

    class SaveBody(BaseModel):
        sections: list[dict]

    @app.post("/api/sections/{track_id}")
    def api_save(track_id: int, body: SaveBody):
        meta = tracks()[track_id]
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
        for s in body.sections:
            new.append(
                {
                    "album": meta["album"],
                    "track": meta["track"],
                    "start": float(s["start"]),
                    "end": float(s["end"]),
                    "role": s.get("role") or "verse",
                    "source": "human",
                }
            )
        sec_path.parent.mkdir(parents=True, exist_ok=True)
        with sec_path.open("w", encoding="utf-8") as f:
            for rec in old + new:
                f.write(json.dumps(rec) + "\n")
        return {"saved": len(new)}

    return app
