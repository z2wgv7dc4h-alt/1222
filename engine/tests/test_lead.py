import random

import pytest

from lead import generate_lead_line
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
