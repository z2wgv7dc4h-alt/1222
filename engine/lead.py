"""Real lead/melodic line generation, driven by `theory.VoiceLeader`."""
from __future__ import annotations

import random

from motif import degree_delta_for_interval
from theory import Scale, VoiceLeader, pick_pitch_interval_markov

__all__ = ["generate_lead_line", "generate_sequence_line"]


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
    markov: dict[int, dict[int, float]] | None = None,
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

    `markov`, when given (a real, corpus-derived first-order transition
    table -- see `reference_vocab.build_preset_from_corpus`), threads
    straight through to the `VoiceLeader` this builds internally, making
    every `pick()`-driven note (via `move()`) real corpus-sequence-aware
    instead of an independent marginal draw. `markov=None` (every preset
    that predates this feature) is byte-identical to before.
    """
    if num_notes <= 0:
        raise ValueError("num_notes must be > 0")
    if not (0.0 <= stab_chance <= 1.0):
        raise ValueError("stab_chance must be within [0, 1]")

    vl = VoiceLeader(
        scale, weights=vocab_weights, rng=rng, low=low, high=high, anchor=anchor,
        motion=motion, markov=markov,
    )
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


# X.36 -- real melodic "sequence" device: a short motif repeated at
# successively shifted scale positions. Direct evidence from a real,
# user-supplied reference MIDI ("born of osiris style midi.mid"): a real
# melodic passage sits inside the guitar track itself, a short shape
# repeating at shifting pitch positions (`72,75,79,75,72,67,72,75,79,80,
# 79,75,72,...`). Confirmed via web research (Fundamental Changes'
# "Writing Better Metal Riffs: Sequencing"; Riffhard's and Splice's guides
# to writing metal guitar solos) that this IS the real, textbook core
# solo/lead-writing technique -- a motif moved stepwise through the scale,
# not independent note-by-note choices the way `generate_lead_line` alone
# produces.
#
# Reuses real existing primitives, no new pitch-choice mechanism invented:
# the motif's own shape is drawn via `motif.pick_pitch_interval` +
# `motif.degree_delta_for_interval`, the EXACT same real weighted-interval-
# to-scale-degree-delta mechanism `motif.generate_motif`'s own pitch loop
# already uses. Mirrors `motif.render_motif`'s own convention: deltas are
# relative to the anchor, the anchor itself is never emitted directly
# unless a delta happens to be 0.
def generate_sequence_line(
    scale: Scale,
    vocab_weights: dict,
    rng: random.Random,
    start_degree: int,
    motif_len: int,
    num_repeats: int,
    step_degrees: int,
    markov: dict[int, dict[int, float]] | None = None,
) -> list[int]:
    """A real sequence: draw ONE short motif once (`motif_len` real
    weighted-interval scale-degree deltas from `vocab_weights`), then
    repeat that EXACT relative shape `num_repeats` times, each repeat's
    anchor shifted by `step_degrees` scale degrees from `start_degree` --
    the real "same shape, moved through the scale" technique. Returns a
    flat `list[int]` of `motif_len * num_repeats` real pitches.

    `markov`, when given (a real, corpus-derived first-order transition
    table), makes each pick AFTER the first depend on the PREVIOUS
    interval actually chosen, via `theory.pick_pitch_interval_markov` --
    the motif's own shape then reflects real corpus-observed note-to-note
    tendencies, not just independent marginal picks. `markov=None` is
    byte-identical to before."""
    if motif_len <= 0:
        raise ValueError("motif_len must be > 0")
    if num_repeats <= 0:
        raise ValueError("num_repeats must be > 0")

    deltas: list[int] = []
    degree_index = 0
    prev_interval: int | None = None
    for _ in range(motif_len):
        iv = pick_pitch_interval_markov(vocab_weights, rng, markov, prev_interval)
        d = degree_delta_for_interval(scale, degree_index, iv)
        deltas.append(d)
        degree_index += d
        prev_interval = iv

    notes: list[int] = []
    for r in range(num_repeats):
        pos = start_degree + r * step_degrees
        for d in deltas:
            pos += d
            notes.append(scale.degree(pos))
    return notes
