"""P9.3/P9.4 -- real, stateless replay of a client's regen-edit history.

Same "same seed = same bytes" law this whole project already follows,
extended to "same seed + edit history = same bytes": the backend never
holds session state -- the frontend keeps the full, real edit history
(which section, what mode, what regen_seed) and resends it on every
compose/export call, so the exact same arrangement can always be
reproduced from scratch.
"""
from __future__ import annotations

import random

from song import regenerate_section


def apply_edits(song: dict, edits: list, preset) -> dict:
    """Real, in-order replay of `edits` (each a real `RegenEdit`-shaped
    object with `.section_position`/`.mode`/`.role`/`.hit_chance_bias`/
    `.regen_seed`) via `song.regenerate_section` -- one real, deterministic
    regeneration per edit, applied to the arrangement the client actually
    sees (i.e. AFTER `arrange.apply_order`, so edits address real timeline
    positions, including duplicated blocks, not the original pre-
    arrangement section list)."""
    current = song
    for edit in edits:
        current = regenerate_section(
            current,
            edit.section_position,
            random.Random(edit.regen_seed),
            preset,
            mode=edit.mode,
            role=edit.role,
            hit_chance_bias=edit.hit_chance_bias,
        )
    return current
