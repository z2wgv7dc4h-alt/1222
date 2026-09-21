"""The one tab/pack precedence decision, read by Guess, figures, and extract
instead of each re-deriving it inline."""
from __future__ import annotations


def resolve_precedence(*, sync_ok: bool | None, has_gp_markers: bool,
                        has_pack: bool, has_gp: bool) -> dict:
    """One precedence decision for a song's structure spine, notes source,
    and clock basis.

    1. No trusted sync (`sync_ok` is not `True`) -> `spine="human"`: never
       propose tab/pack structure off an unverified or failed clock.
    2. Trusted sync + the tab's own GP section markers -> `spine="gp-marker"`;
       a pack may still layer kicks/pulse/meter cuts on top of that spine --
       those aren't spine, so they aren't decided here.
    3. Trusted sync + a pack but no GP markers -> `spine="pack"`.
    4. `notes_source`: `"gp"` when a readable GP exists (regardless of
       markers), else `"pack"` when a pack exists, else `None`.
    5. `clock`: `"gp-notated"` (raw GPIF/tempo-map seconds, no stretch) when
       sync isn't trusted; `"clock_ratio"` (sync's own stretch factor applied
       to GP-notated seconds) when trusted GP markers are the spine;
       `"pack-audio"` (the pack's own `start_sec_audio`) when trusted and the
       pack is the spine.

    Also returns the resolved `sync_ok` boolean, so a caller that only needs
    the trust gate (not spine/notes/clock) can read that alone.
    """
    ok = sync_ok is True
    if not ok:
        spine = "human"
        clock = "gp-notated"
    elif has_gp_markers:
        spine = "gp-marker"
        clock = "clock_ratio"
    elif has_pack:
        spine = "pack"
        clock = "pack-audio"
    else:
        spine = "human"
        clock = "gp-notated"
    notes_source = "gp" if has_gp else ("pack" if has_pack else None)
    return {
        "sync_ok": ok,
        "spine": spine,
        "notes_source": notes_source,
        "clock": clock,
    }


def tab_plan(lab_root, album, track, gp_path=None) -> dict:
    """One read-only resolution of a song's tab/pack precedence: which
    GP/pack files exist, the structure spine, the notes source, and
    which pack overlays (kicks/pulse/meter_cuts) may run. Wraps
    resolve_precedence (the pure spine/notes decision) with the actual
    file discovery, marker counting, and sync-row lookup that Guess and
    figures each used to redo inline. Never writes sections.jsonl."""
    from pathlib import Path as _Path

    from .guess import _prefer_tab, _sync_for
    from .tabnotes import discover_pack

    lab_root = _Path(lab_root) if lab_root is not None else None
    gp_use = _prefer_tab(_Path(gp_path) if gp_path else None, track)

    has_markers = False
    if gp_use is not None:
        try:
            if gp_use.suffix.lower() in (".gp", ".gpx"):
                from .extract import estimate_from_gpif

                g = estimate_from_gpif(gp_use)
            else:
                from .extract import estimate_from_gp

                g = estimate_from_gp(gp_use)
            has_markers = len(g.get("sections") or []) >= 1
        except Exception:
            has_markers = False

    pack_path = None
    if lab_root is not None:
        try:
            pack_path = discover_pack(lab_root, album, track)
        except Exception:
            pack_path = None

    sync_rec = _sync_for(lab_root, album, track) if lab_root is not None else None
    sync_ok_raw = sync_rec.get("sync_ok") if sync_rec is not None else None

    decision = resolve_precedence(
        sync_ok=sync_ok_raw, has_gp_markers=has_markers,
        has_pack=pack_path is not None, has_gp=gp_use is not None,
    )

    overlays_ok = decision["sync_ok"]
    return {
        "spine": decision["spine"],
        "notes": decision["notes_source"],
        "gp_path": str(gp_use) if gp_use is not None else None,
        "pack_path": str(pack_path) if pack_path is not None else None,
        "markers": has_markers,
        "sync_ok": decision["sync_ok"],
        "kicks": overlays_ok,
        "pulse": overlays_ok,
        "meter_cuts": overlays_ok,
    }
