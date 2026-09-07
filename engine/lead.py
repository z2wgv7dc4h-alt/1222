"""Real lead/melodic line generation, driven by `theory.VoiceLeader`.

Per god-tier-metal-scope.md ## 4: "current 'lead' is literally the rhythm
riff transposed up an octave. Needs actual phrase-based melodic writing --
target-note (chord-tone) landing on strong beats ... occasional wide
sweep-style interval leaps."

This wires an ACTUAL `VoiceLeader` (not an ad hoc weight dict) to a real
preset's `vocab`, so the lead's interval choices carry the same style
character as everything else generated from that preset.
"""
from __future__ import annotations

import random

from theory import Scale, VoiceLeader

__all__ = ["generate_lead_line"]


def generate_lead_line(
    scale: Scale,
    vocab_weights: dict,
    motion: float,
    rng: random.Random,
    low: int,
    high: int,
    anchor: int,
    num_notes: int,
    stab_chance: float = 0.15,
    stab_interval: int = 12,
) -> list[int]:
    """A phrase of `num_notes` pitches: `VoiceLeader.move()` (blends
    chord-tone `pick()` and stepwise `walk()` by `motion`, exactly the way
    the preset's vocab is meant to be used) for most notes, with an
    occasional `stab()` leap as a sweep-style accent.

    `VoiceLeader.stab()` is deliberately exempt from register smoothing (see
    theory.py) and can land up to an octave above `high`; this function
    clamps every returned pitch into `[low, high]` regardless of which of
    `move`/`stab` produced it, so a lead line's register span is a hard
    guarantee callers (and tests) can rely on, not just true "most of the
    time."
    """
    if num_notes <= 0:
        raise ValueError("num_notes must be > 0")
    if not (0.0 <= stab_chance <= 1.0):
        raise ValueError("stab_chance must be within [0, 1]")

    vl = VoiceLeader(scale, weights=vocab_weights, rng=rng, low=low, high=high, anchor=anchor, motion=motion)
    notes: list[int] = []
    prev = None
    for i in range(num_notes):
        if i > 0 and rng.random() < stab_chance:
            pitch = vl.stab(prev=prev, interval=stab_interval)
        else:
            pitch = vl.move(prev=prev)
        pitch = max(vl.low, min(vl.high, pitch))
        notes.append(pitch)
        prev = pitch
    return notes
