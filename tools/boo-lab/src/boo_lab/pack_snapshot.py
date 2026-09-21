"""Pack pointers on Save + live note join for export/train.

Keepers stay human labels (album/track/start/end/role/...). When a trusted
tab-notes pack exists (`sync_ok`), Save only stamps a soft-fail `pack_id`
pointer (+ pack timeline bars if missing). Dense arts/pitch aggregates are
NOT copied onto keepers — recompute from the live pack at export/train time
via `notes_for_span` / `export_pack_notes`.

Never blocks Save. Never invents keepers. Machines draft; humans Save heard.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _sync_ok(lab_root, album: str, track: str) -> bool:
    from .tabnotes_drafts import _sync_ok as ok
    return ok(lab_root, album, track)


def _load_trusted_pack(lab_root, album: str, track: str):
    """Return loaded pack or None when missing / clock not trusted."""
    if not _sync_ok(lab_root, album, track):
        return None
    try:
        from . import tabnotes
        path = tabnotes.discover_pack(lab_root, album, track)
        if path is None:
            return None
        return tabnotes.load_pack(path)
    except Exception:
        return None


def load_pack_by_id(lab_root, pack_id: str):
    """Load a pack by id from data/tabnotes, or None."""
    if not pack_id:
        return None
    try:
        from . import tabnotes
        root = Path(lab_root) / "data" / "tabnotes"
        # exact folder or zip stem
        for cand in (root / pack_id, root / (pack_id + ".zip")):
            if cand.exists() and tabnotes.is_pack(cand):
                return tabnotes.load_pack(cand)
        for cand in tabnotes._pack_candidates(lab_root):
            try:
                pack = tabnotes.load_pack(cand)
            except Exception:
                continue
            if getattr(pack, "id", None) == pack_id:
                return pack
    except Exception:
        return None
    return None


def _cat(e) -> str:
    c = (getattr(e, "category", None) or "").lower()
    if c:
        return c
    if getattr(e, "is_percussion", False):
        return "drums"
    name = (getattr(e, "instrument_name", None) or "").lower()
    if "drum" in name:
        return "drums"
    if "bass" in name:
        return "bass"
    if "guitar" in name:
        return "guitar"
    return c or "other"


def bars_for_pack_span(pack, start: float, end: float) -> tuple[int | None, int | None]:
    """Measure numbers overlapping [start, end) from the pack timeline."""
    measures = list(getattr(pack, "measures", None) or [])
    if not measures:
        return None, None
    hit = []
    for m in measures:
        a = float(getattr(m, "start_sec_audio", 0.0) or 0.0)
        dur = float(getattr(m, "audio_duration_sec", 0.0) or 0.0)
        b = a + dur if dur > 0 else a
        if b <= start or a >= end:
            continue
        hit.append(int(getattr(m, "measure", 0)))
    if not hit:
        return None, None
    return min(hit), max(hit)


def attach_pack_snapshots(lab_root, album: str, track: str, keepers: list[dict]) -> int:
    """Stamp `pack_id` (+ bars) on keepers. Soft-fail. No dense aggregates."""
    pack = _load_trusted_pack(lab_root, album, track)
    if pack is None or not keepers:
        return 0
    pack_id = getattr(pack, "id", None) or ""
    if not pack_id:
        # fall back to folder name
        try:
            pack_id = Path(getattr(pack, "source_path", "") or "").name
        except Exception:
            pack_id = ""
    if not pack_id:
        return 0
    n = 0
    for rec in keepers:
        rec.setdefault("pack_note_source", "tabnotes")
        rec.setdefault("pack_id", pack_id)
        try:
            start = float(rec["start"])
            end = float(rec["end"])
        except (KeyError, TypeError, ValueError):
            n += 1
            continue
        if rec.get("start_bar") is None or rec.get("end_bar") is None:
            try:
                sb, eb = bars_for_pack_span(pack, start, end)
            except Exception:
                sb = eb = None
            if sb is not None and rec.get("start_bar") is None:
                rec["start_bar"] = sb
            if eb is not None and rec.get("end_bar") is None:
                rec["end_bar"] = eb
        n += 1
    return n


def _event_to_dict(pack, e) -> dict[str, Any]:
    try:
        t = float(pack.audio_sec(e))
    except Exception:
        t = None
    return {
        "t": round(t, 4) if t is not None else None,
        "track": int(getattr(e, "track", 0) or 0),
        "category": _cat(e),
        "measure": getattr(e, "measure", None),
        "onset_beat": getattr(e, "onset_beat", None),
        "duration_beats": getattr(e, "duration_beats", None),
        "pitch": getattr(e, "pitch", None),
        "string": getattr(e, "string", None),
        "fret": getattr(e, "fret", None),
        "palm_mute": bool(getattr(e, "palm_mute", False)),
        "dead": bool(getattr(e, "dead", False)),
        "hammer": bool(getattr(e, "hammer", False)),
        "bend": bool(getattr(e, "bend", False)),
        "slide": getattr(e, "slide", None),
        "harmonic": bool(getattr(e, "harmonic", False)),
        "instrument": getattr(e, "instrument_name", None) or "",
    }


def notes_for_span(pack, start: float, end: float, *,
                   category: str | None = None,
                   track: int | None = None) -> list[dict[str, Any]]:
    """Live note sequence for [start, end) from the pack (source of truth)."""
    start = float(start)
    end = float(end)
    if end <= start:
        return []
    out = []
    for e in getattr(pack, "events", None) or []:
        if track is not None and int(getattr(e, "track", -1)) != int(track):
            continue
        if category is not None and _cat(e) != category.lower():
            continue
        try:
            t = float(pack.audio_sec(e))
        except Exception:
            continue
        if start <= t < end:
            out.append(_event_to_dict(pack, e))
    out.sort(key=lambda r: (r.get("t") is None, r.get("t") or 0.0, r.get("track") or 0))
    return out


def join_keeper_notes(lab_root, keeper: dict) -> dict[str, Any]:
    """Join one keeper to live pack notes. Soft-fail empty notes list."""
    album = keeper.get("album") or ""
    track = keeper.get("track") or ""
    pack_id = keeper.get("pack_id") or ""
    pack = None
    if pack_id:
        pack = load_pack_by_id(lab_root, pack_id)
    if pack is None:
        pack = _load_trusted_pack(lab_root, album, track)
    try:
        start = float(keeper["start"])
        end = float(keeper["end"])
    except (KeyError, TypeError, ValueError):
        return {"keeper": keeper, "pack_id": pack_id or None, "notes": [], "error": "bad span"}
    if pack is None:
        return {"keeper": {
            "album": album, "track": track, "start": start, "end": end,
            "role": keeper.get("role"), "figure_id": keeper.get("figure_id"),
            "pack_id": pack_id or None,
        }, "notes": [], "error": "no pack"}
    notes = notes_for_span(pack, start, end)
    return {
        "album": album,
        "track": track,
        "start": start,
        "end": end,
        "role": keeper.get("role"),
        "figure_id": keeper.get("figure_id"),
        "pack_id": getattr(pack, "id", None) or pack_id,
        "n_notes": len(notes),
        "notes": notes,
    }


def export_pack_notes(lab_root, out_path=None) -> dict:
    """Write one JSONL row per keeper with live-joined pack notes.

    Default: `work/pack-notes/keepers-notes.jsonl`. Skips songs with no pack.
    Never writes sections.jsonl.
    """
    from .schema import load_section_rows

    lab_root = Path(lab_root)
    sec = lab_root / "data" / "sections.jsonl"
    out = Path(out_path) if out_path else lab_root / "work" / "pack-notes" / "keepers-notes.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = load_section_rows(sec) if sec.exists() else []
    written = 0
    skipped = 0
    with out.open("w", encoding="utf-8") as f:
        for rec in rows:
            joined = join_keeper_notes(lab_root, rec)
            if joined.get("error") == "no pack" or not joined.get("notes"):
                skipped += 1
                # still write pointer rows with empty notes? skip empty for train purity
                if joined.get("error") == "no pack":
                    continue
            f.write(json.dumps(joined, ensure_ascii=False) + "\n")
            written += 1
    return {"written": written, "skipped": skipped, "path": str(out)}
