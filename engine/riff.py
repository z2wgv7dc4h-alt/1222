"""Wires `chords.solve_chord` into the riff-generation side, and (P3.12)
harmonizes a motif's contour for a second rhythm guitar.

Per .claude/rules/anti-patterns.md: "a validator [or solver] that is not
called is not done." `chords.solve_chord` existed with no caller anywhere in
the riff/motif code before this file -- `voice_chord_section` is that real
call path, for a chord-voiced section (as opposed to single-note chugging),
and it is exercised end-to-end in tests/test_riff.py.
"""
from __future__ import annotations

from chords import solve_chord
from fretboard import Fretboard
from motif import Motif, render_motif, transpose
from theory import Scale

__all__ = ["voice_chord_section", "generate_chord_riff", "harmonize_line"]


# --- P3.11: chord-shape solver wired into riff generation --------------------


def voice_chord_section(
    root: int,
    intervals: tuple[int, ...],
    fretboard: Fretboard,
    max_span: int = 4,
) -> list[tuple[int, int]]:
    """Real fingering for one chord-voiced riff hit: calls `solve_chord`
    against `fretboard` and picks the fingering that sits lowest on the neck
    (most comfortable/idiomatic default). Raises ValueError if no fingering
    is reachable -- never fabricates one, matching `solve_chord`'s own
    "return [] rather than invent a shape" contract.
    """
    fingerings = solve_chord(root, intervals, fretboard, max_span=max_span)
    if not fingerings:
        raise ValueError(f"no reachable fingering for root={root} intervals={intervals}")
    return min(fingerings, key=lambda fingering: sum(fret for _string, fret in fingering))


def generate_chord_riff(
    cell: list[dict],
    root: int,
    intervals: tuple[int, ...],
    fretboard: Fretboard,
    max_span: int = 4,
) -> dict:
    """A chord-voiced riff section: the given rhythm `cell` (pitch-agnostic,
    from `rhythm.generate_rhythm`/a groove generator) all struck with ONE
    real fingering for `(root, intervals)` -- the realistic case for
    power-chord chugging, where the hand holds one shape through a rhythmic
    pattern rather than re-fretting every hit.
    """
    fingering = voice_chord_section(root, intervals, fretboard, max_span=max_span)
    return {"cell": cell, "fingering": fingering}


# --- P3.12 (optional): harmonized second guitar ------------------------------


def harmonize_line(
    motif: Motif,
    scale: Scale,
    start_degree: int = 0,
    harmony_degrees: int = 2,
) -> tuple[list[int], list[int]]:
    """Render `motif` twice against the same `scale`/`start_degree`: once as
    the original lead line, once shifted by `harmony_degrees` scale degrees
    (e.g. 2 for a diatonic third, 5 for a sixth) -- a second rhythm guitar
    harmonizing the lead at a fixed interval, sharing the exact same rhythm
    cell (`motif.cell` is untouched by `transpose`).
    """
    lead_pitches = render_motif(motif, scale, start_degree)
    harmony_motif = transpose(motif, harmony_degrees)
    harmony_pitches = render_motif(harmony_motif, scale, start_degree)
    return lead_pitches, harmony_pitches
