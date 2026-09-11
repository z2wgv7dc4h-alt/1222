"""Atmosphere: Phase 7 -- cheap, zero-dependency placeholder pads/hits."""
from __future__ import annotations

from motif import Motif, render_motif
from theory import Scale

__all__ = [
    "PAD_PROGRAM",
    "ORCH_HIT_PROGRAM",
    "SYNTH_DOUBLE_PROGRAM",
    "pad_voicing",
    "stab_voicing",
    "synth_double",
    "find_accents",
]

# --- P7.1: GM program numbers + voicings ------------------------------------

# General MIDI program 90: "Pad 2 (warm)".
PAD_PROGRAM = 90
# General MIDI program 56: "Orchestra Hit".
ORCH_HIT_PROGRAM = 56
# General MIDI program 81: "Lead 2 (sawtooth)" -- a real, distinct
# synth-lead timbre for `synth_double`'s own real doubled-riff voice
# (song.py's dense-chug wiring), deliberately different from the pad/
# orch-hit/guitar/bass programs so it reads as its own voice, not a
# blend into one of the others.
SYNTH_DOUBLE_PROGRAM = 81


def _check_root(root: int) -> int:
    """Reject a non-integer/None root rather than silently producing
    garbage (e.g. `None + 7` raising deep inside a caller, or a float root
    quietly producing a fractional "MIDI pitch"). `bool` is rejected too --
    it's a `int` subclass in Python but never a meaningful pitch here."""
    if isinstance(root, bool) or not isinstance(root, int):
        raise TypeError(f"root must be an int MIDI pitch, got {root!r}")
    return root


def pad_voicing(root: int) -> list[int]:
    """Warm pad (GM 90) voicing: root + 5th + octave -- an open, ambient
    chord, three notes."""
    root = _check_root(root)
    return [root, root + 7, root + 12]


def stab_voicing(root: int) -> list[int]:
    """Orchestra hit (GM 56) voicing: root + 5th + octave + minor-10th --
    a small dramatic cluster (not full orchestration), four notes."""
    root = _check_root(root)
    return [root, root + 7, root + 12, root + 15]


# --- P7.2: synth doubles the motif's own contour ----------------------------


def synth_double(motif: Motif, scale: Scale, start_degree: int = 0, transpose: int = 0) -> list[int]:
    """Re-render `motif`'s contour for a synth voice by reusing
    `motif.render_motif` directly (no reimplemented pitch rendering), then
    shifting every pitch by `transpose` semitones -- e.g. `+12` for an
    octave-up doubling of the guitar riff (a common Born-of-Osiris-style
    synth-doubles-guitar device), or any other interval for a harmony line.
    `transpose=0` is a unison doubling.

    Because this calls the exact same `render_motif(motif, scale,
    start_degree)` the guitar itself would call, the synth line's rhythm/
    contour shape is guaranteed identical to the guitar's own rendering of
    that motif -- only a constant semitone offset can ever separate them.
    """
    pitches = render_motif(motif, scale, start_degree=start_degree)
    return [p + int(transpose) for p in pitches]


# --- P7.3: accent-synced orchestral stabs -----------------------------------

# Accent rule (documented, concrete):
#   1. The FIRST hit of the section is always an accent (e.g. the downbeat
#      of a breakdown).
#   2. The first hit immediately following a rest of duration-sum >=
#      REST_ACCENT_THRESHOLD_BEATS is also an accent (a "band drops out,
#      then everyone hits together" moment) -- a single long rest cell, or
#      a run of consecutive rest cells whose durations add up to at least
#      the threshold, both count.
# A section with zero hits (all rests) produces zero accents.
REST_ACCENT_THRESHOLD_BEATS = 1.0


def find_accents(cell: list[dict], root: int, threshold: float = REST_ACCENT_THRESHOLD_BEATS) -> list[dict]:
    """Walk a rhythm `cell` list (pitch-agnostic hit/rest dicts, e.g.
    `Motif.cell`) and mark which hit positions are structurally accented,
    per the rule documented above. Returns
    `[{"cell_index": int, "voicing": list[int]}, ...]`, one entry per
    accented hit, each carrying a fresh `stab_voicing(root)`.

    An all-rest `cell` (or empty `cell`) returns `[]` -- no fabricated
    accent, not a crash.
    """
    root = _check_root(root)
    if threshold < 0:
        raise ValueError("threshold must be >= 0")

    accents: list[dict] = []
    seen_first_hit = False
    rest_run = 0.0

    for i, c in enumerate(cell):
        if c.get("is_rest", True):
            rest_run += float(c.get("duration", 0.0))
            continue

        is_accent = (not seen_first_hit) or (rest_run >= threshold)
        if is_accent:
            accents.append({"cell_index": i, "voicing": stab_voicing(root)})
        seen_first_hit = True
        rest_run = 0.0

    return accents
