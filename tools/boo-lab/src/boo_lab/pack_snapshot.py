"""Pack span snapshots for Save keepers.

When a song has a trusted tab-notes pack (`sync_ok`), each heard keeper can
carry soft-fail `pack_*` stats for its [start, end) window — arts, pitch,
per-category note counts, active tracks. Never blocks Save; never invents
keepers. Machines draft; humans Save heard boxes.
"""
from __future__ import annotations

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


def span_pack_stats(pack, start: float, end: float) -> dict[str, Any]:
    """Soft stats for events with audio onset in [start, end)."""
    from . import tabnotes

    start = float(start)
    end = float(end)
    if end <= start:
        return {}

    evs = []
    for e in getattr(pack, "events", None) or []:
        try:
            t = float(pack.audio_sec(e))
        except Exception:
            continue
        if start <= t < end:
            evs.append(e)

    if not evs:
        return {
            "pack_note_source": "tabnotes",
            "pack_n_notes": 0,
            "pack_n_guitar_notes": 0,
            "pack_n_bass_notes": 0,
            "pack_n_drum_notes": 0,
            "pack_tracks_active": [],
        }

    by_cat = {"guitar": [], "bass": [], "drums": [], "other": []}
    tracks_active = sorted({int(getattr(e, "track", 0) or 0) for e in evs})
    for e in evs:
        by_cat.setdefault(_cat(e), []).append(e)

    guitar = by_cat.get("guitar") or []
    # Primary guitar track = most notes in span among guitar tracks
    g_by_tr: dict[int, list] = {}
    for e in guitar:
        g_by_tr.setdefault(int(getattr(e, "track", 0) or 0), []).append(e)
    guitar_track = max(g_by_tr, key=lambda k: len(g_by_tr[k])) if g_by_tr else None

    pitches = [int(e.pitch) for e in guitar if e.pitch is not None]
    n_g = len(guitar)
    palm = sum(1 for e in guitar if getattr(e, "palm_mute", False))
    dead = sum(1 for e in guitar if getattr(e, "dead", False))
    hammer = sum(1 for e in guitar if getattr(e, "hammer", False))

    out: dict[str, Any] = {
        "pack_note_source": "tabnotes",
        "pack_n_notes": len(evs),
        "pack_n_guitar_notes": n_g,
        "pack_n_bass_notes": len(by_cat.get("bass") or []),
        "pack_n_drum_notes": len(by_cat.get("drums") or []),
        "pack_tracks_active": tracks_active,
    }
    if guitar_track is not None:
        out["pack_guitar_track"] = int(guitar_track)
    if n_g:
        out["pack_palm_frac"] = round(palm / n_g, 4)
        out["pack_dead_frac"] = round(dead / n_g, 4)
        out["pack_hammer_frac"] = round(hammer / n_g, 4)
    if pitches:
        out["pack_pitch_min"] = min(pitches)
        out["pack_pitch_max"] = max(pitches)
        out["pack_pitch_mean"] = round(sum(pitches) / len(pitches), 2)
        out["pack_unique_pitches"] = len(set(pitches))
    return out


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
    """Mutate keepers in place with pack_* fields. Returns how many got a snapshot.

    Soft-fail: missing pack / bad sync / load errors → 0, keepers unchanged.
    """
    pack = _load_trusted_pack(lab_root, album, track)
    if pack is None or not keepers:
        return 0
    n = 0
    for rec in keepers:
        try:
            start = float(rec["start"])
            end = float(rec["end"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            stats = span_pack_stats(pack, start, end)
        except Exception:
            continue
        if not stats:
            continue
        for k, v in stats.items():
            rec.setdefault(k, v)
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
