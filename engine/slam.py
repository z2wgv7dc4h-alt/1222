"""Slam-specific devices: pinch-harmonic accents and low-string chromatic creep.

Per god-tier-metal-scope.md ## 4: "Slam-specific devices: pinch-harmonic
accent simulation, low open-string chromatic 'creep', sudden half-time
drops." This covers the first two; both are deliberately small and distinct
from a plain chug pattern (see tests/test_slam.py).
"""
from __future__ import annotations

from fretboard import Fretboard

__all__ = ["mark_pinch_harmonics", "chromatic_creep"]


# --- (a) pinch harmonic accent simulation ------------------------------------


def mark_pinch_harmonics(cell: list[dict], velocity_base: int = 100, pinch_velocity: int = 127) -> list[dict]:
    """Return a copy of `cell` with every note carrying `pinch_harmonic`
    (bool) and `velocity` fields, and the phrase's structurally sensible
    accent point -- its LAST hit (end of phrase, the idiomatic place a slam
    riff punches a squeal) -- flagged `pinch_harmonic=True` with a velocity
    spike. Every other hit gets the plain `velocity_base` and
    `pinch_harmonic=False`; rests are copied unchanged plus the same two
    fields for shape-consistency, at velocity 0.
    """
    out = [dict(c) for c in cell]
    hit_indices = [i for i, c in enumerate(out) if not c["is_rest"]]
    for c in out:
        c["pinch_harmonic"] = False
        c["velocity"] = velocity_base if not c["is_rest"] else 0
    if hit_indices:
        last = hit_indices[-1]
        out[last]["pinch_harmonic"] = True
        out[last]["velocity"] = pinch_velocity
    return out


# --- (b) low open-string chromatic creep -------------------------------------


def chromatic_creep(
    fretboard: Fretboard,
    string: int = 0,
    steps: int = 6,
    direction: int = 1,
    start_fret: int = 0,
) -> list[tuple[int, int]]:
    """A slow chromatic creep on one string, one semitone (fret) at a time,
    starting at `start_fret` (0 = open) and moving by `direction` (+1 up,
    -1 down) for `steps` positions.

    Every returned position comes from `Fretboard.pitch_to_fret` -- never a
    fabricated (string, fret) pair -- so an unreachable creep (walking off
    either end of the neck) raises ValueError instead of silently producing
    an unplayable position. `prev` is threaded through each call so the
    solver's tie-break keeps the creep on the same string rather than
    hopping to a lower-numbered string that happens to reach the same pitch.
    """
    if not (0 <= string < len(fretboard.tuning)):
        raise ValueError(f"string out of range: {string}")
    if steps <= 0:
        raise ValueError("steps must be > 0")
    if direction not in (1, -1):
        raise ValueError("direction must be 1 or -1")

    open_note = fretboard.tuning[string]
    fret = start_fret
    prev = None
    positions: list[tuple[int, int]] = []
    for _ in range(steps):
        pitch = open_note + fret
        pos = fretboard.pitch_to_fret(pitch, max_fret=fretboard.max_fret, prev=prev)
        positions.append(pos)
        prev = pos
        fret += direction
    return positions
