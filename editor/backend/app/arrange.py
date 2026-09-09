"""Real, client-driven re-arrangement of an already-composed song.

Honest scope boundary (see the P9.1 plan): the engine has no capability to
regenerate a single section in isolation or blend a freshly-reordered
boundary -- real cross-section blending (X.24/X.28) runs once over the
whole generated sequence, not on a later user edit. `apply_order` below
does NOT attempt to fabricate that; it only rearranges which
ALREADY-GENERATED sections play, and in what order -- reorder, duplicate,
mute (omit), and solo (keep one) all reduce to the same real, uniform
"index into the original lists" mechanism.
"""
from __future__ import annotations


def apply_order(song: dict, order: list[int]) -> dict:
    """Real, pure rearrangement: builds a new `sections`/`sequence`/
    `tempo_map` by indexing `song`'s own real lists with `order` (each
    entry an index into the ORIGINAL section list; repeats duplicate a
    section, omissions drop one -- covers reorder/duplicate/mute/solo in
    one mechanism). Every other key in `song` (preset_id, judge, the
    fretboards) is carried through unchanged -- `judge` becomes stale
    against the new arrangement, which is real and expected (a full
    re-judge of an edited arrangement is a real, separate P9.3-era
    concern, not silently fabricated here).

    Raises `ValueError` for an empty `order` or any out-of-range index --
    fails closed rather than silently clamping or dropping a bad index.
    """
    if not order:
        raise ValueError("order must be non-empty")
    n = len(song["sections"])
    for i in order:
        if not (0 <= i < n):
            raise ValueError(f"order index {i} out of range for {n} real sections")

    rearranged = dict(song)
    rearranged["sections"] = [song["sections"][i] for i in order]
    rearranged["sequence"] = [song["sequence"][i] for i in order]
    rearranged["tempo_map"] = [song["tempo_map"][i] for i in order]
    return rearranged
