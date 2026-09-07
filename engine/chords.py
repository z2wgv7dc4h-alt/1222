"""Ground-up chord-shape solver.

New module, not a port: nothing in reference material actually derives a
chord voicing from theory (they hardcode intervals or a static shape
database) -- see god-tier-metal-scope.md ### 12.3. This derives fingerings
directly from `Fretboard.midi_to_frets`, so every returned note is both a
real chord tone and a real, reachable (string, fret) position. If no such
fingering exists, this returns [] -- never a fabricated one.
"""
from __future__ import annotations

from itertools import product

from fretboard import Fretboard

# A comfortable one-hand fret stretch tops out around 4 frets for most
# players in the low-to-mid neck (fingers 1-4, one fret each); open strings
# (fret 0) are excluded from the span since they cost no stretch.
MAX_FRET_SPAN = 4


def solve_chord(
    root: int,
    intervals: tuple[int, ...],
    fretboard: Fretboard,
    max_span: int = MAX_FRET_SPAN,
) -> list[list[tuple[int, int]]]:
    """Enumerate valid (string, fret) fingerings for a chord.

    `intervals` are semitone offsets from `root` (e.g. a power chord is
    `(0, 7, 12)`: root, 5th, octave). For each resulting chord tone, every
    `(string, fret)` position that reaches it on `fretboard` is a candidate;
    a fingering assigns one distinct string to each tone and is only kept if
    its fretted span (max fret - min fret among non-open positions) is at
    most `max_span`. Returns one list of (string, fret) pairs -- one per
    chord tone, in interval order -- for each valid fingering found.
    """
    if not intervals:
        raise ValueError("intervals must be non-empty")

    tones = [int(root) + int(iv) for iv in intervals]
    per_tone_positions = [fretboard.midi_to_frets(tone) for tone in tones]

    if any(not positions for positions in per_tone_positions):
        # At least one chord tone is unreachable anywhere on this fretboard
        # -- no fingering can be fabricated to cover it.
        return []

    fingerings: list[list[tuple[int, int]]] = []
    for combo in product(*per_tone_positions):
        strings_used = [string for string, _fret in combo]
        if len(set(strings_used)) != len(strings_used):
            continue  # a single string can't sound two chord tones at once
        fretted = [fret for _string, fret in combo if fret > 0]
        if fretted and (max(fretted) - min(fretted) > max_span):
            continue  # exceeds a realistic hand-stretch
        fingerings.append(list(combo))

    return fingerings
