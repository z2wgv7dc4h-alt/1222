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
