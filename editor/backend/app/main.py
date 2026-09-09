"""P9.1 editor backend: a thin FastAPI wrapper around the real engine.

Per god-tier-metal-scope.md sec.10.5: local Python backend + local React
frontend, talking over localhost. This file adds NO generation logic of
its own -- every route calls straight into the real, already-tested
`engine` package (`presets.load_all_presets`, `song.compose_song`,
`midi_export.song_to_midi`); this app only serializes real results for the
browser and applies the client's real timeline arrangement (`arrange.py`).
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

# The engine package uses flat top-level imports (from song import ...,
# not from engine.song import ...) and isn't pip-installed -- same
# convention every script/test in this repo already relies on, just
# applied here via an explicit sys.path insert instead of running with
# engine/ as the cwd.
_ENGINE_DIR = Path(__file__).resolve().parents[3] / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from midi_export import song_to_midi
from presets import load_all_presets, resolve_preset_id
from song import compose_song

from app.arrange import apply_order
from app.serialize import summarize_preset, summarize_song

app = FastAPI(title="God Tier Metal Editor API")

# Local dev only -- the Vite dev server's default origin. Not intended to
# ever serve a non-local frontend (sec.10.5's own "local-only" decision).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ComposeRequest(BaseModel):
    preset_id: str
    seed: int
    num_sections: int = 8


class ExportRequest(ComposeRequest):
    order: list[int]


def _compose(req: ComposeRequest):
    presets = load_all_presets()
    resolved = resolve_preset_id(req.preset_id)
    if resolved not in presets:
        raise HTTPException(status_code=404, detail=f"unknown preset id: {req.preset_id!r}")
    try:
        song = compose_song(req.preset_id, seed=req.seed, num_sections=req.num_sections)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return song, presets[resolved]


@app.get("/api/presets")
def list_presets():
    presets = load_all_presets()
    return [summarize_preset(preset_id, preset) for preset_id, preset in sorted(presets.items())]


@app.post("/api/compose")
def compose(req: ComposeRequest):
    song, preset = _compose(req)
    return summarize_song(song, preset)


@app.post("/api/export-midi")
def export_midi(req: ExportRequest):
    song, _preset = _compose(req)
    try:
        rearranged = apply_order(song, req.order)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # song_to_midi writes to a real path (mido's own file-write API, not a
    # stream) -- a real tempfile round-trip, not a workaround for anything
    # wrong with song_to_midi itself.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "arrangement.mid"
        song_to_midi(rearranged, str(tmp_path))
        data = tmp_path.read_bytes()

    return StreamingResponse(io.BytesIO(data), media_type="audio/midi", headers={
        "Content-Disposition": 'attachment; filename="arrangement.mid"',
    })
