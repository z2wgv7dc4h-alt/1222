import random

import pytest

from lead import generate_lead_line, generate_sequence_line
from presets import load_all_presets
from theory import Scale


# --- P3.7: VoiceLeader-driven lead line --------------------------------------


def test_lead_line_wired_to_real_preset_vocab_stays_in_register():
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)  # Ab2-ish root, arbitrary but in-range
    low, high = 50, 74
    rng = random.Random(42)

    notes = generate_lead_line(
        scale,
        preset.vocab.weights,
        preset.vocab.motion,
        rng,
        low=low,
        high=high,
        anchor=56,
        num_notes=40,
        stab_chance=0.25,
    )

    assert len(notes) == 40
    assert all(low <= n <= high for n in notes)


def test_lead_line_uses_stab_for_accents_without_leaving_register():
    # Force every eligible note to stab -- this is the code path most at
    # risk of leaving [low, high], since VoiceLeader.stab() is explicitly
    # exempt from register smoothing and can otherwise reach high + 12.
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)
    low, high = 50, 62  # a narrow span so an unclamped stab would overshoot
    rng = random.Random(3)

    notes = generate_lead_line(
        scale, preset.vocab.weights, preset.vocab.motion, rng,
        low=low, high=high, anchor=56, num_notes=20, stab_chance=1.0,
    )
    assert all(low <= n <= high for n in notes)


def test_lead_line_rejects_bad_input():
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)
    rng = random.Random(0)
    with pytest.raises(ValueError):
        generate_lead_line(scale, preset.vocab.weights, preset.vocab.motion, rng, 50, 70, 56, num_notes=0)
    with pytest.raises(ValueError):
        generate_lead_line(scale, preset.vocab.weights, preset.vocab.motion, rng, 50, 70, 56, num_notes=5, stab_chance=1.5)


# ---------------------------------------------------------------------------
# X.36 -- real melodic "sequence" device
# ---------------------------------------------------------------------------


def test_sequence_line_repeats_the_exact_same_relative_shape():
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)
    rng = random.Random(7)

    notes = generate_sequence_line(
        scale, preset.vocab.weights, rng,
        start_degree=0, motif_len=4, num_repeats=3, step_degrees=1,
    )
    assert len(notes) == 12

    # Real check: each repeat's own relative shape (degree deltas between
    # consecutive notes within a repeat) must be identical -- the whole
    # point of a "sequence" is the SAME shape, moved.
    def repeat_deltas(chunk):
        idx = [scale.index_of(p) for p in chunk]
        return [b - a for a, b in zip(idx, idx[1:])]

    repeats = [notes[i:i + 4] for i in range(0, 12, 4)]
    shapes = [repeat_deltas(r) for r in repeats]
    assert shapes[0] == shapes[1] == shapes[2]


def test_sequence_line_shifts_anchor_by_step_degrees_each_repeat():
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)
    rng = random.Random(7)

    notes = generate_sequence_line(
        scale, preset.vocab.weights, rng,
        start_degree=0, motif_len=1, num_repeats=4, step_degrees=2,
    )
    # motif_len=1 means each "repeat" is just scale.degree(start_degree +
    # r*step_degrees + delta) -- a single real, checkable pitch per repeat.
    degrees = [scale.index_of(p) for p in notes]
    assert degrees[1] - degrees[0] == degrees[2] - degrees[1] == degrees[3] - degrees[2]


def test_sequence_line_rejects_bad_input():
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)
    rng = random.Random(0)
    with pytest.raises(ValueError):
        generate_sequence_line(scale, preset.vocab.weights, rng, 0, motif_len=0, num_repeats=3, step_degrees=1)
    with pytest.raises(ValueError):
        generate_sequence_line(scale, preset.vocab.weights, rng, 0, motif_len=4, num_repeats=0, step_degrees=1)


def test_sequence_line_negative_step_descends():
    preset = load_all_presets()["melodic"]
    scale = Scale(56, preset.scale)
    rng = random.Random(7)

    notes = generate_sequence_line(
        scale, preset.vocab.weights, rng,
        start_degree=10, motif_len=1, num_repeats=3, step_degrees=-1,
    )
    degrees = [scale.index_of(p) for p in notes]
    assert degrees[0] > degrees[1] > degrees[2]
