"""Real per-bar tonal-center progression -- X.30, the second half of the
Metalerator verse/chorus finding (the first half, X.29, wired verse/chorus
as real structure-graph roles).

Ported per PORTS.md from `reference/metalerator/metalerator/misc/
generate_song.py`'s real `CHORD_PROGRESSIONS` table and `rhythm_guitar/
chorus/chorus.py`'s own (denser) table of the same shape: a named, real
4-bar sequence of scale-degree offsets from the song's tonic. The source's
own real device: `set_root_note(bar) = self.current_scale[self.
progression[bar]]` -- each bar's riff root is looked up fresh from
`progression[bar]`, not one fixed root held for the whole section. This
project has never modulated a tonal center anywhere; every section has held
one fixed `start_degree` (from `theory.arc()`) the whole way through --
directly answers `god-tier-metal-scope.md` sec.2 ("Key/tonal-center
modulation across sections... needs a concept of home key vs modulated key
per section") and sec.14.2 item 5, both OPEN until now.

This module only adds a per-bar ANCHOR on top of `motif.render_motif`'s
existing per-hit rendering -- `motif.py` itself is untouched. Real,
additive-on-top-of-`start_degree` design (not a replacement): a section's
existing `arc_row["start_degree"]` anchor still applies, the progression
modulates AROUND it, consistent with this project's existing all-additive
degree-stacking convention (base_degree + delta + register already stack
this way everywhere else in `song.py`).
"""
from __future__ import annotations

from motif import Motif
from theory import Scale

__all__ = [
    "VERSE_PROGRESSIONS",
    "CHORUS_PROGRESSIONS",
    "degree_for_bar",
    "render_motif_with_progression",
    "pitches_per_cell_with_progression",
]

# Real, ported verbatim (scale-degree offsets per bar) from
# reference/metalerator/metalerator/misc/generate_song.py.
VERSE_PROGRESSIONS: dict[str, list[int]] = {
    "verse_0": [0, 0, 0, 0],
    "verse_1": [0, 0, 5, 4],
    "verse_2": [0, 0, 5, 3],
    "verse_3": [0, 0, 5, 6],
    "verse_4": [0, 0, 4, 2],
    "verse_5": [3, 3, 5, 4],
    "verse_6": [0, 0, 2, 3],
}

# Real, ported verbatim from
# reference/metalerator/metalerator/rhythm_guitar/chorus/chorus.py's own
# CHORD_PROGRESSIONS table (a different, denser real set than verse's).
CHORUS_PROGRESSIONS: dict[str, list[int]] = {
    "chorus_0": [0, 0, 5, 4],
    "chorus_1": [0, 0, 5, 3],
    "chorus_2": [0, 0, 5, 6],
    "chorus_3": [0, 0, 4, 2],
    "chorus_4": [3, 3, 5, 4],
}


def degree_for_bar(progression: list[int], bar_index: int) -> int:
    """The real scale-degree offset for `bar_index`: `progression[bar_index
    % len(progression)]` -- modulo-wrapped so this also works for a preset
    with more bars than the source's fixed 4-bar progressions (the source
    never needed this since its riffs were always fixed at 4/8 bars)."""
    if not progression:
        raise ValueError("progression must be non-empty")
    return progression[bar_index % len(progression)]


def render_motif_with_progression(
    motif: Motif,
    scale: Scale,
    progression: list[int],
    beats_per_bar: float,
    start_degree: int = 0,
) -> list[int]:
    """Real per-hit rendering, same as `motif.render_motif`
    (`scale.degree(anchor + delta)` per non-rest cell), except the anchor is
    `start_degree + degree_for_bar(progression, bar_index_of_this_cell)`
    instead of one fixed `start_degree` for the whole motif -- the bar's own
    real tonal center, not a single anchor held for the whole section. Bar
    index is tracked by walking cumulative beat position across
    `motif.cell`, the same way `song.pitches_per_cell` already walks it."""
    if beats_per_bar <= 0:
        raise ValueError("beats_per_bar must be > 0")
    out: list[int] = []
    pos = 0.0
    delta_iter = iter(motif.deltas)
    for cell in motif.cell:
        if not cell["is_rest"]:
            bar_index = int(pos // beats_per_bar)
            anchor = start_degree + degree_for_bar(progression, bar_index)
            out.append(scale.degree(anchor + next(delta_iter)))
        pos += cell["duration"]
    return out


def pitches_per_cell_with_progression(
    motif: Motif,
    scale: Scale,
    progression: list[int],
    beats_per_bar: float,
    start_degree: int = 0,
) -> list[int | None]:
    """Same real cell-alignment expansion `song.pitches_per_cell` does
    (`None` on rests, one entry per `motif.cell`), built on
    `render_motif_with_progression` instead of plain `render_motif`."""
    hit_pitches = iter(
        render_motif_with_progression(motif, scale, progression, beats_per_bar, start_degree=start_degree)
    )
    out: list[int | None] = []
    for cell in motif.cell:
        out.append(None if cell["is_rest"] else next(hit_pitches))
    return out
