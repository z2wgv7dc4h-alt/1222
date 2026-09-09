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
from presets import blend_presets, load_all_presets, resolve_preset_id
from reaper_project import song_to_rpp
from song import compose_song, compose_song_from_preset

from app.arrange import apply_order
from app.edits import apply_edits
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


class RegenEdit(BaseModel):
    section_position: int
    mode: str = "full"
    role: str | None = None
    hit_chance_bias: float = 0.0
    regen_seed: int = 0


class ComposeRequest(BaseModel):
    preset_id: str
    seed: int
    num_sections: int = 8
    order: list[int] | None = None
    edits: list[RegenEdit] = []
    # P9.2 -- Guided Mode's real knobs. `blend_with`/`blend_t` nudge
    # between `preset_id` and a second real preset (presets.blend_presets)
    # -- the same real mechanism covers "more djent"-style character
    # nudges and Guided's own energy/technicality/atmosphere dials, all as
    # "which preset am I leaning toward" rather than four separate
    # invented knobs. `blast_fill_chance`, when given, overrides the real
    # module default for the "blast-beat frequency" dial specifically.
    blend_with: str | None = None
    blend_t: float = 0.0
    blast_fill_chance: float | None = None


class ExportRequest(ComposeRequest):
    order: list[int]


def _resolve_preset(preset_id: str, presets: dict):
    resolved = resolve_preset_id(preset_id)
    if resolved not in presets:
        raise HTTPException(status_code=404, detail=f"unknown preset id: {preset_id!r}")
    return presets[resolved]


def _compose(req: ComposeRequest):
    presets = load_all_presets()
    preset = _resolve_preset(req.preset_id, presets)
    try:
        if req.blend_with is not None:
            other = _resolve_preset(req.blend_with, presets)
            blended = blend_presets(preset, other, req.blend_t)
            song = compose_song_from_preset(
                blended, seed=req.seed, num_sections=req.num_sections,
                blast_fill_chance=req.blast_fill_chance,
            )
            preset = blended
        else:
            song = compose_song(
                req.preset_id, seed=req.seed, num_sections=req.num_sections,
                blast_fill_chance=req.blast_fill_chance,
            )
        if req.order is not None:
            song = apply_order(song, req.order)
        song = apply_edits(song, req.edits, preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return song, preset


@app.get("/api/presets")
def list_presets():
    presets = load_all_presets()
    return [summarize_preset(preset_id, preset) for preset_id, preset in sorted(presets.items())]


@app.post("/api/compose")
def compose(req: ComposeRequest):
    song, preset = _compose(req)
    return summarize_song(song, preset)


def _write_and_stream(rearranged: dict, writer, filename: str, media_type: str) -> StreamingResponse:
    """Both `song_to_midi` and `song_to_rpp` write to a real path (not a
    stream) -- a real tempfile round-trip, not a workaround for anything
    wrong with either real, already-tested writer."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / filename
        writer(rearranged, str(tmp_path))
        data = tmp_path.read_bytes()
    return StreamingResponse(io.BytesIO(data), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
    })


@app.post("/api/export-midi")
def export_midi(req: ExportRequest):
    """Preview export -- the real MIDI a browser can actually play back
    (P9.1's Tone.js player)."""
    rearranged, _preset = _compose(req)
    return _write_and_stream(rearranged, song_to_midi, "arrangement.mid", "audio/midi")


@app.post("/api/export-rpp")
def export_rpp(req: ExportRequest):
    """P9.5 -- real Render (distinct from Preview): a real, already-tested
    Reaper project file (`reaper_project.song_to_rpp`, verified opening in
    the user's real installed Reaper earlier this session) over the exact
    same real arrange+edits pipeline as the MIDI preview -- same real
    arrangement, a different, DAW-importable real output format."""
    rearranged, _preset = _compose(req)
    return _write_and_stream(rearranged, song_to_rpp, "arrangement.rpp", "application/octet-stream")
